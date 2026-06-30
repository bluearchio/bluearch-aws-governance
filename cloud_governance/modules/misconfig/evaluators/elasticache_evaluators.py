"""ElastiCache evaluators for misconfiguration detection."""

from .base import Condition, Evaluator, Operator


# --- Evaluator definitions ---

ON_DEMAND_WITHOUT_RESERVED_NODE = Evaluator(
    conditions=[
        Condition(field="is_on_demand", operator=Operator.IS_TRUE),
    ],
    applicable_resource_types=["elasticache_cluster"],
    description="ElastiCache cluster is running on demand without a matching active reserved node",
)


# Registry entries: misconfig_id -> Evaluator
ELASTICACHE_EVALUATORS = {
    # ElastiCache Reserved Node Optimization
    "6aa5f0f0-2e69-4f2e-82f2-e4110654b102": ON_DEMAND_WITHOUT_RESERVED_NODE,
}
