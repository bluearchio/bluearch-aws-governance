"""DynamoDB evaluators for misconfiguration detection."""

from .base import Condition, Evaluator, Operator


DYNAMODB_UNDERUTILIZED_THRESHOLD = 0.30


def _inactive_table(metadata, tags, resource):
    age_days = metadata.get("age_days")
    read_units = metadata.get("consumed_read_capacity_units_lookback")
    write_units = metadata.get("consumed_write_capacity_units_lookback")
    if age_days is not None and age_days < 7:
        return (False, "")
    if read_units == 0 and write_units == 0:
        lookback = metadata.get("capacity_metric_lookback_days")
        return (True, f"read_write_capacity_units_{lookback}d=0")
    return (False, "")


def _underutilized_capacity(capacity_field: str, usage_field: str, detail_label: str):
    def _evaluate(metadata, tags, resource):
        if metadata.get("billing_mode") != "PROVISIONED":
            return (False, "")
        provisioned = metadata.get(capacity_field)
        used = metadata.get(usage_field)
        if not provisioned or used is None:
            return (False, "")
        utilization = used / provisioned
        if utilization < DYNAMODB_UNDERUTILIZED_THRESHOLD:
            return (True, f"{detail_label}_utilization={utilization:.2f}")
        return (False, "")

    return _evaluate


def _standard_table_class_with_no_access(metadata, tags, resource):
    table_class = metadata.get("table_class")
    read_units = metadata.get("consumed_read_capacity_units_lookback")
    write_units = metadata.get("consumed_write_capacity_units_lookback")
    if table_class == "STANDARD" and read_units == 0 and write_units == 0:
        return (True, "table_class=STANDARD; read_write_capacity_units=0")
    return (False, "")


# --- Evaluator definitions ---

# No deletion protection
NO_DELETION_PROTECTION = Evaluator(
    conditions=[
        Condition(field="deletion_protection", operator=Operator.IS_FALSE),
    ],
    applicable_resource_types=["dynamodb_table"],
    description="DynamoDB table does not have deletion protection enabled",
)

INACTIVE_TABLE = Evaluator(
    func=_inactive_table,
    applicable_resource_types=["dynamodb_table"],
    description="DynamoDB table has no read or write activity over the metric lookback",
)

UNDERUTILIZED_READ_CAPACITY = Evaluator(
    func=_underutilized_capacity(
        "provisioned_read_capacity_units",
        "avg_read_capacity_units_per_second",
        "read_capacity",
    ),
    applicable_resource_types=["dynamodb_table"],
    description="Provisioned DynamoDB read capacity is under 30 percent utilized",
)

UNDERUTILIZED_WRITE_CAPACITY = Evaluator(
    func=_underutilized_capacity(
        "provisioned_write_capacity_units",
        "avg_write_capacity_units_per_second",
        "write_capacity",
    ),
    applicable_resource_types=["dynamodb_table"],
    description="Provisioned DynamoDB write capacity is under 30 percent utilized",
)

THROTTLED_REQUESTS = Evaluator(
    conditions=[
        Condition(field="throttled_requests_lookback", operator=Operator.GT, value=0),
    ],
    applicable_resource_types=["dynamodb_table"],
    description="DynamoDB table has throttled requests over the metric lookback",
)

STANDARD_CLASS_WITH_NO_ACCESS = Evaluator(
    func=_standard_table_class_with_no_access,
    applicable_resource_types=["dynamodb_table"],
    description="DynamoDB table uses Standard class but has no observed access over the lookback",
)


# Registry entries: misconfig_id -> Evaluator
DYNAMODB_EVALUATORS = {
    # Inactive table / provisioned capacity utilization
    "b4839001-ddb1-4001-c001-001000000001": INACTIVE_TABLE,
    "b4839004-ddb4-4004-c004-004000000004": UNDERUTILIZED_READ_CAPACITY,
    "b4839005-ddb5-4005-c005-005000000005": UNDERUTILIZED_WRITE_CAPACITY,
    "b4839003-ddb3-4003-c003-003000000003": STANDARD_CLASS_WITH_NO_ACCESS,
    "e3de8e59-c849-4544-8b17-e66164d45a64": THROTTLED_REQUESTS,
    "b950825d-41ae-4637-a0c8-281f8903596f": THROTTLED_REQUESTS,
    # DynamoDB deletion protection disabled
    "f7fc3d66-ba34-504f-9af5-3a2ac5abfb89": NO_DELETION_PROTECTION,
}
