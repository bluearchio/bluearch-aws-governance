"""EMR evaluators for misconfiguration detection."""

from .base import Evaluator


def _task_nodes_not_using_spot(metadata, tags, resource):
    task_capacity = metadata.get("task_capacity") or 0
    task_spot_capacity = metadata.get("task_spot_capacity") or 0
    task_on_demand_capacity = metadata.get("task_on_demand_capacity") or 0
    if task_capacity > 0 and task_spot_capacity == 0 and task_on_demand_capacity > 0:
        return (True, f"task_on_demand_capacity={task_on_demand_capacity}; task_spot_capacity=0")
    return (False, "")


TASK_NODES_NOT_USING_SPOT = Evaluator(
    func=_task_nodes_not_using_spot,
    applicable_resource_types=["emr_cluster"],
    description="EMR task capacity is running on On-Demand instances without Spot task nodes",
)


EMR_EVALUATORS = {
    "2b6ae2c7-d432-401b-8164-23782cb1b1dc": TASK_NODES_NOT_USING_SPOT,
}
