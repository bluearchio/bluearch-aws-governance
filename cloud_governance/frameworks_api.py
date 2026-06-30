"""Read-only framework coverage API for Governance Hub."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/frameworks", tags=["frameworks"])

STORAGE_NAMESPACE = "governance-hub"
FINDINGS_COLLECTION = "misconfig-findings"
POLICIES_COLLECTION = "misconfig-policies"
CoreClient: Any = None

PILLARS = (
    {"id": "operational_excellence", "label": "Operational Excellence"},
    {"id": "security", "label": "Security"},
    {"id": "reliability", "label": "Reliability"},
    {"id": "performance_efficiency", "label": "Performance Efficiency"},
    {"id": "cost_optimization", "label": "Cost Optimization"},
    {"id": "sustainability", "label": "Sustainability"},
)

PILLAR_ALIASES = {
    "operational excellence": "operational_excellence",
    "operational-excellence": "operational_excellence",
    "operational_excellence": "operational_excellence",
    "operations": "operational_excellence",
    "security": "security",
    "reliability": "reliability",
    "performance": "performance_efficiency",
    "performance efficiency": "performance_efficiency",
    "performance-efficiency": "performance_efficiency",
    "performance_efficiency": "performance_efficiency",
    "cost": "cost_optimization",
    "cost optimization": "cost_optimization",
    "cost-optimization": "cost_optimization",
    "cost_optimization": "cost_optimization",
    "sustainability": "sustainability",
}

RISK_DETAIL_PILLARS = {
    "operations": "operational_excellence",
    "operational": "operational_excellence",
    "security": "security",
    "reliability": "reliability",
    "performance": "performance_efficiency",
    "cost": "cost_optimization",
    "sustainability": "sustainability",
}

WELL_ARCHITECTED_POLICY_DESCRIPTIONS = {
    "operational_excellence": "Operational controls for observability, governance, maintenance, and safe day-to-day cloud operations.",
    "security": "Security controls for identity, access, encryption, exposure, auditability, and detective safeguards.",
    "reliability": "Reliability controls for backup, recovery, availability, redundancy, and failure tolerance.",
    "performance_efficiency": "Performance controls for right-sized capacity, latency, throughput, and managed service efficiency.",
    "cost_optimization": "Cost controls for unused resources, overprovisioning, purchasing options, lifecycle policies, and waste reduction.",
    "sustainability": "Sustainability controls for resource efficiency and reduced waste where catalog checks explicitly map to that pillar.",
}

FRAMEWORKS = (
    {"id": "well_architected", "label": "Well-Architected", "external_ref_key": "well_architected"},
    {"id": "attack", "label": "MITRE ATT&CK", "external_ref_key": "attack_technique"},
    {"id": "d3fend", "label": "D3FEND", "external_ref_key": "d3fend"},
    {"id": "cis", "label": "CIS AWS", "external_ref_key": "cis_aws"},
    {"id": "config", "label": "AWS Config", "external_ref_key": "config_rule"},
    {"id": "prowler", "label": "Prowler", "external_ref_key": "prowler_check"},
    {"id": "trusted_advisor", "label": "Trusted Advisor", "external_ref_key": "trusted_advisor"},
    {"id": "cwe", "label": "CWE", "external_ref_key": "cwe"},
)

EXTERNAL_REF_KEYS = tuple(item["external_ref_key"] for item in FRAMEWORKS)
FRAMEWORK_ALIASES = {
    "well-architected": "well_architected",
    "well_architected": "well_architected",
    "wellarchitected": "well_architected",
    "attack": "attack_technique",
    "att&ck": "attack_technique",
    "mitre": "attack_technique",
    "attack_technique": "attack_technique",
    "attack-technique": "attack_technique",
    "d3fend": "d3fend",
    "cis": "cis_aws",
    "cis_aws": "cis_aws",
    "cis-aws": "cis_aws",
    "config": "config_rule",
    "aws_config": "config_rule",
    "config_rule": "config_rule",
    "config-rule": "config_rule",
    "prowler": "prowler_check",
    "prowler_check": "prowler_check",
    "prowler-check": "prowler_check",
    "trusted_advisor": "trusted_advisor",
    "trusted-advisor": "trusted_advisor",
    "trustedadvisor": "trusted_advisor",
    "cwe": "cwe",
}


@router.get("/coverage")
def framework_coverage():
    entries = _list_catalog_entries()
    open_findings = _open_finding_counts()
    controls = [_control_from_entry(entry, open_findings) for entry in entries]
    mapped_controls = [control for control in controls if _is_mapped_control(control)]

    pillar_rows = {
        pillar["id"]: {
            "id": pillar["id"],
            "label": pillar["label"],
            "catalog_count": 0,
            "executable_count": 0,
            "open_findings": 0,
        }
        for pillar in PILLARS
    }
    framework_rows = {
        item["id"]: {
            "id": item["id"],
            "label": item["label"],
            "external_ref_key": item["external_ref_key"],
            "catalog_count": 0,
            "explicit_count": 0,
            "inferred_count": 0,
            "open_findings": 0,
        }
        for item in FRAMEWORKS
    }
    unassigned_mapped_total = 0

    for control in mapped_controls:
        if control["pillars"]:
            for pillar in control["pillars"]:
                row = pillar_rows.get(pillar)
                if not row:
                    continue
                row["catalog_count"] += 1
                if control["executable"]:
                    row["executable_count"] += 1
                row["open_findings"] += control["open_findings"]
        else:
            unassigned_mapped_total += 1

        for framework in FRAMEWORKS:
            key = framework["external_ref_key"]
            row = framework_rows[framework["id"]]
            if control["external_refs"].get(key):
                row["explicit_count"] += 1
                row["catalog_count"] += 1
                row["open_findings"] += control["open_findings"]
            elif key == "well_architected" and control["pillars"]:
                row["inferred_count"] += 1
                row["catalog_count"] += 1
                row["open_findings"] += control["open_findings"]

    total = len(entries)
    mapped_total = len(mapped_controls)
    return {
        "status": "available" if mapped_total else "unmapped",
        "catalog_total": total,
        "mapped_catalog_total": mapped_total,
        "unmapped_catalog_total": max(0, total - mapped_total),
        "unassigned_mapped_total": unassigned_mapped_total,
        "open_findings_total": sum(control["open_findings"] for control in mapped_controls),
        "pillars": list(pillar_rows.values()),
        "frameworks": list(framework_rows.values()),
        "scan_context": _scan_context(),
    }


@router.get("/controls")
def framework_controls(
    pillar: Optional[str] = Query(None),
    framework: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    normalized_pillar = _normalize_pillar(pillar) if pillar else None
    external_ref_key = _normalize_framework_key(framework) if framework else None
    search_term = (search or "").strip().lower()
    if pillar and not normalized_pillar:
        return {"items": [], "total": 0, "limit": limit}
    if framework and not external_ref_key:
        return {"items": [], "total": 0, "limit": limit}

    open_findings = _open_finding_counts()
    controls = []
    for entry in _list_catalog_entries():
        control = _control_from_entry(entry, open_findings)
        if not _is_mapped_control(control):
            continue
        if normalized_pillar and normalized_pillar not in control["pillars"]:
            continue
        if external_ref_key == "well_architected":
            if not control["pillars"] and not control["external_refs"].get(external_ref_key):
                continue
        elif external_ref_key and not control["external_refs"].get(external_ref_key):
            continue
        if search_term and search_term not in _control_search_text(control):
            continue
        controls.append(control)

    controls.sort(
        key=lambda item: (
            -int(item["open_findings"] or 0),
            _support_sort_rank(item),
            -int(item.get("risk_value") or 0),
            item["title"].lower(),
        )
    )
    return {"items": controls[:limit], "total": len(controls), "limit": limit}


@router.get("/policies")
def well_architected_policies():
    open_findings = _open_finding_counts()
    controls = [_control_from_entry(entry, open_findings) for entry in _list_catalog_entries()]
    existing = _existing_framework_policies()
    items = []
    for pillar in PILLARS:
        pack = _policy_pack_from_controls(pillar, controls)
        current = existing.get(pack["id"])
        if current:
            pack["misconfig_policy_id"] = current.get("id")
            pack["enabled"] = bool(current.get("enabled", True))
            pack["resources_flagged"] = int(current.get("resources_flagged") or 0)
            pack["last_scanned_at"] = current.get("last_scanned_at")
        items.append(pack)
    return {"items": items, "total": len(items)}


@router.post("/policies/{framework_policy_id}/activate")
def activate_well_architected_policy(framework_policy_id: str):
    open_findings = _open_finding_counts()
    controls = [_control_from_entry(entry, open_findings) for entry in _list_catalog_entries()]
    packs = {_policy_pack_id(pillar["id"]): _policy_pack_from_controls(pillar, controls) for pillar in PILLARS}
    pack = packs.get(framework_policy_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Well-Architected policy pack not found")
    if not pack["misconfig_ids"]:
        raise HTTPException(status_code=400, detail="This Well-Architected policy pack has no executable checks yet")

    existing = _existing_framework_policies().get(framework_policy_id)
    now = _now()
    policy = dict(existing or {})
    policy.update(
        {
            "id": policy.get("id") or str(uuid.uuid4()),
            "name": pack["name"],
            "description": pack["description"],
            "resource_types": policy.get("resource_types") or [],
            "risk_types": [pack["pillar"]],
            "min_risk_value": int(policy.get("min_risk_value") or 0),
            "misconfig_ids": pack["misconfig_ids"],
            "exclude_patterns": policy.get("exclude_patterns") or [],
            "enabled": True,
            "priority": int(policy.get("priority") or 90),
            "resources_flagged": int(policy.get("resources_flagged") or 0),
            "last_scanned_at": policy.get("last_scanned_at"),
            "framework": "well_architected",
            "framework_policy_id": framework_policy_id,
            "framework_pillar": pack["pillar"],
            "updated_at": now,
        }
    )
    policy.setdefault("created_at", now)
    _save_policy(policy)
    pack["misconfig_policy_id"] = policy["id"]
    pack["enabled"] = True
    pack["resources_flagged"] = int(policy.get("resources_flagged") or 0)
    pack["last_scanned_at"] = policy.get("last_scanned_at")
    return pack


def _list_catalog_entries() -> list[dict[str, Any]]:
    client = _core_client(timeout=60)
    entries: list[dict[str, Any]] = []
    offset = 0
    limit = 1000
    while True:
        page = client.catalog(limit=limit, offset=offset)
        page_entries = page.get("entries") or page.get("items") or []
        entries.extend(page_entries)
        total = int(page.get("total") or len(entries))
        if len(page_entries) < limit or len(entries) >= total:
            break
        offset += limit
    return entries


def _open_finding_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in _list_storage(FINDINGS_COLLECTION):
        payload = record.get("payload") or {}
        if payload.get("status") != "open":
            continue
        misconfig_id = payload.get("misconfig_id")
        if not misconfig_id:
            continue
        key = str(misconfig_id)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _list_storage(collection: str) -> list[dict[str, Any]]:
    client = _core_client()
    records: list[dict[str, Any]] = []
    offset = 0
    limit = 10000
    while True:
        page = client.list_storage(STORAGE_NAMESPACE, collection, limit=limit, offset=offset)
        records.extend(page)
        if len(page) < limit:
            break
        offset += limit
    return records


def _core_client(**kwargs):
    global CoreClient
    if CoreClient is None:
        from .core_client import CoreClient as ImportedCoreClient

        CoreClient = ImportedCoreClient
    return CoreClient(**kwargs)


def _control_from_entry(entry: dict[str, Any], open_findings: dict[str, int]) -> dict[str, Any]:
    payload = entry.get("payload") or {}
    catalog_id = str(entry.get("catalog_id") or entry.get("id") or payload.get("id") or "")
    executable = bool(entry.get("executable") or payload.get("executable"))
    pillars = _extract_pillars(payload)
    external_refs = _extract_external_refs(payload)
    mapping_sources = _mapping_sources(pillars, external_refs)
    return {
        "catalog_id": catalog_id,
        "title": _entry_title(entry, payload, catalog_id),
        "service": entry.get("service") or payload.get("service_name") or payload.get("service"),
        "risk_detail": payload.get("risk_detail") or entry.get("category"),
        "risk_value": _risk_value(entry, payload),
        "executable": executable,
        "support_status": _support_status(payload, executable),
        "support_reason": _support_reason(payload, executable),
        "pillars": pillars,
        "external_refs": external_refs,
        "mapping_sources": mapping_sources,
        "mapping_source": _primary_mapping_source(mapping_sources),
        "open_findings": open_findings.get(catalog_id, 0),
    }


def _entry_title(entry: dict[str, Any], payload: dict[str, Any], catalog_id: str) -> str:
    for key in (
        "title",
        "behavior_title",
        "finding_title",
        "countermeasure_title",
        "scenario",
        "recommendation_action",
    ):
        value = entry.get(key) if key == "title" else payload.get(key)
        if value:
            return str(value)
    return catalog_id or "Untitled control"


def _risk_value(entry: dict[str, Any], payload: dict[str, Any]) -> int | None:
    value = payload.get("risk_value", entry.get("severity"))
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_pillars(payload: dict[str, Any]) -> list[str]:
    pillars = []
    for raw in _as_list(payload.get("pillars")):
        normalized = _normalize_pillar(raw)
        if normalized and normalized not in pillars:
            pillars.append(normalized)
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    for raw in _as_list(metadata.get("pillars")):
        normalized = _normalize_pillar(raw)
        if normalized and normalized not in pillars:
            pillars.append(normalized)
    for normalized in _catalog_risk_pillars(payload):
        if normalized not in pillars:
            pillars.append(normalized)
    return pillars


def _catalog_risk_pillars(payload: dict[str, Any]) -> list[str]:
    pillars = []
    raw_values = []
    raw_values.extend(_as_list(payload.get("risk_detail")))
    if not raw_values:
        raw_values.extend(_as_list(payload.get("category")))
    for raw_value in raw_values:
        for token in str(raw_value).replace("/", ",").replace(";", ",").split(","):
            normalized = RISK_DETAIL_PILLARS.get(token.strip().lower())
            if normalized and normalized not in pillars:
                pillars.append(normalized)
    return pillars


def _extract_external_refs(payload: dict[str, Any]) -> dict[str, list[str]]:
    refs = payload.get("external_refs") or {}
    if not isinstance(refs, dict):
        refs = {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    metadata_refs = metadata.get("external_refs") if isinstance(metadata.get("external_refs"), dict) else {}
    extracted = {}
    for key in EXTERNAL_REF_KEYS:
        values = _as_list(refs.get(key))
        for metadata_value in _as_list(metadata_refs.get(key)):
            if metadata_value not in values:
                values.append(metadata_value)
        extracted[key] = values
    return extracted


def _mapping_sources(pillars: list[str], external_refs: dict[str, list[str]]) -> dict[str, str]:
    sources = {}
    for framework in FRAMEWORKS:
        key = framework["external_ref_key"]
        if external_refs.get(key):
            sources[key] = "explicit"
        elif key == "well_architected" and pillars:
            sources[key] = "inferred"
        else:
            sources[key] = "none"
    return sources


def _primary_mapping_source(mapping_sources: dict[str, str]) -> str:
    if any(source == "explicit" for source in mapping_sources.values()):
        return "explicit"
    if any(source == "inferred" for source in mapping_sources.values()):
        return "inferred"
    return "none"


def _support_status(payload: dict[str, Any], executable: bool) -> str:
    if executable:
        return "executable"
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    status = str(metadata.get("detector_status") or metadata.get("detection_status") or "").strip().lower()
    if status in {"planned", "planned_resource_metadata", "detector-candidate", "resource_metadata_candidate"}:
        return "planned"
    if status in {"manual_review", "unsupported_manual", "unsupported", "not_detectable"}:
        return "unsupported"
    return "unsupported"


def _support_reason(payload: dict[str, Any], executable: bool) -> str | None:
    if executable:
        return "Detector is implemented and can run through Governance Hub scans."
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    for key in ("support_reason", "unsupported_reason", "detector_notes"):
        value = metadata.get(key)
        if value:
            return str(value)
    return "No executable Governance Hub detector is mapped to this catalog control yet."


def _support_sort_rank(control: dict[str, Any]) -> int:
    status = control.get("support_status")
    if status == "executable":
        return 0
    if status == "planned":
        return 1
    return 2


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = [value]
    return [str(item).strip() for item in values if str(item).strip()]


def _normalize_pillar(value: str | None) -> str | None:
    if not value:
        return None
    key = str(value).strip().lower().replace("_", " ")
    return PILLAR_ALIASES.get(key) or PILLAR_ALIASES.get(key.replace(" ", "-")) or PILLAR_ALIASES.get(key.replace(" ", "_"))


def _normalize_framework_key(value: str | None) -> str | None:
    if not value:
        return None
    key = str(value).strip().lower().replace(" ", "_")
    if key in EXTERNAL_REF_KEYS:
        return key
    return FRAMEWORK_ALIASES.get(key) or FRAMEWORK_ALIASES.get(key.replace("_", "-"))


def _is_mapped_control(control: dict[str, Any]) -> bool:
    if control["pillars"]:
        return True
    return any(values for values in control["external_refs"].values())


def _scan_context() -> dict[str, Any]:
    context = {
        "resource_total": 0,
        "account_count": 0,
        "region_count": 0,
        "service_count": 0,
        "by_service": [],
        "by_region": [],
        "by_account": [],
        "status": "unavailable",
    }
    try:
        summary = _core_client(timeout=10).proxy("GET", "/api/v1/resources/summary")
    except Exception as exc:
        context["error"] = str(exc)
        return context

    if not isinstance(summary, dict):
        return context

    by_service = _summary_rows(summary.get("by_service"), "service_name")
    by_region = _summary_rows(summary.get("by_region"), "region")
    by_account = _summary_rows(summary.get("by_account"), "account_id", label_key="account_name")
    context.update(
        {
            "resource_total": int(summary.get("total") or 0),
            "account_count": len(by_account),
            "region_count": len(by_region),
            "service_count": len(by_service),
            "by_service": by_service[:10],
            "by_region": by_region[:10],
            "by_account": by_account[:10],
            "status": "available",
        }
    )
    return context


def _summary_rows(value: Any, key: str, label_key: str | None = None) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = item.get(key) or item.get(key.replace("_name", "")) or item.get("service") or item.get("region")
        if not name:
            continue
        row = {
            "key": str(name),
            "count": int(item.get("count") or 0),
        }
        if label_key and item.get(label_key):
            row["label"] = str(item.get(label_key))
        rows.append(row)
    rows.sort(key=lambda item: (-int(item.get("count") or 0), item.get("key") or ""))
    return rows


def _control_search_text(control: dict[str, Any]) -> str:
    refs = []
    for values in control["external_refs"].values():
        refs.extend(values)
    return " ".join(
        str(value or "")
        for value in (
            control.get("catalog_id"),
            control.get("title"),
            control.get("service"),
            control.get("risk_detail"),
            control.get("support_status"),
            " ".join(control.get("pillars") or []),
            " ".join(refs),
        )
    ).lower()


def _policy_pack_from_controls(pillar: dict[str, str], controls: list[dict[str, Any]]) -> dict[str, Any]:
    pillar_controls = [control for control in controls if pillar["id"] in control["pillars"]]
    executable_controls = [control for control in pillar_controls if control["executable"]]
    planned_controls = [control for control in pillar_controls if control.get("support_status") == "planned"]
    unsupported_controls = [
        control
        for control in pillar_controls
        if not control["executable"] and control.get("support_status") != "planned"
    ]
    misconfig_ids = sorted({control["catalog_id"] for control in executable_controls if control["catalog_id"]})
    return {
        "id": _policy_pack_id(pillar["id"]),
        "pillar": pillar["id"],
        "name": f"AWS Well-Architected - {pillar['label']}",
        "description": WELL_ARCHITECTED_POLICY_DESCRIPTIONS[pillar["id"]],
        "catalog_count": len(pillar_controls),
        "executable_count": len(executable_controls),
        "planned_count": len(planned_controls),
        "unsupported_count": len(unsupported_controls),
        "open_findings": sum(int(control.get("open_findings") or 0) for control in pillar_controls),
        "misconfig_ids": misconfig_ids,
        "enabled": False,
        "misconfig_policy_id": None,
        "resources_flagged": 0,
        "last_scanned_at": None,
    }


def _policy_pack_id(pillar_id: str) -> str:
    return f"well_architected_{pillar_id}"


def _existing_framework_policies() -> dict[str, dict[str, Any]]:
    policies = {}
    for record in _list_storage(POLICIES_COLLECTION):
        payload = record.get("payload") or {}
        framework_policy_id = payload.get("framework_policy_id")
        if framework_policy_id:
            policies[str(framework_policy_id)] = payload
    return policies


def _save_policy(policy: dict[str, Any]) -> None:
    _core_client().upsert_storage(STORAGE_NAMESPACE, POLICIES_COLLECTION, policy["id"], policy)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
