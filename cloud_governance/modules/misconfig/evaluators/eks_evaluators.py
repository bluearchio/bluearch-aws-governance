"""EKS evaluators for misconfiguration detection."""

from .base import Evaluator


def _guardduty_runtime_monitoring_disabled(metadata, tags, resource):
    runtime_enabled = metadata.get("guardduty_runtime_monitoring_enabled")
    if runtime_enabled is False:
        return (True, "guardduty_runtime_monitoring_enabled=false")
    return (False, "")


# --- Evaluator definitions ---

GUARDDUTY_RUNTIME_MONITORING_DISABLED = Evaluator(
    func=_guardduty_runtime_monitoring_disabled,
    applicable_resource_types=["eks_cluster"],
    description="GuardDuty EKS runtime monitoring is not enabled for the region",
)


# Registry entries: misconfig_id -> Evaluator
EKS_EVALUATORS = {
    # Amazon EKS clusters do not have GuardDuty Extended Threat Detection enabled
    "38c186b1-36f2-4133-a6ef-9c1628f5c6f6": GUARDDUTY_RUNTIME_MONITORING_DISABLED,
}
