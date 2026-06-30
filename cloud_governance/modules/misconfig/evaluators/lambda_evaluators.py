"""Lambda evaluators for misconfiguration detection."""

from .base import Evaluator


# Known deprecated Lambda runtimes (EOL'd by AWS)
DEPRECATED_RUNTIMES = {
    'python2.7', 'python3.6', 'python3.7', 'python3.8',
    'nodejs', 'nodejs4.3', 'nodejs4.3-edge', 'nodejs6.10',
    'nodejs8.10', 'nodejs10.x', 'nodejs12.x', 'nodejs14.x', 'nodejs16.x',
    'dotnetcore1.0', 'dotnetcore2.0', 'dotnetcore2.1', 'dotnetcore3.1',
    'dotnet5.0', 'dotnet6',
    'java8', 'java8.al2',
    'go1.x',
    'ruby2.5', 'ruby2.7',
}


def _is_default_memory(metadata, tags, resource):
    """Check if Lambda function uses the default 128MB memory."""
    memory = metadata.get('memory_size')
    if memory is not None and memory == 128:
        return (True, "memory_size=128")
    return (False, "")


def _is_deprecated_runtime(metadata, tags, resource):
    """Check if Lambda function uses a deprecated runtime."""
    runtime = metadata.get('runtime')
    if not runtime:
        # Container-based functions don't have a runtime
        return (False, "")
    if runtime in DEPRECATED_RUNTIMES:
        return (True, f"runtime={runtime}")
    return (False, "")


def _lambda_throttled(metadata, tags, resource):
    throttles = metadata.get("throttles_lookback")
    if throttles is not None and throttles > 0:
        return (True, f"throttles_lookback={int(throttles)}")
    return (False, "")


def _lambda_high_error_rate(metadata, tags, resource):
    invocations = metadata.get("invocations_lookback")
    error_rate = metadata.get("error_rate")
    if invocations and error_rate is not None and error_rate > 0.10:
        return (True, f"error_rate={error_rate:.2f}")
    return (False, "")


def _inactive_lambda_function(metadata, tags, resource):
    age_days = metadata.get("last_modified_age_days")
    invocations = metadata.get("invocations_lookback")
    if age_days is not None and age_days >= 30 and invocations == 0:
        return (True, f"last_modified_age_days={age_days}; invocations_lookback=0")
    return (False, "")


def _very_old_inactive_lambda_function(metadata, tags, resource):
    age_days = metadata.get("last_modified_age_days")
    invocations = metadata.get("invocations_lookback")
    if age_days is not None and age_days >= 365 and invocations == 0:
        return (True, f"last_modified_age_days={age_days}; invocations_lookback=0")
    return (False, "")


def _shared_execution_role(metadata, tags, resource):
    count = metadata.get("execution_role_function_count")
    if count is not None and count > 1:
        return (True, f"execution_role_function_count={count}")
    return (False, "")


# --- Evaluator definitions ---

DEFAULT_MEMORY = Evaluator(
    func=_is_default_memory,
    applicable_resource_types=["lambda_function"],
    description="Lambda function uses default 128MB memory allocation",
)

DEPRECATED_RUNTIME = Evaluator(
    func=_is_deprecated_runtime,
    applicable_resource_types=["lambda_function"],
    description="Lambda function uses a deprecated runtime",
)

THROTTLING_OCCURRED = Evaluator(
    func=_lambda_throttled,
    applicable_resource_types=["lambda_function"],
    description="Lambda function has throttled invocations over the metric lookback",
)

HIGH_ERROR_RATE = Evaluator(
    func=_lambda_high_error_rate,
    applicable_resource_types=["lambda_function"],
    description="Lambda function has an error rate over 10 percent during the metric lookback",
)

INACTIVE_FUNCTION = Evaluator(
    func=_inactive_lambda_function,
    applicable_resource_types=["lambda_function"],
    description="Lambda function is older than 30 days and has no invocations in the metric lookback",
)

VERY_OLD_INACTIVE_FUNCTION = Evaluator(
    func=_very_old_inactive_lambda_function,
    applicable_resource_types=["lambda_function"],
    description="Lambda function is older than one year and has no invocations in the metric lookback",
)

XRAY_TRACING_DISABLED = Evaluator(
    func=lambda metadata, tags, resource: (
        (True, "xray_tracing_enabled=false")
        if metadata.get("xray_tracing_enabled") is False
        else (False, "")
    ),
    applicable_resource_types=["lambda_function"],
    description="Lambda function does not have X-Ray tracing enabled",
)

SHARED_EXECUTION_ROLE = Evaluator(
    func=_shared_execution_role,
    applicable_resource_types=["lambda_function"],
    description="Multiple Lambda functions share the same execution role",
)


# Registry entries: misconfig_id -> Evaluator
# Note: Lambda misconfigs in the DB don't have clear 1:1 IDs for these checks.
# The "processes performing poorly" (1f780989-...) maps loosely to default memory.
# We register what we can match:
LAMBDA_EVALUATORS = {
    # Lambda performing poorly / default memory
    "1f780989-b697-4817-b38c-dee807324c6b": DEFAULT_MEMORY,
    # Deprecated runtime
    "eb131adb-89d6-5c40-8733-5d8ef92910ae": DEPRECATED_RUNTIME,
    # Lambda throttling / high error rates
    "c8fd0f3c-90c1-45ec-9467-963920497527": THROTTLING_OCCURRED,
    "59b90e10-df31-4a2e-9cd7-1a598eecb2a1": HIGH_ERROR_RATE,
    # Lambda inactivity / tracing / role isolation
    "d814745d-a655-4612-9d03-07f7236cab77": INACTIVE_FUNCTION,
    "64a6e315-cfef-4450-a761-247576cbe77e": VERY_OLD_INACTIVE_FUNCTION,
    "2cd8897d-8db5-4bde-8476-1edbe7f97894": XRAY_TRACING_DISABLED,
    "24a0eea7-9e43-4549-9c5d-17d1ddcaa4ef": SHARED_EXECUTION_ROLE,
}
