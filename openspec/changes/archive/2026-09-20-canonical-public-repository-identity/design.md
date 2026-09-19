## Context

插件的公开身份必须与实际 GitHub 组织、仓库名和 Release 对齐，同时区分当前入口、宿主专属 manifest、历史证据和外部镜像。

## Decisions

### 当前 GitHub 仓库是规范身份

当前 manifest、README、schema ID 和验证断言使用实际发布仓 URL；旧 PartMe GitHub URL不再作为当前入口。

### 保留真实例外

`.codex-plugin`、Codex CLI 命令和 `+codex.<date>` 是宿主契约；AtomGit 旧镜像名与历史证据保持原样并明确其性质。

### 安装引用不可变

GitHub 安装示例和仓内 marketplace 使用当前 release tag，不使用 `main` 代表正式发布物。

