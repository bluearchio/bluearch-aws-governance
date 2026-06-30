"""Central registry mapping misconfig IDs to their evaluators."""

from typing import Dict, Optional

from .base import Evaluator
from .account_evaluators import ACCOUNT_EVALUATORS
from .ec2_evaluators import EC2_EVALUATORS
from .ecs_evaluators import ECS_EVALUATORS
from .efs_evaluators import EFS_EVALUATORS
from .eks_evaluators import EKS_EVALUATORS
from .guardduty_evaluators import GUARDDUTY_EVALUATORS
from .inspector_evaluators import INSPECTOR_EVALUATORS
from .kinesis_evaluators import KINESIS_EVALUATORS
from .elb_evaluators import ELB_EVALUATORS
from .elasticache_evaluators import ELASTICACHE_EVALUATORS
from .elastic_beanstalk_evaluators import ELASTIC_BEANSTALK_EVALUATORS
from .emr_evaluators import EMR_EVALUATORS
from .rds_evaluators import RDS_EVALUATORS
from .redshift_evaluators import REDSHIFT_EVALUATORS
from .dynamodb_evaluators import DYNAMODB_EVALUATORS
from .cloudwatch_evaluators import CLOUDWATCH_EVALUATORS
from .config_evaluators import CONFIG_EVALUATORS
from .cloudtrail_evaluators import CLOUDTRAIL_EVALUATORS
from .acm_evaluators import ACM_EVALUATORS
from .route53_evaluators import ROUTE53_EVALUATORS
from .cloudfront_evaluators import CLOUDFRONT_EVALUATORS
from .securityhub_evaluators import SECURITYHUB_EVALUATORS
from .waf_evaluators import WAF_EVALUATORS
from .lambda_evaluators import LAMBDA_EVALUATORS
from .iam_evaluators import IAM_EVALUATORS
from .networking_evaluators import NETWORKING_EVALUATORS
from .nat_gateway_evaluators import NAT_GATEWAY_EVALUATORS
from .network_firewall_evaluators import NETWORK_FIREWALL_EVALUATORS
from .resource_explorer_evaluators import RESOURCE_EXPLORER_EVALUATORS
from .sns_evaluators import SNS_EVALUATORS
from .sqs_evaluators import SQS_EVALUATORS
from .s3_evaluators import S3_EVALUATORS

# Combined registry: misconfig_id -> Evaluator
EVALUATOR_REGISTRY: Dict[str, Evaluator] = {}
EVALUATOR_REGISTRY.update(ACCOUNT_EVALUATORS)
EVALUATOR_REGISTRY.update(EC2_EVALUATORS)
EVALUATOR_REGISTRY.update(ECS_EVALUATORS)
EVALUATOR_REGISTRY.update(EFS_EVALUATORS)
EVALUATOR_REGISTRY.update(EKS_EVALUATORS)
EVALUATOR_REGISTRY.update(GUARDDUTY_EVALUATORS)
EVALUATOR_REGISTRY.update(INSPECTOR_EVALUATORS)
EVALUATOR_REGISTRY.update(KINESIS_EVALUATORS)
EVALUATOR_REGISTRY.update(ELB_EVALUATORS)
EVALUATOR_REGISTRY.update(ELASTICACHE_EVALUATORS)
EVALUATOR_REGISTRY.update(ELASTIC_BEANSTALK_EVALUATORS)
EVALUATOR_REGISTRY.update(EMR_EVALUATORS)
EVALUATOR_REGISTRY.update(RDS_EVALUATORS)
EVALUATOR_REGISTRY.update(REDSHIFT_EVALUATORS)
EVALUATOR_REGISTRY.update(DYNAMODB_EVALUATORS)
EVALUATOR_REGISTRY.update(CLOUDWATCH_EVALUATORS)
EVALUATOR_REGISTRY.update(CONFIG_EVALUATORS)
EVALUATOR_REGISTRY.update(CLOUDTRAIL_EVALUATORS)
EVALUATOR_REGISTRY.update(ACM_EVALUATORS)
EVALUATOR_REGISTRY.update(ROUTE53_EVALUATORS)
EVALUATOR_REGISTRY.update(CLOUDFRONT_EVALUATORS)
EVALUATOR_REGISTRY.update(SECURITYHUB_EVALUATORS)
EVALUATOR_REGISTRY.update(WAF_EVALUATORS)
EVALUATOR_REGISTRY.update(LAMBDA_EVALUATORS)
EVALUATOR_REGISTRY.update(IAM_EVALUATORS)
EVALUATOR_REGISTRY.update(NETWORKING_EVALUATORS)
EVALUATOR_REGISTRY.update(NAT_GATEWAY_EVALUATORS)
EVALUATOR_REGISTRY.update(NETWORK_FIREWALL_EVALUATORS)
EVALUATOR_REGISTRY.update(RESOURCE_EXPLORER_EVALUATORS)
EVALUATOR_REGISTRY.update(SNS_EVALUATORS)
EVALUATOR_REGISTRY.update(SQS_EVALUATORS)
EVALUATOR_REGISTRY.update(S3_EVALUATORS)


def has_evaluator(misconfig_id: str) -> bool:
    """Check if an evaluator exists for the given misconfig ID."""
    return misconfig_id in EVALUATOR_REGISTRY


def get_evaluator(misconfig_id: str) -> Optional[Evaluator]:
    """Get the evaluator for the given misconfig ID, or None."""
    return EVALUATOR_REGISTRY.get(misconfig_id)
