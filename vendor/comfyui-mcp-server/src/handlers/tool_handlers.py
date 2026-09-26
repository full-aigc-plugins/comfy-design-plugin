"""
MCP Tool Handlers / MCP 工具处理器

This module implements the execution logic for all tools exposed to the MCP client.
Each handler function takes the arguments provided by the client and the server instance,
processes the request via the service container, and returns a list of TextContent objects.

本模块实现了暴露给 MCP 客户端的所有工具的执行逻辑。
每个处理器函数接收客户端提供的参数和服务器实例，
通过服务容器处理请求，并返回 TextContent 对象列表。
"""
import os
import json
import time
import asyncio
import urllib.parse
import mcp.types as types

from ..logger import logger
from ..services.formatting import extract_configurable_params
from ..dependencies import container

# Cache for workflow mount data to optimize repeated mount requests.
# 用于缓存工作流挂载数据，以优化重复的挂载请求。
_WORKFLOW_MOUNT_CACHE = {}


async def _trigger_ondemand_refresh(wait: bool = True):
    """Triggers a workflow refresh when SYNC_MODE=manual and scanner is available.
    当 SYNC_MODE=manual 且扫描器可用时，触发工作流手动刷新。
    
    Args:
        wait: If True, awaits the refresh (10s timeout). If False, fires and forgets.
              如果为 True，等待刷新完成（10秒超时）。如果为 False，则异步触发且不等待。
    """
    from ..config import settings as _s
    if _s.SYNC_MODE != "manual" or not container.scanner:
        return
    if wait:
        try:
            await asyncio.wait_for(container.scanner.check_and_refresh(), timeout=10)
        except asyncio.TimeoutError:
            logger.warning("[on_demand] Refresh timed out after 10s, returning cached data.")
    else:
        asyncio.create_task(container.scanner.check_and_refresh())

async def handle_get_core_manual(arguments: dict, app_server) -> list[types.TextContent]:
    """Return the core operations manual for the AI agent.
    返回核心操作手册，供 AI 代理参考。
    """
    manual = container.skills_service.get_core_manual()
    return [types.TextContent(type="text", text=manual)]

async def handle_get_workflows_catalog(arguments: dict, app_server) -> list[types.TextContent]:
    """Retrieve the JSON catalog of available workflows.
    获取可用工作流的 JSON 目录。
    """
    await _trigger_ondemand_refresh(wait=True)
    catalog_path = container.catalog_service.catalog_path
    
    # Wait for any rebuild that is currently running
    # 等待当前正在运行的任何重建过程完成
    async with container.catalog_service._lock:
        if not os.path.exists(catalog_path):
            return [types.TextContent(type="text", text="[]")]
            
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            return [types.TextContent(type="text", text=content)]
        except Exception as e:
            logger.error(f"Failed to read workflow catalog: {e}")
            return [types.TextContent(type="text", text=f"Error reading catalog: {e}")]

async def handle_get_prompt_result(arguments: dict, app_server) -> list[types.TextContent]:
    """Fetch the result history of a specific task and inject verifiable URLs for generated media.
    获取特定任务的结果历史记录，并为生成的媒体文件注入可验证的 URL。
    """
    prompt_id = arguments.get("prompt_id") or arguments.get("promptId")
    if not prompt_id:
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e="'prompt_id' is required."))]
        
    try:
        history = await container.http_client.get_history(prompt_id)
        if not history or prompt_id not in history:
            return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e="Task not found in history yet. It might be pending or running. / 未在历史中找到任务，可能正在运行或排队中。"))]
            
        task_data = history[prompt_id]
        
        # Inject URL into outputs
        # 提取结果并拼接为完整的媒体 URL
        outputs = task_data.get("outputs", {})
        base_url = container.http_client.base_url
        for node_id, output_data in outputs.items():
            for key in ["images", "gifs", "videos"]:  # Typical keys in ComfyUI output / ComfyUI 输出中的典型键名
                if key in output_data:
                    for item in output_data[key]:
                        if "filename" in item:
                            filename = item.get("filename", "")
                            subfolder = item.get("subfolder", "")
                            file_type = item.get("type", "output")
                            qs = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": file_type})
                            item["url"] = f"{base_url}/view?{qs}"
                            
        return [types.TextContent(type="text", text=json.dumps(task_data, ensure_ascii=False, indent=2))]
    except Exception as e:
        logger.error(f"Failed to get task detail for {prompt_id}: {e}")
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e=f"Failed to get task detail: {e}"))]

