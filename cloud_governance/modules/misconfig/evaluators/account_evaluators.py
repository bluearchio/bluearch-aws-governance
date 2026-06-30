"""AWS account and Organizations evaluators for misconfiguration detection."""

from .base import Condition, Evaluator, Operator


MISSING_ALTERNATE_SECURITY_CONTACT = Evaluator(
    conditions=[
        Condition(field="alternate_security_contact_present", operator=Operator.IS_FALSE),
    ],
    applicable_resource_types=["account"],
    description="AWS account has no alternate security contact configured",
)

STANDALONE_ACCOUNT = Evaluator(
    conditions=[
        Condition(field="organization_present", operator=Operator.IS_FALSE),
    ],
    applicable_resource_types=["organization"],
    description="AWS account is not a member of an AWS Organization",
)


ACCOUNT_EVALUATORS = {
    "3e4cd300-6cff-4fd6-9504-38c0f38ab2ac": MISSING_ALTERNATE_SECURITY_CONTACT,
    "77ef079b-c64e-403b-973f-6782b3f8087d": STANDALONE_ACCOUNT,
}
