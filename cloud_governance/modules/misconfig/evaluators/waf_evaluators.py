"""WAF evaluators for misconfiguration detection."""

from .base import Evaluator


def _public_application_missing_waf(metadata, tags, resource):
    resource_type = getattr(resource, "resource_type", "")
    web_acl_attached = metadata.get("web_acl_attached")

    if web_acl_attached is not False:
        return (False, "")

    if resource_type == "AWS::CloudFront::Distribution":
        if metadata.get("enabled") is False:
            return (False, "")
        return (True, "web_acl_attached=false")

    if resource_type.startswith("AWS::ElasticLoadBalancingV2::LoadBalancer"):
        if metadata.get("type") != "application":
            return (False, "")
        if metadata.get("scheme") != "internet-facing":
            return (False, "")
        return (True, "web_acl_attached=false")

    return (False, "")


# --- Evaluator definitions ---

PUBLIC_APPLICATION_MISSING_WAF = Evaluator(
    func=_public_application_missing_waf,
    applicable_resource_types=["cloudfront_distribution", "elb_load_balancer"],
    description="Public CloudFront distributions or internet-facing ALBs do not have AWS WAF protection",
)


# Registry entries: misconfig_id -> Evaluator
WAF_EVALUATORS = {
    "e55a54dd-f7ab-4b75-bac7-8067de64ea1a": PUBLIC_APPLICATION_MISSING_WAF,
}
