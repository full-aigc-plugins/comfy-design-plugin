"""
HTTP Client for ComfyUI REST API / ComfyUI REST API HTTP 客户端

Wraps httpx async calls to all ComfyUI HTTP endpoints used by this server.
All requests use `trust_env=False` to bypass any system proxy settings that
could interfere with local ComfyUI connections.

封装对 ComfyUI 所有 HTTP 接口的 httpx 异步调用。
所有请求使用 `trust_env=False` 以绕过系统代理设置，
避免干扰本地 ComfyUI 连接。
"""

import httpx
from typing import Dict, Any, Optional
from ..logger import logger
from ..config import settings
from ..models.comfyui import ComfyTaskResponse


class ComfyUIHttpClient:
    """Async HTTP client for the ComfyUI server REST API.
    ComfyUI 服务器 REST API 的异步 HTTP 客户端。

    Each method opens a fresh httpx.AsyncClient to avoid connection-state
    issues across long-lived server sessions.
    每个方法都新建一个 httpx.AsyncClient，避免长时间服务会话中的连接状态问题。
    """

    def __init__(self, base_url: Optional[str] = None):
        host = settings.COMFY_UI_SERVER_IP
        self.base_url = base_url or host
        # Ensure there's no trailing slash
        # 确保末尾无斜杠
        if self.base_url.endswith('/'):
            self.base_url = self.base_url[:-1]
        logger.info(f"Initialized ComfyUI HTTP Client with base URL: {self.base_url}")

    async def get_object_info(self) -> Dict[str, Any]:
        """Fetch the full node definition registry from ComfyUI.
        从 ComfyUI 获取完整的节点定义注册表（用于探测可用模型等）。
        """
        async with httpx.AsyncClient(trust_env=False) as client:
            url = f"{self.base_url}/object_info"
            logger.debug(f"Fetching object info from {url}")
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def queue_prompt(self, prompt_config: Dict[str, Any], client_id: str) -> ComfyTaskResponse:
        """Submit a prompt (workflow) for execution.
        提交一个 Prompt（工作流）到 ComfyUI 执行队列。

        Returns a ComfyTaskResponse containing the assigned prompt_id.
        返回包含 prompt_id 的 ComfyTaskResponse。
        """
        async with httpx.AsyncClient(trust_env=False) as client:
            url = f"{self.base_url}/prompt"
            payload = {
                "prompt": prompt_config,
                "client_id": client_id
            }
            logger.debug(f"Queuing prompt to {url} with client_id: {client_id}")
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return ComfyTaskResponse(**data)

    async def get_history(self, prompt_id: str) -> Dict[str, Any]:
        """Fetch execution history for a specific prompt_id.
        获取指定 prompt_id 的执行历史记录。
        """
        async with httpx.AsyncClient(trust_env=False) as client:
            url = f"{self.base_url}/history/{prompt_id}"
            logger.debug(f"Fetching history for prompt_id: {prompt_id}")
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def get_queue(self) -> Dict[str, Any]:
        """Fetch the current execution queue (running + pending).
        获取当前执行队列（包含运行中和待处理的任务）。
        """
        async with httpx.AsyncClient(trust_env=False) as client:
            url = f"{self.base_url}/queue"
            logger.debug(f"Fetching current queue from {url}")
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def get_all_history(self) -> Dict[str, Any]:
        """Fetch the complete execution history for all prompts.
        获取所有 Prompt 的完整执行历史记录。
        """
        async with httpx.AsyncClient(trust_env=False) as client:
            url = f"{self.base_url}/history"
            logger.debug(f"Fetching all history from {url}")
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def get_user_data(self, path: str) -> Any:
        """List files/directories under a ComfyUI userdata path.
        列出 ComfyUI userdata 目录下的文件/子目录。

        Uses the ?dir= query parameter for directory listing.
        Returns None if the path does not exist (404).
        使用 ?dir= 查询参数列出目录内容。
        若路径不存在（404），返回 None。
        """
        async with httpx.AsyncClient(trust_env=False) as client:
            url = f"{self.base_url}/userdata?dir={path}"
            logger.debug(f"Fetching user data directory from {url}")
            response = await client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

    async def get_user_data_detail(self, file_path: str) -> Dict[str, Any]:
        """Fetch the contents of a specific userdata file.
        获取特定 userdata 文件的内容（工作流 JSON）。

        URL-encodes the path before calling /api/userdata/{encoded_path}.
        Returns None if the file does not exist (404).
        对路径进行 URL 编码后请求 /api/userdata/{encoded_path}。
        若文件不存在（404），返回 None。
        """
        async with httpx.AsyncClient(trust_env=False) as client:
            import urllib.parse
            encoded_path = urllib.parse.quote(file_path, safe="")
            url = f"{self.base_url}/api/userdata/{encoded_path}"
            logger.debug(f"Fetching detail user data from {url}")
            response = await client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

    async def delete_from_queue(self, prompt_id: str) -> None:
        """Request deletion of a pending prompt from the queue.
        请求从队列中删除指定的待处理 Prompt。

        Failures are logged as warnings rather than raised, because the prompt
        may have already executed by the time the delete request arrives.
        失败只记录警告而不抛出，因为请求到达时任务可能已执行完毕。
        """
        async with httpx.AsyncClient(trust_env=False) as client:
            url = f"{self.base_url}/queue"
            payload = {"delete": [prompt_id]}
            logger.debug(f"Deleting prompt {prompt_id} from queue")
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
            except Exception as e:
                logger.warning(f"Failed to delete prompt {prompt_id} from queue: {e}")

    async def interrupt(self) -> None:
        """Send an interrupt signal to stop the currently-running prompt.
        发送中断信号，停止当前正在执行的 Prompt。
        """
        async with httpx.AsyncClient(trust_env=False) as client:
            url = f"{self.base_url}/interrupt"
            logger.debug(f"Interrupting running prompt at {url}")
            response = await client.post(url)
            response.raise_for_status()

    async def get_system_stats(self) -> Dict[str, Any]:
        """Fetch ComfyUI system statistics (GPU VRAM, RAM, etc.).
        获取 ComfyUI 系统统计信息（GPU 显存、内存等）。
        """
        async with httpx.AsyncClient(trust_env=False) as client:
            url = f"{self.base_url}/system_stats"
            logger.debug(f"Fetching system stats from {url}")
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def download_file(self, filename: str, subfolder: str = "", file_type: str = "output") -> bytes:
        """Download an output file from the ComfyUI /view endpoint.
        从 ComfyUI /view 接口下载输出文件（图像、视频等）。
        """
        import urllib.parse
        async with httpx.AsyncClient(trust_env=False) as client:
            qs = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": file_type})
            url = f"{self.base_url}/view?{qs}"
            logger.debug(f"Downloading file from {url}")
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    async def upload_image(self, image_data: bytes, filename: str, mime_type: str = "application/octet-stream", overwrite: bool = True) -> Dict[str, Any]:
        """Upload an image or asset to the ComfyUI /upload/image endpoint.
        上传图像或资产到 ComfyUI /upload/image 接口。

        Returns the JSON response from ComfyUI (typically includes the final filename).
        返回 ComfyUI 的 JSON 响应（通常包含最终存储的文件名）。
        """
        async with httpx.AsyncClient(trust_env=False) as client:
            url = f"{self.base_url}/upload/image"
            logger.debug(f"Uploading file {filename} to {url}")
            files = {
                "image": (filename, image_data, mime_type)
            }
            data = {"overwrite": "true" if overwrite else "false"}
            response = await client.post(url, files=files, data=data)
            response.raise_for_status()
            return response.json()

    # ------------------------- FUSION PATCH #3 (PartMe.AI) -------------------------

    async def post_free(self, unload_models: bool = True, free_memory: bool = True) -> None:
        """POST /free — unload models and/or free system memory on ComfyUI.
        请求 ComfyUI 卸载模型和/或释放内存（OOM 恢复用）。
        """
        async with httpx.AsyncClient(trust_env=False) as client:
            url = f"{self.base_url}/free"
            # ComfyUI's /free reads a JSON body with boolean flags (NOT form data).
            payload = {"unload_models": unload_models, "free_memory": free_memory}
            logger.debug(f"Posting free request to {url} with {payload}")
            response = await client.post(url, json=payload)
            response.raise_for_status()

    async def get_embeddings(self) -> Any:
        """GET /embeddings — list available embedding names.
        获取可用的 embedding 名称清单（提示词用）。
        """
        async with httpx.AsyncClient(trust_env=False) as client:
            url = f"{self.base_url}/embeddings"
            logger.debug(f"Fetching embeddings from {url}")
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def get_workflow_templates(self) -> Any:
        """GET /workflow_templates — local template tree shipped with ComfyUI.
        获取 ComfyUI 自带的本地工作流模板树（非云端注册表）。
        """
        async with httpx.AsyncClient(trust_env=False) as client:
            url = f"{self.base_url}/workflow_templates"
            logger.debug(f"Fetching workflow templates from {url}")
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def upload_mask(self, mask_data: bytes, filename: str, mime_type: str = "application/octet-stream", overwrite: bool = True, original_ref: Optional[str] = None) -> Dict[str, Any]:
        """POST /upload/mask — upload an inpainting mask (needs original_ref for alpha derivation).
        上传局部重绘蒙版到 /upload/mask（original_ref 指向原图以派生 alpha）。
        """
        async with httpx.AsyncClient(trust_env=False) as client:
            url = f"{self.base_url}/upload/mask"
            logger.debug(f"Uploading mask {filename} to {url}")
            files = {
                "image": (filename, mask_data, mime_type)
            }
            data: Dict[str, str] = {"overwrite": "true" if overwrite else "false"}
            if original_ref:
                data["original_ref"] = original_ref
            response = await client.post(url, files=files, data=data)
            response.raise_for_status()
            return response.json()
