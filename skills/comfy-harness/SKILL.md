---
name: comfy-harness
description: Comfy 专家团的调用规范：本地优先路由（默认本地 comfy-mcp＝MetaBrain 融合版，云端 comfy-cloud 仅作升级路径）、云端↔本地工具面映射、成本门禁、一次提交原则与产物落盘约定。调用任何 Comfy MCP 工具前使用。
---

# Comfy Harness — 团队调用规范（本地优先）

## 1. 连接：默认本地，云端仅升级

| | 本地 `comfy-mcp`（**默认**，MetaBrain 融合版） | 云端 `comfy-cloud`（升级路径） |
|---|---|---|
| 传输 | stdio，宿主经 `scripts/comfy_mcp_bootstrap.py` 拉起（首次需 `scripts/setup_comfy_mcp.py` 装 venv） | HTTP `https://cloud.comfy.org/mcp` |
| 算力 | 本机 GPU（或 .env 指定的局域网主机），**零积分** | Comfy Cloud GPU，**生成计费** |
| 鉴权 | 无（目标 ComfyUI 须**已在运行**；本服务不会自行拉起它） | OAuth（`codex mcp login comfy-cloud`）或 `comfyui-` 前缀 API key |
| 产物 | `save_task_assets` 直接落本地目录 | `get_output` 返回签名 URL + `curl` 命令 |
| 素材 | 工作流直接给文件路径（跨机场景 `upload_assets`） | `upload_file` 上传（24h 自动清理） |

**默认永远走本地。** 只有本地工具面确实没有等价能力时（见 §2 升级白名单）才升级到云端，
且升级前必须先说明「这一步要用云端：会把数据发给 Comfy Cloud、可能计费」并取得用户同意。

启动器做三项预检：vendored venv 存在、`.env` 存在（首次自动生成默认值）、目标 ComfyUI 可达
（`COMFY_UI_SERVER_IP`，默认 `127.0.0.1:8188`，可指向局域网内任意主机）。ComfyUI 未运行时
启动器直接退出并给出指引——**先启动 ComfyUI 再调工具**。执行类工具调用前先
`get_system_status()` 确认服务在跑、显存余量。

## 2. 工具面：云端 ↔ 本地映射

冻结的命令/技能文本写的是云端工具名。本地优先时按下表翻译（本地工具面＝17 个工具（含补丁 #3 新增 4 个：free_memory/list_embeddings/list_local_templates/upload_mask））：

| 冻结文本写的 | 本地 MetaBrain 工具 | 处置 |
|---|---|---|
| `search_models` | `list_models(type_name)` | **映射**（本地模型清单；注册表搜索仍走云端） |
| `submit_workflow(workflow JSON)` | `queue_custom_prompt(workflow_name, api_json, is_async)` | **映射**：直接传 JSON 字符串，无需落盘；`workflow_name` 只用 ASCII |
| `get_job_status(prompt_id)` | `get_prompt_result(prompt_id)` | 映射 |
| `wait_for_job` | `get_prompt_result(prompt_id)` 轮询 | 映射 |
| `get_output(prompt_id, description)` | `save_task_assets(prompt_id, destination_dir)` | 映射：产物直接落本地，**无签名 URL、无 curl**（铁律④ 本地分支） |
| `cancel_job(prompt_id)` | `interrupt_prompt(prompt_id)` | **映射**（本地已可取消，无需升级云端） |
| `get_template` / `search_templates` / `search_nodes` / `get_node` | —（本地只有 `get_core_manual` 节点手册与 `get_workflows_catalog` 本地工作流目录） | 注册表检索**升级云端**（发现类免费）；本地工作流用 `get_workflows_catalog` |
| `upload_file` | 本地**直接给文件路径**；需把素材送进 ComfyUI 输入目录时 `upload_assets` | 本地优先（铁律⑤） |
| `partner_generate` | — | **升级云端**（铁律③） |
| `run_template(api_*)` | —（`queue_custom_prompt` 手工两步可近似） | 升级云端，或本地手工构造 JSON |
| `save_workflow` / `run_saved_workflow` | `save_custom_workflow` / 目录 + `queue_custom_prompt` | **映射**（本地目录即 ComfyUI 工作流目录） |
| `get_prompting_guide` | — | **升级云端** |
| `apply_slots` | — | **升级云端** |

**升级白名单**（本地确实没有，允许升级 `comfy-cloud`）：`partner_generate`、
`run_template`、`get_prompting_guide`、`apply_slots`、注册表版 `search_templates` /
`search_nodes` / `search_models`。（`cancel_job` 已有本地等价，不在白名单。）

本地独有增益，优先用：

- **`get_system_status()` 先调** —— ComfyUI 版本、GPU/显存余量
- **工作流即工具**：`get_workflows_catalog` → `mount_workflow` → `queue_prompt`——
  只调打了 `==名称==` 标记的工作流里 `=>参数` 暴露的参数，防幻觉、适合精确复用
- `get_workflow_API`（取工作流的 API JSON）、`save_custom_workflow`（保存）
- `list_models(type_name)`（checkpoints / loras / controlnet / vae …）

本地已知缺口（融合 roadmap，暂时按右列处置）：

- ComfyUI 启停（`launch/stop_comfyui` 类）——**没有**：要求 ComfyUI 先运行；确实需要拉起时
  由宿主 agent 用本机命令自行启动 ComfyUI，而不是等本服务
- 提交前拓扑校验（`validate_workflow` 类）——**没有**：提交错误由 ComfyUI 执行期报错兜底
- 模型下载管理——**没有**：由宿主 agent 自行下载放入模型目录

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
   本地：`save_task_assets(prompt_id, destination_dir)` 直接落盘，核验文件存在且可读即可。
5. **素材引用分两条路。** 本地：工作流直接给文件路径。云端：用 `upload_file` 上传拿返回的文件名
   （24h 自动清理），工作流引用文件名、不写绝对路径。**云端 SaveImage 输出目录 ≠ LoadImage 输入目录**
   ——跨工作流复用产物必须重新 `upload_file`；本地无此限制。
6. **任务标识是 `prompt_id`。** 冻结文本只说 `prompt_id`（从不说 job id）；`queue_custom_prompt`
   与 `submit_workflow` 返回的都是它，本地 `get_prompt_result` / `save_task_assets` /
   `interrupt_prompt` 也用它。
7. **本地调用的三条硬约束：**
   - `workflow_name` / client id **只用 ASCII**——非 ASCII 会炸 ComfyUI WebSocket 连接；
   - `queue_custom_prompt` 默认**同步等待**：短任务（SD1.5 出图约 10 秒）用 `is_async:"false"`，
     长任务（SDXL/视频/放大）用 `is_async:"true"` 提交后轮询 `get_prompt_result`；
   - 服务启动后工作流目录在**后台异步填充**（约每工作流 7 秒；大型工作流库首次约数分钟），
     `get_workflows_catalog` 返回空/不全时不是故障——等一会或直接用 `queue_custom_prompt`。
