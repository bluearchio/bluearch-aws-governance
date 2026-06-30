"""CloudWatch evaluators for misconfiguration detection."""

from .base import Condition, Evaluator, Operator


# --- Evaluator definitions ---

# No log retention policy (retention_days is null = never expire)
NO_LOG_RETENTION = Evaluator(
    conditions=[
        Condition(field="retention_days", operator=Operator.IS_NULL),
    ],
    applicable_resource_types=["cloudwatch_log_group"],
    description="CloudWatch Log Group has no retention policy (never expires)",
)


# Registry entries: misconfig_id -> Evaluator
CLOUDWATCH_EVALUATORS = {
    # No log retention
    "e7b5c9a1-3f2d-4e8b-9c6a-1d5e8f2b4a3c": NO_LOG_RETENTION,
}
