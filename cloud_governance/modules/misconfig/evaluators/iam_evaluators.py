"""IAM evaluators for misconfiguration detection."""

from .base import Evaluator


KEY_ROTATION_DAYS = 90


def _resource_type(resource):
    return getattr(resource, "resource_type", "")


def _active_key_age(metadata):
    if metadata.get("status") != "Active":
        return None
    return metadata.get("age_days")


def _old_access_key(metadata, tags, resource):
    age_days = _active_key_age(metadata)
    if age_days is not None and age_days > KEY_ROTATION_DAYS:
        return (True, f"age_days={age_days}")
    return (False, "")


def _first_access_key_old(metadata, tags, resource):
    if metadata.get("access_key_index") != 1:
        return (False, "")
    return _old_access_key(metadata, tags, resource)


def _second_access_key_old(metadata, tags, resource):
    if metadata.get("access_key_index") != 2:
        return (False, "")
    return _old_access_key(metadata, tags, resource)


def _root_mfa_disabled(metadata, tags, resource):
    if metadata.get("account_mfa_enabled") is False:
        return (True, "account_mfa_enabled=false")
    return (False, "")


def _root_access_key_present(metadata, tags, resource):
    count = metadata.get("account_access_keys_present")
    if count and count > 0:
        return (True, f"account_access_keys_present={count}")
    return (False, "")


def _support_role_missing(metadata, tags, resource):
    if metadata.get("support_role_present") is False:
        return (True, "support_role_present=false")
    return (False, "")


def _password_policy_missing_number(metadata, tags, resource):
    if metadata.get("password_policy_present") is False:
        return (True, "password_policy_present=false")
    if metadata.get("require_numbers") is False:
        return (True, "require_numbers=false")
    return (False, "")


def _weak_password_policy(metadata, tags, resource):
    if metadata.get("password_policy_present") is False:
        return (True, "password_policy_present=false")

    details = []
    minimum_length = metadata.get("minimum_password_length")
    reuse_prevention = metadata.get("password_reuse_prevention")
    max_password_age = metadata.get("max_password_age")
    required_flags = [
        ("require_symbols", metadata.get("require_symbols")),
        ("require_numbers", metadata.get("require_numbers")),
        ("require_uppercase_characters", metadata.get("require_uppercase_characters")),
        ("require_lowercase_characters", metadata.get("require_lowercase_characters")),
    ]
    for name, value in required_flags:
        if value is False:
            details.append(f"{name}=false")
    if minimum_length is not None and minimum_length < 14:
        details.append(f"minimum_password_length={minimum_length}")
    if reuse_prevention is not None and reuse_prevention < 24:
        details.append(f"password_reuse_prevention={reuse_prevention}")
    if max_password_age is not None and max_password_age > 90:
        details.append(f"max_password_age={max_password_age}")

    return (bool(details), "; ".join(details))


def _console_user_without_mfa(metadata, tags, resource):
    if _resource_type(resource) != "AWS::IAM::User":
        return (False, "")
    if metadata.get("password_enabled") is True and metadata.get("mfa_device_count") == 0:
        return (True, "password_enabled=true; mfa_device_count=0")
    return (False, "")


def _root_user_used_recently(metadata, tags, resource):
    days = metadata.get("root_user_last_used_days")
    if days is not None and days <= 90:
        return (True, f"root_user_last_used_days={days}")
    return (False, "")


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _matches_all(value):
    return any(str(item).lower() == "*" for item in _as_list(value))


def _policy_allows_full_admin(metadata, tags, resource):
    document = metadata.get("policy_document") or {}
    for statement in _as_list(document.get("Statement")):
        if not isinstance(statement, dict):
            continue
        if str(statement.get("Effect", "")).lower() != "allow":
            continue
        if _matches_all(statement.get("Action")) and _matches_all(statement.get("Resource")):
            return (True, "policy_allows=*; resource=*")
    return (False, "")


def _policy_attached_to_user(metadata, tags, resource):
    user_count = metadata.get("attached_user_count") or 0
    if user_count > 0:
        return (True, f"attached_user_count={user_count}")
    return (False, "")


# --- Evaluator definitions ---

