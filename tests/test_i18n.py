"""i18n catalog, namespace, and interpolation safeguards."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("zh", "en", "mn")
PLACEHOLDER_RE = re.compile(r"(?<!\$)\{([A-Za-z_][A-Za-z0-9_]*)\}")
LEAK_RE = re.compile(
    r"className=|onClick=|latest_data\.get|total\[|join\(|setStatus\(\{|notify\(`|\$\{"
)
CJK_RE = re.compile(r"[\u3400-\u9fff]")
LEGACY_HASH_KEY_RE = re.compile(r"_[0-9a-f]{4,}$")
I18N_LITERAL_RE = re.compile(r"([\"'`])((?:\\.|(?!\1).)*?)\1")
I18N_CALL_RE = re.compile(r"(?:i18n\.t|(?<![\w.])t)\(\s*[\"']([^\"']+)[\"']")


def _load_catalogs(directory: str) -> dict[str, dict[str, str]]:
    catalogs = {}
    for language in LANGUAGES:
        nested = json.loads((ROOT / directory / f"{language}.json").read_text(encoding="utf-8"))
        catalogs[language] = {
            f"{namespace}:{key}": value
            for namespace, entries in nested.items()
            for key, value in entries.items()
        }
    return catalogs


@pytest.mark.parametrize("directory", ("src/locales",))
def test_locale_catalogs_have_matching_keys_and_placeholders(directory: str):
    catalogs = _load_catalogs(directory)
    key_sets = [set(catalog) for catalog in catalogs.values()]
    assert key_sets[0] == key_sets[1] == key_sets[2]

    for key in key_sets[0]:
        placeholders = {
            language: sorted(PLACEHOLDER_RE.findall(catalogs[language][key]))
            for language in LANGUAGES
        }
        assert placeholders["zh"] == placeholders["en"] == placeholders["mn"], key


@pytest.mark.parametrize("directory", ("src/locales",))
def test_locale_values_do_not_expose_source_fragments(directory: str):
    catalogs = _load_catalogs(directory)
    for language, catalog in catalogs.items():
        assert all(isinstance(value, str) and value for value in catalog.values())
        leaked = {key: value for key, value in catalog.items() if LEAK_RE.search(value)}
        assert leaked == {}, f"{directory}/{language}.json contains source fragments: {leaked}"


@pytest.mark.parametrize("directory", ("src/locales",))
def test_non_default_locales_do_not_leak_cjk_ui_text(directory: str):
    """EN/MH must not silently fall back to Chinese UI copy."""
    catalogs = _load_catalogs(directory)
    for language in ("en", "mn"):
        leaked = {
            key: value
            for key, value in catalogs[language].items()
            if CJK_RE.search(value)
        }
        assert leaked == {}, f"{directory}/{language}.json contains CJK UI text: {leaked}"


@pytest.mark.parametrize("directory", ("src/locales",))
def test_locale_keys_do_not_use_legacy_hash_suffixes(directory: str):
    """Namespace keys remain stable semantic identifiers after the migration."""
    catalogs = _load_catalogs(directory)
    legacy = sorted(key for key in catalogs["zh"] if LEGACY_HASH_KEY_RE.search(key.rsplit(":", 1)[-1]))
    assert legacy == []
    assert all(not CJK_RE.search(key.rsplit(":", 1)[-1]) for key in catalogs["zh"])


def test_source_i18n_literals_do_not_use_legacy_hash_suffixes():
    """Literal Tauri references must use the renamed semantic keys too."""
    legacy = []
    for source_root in (ROOT / "src",):
        for path in source_root.rglob("*"):
            if path.suffix not in {".ts", ".tsx", ".py"}:
                continue
            for match in I18N_LITERAL_RE.finditer(path.read_text(encoding="utf-8")):
                literal = match.group(2)
                if ":" in literal and LEGACY_HASH_KEY_RE.search(literal.rsplit(":", 1)[-1]):
                    legacy.append(f"{path}:{literal}")
    assert legacy == []


def test_source_i18n_calls_are_namespaced_and_resolvable():
    """Every production literal call must use namespace:key and exist in the app catalog."""
    catalogs = _load_catalogs("src/locales")
    catalog_keys = set(catalogs["zh"])
    unnamespaced: list[str] = []
    missing: list[str] = []
    source_root = ROOT / "src"
    for path in source_root.rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".py"} or "/test" in str(path):
            continue
        for match in I18N_CALL_RE.finditer(path.read_text(encoding="utf-8")):
            key = match.group(1)
            if ":" not in key:
                unnamespaced.append(f"{path}:{key}")
            elif key not in catalog_keys:
                missing.append(f"{path}:{key}")
    assert unnamespaced == []
    assert missing == []


def test_business_identifiers_remain_chinese_and_do_not_depend_on_i18n():
    """Locale changes must not rename business columns, sheets, or ledger exports."""
    llm_business = (ROOT / "src/lib/llm-labeling.ts").read_text(encoding="utf-8")
    assert "from \"../i18n\"" not in llm_business
    assert '"维修内容列"' in llm_business
    assert "列映射冲突：" in llm_business