async def handle_get_workflow_API(arguments: dict, app_server) -> list[types.TextContent]:
    """Read the raw JSON api file for a specific workflow. Used for diagnostics.
    读取特定工作流的原始 JSON api 文件。主要用于诊断底层拓扑。
    """
    workflow_name = arguments.get("workflow_name")
    if not workflow_name:
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e="'workflow_name' is required."))]
        
    workflow_path = os.path.join(os.getcwd(), 'workflow', f"{workflow_name}.json")
    if not os.path.exists(workflow_path):
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e=f"Workflow '{workflow_name}' not found locally."))]
        
    try:
        with open(workflow_path, "r", encoding="utf-8") as f:
            workflow_template = json.load(f)
        return [types.TextContent(type="text", text=json.dumps(workflow_template, ensure_ascii=False, indent=2))]
    except Exception as e:
        logger.error(f"Failed to read workflow for {workflow_name}: {e}")
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e=f"Error reading workflow '{workflow_name}': {e}"))]

async def handle_mount_workflow(arguments: dict, app_server) -> list[types.TextContent]:
    """Parse a workflow to extract its configurable parameters (the 'mount' schema).
    解析工作流以提取其可配置的参数（即“挂载”模式）。
    """
    workflow_name = arguments.get("workflow_name")
    await _trigger_ondemand_refresh(wait=True)

    if not workflow_name:
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e="'workflow_name' is required."))]
        
    workflow_path = os.path.join(os.getcwd(), 'workflow', f"{workflow_name}.json")
    if not os.path.exists(workflow_path):
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e=f"Workflow '{workflow_name}' not found locally."))]
        
    try:
        # Check cache
        # 检查缓存是否存在并且文件尚未修改
        mtime = os.path.getmtime(workflow_path)
        cached_data = _WORKFLOW_MOUNT_CACHE.get(workflow_name)
        
        if cached_data and cached_data['mtime'] == mtime:
            logger.info(f"Using cached mount structure for {workflow_name} / 使用缓存的挂载结构：{workflow_name}")
            return [types.TextContent(type="text", text=json.dumps(cached_data['data'], ensure_ascii=False, indent=2))]
            
        # Cache miss or file updated, re-process
        # 缓存未命中或文件已更新，重新处理
        with open(workflow_path, "r", encoding="utf-8") as f:
            workflow_template = json.load(f)
            
        params = extract_configurable_params(workflow_template)
        
        # Build strict definition omitting lines
        # 构建仅包含节点和参数的严格定义，忽略连接线等拓扑细节
        definition_result = {
            "workflow_name": workflow_name,
            "configurable_parameters": []
        }
        
        grouped_nodes = {}
        for param in params:
            # Only keep non-link values
            # 只保留非连接线的明确值（排除节点间的连线）
            if isinstance(param.defaultValue, list): 
                continue
                
            if param.nodeId not in grouped_nodes:
                grouped_nodes[param.nodeId] = {
                    "node_name": param.classType,
                    "node_id": param.nodeId,
                    "node_description": param.nodeDescription,
                    "parameters": []
                }
                
            grouped_nodes[param.nodeId]["parameters"].append({
                 "parameter": f"{param.nodeId}_{param.inputKey}",
                 "default_value": param.defaultValue,
                 "enum_values": param.enumValues
            })
            
        definition_result["configurable_parameters"] = list(grouped_nodes.values())
            
        # Save to cache
        # 保存到缓存中以备后用
        _WORKFLOW_MOUNT_CACHE[workflow_name] = {
            'mtime': mtime,
            'data': definition_result
        }
        
        return [types.TextContent(type="text", text=json.dumps(definition_result, ensure_ascii=False, indent=2))]
    except Exception as e:
        logger.error(f"Failed to mount workflow {workflow_name}: {e}")
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e=f"Error mounting workflow: {e}"))]

