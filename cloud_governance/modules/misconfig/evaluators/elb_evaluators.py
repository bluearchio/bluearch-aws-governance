"""ELB/ALB evaluators for misconfiguration detection."""

from .base import Evaluator


WEAK_SSL_POLICY_MARKERS = (
    "2015-05",
    "2016-08",
    "TLS-1-0",
    "TLS-1-1",
)


def _idle_load_balancer(metadata, tags, resource):
    request_count = metadata.get("request_count_7d")
    if request_count is not None and request_count < 700:
        return (True, f"request_count_7d={request_count}")
    return (False, "")


def _no_healthy_targets(metadata, tags, resource):
    registered = metadata.get("registered_target_count")
    healthy = metadata.get("healthy_target_count")
    if registered and registered > 0 and healthy == 0:
        return (True, f"registered_target_count={registered}; healthy_target_count=0")
    return (False, "")


def _no_registered_targets(metadata, tags, resource):
    registered = metadata.get("registered_target_count")
    if registered == 0:
        return (True, "registered_target_count=0")
    return (False, "")


def _unhealthy_targets(metadata, tags, resource):
    unhealthy = metadata.get("unhealthy_target_count") or 0
    if unhealthy > 0:
        return (True, f"unhealthy_target_count={unhealthy}")
    return (False, "")


def _access_logs_disabled(metadata, tags, resource):
    if metadata.get("access_logs_enabled") is False:
        return (True, "access_logs_enabled=false")
    return (False, "")


def _missing_secure_listener(metadata, tags, resource):
    protocols = metadata.get("listener_protocols") or []
    scheme = metadata.get("scheme")
    if scheme == "internet-facing" and not any(protocol in {"HTTPS", "TLS"} for protocol in protocols):
        return (True, f"listener_protocols={','.join(protocols) or 'none'}")
    return (False, "")


def _weak_ssl_policy(metadata, tags, resource):
    policies = metadata.get("listener_ssl_policies") or []
    weak = [
        policy for policy in policies
        if any(marker in policy for marker in WEAK_SSL_POLICY_MARKERS)
    ]
    if weak:
        return (True, f"listener_ssl_policies={','.join(weak)}")
    return (False, "")


def _listener_certificate_expires_within(days: int):
    def _evaluate(metadata, tags, resource):
        expiring = metadata.get(f"listener_certificates_expiring_within_{days}_days")
        if isinstance(expiring, list) and expiring:
            return (True, f"listener_certificate_min_days_until_expiration={metadata.get('listener_certificate_min_days_until_expiration')}")
        return (False, "")

    return _evaluate


# --- Evaluator definitions ---

IDLE_LOAD_BALANCER = Evaluator(
    func=_idle_load_balancer,
    applicable_resource_types=["elb_load_balancer"],
    description="Load balancer has fewer than 100 requests per day over 7 days",
)

NO_HEALTHY_TARGETS = Evaluator(
    func=_no_healthy_targets,
    applicable_resource_types=["elb_load_balancer"],
    description="Load balancer has registered targets but none are healthy",
)

NO_REGISTERED_TARGETS = Evaluator(
    func=_no_registered_targets,
    applicable_resource_types=["elb_load_balancer"],
    description="Load balancer has no registered targets",
)

UNHEALTHY_TARGETS = Evaluator(
    func=_unhealthy_targets,
    applicable_resource_types=["elb_load_balancer"],
    description="Load balancer has targets in an unhealthy state",
)

ACCESS_LOGS_DISABLED = Evaluator(
    func=_access_logs_disabled,
    applicable_resource_types=["elb_load_balancer"],
    description="Load balancer access logs are disabled",
)

MISSING_SECURE_LISTENER = Evaluator(
    func=_missing_secure_listener,
    applicable_resource_types=["elb_load_balancer"],
    description="Internet-facing load balancer has no HTTPS or TLS listener",
)

WEAK_SSL_POLICY = Evaluator(
    func=_weak_ssl_policy,
    applicable_resource_types=["elb_load_balancer"],
    description="Load balancer listener uses a weak SSL policy",
)

LISTENER_CERTIFICATE_EXPIRES_WITHIN_30_DAYS = Evaluator(
    func=_listener_certificate_expires_within(30),
    applicable_resource_types=["elb_load_balancer"],
    description="Load balancer listener certificate expires within 30 days",
)

LISTENER_CERTIFICATE_EXPIRES_WITHIN_7_DAYS = Evaluator(
    func=_listener_certificate_expires_within(7),
    applicable_resource_types=["elb_load_balancer"],
    description="Load balancer listener certificate expires within 7 days",
)


# Registry entries: misconfig_id -> Evaluator
ELB_EVALUATORS = {
    # Idle load balancer by request volume
    "475b24d9-4b5b-4ce4-8161-af25f89bee49": IDLE_LOAD_BALANCER,
    # No healthy or active targets
    "75ba739e-a10d-4233-9d93-233587bf1de5": NO_HEALTHY_TARGETS,
    "f8873ffb-d1ce-44d2-adf9-50148350fc92": NO_REGISTERED_TARGETS,
    "01e58c92-8f90-4ef0-a438-e35bf01ecfd8": UNHEALTHY_TARGETS,
    # TLS/listener/logging controls
    "71534f32-7b63-4d9b-8c41-9328ea305e23": WEAK_SSL_POLICY,
    "00b372b2-8825-4bdf-834f-b10742dc715b": WEAK_SSL_POLICY,
    "8ac617e8-5a7a-4da8-8084-7ef5e5cbc74c": ACCESS_LOGS_DISABLED,
    "b5337466-a827-460e-873e-613c28a101e4": MISSING_SECURE_LISTENER,
    "a3e36ea7-b611-4706-bc1f-40f09a17dc70": LISTENER_CERTIFICATE_EXPIRES_WITHIN_30_DAYS,
    "38ef673f-016f-4b10-ba8c-e0ab9d15494a": LISTENER_CERTIFICATE_EXPIRES_WITHIN_30_DAYS,
    "b70a15dd-4b86-4345-ab46-a3e02c6abfea": LISTENER_CERTIFICATE_EXPIRES_WITHIN_7_DAYS,
    "255365fe-3007-414f-85b6-713846173847": LISTENER_CERTIFICATE_EXPIRES_WITHIN_7_DAYS,
}
