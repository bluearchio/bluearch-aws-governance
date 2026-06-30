"""Elastic Beanstalk evaluators for misconfiguration detection."""

from .base import Evaluator


HEALTHY_VALUES = {"Green", "Ok"}
READY_STATUSES = {"Ready", "Updating"}


def _environment_unhealthy(metadata, tags, resource):
    health = metadata.get("health")
    health_status = metadata.get("health_status")
    status = metadata.get("status")
    if health and health not in HEALTHY_VALUES:
        return (True, f"health={health}")
    if health_status and health_status not in HEALTHY_VALUES:
        return (True, f"health_status={health_status}")
    if status and status not in READY_STATUSES:
        return (True, f"status={status}")
    return (False, "")


def _platform_deprecated(metadata, tags, resource):
    values = [
        metadata.get("platform_lifecycle_state"),
        metadata.get("platform_status"),
    ]
    for value in values:
        if value and str(value).lower() in {"deprecated", "retired", "deleted"}:
            return (True, f"platform_state={value}")
    return (False, "")


ENVIRONMENT_UNHEALTHY = Evaluator(
    func=_environment_unhealthy,
    applicable_resource_types=["elastic_beanstalk_environment"],
    description="Elastic Beanstalk environment is not healthy or ready",
)

PLATFORM_DEPRECATED = Evaluator(
    func=_platform_deprecated,
    applicable_resource_types=["elastic_beanstalk_environment"],
    description="Elastic Beanstalk environment platform is deprecated or retired",
)


ELASTIC_BEANSTALK_EVALUATORS = {
    "c727a01a-e43a-4157-a80c-21dc130a50c5": ENVIRONMENT_UNHEALTHY,
    "ceb5228b-8733-4978-8fed-36588bfb638d": PLATFORM_DEPRECATED,
}
