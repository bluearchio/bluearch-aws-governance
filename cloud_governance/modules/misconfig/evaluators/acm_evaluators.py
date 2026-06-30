"""ACM evaluators for misconfiguration detection."""

from .base import Evaluator


def _certificate_expires_within(days: int):
    def _evaluate(metadata, tags, resource):
        days_until_expiration = metadata.get("days_until_expiration")
        if not isinstance(days_until_expiration, int):
            return (False, "")
        if days_until_expiration <= days:
            return (True, f"days_until_expiration={days_until_expiration}")
        return (False, "")

    return _evaluate


def _rsa_key_smaller_than_2048(metadata, tags, resource):
    key_algorithm = metadata.get("key_algorithm") or ""
    key_size_bits = metadata.get("key_size_bits")
    if str(key_algorithm).startswith("RSA_") and isinstance(key_size_bits, int) and key_size_bits < 2048:
        return (True, f"key_algorithm={key_algorithm}")
    return (False, "")


# --- Evaluator definitions ---

CERTIFICATE_EXPIRES_WITHIN_30_DAYS = Evaluator(
    func=_certificate_expires_within(30),
    applicable_resource_types=["acm_certificate"],
    description="ACM certificate expires within 30 days",
)

CERTIFICATE_EXPIRES_WITHIN_7_DAYS = Evaluator(
    func=_certificate_expires_within(7),
    applicable_resource_types=["acm_certificate"],
    description="ACM certificate expires within 7 days",
)

RSA_KEY_SMALLER_THAN_2048 = Evaluator(
    func=_rsa_key_smaller_than_2048,
    applicable_resource_types=["acm_certificate"],
    description="ACM RSA certificate key size is smaller than 2048 bits",
)


# Registry entries: misconfig_id -> Evaluator
ACM_EVALUATORS = {
    "9be76839-271a-4733-b947-c4c3705da1f5": CERTIFICATE_EXPIRES_WITHIN_30_DAYS,
    "d8163f98-8bb2-4159-bde7-e7668e8ee21d": CERTIFICATE_EXPIRES_WITHIN_7_DAYS,
    "75a780d7-e8f9-4175-bc93-8c5c5039fd4e": RSA_KEY_SMALLER_THAN_2048,
}
