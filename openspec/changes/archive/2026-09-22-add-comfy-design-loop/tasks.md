## 1. 技能创作与注册

- [x] 1.1 新建 `skills/comfy-design-loop/SKILL.md`（<500 行）：循环总览、轮语义（新意图提交 ≠ 重试）、逐轮/预算授权门禁、评审独立性、退出判据与熔断、`.comfy-loop/` 台账约定；frontmatter `name`/`description` 写明触发场景（多轮打磨、对照目标图迭代、按参考图收敛）。
- [x] 1.2 新建 `skills/comfy-design-loop/references/rubric-image.md` 与 `references/rubric-video.md`：judge 子代理提示词全文（轴定义、小数分、可执行 gap 纪律、反棘轮条款、历史裁决一致性）。
- [x] 1.3 在 `plugin-local-skills.json` 的 `skills` 数组登记 `comfy-design-loop`（与 `comfy-harness` 并列）。
- [x] 1.4 更新根 `README.md` 的技能计数表与「What's inside」说明，标注 `comfy-design-loop` 为插件本地技能。

## 2. Harness 增补

- [x] 2.1 `skills/comfy-harness/SKILL.md` 铁律②追加边界注：循环的下一轮是携带评审反馈的新意图提交，不属于失败重试；失败/超时/Unknown 仍照本条上报 lead。
- [x] 2.2 `skills/comfy-harness/SKILL.md` 追加「质量循环」索引段：多轮打磨任务 hand off 到 `comfy-design-loop` 技能（技能名 + 安装命令，不写相对路径）。

## 3. 校验与测试

- [x] 3.1 运行 skill vendor check（offline + online），确认新插件本地技能登记后校验通过、`skills.lock.json` 无漂移。
- [x] 3.2 按需补 `tests/` 断言：`plugin-local-skills.json` 与 `skills/` 目录一致、新 SKILL.md <500 行、frontmatter 合法；确认现有分发安全测试不回归。
- [x] 3.3 `python3 -m unittest discover -s tests` 全绿。

## 4. 验证

- [x] 4.1 跨技能引用审计：新增文档无 `../` 相对路径链接，技能间引用均为技能名 + 安装命令。
- [x] 4.2 运行 `git diff --check` 与严格 OpenSpec 校验（`openspec validate --all --strict`）。

## 5. 发版与市场同步（仓库强制流程）

- [x] 5.1 `node scripts/bump-plugin.mjs comfy-design minor` 升至 0.2.0（含 codex `+codex.<date>` 后缀），确认四份 manifest 版本一致。
- [x] 5.2 提交并 push 本仓；在 `full-aigc-plugins` 市场仓同步 `catalog.json` 版本，`node scripts/sync-marketplaces.mjs --plugin=comfy-design --write` 后校验并 push。

## 6. 归档

- [x] 6.1 全部任务完成后 `openspec archive add-comfy-design-loop`，归档变更单独提交。
