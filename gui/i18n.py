"""轻量级 i18n 模块：从 JSON locale 文件加载翻译，提供 t() 翻译函数。"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_LOCALES_DIR = Path(__file__).resolve().parent / "locales"
DEFAULT_LANGUAGE = "zh"
SUPPORTED_LANGUAGES = ("zh", "en", "mn")
LANGUAGE_OPTIONS = (
    ("zh", "中文"),
    ("en", "EN"),
    ("mn", "МН"),
)

# 当前语言与翻译数据
_current_lang: str = "zh"
_translations: dict[str, dict[str, str]] = {}
_all_locales: dict[str, dict[str, dict[str, str]]] = {}
_fallback: dict[str, dict[str, str]] = {}
_initialized: bool = False
_missing_keys: set[str] = set()


def normalize_language(lang: str | None) -> str | None:
    """将语言标签归一化为项目支持的基础语言代码。"""

    if not isinstance(lang, str):
        return None
    base = lang.strip().lower().replace("_", "-").split("-", 1)[0]
    return base if base in SUPPORTED_LANGUAGES else None


def _load_locale(lang: str) -> dict[str, dict[str, str]]:
    """加载单个语言的翻译文件。"""
    path = _LOCALES_DIR / f"{lang}.json"
    if not path.exists():
        logger.warning("locale 文件不存在: %s", path)
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as ex:
        logger.warning("无法加载 locale '%s': %s", lang, ex)
        return {}
    if not isinstance(payload, dict):
        logger.warning("locale '%s' 必须是 JSON 对象", lang)
        return {}
    locales: dict[str, dict[str, str]] = {}
    for namespace, entries in payload.items():
        if not isinstance(namespace, str) or not isinstance(entries, dict):
            logger.warning("locale '%s' 的 namespace '%s' 必须是对象，已忽略", lang, namespace)
            continue
        invalid = [key for key, value in entries.items() if not isinstance(key, str) or not isinstance(value, str)]
        if invalid:
            logger.warning("locale '%s:%s' 含有非字符串翻译值，已忽略: %s", lang, namespace, invalid[:5])
        locales[namespace] = {
            key: value
            for key, value in entries.items()
            if isinstance(key, str) and isinstance(value, str)
        }
    return locales


def init(lang: str = "zh") -> None:
    """初始化 i18n 模块，加载所有 locale 并设置当前语言。"""
    global _current_lang, _translations, _all_locales, _fallback, _initialized, _missing_keys

    _all_locales = {
        lang_code: _load_locale(lang_code)
        for lang_code in SUPPORTED_LANGUAGES
        if (_LOCALES_DIR / f"{lang_code}.json").exists()
    }

    _fallback = _all_locales.get(DEFAULT_LANGUAGE, {})
    _missing_keys = set()
    _initialized = True
    set_language(lang)


def set_language(lang: str) -> str:
    """切换当前语言，并返回最终生效的语言代码。"""
    global _current_lang, _translations
    if not _initialized:
        init()
    normalized = normalize_language(lang)
    if normalized not in _all_locales:
        logger.warning("语言 '%s' 不可用，回退到 '%s'", lang, DEFAULT_LANGUAGE)
        normalized = DEFAULT_LANGUAGE
    _current_lang = normalized
    _translations = _all_locales.get(normalized, _fallback)
    return _current_lang


def get_language() -> str:
    """返回当前语言代码。"""
    return _current_lang


def get_available_languages() -> list[str]:
    """返回所有可用语言代码。"""
    if not _initialized:
        init()
    return [lang for lang in SUPPORTED_LANGUAGES if lang in _all_locales]


def get_language_options() -> tuple[tuple[str, str], ...]:
    """返回语言切换器使用的稳定顺序和原生名称。"""

    available = set(get_available_languages())
    return tuple(option for option in LANGUAGE_OPTIONS if option[0] in available)


def t(key: str, **kwargs: Any) -> str:
    """翻译函数：按 key 查找翻译文本，支持格式化参数。

    用法:
        t("common:process")             → "处理"
        t("logic:fileCount", count=10)  → "共 10 个文件"
    """
    global _initialized
    if not _initialized:
        init()
    namespace, separator, local_key = key.partition(":")
    if not separator or not namespace or not local_key:
        if key not in _missing_keys:
            logger.warning("翻译键必须使用 namespace:key 格式: '%s'", key)
            _missing_keys.add(key)
        return key

    text = _translations.get(namespace, {}).get(local_key)
    if text is None:
        # 回退到中文
        text = _fallback.get(namespace, {}).get(local_key, key)
    if text == key and key not in _missing_keys:
        logger.warning("缺少翻译键 '%s'（语言: %s）", key, _current_lang)
        _missing_keys.add(key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError, ValueError) as ex:
            logger.warning("翻译格式化失败（键: %s）: %s", key, ex)
    return text
