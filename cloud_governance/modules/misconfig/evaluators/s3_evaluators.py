"""S3 evaluators for misconfiguration detection."""

from .base import Evaluator


def _metadata_flag(metadata, field, expected, detail_name=None):
    actual = metadata.get(field)
    if actual == expected:
        return (True, f"{detail_name or field}={actual}")
    return (False, "")


def _unencrypted_bucket(metadata, tags, resource):
    return _metadata_flag(metadata, "encryption", "none")


def _public_bucket(metadata, tags, resource):
    details = []
    if metadata.get("bucket_policy_is_public") is True:
        details.append("bucket_policy_is_public=true")
    if metadata.get("acl_public") is True:
        details.append("acl_public=true")
    return (bool(details), "; ".join(details))


def _missing_lifecycle(metadata, tags, resource):
    return _metadata_flag(metadata, "lifecycle_enabled", False)


def _missing_access_logging(metadata, tags, resource):
    return _metadata_flag(metadata, "logging_enabled", False)


def _versioning_disabled(metadata, tags, resource):
    return _metadata_flag(metadata, "versioning", "Disabled")


def _mfa_delete_disabled(metadata, tags, resource):
    mfa_delete = metadata.get("mfa_delete")
    if mfa_delete in {"Disabled", "Off"}:
        return (True, f"mfa_delete={mfa_delete}")
    return (False, "")


def _public_all_actions_policy(metadata, tags, resource):
    return _metadata_flag(
        metadata,
        "bucket_policy_allows_all_principals_all_actions",
        True,
    )


def _public_delete_actions_policy(metadata, tags, resource):
    return _metadata_flag(
        metadata,
        "bucket_policy_allows_public_delete_actions",
        True,
    )


def _missing_ssl_enforcement(metadata, tags, resource):
    return _metadata_flag(metadata, "bucket_policy_enforces_ssl", False)


def _object_lock_disabled(metadata, tags, resource):
    return _metadata_flag(metadata, "object_lock_enabled", False)


def _missing_encrypted_write_enforcement(metadata, tags, resource):
    return _metadata_flag(metadata, "bucket_policy_enforces_encrypted_writes", False)


def _cloudtrail_log_bucket_missing_access_logging(metadata, tags, resource):
    if metadata.get("is_cloudtrail_log_bucket") is not True:
        return (False, "")
    if metadata.get("logging_enabled") is False:
        return (True, "is_cloudtrail_log_bucket=True; logging_enabled=False")
    return (False, "")


def _cloudtrail_log_bucket_public(metadata, tags, resource):
    if metadata.get("is_cloudtrail_log_bucket") is not True:
        return (False, "")
    details = []
    if metadata.get("bucket_policy_is_public") is True:
        details.append("bucket_policy_is_public=true")
    if metadata.get("acl_public") is True:
        details.append("acl_public=true")
    if details:
        return (True, "; ".join(["is_cloudtrail_log_bucket=True", *details]))
    return (False, "")


# --- Evaluator definitions ---

UNENCRYPTED_BUCKET = Evaluator(
    func=_unencrypted_bucket,
    applicable_resource_types=["s3_bucket"],
    description="S3 bucket does not have default server-side encryption configured",
)

PUBLIC_BUCKET = Evaluator(
    func=_public_bucket,
    applicable_resource_types=["s3_bucket"],
    description="S3 bucket policy or ACL is public",
)

MISSING_LIFECYCLE = Evaluator(
    func=_missing_lifecycle,
    applicable_resource_types=["s3_bucket"],
    description="S3 bucket does not have an enabled lifecycle configuration",
)

MISSING_ACCESS_LOGGING = Evaluator(
    func=_missing_access_logging,
    applicable_resource_types=["s3_bucket"],
    description="S3 bucket server access logging is disabled",
)

VERSIONING_DISABLED = Evaluator(
    func=_versioning_disabled,
    applicable_resource_types=["s3_bucket"],
    description="S3 bucket versioning is disabled",
)

MFA_DELETE_DISABLED = Evaluator(
    func=_mfa_delete_disabled,
    applicable_resource_types=["s3_bucket"],
    description="S3 bucket versioning MFA delete is disabled",
)

