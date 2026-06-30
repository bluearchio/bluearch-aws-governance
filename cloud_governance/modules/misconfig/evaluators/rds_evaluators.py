"""RDS evaluators for misconfiguration detection."""

from .base import Condition, Evaluator, Operator


# Previous-generation RDS instance class families
PREVIOUS_GEN_RDS_FAMILIES = {
    'db.t2', 'db.t1',
    'db.m1', 'db.m2', 'db.m3', 'db.m4',
    'db.r3', 'db.r4',
    'db.cr1',
}


def _is_previous_gen_rds(metadata, tags, resource):
    """Check if RDS instance uses a previous-generation instance class."""
    instance_class = metadata.get('instance_class', '')
    if not instance_class:
        return (False, "")

    # instance_class is like "db.m5.large" - extract "db.m5"
    parts = instance_class.split('.')
    if len(parts) >= 2:
        family = parts[0] + '.' + parts[1]
    else:
        family = instance_class

    if family in PREVIOUS_GEN_RDS_FAMILIES:
        return (True, f"instance_class={instance_class}")
    return (False, "")


def _idle_rds_instance(metadata, tags, resource):
    age_days = metadata.get("age_days")
    connections_avg = metadata.get("connections_avg")
    if age_days is not None and age_days < 7:
        return (False, "")
    if connections_avg == 0:
        return (True, "connections_avg=0")
    return (False, "")


def _overprovisioned_storage_without_autoscaling(metadata, tags, resource):
    storage_gb = metadata.get("storage_gb")
    free_bytes = metadata.get("free_storage_space_bytes")
    autoscaling = metadata.get("storage_autoscaling_enabled")
    if not storage_gb or free_bytes is None or autoscaling is not False:
        return (False, "")
    allocated_bytes = storage_gb * 1024 * 1024 * 1024
    free_ratio = free_bytes / allocated_bytes if allocated_bytes else 0
    if free_ratio > 0.60:
        return (True, f"free_storage_ratio={free_ratio:.2f}; storage_autoscaling_enabled=false")
    return (False, "")


# --- Evaluator definitions ---

# Unencrypted RDS storage
UNENCRYPTED_RDS = Evaluator(
    conditions=[
        Condition(field="storage_encrypted", operator=Operator.IS_FALSE),
    ],
    applicable_resource_types=["rds_instance"],
    description="RDS instance storage is not encrypted",
)

# No Multi-AZ deployment
NO_MULTI_AZ = Evaluator(
    conditions=[
        Condition(field="multi_az", operator=Operator.IS_FALSE),
    ],
    applicable_resource_types=["rds_instance"],
    description="RDS instance does not have Multi-AZ enabled",
)

# Previous-generation RDS instance class
PREVIOUS_GEN_RDS = Evaluator(
    func=_is_previous_gen_rds,
    applicable_resource_types=["rds_instance"],
    description="RDS instance uses a previous-generation instance class family",
)

# RDS publicly accessible
PUBLICLY_ACCESSIBLE_RDS = Evaluator(
    conditions=[
        Condition(field="publicly_accessible", operator=Operator.IS_TRUE),
    ],
    applicable_resource_types=["rds_instance"],
    description="RDS instance is publicly accessible from the internet",
)

# Idle RDS instance
IDLE_RDS_INSTANCE = Evaluator(
    func=_idle_rds_instance,
    applicable_resource_types=["rds_instance"],
    description="RDS instance has no database connections over the metric lookback",
)

# RDS using GP2 storage instead of GP3
GP2_STORAGE = Evaluator(
    conditions=[
        Condition(field="storage_type", operator=Operator.EQ, value="gp2"),
    ],
    applicable_resource_types=["rds_instance"],
    description="RDS instance uses GP2 storage instead of cost-effective GP3",
)

# No deletion protection
NO_DELETION_PROTECTION_RDS = Evaluator(
    conditions=[
        Condition(field="deletion_protection", operator=Operator.IS_FALSE),
    ],
    applicable_resource_types=["rds_instance"],
    description="RDS instance does not have deletion protection enabled",
)

# No backups configured
NO_BACKUPS_RDS = Evaluator(
    conditions=[
        Condition(field="backup_retention_period", operator=Operator.EQ, value=0),
    ],
    applicable_resource_types=["rds_instance"],
    description="RDS instance has no automated backups configured",
)

OVERPROVISIONED_STORAGE_WITHOUT_AUTOSCALING = Evaluator(
    func=_overprovisioned_storage_without_autoscaling,
    applicable_resource_types=["rds_instance"],
    description="RDS instance has more than 60 percent free allocated storage and storage autoscaling is disabled",
)


# Registry entries: misconfig_id -> Evaluator
RDS_EVALUATORS = {
    # Unencrypted RDS
    "4a77b3fb-647d-4f79-8605-28d7ab946ad2": UNENCRYPTED_RDS,
    # No Multi-AZ
    "67c7713f-5866-4e0e-bd65-2fd445775878": NO_MULTI_AZ,
    # Previous gen RDS instances
    "a1f5645b-0bce-475a-b036-d34b9abd5dbb": PREVIOUS_GEN_RDS,
    # RDS publicly accessible
    "c0764b9f-5241-46c5-af3f-3bcf30721fec": PUBLICLY_ACCESSIBLE_RDS,
    # Idle RDS DB instance
    "3afeb36c-4c09-400f-8f70-13314ff8d578": IDLE_RDS_INSTANCE,
    # GP2 storage instead of GP3
    "b3c7e2d1-8a4f-4b6e-9c5d-7e1a8f3b2c4d": GP2_STORAGE,
    # No deletion protection
    "893360d4-1ada-5049-abce-9e2bf3803358": NO_DELETION_PROTECTION_RDS,
    # No automated backups
    "594a44db-71b6-5612-abc5-cc485e07158c": NO_BACKUPS_RDS,
    # Over-provisioned storage without autoscaling
    "a4d8f3e1-9c2b-4f7e-8a5d-6b1c9e3f2a4d": OVERPROVISIONED_STORAGE_WITHOUT_AUTOSCALING,
}
