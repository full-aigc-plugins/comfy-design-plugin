---
name: comfyui-mcp-server
description: Enables AI agents to discover, inspect, and execute ComfyUI workflows through a structured MCP interface. Covers the full task lifecycle — from initial context loading and workflow discovery, through parameter mounting and task submission, to result retrieval and asset management.
metadata:
  tags: ComfyUI, image generation, video generation, MCP, workflow automation
---

# ComfyUI MCP Server

## When to Use

Activate this skill whenever the user issues any request involving image, video, or multimedia generation. Your role is the **ComfyUI Intelligent Operator** — you orchestrate generative AI tasks through the ComfyUI MCP server using a strict sequential tool protocol.

---

## Instructions

### Step 1: Initialize Context (Required at the start of every session)

Call the core manual tool to retrieve the latest operational rules, parameter-filling strategies, and error recovery mechanisms.

```
get_core_manual()
```

Expected output: A complete operations manual document. Use its contents as the governing ruleset for all subsequent tool calls.

---

### Step 2: Retrieve the Workflow Catalog

Before any generation task, fetch the list of all workflows currently supported by the server.

```
get_workflows_catalog()
```

Expected output: A JSON array where each entry contains `name` (workflow identifier), `description`, and other metadata fields.

> **STRICTLY FORBIDDEN** to use workflow names from memory or guesswork. You MUST pick an exact match from this catalog.

---

### Step 3: Mount the Workflow — Obtain the Parameter Schema

After matching the target workflow from the catalog, call the mount interface to retrieve the valid parameter key map.

```
mount_workflow(workflowName: "your_workflow_name")
```

Expected output: A JSON object describing configurable parameters, each with `parameter` (key name), `default_value`, and `enum_values` (if applicable).

> All parameter keys MUST come exclusively from this response. **STRICTLY FORBIDDEN** to fabricate or guess key names.

---

### Step 4: Submit the Task

Map the user's request to parameter key-value pairs and submit the workflow task.

```
queue_prompt(
  workflowName: "your_workflow_name",
  parameters: { "nodeId_inputKey": "user_value", ... },
  isAsync: false   // false = wait for result; true = return promptId immediately (for batch tasks)
)
```

Expected output (sync): Task execution snapshot including media file URLs (images, videos, etc.) from output nodes.

Expected output (async): `{ "prompt_id": "..." }` — query the result later with `get_prompt_result`.

---

### Step 5 (Optional): Query Async Task Result

After an async submission, retrieve the completed result using the promptId.

```
get_prompt_result(promptId: "the_prompt_id_from_step_4")
```

Expected output: Full task history snapshot with accessible URLs for all generated media files.

---

### Step 6 (Optional): Save Generated Assets

Download and save generated images, videos, or other files to a local directory.

```
save_task_assets(
  promptId: "the_task_prompt_id",
  destinationDir: "/path/to/save"   // Defaults to the project's assets/ folder if omitted
)
```

Expected output: A list of local file paths for all saved assets.

---

## Additional Tools Reference

| Tool | Purpose |
|---|---|
| `upload_assets(fileSource)` | Upload a local file or HTTP URL to ComfyUI's input directory for use in workflows |
| `interrupt_prompt(promptId)` | Cancel a running or queued task |
| `list_models(typeName)` | List available model files (checkpoints / loras / vae / controlnet) |
| `get_system_status()` | Fetch ComfyUI runtime RAM, VRAM, and queue metrics |
| `get_workflow_API(workflowName)` | Read the raw workflow topology JSON (for deep debugging only) |

---

## Critical Constraints

1. **Catalog first**: The workflow name MUST be an exact match from `get_workflows_catalog`. Never hallucinate names.
2. **Mount before submit**: Always call `mount_workflow` before submitting. All parameter keys must come from the mount result.
3. **Verify models**: When a task requires a specific model, always call `list_models` first to enumerate valid filenames. Never fabricate model paths.
4. **Handle errors**: When ComfyUI returns an execution error, diagnose based on the node error log and correct the issue. Do NOT blindly retry.
