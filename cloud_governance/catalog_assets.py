"""Bundled Governance Hub catalog asset helpers."""

from __future__ import annotations

import sys
from pathlib import Path


def package_data_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "cloud_governance"
    return Path(__file__).resolve().parent


def bundled_catalog_source_path() -> Path:
    return package_data_dir() / "catalog_seed"


def repository_catalog_source_path() -> Path:
    return Path(__file__).resolve().parents[1] / "catalog"


def is_catalog_source(path: Path) -> bool:
    return (path / "data" / "by-service").is_dir() or (path / "by-service").is_dir()


def resolve_catalog_source_path(configured: str | Path | None = None) -> Path | None:
    candidates = [Path(configured).expanduser()] if configured else []
    candidates.append(repository_catalog_source_path())
    candidates.append(bundled_catalog_source_path())
    for candidate in candidates:
        if is_catalog_source(candidate):
            return candidate.resolve()
    return None
