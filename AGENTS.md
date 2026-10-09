# AGENTS.md — Comfy Design

## 版本升级要求（强制，AI 必须遵守）

任何代码改动——无论大小——都必须 bump 版本并发布。PartMe.AI 插件市场
靠版本号感知更新：版本号不动，用户永远看不到「可更新」提示。


### 发版流程（每次改动完成后执行）

```bash
node scripts/bump-plugin.mjs comfy-design patch   # 文档/注释/小修复
node scripts/bump-plugin.mjs comfy-design minor   # 新功能
node scripts/bump-plugin.mjs comfy-design major   # 破坏性变更
```

脚本自动完成：catalog.json 版本更新 + 全部 manifest 同步（codex 清单带
当日 `+codex.日期` 后缀）+ 三平台市场清单重新生成与校验。之后按脚本
提示提交并 push **两个仓库**（本仓 + plugins 市场仓）。

### 市场仓版本同步（强制，漏做用户就看不到更新）

插件仓 bump+push 只是第一步——**ZCode/Codex/Kimi 感知更新看的是市场仓清单**。
每次发版必须同步更新市场仓的 catalog 版本并重新生成清单：

cd <市场仓目录>  # 本仓: workspace-agent-skills/full-aigc-plugins
python3 - <<'EOF'
import json
d = json.load(open("catalog.json"))
for p in d["plugins"]:
    if p["id"] == "<插件id>": p["version"] = "<新版本号>"
json.dump(d, open("catalog.json","w"), ensure_ascii=False, indent=2); open("catalog.json","a").write("
")
EOF
node scripts/sync-marketplaces.mjs --write && node scripts/sync-marketplaces.mjs
git add -A && git commit -m "release: <插件id> <版本>" && git push

### 硬性禁令

- 禁止改代码不 bump 版本（「小版本也要发」）
- 禁止手改 catalog.json 的 version 以外的生成产物、或手改三份市场清单——
  它们只能由 `scripts/bump-plugin.mjs` 与 `plugins/scripts/sync-marketplaces.mjs` 生成
- 版本号必须全链一致（catalog + 4 manifest），`sync-marketplaces` 校验会拦截不一致
- 插件本体放本仓根目录；`plugins/` 市场仓只存元数据，绝不物理包含插件代码

<!-- partme-agent-plugin-policy:v1 -->
## Partme Agent Plugin Architecture Rules v1

- 组织级架构规范（唯一事实源）：[Partme Agent Plugin Architecture Rules v1](https://github.com/full-aigc-plugins/.github/blob/main/docs/standards/partme-agent-plugin-architecture-rules-v1.md)。
- **Harness 可选**：默认直接使用 Skills + CLI/MCP；只有确有必要时才保留最多一个可发现的 `skills/*-harness/SKILL.md`，其 `scripts/harness.py` 也可选。
- 不复制宿主 Agent Runtime 或已有 CLI/MCP 的业务执行、任务数据库与权威状态；代码能力必须能追踪到真实 Agent → Skill/Command → Tool → 结果的调用链。
- 保留本仓库现有 OpenSpec、安全门禁、发布及验证要求。静态校验不代表真实宿主可执行性；所有上线宣称均需实际宿主验收。
- CI 统一使用组织级 [Partme Plugin Architecture 检查器](https://github.com/full-aigc-plugins/.github/blob/main/scripts/check_plugin_architecture.py)，不得复制实现或禁用检查。
<!-- /partme-agent-plugin-policy:v1 -->
