---
name: comfy-design-loop
description: 多轮打磨 Comfy 生成结果的质量循环：先锚定一张目标图（target），逐轮生成并交由独立子代理按 rubric 评审，按退出判据收敛。当用户要求「对照目标图迭代」「多轮打磨/逼近参考效果」「按质量闭环收敛生成结果」，或一次性生成结果明显不达预期需要系统性返工时使用。单轮一次性生成不要使用本技能。
---

# Comfy Design Loop — 生成质量循环

受控的多轮生成循环：**目标图锚定 → 逐轮生成 → 独立评审 → 修复 → 按判据退出**。
每一步都在 `comfy-harness` 技能的铁律约束下进行（本地零积分/云端才计费、一次提交、
命名模型须显式升级云端、产物核验与素材引用都分本地/云端两条路）；本技能只增加循环边界，不豁免任何铁律。
默认全程走本地 `comfy-mcp`，只有 `comfy-harness` §2 的升级白名单里的工具才升级到 `comfy-cloud`。

## 何时进入 / 不进入

进入：用户明确要求迭代逼近某个视觉效果、多轮打磨、或首轮结果不达预期且用户同意返工。
不进入：单轮一次性生成；用户只要「随便生成一张看看」；预算或授权不支持第二轮。

## 0. 准备工作目录

在项目根创建 `.comfy-loop/` 并写入 `.gitignore`（若尚无）：

```text
.comfy-loop/
├── target.png              # 目标图
├── rounds/
│   └── NNN/                # 每轮一个三位数目录
│       ├── workflow.json   # 本轮提交的工作流（或 run_template 的模板 id + 参数）
│       ├── artifact.*      # 本地产物（本地 fetch_outputs 落盘；云端则是签名 URL 下载核验后的文件）
│       └── verdict.md      # 本轮评审结论
└── ledger.json             # 台账（见 §6）
```

循环状态只认台账。会话中断后恢复时，从 `ledger.json` 重建现场，不依赖对话记忆。

## 1. 目标图（target）

循环开始前必须有 target：

- 用户提供 → 直接用，存为 `.comfy-loop/target.png`。
- 用户没有 → 在**一次授权内**生成：优先 `partner_generate` 命名模型，其次廉价 OSS checkpoint。
  提示词遵守反 concept-art 纪律：target 是「真实结果截图级」的可达目标，
  禁止 concept art / cinematic / painting 等词——不可达的艺术图会让循环空转。
- 已有旧产物 → 先把旧产物作为 baseline 输入生成「改良版」target，禁止发散重画。

target 同时用于两处：作为工作流参考图输入（LoadImage / img2img），以及评审时的对照图。
本地直接把 `target.png` 的文件路径写进工作流；只有升级到云端时才需要先 `upload_file`
并引用返回的文件名。

## 2. 授权与预算门禁

- 默认**逐轮确认**：每轮发起任何**云端计费**调用（`run_template` / `submit_workflow` /
  `partner_generate`）前，向用户说明本轮意图与预计成本并获确认。
  本地 `run_workflow` 零积分，但仍要说明本轮意图（铁律①的本地分支）。
- 用户显式给出预算（金额或轮数上限）→ 整环预授权，写入 `ledger.json`，轮内不再打断；
  预算耗尽即停，交付当前最优产物并附 gap 清单。
- 无授权不出轮。不要把「循环继续」当作授权。

## 3. 轮语义：新意图提交，不是重试

每一轮 = 携带上一轮评审反馈的**新 workflow / 新 prompt** 的新意图提交。

- 同一 job 失败、超时、Unknown → **不重试、不进入下一轮**，按 `comfy-harness`
  铁律②持久化 job id 并上报 lead，循环暂停等用户决定。
- 铁律②管「同一个 job 的命运」，本循环管「下一个意图的诞生」——两者不冲突。

## 4. 产物回收与评审

1. 取产物并本地核验文件存在且可读。本地：`fetch_outputs(prompt_id, out_dir)` 直接落盘。
   云端：`get_output` 取产物 → **原样执行**返回的签名 `curl` 命令
   （铁律④：不重构 URL、不再编码）。
2. 产物存入 `rounds/NNN/artifact.*`。
3. 派**全新上下文的评审子代理**（宿主 subagent 工具），输入只有三样：
   target 图、本轮产物、历史裁决摘要（上轮分数 + gap 列表）。
   **不给**本轮 prompt 草稿、对话上下文、作者的自我评价；写 prompt 的主体不得自评。
4. 评审提示词：图像读 `references/rubric-image.md`，视频读 `references/rubric-video.md`。
5. 结论写入 `rounds/NNN/verdict.md` 并更新台账。
6. 无子代理能力的宿主：退化为「全新会话自评」，并在交付中显式标注独立性降级。

## 5. 退出判据

| 条件 | 判据 | 动作 |
|---|---|---|
| 达标 | 图像 ≥ 8/10；视频 ≥ 13/16 | 交付最新产物，收工 |
| stall approaching | 连续 2 轮无提升，或同一 gap 连续 2 轮被点名 | **禁止微调**；换模板、换模型档位、重构 workflow 拓扑等架构级重想 |
| stalled | 架构级重想后仍无提升 | 停下，交当前结果 + gap 清单，请用户裁决 |
| 预算耗尽 | 台账预算用完 | 停下，交付历史最优产物 + gap 清单 |

「历史最优」以台账中最高分轮次为准；无提升时不得用最新轮覆盖最优轮交付。

## 6. 台账 `ledger.json`

```json
{
  "loop_id": "<时间戳或用户名>",
  "created_at": "<ISO8601>",
  "budget": { "mode": "per-round | pre-authorized", "amount": null, "max_rounds": null, "spent": [] },
  "rounds": [
    { "n": 1, "job_id": "<prompt_id>", "artifact": "rounds/001/artifact.png",
      "score": 5.5, "gaps": ["主光方向与 target 相反：把 Key Light 移到画面左侧"], "at": "<ISO8601>" }
  ],
  "best": { "round": 1, "score": 5.5, "artifact": "rounds/001/artifact.png" },
  "status": "active | done | stalled | budget-exhausted"
}
```

stall 判定只读 `rounds[].score` 与 `gaps`，逐轮追加，永不回写历史轮。

## 7. 交付

循环结束时输出：最优产物路径、逐轮分数轨迹、未解决 gap 清单、花费记录（来自台账）、
以及（若走了降级评审）独立性说明。
