"""
Skills Service / 技能服务

Provides access to static skill/manual documents stored in the skill directory.
These documents are served to the LLM host via the `get_core_manual` MCP tool.
The locale setting (LOCALE env var, default "en") controls which language
version of SKILL.md is returned.

提供对技能目录中静态技能/手册文档的访问。
这些文档通过 `get_core_manual` MCP 工具提供给 LLM Host。
语言版本由 LOCALE 环境变量控制（默认 "en"）：
  - "zh-CN" → references/SKILL.zh.md（中文版）
  - 其他    → SKILL.md（英文版，根目录）
"""

from pathlib import Path
from ..logger import logger


class SkillsService:
    """Reads and serves Markdown-based skill documents.
    读取并提供基于 Markdown 的技能文档。
    """

    def __init__(self, skills_dir: str = "comfyui-mcp-server-skill"):
        # Resolve from this file's location upward to the project root.
        # 从当前文件位置向上解析到项目根目录。
        self.project_root = Path(__file__).parent.parent.parent
        self.skills_dir = self.project_root / skills_dir

    def get_core_manual(self) -> str:
        """Return the SKILL.md appropriate for the current locale setting.
        根据当前语言配置返回对应语言版本的 SKILL.md。

        Locale resolution / 语言解析逻辑:
          LOCALE=xxx → references/SKILL.xxx.md
          falls back to references/SKILL.{lang}.md if xxx has a region code
          finally falls back to SKILL.md (English, canonical version) if missing

        Returns a fallback string if no file can be read.
        若文件缺失或不可读，返回降级提示字符串。
        """
        # Import settings here to avoid circular imports at module level.
        # 延迟导入 settings，避免模块级循环导入。
        from ..config import settings

        locale = getattr(settings, "LOCALE", "en").strip().lower()

        # Determine candidate paths in priority order.
        # 按优先顺序确定候选文件路径。
        candidates = []
        
        if locale != "en":
            # 1. Exact locale match / 精确匹配 (e.g., zh-cn)
            candidates.append(self.skills_dir / "references" / f"SKILL.{locale}.md")
            
            # 2. Language-only match / 基础语言匹配 (e.g., zh)
            if "-" in locale:
                lang_code = locale.split("-")[0]
                candidates.append(self.skills_dir / "references" / f"SKILL.{lang_code}.md")
                
        # 3. English fallback / 英文降级
        candidates.append(self.skills_dir / "SKILL.md")

        for path in candidates:
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        logger.info(f"Serving core manual from: {path.relative_to(self.project_root)}")
                        return f.read()
                except Exception as e:
                    logger.error(f"Error reading core manual at {path}: {e}")

        logger.warning(f"Core manual not found in skill dir: {self.skills_dir}")
        return "ComfyUI MCP Server Core Manual not found."
