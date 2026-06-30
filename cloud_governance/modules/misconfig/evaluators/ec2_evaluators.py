"""EC2 and EBS evaluators for misconfiguration detection."""

from datetime import datetime, timezone

from .base import Condition, Evaluator, Operator


# Previous-generation EC2 instance type families
PREVIOUS_GEN_INSTANCE_FAMILIES = {
    't1', 't2',
    'm1', 'm2', 'm3', 'm4',
    'c1', 'c3', 'c4',
    'r3', 'r4',
    'i2', 'i3',
    'd2',
    'g2',
    'p2',
    'x1',
}

# Previous-generation EBS volume types
PREVIOUS_GEN_VOLUME_TYPES = ['standard', 'io1', 'gp2']


def _is_previous_gen_instance(metadata, tags, resource):
    """Check if EC2 instance uses a previous-generation instance type."""
    instance_type = metadata.get('instance_type', '')
    if not instance_type:
        return (False, "")

    # Extract family: e.g. "t2.micro" -> "t2"
    family = instance_type.split('.')[0] if '.' in instance_type else instance_type
    # Strip size suffix numbers for families like "m5a" -> check "m5" prefix
    base_family = ''.join(c for c in family if not c.isdigit())
    numeric_part = ''.join(c for c in family if c.isdigit())

    # Build the family key: e.g. "t2", "m4", "c3"
    family_key = base_family + numeric_part if numeric_part else family

    if family_key in PREVIOUS_GEN_INSTANCE_FAMILIES:
        return (True, f"instance_type={instance_type}")
    return (False, "")


def _days_until_iso_timestamp(value):
    if not value:
        return None
    try:
        end = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return (end - datetime.now(timezone.utc)).days


def _reserved_instance_expires_within_30_days(metadata, tags, resource):
    days = _days_until_iso_timestamp(metadata.get("end_time"))
    if days is not None and 0 <= days <= 30:
        return (True, f"days_until_expiration={days}")
    return (False, "")


def _ec2_idle_instance(metadata, tags, resource):
    if metadata.get("state") != "running":
        return (False, "")
    observed_days = metadata.get("metric_observed_days_14d") or 0
    idle_days = metadata.get("idle_days_14d")
    if observed_days >= 4 and idle_days is not None and idle_days >= 4:
        return (True, f"idle_days_14d={idle_days}")
    return (False, "")


def _ec2_high_cpu_instance(metadata, tags, resource):
    if metadata.get("state") != "running":
        return (False, "")
    high_cpu_days = metadata.get("high_cpu_days_14d")
    if high_cpu_days is not None and high_cpu_days >= 4:
        return (True, f"high_cpu_days_14d={high_cpu_days}")
    return (False, "")


def _ec2_very_low_cpu_instance(metadata, tags, resource):
    if metadata.get("state") != "running":
        return (False, "")
    observed_days = metadata.get("metric_observed_days_14d") or 0
    cpu_avg = metadata.get("cpu_avg_14d")
    low_days = metadata.get("very_low_cpu_days_14d")
    if observed_days >= 7 and cpu_avg is not None and cpu_avg <= 2:
        return (True, f"cpu_avg_14d={cpu_avg}")
    if observed_days >= 7 and low_days is not None and low_days >= 7:
        return (True, f"very_low_cpu_days_14d={low_days}")
    return (False, "")


def _ec2_classic_security_group_over_100_rules(metadata, tags, resource):
    if metadata.get("vpc_id") is not None:
        return (False, "")
    total_rules = metadata.get("total_rules_count") or 0
    if total_rules > 100:
        return (True, f"vpc_id=None; total_rules_count={total_rules}")
    return (False, "")


def _ec2_classic_instance_over_100_security_group_rules(metadata, tags, resource):
    if metadata.get("vpc_id") is not None:
        return (False, "")
    total_rules = metadata.get("security_group_rule_count") or 0
    if total_rules > 100:
        return (True, f"vpc_id=None; security_group_rule_count={total_rules}")
    return (False, "")


def _vpc_flow_logs_disabled(metadata, tags, resource):
    if metadata.get("flow_logs_enabled") is False:
        return (True, "flow_logs_enabled=False")
    return (False, "")


def _provisioned_iops_volume_on_non_ebs_optimized_instance(metadata, tags, resource):
    if metadata.get("volume_type") not in {"io1", "io2"}:
        return (False, "")
    attachments = metadata.get("attachments") or []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        if attachment.get("instance_ebs_optimized") is False:
            instance_id = attachment.get("instance_id") or "unknown"
            return (True, f"volume_type={metadata.get('volume_type')}; instance_id={instance_id}; ebs_optimized=False")
    return (False, "")


