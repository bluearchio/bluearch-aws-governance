"""Kinesis evaluators for misconfiguration detection."""

from .base import Condition, Evaluator, Operator


UNENCRYPTED_STREAM = Evaluator(
    conditions=[
        Condition(field="encrypted", operator=Operator.IS_FALSE),
    ],
    applicable_resource_types=["kinesis_stream"],
    description="Kinesis stream is not encrypted with server-side KMS encryption",
)

MISSING_CUSTOMER_MANAGED_KMS_KEY = Evaluator(
    conditions=[
        Condition(field="customer_managed_kms_key", operator=Operator.IS_FALSE),
    ],
    applicable_resource_types=["kinesis_stream"],
    description="Kinesis stream is not encrypted with a customer-managed KMS key",
)


KINESIS_EVALUATORS = {
    "9f926c3f-adce-47e7-8d55-e2fad047d3a9": UNENCRYPTED_STREAM,
    "df37f539-ce9b-4eb3-9ff9-fc8b820b6e7d": MISSING_CUSTOMER_MANAGED_KMS_KEY,
}
