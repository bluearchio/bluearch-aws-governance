"""NAT Gateway and VPC endpoint evaluators for misconfiguration detection."""

from .base import Evaluator


def _inactive_nat_gateway(metadata, tags, resource):
    if metadata.get("state") not in {"available", "pending"}:
        return (False, "")
    route_count = metadata.get("active_route_count")
    if route_count == 0:
        return (True, "active_route_count=0")
    return (False, "")


def _inactive_vpc_endpoint(metadata, tags, resource):
    if metadata.get("state") not in {"available", "pending"}:
        return (False, "")
    association_count = (
        (metadata.get("subnet_count") or 0)
        + (metadata.get("route_table_count") or 0)
        + (metadata.get("network_interface_count") or 0)
    )
    if association_count == 0:
        return (True, "endpoint_association_count=0")
    return (False, "")


def _missing_s3_or_dynamodb_endpoint(metadata, tags, resource):
    if (metadata.get("nat_gateway_count") or 0) == 0:
        return (False, "")
    missing = []
    if metadata.get("has_s3_gateway_endpoint") is False:
        missing.append("s3")
    if metadata.get("has_dynamodb_gateway_endpoint") is False:
        missing.append("dynamodb")
    if missing:
        return (True, f"missing_gateway_endpoints={','.join(missing)}")
    return (False, "")


def _cross_az_nat_gateway_route(metadata, tags, resource):
    count = metadata.get("cross_az_route_count") or 0
    if count > 0:
        return (True, f"cross_az_route_count={count}")
    return (False, "")


INACTIVE_NAT_GATEWAY = Evaluator(
    func=_inactive_nat_gateway,
    applicable_resource_types=["nat_gateway"],
    description="NAT Gateway has no route-table routes pointing to it",
)

INACTIVE_VPC_ENDPOINT = Evaluator(
    func=_inactive_vpc_endpoint,
    applicable_resource_types=["vpc_endpoint"],
    description="VPC endpoint has no subnet, route table, or network interface associations",
)

MISSING_S3_OR_DYNAMODB_ENDPOINT = Evaluator(
    func=_missing_s3_or_dynamodb_endpoint,
    applicable_resource_types=["ec2_vpc"],
    description="VPC has NAT gateways but is missing S3 or DynamoDB gateway endpoints",
)

CROSS_AZ_NAT_GATEWAY_ROUTE = Evaluator(
    func=_cross_az_nat_gateway_route,
    applicable_resource_types=["nat_gateway"],
    description="Route table sends subnet traffic to a NAT Gateway in another Availability Zone",
)


NAT_GATEWAY_EVALUATORS = {
    "c7739001-aa01-4001-b001-001000000001": INACTIVE_NAT_GATEWAY,
    "c7739002-aa02-4002-b002-002000000002": INACTIVE_VPC_ENDPOINT,
    "c8908001-aa03-4003-b003-003000000003": MISSING_S3_OR_DYNAMODB_ENDPOINT,
    "c7739004-aa04-4004-b004-004000000004": CROSS_AZ_NAT_GATEWAY_ROUTE,
    "c7739005-aa05-4005-b005-005000000005": MISSING_S3_OR_DYNAMODB_ENDPOINT,
}
