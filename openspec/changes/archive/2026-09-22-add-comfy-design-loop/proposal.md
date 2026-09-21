## Why

插件的生成技能全部是「一次提交即交付」的单向流：prompt → workflow → 产物，没有质量评审与迭代面。用户对结果不满意时只能整段重跑、靠手动调 prompt 碰运气，且每一轮都是真实计费、花费不可控。`research/dream-loop`（MIT，@anshuc）验证了「目标图锚定 + 独立评审 + 退出阶梯」的闭环模式，但其 Build 主体是代码工程、假设图片生成近乎免费，且本仓 11 个 vendored 技能被 `skills.lock.json` sha 锁定不可修改——因此不能直接安装 dream-loop，只能以插件本地技能移植其机制。

## What Changes

- 新增插件本地技能 `skills/comfy-design-loop/`：质量循环规范（目标图锚定、轮语义、授权门禁、评审独立性、退出判据、`.comfy-loop/` 台账约定），并登记进 `plugin-local-skills.json`。
- `skills/comfy-harness/SKILL.md` 增补两处：铁律②边界注（循环的下一轮是携带评审反馈的新意图提交，不属于失败重试），以及指向 `comfy-design-loop` 的质量循环索引段。
- 引入 `.comfy-loop/` 工作目录（gitignore）与 `ledger.json` 台账：预算授权、逐轮产物与裁决、gap 历史。
- 明确不修改：11 个 vendored 技能与 `skills.lock.json`、hooks、commands、MCP 工具面、任何运行时行为；不移植 dream-loop 的 `fal-batch.mjs`、FPS 判据与按订阅分档。

## Capabilities

### New Capabilities

- `comfy-design-quality-loop`: Defines the requirements for an authorized, independently-judged generation quality loop over Comfy Cloud.

### Modified Capabilities

None.

## Impact

新增 `skills/comfy-design-loop/**`（SKILL.md + references/）；修改 `skills/comfy-harness/SKILL.md` 与 `plugin-local-skills.json`；`tests/` 补充注册与规范断言；README 技能计数更新；按仓库发版流程 bump（minor → 0.2.0）并同步 `full-aigc-plugins` 市场仓 catalog。`skills.lock.json` 与上游 sha 不变。
