"""Governance Hub misconfiguration API.

This is the product-owned API surface copied from BlueArch CLI and adapted to
the core split: catalog and inventory come from bluearch-core, while Governance
Hub runs the executable evaluators and persists policies/findings through core
storage APIs.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .catalog_assets import resolve_catalog_source_path
from .core_client import CoreClient
from .modules.misconfig.evaluators.registry import EVALUATOR_REGISTRY
from .modules.misconfig.registry import MisconfigRegistry
from .modules.misconfig.scanner import MisconfigScanner, PolicyRecord, ResourceRecord
from .modules.misconfig.support import build_support_map, find_unexecutable_ids, summarize_support_map

router = APIRouter(prefix="/api/v1/misconfig", tags=["misconfig"])

STORAGE_NAMESPACE = "governance-hub"
POLICIES_COLLECTION = "misconfig-policies"
FINDINGS_COLLECTION = "misconfig-findings"


class CreatePolicyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    resource_types: Optional[list[str]] = None
    risk_types: Optional[list[str]] = None
    min_risk_value: int = Field(default=0, ge=0, le=3)
    misconfig_ids: Optional[list[str]] = None
    description: Optional[str] = None
    exclude_patterns: Optional[list[str]] = None
    enabled: bool = True


class UpdatePolicyRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    resource_types: Optional[list[str]] = None
    risk_types: Optional[list[str]] = None
    min_risk_value: Optional[int] = Field(default=None, ge=0, le=3)
    misconfig_ids: Optional[list[str]] = None
    description: Optional[str] = None
    exclude_patterns: Optional[list[str]] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None


class UpdateFindingRequest(BaseModel):
    status: str = Field(..., pattern="^(open|acknowledged|resolved|suppressed)$")
    acknowledged_by: Optional[str] = None


@router.get("/findings")
def list_findings(
    status: Optional[str] = Query(None),
    risk_type: Optional[str] = Query(None),
    service: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    misconfig_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    items = _filtered_findings(status, risk_type, service, tier, misconfig_id)
    items.sort(key=lambda item: (int(item.get("risk_value") or 0), str(item.get("detected_at") or "")), reverse=True)
    total = len(items)
    start = (page - 1) * page_size
    return {"items": items[start:start + page_size], "total": total, "page": page, "page_size": page_size}


@router.get("/finding-groups")
def finding_groups(
    status: Optional[str] = Query(None),
    risk_type: Optional[str] = Query(None),
    service: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    misconfig_id: Optional[str] = Query(None),
    limit: int = Query(25, ge=1, le=100),
):
    groups: dict[str, dict[str, Any]] = {}
    for item in _filtered_findings(status, risk_type, service, tier, misconfig_id):
        catalog_id = str(item.get("misconfig_id") or "unknown")
        group = groups.setdefault(
            catalog_id,
            {
                "misconfig_id": catalog_id,
                "scenario": item.get("scenario") or "Untitled control",
                "recommendation": item.get("recommendation") or "",
                "service_name": item.get("service_name") or "unknown",
                "risk_type": item.get("risk_type") or "unknown",
                "risk_value": int(item.get("risk_value") or 0),
                "total_findings": 0,
                "confirmed_count": 0,
                "advisory_count": 0,
                "account_count": 0,
                "region_count": 0,
                "resource_type_count": 0,
                "accounts": set(),
                "regions": set(),
                "resource_types": set(),
                "latest_detected_at": item.get("detected_at"),
                "sample_finding_id": item.get("id"),
            },
        )
        group["total_findings"] += 1
        tier_value = item.get("evaluation_tier") or "advisory"
        if tier_value == "confirmed":
            group["confirmed_count"] += 1
        else:
            group["advisory_count"] += 1
        account_id, region = _account_region_from_finding(item)
        if account_id:
            group["accounts"].add(account_id)
        if region:
            group["regions"].add(region)
        if item.get("resource_type"):
            group["resource_types"].add(str(item.get("resource_type")))
        if str(item.get("detected_at") or "") > str(group.get("latest_detected_at") or ""):
            group["latest_detected_at"] = item.get("detected_at")
            group["sample_finding_id"] = item.get("id")

    items = []
    for group in groups.values():
        accounts = sorted(group.pop("accounts"))
        regions = sorted(group.pop("regions"))
        resource_types = sorted(group.pop("resource_types"))
        group["account_count"] = len(accounts)
        group["region_count"] = len(regions)
        group["resource_type_count"] = len(resource_types)
        group["accounts"] = accounts[:5]
        group["regions"] = regions[:5]
        group["resource_types"] = resource_types[:5]
        items.append(group)

    items.sort(
        key=lambda item: (
            -int(item.get("risk_value") or 0),
            -int(item.get("total_findings") or 0),
            str(item.get("scenario") or "").lower(),
        )
    )
    return {"items": items[:limit], "total": len(items), "limit": limit}


@router.get("/summary")
def findings_summary():
    items = [item for item in _list_findings() if item.get("status") == "open"]
    by_risk = _count_by(items, "risk_type")
    by_tier = _count_by(items, "evaluation_tier")
    return {
        "total_open": len(items),
        "by_risk": [{"risk_type": key, "count": count} for key, count in by_risk.items()],
        "by_tier": [{"tier": key, "count": count} for key, count in by_tier.items()],
    }


@router.get("/dashboard")
def dashboard():
    findings = _list_findings()
    open_findings = [item for item in findings if item.get("status") == "open"]
    by_severity = _count_by(open_findings, "risk_value")
    by_service = _count_by(open_findings, "service_name")
    by_tier = _count_by(open_findings, "evaluation_tier")
    return {
        "total_open": len(open_findings),
        "total_acknowledged": sum(1 for item in findings if item.get("status") == "acknowledged"),
        "total_resolved": sum(1 for item in findings if item.get("status") == "resolved"),
        "total_suppressed": sum(1 for item in findings if item.get("status") == "suppressed"),
        "by_severity": [
            {"risk_value": key, "count": count}
            for key, count in sorted(by_severity.items(), key=lambda pair: int(pair[0] or 0), reverse=True)
        ],
        "by_service": [
            {"service": key, "count": count}
            for key, count in sorted(by_service.items(), key=lambda pair: pair[1], reverse=True)
        ],
        "by_tier": [{"tier": key, "count": count} for key, count in by_tier.items()],
    }


@router.get("/policies")
def list_policies():
    policies = _list_policies()
    policies.sort(key=lambda item: int(item.get("priority") or 100))
    return [_policy_response(policy) for policy in policies]


@router.get("/catalog")
def catalog(
    service: Optional[str] = Query(None),
    risk_type: Optional[str] = Query(None),
    resource_types: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    _ensure_catalog_loaded()
    registry = MisconfigRegistry()
    resource_type_list = [item.strip() for item in resource_types.split(",") if item.strip()] if resource_types else None

    if search:
        items = registry.search(search)
    elif resource_type_list or service or risk_type:
        items = registry.filter(service=service, risk_type=risk_type, resource_types=resource_type_list)
    else:
        items = registry.all()

    items = items[:limit]
    support_map = build_support_map(items)
    return {
        "items": [_catalog_response(entry, support_map.get(entry.get("id"), {})) for entry in items],
        "total": len(items),
        "services": registry.services,
        "risk_types": registry.risk_types,
        "support_summary": summarize_support_map(support_map),
    }


@router.post("/policies")
def create_policy(body: CreatePolicyRequest):
    _ensure_catalog_loaded()
    policies = _list_policies()
    if any(policy.get("name") == body.name for policy in policies):
        raise HTTPException(status_code=409, detail=f"Policy '{body.name}' already exists")
    _validate_executable_misconfig_ids(body.misconfig_ids)

    now = _now()
    policy = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "description": body.description,
        "resource_types": body.resource_types or [],
        "risk_types": body.risk_types or [],
        "min_risk_value": body.min_risk_value,
        "misconfig_ids": body.misconfig_ids or [],
        "exclude_patterns": body.exclude_patterns or [],
        "enabled": body.enabled,
        "priority": 100,
        "resources_flagged": 0,
        "last_scanned_at": None,
        "created_at": now,
        "updated_at": now,
    }
    _save_policy(policy)
    return _policy_response(policy)


@router.patch("/policies/{policy_id}")
def update_policy(policy_id: str, body: UpdatePolicyRequest):
    policy = _get_policy(policy_id)
    update_data = body.model_dump(exclude_unset=True)
    if "name" in update_data:
        duplicate = next((item for item in _list_policies() if item.get("name") == update_data["name"] and item.get("id") != policy_id), None)
        if duplicate:
            raise HTTPException(status_code=409, detail=f"Policy '{update_data['name']}' already exists")
    if "misconfig_ids" in update_data:
        _ensure_catalog_loaded()
        _validate_executable_misconfig_ids(update_data["misconfig_ids"])
    policy.update(update_data)
    policy["updated_at"] = _now()
    _save_policy(policy)
    return _policy_response(policy)


@router.delete("/policies/{policy_id}")
def delete_policy(policy_id: str):
    policy = _get_policy(policy_id)
    client = CoreClient()
    for finding in _list_findings():
        if finding.get("policy_id") == policy_id:
            client.delete_storage(STORAGE_NAMESPACE, FINDINGS_COLLECTION, finding["id"])
    client.delete_storage(STORAGE_NAMESPACE, POLICIES_COLLECTION, policy_id)
    return {"message": f"Policy '{policy['name']}' and its findings deleted"}


@router.post("/preview")
def preview_findings(body: dict):
    _ensure_catalog_loaded()
    resource_types = body.get("resource_types", [])
    misconfig_ids = body.get("misconfig_ids", [])
    if not resource_types or not misconfig_ids:
        return {"resources": [], "total": 0}

    registry = MisconfigRegistry()
    scanner = MisconfigScanner(registry)
    resources = _list_resources()
    policy = PolicyRecord(
        id="preview",
        name="preview",
        resource_types=resource_types,
        misconfig_ids=misconfig_ids,
        min_risk_value=body.get("min_risk_value", 0),
        enabled=True,
    )
    findings = scanner.evaluate_policy(policy, resources)
    grouped = _group_preview_findings(findings)
    return {"resources": grouped[:100], "total": len(grouped)}


@router.post("/scan")
def trigger_scan():
    _ensure_catalog_loaded()
    policies = [PolicyRecord(**_policy_record_payload(policy)) for policy in _list_policies() if policy.get("enabled", True)]
    result = _run_scan_for_policies(policies)
    return {
        "job_id": str(uuid.uuid4()),
        "status": "completed",
        "message": f"Misconfig scan complete: {result['findings_created']} findings",
        "result": result,
    }


@router.post("/policies/{policy_id}/scan")
def scan_single_policy(policy_id: str):
    _ensure_catalog_loaded()
    policy = _get_policy(policy_id)
    result = _run_scan_for_policies([PolicyRecord(**_policy_record_payload(policy))])
    return {
        "job_id": str(uuid.uuid4()),
        "status": "completed",
        "message": f"Scan for policy '{policy['name']}' complete",
        "result": result,
    }


@router.patch("/findings/{finding_id}")
def update_finding(finding_id: str, body: UpdateFindingRequest):
    finding = _get_finding(finding_id)
    finding["status"] = body.status
    if body.status == "acknowledged":
        finding["acknowledged_at"] = _now()
        finding["acknowledged_by"] = body.acknowledged_by
    elif body.status == "resolved":
        finding["resolved_at"] = _now()
    _save_finding(finding)
    return finding


def _ensure_catalog_loaded() -> None:
    client = CoreClient(timeout=60)
    try:
        if int(client.catalog_summary().get("total") or 0) > 0:
            return
    except Exception:
        raise

    source_path = resolve_catalog_source_path(os.environ.get("GOVERNANCE_MISCONFIG_DB_PATH"))
    if not source_path or not source_path.exists():
        return
    client.import_catalog(str(source_path), executable_mapping=_local_executable_mapping())


def _local_executable_mapping() -> dict[str, dict[str, Any]]:
    mapping = {}
    for catalog_id, evaluator in EVALUATOR_REGISTRY.items():
        resource_types = list(getattr(evaluator, "applicable_resource_types", []) or [])
        mapping[catalog_id] = {
            "executable": True,
            "evaluator_key": catalog_id,
            "resource_types": resource_types,
            "resource_requirements": {
                "resource_types": resource_types,
                "description": getattr(evaluator, "description", None),
            },
        }
    return mapping


def _validate_executable_misconfig_ids(misconfig_ids: Optional[list[str]]) -> None:
    if not misconfig_ids:
        return
    registry = MisconfigRegistry()
    invalid = find_unexecutable_ids(registry, misconfig_ids)
    if invalid["unknown"] or invalid["unsupported"]:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Only executable misconfiguration rules can be added to policies.",
                "unknown_misconfig_ids": invalid["unknown"],
                "unsupported_misconfig_ids": invalid["unsupported"],
            },
        )


def _list_policies() -> list[dict[str, Any]]:
    return [record.get("payload") or {} for record in _list_all_storage(POLICIES_COLLECTION)]


def _list_findings() -> list[dict[str, Any]]:
    return [record.get("payload") or {} for record in _list_all_storage(FINDINGS_COLLECTION)]


def _filtered_findings(
    status: Optional[str],
    risk_type: Optional[str],
    service: Optional[str],
    tier: Optional[str],
    misconfig_id: Optional[str],
) -> list[dict[str, Any]]:
    items = _list_findings()
    if status:
        items = [item for item in items if item.get("status") == status]
    if risk_type:
        items = [item for item in items if item.get("risk_type") == risk_type]
    if service:
        items = [item for item in items if item.get("service_name") == service]
    if tier:
        items = [item for item in items if item.get("evaluation_tier") == tier]
    if misconfig_id:
        items = [item for item in items if item.get("misconfig_id") == misconfig_id]
    return items


def _account_region_from_finding(finding: dict[str, Any]) -> tuple[str, str]:
    account_id = str(finding.get("account_id") or "")
    region = str(finding.get("region") or "")
    arn = str(finding.get("resource_arn") or "")
    if arn.startswith("arn:"):
        parts = arn.split(":", 5)
        if len(parts) >= 5:
            region = region or parts[3]
            account_id = account_id or parts[4]
    return account_id, region


def _list_all_storage(collection: str) -> list[dict[str, Any]]:
    client = CoreClient()
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


def _get_policy(policy_id: str) -> dict[str, Any]:
    policy = next((item for item in _list_policies() if item.get("id") == policy_id), None)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


def _get_finding(finding_id: str) -> dict[str, Any]:
    finding = next((item for item in _list_findings() if item.get("id") == finding_id), None)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    return finding


def _save_policy(policy: dict[str, Any]) -> None:
    CoreClient().upsert_storage(STORAGE_NAMESPACE, POLICIES_COLLECTION, policy["id"], policy)


def _save_finding(finding: dict[str, Any]) -> None:
    CoreClient().upsert_storage(STORAGE_NAMESPACE, FINDINGS_COLLECTION, finding["id"], finding)


def _list_resources() -> list[ResourceRecord]:
    client = CoreClient(timeout=60)
    rows = []
    offset = 0
    limit = 1000
    while True:
        page = client.list_resources(limit=limit, offset=offset)
        items = page.get("items") or []
        rows.extend(items)
        if offset + len(items) >= int(page.get("total") or 0) or len(items) < limit:
            break
        offset += limit
    return [_resource_from_core(row) for row in rows]


def _resource_from_core(row: dict[str, Any]) -> ResourceRecord:
    return ResourceRecord(
        id=str(row.get("id") or row.get("resource_arn")),
        resource_arn=str(row.get("resource_arn") or ""),
        resource_type=str(row.get("resource_type") or ""),
        service_name=str(row.get("service_name") or ""),
        metadata_json=row.get("metadata_json") or row.get("metadata") or row.get("attributes") or {},
        current_tags=row.get("current_tags") or row.get("tags") or {},
    )


def _run_scan_for_policies(policies: list[PolicyRecord]) -> dict[str, int]:
    registry = MisconfigRegistry()
    scanner = MisconfigScanner(registry)
    resources = _list_resources()
    all_findings = scanner.evaluate_all_policies(policies, resources)
    client = CoreClient()
    existing_findings = _list_findings()
    total_created = 0
    for policy in policies:
        for finding in existing_findings:
            if finding.get("policy_id") == policy.id and finding.get("status") == "open":
                client.delete_storage(STORAGE_NAMESPACE, FINDINGS_COLLECTION, finding["id"])
        findings = all_findings.get(policy.id, [])
        for finding in findings:
            _save_finding(finding)
        total_created += len(findings)
        policy_payload = _get_policy(policy.id)
        policy_payload["resources_flagged"] = len(findings)
        policy_payload["last_scanned_at"] = _now()
        policy_payload["updated_at"] = _now()
        _save_policy(policy_payload)
    return {"policies_evaluated": len(policies), "findings_created": total_created}


def _policy_record_payload(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": policy["id"],
        "name": policy.get("name") or "Untitled policy",
        "resource_types": policy.get("resource_types") or [],
        "misconfig_ids": policy.get("misconfig_ids") or [],
        "min_risk_value": int(policy.get("min_risk_value") or 0),
        "exclude_patterns": policy.get("exclude_patterns") or [],
        "enabled": bool(policy.get("enabled", True)),
    }


def _policy_response(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": policy.get("id"),
        "name": policy.get("name"),
        "description": policy.get("description"),
        "enabled": policy.get("enabled", True),
        "risk_types": policy.get("risk_types") or [],
        "min_risk_value": policy.get("min_risk_value") or 0,
        "misconfig_ids": policy.get("misconfig_ids") or [],
        "resource_types": policy.get("resource_types") or [],
        "resources_flagged": policy.get("resources_flagged") or 0,
        "last_scanned_at": policy.get("last_scanned_at"),
        "created_at": policy.get("created_at"),
    }


def _catalog_response(entry: dict[str, Any], support: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entry.get("id"),
        "service_name": entry.get("service_name"),
        "scenario": entry.get("scenario"),
        "risk_detail": entry.get("risk_detail"),
        "risk_value": entry.get("risk_value"),
        "recommendation_action": entry.get("recommendation_action"),
        "recommendation_description_detailed": entry.get("recommendation_description_detailed"),
        "evaluation_criteria": entry.get("evaluation_criteria"),
        **support,
    }


def _group_preview_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resource_map: dict[str, dict[str, Any]] = {}
    for finding in findings:
        arn = finding.get("resource_arn") or "unknown"
        if arn not in resource_map:
            resource_map[arn] = {
                "resource_arn": arn,
                "resource_type": finding.get("resource_type"),
                "service_name": finding.get("service_name"),
                "findings_count": 0,
                "confirmed": 0,
                "advisory": 0,
                "scenarios": [],
            }
        item = resource_map[arn]
        item["findings_count"] += 1
        if finding.get("evaluation_tier") == "confirmed":
            item["confirmed"] += 1
        else:
            item["advisory"] += 1
        if len(item["scenarios"]) < 3:
            item["scenarios"].append(finding.get("scenario") or "")
    return list(resource_map.values())


def _count_by(items: list[dict[str, Any]], field: str) -> dict[Any, int]:
    counts: dict[Any, int] = {}
    for item in items:
        key = item.get(field) or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