# --- Evaluator definitions ---

# Unencrypted EBS volumes
UNENCRYPTED_VOLUME = Evaluator(
    conditions=[
        Condition(field="encrypted", operator=Operator.IS_FALSE),
    ],
    applicable_resource_types=["ec2_volume"],
    description="EBS volume is not encrypted",
)

# Unattached EBS volumes (state == 'available' means not attached)
UNATTACHED_VOLUME = Evaluator(
    conditions=[
        Condition(field="state", operator=Operator.EQ, value="available"),
    ],
    applicable_resource_types=["ec2_volume"],
    description="EBS volume is not attached to any instance",
)

# Previous-generation EBS volume types (standard, io1, gp2)
PREVIOUS_GEN_VOLUME_TYPE = Evaluator(
    conditions=[
        Condition(field="volume_type", operator=Operator.IN, value=PREVIOUS_GEN_VOLUME_TYPES),
    ],
    applicable_resource_types=["ec2_volume"],
    description="EBS volume uses a previous-generation volume type",
)

# Previous-generation EC2 instances (custom function)
PREVIOUS_GEN_INSTANCE = Evaluator(
    func=_is_previous_gen_instance,
    applicable_resource_types=["ec2_instance"],
    description="EC2 instance uses a previous-generation instance type family",
)

# Publicly shared AMI
PUBLIC_AMI = Evaluator(
    conditions=[
        Condition(field="public", operator=Operator.IS_TRUE),
    ],
    applicable_resource_types=["ec2_ami"],
    description="EC2 AMI is publicly shared",
)

# Unassociated Elastic IP (no association_id means not attached)
UNASSOCIATED_EIP = Evaluator(
    conditions=[
        Condition(field="association_id", operator=Operator.IS_NULL),
    ],
    applicable_resource_types=["ec2_eip"],
    description="Elastic IP is not associated with any instance or network interface",
)

EXPIRING_RESERVED_INSTANCE = Evaluator(
    func=_reserved_instance_expires_within_30_days,
    applicable_resource_types=["ec2_reserved_instance"],
    description="EC2 Reserved Instance lease expires within 30 days",
)

IDLE_INSTANCE = Evaluator(
    func=_ec2_idle_instance,
    applicable_resource_types=["ec2_instance"],
    description="EC2 instance has low CPU and network activity on at least four observed days",
)

HIGH_CPU_INSTANCE = Evaluator(
    func=_ec2_high_cpu_instance,
    applicable_resource_types=["ec2_instance"],
    description="EC2 instance has average CPU above 90% on at least four observed days",
)

VERY_LOW_CPU_INSTANCE = Evaluator(
    func=_ec2_very_low_cpu_instance,
    applicable_resource_types=["ec2_instance"],
    description="EC2 instance has very low CPU utilization across the lookback window",
)

OVERSIZED_SECURITY_GROUP = Evaluator(
    conditions=[
        Condition(field="total_rules_count", operator=Operator.GT, value=50),
    ],
    applicable_resource_types=["ec2_security_group"],
    description="Security group has more than 50 concrete ingress and egress rules",
)

INSTANCE_WITH_OVERSIZED_SECURITY_GROUPS = Evaluator(
    conditions=[
        Condition(field="security_group_rule_count", operator=Operator.GT, value=50),
    ],
    applicable_resource_types=["ec2_instance"],
    description="EC2 instance is attached to security groups with more than 50 total rules",
)

EC2_CLASSIC_OVERSIZED_SECURITY_GROUP = Evaluator(
    func=_ec2_classic_security_group_over_100_rules,
    applicable_resource_types=["ec2_security_group"],
    description="EC2-Classic security group has more than 100 ingress and egress rules",
)

EC2_CLASSIC_INSTANCE_WITH_OVERSIZED_SECURITY_GROUPS = Evaluator(
    func=_ec2_classic_instance_over_100_security_group_rules,
    applicable_resource_types=["ec2_instance"],
    description="EC2-Classic instance is attached to security groups with more than 100 total rules",
)

EC2_VPC_FLOW_LOGS_DISABLED = Evaluator(
    func=_vpc_flow_logs_disabled,
    applicable_resource_types=["ec2_vpc"],
    description="EC2 VPC flow logs are disabled",
)

PIOPS_VOLUME_ON_NON_EBS_OPTIMIZED_INSTANCE = Evaluator(
    func=_provisioned_iops_volume_on_non_ebs_optimized_instance,
    applicable_resource_types=["ec2_volume"],
    description="Provisioned IOPS EBS volume is attached to an EC2 instance that is not EBS-optimized",
)

