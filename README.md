# PartMe.AI Comfy Plugin

Tri-platform plugin (Codex / ZCode / Kimi Code) that connects coding agents to **a local ComfyUI by default**: generate images, video, audio, and 3D, search models / nodes / templates, and run ComfyUI workflows through the local Comfy MCP (`comfy-mcp`) on your own GPU. The hosted Comfy MCP (`https://cloud.comfy.org/mcp`) stays available as an **opt-in escalation path** for the cloud-only tool surface (partner models, uploads, saved workflows).

> 内容主体 vendor 自 [Comfy-Org/comfy-skills](https://github.com/Comfy-Org/comfy-skills)（MIT），逐字保留、仅加平台适配包装。版本钉在 `upstream/comfy-skills.lock.json`。

## What's inside

| Component | Count | Source |
|---|---|---|
| Commands | 11 (`/comfy-generate-image`, `/comfy-generate-video`, …) | verbatim from upstream `claude-code/commands/` |
| Skills | 13 (same topics, model auto-trigger) | 11 verbatim from upstream `skills/`, wrapped in `SKILL.md` frontmatter; 2 plugin-local (`comfy-harness`, `comfy-design-loop`) |
| MCP | `comfy-mcp` (stdio, **default**) + `comfy-cloud` (HTTP, escalation) | local server from `pip install comfy-mcp`; cloud endpoint from upstream comfy-cloud plugin manifest |

Vendored bodies are **unmodified**; only platform packaging (frontmatter, manifests, hooks, commands) is added by this repository.

## Installation

### Codex

```bash
codex plugin marketplace add partme-ai/plugins
codex plugin add comfy-design@partme-ai
```

### ZCode

插件 → 添加插件市场 → `https://github.com/partme-ai/plugins` → 安装 `comfy`。

### Kimi Code CLI

```
/plugins marketplace https://raw.githubusercontent.com/partme-ai/plugins/main/kimi-marketplace.json
```

或 `/plugins` 面板直接添加本仓库 GitHub URL。

### China mirror (AtomGit)

If GitHub is slow or unreachable, install from the AtomGit mirror instead. The
commands are identical apart from the marketplace URL:

```bash
codex plugin marketplace add https://atomgit.com/partme-ai/partme-comfy-plugin.git --ref main
codex plugin add comfy-design@partme-ai
```

To install the whole partme-ai plugin catalog from the mirror in one step:

```bash
codex plugin marketplace add https://atomgit.com/partme-ai/plugins.git
codex plugin add comfy-design@partme-ai
```

Notes:

- The AtomGit source and the GitHub source share marketplace names, so adding
  one replaces the other. Switch back with
  `codex plugin marketplace add https://github.com/partme-ai/plugins.git`.
- For ZCode or Kimi, clone the mirror repository and register the local
  directory in the respective marketplace configuration.

## Local ComfyUI (default connection)

这是**默认路径**：跑在你自己的 GPU 上，发现与生成都不花积分，提示词与产物不出本机。

```bash
pip install comfy-mcp "comfy-cli>=1.14.0"
comfy install                # 创建工作区（或 comfy set-default <path>）
```

ComfyUI 服务本身不在启动器里隐式拉起：需要执行类工具前先 `comfy launch`，或让代理调
`comfy-mcp` 的 `launch_comfyui`。启动前建议先调 `server_info()` 确认服务在跑、工作区在哪。

宿主实际拉起的是 `scripts/comfy_mcp_bootstrap.py`：它做就绪预检并自动解析注入 `COMFY_BIN`，
缺依赖时给一条可操作诊断（而不是 `command not found`），齐了才把 stdio 交给 `comfy-mcp`。

## Comfy Cloud (optional / escalation path)

默认不连。只有本地工具面没有等价能力时（见下表）才升级到云端，升级前会说明「这一步会把数据
发给 Comfy Cloud、可能计费」并征求同意。凭据（升级时才需要）：

- **Codex**：`codex mcp login comfy-cloud`（OAuth），或 API key
- **ZCode**：userConfig 填 `comfy_api_key`（sensitive，注入 `X-API-Key` 头）
- **Kimi**：环境变量 `COMFY_API_KEY`（`bearerTokenEnvVar` 注入）

API key 在 platform.comfy.org/profile/api-keys 创建（前缀 `comfyui-`）。

云端额外提供的能力（本地没有）：伙伴/API 模型直连（`partner_generate`）、素材上传
（`upload_file`）、模板运行（`run_template`）、保存/运行已存工作流、`get_prompting_guide`、
`apply_slots`、`cancel_job`，以及云端 GPU 算力。

## Cloud ↔ local tool surface

冻结的命令/技能文本写的是云端工具名。本地优先时按 `comfy-harness` 技能的这张表翻译
（**诚实标注能力缺口**：8 个云端工具本地没有等价物）：

| 命令/技能文本写的 | 本地 `comfy-mcp` | 处置 |
|---|---|---|
| `search_nodes` / `search_templates` / `search_models` / `get_node` / `wait_for_job` | 同名 | 直接本地，免费 |
| `submit_workflow(workflow JSON)` | `run_workflow(workflow_path, wait)` | 映射：先落盘 `workflow.json` 再调 |
| `get_job_status(prompt_id)` | `job_status` | 映射 |
| `get_output(prompt_id, description)` | `fetch_outputs(prompt_id, out_dir)` | 映射：产物直接落本地，**无签名 URL、无 curl** |
| `get_template` | `fetch_template` | 映射 |
| `upload_file` | — | 本地直接给文件路径，不上传 |
| `cancel_job` | — | 本地无等价（`stop_comfyui` 是停服务），要取消须升级云端 |
| `partner_generate` | — | **升级云端** |
| `run_template(api_*)` | —（`fetch_template` + `run_workflow` 两步） | 升级云端，或本地手工两步 |
| `save_workflow` / `run_saved_workflow` | — | **升级云端** |
| `get_prompting_guide` | — | **升级云端** |
| `apply_slots` | — | **升级云端** |

本地独有增益：`server_info()`、`launch_comfyui` / `stop_comfyui`、`list_nodes`、
`validate_workflow`、`watch_job`。

> 注意：命名伙伴模型（Flux Pro / Kling / Seedance / DALL-E 等）**只在云端提供**。
> 命中这类请求时会明确告知需升级并计费，不会默默走云端。

## Commands

| Command | 作用 |
|---|---|
| `/comfy-generate-image` | 文生图 / 图生图 / 编辑（Flux、Nano Banana、DALL-E 等） |
| `/comfy-generate-video` | 文生视频 / 图生视频（Seedance、Kling、Luma 等） |
| `/comfy-generate-audio` | 音频生成 |
| `/comfy-generate-3d` | 3D 生成 |
| `/comfy-upscale-image` | 图像放大 |
| `/comfy-remove-background` | 去背景 |
| `/comfy-combine-people` | 人物合成 |
| `/comfy-search-models` | 搜索模型 |
| `/comfy-search-nodes` | 搜索节点 |
| `/comfy-search-templates` | 搜索工作流模板 |
| `/comfy-help` | 使用帮助 |

## Cost note

本地 `comfy-mcp` 的发现与生成**全免费**（用自己的 GPU 与电力）。只有升级到云端 `comfy-cloud`
才计费：发现类调用（搜模板/模型/节点）免费，**运行生成需要 Comfy Cloud 订阅或积分**
（新用户 5 次免费），伙伴/API 模型另按次计价。命令体 preserves 上游的 partner-API 直连路由
与审批语义，但默认不走云端。

<!-- FULL_STACK_DOC_START -->
## 项目定位与运行边界

`comfy-design-plugin` 是面向 Codex、ZCode 与 Kimi 的跨宿主插件。当前基础版本为 `0.2.0`，三个宿主清单分别是 `.codex-plugin/plugin.json`、`.zcode-plugin/plugin.json` 和 `kimi.plugin.json`。README 中的版本、技能数量和安装来源以这些清单、`skills.lock.json` 与正式 Release 为准。

```text
宿主请求
  │
  ▼
三端 manifest / command / skill discovery
  │
  ▼
插件本地 Harness（默认本地 comfy-mcp，云端 comfy-cloud 仅升级）
  │
  ├── 成功：本地产物 + 回执 + 哈希
  └── 失败：稳定错误 + 可恢复状态，不静默重试付费动作
```

### 能力边界

- 插件负责宿主适配、配置注入、可执行脚本和插件专属技能；
- 外部技能只能从不可变 Release 按 lock 同步，受管副本禁止直接修改；
- “安装成功”“manifest 被发现”“MCP/Hook 已加载”“供应商调用成功”是四个不同证据等级；
- 网络、付费生成、上传、覆盖、删除和发布不会因安装插件而自动获得授权；
- 本地优先：默认连接是本地 `comfy-mcp`，数据不出本机；升级到云端须先告知并获同意。

## 三端清单与技能供应链

| 宿主 | 清单 | 声明版本 |
|---|---|---|
| Codex | `.codex-plugin/plugin.json` | `0.2.0+codex.20260921` |
| ZCode | `.zcode-plugin/plugin.json` | `0.2.0` |
| Kimi | `kimi.plugin.json` | `0.2.0` |

| 外部技能包 | Release ref | Peeled SHA | 技能数 |
|---|---|---|---:|
| `comfy-skills` | `v0.1.0` | `7d21bb5d279d` | 11 |

插件专属技能：`comfy-harness`（调用规范，本地优先路由）、`comfy-design-loop`（生成质量循环：目标图锚定 → 独立评审 → 按退出判据收敛）。外部技能共 11 个；插件专属技能不进入 `skills.lock.json`。

## 验证与发布门禁

```bash
python3 scripts/vendor/skill_vendor.py check --offline
python3 scripts/vendor/skill_vendor.py check
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

发布前必须验证：三端基础版本一致、Codex build metadata 合法、受管技能在线/离线摘要一致、插件专属技能已声明、测试通过、市场安装源固定到 Release tag，并在干净环境检查加载结果。

## 安全与凭据

- 凭据只通过宿主的 sensitive 配置、环境变量或外部秘密系统注入；
- README、日志、错误和测试夹具不得包含真实 token；
- 网络请求必须有超时、状态分类和有限重试；付费异步任务先持久化 task ID，再允许查询恢复；
- 路径写入限制在批准目录，已有文件默认不得覆盖。

## 故障排查

| 现象 | 证据入口 | 处理 |
|---|---|---|
| 插件未发现 | 对应宿主 manifest、市场 pin、安装缓存 | 核对插件 ID、版本和 Release ref |
| 技能数量不一致 | `skills.lock.json`、`plugin-local-skills.json` | 运行 vendor check，禁止手工修受管副本 |
| MCP/Hook 未加载 | 宿主诊断、配置 Schema、可执行文件 | 区分配置缺失、工具缺失和运行时错误 |
| 本地 MCP 起不来 | `scripts/comfy_mcp_bootstrap.py` 的 stderr 预检诊断 | 按诊断逐项补 `comfy-mcp` / `comfy-cli` / 工作区 |
| 请求超时 | task ID、错误响应、超时配置 | 查询已有任务，不自动再次提交付费请求 |
| 发布后市场仍是旧内容 | tag、Release、市场生成器输出 | 校验 tag SHA 后重新生成和验证市场 |
<!-- FULL_STACK_DOC_END -->

## License

Apache-2.0 for the adapter code in this repository. Vendored skill/command content is MIT (Comfy-Org) — see `NOTICE` and `upstream/comfy-skills.lock.json`.
