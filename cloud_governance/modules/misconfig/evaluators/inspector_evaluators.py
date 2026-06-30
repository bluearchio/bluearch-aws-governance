"""Inspector evaluators for misconfiguration detection."""

from .base import Evaluator


HIGH_RISK_SEVERITIES = {"HIGH", "CRITICAL"}


def _active_high_risk_finding(metadata, tags, resource):
    status = metadata.get("status")
    severity = metadata.get("severity")
    if status == "ACTIVE" and severity in HIGH_RISK_SEVERITIES:
        return (True, f"severity={severity}")
    return (False, "")


# --- Evaluator definitions ---

ACTIVE_HIGH_RISK_FINDING = Evaluator(
    func=_active_high_risk_finding,
    applicable_resource_types=["inspector_finding"],
    description="Inspector has active high or critical findings",
)


# Registry entries: misconfig_id -> Evaluator
INSPECTOR_EVALUATORS = {
    "be5dfe89-42e6-489b-9b70-3c32a154ffc8": ACTIVE_HIGH_RISK_FINDING,
}