async def handle_queue_prompt(arguments: dict, app_server) -> list[types.TextContent]:
    """Execute a predefined workflow by applying parameters and subscribing to its progress.
    执行预定义的工作流，应用所传入的参数并订阅其执行进度。
    """
    workflow_name = arguments.get("workflow_name")
    parameters = arguments.get("parameters", {})
    is_async_str = arguments.get("is_async", "false")
    is_async = str(is_async_str).lower() in ("true", "1", "yes")
    await _trigger_ondemand_refresh(wait=False)

    if not workflow_name:
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e="'workflow_name' is required."))]
        
    workflow_path = os.path.join(os.getcwd(), 'workflow', f"{workflow_name}.json")
    if not os.path.exists(workflow_path):
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e=f"Workflow '{workflow_name}' not found locally."))]
        
    try:
        with open(workflow_path, "r", encoding="utf-8") as f:
            workflow_template = json.load(f)
    except Exception as e:
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e=f"Error reading workflow '{workflow_name}': {e}"))]
        
    # Apply parameters securely mapped by configurable extractor
    # 安全地应用由配置提取器映射的参数，防止外部注入非法节点属性
    params_def = extract_configurable_params(workflow_template)
    prompt = json.loads(json.dumps(workflow_template))
    
    for param in params_def:
        key = f"{param.nodeId}_{param.inputKey}"
        if key in parameters:
            prompt.setdefault(param.nodeId, {}).setdefault("inputs", {})[param.inputKey] = parameters[key]
            
    client_id = f"mcp_client_unified_{workflow_name}"
    try:
        ws_client = await container.ws_manager.get_connection(client_id)
        
        # Setup progress notification for MCP client
        # 为 MCP 客户端设置进度通知功能
        progress_token = None
        if hasattr(app_server, "request_context") and app_server.request_context:
            ctx = app_server.request_context
            if hasattr(ctx, "meta") and ctx.meta:
                if hasattr(ctx.meta, "progressToken") and ctx.meta.progressToken:
                    progress_token = ctx.meta.progressToken
                elif isinstance(ctx.meta, dict) and "progressToken" in ctx.meta:
                    progress_token = ctx.meta.get("progressToken")
                    
        async def on_progress(value: int, max_value: int):
            if progress_token and max_value > 0:
                try:
                    await app_server.request_context.session.send_progress_notification(
                        progress_token=progress_token,
                        progress=value,
                        total=max_value
                    )
                except Exception as e:
                    logger.debug(f"Failed to send progress notification: {e}")

        result = await container.task_service.execute_workflow_task_by_prompts(prompt, client_id, ws_client, progress_callback=on_progress, is_async=is_async)
        
        if not is_async and result.get("status", {}).get("status_str") == "error":
            logger.error(f"ComfyUI Execution Error for {workflow_name}: {result}")
            return [types.TextContent(type="text", text=container.i18n.t("error.comfyui_execution_failed", result=json.dumps(result, ensure_ascii=False)))]
            
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
    except Exception as e:
        logger.error(f"MCP Execution failed for {workflow_name}: {e}")
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e=e))]

async def handle_queue_custom_prompt(arguments: dict, app_server) -> list[types.TextContent]:
    """Execute a raw ComfyUI Prompt JSON (advanced usage).
    直接执行原始的 ComfyUI Prompt JSON（受限的高级用法）。
    """
    workflow_name = arguments.get("workflow_name")
    api_json = arguments.get("api_json")
    is_async_str = arguments.get("is_async", "false")
    is_async = str(is_async_str).lower() in ("true", "1", "yes")
    await _trigger_ondemand_refresh(wait=False)

    if not workflow_name or not api_json:
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e="'workflow_name' and 'api_json' are required."))]
        
    try:
        if isinstance(api_json, str):
            prompt = json.loads(api_json)
        else:
            prompt = api_json
    except json.JSONDecodeError as e:
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e=f"Error parsing api_json: {e}"))]
        
    client_id = f"mcp_client_custom_{workflow_name}"
    try:
        ws_client = await container.ws_manager.get_connection(client_id)
        result = await container.task_service.execute_workflow_task_by_prompts(prompt, client_id, ws_client, is_async=is_async)
        
        if not is_async and result.get("status", {}).get("status_str") == "error":
            logger.error(f"ComfyUI Custom Execution Error for '{workflow_name}': {result}")
            return [types.TextContent(type="text", text=container.i18n.t("error.comfyui_execution_failed", result=json.dumps(result, ensure_ascii=False)))]
            
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
    except Exception as e:
        logger.error(f"MCP Custom execution failed for '{workflow_name}': {e}")
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e=e))]

