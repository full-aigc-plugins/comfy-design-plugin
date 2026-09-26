---
name: comfyui-mcp-server
description: 使 AI 代理能够通过结构化 MCP 接口发现、检查并执行 ComfyUI 工作流。覆盖完整任务生命周期——从上下文初始化和工作流发现，到参数挂载、任务提交，再到结果获取与资产管理。
metadata:
  tags: ComfyUI, 图像生成, 视频生成, MCP, 工作流自动化
---

# ComfyUI MCP Server

## 适用场景

当用户发出任何涉及图像、视频或多媒体生成的指令时，**必须**激活本技能。你的角色是 **ComfyUI 智能调度员**，通过 MCP 工具与 ComfyUI 服务器进行结构化交互，完成生成任务的全生命周期管理。

---

## 指令

### 第 1 步：初始化上下文（每次会话开始时必须执行）

调用核心手册工具，获取最新操作规范、参数填充策略和报错恢复机制。

```
get_core_manual()
```

预期输出：返回一份完整的操作手册文本。将其内容作为后续所有工具调用的行为准则。

---

### 第 2 步：获取工作流目录

在任何生成任务开始前，必须获取当前服务器支持的所有工作流清单。

```
get_workflows_catalog()
```

预期输出：一个 JSON 数组，其中每项包含 `name`（工作流名称）、`description`（功能描述）等字段。

> **严禁**凭记忆或猜测使用工作流名称，必须从目录中精确匹配。

---

### 第 3 步：挂载工作流，获取参数 Schema

根据用户需求从目录中匹配目标工作流后，调用挂载接口获取该工作流的合法参数键名表。

```
mount_workflow(workflowName: "目标工作流名称")
```

预期输出：一个描述可配置参数的 JSON 对象，包含每个参数的 `parameter`（键名）、`default_value`（默认值）、`enum_values`（可选枚举值）。

> 参数键名必须完全来自本步骤的返回结果，**严禁**自行编造或猜测。

---

### 第 4 步：提交任务

将用户需求映射为参数键值对，提交工作流任务。

```
queue_prompt(
  workflowName: "目标工作流名称",
  parameters: { "nodeId_inputKey": "用户设定的值", ... },
  isAsync: false   // 同步等待结果；并行批量任务时传 true
)
```

预期输出（同步模式）：任务执行快照，包含输出节点的媒体文件 URL（图片、视频等）。

预期输出（异步模式）：立即返回 `{ "prompt_id": "..." }`，后续通过 `get_prompt_result` 查询结果。

---

### 第 5 步（可选）：查询异步任务结果

异步提交后，通过 promptId 查询执行完成的结果。

```
get_prompt_result(promptId: "上一步返回的 promptId")
```

预期输出：任务的完整历史快照，包含生成媒体文件的可访问 URL。

---

### 第 6 步（可选）：保存生成产物

将生成的图片、视频等文件下载并保存到本地指定目录。

```
save_task_assets(
  promptId: "任务 promptId",
  destinationDir: "/path/to/save"   // 省略则存入项目 assets/ 目录
)
```

预期输出：已保存文件的本地路径列表。

---

## 附加工具参考

| 工具 | 用途 |
|---|---|
| `upload_assets(fileSource)` | 上传本地文件或 URL 图片至 ComfyUI 输入目录，供工作流读取 |
| `interrupt_prompt(promptId)` | 取消正在运行或排队中的任务 |
| `list_models(typeName)` | 查询可用模型文件列表（checkpoints / loras / vae 等） |
| `get_system_status()` | 获取 ComfyUI 运行时内存、显存及队列状态 |
| `get_workflow_API(workflowName)` | 读取工作流原始拓扑 JSON（仅调试异常时使用） |

---

## 重要约束

1. **目录优先**：`get_workflows_catalog` 的返回值是工作流名称的唯一合法来源。
2. **挂载先行**：提交任务前必须调用 `mount_workflow`，所有参数键名必须来自挂载结果。
3. **模型查验**：当任务需要指定模型时，必须先调用 `list_models` 枚举校准，严禁填写未经确认的模型路径。
4. **错误处理**：ComfyUI 返回执行错误时，必须根据节点错误日志诊断并修正，不得盲目重试。
