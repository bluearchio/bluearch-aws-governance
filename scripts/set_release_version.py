#!/usr/bin/env python3
"""Set runtime and package metadata versions from a canonical release tag."""

from __future__ import annotations

import re
import sys
from pathlib import Path

INIT_FILE = Path("cloud_governance/__init__.py")
PYPROJECT_FILE = Path("pyproject.toml")


def normalize_release_tag(raw: str) -> str:
    """Validate a stable release tag and return its bare version."""
    value = raw
    if not re.fullmatch(r"v\d+\.\d+\.\d+", value):
        raise ValueError("release version must match vX.Y.Z")
    return value[1:]


def replace_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"Unable to update version in {path}")
    path.write_text(updated, encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: scripts/set_release_version.py <vX.Y.Z>", file=sys.stderr)
        return 2

    try:
        package_version = normalize_release_tag(sys.argv[1])
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    replace_once(
        INIT_FILE,
        r'^__version__ = "[^"]+"',
        f'__version__ = "{package_version}"',
    )
    replace_once(
        PYPROJECT_FILE,
        r'^version = "[^"]+"',
        f'version = "{package_version}"',
    )

    print(f"Runtime version: {package_version}")
    print(f"Package version: {package_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