OLD_ACCESS_KEY = Evaluator(
    func=_old_access_key,
    applicable_resource_types=["iam_access_key"],
    description="Active IAM access key is older than 90 days",
)

FIRST_ACCESS_KEY_OLD = Evaluator(
    func=_first_access_key_old,
    applicable_resource_types=["iam_access_key"],
    description="First active IAM access key is older than 90 days",
)

SECOND_ACCESS_KEY_OLD = Evaluator(
    func=_second_access_key_old,
    applicable_resource_types=["iam_access_key"],
    description="Second active IAM access key is older than 90 days",
)

ROOT_MFA_DISABLED = Evaluator(
    func=_root_mfa_disabled,
    applicable_resource_types=["iam_account"],
    description="AWS account root user does not have MFA enabled",
)

ROOT_ACCESS_KEY_PRESENT = Evaluator(
    func=_root_access_key_present,
    applicable_resource_types=["iam_account"],
    description="AWS account root user has access keys",
)

SUPPORT_ROLE_MISSING = Evaluator(
    func=_support_role_missing,
    applicable_resource_types=["iam_account"],
    description="No IAM role with the AWS managed AWSSupportAccess policy was found",
)

PASSWORD_POLICY_MISSING_NUMBER = Evaluator(
    func=_password_policy_missing_number,
    applicable_resource_types=["iam_account"],
    description="IAM account password policy does not require numbers",
)

WEAK_PASSWORD_POLICY = Evaluator(
    func=_weak_password_policy,
    applicable_resource_types=["iam_account"],
    description="IAM account password policy does not meet baseline complexity requirements",
)

CONSOLE_USER_WITHOUT_MFA = Evaluator(
    func=_console_user_without_mfa,
    applicable_resource_types=["iam_user"],
    description="IAM user with console password does not have an MFA device",
)

ROOT_USER_USED_RECENTLY = Evaluator(
    func=_root_user_used_recently,
    applicable_resource_types=["iam_account"],
    description="AWS account root user was used recently",
)

POLICY_ALLOWS_FULL_ADMIN = Evaluator(
    func=_policy_allows_full_admin,
    applicable_resource_types=["iam_policy"],
    description="Customer managed IAM policy allows * actions on * resources",
)

POLICY_ATTACHED_TO_USER = Evaluator(
    func=_policy_attached_to_user,
    applicable_resource_types=["iam_policy"],
    description="Customer managed IAM policy is attached directly to one or more users",
)


# Registry entries: misconfig_id -> Evaluator
IAM_EVALUATORS = {
    # IAM access keys older than 90 days
    "85d589af-ca9b-4cb6-8311-6c9e50da0687": OLD_ACCESS_KEY,
    "8c0a3d78-a5e3-4ac1-a1ca-f25306b46143": OLD_ACCESS_KEY,
    "13bddd8f-7a89-4fa4-8f4e-bce30b3da26c": FIRST_ACCESS_KEY_OLD,
    "299fc2d0-a2f2-4b79-a3d2-2b479b25d07f": SECOND_ACCESS_KEY_OLD,
    # Root account controls
    "314f0d94-7381-454d-915d-45b962d801e3": ROOT_MFA_DISABLED,
    "e53ff93a-a43d-4580-bf17-a915dfeba8ce": ROOT_ACCESS_KEY_PRESENT,
    # Account-level IAM controls
    "07f63c10-f164-4f31-95fb-57c07eb87261": SUPPORT_ROLE_MISSING,
    "f2ee54dd-37e7-4118-80f9-f164d89f3a8f": PASSWORD_POLICY_MISSING_NUMBER,
    "aead0be5-3b3f-4e96-b561-6bafc7162801": WEAK_PASSWORD_POLICY,
    # IAM users with console password but no MFA
    "e3e22326-af1e-4fc5-89e6-757cf12a2f4a": CONSOLE_USER_WITHOUT_MFA,
    # Root account usage
    "50ba9f4d-388d-46dc-9b71-bd7a10c588c5": ROOT_USER_USED_RECENTLY,
    # Customer managed IAM policy hygiene
    "20da6654-9c4a-4b02-aaaf-5327efab6599": POLICY_ALLOWS_FULL_ADMIN,
    "6a285348-b16e-4905-b347-09df596d02d5": POLICY_ATTACHED_TO_USER,
}