async def handle_interrupt_prompt(arguments: dict, app_server) -> list[types.TextContent]:
    """Cancel a running or pending task by prompt_id.
    通过 prompt_id 取消正在运行或排队中的任务。
    """
    prompt_id = arguments.get("prompt_id")
    if not prompt_id:
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e="'prompt_id' is required."))]
        
    try:
        # We try to interrupt the active node AND delete it from the pending queue
        # 尝试中断正在执行的节点，同时将其从排队队列中删除
        await asyncio.gather(
            container.http_client.interrupt(),
            container.http_client.delete_from_queue(prompt_id)
        )
        return [types.TextContent(type="text", text=f"Task {prompt_id} cancellation requested successfully.")]
    except Exception as e:
        logger.error(f"Failed to cancel task {prompt_id}: {e}")
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e=f"Failed to cancel task: {e}"))]

async def handle_save_custom_workflow(arguments: dict, app_server) -> list[types.TextContent]:
    """Save a user-provided API JSON as a custom workflow to local storage.
    将用户提供的 API JSON 作为自定义工作流保存到本地目录中进行管理和挂载。
    """
    filename = arguments.get("filename")
    api_json = arguments.get("api_json")
    
    if not filename or not api_json:
        raise ValueError("Missing 'filename' or 'api_json'")
        
    if isinstance(api_json, str):
        try:
            api_json = json.loads(api_json)
        except Exception:
            raise ValueError("api_json must be a valid JSON object or parseable string")
            
    try:
        parsed_data = await container.catalog_service.save_custom_workflow(filename, api_json)
        result_text = f"Successfully saved and mounted workflow '{parsed_data.get('name')}' to {filename}"
        return [types.TextContent(type="text", text=result_text)]
    except Exception as e:
        logger.error(f"Save custom workflow error: {e}")
        error_msg = container.i18n.t("error.mcp_execution_failed").format(e=str(e))
        return [types.TextContent(type="text", text=error_msg)]

async def handle_save_task_assets(arguments: dict, app_server) -> list[types.TextContent]:
    """Download all media outputs generated by a specific task to a local project directory.
    将特定任务产生的所有媒体输出（图像/视频等）下载并保存到本地项目目录中。
    """
    prompt_id = arguments.get("prompt_id") or arguments.get("promptId")
    destination_dir = arguments.get("destination_dir")
    overwrite = arguments.get("overwrite", False)
    
    if not prompt_id:
        raise ValueError("Missing 'prompt_id'")
        
    # Default to placing it in the projects 'assets' folder
    # 默认存储位置为项目目录下的 'assets' 文件夹
    default_dir = os.path.join(os.getcwd(), 'assets')
    
    if not destination_dir or not isinstance(destination_dir, str) or not destination_dir.strip():
        destination_dir = default_dir
        
    # Ensure destination exists or fallback
    # 确保目标路径存在，否则降级使用默认路径
    try:
        os.makedirs(destination_dir, exist_ok=True)
    except Exception as e:
        logger.warning(f"Invalid destination_dir {destination_dir}: {e}. Falling back to default.")
        destination_dir = default_dir
        os.makedirs(destination_dir, exist_ok=True)
    
    try:
        history = await container.http_client.get_history(prompt_id)
        if not history or prompt_id not in history:
            return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e="Task not found in history yet. It might be pending or running."))]
            
        task_data = history[prompt_id]
        outputs = task_data.get("outputs", {})
        
        saved_files = []
        errors = []
        
        # Iterate over all node outputs
        # 遍历所有节点的输出
        for node_id, output_data in outputs.items():
            if not isinstance(output_data, dict):
                continue
                
            # Iterate over all possible lists in the output
            # 遍历输出中所有的列表结构（如 images, videos 数组）
            for media_list in output_data.values():
                if not isinstance(media_list, list):
                    continue
                    
                for item in media_list:
                    if isinstance(item, dict) and "filename" in item:
                        filename = item.get("filename", "")
                        subfolder = item.get("subfolder", "")
                        file_type = item.get("type", "output")
                        
                        target_path = os.path.join(destination_dir, filename)
                        
                        if os.path.exists(target_path) and not overwrite:
                            logger.info(f"Skipping existing file {target_path} / 跳过已存在的文件")
                            saved_files.append(f"{filename} (Skipped - exists)")
                            continue
                            
                        # Download and save
                        # 通过 HTTP 客户端下载并写入本地文件
                        try:
                            file_data = await container.http_client.download_file(filename, subfolder, file_type)
                            with open(target_path, "wb") as f:
                                f.write(file_data)
                            saved_files.append(target_path)
                            logger.info(f"Saved asset to {target_path}")
                        except Exception as dl_error:
                            error_text = f"Failed to download {filename}: {dl_error}"
                            logger.error(error_text)
                            errors.append(error_text)
                            
        result_lines = [f"Successfully processed assets for prompt_id: {prompt_id}"]
        if saved_files:
            result_lines.append("Saved Files:")
            for bf in saved_files:
                result_lines.append(f" - {bf}")
        if errors:
            result_lines.append("Errors encountered:")
            for err in errors:
                result_lines.append(f" - {err}")
                
        if not saved_files and not errors:
            result_lines.append("No media output files found in the task history.")
            
        return [types.TextContent(type="text", text="\n".join(result_lines))]
    except Exception as e:
        logger.error(f"Failed to get task detail or save assets for {prompt_id}: {e}")
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e=f"Failed to save task assets: {e}"))]

