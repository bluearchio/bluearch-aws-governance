"""GuardDuty evaluators for misconfiguration detection."""

from .base import Evaluator


def _guardduty_detector_missing(metadata, tags, resource):
    detector_present = metadata.get("detector_present")
    if detector_present is False:
        return (True, "detector_present=false")
    return (False, "")


# --- Evaluator definitions ---

GUARDDUTY_DETECTOR_MISSING = Evaluator(
    func=_guardduty_detector_missing,
    applicable_resource_types=["guardduty_region"],
    description="GuardDuty detector is not enabled in the scanned region",
)


# Registry entries: misconfig_id -> Evaluator
GUARDDUTY_EVALUATORS = {
    "ffb6b99f-0dec-47a4-9274-6e1552c05c02": GUARDDUTY_DETECTOR_MISSING,
}
