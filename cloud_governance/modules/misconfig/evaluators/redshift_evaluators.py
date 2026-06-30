"""Redshift evaluators for misconfiguration detection."""

from .base import Evaluator


def _running_cluster_no_connections(metadata, tags, resource):
    if metadata.get("cluster_status") != "available":
        return (False, "")
    connections = metadata.get("database_connections_max_7d")
    if connections == 0:
        return (True, "database_connections_max_7d=0")
    return (False, "")


def _running_cluster_low_cpu(metadata, tags, resource):
    if metadata.get("cluster_status") != "available":
        return (False, "")
    cpu_avg = metadata.get("cpu_avg_7d")
    if cpu_avg is not None and cpu_avg < 5:
        return (True, f"cpu_avg_7d={cpu_avg}")
    return (False, "")


NO_CONNECTIONS = Evaluator(
    func=_running_cluster_no_connections,
    applicable_resource_types=["redshift_cluster"],
    description="Running Redshift cluster has no database connections over seven days",
)

LOW_CPU = Evaluator(
    func=_running_cluster_low_cpu,
    applicable_resource_types=["redshift_cluster"],
    description="Running Redshift cluster has less than five percent average CPU over seven days",
)


REDSHIFT_EVALUATORS = {
    "7d5eed76-e0e9-41d3-98ca-5d1becff0c18": NO_CONNECTIONS,
    "0c1b66db-e282-4fbe-91cb-5c49cc88427a": LOW_CPU,
}
