"""SQS evaluators for misconfiguration detection."""

from .base import Condition, Evaluator, Operator


# --- Evaluator definitions ---

# SQS queue not encrypted with KMS
UNENCRYPTED_QUEUE = Evaluator(
    conditions=[
        Condition(field="kms_master_key_id", operator=Operator.IS_NULL),
    ],
    applicable_resource_types=["sqs_queue"],
    description="SQS queue is not encrypted with KMS",
)

STANDARD_QUEUE_DUPLICATES_POSSIBLE = Evaluator(
    conditions=[
        Condition(field="fifo_queue", operator=Operator.IS_FALSE),
    ],
    applicable_resource_types=["sqs_queue"],
    description="SQS standard queue can deliver duplicate messages; FIFO queues provide deduplication",
)


# Registry entries: misconfig_id -> Evaluator
SQS_EVALUATORS = {
    # Unencrypted SQS queue
    "e774f17d-2656-5a6d-9e49-59d006f5daff": UNENCRYPTED_QUEUE,
    # Duplicate message mitigation
    "293ff9bc-a6b4-46ac-a524-c967b965101d": STANDARD_QUEUE_DUPLICATES_POSSIBLE,
}