DELETE_ON_TERMINATION_DISABLED = Evaluator(
    conditions=[
        Condition(field="delete_on_termination_disabled", operator=Operator.IS_TRUE),
    ],
    applicable_resource_types=["ec2_instance"],
    description="EC2 root or attached EBS volume is not deleted when the instance is terminated",
)

UNNECESSARY_SNAPSHOT = Evaluator(
    conditions=[
        Condition(field="is_unnecessary_snapshot", operator=Operator.IS_TRUE),
    ],
    applicable_resource_types=["ec2_snapshot"],
    description="EBS snapshot is older than seven days or superseded by a newer snapshot from the same volume",
)

ORPHANED_SNAPSHOT = Evaluator(
    conditions=[
        Condition(field="is_orphaned_snapshot", operator=Operator.IS_TRUE),
    ],
    applicable_resource_types=["ec2_snapshot"],
    description="EBS snapshot source volume no longer exists in the scanned account and region",
)


# Registry entries: misconfig_id -> Evaluator
EC2_EVALUATORS = {
    # Unencrypted EBS volumes
    "249dd667-4b1e-4200-bec5-19c6c718f958": UNENCRYPTED_VOLUME,
    # Unattached EBS volumes
    "033ae438-4620-4f65-80cd-776fd0102bb0": UNATTACHED_VOLUME,
    # Previous gen EBS volume types
    "0f5cfb3e-623b-4140-a5ed-db4b5be406f8": PREVIOUS_GEN_VOLUME_TYPE,
    # Previous gen EC2 instances
    "030f361e-eb21-4382-8d26-fcd86f47c8d5": PREVIOUS_GEN_INSTANCE,
    # Publicly shared AMI
    "15771cd0-38a1-58f6-9516-76a09f6b88a7": PUBLIC_AMI,
    # Unassociated Elastic IPs
    "40d46878-ac12-44c8-902f-196a18dc9f6c": UNASSOCIATED_EIP,
    # Reserved Instance lease expires within the next 30 days
    "6d6e48e1-29bb-49ac-a848-a33fba2a712a": EXPIRING_RESERVED_INSTANCE,
    "6a2c2d54-b4ce-4d2c-a3c1-4ce04986052c": EXPIRING_RESERVED_INSTANCE,
    # EC2 utilization
    "74492e33-2626-4630-bf53-2bd5ef074061": IDLE_INSTANCE,
    "f15adfc7-d970-4925-b0fb-99dbe1796d3b": HIGH_CPU_INSTANCE,
    "fb608bb0-abfd-4543-876d-b7d44bc64329": VERY_LOW_CPU_INSTANCE,
    "e8fc5179-9193-4d19-808f-dee3aa5a08a1": VERY_LOW_CPU_INSTANCE,
    "c2868099-49ec-4473-8020-47a470a23414": VERY_LOW_CPU_INSTANCE,
    # Large security group rule sets
    "63b4f412-c3ab-4ec8-af7f-ddfecbc25269": OVERSIZED_SECURITY_GROUP,
    "ebe7cf51-ecf8-4eee-a8f4-61d7e7d8fa1c": INSTANCE_WITH_OVERSIZED_SECURITY_GROUPS,
    # EC2-Classic large security group rule sets
    "e5bd9c73-a9fb-4dab-b90c-55d37577bc19": EC2_CLASSIC_OVERSIZED_SECURITY_GROUP,
    "89e0797c-0de8-4d2a-826e-810dd6843d23": EC2_CLASSIC_INSTANCE_WITH_OVERSIZED_SECURITY_GROUPS,
    # EC2 VPC flow logs
    "9f8cd266-20b2-4bb8-867c-7ef54923cc00": EC2_VPC_FLOW_LOGS_DISABLED,
    # EBS PIOPS volume attachment
    "444fd30a-f2f2-4a7f-afbc-063349fc900f": PIOPS_VOLUME_ON_NON_EBS_OPTIMIZED_INSTANCE,
    # EBS attached volume lifecycle
    "9b4bd9b6-9139-4e8d-a157-055bbb6bacc3": DELETE_ON_TERMINATION_DISABLED,
    # Snapshot lifecycle
    "8dfe3ba4-c72f-4ed8-9a07-f88c1ccc8b3b": UNNECESSARY_SNAPSHOT,
    "8312c521-673e-48df-aca3-ae6a284f7079": ORPHANED_SNAPSHOT,
}
