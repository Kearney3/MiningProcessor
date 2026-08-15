"""i18n catalog, namespace, and interpolation safeguards."""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from gui import i18n


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


@pytest.mark.parametrize("directory", ("src/locales", "gui/locales"))
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


@pytest.mark.parametrize("directory", ("src/locales", "gui/locales"))
def test_locale_values_do_not_expose_source_fragments(directory: str):
    catalogs = _load_catalogs(directory)
    for language, catalog in catalogs.items():
        assert all(isinstance(value, str) and value for value in catalog.values())
        leaked = {key: value for key, value in catalog.items() if LEAK_RE.search(value)}
        assert leaked == {}, f"{directory}/{language}.json contains source fragments: {leaked}"


@pytest.mark.parametrize("directory", ("src/locales", "gui/locales"))
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


@pytest.mark.parametrize("directory", ("src/locales", "gui/locales"))
def test_locale_keys_do_not_use_legacy_hash_suffixes(directory: str):
    """Namespace keys remain stable semantic identifiers after the migration."""
    catalogs = _load_catalogs(directory)
    legacy = sorted(key for key in catalogs["zh"] if LEGACY_HASH_KEY_RE.search(key.rsplit(":", 1)[-1]))
    assert legacy == []
    assert all(not CJK_RE.search(key.rsplit(":", 1)[-1]) for key in catalogs["zh"])


def test_source_i18n_literals_do_not_use_legacy_hash_suffixes():
    """Literal Flet/Tauri references must use the renamed semantic keys too."""
    legacy = []
    for source_root in (ROOT / "src", ROOT / "gui"):
        for path in source_root.rglob("*"):
            if path.suffix not in {".ts", ".tsx", ".py"}:
                continue
            for match in I18N_LITERAL_RE.finditer(path.read_text(encoding="utf-8")):
                literal = match.group(2)
                if ":" in literal and LEGACY_HASH_KEY_RE.search(literal.rsplit(":", 1)[-1]):
                    legacy.append(f"{path}:{literal}")
    assert legacy == []


@pytest.mark.parametrize("app", ("src", "gui"))
def test_source_i18n_calls_are_namespaced_and_resolvable(app: str):
    """Every production literal call must use namespace:key and exist in the app catalog."""
    catalogs = _load_catalogs(f"{app}/locales")
    catalog_keys = set(catalogs["zh"])
    unnamespaced: list[str] = []
    missing: list[str] = []
    source_root = ROOT / app
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

    ledger_specs = {
        "ledger.py": ("设备台账", "设备台账模板.xlsx"),
        "oil_ledger.py": ("油品台账", "油品台账模板.xlsx"),
        "model_ledger.py": ("型号台账", "型号台账模板.xlsx"),
    }
    for filename, (title, template) in ledger_specs.items():
        source = (ROOT / "gui/components" / filename).read_text(encoding="utf-8")
        assert f'section_title="{title}"' in source
        assert f'template_filename="{template}"' in source

    ledger_base = (ROOT / "gui/components/ledger_base.py").read_text(encoding="utf-8")
    assert 'write_formatted_excel(save_path, {"模板": df})' in ledger_base


def test_gui_i18n_normalizes_language_and_supports_namespaces():
    original = i18n.get_language()
    try:
        assert i18n.normalize_language("en-US") == "en"
        assert i18n.normalize_language("mn_MN") == "mn"
        assert i18n.normalize_language("fr-FR") is None

        i18n.init("en-US")
        assert i18n.get_language() == "en"
        assert i18n.t("common:ok") == "OK"
        assert "pending review" in i18n.t("components:llm_labeling.inputValuesHint")
        assert i18n.t("logic:successSkippedFailed", success=1, skipped=2, failed=3) == (
            "Success: 1  Skipped: 2  Failed: 3"
        )
        assert "preview.xlsx" in i18n.t("logic:previewFile", dry_run_file="preview.xlsx")
        assert i18n.t("common.ok") == "common.ok"
    finally:
        i18n.init(original)
