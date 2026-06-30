"""CloudTrail evaluators for misconfiguration detection."""

from .base import Evaluator


def _cloudtrail_not_logging(metadata, tags, resource):
    count = metadata.get("logging_trail_count")
    if count == 0:
        return (True, "logging_trail_count=0")
    return (False, "")


def _multi_region_trail_missing(metadata, tags, resource):
    if metadata.get("multi_region_trail_present") is False:
        return (True, "multi_region_trail_present=false")
    return (False, "")


def _log_file_validation_disabled(metadata, tags, resource):
    if metadata.get("log_file_validation_enabled") is False:
        return (True, "log_file_validation_enabled=false")
    return (False, "")


def _kms_encryption_missing(metadata, tags, resource):
    if not metadata.get("kms_key_id"):
        return (True, "kms_key_id=null")
    return (False, "")


def _cloudwatch_logs_missing(metadata, tags, resource):
    if not metadata.get("cloud_watch_logs_log_group_arn"):
        return (True, "cloud_watch_logs_log_group_arn=null")
    return (False, "")


# --- Evaluator definitions ---

CLOUDTRAIL_NOT_LOGGING = Evaluator(
    func=_cloudtrail_not_logging,
    applicable_resource_types=["cloudtrail_region"],
    description="CloudTrail has no logging trail in the scanned region",
)

MULTI_REGION_TRAIL_MISSING = Evaluator(
    func=_multi_region_trail_missing,
    applicable_resource_types=["cloudtrail_region"],
    description="CloudTrail has no multi-region trail visible in the scanned region",
)

LOG_FILE_VALIDATION_DISABLED = Evaluator(
    func=_log_file_validation_disabled,
    applicable_resource_types=["cloudtrail_trail"],
    description="CloudTrail trail log file validation is disabled",
)

KMS_ENCRYPTION_MISSING = Evaluator(
    func=_kms_encryption_missing,
    applicable_resource_types=["cloudtrail_trail"],
    description="CloudTrail trail is not encrypted with a KMS key",
)

CLOUDWATCH_LOGS_MISSING = Evaluator(
    func=_cloudwatch_logs_missing,
    applicable_resource_types=["cloudtrail_trail"],
    description="CloudTrail trail is not integrated with CloudWatch Logs",
)


# Registry entries: misconfig_id -> Evaluator
CLOUDTRAIL_EVALUATORS = {
    "1a48e014-dc5b-4b3d-9e8a-4fa00ebd4223": CLOUDTRAIL_NOT_LOGGING,
    "a947ee7d-2155-4f72-8c3f-4097c7ec3974": MULTI_REGION_TRAIL_MISSING,
    "450eb05d-23fe-47dc-83f0-4e13c1149c00": LOG_FILE_VALIDATION_DISABLED,
    "bbeaea1f-8aeb-4a4b-978c-7f05c0ed0722": KMS_ENCRYPTION_MISSING,
    "3eae64a8-7a42-4ffc-b552-6e7a8555d3c3": CLOUDWATCH_LOGS_MISSING,
}
