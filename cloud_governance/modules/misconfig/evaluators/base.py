"""Core evaluator framework for misconfiguration detection.

Provides declarative condition-based evaluation of resource metadata
to determine if a resource has a specific misconfiguration.

Tier 1 (Confirmed): Rules with evaluators check actual metadata.
Tier 2 (Advisory): Rules without evaluators flag all matching resources.
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class Operator(Enum):
    """Comparison operators for condition evaluation."""
    EQ = "eq"
    NE = "ne"
    IS_TRUE = "is_true"
    IS_FALSE = "is_false"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    LT = "lt"
    GT = "gt"
    LTE = "lte"
    GTE = "gte"
    IN = "in_"
    NOT_IN = "not_in"
    STARTS_WITH = "starts_with"
    CONTAINS = "contains"


@dataclass
class Condition:
    """A single declarative check against resource data.

    Attributes:
        field: Dot-separated field path (e.g. 'encrypted', 'volume_type').
        operator: The comparison operator.
        value: Expected value for comparison (unused for IS_TRUE/IS_FALSE/IS_NULL).
        source: Where to look up the field: 'metadata', 'tags', or 'resource'.
    """
    field: str
    operator: Operator
    value: Any = None
    source: str = "metadata"


@dataclass
class Evaluator:
    """Evaluates whether a resource has a specific misconfiguration.

    Can use either declarative conditions or a custom function.

    Attributes:
        conditions: List of declarative conditions to check.
        logic: How to combine conditions - 'all' (AND) or 'any' (OR).
        func: Optional custom evaluation function taking (metadata, tags, resource)
              and returning True if resource FAILS (has misconfiguration).
        applicable_resource_types: Resource types this evaluator applies to.
            If empty, applies to all types matched by the misconfig's service.
        description: Human-readable description of what this evaluator checks.
    """
    conditions: List[Condition] = field(default_factory=list)
    logic: str = "all"
    func: Optional[Callable] = None
    applicable_resource_types: List[str] = field(default_factory=list)
    description: str = ""

    def evaluate(self, resource) -> tuple:
        """Evaluate whether a resource has this misconfiguration.

        Args:
            resource: A Resource ORM object with metadata_json, current_tags, etc.

        Returns:
            Tuple of (failed: bool, details: str).
            failed=True means the resource HAS the misconfiguration.
        """
        try:
            metadata = _parse_metadata(resource.metadata_json)
            tags = resource.current_tags or {}

            if self.func:
                result = self.func(metadata, tags, resource)
                if isinstance(result, tuple):
                    return result
                return (bool(result), "")

            if not self.conditions:
                return (False, "")

            results = []
            detail_parts = []

            for cond in self.conditions:
                passed, detail = _evaluate_condition(cond, metadata, tags, resource)
                results.append(passed)
                if detail:
                    detail_parts.append(detail)

            if self.logic == "any":
                failed = any(results)
            else:
                failed = all(results)

            return (failed, "; ".join(detail_parts))

        except Exception as e:
            logger.debug("Evaluator error for resource %s: %s", getattr(resource, 'id', '?'), e)
            raise


def _parse_metadata(metadata_json) -> Dict[str, Any]:
    """Parse metadata_json which may be a dict or a JSON string."""
    if metadata_json is None:
        return {}
    if isinstance(metadata_json, str):
        try:
            return json.loads(metadata_json)
        except (json.JSONDecodeError, TypeError):
            return {}
    if isinstance(metadata_json, dict):
        return metadata_json
    return {}


def _get_field_value(source: str, field_path: str, metadata: dict, tags: dict, resource) -> Any:
    """Resolve a field value from the specified source."""
    if source == "metadata":
        obj = metadata
    elif source == "tags":
        obj = tags
    elif source == "resource":
        obj = resource
    else:
        obj = metadata

    parts = field_path.split(".")
    current = obj
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif hasattr(current, part):
            current = getattr(current, part)
        else:
            return None
        if current is None:
            return None
    return current


def _evaluate_condition(cond: Condition, metadata: dict, tags: dict, resource) -> tuple:
    """Evaluate a single condition. Returns (failed: bool, detail: str)."""
    actual = _get_field_value(cond.source, cond.field, metadata, tags, resource)

    if cond.operator == Operator.EQ:
        failed = actual == cond.value
        detail = f"{cond.field}={actual}" if failed else ""
    elif cond.operator == Operator.NE:
        failed = actual != cond.value
        detail = f"{cond.field}={actual}" if failed else ""
    elif cond.operator == Operator.IS_TRUE:
        failed = bool(actual) is True
        detail = f"{cond.field}=true" if failed else ""
    elif cond.operator == Operator.IS_FALSE:
        failed = actual is not None and bool(actual) is False
        detail = f"{cond.field}=false" if failed else ""
    elif cond.operator == Operator.IS_NULL:
        failed = actual is None
        detail = f"{cond.field}=null" if failed else ""
    elif cond.operator == Operator.IS_NOT_NULL:
        failed = actual is not None
        detail = f"{cond.field}={actual}" if failed else ""
    elif cond.operator == Operator.LT:
        failed = actual is not None and actual < cond.value
        detail = f"{cond.field}={actual}" if failed else ""
    elif cond.operator == Operator.GT:
        failed = actual is not None and actual > cond.value
        detail = f"{cond.field}={actual}" if failed else ""
    elif cond.operator == Operator.LTE:
        failed = actual is not None and actual <= cond.value
        detail = f"{cond.field}={actual}" if failed else ""
    elif cond.operator == Operator.GTE:
        failed = actual is not None and actual >= cond.value
        detail = f"{cond.field}={actual}" if failed else ""
    elif cond.operator == Operator.IN:
        failed = actual is not None and actual in (cond.value or [])
        detail = f"{cond.field}={actual}" if failed else ""
    elif cond.operator == Operator.NOT_IN:
        failed = actual is not None and actual not in (cond.value or [])
        detail = f"{cond.field}={actual}" if failed else ""
    elif cond.operator == Operator.STARTS_WITH:
        failed = isinstance(actual, str) and actual.startswith(cond.value or "")
        detail = f"{cond.field}={actual}" if failed else ""
    elif cond.operator == Operator.CONTAINS:
        failed = isinstance(actual, str) and (cond.value or "") in actual
        detail = f"{cond.field}={actual}" if failed else ""
    else:
        failed = False
        detail = ""

    return (failed, detail)
