# PartMe.AI Comfy Plugin

Tri-platform plugin (Codex / ZCode / Kimi Code) that connects coding agents to **Comfy Cloud**: generate images, video, audio, and 3D, search models / nodes / templates, and run ComfyUI workflows through the hosted Comfy MCP (`https://cloud.comfy.org/mcp`).

> 内容主体 vendor 自 [Comfy-Org/comfy-skills](https://github.com/Comfy-Org/comfy-skills)（MIT），逐字保留、仅加平台适配包装。版本钉在 `upstream/comfy-skills.lock.json`。

## What's inside

| Component | Count | Source |
|---|---|---|
| Commands | 12 (`/comfy-generate-image`, `/comfy-generate-video`, …) | verbatim from upstream `claude-code/commands/` |
| Skills | 12 (same topics, model auto-trigger) | verbatim from upstream `skills/`, wrapped in `SKILL.md` frontmatter |
| MCP | `comfy-cloud` (HTTP, `https://cloud.comfy.org/mcp`) | from upstream comfy-cloud plugin manifest |

Vendored bodies are **unmodified**; only platform packaging (frontmatter, manifests, hooks, commands) is added by this repository.

## Installation

### Codex

```bash
codex plugin marketplace add partme-ai/plugins
codex plugin add comfy-design@partme-ai
```

First generation triggers OAuth login, or set an API key (created at platform.comfy.org/profile/api-keys, prefix `comfyui-`):

```bash
codex mcp login comfy-cloud
```

### ZCode

插件 → 添加插件市场 → `https://github.com/partme-ai/plugins` → 安装 `comfy`。

Optional userConfig: `comfy_api_key`（sensitive，注入 `X-API-Key` 头）。留空则按 OAuth 流程在首次调用时登录。

### Kimi Code CLI

```
/plugins marketplace https://raw.githubusercontent.com/partme-ai/plugins/main/kimi-marketplace.json
```

或 `/plugins` 面板直接添加本仓库 GitHub URL。凭据：设置环境变量 `COMFY_API_KEY`（`bearerTokenEnvVar` 注入）。

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

## Local ComfyUI path (optional)

云端路径无需本地安装。若要走本地 ComfyUI：

```bash
pip install "comfy-cli>=1.14.0"
comfy install        # 创建工作区（或 comfy set-default <path>）
comfy launch         # 运行类工具需要 ComfyUI 在跑
```

本地 stdio MCP（`comfy-mcp`）可另行按 [docs.comfy.org/agent-tools/mcp](https://docs.comfy.org/agent-tools/mcp) 接入。

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

发现类调用（搜模板/模型/节点）免费；**运行生成需要 Comfy Cloud 订阅或积分**（新用户 5 次免费）。命令体 preserves 上游的 partner-API 直连路由与审批语义。

<!-- FULL_STACK_DOC_START -->
## 项目定位与运行边界

`comfy-design-plugin` 是面向 Codex、ZCode 与 Kimi 的跨宿主插件。当前基础版本为 `0.1.2`，三个宿主清单分别是 `.codex-plugin/plugin.json`、`.zcode-plugin/plugin.json` 和 `kimi.plugin.json`。README 中的版本、技能数量和安装来源以这些清单、`skills.lock.json` 与正式 Release 为准。

```text
宿主请求
  │
  ▼
三端 manifest / command / skill discovery
  │
  ▼
插件本地 Harness 或供应商客户端
  │
  ├── 成功：本地产物 + 回执 + 哈希
  └── 失败：稳定错误 + 可恢复状态，不静默重试付费动作
```

### 能力边界

- 插件负责宿主适配、配置注入、可执行脚本和插件专属技能；
- 外部技能只能从不可变 Release 按 lock 同步，受管副本禁止直接修改；
- “安装成功”“manifest 被发现”“MCP/Hook 已加载”“供应商调用成功”是四个不同证据等级；
- 网络、付费生成、上传、覆盖、删除和发布不会因安装插件而自动获得授权。

## 三端清单与技能供应链

| 宿主 | 清单 | 声明版本 |
|---|---|---|
| Codex | `.codex-plugin/plugin.json` | `0.1.2+codex.20260919` |
| ZCode | `.zcode-plugin/plugin.json` | `0.1.2` |
| Kimi | `kimi.plugin.json` | `0.1.2` |

| 外部技能包 | Release ref | Peeled SHA | 技能数 |
|---|---|---|---:|
| `comfy-skills` | `v0.1.0` | `7d21bb5d279d` | 11 |

插件专属技能：`comfy-harness`。外部技能共 11 个；插件专属技能不进入 `skills.lock.json`。

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
| 请求超时 | task ID、错误响应、超时配置 | 查询已有任务，不自动再次提交付费请求 |
| 发布后市场仍是旧内容 | tag、Release、市场生成器输出 | 校验 tag SHA 后重新生成和验证市场 |
<!-- FULL_STACK_DOC_END -->

## License

Apache-2.0 for the adapter code in this repository. Vendored skill/command content is MIT (Comfy-Org) — see `NOTICE` and `upstream/comfy-skills.lock.json`.
