"""Security Hub evaluators for misconfiguration detection."""

from .base import Evaluator


def _security_hub_not_enabled_to_aggregate(metadata, tags, resource):
    hub_enabled = metadata.get("hub_enabled")
    finding_aggregator_present = metadata.get("finding_aggregator_present")

    if hub_enabled is False:
        return (True, "hub_enabled=false")
    if hub_enabled is True and finding_aggregator_present is False:
        return (True, "finding_aggregator_present=false")
    return (False, "")


# --- Evaluator definitions ---

SECURITY_HUB_NOT_ENABLED_TO_AGGREGATE = Evaluator(
    func=_security_hub_not_enabled_to_aggregate,
    applicable_resource_types=["securityhub_region"],
    description="Security Hub is not enabled or has no finding aggregator in the scanned region",
)


# Registry entries: misconfig_id -> Evaluator
SECURITYHUB_EVALUATORS = {
    "de2df33a-9650-4d05-86a8-5f2c716a6034": SECURITY_HUB_NOT_ENABLED_TO_AGGREGATE,
}
