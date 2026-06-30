"""Route 53 evaluators for misconfiguration detection."""

from .base import Condition, Evaluator, Operator


CNAME_TO_S3_WEBSITE = Evaluator(
    conditions=[
        Condition(field="cname_to_s3_website", operator=Operator.IS_TRUE),
    ],
    applicable_resource_types=["route53_record_set"],
    description="Route 53 CNAME points to an S3 website endpoint instead of an alias record",
)

CNAME_TO_CLOUDFRONT = Evaluator(
    conditions=[
        Condition(field="cname_to_cloudfront", operator=Operator.IS_TRUE),
    ],
    applicable_resource_types=["route53_record_set"],
    description="Route 53 CNAME points to a CloudFront distribution instead of an alias record",
)

CNAME_TO_ELB = Evaluator(
    conditions=[
        Condition(field="cname_to_elb", operator=Operator.IS_TRUE),
    ],
    applicable_resource_types=["route53_record_set"],
    description="Route 53 CNAME points to an ELB endpoint instead of an alias record",
)


ROUTE53_EVALUATORS = {
    "332b3d41-5118-4fa2-ab98-1b2181c80f84": CNAME_TO_S3_WEBSITE,
    "e39158bd-8550-4a6e-ba9f-6060f584ec73": CNAME_TO_CLOUDFRONT,
    "c5a5b3c1-b229-4839-8c91-63c630ad1fb9": CNAME_TO_ELB,
}
