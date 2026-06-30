"""AWS Config evaluators for misconfiguration detection."""

from .base import Condition, Evaluator, Operator


CONFIG_NOT_RECORDING = Evaluator(
    conditions=[
        Condition(field="recording", operator=Operator.IS_FALSE),
    ],
    applicable_resource_types=["config_recorder"],
    description="AWS Config recorder is missing or not recording in the region",
)

CONFIG_RECORDING_ALL_RESOURCE_TYPES = Evaluator(
    conditions=[
        Condition(field="all_supported", operator=Operator.IS_TRUE),
    ],
    applicable_resource_types=["config_recorder"],
    description="AWS Config recorder captures all supported resource types",
)


CONFIG_EVALUATORS = {
    "06f2bdc9-2b6e-4c70-895d-1b6d4e17f87c": CONFIG_NOT_RECORDING,
    "6e839f06-4474-45c8-82a9-84003aade522": CONFIG_NOT_RECORDING,
    "e6001003-cf03-4003-a003-003000000003": CONFIG_RECORDING_ALL_RESOURCE_TYPES,
}
