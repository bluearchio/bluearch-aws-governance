"""Governance Hub misconfiguration catalog registry.

The catalog rows live in bluearch-core. This registry adapts the core catalog
response to the same in-memory lookup shape used by the legacy BlueArch
misconfig scanner so the evaluator modules can be moved without carrying the
bundled JSON catalog into this repo.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from ...core_client import CoreClient

logger = logging.getLogger(__name__)


SERVICE_TO_RESOURCE_TYPES = {
    "ec2": [
        "ec2_instance",
        "ec2_volume",
        "ec2_snapshot",
        "ec2_ami",
        "ec2_eip",
        "ec2_reserved_instance",
        "ec2_vpc",
        "ec2_security_group",
    ],
    "account": ["account"],
    "ebs": ["ec2_volume", "ec2_snapshot", "ec2_instance"],
    "s3": ["s3_bucket"],
    "lambda": ["lambda_function", "lambda_layer"],
    "rds": ["rds_instance", "rds_cluster", "rds_snapshot"],
    "redshift": ["redshift_cluster"],
    "route-53": ["route53_record_set"],
    "kinesis": ["kinesis_stream"],
    "dynamodb": ["dynamodb_table"],
    "ecs": ["ecs_cluster", "ecs_service", "ecs_task_definition"],
    "eks": ["eks_cluster"],
    "efs": ["efs_file_system"],
    "guardduty": ["guardduty_region"],
    "organizations": ["organization"],
    "aws-config": ["config_recorder"],
    "config": ["config_recorder"],
    "inspector": ["inspector_finding"],
    "elasticache": ["elasticache_cluster"],
    "elastic beanstalk": ["elastic_beanstalk_environment"],
    "emr": ["emr_cluster"],
    "alb/elb": ["elb_load_balancer"],
    "iam": ["iam_account", "iam_role", "iam_user", "iam_policy", "iam_access_key"],
    "sns": ["sns_topic"],
    "sqs": ["sqs_queue"],
    "cloudwatch": ["cloudwatch_alarm", "cloudwatch_log_group"],
    "cloudtrail": ["cloudtrail_region", "cloudtrail_trail"],
    "acm": ["acm_certificate"],
    "cloudfront": ["cloudfront_distribution"],
    "security-hub": ["securityhub_region"],
    "waf": ["cloudfront_distribution", "elb_load_balancer"],
    "networking": ["ec2_instance", "ec2_vpc", "ec2_security_group"],
    "vpc": ["ec2_vpc", "ec2_security_group"],
    "nat-gateway": ["nat_gateway", "vpc_endpoint", "ec2_vpc"],
    "network-firewall": ["network_firewall"],
    "all": ["resource_explorer_index"],
}

RESOURCE_TYPE_TO_SERVICES = {}
for _svc, _types in SERVICE_TO_RESOURCE_TYPES.items():
    for _rt in _types:
        RESOURCE_TYPE_TO_SERVICES.setdefault(_rt, []).append(_svc)


def _parse_risk_detail(risk_detail: str) -> List[str]:
    if not risk_detail:
        return []
    return [risk.strip().lower() for risk in risk_detail.split(",") if risk.strip()]


class MisconfigRegistry:
    """In-memory index of catalog rows fetched from bluearch-core."""

    def __init__(self, client: CoreClient | None = None):
        self.client = client or CoreClient(timeout=30)
        self._by_id: Dict[str, dict] = {}
        self._by_service: Dict[str, List[dict]] = {}
        self._by_risk: Dict[str, List[dict]] = {}
        self._all: List[dict] = []
        self._load()

    def _load(self) -> None:
        loaded = 0
        offset = 0
        limit = 1000
        while True:
            response = self.client.catalog(limit=limit, offset=offset)
            entries = response.get("entries") or []
            for row in entries:
                entry = _entry_from_core(row)
                entry_id = entry.get("id")
                if not entry_id or entry_id in self._by_id:
                    continue
                entry["_risk_types"] = _parse_risk_detail(entry.get("risk_detail", ""))
                self._by_id[entry_id] = entry
                self._all.append(entry)
                service = (entry.get("service_name") or "").lower()
                self._by_service.setdefault(service, []).append(entry)
                for risk in entry["_risk_types"]:
                    self._by_risk.setdefault(risk, []).append(entry)
                loaded += 1
            if offset + len(entries) >= int(response.get("total") or 0) or len(entries) < limit:
                break
            offset += limit
        logger.info("MisconfigRegistry loaded %d catalog rows from bluearch-core", loaded)

    @property
    def count(self) -> int:
        return len(self._all)

    @property
    def services(self) -> List[str]:
        return sorted(self._by_service.keys())

    @property
    def risk_types(self) -> List[str]:
        return sorted(self._by_risk.keys())

    def get(self, misconfig_id: str) -> Optional[dict]:
        return self._by_id.get(misconfig_id)

    def all(self) -> List[dict]:
        return list(self._all)

    def by_service(self, service: str) -> List[dict]:
        return list(self._by_service.get(service.lower(), []))

    def by_risk(self, risk_type: str) -> List[dict]:
        return list(self._by_risk.get(risk_type.lower(), []))

    def for_resource_types(self, resource_types: List[str]) -> List[dict]:
        target_services = set()
        for resource_type in resource_types:
            for service in RESOURCE_TYPE_TO_SERVICES.get(resource_type, []):
                target_services.add(service)

        results = []
        seen_ids = set()
        for service in target_services:
            for entry in self._by_service.get(service, []):
                if entry["id"] not in seen_ids:
                    seen_ids.add(entry["id"])
                    results.append(entry)
        return results

    def search(self, query: str) -> List[dict]:
        query_lower = query.lower()
        results = []
        for entry in self._all:
            if (
                query_lower in entry.get("scenario", "").lower()
                or query_lower in entry.get("recommendation_action", "").lower()
                or query_lower in entry.get("recommendation_description_detailed", "").lower()
                or query_lower in entry.get("service_name", "").lower()
            ):
                results.append(entry)
        return results

    def filter(
        self,
        service: Optional[str] = None,
        risk_type: Optional[str] = None,
        min_risk_value: int = 0,
        resource_types: Optional[List[str]] = None,
    ) -> List[dict]:
        if resource_types:
            candidates = self.for_resource_types(resource_types)
        elif service:
            candidates = self._by_service.get(service.lower(), [])
        else:
            candidates = self._all

        results = []
        for entry in candidates:
            if (entry.get("risk_value") or 0) < min_risk_value:
                continue
            if risk_type and risk_type.lower() not in entry.get("_risk_types", []):
                continue
            results.append(entry)
        return results


def _entry_from_core(row: dict) -> dict:
    payload = dict(row.get("payload") or {})
    catalog_id = row.get("catalog_id") or payload.get("id")
    payload.setdefault("id", catalog_id)
    payload.setdefault("service_name", row.get("service"))
    payload.setdefault("scenario", row.get("title"))
    payload.setdefault("risk_detail", row.get("category"))
    if row.get("severity") not in (None, ""):
        try:
            payload.setdefault("risk_value", int(row.get("severity")))
        except (TypeError, ValueError):
            payload.setdefault("risk_value", 0)
    return payload
