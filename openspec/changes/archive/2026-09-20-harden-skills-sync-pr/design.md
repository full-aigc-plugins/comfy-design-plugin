## Context

真实 release 验证显示同步内容与锁校验成功，但复用固定同步分支时 lease 信息缺失，或 PR label 不存在，导致升级链在最后阶段失败。

## Decisions

- 显式 fetch refs/heads/chore/skills-sync 到远端跟踪引用，然后继续使用 force-with-lease，不降级为无保护的 force。
- 删除硬编码 label 参数；分支和 PR 标题仍可清楚识别同步来源。
- 保留单一同步分支，避免并发 release 产生无限分支。

## Verification

使用静态 workflow 断言、YAML 解析、OpenSpec strict validation，并以 Dreamina/Maya 的真实 immutable release 重新触发端到端同步。
