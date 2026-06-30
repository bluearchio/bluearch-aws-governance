"""SNS evaluators for misconfiguration detection."""

from .base import Condition, Evaluator, Operator


# --- Evaluator definitions ---

# SNS topic not encrypted with KMS
UNENCRYPTED_TOPIC = Evaluator(
    conditions=[
        Condition(field="kms_master_key_id", operator=Operator.IS_NULL),
    ],
    applicable_resource_types=["sns_topic"],
    description="SNS topic is not encrypted with KMS",
)

NO_CONFIRMED_SUBSCRIBERS = Evaluator(
    conditions=[
        Condition(field="subscriptions_confirmed", operator=Operator.LTE, value=0),
    ],
    applicable_resource_types=["sns_topic"],
    description="SNS topic has no confirmed subscribers",
)


# Registry entries: misconfig_id -> Evaluator
SNS_EVALUATORS = {
    # Unencrypted SNS topic
    "55a01003-ad34-5418-9979-9b08757cd04e": UNENCRYPTED_TOPIC,
    # Topic subscriber configuration
    "55db77af-694b-428d-8337-fa10d770e17f": NO_CONFIRMED_SUBSCRIBERS,
}
