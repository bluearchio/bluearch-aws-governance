"""Networking and VPC evaluators for misconfiguration detection."""

from .base import Condition, Evaluator, Operator


def _metadata_flag(metadata, field, expected):
    actual = metadata.get(field)
    if actual == expected:
        return (True, f"{field}={actual}")
    return (False, "")


def _public_management_ports(metadata, tags, resource):
    ports = metadata.get("public_management_ports") or []
    if ports:
        return (True, f"public_management_ports={','.join(ports)}")
    return (False, "")


def _insufficient_nat_gateway_az_coverage(metadata, tags, resource):
    instance_az_count = metadata.get("running_instance_az_count")
    nat_gateway_az_count = metadata.get("nat_gateway_az_count")
    if not instance_az_count or nat_gateway_az_count is None:
        return (False, "")
    if instance_az_count > nat_gateway_az_count:
        return (
            True,
            f"running_instance_az_count={instance_az_count}; nat_gateway_az_count={nat_gateway_az_count}",
        )
    return (False, "")


# --- Evaluator definitions ---

PUBLIC_INGRESS = Evaluator(
    conditions=[
        Condition(field="public_ingress", operator=Operator.IS_TRUE),
    ],
    applicable_resource_types=["ec2_security_group"],
    description="Security group allows inbound traffic from the public internet",
)

PUBLIC_SSH = Evaluator(
    conditions=[
        Condition(field="public_ssh", operator=Operator.IS_TRUE),
    ],
    applicable_resource_types=["ec2_security_group"],
    description="Security group allows SSH from the public internet",
)

PUBLIC_RDP = Evaluator(
    conditions=[
        Condition(field="public_rdp", operator=Operator.IS_TRUE),
    ],
    applicable_resource_types=["ec2_security_group"],
    description="Security group allows RDP from the public internet",
)

PUBLIC_MANAGEMENT_PORTS = Evaluator(
    func=_public_management_ports,
    applicable_resource_types=["ec2_security_group"],
    description="Security group exposes management ports to the public internet",
)

DEFAULT_SECURITY_GROUP_HAS_RULES = Evaluator(
    conditions=[
        Condition(field="default_sg_has_rules", operator=Operator.IS_TRUE),
    ],
    applicable_resource_types=["ec2_security_group"],
    description="Default security group has inbound or outbound rules",
)

SECURITY_GROUP_WITHOUT_VPC = Evaluator(
    conditions=[
        Condition(field="vpc_id", operator=Operator.IS_NULL),
    ],
    applicable_resource_types=["ec2_security_group"],
    description="Security group is not associated with a VPC",
)

VPC_FLOW_LOGS_DISABLED = Evaluator(
    func=lambda metadata, tags, resource: _metadata_flag(metadata, "flow_logs_enabled", False),
    applicable_resource_types=["ec2_vpc"],
    description="VPC flow logs are disabled",
)

MULTIPLE_SSH_SECURITY_GROUPS = Evaluator(
    conditions=[
        Condition(field="ssh_security_group_count", operator=Operator.GT, value=1),
    ],
    applicable_resource_types=["ec2_instance"],
    description="EC2 instance is attached to multiple security groups that allow SSH",
)

EC2_INSTANCE_WITHOUT_VPC = Evaluator(
    conditions=[
        Condition(field="vpc_id", operator=Operator.IS_NULL),
    ],
    applicable_resource_types=["ec2_instance"],
    description="EC2 instance is not configured under a VPC",
)

NAT_INSTANCE_USED = Evaluator(
    conditions=[
        Condition(field="source_dest_check", operator=Operator.IS_FALSE),
    ],
    applicable_resource_types=["ec2_instance"],
    description="EC2 instance has source/destination checks disabled, which is typical for NAT instances",
)

INSUFFICIENT_NAT_GATEWAY_AZ_COVERAGE = Evaluator(
    func=_insufficient_nat_gateway_az_coverage,
    applicable_resource_types=["ec2_vpc"],
    description="Running instances span more Availability Zones than active NAT gateways",
)


# Registry entries: misconfig_id -> Evaluator
NETWORKING_EVALUATORS = {
    # Security groups allow ingress from 0.0.0.0/0 or ::/0
    "d38ff956-167f-4916-8335-1b224bf8a75b": PUBLIC_INGRESS,
    # RDP and SSH exposed publicly
    "64036652-ec42-41db-a7d6-32819a169fe5": PUBLIC_RDP,
    "bfea29bc-2ef9-4c6e-9ce3-d0c5823e3447": PUBLIC_SSH,
    # Security groups should be VPC-scoped
    "66837592-9e61-4dca-8784-f46209ed7d41": SECURITY_GROUP_WITHOUT_VPC,
    # Default security group should restrict all traffic
    "7e35eb21-1180-43d0-8d7d-5bb01fff7874": DEFAULT_SECURITY_GROUP_HAS_RULES,
    # VPC flow logs disabled
    "955b348e-b934-4d1a-bc1b-966994f99322": VPC_FLOW_LOGS_DISABLED,
    "15ed0da6-a382-4fe0-969b-e0c4f66425bd": VPC_FLOW_LOGS_DISABLED,
    # Network edge management interfaces exposed
    "e7615b72-a401-4432-bb8f-df41c69497f7": PUBLIC_MANAGEMENT_PORTS,
    # Multiple SSH security groups attached to one instance
    "721c9e93-f089-4269-b9ad-cf9ba3bb3ebe": MULTIPLE_SSH_SECURITY_GROUPS,
    # Instances should run inside a VPC
    "5d501b94-d91b-4ea0-8dff-f722393a3ad6": EC2_INSTANCE_WITHOUT_VPC,
    # NAT instances should be replaced by managed NAT Gateway or private endpoints
    "a6c18252-225d-4e21-b7ca-5c591200715c": NAT_INSTANCE_USED,
    # NAT gateway coverage should match running instance AZ spread
    "04dbd22f-e862-4f8b-8a00-7ad7ac48836e": INSUFFICIENT_NAT_GATEWAY_AZ_COVERAGE,
}
