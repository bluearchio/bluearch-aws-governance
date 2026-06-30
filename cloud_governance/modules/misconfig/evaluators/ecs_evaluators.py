"""ECS evaluators for misconfiguration detection."""

from .base import Evaluator


def _resource_type(resource):
    return getattr(resource, "resource_type", "")


def _inactive_task_definition(metadata, tags, resource):
    if metadata.get("status") == "INACTIVE":
        return (True, "status=INACTIVE")
    return (False, "")


def _platform_not_latest(metadata, tags, resource):
    platform_version = metadata.get("platform_version")
    if _resource_type(resource) != "AWS::ECS::Service" or not platform_version:
        return (False, "")
    if platform_version != "LATEST":
        return (True, f"platform_version={platform_version}")
    return (False, "")


def _deployment_circuit_breaker_disabled(metadata, tags, resource):
    if _resource_type(resource) != "AWS::ECS::Service":
        return (False, "")

    enabled = metadata.get("deployment_circuit_breaker_enabled")
    rollback = metadata.get("deployment_circuit_breaker_rollback")
    details = []
    if enabled is False:
        details.append("deployment_circuit_breaker_enabled=false")
    if rollback is False:
        details.append("deployment_circuit_breaker_rollback=false")
    return (bool(details), "; ".join(details))


def _unsafe_ecs_defaults(metadata, tags, resource):
    details = []
    if _resource_type(resource) == "AWS::ECS::Service":
        if metadata.get("assign_public_ip") == "ENABLED":
            details.append("assign_public_ip=ENABLED")

    if _resource_type(resource) == "AWS::ECS::TaskDefinition":
        privileged = metadata.get("privileged_containers") or []
        writable_root = metadata.get("writable_root_containers") or []
        plaintext = metadata.get("plaintext_secret_env_vars") or []
        if privileged:
            details.append(f"privileged_containers={','.join(privileged)}")
        if writable_root:
            details.append(f"writable_root_containers={','.join(writable_root)}")
        if plaintext:
            details.append(f"plaintext_secret_env_vars={','.join(plaintext)}")

    return (bool(details), "; ".join(details))


# --- Evaluator definitions ---

INACTIVE_TASK_DEFINITION = Evaluator(
    func=_inactive_task_definition,
    applicable_resource_types=["ecs_task_definition"],
    description="ECS task definition is inactive",
)

PLATFORM_NOT_LATEST = Evaluator(
    func=_platform_not_latest,
    applicable_resource_types=["ecs_service"],
    description="ECS service is pinned to a platform version instead of LATEST",
)

DEPLOYMENT_CIRCUIT_BREAKER_DISABLED = Evaluator(
    func=_deployment_circuit_breaker_disabled,
    applicable_resource_types=["ecs_service"],
    description="ECS service deployment circuit breaker or rollback is disabled",
)

UNSAFE_ECS_DEFAULTS = Evaluator(
    func=_unsafe_ecs_defaults,
    applicable_resource_types=["ecs_service", "ecs_task_definition"],
    description="ECS service or task definition uses unsafe defaults",
)


# Registry entries: misconfig_id -> Evaluator
ECS_EVALUATORS = {
    # ECS task definition is inactive
    "4305d944-eb3c-473c-b9ce-99fe6911713b": INACTIVE_TASK_DEFINITION,
    # ECS service is not using the latest platform version
    "326eaec8-4b35-417d-b883-33c31948a9cd": PLATFORM_NOT_LATEST,
    # ECS service deployment circuit breaker / rollback disabled
    "57fdeba4-4823-4bd7-957f-5cb8b0d9f84e": DEPLOYMENT_CIRCUIT_BREAKER_DISABLED,
    # ECS unsafe defaults
    "b792ba90-f7d5-4324-938d-3213142d9d01": UNSAFE_ECS_DEFAULTS,
}
