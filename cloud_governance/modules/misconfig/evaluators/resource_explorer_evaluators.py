"""Resource Explorer evaluators for misconfiguration detection."""

from .base import Evaluator


def _resource_explorer_disabled(metadata, tags, resource):
    if metadata.get("index_enabled") is False:
        return (True, "index_enabled=false")
    return (False, "")


RESOURCE_EXPLORER_DISABLED = Evaluator(
    func=_resource_explorer_disabled,
    applicable_resource_types=["resource_explorer_index"],
    description="AWS Resource Explorer index is not enabled in the region",
)


RESOURCE_EXPLORER_EVALUATORS = {
    "277608d6-b89d-459a-ab2d-e2c05ac47af3": RESOURCE_EXPLORER_DISABLED,
}
