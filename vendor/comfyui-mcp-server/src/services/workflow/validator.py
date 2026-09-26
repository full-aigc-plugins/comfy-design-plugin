"""
Workflow Validator / 工作流校验器

Provides static methods to validate whether a ComfyUI API prompt graph
contains the required MCP naming markers (==name== and =>param), and to
extract the workflow name when it does.

提供静态方法，用于验证 ComfyUI API Prompt 图是否包含必需的
MCP 命名标识符（==名称== 和 =>参数），并在验证通过时提取工作流名称。
"""

from typing import Dict, Any, Optional
from ...logger import logger
from ...config import settings


class WorkflowValidator:
    """Validates and extracts metadata from ComfyUI API-format workflow prompts.
    对 ComfyUI API 格式的工作流 Prompt 进行校验并提取元数据。
    """

    @staticmethod
    def extract_workflow_name(node: Dict[str, Any]) -> Optional[str]:
        """Check if a node is the workflow descriptor and return its name.
        检查节点是否为工作流描述节点，若是则返回工作流名称。

        Matches PrimitiveStringMultiline nodes whose title satisfies
        WORKFLOW_NAME_REGEX (default: ==name==).
        匹配 title 满足 WORKFLOW_NAME_REGEX（默认 ==名称==）的
        PrimitiveStringMultiline 节点。
        """
        if node.get("type") == "PrimitiveStringMultiline" or node.get("class_type") == "PrimitiveStringMultiline":
            title = node.get("_meta", {}).get("title", "")
            match = settings.WORKFLOW_NAME_REGEX.search(title)
            if match:
                return match.group(1).strip()
        return None

    @staticmethod
    def validate_and_extract(
        prompt_data: Dict[str, Any],
        prompt_id: Optional[str] = None,
        inspection_status: str = "External"
    ) -> Optional[str]:
        """Validate an API prompt graph and return the workflow name if valid.
        校验 API Prompt 图，若有效则返回工作流名称，否则返回 None。

        A prompt is valid when it contains:
          1. A PrimitiveStringMultiline node matching WORKFLOW_NAME_REGEX  → sets workflow_name
          2. At least one node matching WORKFLOW_PARAM_REGEX               → confirms it has params

        以下两个条件同时满足时 Prompt 有效：
          1. 存在 title 匹配 WORKFLOW_NAME_REGEX 的 PrimitiveStringMultiline 节点 → 设置工作流名称
          2. 至少存在一个 title 匹配 WORKFLOW_PARAM_REGEX 的节点 → 确认存在参数标识

        Side effect: injects `prompt_id` and `inspection_status` into the
        descriptor node's `_meta` dict if the prompt is valid.
        副作用：若 Prompt 有效，将 `prompt_id` 和 `inspection_status` 注入
        描述节点的 `_meta` 字典，用于后续追踪。
        """
        try:
            workflow_name = None
            has_params = False
            target_node = None

            for node_id, node in prompt_data.items():
                if not isinstance(node, dict):
                    continue

                name = WorkflowValidator.extract_workflow_name(node)
                if name:
                    workflow_name = name
                    target_node = node

                # Check for at least one parameter marker node.
                # 检查是否存在至少一个参数标识节点。
                title = node.get("_meta", {}).get("title", "")
                if settings.WORKFLOW_PARAM_REGEX.search(title):
                    has_params = True

            if workflow_name and has_params:
                # Annotate the descriptor node with tracing metadata.
                # 向描述节点注入追踪元数据。
                if target_node:
                    if "_meta" not in target_node:
                        target_node["_meta"] = {}
                    if prompt_id:
                        target_node["_meta"]["prompt_id"] = prompt_id
                    target_node["_meta"]["inspection_status"] = inspection_status
                return workflow_name

            return None
        except Exception as e:
            logger.error(f"Error validating workflow {prompt_id}: {e}")
            return None
