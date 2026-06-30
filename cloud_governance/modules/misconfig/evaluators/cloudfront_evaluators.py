"""CloudFront evaluators for misconfiguration detection."""

from .base import Evaluator


LEGACY_TLS_MINIMUM_PROTOCOLS = {
    "SSLv3",
    "TLSv1",
    "TLSv1_2016",
    "TLSv1.1_2016",
}


def _legacy_tls_minimum_protocol(metadata, tags, resource):
    minimum_protocol_version = metadata.get("minimum_protocol_version")
    if minimum_protocol_version in LEGACY_TLS_MINIMUM_PROTOCOLS:
        return (True, f"minimum_protocol_version={minimum_protocol_version}")
    return (False, "")


def _origin_connection_not_https_only(metadata, tags, resource):
    origins_without_https_only = metadata.get("origins_without_https_only")
    if isinstance(origins_without_https_only, list) and origins_without_https_only:
        origins = ",".join(origins_without_https_only)
        return (True, f"origins_without_https_only={origins}")
    return (False, "")


# --- Evaluator definitions ---

LEGACY_TLS_MINIMUM_PROTOCOL = Evaluator(
    func=_legacy_tls_minimum_protocol,
    applicable_resource_types=["cloudfront_distribution"],
    description="CloudFront distribution allows legacy TLS protocol versions",
)

ORIGIN_CONNECTION_NOT_HTTPS_ONLY = Evaluator(
    func=_origin_connection_not_https_only,
    applicable_resource_types=["cloudfront_distribution"],
    description="CloudFront distribution has a custom origin connection policy other than https-only",
)


# Registry entries: misconfig_id -> Evaluator
CLOUDFRONT_EVALUATORS = {
    "12f2d76b-5c61-403a-bcbe-71c1a4d3ec61": LEGACY_TLS_MINIMUM_PROTOCOL,
    "fa2ba14d-f984-4efb-a5ae-6a7da7f4257a": ORIGIN_CONNECTION_NOT_HTTPS_ONLY,
}
