"""
Internationalisation (i18n) Service / 国际化服务

Loads locale JSON files from the `locales/` directory and provides a
translation lookup method `t()` that supports keyword argument substitution.
Falls back to `default_locale` (from settings.LOCALE) when a key is missing
in the active locale.

从 `locales/` 目录加载语言 JSON 文件，并提供支持关键字参数替换的
翻译查找方法 `t()`。当活跃语言中找不到某个键时，自动回退到
`default_locale`（来自 settings.LOCALE）。
"""

import json
import os
from pathlib import Path
from typing import Dict
from ..logger import logger
from ..config import settings


class I18nService:
    """Loads and serves localised strings from JSON translation files.
    从 JSON 翻译文件加载并提供本地化字符串。
    """

    def __init__(self, locale_dir: str = "locales", default_locale: str = None):
        self.project_root = Path(__file__).parent.parent.parent
        self.locale_dir = self.project_root / locale_dir
        # Normalize locale identifiers to lowercase for consistent key lookups.
        # 将语言标识符规范化为小写，确保键名一致性。
        self.default_locale = (default_locale or settings.LOCALE).strip().lower()
        self.current_locale = self.default_locale
        # { "en": { "key": "value", ... }, "zh-cn": { ... } }
        self.translations: Dict[str, Dict[str, str]] = {}
        self._load_translations()

    def _load_translations(self):
        """Scan the locale directory and load all *.json locale files.
        扫描语言目录，加载所有 *.json 语言文件。
        """
        if not self.locale_dir.exists():
            logger.warning(f"Locales directory {self.locale_dir} does not exist.")
            return

        for file in self.locale_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    # Normalize to lowercase: "zh-CN" file.stem -> "zh-cn" key.
                    # 规范为小写：如 "zh-CN" 的 stem 存为 "zh-cn" 键。
                    locale_name = file.stem.lower()
                    self.translations[locale_name] = json.load(f)
                    logger.debug(f"Loaded translations for {locale_name}")
            except Exception as e:
                logger.error(f"Failed to load translation file {file}: {e}")

    def set_locale(self, locale: str):
        """Change the active locale at runtime.
        在运行时切换活跃语言。

        Accepts full locale tags (e.g. "zh-CN") or short codes ("en").
        All keys are normalized to lowercase before lookup.
        接受完整语言标签（如 "zh-CN"）或短代码（如 "en"）。
        所有键名均规范化为小写后再查找。
        """
        normalized = locale.strip().lower()
        if normalized in self.translations:
            self.current_locale = normalized
        else:
            logger.warning(f"Locale '{locale}' not found, falling back to {self.default_locale}")
            self.current_locale = self.default_locale

    def t(self, key: str, **kwargs) -> str:
        """Look up a translation key via dot-path and substitute keyword arguments.
        通过点号路径查找翻译键并替换关键字参数占位符。

        Supports nested JSON paths (e.g. "tool.get_core_manual.description").
        支持嵌套 JSON 路径（如 "tool.get_core_manual.description"）。
        Falls back to default_locale, then to the raw key if not found.
        先回退到 default_locale，若仍未找到则返回原始键名。
        """
        def _resolve(d: dict, dotkey: str):
            """Walk nested dict using dot-separated segments.
            用点号分隔的路径段遍历嵌套字典。
            """
            node = d
            for part in dotkey.split("."):
                if isinstance(node, dict) and part in node:
                    node = node[part]
                else:
                    return None
            # Only return leaf strings; ignore intermediate dicts.
            # 仅返回叶子字符串，忽略中间字典节点。
            return node if isinstance(node, str) else None

        # Try active locale first.
        # 先查活跃语言。
        text = _resolve(self.translations.get(self.current_locale, {}), key)

        if text is None:
            # Fall back to default locale.
            # 回退到默认语言。
            text = _resolve(self.translations.get(self.default_locale, {}), key)

        if text is None:
            # Key not found in any locale — return the raw key and log a warning.
            # 任何语言中均未找到——返回原始键名并记录警告。
            logger.warning(f"i18n key not found: '{key}' (locale={self.current_locale})")
            text = key

        # Replace {placeholder} with provided kwargs.
        # 用 kwargs 替换 {占位符}。
        for k, v in kwargs.items():
            text = text.replace(f"{{{k}}}", str(v))

        return text