PUBLIC_ALL_ACTIONS_POLICY = Evaluator(
    func=_public_all_actions_policy,
    applicable_resource_types=["s3_bucket"],
    description="S3 bucket policy allows all principals to perform all S3 actions",
)

PUBLIC_DELETE_ACTIONS_POLICY = Evaluator(
    func=_public_delete_actions_policy,
    applicable_resource_types=["s3_bucket"],
    description="S3 bucket policy allows public delete actions",
)

MISSING_SSL_ENFORCEMENT = Evaluator(
    func=_missing_ssl_enforcement,
    applicable_resource_types=["s3_bucket"],
    description="S3 bucket policy does not deny insecure transport",
)

OBJECT_LOCK_DISABLED = Evaluator(
    func=_object_lock_disabled,
    applicable_resource_types=["s3_bucket"],
    description="S3 bucket object lock is disabled",
)

MISSING_ENCRYPTED_WRITE_ENFORCEMENT = Evaluator(
    func=_missing_encrypted_write_enforcement,
    applicable_resource_types=["s3_bucket"],
    description="S3 bucket policy does not deny unencrypted PutObject writes",
)

CLOUDTRAIL_LOG_BUCKET_MISSING_ACCESS_LOGGING = Evaluator(
    func=_cloudtrail_log_bucket_missing_access_logging,
    applicable_resource_types=["s3_bucket"],
    description="CloudTrail log bucket does not have S3 server access logging enabled",
)

CLOUDTRAIL_LOG_BUCKET_PUBLIC = Evaluator(
    func=_cloudtrail_log_bucket_public,
    applicable_resource_types=["s3_bucket"],
    description="CloudTrail log bucket is publicly accessible through policy or ACL",
)


# Registry entries: misconfig_id -> Evaluator
S3_EVALUATORS = {
    # S3 lifecycle/intelligent tiering is not configured
    "e9b21a0d-2fe8-4f5b-8875-52995b4cf2e7": MISSING_LIFECYCLE,
    # S3 standard storage without lifecycle policies
    "ffc337be-4cb6-4899-b02c-d447af23221e": MISSING_LIFECYCLE,
    # S3 bucket default encryption is not configured
    "03736e4a-6ce5-4375-84ce-278711247314": UNENCRYPTED_BUCKET,
    "2b2b9981-af69-40ca-a033-f39dd6eef852": UNENCRYPTED_BUCKET,
    # S3 bucket is public through policy or ACL
    "356570fe-de33-4782-bc81-152cb144fb05": PUBLIC_BUCKET,
    "f09206a7-4462-400d-811b-fd5f9be3b90a": PUBLIC_BUCKET,
    # S3 bucket policy grants public broad or delete access
    "06aabba0-436b-4295-91b1-165ee4741dc8": PUBLIC_ALL_ACTIONS_POLICY,
    "743e9f6e-7cda-4e47-bbbb-10e47c728456": PUBLIC_DELETE_ACTIONS_POLICY,
    # S3 bucket policy does not enforce TLS
    "ce620d59-96ae-4465-b6cf-6262e9e5f403": MISSING_SSL_ENFORCEMENT,
    # S3 bucket policy does not enforce encrypted object writes
    "83c3686a-7b31-478e-b388-453384ad53ba": MISSING_ENCRYPTED_WRITE_ENFORCEMENT,
    # S3 object lock / WORM protection is disabled
    "73c98951-d7a6-4858-b14a-e209b16bb222": OBJECT_LOCK_DISABLED,
    # S3 server access logging is disabled
    "fa44e6cf-5243-4819-8256-2379e5347eff": MISSING_ACCESS_LOGGING,
    # CloudTrail log bucket logging and public access posture
    "5449c935-aa36-4885-86e0-fee05a533361": CLOUDTRAIL_LOG_BUCKET_MISSING_ACCESS_LOGGING,
    "e8d205d0-3a21-49b3-9b3c-8ef6214a2b5e": CLOUDTRAIL_LOG_BUCKET_PUBLIC,
    # S3 versioning and MFA delete are disabled
    "60c00aeb-ec1d-4b10-91fa-7025fd7a70be": VERSIONING_DISABLED,
    "a97bfdeb-87c8-4550-a146-e926be7e6ecf": MFA_DELETE_DISABLED,
}
