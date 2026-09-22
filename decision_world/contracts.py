"""Strict, bounded contracts for the product-launch world."""

from __future__ import annotations

import math
from typing import Any

MAX_WORLD_STEPS = 2_000_000


def _object(value: Any, name: str, required: set[str], optional: set[str] = set()) -> dict:
    if not isinstance(value, dict) or required - value.keys() or value.keys() - required - optional:
        raise ValueError(f"{name} has missing or unknown fields")
    return value


def _number(value: Any, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be a finite number between {low} and {high}")
    return float(value)


def _integer(value: Any, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name} must be an integer between {low} and {high}")
    return value


def _id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 100:
        raise ValueError(f"{name} must be a nonempty string of at most 100 characters")
    return value


def validate(raw: Any) -> dict:
    top = {"schema_version", "world_id", "horizon_days", "runs", "seed", "baseline", "interventions", "limits"}
    s = _object(raw, "world", top, {"economics"})
    if s["schema_version"] != "0.1.0":
        raise ValueError("unsupported schema_version")
    _id(s["world_id"], "world_id")
    days = _integer(s["horizon_days"], "horizon_days", 1, 90)
    runs = _integer(s["runs"], "runs", 1, 500)
    _integer(s["seed"], "seed", 0, 2**32 - 1)
    b = _object(s["baseline"], "baseline", {"daily_demand", "demand_volatility", "price", "unit_cost", "inventory", "price_elasticity", "ticket_rate", "support_capacity_per_day", "support_cost_per_slot_day", "backlog_penalty_per_ticket_day", "marketing_cost_per_day"})
    bounds = {
        "daily_demand": (0, 100000), "demand_volatility": (0, 2), "price": (0.01, 100000),
        "unit_cost": (0, 100000), "inventory": (0, 10000000), "price_elasticity": (0, 5),
        "ticket_rate": (0, 1), "support_capacity_per_day": (0, 100000),
        "support_cost_per_slot_day": (0, 10000), "backlog_penalty_per_ticket_day": (0, 10000),
        "marketing_cost_per_day": (0, 1000000),
    }
    for key, (low, high) in bounds.items():
        _number(b[key], key, low, high)
    if b["unit_cost"] > b["price"]:
        raise ValueError("baseline unit_cost exceeds price")
    interventions = s["interventions"]
    if not isinstance(interventions, list) or not 1 <= len(interventions) <= 12:
        raise ValueError("interventions must contain 1-12 entries")
    names: set[str] = set()
    for item in interventions:
        fields = {"id", "demand_lift", "price_delta", "ticket_rate_delta", "support_capacity_delta", "setup_cost", "daily_cost", "required_capability"}
        p = _object(item, "intervention", fields)
        name = _id(p["id"], "intervention.id")
        if name in names or name == "baseline":
            raise ValueError("intervention ids must be unique and not baseline")
        names.add(name)
        _number(p["demand_lift"], "demand_lift", -0.9, 3)
        _number(p["price_delta"], "price_delta", -100000, 100000)
        _number(p["ticket_rate_delta"], "ticket_rate_delta", -1, 1)
        _number(p["support_capacity_delta"], "support_capacity_delta", -100000, 100000)
        _number(p["setup_cost"], "setup_cost", 0, 1000000)
        _number(p["daily_cost"], "daily_cost", 0, 1000000)
        _id(p["required_capability"], "required_capability")
    limits = _object(s["limits"], "limits", {"max_setup_cost", "max_extra_daily_cost", "max_interventions", "risk_weight"})
    _number(limits["max_setup_cost"], "max_setup_cost", 0, 10000000)
    _number(limits["max_extra_daily_cost"], "max_extra_daily_cost", 0, 1000000)
    _integer(limits["max_interventions"], "max_interventions", 1, len(interventions))
    _number(limits["risk_weight"], "risk_weight", 0, 5)
    # Every bundle can be enumerated for this reference engine. Account for
    # each day and each Monte Carlo run before starting work.
    if (2 ** len(interventions)) * days * runs > MAX_WORLD_STEPS:
        raise ValueError("world exceeds work budget")
    if "economics" in s:
        economics = _object(s["economics"], "economics", {"compute_cost_per_1000_world_steps", "storage_cost_per_plan", "operating_allowance_fraction"})
        _number(economics["compute_cost_per_1000_world_steps"], "compute_cost_per_1000_world_steps", 0, 1000)
        _number(economics["storage_cost_per_plan"], "storage_cost_per_plan", 0, 1000)
        _number(economics["operating_allowance_fraction"], "operating_allowance_fraction", 0, 5)
    return s
