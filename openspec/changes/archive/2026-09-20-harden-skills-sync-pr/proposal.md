## Why

技能同步工作流在远端已存在 chore/skills-sync 分支时没有获取 lease 基线，导致 force-with-lease 以 stale info 失败；仓库缺少 skills-sync label 时，PR 创建也会失败。

## What Changes

- 在重建同步分支前获取远端分支引用，保留安全的 force-with-lease 语义。
- PR 创建不再依赖预先存在的 label。
- 保持 ref、peeled SHA、vendor hash 校验与 PR 审核边界不变。

## Capabilities

### New Capabilities

None. This is an infrastructure-only workflow correction and skip_specs: true is set.

### Modified Capabilities

None.

## Impact

仅影响 .github/workflows/skills-sync.yml 和本 OpenSpec 记录；不直接修改技能快照、插件版本或运行时行为。
