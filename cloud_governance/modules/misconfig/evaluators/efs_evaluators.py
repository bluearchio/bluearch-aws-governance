"""EFS evaluators for misconfiguration detection."""

from .base import Condition, Evaluator, Operator


def _inactive_or_unmounted_file_system(metadata, tags, resource):
    mount_target_count = metadata.get("mount_target_count")
    client_connections = metadata.get("client_connections_max_14d")
    total_io_bytes = metadata.get("total_io_bytes_14d")

    if mount_target_count == 0:
        return (True, "mount_target_count=0")
    if client_connections == 0 or total_io_bytes == 0:
        details = []
        if client_connections == 0:
            details.append("client_connections_max_14d=0")
        if total_io_bytes == 0:
            details.append("total_io_bytes_14d=0")
        return (True, "; ".join(details))
    return (False, "")


def _missing_lifecycle_policy(metadata, tags, resource):
    transitions = metadata.get("lifecycle_transitions") or []
    if not transitions:
        return (True, "lifecycle_transitions=[]")
    return (False, "")


def _replicated_file_system_missing_lifecycle(metadata, tags, resource):
    replication_count = metadata.get("replication_configuration_count") or 0
    transitions = metadata.get("lifecycle_transitions") or []
    if replication_count > 0 and not transitions:
        return (True, f"replication_configuration_count={replication_count}; lifecycle_transitions=[]")
    return (False, "")


INACTIVE_OR_UNMOUNTED_FILE_SYSTEM = Evaluator(
    func=_inactive_or_unmounted_file_system,
    applicable_resource_types=["efs_file_system"],
    description="EFS file system is unmounted or has no observed client connections or IO",
)

MISSING_LIFECYCLE_POLICY = Evaluator(
    func=_missing_lifecycle_policy,
    applicable_resource_types=["efs_file_system"],
    description="EFS file system has no lifecycle transition policy",
)

REPLICATED_FILE_SYSTEM_MISSING_LIFECYCLE = Evaluator(
    func=_replicated_file_system_missing_lifecycle,
    applicable_resource_types=["efs_file_system"],
    description="Replicated EFS file system has no lifecycle transition policy",
)

UNENCRYPTED_FILE_SYSTEM = Evaluator(
    conditions=[
        Condition(field="encrypted", operator=Operator.IS_FALSE),
    ],
    applicable_resource_types=["efs_file_system"],
    description="EFS file system is not encrypted",
)

MISSING_CUSTOMER_MANAGED_KMS_KEY = Evaluator(
    conditions=[
        Condition(field="customer_managed_kms_key", operator=Operator.IS_FALSE),
    ],
    applicable_resource_types=["efs_file_system"],
    description="EFS file system is not encrypted with a customer-managed KMS key",
)


EFS_EVALUATORS = {
    "d5001001-ef01-4001-b001-001000000001": INACTIVE_OR_UNMOUNTED_FILE_SYSTEM,
    "d5001002-ef02-4002-b002-002000000002": MISSING_LIFECYCLE_POLICY,
    "d5001003-ef03-4003-b003-003000000003": REPLICATED_FILE_SYSTEM_MISSING_LIFECYCLE,
    "74b0f0d7-fcb8-46ed-beb4-3d3ec6ecbe64": UNENCRYPTED_FILE_SYSTEM,
    "4e33a295-b0c0-4cb5-a8ac-942a08de57b3": MISSING_CUSTOMER_MANAGED_KMS_KEY,
}
