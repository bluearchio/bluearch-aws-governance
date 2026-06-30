"""Misconfiguration scanner for Governance Hub."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .evaluators.registry import get_evaluator
from .registry import MisconfigRegistry, SERVICE_TO_RESOURCE_TYPES

logger = logging.getLogger(__name__)


RESOURCE_TYPE_MAPPING = {
    "AWS::EC2::Instance": "ec2_instance",
    "AWS::EC2::Volume": "ec2_volume",
    "AWS::EC2::Snapshot": "ec2_snapshot",
    "AWS::EC2::Image": "ec2_ami",
    "AWS::EC2::EIP": "ec2_eip",
    "AWS::EC2::ReservedInstances": "ec2_reserved_instance",
    "AWS::EC2::VPC": "ec2_vpc",
    "AWS::EC2::SecurityGroup": "ec2_security_group",
    "AWS::EC2::NatGateway": "nat_gateway",
    "AWS::EC2::VPCEndpoint": "vpc_endpoint",
    "AWS::Account::Account": "account",
    "AWS::Organizations::Organization": "organization",
    "AWS::Config::ConfigurationRecorder": "config_recorder",
    "AWS::Lambda::Function": "lambda_function",
    "AWS::Lambda::LayerVersion": "lambda_layer",
    "AWS::S3::Bucket": "s3_bucket",
    "AWS::RDS::DBInstance": "rds_instance",
    "AWS::RDS::DBCluster": "rds_cluster",
    "AWS::RDS::DBSnapshot": "rds_snapshot",
    "AWS::Redshift::Cluster": "redshift_cluster",
    "AWS::Route53::RecordSet": "route53_record_set",
    "AWS::Kinesis::Stream": "kinesis_stream",
    "AWS::DynamoDB::Table": "dynamodb_table",
    "AWS::ElastiCache::CacheCluster": "elasticache_cluster",
    "AWS::ElasticBeanstalk::Environment": "elastic_beanstalk_environment",
    "AWS::EMR::Cluster": "emr_cluster",
    "AWS::ECS::Cluster": "ecs_cluster",
    "AWS::ECS::Service": "ecs_service",
    "AWS::ECS::TaskDefinition": "ecs_task_definition",
    "AWS::EKS::Cluster": "eks_cluster",
    "AWS::EFS::FileSystem": "efs_file_system",
    "AWS::GuardDuty::Region": "guardduty_region",
    "AWS::InspectorV2::Finding": "inspector_finding",
    "AWS::SNS::Topic": "sns_topic",
    "AWS::SQS::Queue": "sqs_queue",
    "AWS::CloudWatch::Alarm": "cloudwatch_alarm",
    "AWS::Logs::LogGroup": "cloudwatch_log_group",
    "AWS::CloudTrail::Region": "cloudtrail_region",
    "AWS::CloudTrail::Trail": "cloudtrail_trail",
    "AWS::CertificateManager::Certificate": "acm_certificate",
    "AWS::CloudFront::Distribution": "cloudfront_distribution",
    "AWS::SecurityHub::Region": "securityhub_region",
    "AWS::ElasticLoadBalancingV2::LoadBalancer": "elb_load_balancer",
    "AWS::ElasticLoadBalancingV2::LoadBalancer/Application": "elb_load_balancer",
    "AWS::ElasticLoadBalancingV2::LoadBalancer/Network": "elb_load_balancer",
    "AWS::IAM::Account": "iam_account",
    "AWS::IAM::Role": "iam_role",
    "AWS::IAM::User": "iam_user",
    "AWS::IAM::Policy": "iam_policy",
    "AWS::IAM::AccessKey": "iam_access_key",
    "AWS::NetworkFirewall::Firewall": "network_firewall",
    "AWS::ResourceExplorer2::Index": "resource_explorer_index",
}


@dataclass
class ResourceRecord:
    id: str
    resource_arn: str
    resource_type: str
    service_name: str
    metadata_json: dict[str, Any] | None = None
    current_tags: dict[str, Any] | None = None


@dataclass
class PolicyRecord:
    id: str
    name: str
    resource_types: list[str] = field(default_factory=list)
    misconfig_ids: list[str] = field(default_factory=list)
    min_risk_value: int = 0
    exclude_patterns: list[str] = field(default_factory=list)
    enabled: bool = True


def _normalize_resource_type(resource: ResourceRecord) -> str:
    return RESOURCE_TYPE_MAPPING.get(resource.resource_type, resource.resource_type.lower())


class MisconfigScanner:
    """Evaluates selected executable catalog entries against core inventory."""

    def __init__(self, registry: MisconfigRegistry):
        self.registry = registry

    def evaluate_policy(
        self,
        policy: PolicyRecord,
        resources: List[ResourceRecord],
    ) -> List[dict[str, Any]]:
        findings = []
        existing_keys = set()

        for misconfig_id in policy.misconfig_ids or []:
            misconfig = self.registry.get(misconfig_id)
            if not misconfig:
                logger.warning("Misconfig ID %s not found in registry, skipping", misconfig_id)
                continue

            if (misconfig.get("risk_value") or 0) < (policy.min_risk_value or 0):
                continue

            evaluator = get_evaluator(misconfig_id)
            matched = self._match_resources(misconfig, resources, policy, evaluator)

            for resource, tier, details in matched:
                key = (resource.id, misconfig_id)
                if key in existing_keys:
                    continue
                existing_keys.add(key)
                findings.append(self._create_finding(policy, resource, misconfig, tier, details))

        return findings

    def _match_resources(
        self,
        misconfig: dict,
        resources: List[ResourceRecord],
        policy: PolicyRecord,
        evaluator=None,
    ) -> List[Tuple[ResourceRecord, str, Optional[str]]]:
        service_name = (misconfig.get("service_name") or "").lower()
        applicable_types = set(SERVICE_TO_RESOURCE_TYPES.get(service_name, []))

        policy_types = set(policy.resource_types or [])
        if policy_types:
            applicable_types = applicable_types & policy_types

        if evaluator and evaluator.applicable_resource_types:
            applicable_types = applicable_types & set(evaluator.applicable_resource_types)

        if not applicable_types:
            return []

        matched = []
        for resource in resources:
            if _normalize_resource_type(resource) not in applicable_types:
                continue
            if self._is_excluded(resource, policy.exclude_patterns):
                continue
            if evaluator:
                try:
                    failed, details = evaluator.evaluate(resource)
                    if failed:
                        matched.append((resource, "confirmed", details or None))
                except Exception as exc:
                    logger.warning(
                        "Evaluator error for misconfig %s on resource %s: %s",
                        misconfig.get("id", "?"),
                        resource.id,
                        exc,
                    )
                    matched.append((resource, "advisory", f"evaluator error: {exc}"))
        return matched

    def _is_excluded(self, resource: ResourceRecord, exclude_patterns: Optional[list]) -> bool:
        if not exclude_patterns:
            return False

        resource_name = ""
        if isinstance(resource.current_tags, dict):
            resource_name = str(resource.current_tags.get("Name", ""))

        for pattern in exclude_patterns:
            pattern_lower = str(pattern).lower()
            if pattern_lower in resource.resource_arn.lower():
                return True
            if resource_name and pattern_lower in resource_name.lower():
                return True
        return False

    def _create_finding(
        self,
        policy: PolicyRecord,
        resource: ResourceRecord,
        misconfig: dict,
        tier: str,
        details: Optional[str],
    ) -> dict[str, Any]:
        risk_types = misconfig.get("_risk_types", [])
        primary_risk = risk_types[0] if risk_types else misconfig.get("risk_detail", "operations")
        return {
            "id": str(uuid.uuid4()),
            "policy_id": policy.id,
            "resource_id": resource.id,
            "misconfig_id": misconfig["id"],
            "status": "open",
            "risk_type": primary_risk,
            "risk_value": misconfig.get("risk_value", 0) or 0,
            "scenario": misconfig.get("scenario", ""),
            "recommendation": misconfig.get("recommendation_action", ""),
            "resource_arn": resource.resource_arn,
            "resource_type": resource.resource_type,
            "service_name": resource.service_name,
            "evaluation_tier": tier,
            "evaluation_details": details,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }

    def evaluate_all_policies(
        self,
        policies: List[PolicyRecord],
        resources: List[ResourceRecord],
    ) -> Dict[str, List[dict[str, Any]]]:
        results = {}
        for policy in policies:
            if not policy.enabled:
                continue
            findings = self.evaluate_policy(policy, resources)
            results[policy.id] = findings
            logger.info(
                "Policy '%s': %d findings from %d misconfigs",
                policy.name,
                len(findings),
                len(policy.misconfig_ids or []),
            )
        return results
