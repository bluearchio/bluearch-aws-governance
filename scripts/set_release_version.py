#!/usr/bin/env python3
"""Set runtime and package metadata versions for release builds."""

from __future__ import annotations

import re
import sys
from pathlib import Path

INIT_FILE = Path("cloud_governance/__init__.py")
PYPROJECT_FILE = Path("pyproject.toml")


def normalize_package_version(raw: str) -> str:
    """Return a PEP 440-compatible package version for pyproject.toml."""
    value = raw.strip()
    semver = re.fullmatch(
        r"v?(?P<base>\d+\.\d+\.\d+)(?:[-.]?(?P<pre>a|alpha|b|beta|rc)\.?(?P<pre_n>\d+))?",
        value,
        flags=re.IGNORECASE,
    )
    if semver:
        pre = semver.group("pre")
        if not pre:
            return semver.group("base")
        pre_map = {"alpha": "a", "beta": "b"}
        return f"{semver.group('base')}{pre_map.get(pre.lower(), pre.lower())}{semver.group('pre_n')}"

    if re.fullmatch(r"[a-f0-9]{7,40}", value, flags=re.IGNORECASE):
        return f"0.0.0.dev0+{value.lower()[:12]}"

    local = re.sub(r"[^A-Za-z0-9]+", ".", value).strip(".").lower()
    if not local:
        local = "local"
    return f"0.0.0.dev0+{local}"


def replace_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"Unable to update version in {path}")
    path.write_text(updated, encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: scripts/set_release_version.py <release-tag-or-sha>", file=sys.stderr)
        return 2

    runtime_version = sys.argv[1].strip()
    package_version = normalize_package_version(runtime_version)

    replace_once(
        INIT_FILE,
        r'^__version__ = "[^"]+"',
        f'__version__ = "{runtime_version}"',
    )
    replace_once(
        PYPROJECT_FILE,
        r'^version = "[^"]+"',
        f'version = "{package_version}"',
    )

    print(f"Runtime version: {runtime_version}")
    print(f"Package version: {package_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
