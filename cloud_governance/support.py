"""Executable mapping import helpers."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any


def load_bluearch_executable_mapping(bluearch_api_path: str | None) -> dict[str, dict[str, Any]]:
    """Load executable evaluator mapping metadata.

    During the migration this first tries the legacy BlueArch evaluator path
    when provided. After the Governance Hub split, the registry lives in this
    package, so missing legacy modules fall back to the local registry.
    """
    registry_module: Any | None = None
    path: Path | None = None
    if bluearch_api_path:
        path = Path(bluearch_api_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"BlueArch API path not found: {path}")

        sys.path.insert(0, str(path))
        try:
            registry_module = importlib.import_module("modules.misconfig.evaluators.registry")
        except ModuleNotFoundError:
            registry_module = None
        finally:
            try:
                sys.path.remove(str(path))
            except ValueError:
                pass

    if registry_module is None:
        registry_module = importlib.import_module(
            "cloud_governance.modules.misconfig.evaluators.registry"
        )

    evaluator_registry = getattr(registry_module, "EVALUATOR_REGISTRY", {})
    mapping: dict[str, dict[str, Any]] = {}
    for catalog_id, evaluator in evaluator_registry.items():
        resource_types = list(getattr(evaluator, "applicable_resource_types", []) or [])
        description = getattr(evaluator, "description", None)
        mapping[catalog_id] = {
            "executable": True,
            "evaluator_key": catalog_id,
            "resource_types": resource_types,
            "resource_requirements": {
                "resource_types": resource_types,
                "legacy_description": description,
            },
        }
    return mapping