async def handle_get_system_status(arguments: dict, app_server) -> list[types.TextContent]:
    """Retrieve runtime diagnostics such as Host Python version, RAM, VRAM and Queue stats.
    获取底层环境运行时诊断信息，例如 Python 版本、内存、显存以及排队状态。
    """
    try:
        stats = await container.http_client.get_system_stats()
        return [types.TextContent(type="text", text=json.dumps(stats, ensure_ascii=False, indent=2))]
    except Exception as e:
        logger.error(f"Failed to fetch system stats: {e}")
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e=f"Failed to fetch system stats: {e}"))]

async def handle_upload_assets(arguments: dict, app_server) -> list[types.TextContent]:
    """Upload a local or remote media file to the ComfyUI 'input' directory.
    上传本地或远程媒体文件到 ComfyUI 系统的 'input'（输入）目录以供工作流读取。
    """
    file_source = arguments.get("fileSource")
    mime_type = arguments.get("mimeType") or "application/octet-stream"
    
    if not file_source:
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e="'fileSource' is required."))]
        
    start_time = time.time()
    
    try:
        if file_source.lower().startswith("http://") or file_source.lower().startswith("https://"):
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(file_source)
                if resp.status_code != 200:
                    return [types.TextContent(type="text", text=container.i18n.t("error.downloadAssetsFail", status=resp.status_code))]
                file_data = resp.content
                
            # Exclude query parameters and get filename
            # 过滤掉查询参数，仅解析获取 URL 路径中的基础文件名
            url_without_query = file_source.split("?")[0]
            final_filename = os.path.basename(urllib.parse.urlparse(url_without_query).path)
            if not final_filename:
                final_filename = "downloaded.png"
        else:
            if not os.path.exists(file_source):
                return [types.TextContent(type="text", text=container.i18n.t("error.fileNotExistError", fileSource=file_source))]
            
            with open(file_source, "rb") as f:
                file_data = f.read()
                
            final_filename = os.path.basename(file_source)
            if not final_filename:
                final_filename = "uploaded_image.png"
                
        # Uploading via HTTP client to ComfyUI
        # 通过 HTTP 客户端执行二进制数据上传
        response_data = await container.http_client.upload_image(file_data, final_filename, mime_type=mime_type, overwrite=True)
        
        execution_time = int((time.time() - start_time) * 1000)
        
        success_msg = container.i18n.t("tool.upload_assets.success", finalFileName=final_filename)
        return [types.TextContent(type="text", text=f"{success_msg}\nResponse: {json.dumps(response_data)}\nExecution Time: {execution_time}ms")]
        
    except Exception as e:
        logger.error(f"Failed to upload asset {file_source}: {e}")
        return [types.TextContent(type="text", text=container.i18n.t("error.uploadFail", message=str(e)))]

