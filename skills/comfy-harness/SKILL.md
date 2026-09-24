---
name: comfy-harness
description: Comfy 专家团的调用规范：本地优先路由（默认 comfy-mcp，云端 comfy-cloud 仅作升级路径）、云端↔本地工具面映射、成本门禁、一次提交原则与产物落盘约定。调用任何 Comfy MCP 工具前使用。
---

# Comfy Harness — 团队调用规范（本地优先）

## 1. 连接：默认本地，云端仅升级

| | 本地 `comfy-mcp`（**默认**） | 云端 `comfy-cloud`（升级路径） |
|---|---|---|
| 传输 | stdio，宿主经 `scripts/comfy_mcp_bootstrap.py` 拉起 | HTTP `https://cloud.comfy.org/mcp` |
| 算力 | 本机 GPU，**零积分** | Comfy Cloud GPU，**生成计费** |
| 鉴权 | 无 | OAuth（`codex mcp login comfy-cloud`）或 `comfyui-` 前缀 API key |
| 产物 | `fetch_outputs` 直接落本地目录 | `get_output` 返回签名 URL + `curl` 命令 |
| 素材 | 工作流直接给文件路径 | `upload_file` 上传（24h 自动清理） |

**默认永远走本地。** 只有本地工具面确实没有等价能力时（见 §2 升级白名单）才升级到云端，
且升级前必须先说明「这一步要用云端：会把数据发给 Comfy Cloud、可能计费」并取得用户同意。

启动器只在 `comfy-mcp` 未安装时退出并给出安装指引；`comfy-cli` 与 ComfyUI 工作区的缺失只做提示、
不拦启动（`comfy-mcp` 自己暴露 `launch_comfyui`）。执行类工具调用前先 `server_info()` 确认服务在跑。

## 2. 工具面：云端 ↔ 本地映射

冻结的命令/技能文本写的是云端工具名。本地优先时按下表翻译：

| 冻结文本写的 | 本地 `comfy-mcp` | 处置 |
|---|---|---|
| `search_nodes` / `search_templates` / `search_models` / `get_node` / `wait_for_job` | 同名 | **直接本地**，免费 |
| `submit_workflow(workflow JSON)` | `run_workflow(workflow_path, wait)` | 映射：先把工作流落盘成 `workflow.json` 再调 |
| `get_job_status(prompt_id)` | `job_status` | 映射 |
| `get_output(prompt_id, description)` | `fetch_outputs(prompt_id, out_dir)` | 映射：产物直接落本地，**无签名 URL、无 curl**（铁律④ 本地分支） |
| `get_template` | `fetch_template` | 映射 |
| `upload_file` | — | 本地**直接给文件路径**，不上传（铁律⑤） |
| `cancel_job(prompt_id)` | — | 本地无等价（`stop_comfyui` 是停服务，不等于取消任务），只能等跑完；要取消须升级云端 |
| `partner_generate` | — | **升级云端**（铁律③） |
| `run_template(api_*)` | —（`fetch_template` + `run_workflow` 两步） | 升级云端，或本地手工两步 |
| `save_workflow` / `run_saved_workflow` | — | **升级云端** |
| `get_prompting_guide` | — | **升级云端** |
| `apply_slots` | — | **升级云端** |

**升级白名单**（本地确实没有，允许升级 `comfy-cloud`）：`partner_generate`、`upload_file`、
`run_template`、`save_workflow`、`run_saved_workflow`、`get_prompting_guide`、`apply_slots`、`cancel_job`。

本地独有增益，优先用：

- **`server_info()` 先调** —— 确认 ComfyUI 在跑、工作区在哪
- `launch_comfyui` / `stop_comfyui` —— 启动器不隐式拉起 ComfyUI，需要执行工具前先 `launch_comfyui`
- `list_nodes`、`validate_workflow`（提交前校验拓扑）、`watch_job`

## 3. 铁律

1. **本地零积分、云端才计费。** 本地发现与生成都不花钱；升级到云端前必须先告知用户代价
   （伙伴按次价 + 云端算力积分）并取得同意。云端发现类（搜模板/模型/节点）免费。
2. **一次提交**：提交后先持久化 `prompt_id`；fail/timeout/Unknown 上报 lead，绝不自动重提交。
   边界注：质量循环（见 `comfy-design-loop` 技能）的「下一轮」是携带评审反馈的**新意图提交**，
   不属于本条禁止的重试；但失败/超时/Unknown 的任务仍照本条上报 lead，不得循环重试。
3. **命名模型短路 = 显式云端升级。** 冻结文本说「命名 Flux/Kling/Seedance/DALL-E 等先试
   `partner_generate`」——那些是伙伴/API 专属，本地无等价。本地优先时不得默默升级：
   必须告知用户「该模型只在云端提供，需要升级并计费」，用户同意后才调 `partner_generate`。
   触发判据同时兼容冻结文本的两种说法：节点 category 以 **`api node/`**（命令体）或
   **`partner/`**（技能体）开头，两者都算。
   参数纠偏：`exclude_api=True` **不是真实参数**（技能体已证伪）；要收窄到 API 节点用
   `api_nodes_only: true`，而 `api_nodes_only: false` 是 no-op。模板名前缀也能分路由：
   `api_*` 是伙伴/API，其余（如 `video_*`）是 OSS。
4. **产物核验分两条路。** 云端：`get_output` 返回签名 URL 与可直接执行的 `curl`，**原样执行**
   （不重构 URL、不再编码、不剥 query 参数），下载后本地核验再验收。
   本地：`fetch_outputs(prompt_id, out_dir)` 直接落盘，核验文件存在且可读即可。
5. **素材引用分两条路。** 本地：工作流直接给文件路径。云端：用 `upload_file` 上传拿返回的文件名
   （24h 自动清理），工作流引用文件名、不写绝对路径。**云端 SaveImage 输出目录 ≠ LoadImage 输入目录**
   ——跨工作流复用产物必须重新 `upload_file`；本地无此限制。
6. **任务标识是 `prompt_id`。** 冻结文本只说 `prompt_id`（从不说 job id）；`run_workflow` 与
   `submit_workflow` 返回的都是它，本地 `job_status` / `fetch_outputs` 也用它。

## 4. 质量循环

多轮迭代（对照目标图迭代、逼近参考效果、按质量闭环收敛）hand off 到
**`comfy-design-loop`** 技能（本插件内置，随 comfy-design 安装）：
目标图锚定 → 逐轮生成 → 独立子代理评审 → 按退出判据收敛。
单轮一次性生成不需要它；循环全程仍受上述铁律约束。
