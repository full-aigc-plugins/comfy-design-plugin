---
name: comfy-local-setup
description: 配置本机 Comfy Design 环境：ComfyUI 目标主机（本机或局域网）、可选 Comfy Cloud API Key 与本地 MCP 运行环境自检。首次使用、连接失败、更换目标主机或需要云端升级凭据时使用。
license: Apache-2.0
---

# Comfy Design 本地设置

## 快速开始

典型触发：

1. “第一次使用 Comfy Design / ComfyUI MCP。”
2. “bootstrap 说 ComfyUI 不可达 / venv 缺失。”
3. “我要连局域网另一台机器上的 ComfyUI。”
4. “要升级云端伙伴模型，帮我配 API Key。”

## 能力边界

### ✅ 擅长处理

- 只读检查（不打印任何密钥值）：

  ```bash
  python3 /absolute/plugin/root/scripts/comfy_local_setup.py check
  ```

- 打开本地配置页（仅本机 127.0.0.1 可访问；表单含“测试连接”实时显示版本/GPU/显存）：

  ```bash
  python3 /absolute/plugin/root/scripts/comfy_local_setup.py ui
  ```

- 保存结果落在两个位置：目标主机写入插件内 `vendor/comfyui-mcp-server/.env`；
  Cloud Key 写入当前用户受限配置文件（0600，Windows 为
  `%LOCALAPPDATA%\comfy-design-plugin\config.json`），绝不进 Git/聊天/日志。

### ⚠️ 需要用户完成

- 在配置页里**亲手填写**目标地址与（可选）Cloud Key——不要让用户把 Key 粘贴到聊天。
- Cloud Key 在 <https://platform.comfy.org/profile/api-keys> 创建（`comfyui-` 前缀）。
- 保存目标主机后**下次启动**本地 MCP 才生效（正在运行的实例不会热切换）。

### ❌ 不适用场景及交接

- ChatGPT 网页端连接：走 webcodex/connector 的正式凭据，不用本页面。
- 纯本地生成不需要 Cloud Key：留空即为零计费模式。
- ComfyUI 本身没启动：先让用户启动 ComfyUI（本插件不代管其进程）。

## 工作流

1. 先跑 `check`；三行输出分别对应目标可达性 / venv / Cloud Key 状态。
2. 有任何一项不合格 → 打开 `ui` 让用户在表单里完成（含一键安装 venv 按钮）。
3. 配置完成后回宿主重试原任务；首次使用建议按 `comfy-harness` 技能先调
   `get_system_status()` 确认链路。
