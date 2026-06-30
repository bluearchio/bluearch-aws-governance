"""Network Firewall evaluators for misconfiguration detection."""

from .base import Evaluator


def _missing_active_threat_defense(metadata, tags, resource):
    if metadata.get("managed_threat_rule_group_present") is False:
        return (True, "managed_threat_rule_group_present=false")
    return (False, "")


MISSING_ACTIVE_THREAT_DEFENSE = Evaluator(
    func=_missing_active_threat_defense,
    applicable_resource_types=["network_firewall"],
    description="Network Firewall policy has no detected AWS managed threat-defense rule group",
)


NETWORK_FIREWALL_EVALUATORS = {
    "b86ef141-f21b-4818-9062-fee738816c22": MISSING_ACTIVE_THREAT_DEFENSE,
}
