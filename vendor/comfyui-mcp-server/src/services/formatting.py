"""
Workflow Formatting Utilities / 工作流格式化工具

Provides helper functions to parse ComfyUI API-format workflow JSONs:
  - `format_task()`                  → Detect and format a workflow as an MCP task definition
  - `extract_configurable_params()`  → Extract user-facing configurable parameters

提供解析 ComfyUI API 格式工作流 JSON 的辅助函数：
  - `format_task()`                  → 检测并将工作流格式化为 MCP 任务定义
  - `extract_configurable_params()`  → 提取面向用户的可配置参数列表
"""

import re
from typing import Dict, Any, List, Optional
from ..logger import logger
from ..models.comfyui import ConfigurableParam
from ..config import settings as _s


def format_task(workflow: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Check if a workflow qualifies as a named MCP task and return its definition.
    检查工作流是否符合命名 MCP 任务规范，若符合则返回任务定义字典。

    A workflow qualifies when it contains a PrimitiveStringMultiline node whose
    title matches WORKFLOW_NAME_REGEX (default: ==name==).
    当工作流中存在 title 匹配 WORKFLOW_NAME_REGEX（默认 ==名称==）
    的 PrimitiveStringMultiline 节点时，该工作流符合规范。

    Returns None if the workflow does not match the naming convention.
    若工作流不匹配命名规范，返回 None。
    """
    node_desc = _find_description_node(workflow)
    if not node_desc:
        return None

    title = node_desc.get("_meta", {}).get("title", "")
    match = _s.WORKFLOW_NAME_REGEX.match(title)
    if not match:
        return None

    workflow_name = match.group(1).strip()
    return {
        "workflow_name": workflow_name,
        "description": node_desc.get("inputs", {}).get("string", ""),
        "workflowTemplate": workflow
    }


def _find_description_node(workflow: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Locate the PrimitiveStringMultiline node that acts as the workflow descriptor.
    找到充当工作流描述标识的 PrimitiveStringMultiline 节点。
    """
    if not isinstance(workflow, dict):
        return None
    for _, node in workflow.items():
        if not isinstance(node, dict):
            continue
        if node.get("class_type") == "PrimitiveStringMultiline":
            title = node.get("_meta", {}).get("title", "")
            if _s.WORKFLOW_NAME_REGEX.match(title):
                return node
    return None


def is_connection_reference(value: Any) -> bool:
    """Return True if `value` is a ComfyUI inter-node connection reference.
    若 `value` 是 ComfyUI 节点间连接引用，返回 True。

    Connection refs are either:
      - ["nodeId", outputIndex]  — direct link / 直连
      - [[...], ...]             — nested list (rare) / 嵌套列表（少见）
    """
    if not isinstance(value, list) or not value:
        return False
    if len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], (int, float)):
        return True
    return isinstance(value[0], list)


def get_value_type(value: Any) -> str:
    """Map a Python value to its JSON Schema type string.
    将 Python 值映射到对应的 JSON Schema 类型字符串。
    """
    if isinstance(value, str):   return "string"
    if isinstance(value, bool):  return "boolean"
    if isinstance(value, (int, float)): return "number"
    if isinstance(value, list):  return "array"
    return "string"


def extract_configurable_params(workflow: Dict[str, Any]) -> List[ConfigurableParam]:
    """Extract all configurable parameters from a workflow's marker nodes.
    从工作流的标识节点中提取所有可配置参数。

    A node is considered a configurable parameter node when its `_meta.title`
    matches WORKFLOW_PARAM_REGEX (default: =>description).
    当节点的 `_meta.title` 匹配 WORKFLOW_PARAM_REGEX（默认 =>描述）时，
    该节点被识别为可配置参数节点。

    Skips connection-reference values and None values.
    跳过连接引用值和 None 值。
    """
    params = []
    if not isinstance(workflow, dict):
        return params

    for node_id, nodeConfig in workflow.items():
        if not isinstance(nodeConfig, dict):
            continue

        inputs = nodeConfig.get("inputs", {})
        class_type = nodeConfig.get("class_type", "Unknown")
        meta = nodeConfig.get("_meta", {})

        for input_key, value in inputs.items():
            # Skip inter-node wires and null values — they are not user-configurable.
            # 跳过节点间连线和 null 值，它们不是用户可配置的参数。
            if is_connection_reference(value):
                continue
            if value is None:
                continue

            node_title = meta.get("title", "")
            param_match = _s.WORKFLOW_PARAM_REGEX.match(node_title)

            # Only include nodes explicitly marked with the param marker.
            # 仅包含显式带有参数标识符的节点。
            if not param_match:
                continue

            # Extract the human-readable label from the '=>label' marker.
            # 从 '=>标签' 标识中提取人类可读的参数描述标签。
            param_description_label = param_match.group(1).strip()

            # Build an LLM-friendly description string with semantic hints.
            # 构建包含语义提示的 LLM 友好描述字符串。
            description = f"【必须填充】{class_type} 节点的 {input_key} 参数"

            lower_key = input_key.lower()
            if any(k in lower_key for k in ["seed", "种子"]):
                description += "随机种子 (Seed)，控制生成结果的随机性"
            elif any(k in lower_key for k in ["prompt", "text"]):
                description += "提示词文本，支持多行"
            elif any(k in lower_key for k in ["width", "宽度"]):
                description += "图像宽度 (像素)"
            elif any(k in lower_key for k in ["height", "高度"]):
                description += "图像高度 (像素)"
            elif any(k in lower_key for k in ["steps", "步数"]):
                description += "采样步数"
            elif any(k in lower_key for k in ["cfg", "scale"]):
                description += "CFG Scale，提示词遵循程度"

            # At this point is_required is always True (non-required params were skipped above)
            # 到达此处时参数一定是必填项（非必填项已通过 continue 跳过）
            description += f" (原值: {value})"

            params.append(ConfigurableParam(
                path=f"{node_id}.{input_key}",
                nodeId=str(node_id),
                inputKey=input_key,
                type=get_value_type(value),
                defaultValue=value,
                classType=class_type,
                nodeTitle=node_title,
                nodeDescription=param_description_label,
                description=description,
                required=True
            ))

    return params
