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


def test_gui_i18n_normalizes_language_and_supports_namespaces():
    original = i18n.get_language()
    try:
        assert i18n.normalize_language("en-US") == "en"
        assert i18n.normalize_language("mn_MN") == "mn"
        assert i18n.normalize_language("fr-FR") is None

        i18n.init("en-US")
        assert i18n.get_language() == "en"
        assert i18n.t("common:ok") == "OK"
        assert i18n.t("logic:成功:跳过:失败:_86d9", success=1, skipped=2, failed=3) == (
            "Success: 1  Skipped: 2  Failed: 3"
        )
        assert "preview.xlsx" in i18n.t("logic:previewFile", dry_run_file="preview.xlsx")
        assert i18n.t("common.ok") == "common.ok"
    finally:
        i18n.init(original)
