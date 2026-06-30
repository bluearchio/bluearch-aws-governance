"""Catalog support metadata for executable misconfiguration rules."""

from typing import Dict, Iterable

from .evaluators.registry import get_evaluator
from .registry import SERVICE_TO_RESOURCE_TYPES

SUPPORT_EXECUTABLE = "executable"
SUPPORT_MAPPED = "mapped"
SUPPORT_UNSUPPORTED = "unsupported"


def get_catalog_entry_support(entry: dict) -> dict:
    """Return UI/API support metadata for a misconfig catalog entry.

    A catalog entry is selectable only when BlueArch has a concrete evaluator for
    it. Service-mapped entries without evaluators are visible but disabled so the
    catalog can grow without accidentally creating noisy advisory-only policies.
    """
    misconfig_id = entry.get("id")
    service_name = (entry.get("service_name") or "").lower()
    mapped_resource_types = list(SERVICE_TO_RESOURCE_TYPES.get(service_name, []))
    evaluator = get_evaluator(misconfig_id) if misconfig_id else None

    if evaluator:
        resource_types = list(evaluator.applicable_resource_types or mapped_resource_types)
        return {
            "support_level": SUPPORT_EXECUTABLE,
            "selectable": True,
            "supported": True,
            "has_evaluator": True,
            "resource_types": resource_types,
            "support_reason": "Executable evaluator available.",
        }

    if mapped_resource_types:
        return {
            "support_level": SUPPORT_MAPPED,
            "selectable": False,
            "supported": False,
            "has_evaluator": False,
            "resource_types": mapped_resource_types,
            "support_reason": "BlueArch scans this resource type, but this catalog entry has no executable evaluator yet.",
        }

    return {
        "support_level": SUPPORT_UNSUPPORTED,
        "selectable": False,
        "supported": False,
        "has_evaluator": False,
        "resource_types": [],
        "support_reason": "BlueArch does not collect this service/resource type yet.",
    }


def is_executable_entry(entry: dict) -> bool:
    """Return True when a catalog entry has executable evaluator support."""
    return get_catalog_entry_support(entry)["support_level"] == SUPPORT_EXECUTABLE


def filter_executable_entries(entries: Iterable[dict]) -> list:
    """Return only catalog entries that can be executed as confirmed checks."""
    return [entry for entry in entries if is_executable_entry(entry)]


def find_unexecutable_ids(registry, misconfig_ids: Iterable[str]) -> dict:
    """Return unknown and non-executable IDs from a requested rule list."""
    unknown = []
    unsupported = []

    for misconfig_id in misconfig_ids or []:
        entry = registry.get(misconfig_id)
        if not entry:
            unknown.append(misconfig_id)
        elif not is_executable_entry(entry):
            unsupported.append(misconfig_id)

    return {
        "unknown": unknown,
        "unsupported": unsupported,
    }


def summarize_support(entries: Iterable[dict]) -> Dict[str, int]:
    """Count catalog entries by support level."""
    counts = {
        SUPPORT_EXECUTABLE: 0,
        SUPPORT_MAPPED: 0,
        SUPPORT_UNSUPPORTED: 0,
    }
    for entry in entries:
        support = get_catalog_entry_support(entry)
        counts[support["support_level"]] += 1
    return counts


def build_support_map(entries: Iterable[dict]) -> Dict[str, dict]:
    """Build an id -> support metadata map for catalog entries."""
    support_map: Dict[str, dict] = {}
    for entry in entries:
        misconfig_id = entry.get("id")
        if misconfig_id:
            support_map[misconfig_id] = get_catalog_entry_support(entry)
    return support_map


def summarize_support_map(support_map: Dict[str, dict]) -> Dict[str, int]:
    """Count support levels from a precomputed support map."""
    counts = {
        SUPPORT_EXECUTABLE: 0,
        SUPPORT_MAPPED: 0,
        SUPPORT_UNSUPPORTED: 0,
    }
    for support in support_map.values():
        counts[support["support_level"]] += 1
    return counts
