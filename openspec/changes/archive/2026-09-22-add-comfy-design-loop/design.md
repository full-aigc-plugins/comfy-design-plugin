## Context

codegraph 与文档实测确认了三条硬约束和一个结构性优势：

1. **计费与一次提交**：comfy-cloud MCP 的生成面（`run_template` / `submit_workflow` / `partner_generate`）全部计费；harness 铁律②要求提交后持久化 job id、失败/超时/Unknown 一律上报 lead、绝不自动重提交。dream-loop「无预算就跑到退出判据」与「自动下一轮」在此不可直接成立。
2. **vendor 冻结面**：11 个 vendored 技能被 `skills.lock.json` 逐技能 sha256 钉死，`test_skill_vendor.py` 含在树篡改检测；`plugin-local-skills.json` 当前仅登记 `comfy-harness`。循环规范的唯一合法落点是插件本地面。
3. **域错配**：dream-loop 的 Build 主体是「改代码→截屏」（FPS、3D 资产、代码工程占其 workflow 文档七成篇幅），comfy 是「构造 workflow JSON→云端渲染」。可移植的是循环骨架与评审纪律，不是文本本身。
4. **结构性优势**：Comfy 工作流原生支持参考图输入（`upload_file` 24h + `LoadImage`/img2img 节点），target 图可以直接作为生成输入与评审对照——「目标锚定→以图证图」链路在 comfy 是所有插件里接线最短的。

## Decisions

### 独立插件本地技能，不扩写 harness

`comfy-harness` 的定位是调用规范速查（5 条铁律、30 行内）；循环规范 + 双 rubric + 台账约定约需独立 SKILL.md 与 `references/`。新技能按本仓 vendor 纪律登记进 `plugin-local-skills.json`，与 `comfy-harness` 并列；SKILL.md 控制在 500 行内，细则下沉 `references/`。跨技能引用一律用技能名 + 安装命令，不写相对路径。

### 轮语义：新意图提交，不是重试

循环的每一轮定义为「携带上一轮评审反馈的新 workflow/新 prompt」的新意图提交；失败、超时、Unknown 的任务不进入循环、不重试，照 harness 铁律②上报 lead。铁律②管「同一个 job 的命运」，循环管「下一个意图的诞生」——边界在两份文档中同句表述，避免双规范打架。

### 授权门禁：逐轮确认或显式预算预授权

默认每轮发起计费调用前确认；用户显式给出预算（金额或轮数上限）时整环预授权并写入 ledger。无授权不出轮，预算耗尽即停并交付当前最优产物。不采纳 dream-loop「无预算跑到退出判据」的行为。

### 评审独立性与 rubric

judge 必须是新上下文子代理（宿主 subagent 工具），输入仅三样：target 图、本轮本地产物、历史裁决摘要；不携带本轮 prompt 草稿、对话上下文或作者的自我评价。prompt 作者不得自评。图像 rubric 四轴：构图 0-3 / 光照 0-3 / 材质 0-3 / 细节 0-1，总 10 分允许小数；视频增加运动质量 0-3、时间一致性 0-3，总 16 分。反馈纪律沿用 dream-loop：每条 gap 必须点名具体差异与修法，禁止「不够好」式评语；注入上一轮分数与 gap 清单，回退必须降分、不得注水（反棘轮）。无子代理能力的宿主退化为「全新会话自评」，并在交付中显式标注独立性降级。

### 退出判据与熔断

- 达标：图像 ≥ 8/10、视频 ≥ 13/16，交付收工。
- stall approaching：连续 2 轮无提升，或同一 gap 连续 2 轮被点名——禁止继续微调，转为架构级重想（换模板、换模型档位、重构 workflow 拓扑）。
- stalled：架构级重想后仍无提升——停下，上报 lead/用户裁决。
- 预算耗尽：停下，交付当前最优并附 gap 清单。

stall 判定读 ledger 的逐轮分数与 gap 历史，不依赖对话记忆。

### 目标图锚定

用户提供 target 则直接用；否则在一次授权内生成：优先 `partner_generate` 命名模型，其次廉价 OSS checkpoint。提示词遵守反 concept-art 纪律——target 是「真实引擎截图级」的可达目标，不是概念艺术。已有旧产物时，先取旧产物作 baseline 参考生成「改良版」target，禁止发散重画。target 经 `upload_file` 进入工作流参考图输入，同时落盘 `.comfy-loop/target.png` 供 judge 对照。

### 产物回收即评审输入

每轮产物：`get_output` → 原样执行返回的签名 `curl` → 本地核验（铁律④⑤）→ 该文件即 judge 的「live screenshot」。不重构 URL、不再编码。

### 台账与工作目录

`.comfy-loop/`（进 gitignore）：`target.png`、`rounds/`（每轮 workflow JSON、产物、裁决）、`ledger.json`（预算与授权记录、逐轮分数、gap 历史、轮数计数）。

### 明确不移植

`fal-batch.mjs`（comfy-cloud 自带 `get_job_status` / `wait_for_job` / `cancel_job` 任务面，铁律②更严）、FPS 退出判据、按模型订阅分档（改为按预算分档）、任何形式的自动重试。

## Risks / Trade-offs

- 计费失控 → 逐轮/预算门禁 + 预算熔断兜底；最坏损失即授权上限。
- judge 视觉模型差异导致 rubric 打分漂移 → 首个真实任务人工抽查两轮后再放手；rubric 分数只作停走判据，不对外承诺绝对质量。
- rubric 苛刻导致早期低分 → 规范声明「低分 + 可执行 gap 清单」正是循环的预期产物，不是失败。
- 循环增加交付时长 → 预算与轮数上限由用户显式控制；单轮任务（一次性生成）完全不进入循环，行为与现状一致。
