#!/usr/bin/env python3
"""
统一版本号管理工具 — 以 pyproject.toml 为唯一真相源

用法：
    uv run scripts/bump_version.py               # 同步（仅同步，不改变版本）
    uv run scripts/bump_version.py 1.3.1          # 设置指定版本
    uv run scripts/bump_version.py --bump patch   # 1.2.0 → 1.2.1
    uv run scripts/bump_version.py --bump minor   # 1.2.0 → 1.3.0
    uv run scripts/bump_version.py --bump major   # 1.2.0 → 2.0.0
    uv run scripts/bump_version.py --dry-run      # 预览变更，不实际写入
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# 项目根目录（脚本位于 scripts/ 下）
ROOT = Path(__file__).resolve().parent.parent

# ── 版本号所在文件与对应的正则替换规则 ──────────────────────────────

_TARGETS: list[tuple[Path, str, str]] = [
    # (相对路径, 匹配模式, 替换模板)
    (
        Path("pyproject.toml"),
        r'(?m)^(version\s*=\s*")([^"]+)(")',
        r'\g<1>{version}\3',
    ),
    (
        Path("package.json"),
        r'(?m)^(\s*"version"\s*:\s*")([^"]+)(")',
        r'\g<1>{version}\3',
    ),
    (
        Path("src-tauri/tauri.conf.json"),
        r'(?m)^(\s*"version"\s*:\s*")([^"]+)(")',
        r'\g<1>{version}\3',
    ),
    (
        Path("src-tauri/Cargo.toml"),
        r'(?m)^(version\s*=\s*")([^"]+)(")',
        r'\g<1>{version}\3',
    ),
]


def _read_version(pyproject: Path) -> str:
    text = pyproject.read_text(encoding="utf-8")
    m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    if not m:
        sys.exit("ERROR: pyproject.toml 中未找到 version 字段")
    return m.group(1)


def _bump(version: str, part: str) -> str:
    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        sys.exit(f"ERROR: 无效的语义版本号: {version}")
    major, minor, patch = (int(p) for p in parts)
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    sys.exit(f"ERROR: 未知的 bump 类型: {part}（可选 major/minor/patch）")


def _sync(version: str, *, dry_run: bool = False) -> None:
    for rel_path, pattern, replacement_tpl in _TARGETS:
        abs_path = ROOT / rel_path
        if not abs_path.exists():
            print(f"  SKIP  {rel_path}（文件不存在）")
            continue
        text = abs_path.read_text(encoding="utf-8")
        replacement = replacement_tpl.format(version=version)
        new_text, count = re.subn(pattern, replacement, text)
        if count == 0:
            print(f"  WARN  {rel_path}（未找到版本号字段）")
        elif new_text == text:
            print(f"  OK    {rel_path}（已是 {version}）")
        else:
            print(f"  {'PREVIEW' if dry_run else 'UPDATE'} {rel_path}")
            if not dry_run:
                abs_path.write_text(new_text, encoding="utf-8")


def main() -> None:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    if dry_run:
        args.remove("--dry-run")

    pyproject = ROOT / "pyproject.toml"
    current = _read_version(pyproject)

    if not args:
        # 无参数：仅同步当前版本到所有文件
        print(f"同步版本号: {current}")
        _sync(current, dry_run=dry_run)
        return

    if args[0] == "--bump":
        if len(args) < 2:
            sys.exit("ERROR: --bump 需要指定 part（major/minor/patch）")
        new_version = _bump(current, args[1])
    else:
        new_version = args[0]
        if not re.fullmatch(r"\d+\.\d+\.\d+", new_version):
            sys.exit(f"ERROR: 无效的版本号格式: {new_version}（期望 X.Y.Z）")

    print(f"版本号: {current} → {new_version}")
    _sync(new_version, dry_run=dry_run)

    if not dry_run:
        print(f"\n✅ 所有文件已更新到 {new_version}")
        print("   记得 commit 并打 tag：")
        print(f"   git add -A && git commit -m 'chore: bump version to {new_version}'")
        print(f"   git tag v{new_version}")


if __name__ == "__main__":
    main()
