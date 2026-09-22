"""Constrained product-launch intervention search and paired world simulation."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import random
from typing import Any

from .audience import import_audience_result
from .contracts import validate

MODEL_VERSION = "0.1.0"


def _summary(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)

    def quantile(q: float) -> float:
        at = (len(ordered) - 1) * q
        low = int(at)
        fraction = at - low
        return ordered[low] * (1 - fraction) + ordered[min(low + 1, len(ordered) - 1)] * fraction

    return {"mean": sum(values) / len(values), "p05": quantile(0.05), "p95": quantile(0.95)}


def _bundle_parameters(world: dict, actions: tuple[dict, ...], imported: dict[str, float]) -> tuple[dict, list[str]]:
    b = world["baseline"]
    price = b["price"] + sum(a["price_delta"] for a in actions)
    ticket_rate = b["ticket_rate"] + sum(a["ticket_rate_delta"] for a in actions)
    capacity = b["support_capacity_per_day"] + sum(a["support_capacity_delta"] for a in actions)
    setup = sum(a["setup_cost"] for a in actions)
    extra_daily = sum(a["daily_cost"] for a in actions)
    reasons = []
    if setup > world["limits"]["max_setup_cost"]:
        reasons.append("setup_budget_exceeded")
    if extra_daily > world["limits"]["max_extra_daily_cost"]:
        reasons.append("daily_budget_exceeded")
    if price <= 0:
        reasons.append("nonpositive_price")
    if not 0 <= ticket_rate <= 1:
        reasons.append("ticket_rate_out_of_range")
    if capacity < 0:
        reasons.append("negative_support_capacity")
    multiplier = math.prod(1 + imported.get(a["id"], a["demand_lift"]) for a in actions)
    # An imported offer response already includes that arm's price effect.
    # Apply the reference elasticity only to unimported price changes.
    residual_price = b["price"] + sum(a["price_delta"] for a in actions if a["id"] not in imported)
    if residual_price <= 0:
        reasons.append("nonpositive_residual_price")
    elif not reasons:
        multiplier *= (residual_price / b["price"]) ** (-b["price_elasticity"])
    return {"price": price, "ticket_rate": ticket_rate, "capacity": capacity, "setup": setup, "extra_daily": extra_daily, "demand_multiplier": multiplier}, reasons


def _simulate_one(world: dict, params: dict, shocks: list[float]) -> dict[str, float]:
    b = world["baseline"]
    inventory = b["inventory"]
    backlog = 0.0
    sold = 0.0
    unmet = 0.0
    ticket_days = 0.0
    for shock in shocks:
        demand = max(0, round(b["daily_demand"] * params["demand_multiplier"] * shock))
        units = min(demand, inventory)
        inventory -= units
        sold += units
        unmet += demand - units
        backlog = max(0.0, backlog + units * params["ticket_rate"] - params["capacity"])
        ticket_days += backlog
    days = len(shocks)
    contribution = sold * (params["price"] - b["unit_cost"])
    support_cost = days * params["capacity"] * b["support_cost_per_slot_day"]
    marketing_cost = days * b["marketing_cost_per_day"]
    extra_cost = params["setup"] + days * params["extra_daily"]
    backlog_cost = ticket_days * b["backlog_penalty_per_ticket_day"]
    return {
        "units_sold": sold, "unmet_demand": unmet, "ending_backlog": backlog,
        "ticket_days": ticket_days, "gross_contribution": contribution,
        "total_cost": support_cost + marketing_cost + extra_cost + backlog_cost,
        "net_value": contribution - support_cost - marketing_cost - extra_cost - backlog_cost,
    }


def plan(raw: dict, audience_result: dict | None = None) -> dict[str, Any]:
    world = validate(raw)
    digest = hashlib.sha256(json.dumps(world, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    signal = import_audience_result(audience_result) if audience_result is not None else None
    imported = signal["relative_demand_lifts"] if signal else {}
    # Common lognormal shocks give comparable baseline and intervention runs.
    rng = random.Random(world["seed"])
    sigma = world["baseline"]["demand_volatility"]
    shocks = [[rng.lognormvariate(-0.5 * sigma * sigma, sigma) for _ in range(world["horizon_days"])] for _ in range(world["runs"])]
    interventions = world["interventions"]
    bundles = [()] + [part for size in range(1, world["limits"]["max_interventions"] + 1) for part in itertools.combinations(interventions, size)]
    baseline_params, _ = _bundle_parameters(world, (), imported)
    baseline_trials = [_simulate_one(world, baseline_params, series) for series in shocks]
    metrics = ("units_sold", "unmet_demand", "ending_backlog", "ticket_days", "gross_contribution", "total_cost", "net_value")
    plans = []
    evaluated = 0
    for actions in bundles:
        params, reasons = _bundle_parameters(world, actions, imported)
        name = "+".join(a["id"] for a in actions) if actions else "baseline"
        entry: dict[str, Any] = {
            "plan_id": name, "interventions": [a["id"] for a in actions],
            "required_capabilities": sorted({a["required_capability"] for a in actions}),
            "feasible": not reasons, "reasons": reasons,
            "execution_status": "ADVISORY_ONLY_NOT_AUTHORIZED",
        }
        if not reasons:
            trials = baseline_trials if not actions else [_simulate_one(world, params, series) for series in shocks]
            evaluated += 1
            entry["outcomes"] = {metric: _summary([trial[metric] for trial in trials]) for metric in metrics}
            entry["paired_effects"] = {metric: _summary([trial[metric] - base[metric] for trial, base in zip(trials, baseline_trials)]) for metric in ("units_sold", "ending_backlog", "net_value")}
            effect = entry["paired_effects"]["net_value"]
            entry["risk_adjusted_net_lift"] = effect["mean"] - world["limits"]["risk_weight"] * max(0, -effect["p05"])
        plans.append(entry)
    ranked = sorted((p for p in plans if p["feasible"]), key=lambda p: (-p["risk_adjusted_net_lift"], len(p["interventions"]), p["plan_id"]))
    best = ranked[0]
    world_steps = evaluated * world["runs"] * world["horizon_days"]
    cost = None
    if "economics" in world:
        e = world["economics"]
        compute = world_steps / 1000 * e["compute_cost_per_1000_world_steps"]
        direct = compute + len(plans) * e["storage_cost_per_plan"]
        cost = {"currency": "USD", "basis": "illustrative input rates; excludes model providers and human review", "compute": compute, "storage": len(plans) * e["storage_cost_per_plan"], "direct": direct, "with_operating_allowance": direct * (1 + e["operating_allowance_fraction"])}
    return {
        "model_version": MODEL_VERSION, "world_id": world["world_id"], "world_sha256": digest,
        "evidence_label": "SYNTHETIC_SCENARIO", "execution_status": "ADVISORY_ONLY_NOT_AUTHORIZED",
        "runs": world["runs"], "horizon_days": world["horizon_days"], "world_steps": world_steps,
        "audience_signal": signal, "selected_plan_id": best["plan_id"], "plans": plans,
        "cost_estimate": cost,
        "interpretation": "Paired synthetic worlds only. Run quantiles are model spread, not confidence intervals or measured causal effects. Bundled audience lifts assume independent multiplicative effects.",
    }