async def handle_list_models(arguments: dict, app_server) -> list[types.TextContent]:
    """Retrieve lists of properly resolved exact file names for weights (Checkpoints, Loras, etc.).
    调取精确的文件名清单以供预置各类权重下拉框（Checkpoints, Loras, VAE, ControlNet 等）。
    """
    type_name = arguments.get("type_name", "checkpoints").lower()
    
    try:
        object_info = await container.http_client.get_object_info()
    except Exception as e:
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e=f"Failed to fetch object_info: {e}"))]
        
    node_maps = {
        "checkpoints": [("CheckpointLoaderSimple", "ckpt_name"), ("UNETLoader", "unet_name")],
        "loras": [("LoraLoader", "lora_name")],
        "vae": [("VAELoader", "vae_name")],
        "controlnet": [("ControlNetLoader", "control_net_name"), ("ControlNetLoaderAdvanced", "control_net_name")]
    }
    
    models = []
    if type_name in node_maps:
        for node_class, param_name in node_maps[type_name]:
            if node_class in object_info:
                try:
                    node_def = object_info.get(node_class, {})
                    node_inputs = node_def.get("input", {}).get("required", {})
                    if param_name in node_inputs:
                        param_def = node_inputs[param_name]
                        if isinstance(param_def, list) and len(param_def) > 0:
                            model_list = param_def[0]
                            if isinstance(model_list, list):
                                models.extend(model_list)
                except Exception as e:
                    logger.debug(f"list_models parsing error for {node_class}: {e}")
    else:
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e=f"Unsupported exact model type '{type_name}' for listing. Try checkpoints, loras, vae, or controlnet."))]
        
    # Deduplicate in case of overlapping mappings
    # 对查询过程中产生重叠的映射部分去重归并
    models = sorted(list(set(models)))
    
    result = {
        "type": type_name,
        "count": len(models),
        "models": models
    }
    return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


# ------------------- FUSION PATCH #3 (PartMe.AI): API completion -------------------

async def handle_free_memory(arguments: dict, app_server) -> list[types.TextContent]:
    """Unload models and/or free system memory on ComfyUI (OOM recovery).
    请求 ComfyUI 卸载模型和/或释放内存（OOM 恢复）。
    """
    unload_models = arguments.get("unload_models", True)
    free_memory = arguments.get("free_memory", True)
    try:
        await container.http_client.post_free(unload_models=unload_models, free_memory=free_memory)
        return [types.TextContent(type="text", text=json.dumps({
            "status": "ok",
            "unload_models": unload_models,
            "free_memory": free_memory,
            "note": "VRAM/system memory freed; next run reloads models on demand.",
        }, ensure_ascii=False))]
    except Exception as e:
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e=e))]


async def handle_list_embeddings(arguments: dict, app_server) -> list[types.TextContent]:
    """List available embedding names (GET /embeddings).
    列出可用的 embedding 名称（提示词引用用）。
    """
    try:
        embeddings = await container.http_client.get_embeddings()
        if not isinstance(embeddings, list):
            embeddings = []
        return [types.TextContent(type="text", text=json.dumps({
            "count": len(embeddings),
            "embeddings": sorted(embeddings),
        }, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e=e))]


async def handle_list_local_templates(arguments: dict, app_server) -> list[types.TextContent]:
    """List the LOCAL workflow template tree shipped with this ComfyUI (GET /workflow_templates).
    列出本机 ComfyUI 自带的工作流模板树（本地模板，非云端注册表）。
    """
    try:
        templates = await container.http_client.get_workflow_templates()

        def _count(node):
            # type: (dict) -> int
            if isinstance(node, dict):
                if "templates" in node:
                    return len(node["templates"])
                return sum(_count(v) for v in node.values() if isinstance(v, (dict, list)))
            if isinstance(node, list):
                return len(node)
            return 0

        return [types.TextContent(type="text", text=json.dumps({
            "source": "local",
            "template_count": _count(templates),
            "templates": templates,
        }, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e=e))]


async def handle_upload_mask(arguments: dict, app_server) -> list[types.TextContent]:
    """Upload an inpainting mask file to ComfyUI input (POST /upload/mask).
    上传局部重绘蒙版到 ComfyUI 输入目录（POST /upload/mask）。
    """
    file_path = arguments.get("file_path")
    original_ref = arguments.get("original_ref")
    if not file_path:
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e="'file_path' is required."))]
    if not os.path.exists(file_path):
        return [types.TextContent(type="text", text=container.i18n.t("error.fileNotExistError", fileSource=file_path))]
    try:
        with open(file_path, "rb") as fh:
            data = fh.read()
        response = await container.http_client.upload_mask(
            mask_data=data,
            filename=os.path.basename(file_path),
            original_ref=original_ref,
        )
        return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False))]
    except Exception as e:
        return [types.TextContent(type="text", text=container.i18n.t("error.mcp_execution_failed", e=e))]
