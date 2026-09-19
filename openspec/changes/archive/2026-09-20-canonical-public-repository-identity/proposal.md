## Why

插件已经迁移到当前 Full Stack/AIGC 插件组织并同时服务 Codex、ZCode 与 Kimi，但部分公开清单和 README 仍指向早期 PartMe 单仓身份，导致安装来源、Release 与项目主页不一致。

## What Changes

- 将当前公开 repository、homepage、schema ID 与安装示例统一到实际发布仓。
- 保留 AtomGit 镜像名称和历史证据中的原始仓库名，不伪造未发生的迁移。
- 使用不可变 release tag 作为当前 GitHub 安装来源。

## Capabilities

### New Capabilities

- `canonical-public-repository-identity`: 定义跨宿主插件唯一、可验证的公开仓库身份。

### Modified Capabilities

None.

## Impact

影响当前 manifest、README、验证脚本与测试；不改变运行时 API、历史 tag 或镜像事实。

