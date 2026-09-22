"""Import synthetic aggregate signals from Audience Swarm Lab."""

from __future__ import annotations

import math
from typing import Any


def import_audience_result(result: Any) -> dict:
    if not isinstance(result, dict) or result.get("evidence_label") != "SYNTHETIC_SCENARIO":
        raise ValueError("audience result must be labeled SYNTHETIC_SCENARIO")
    digest = result.get("scenario_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("audience result needs a scenario digest")
    try:
        baseline = result["arms"]["baseline"]["adoption_share"]["mean"]
        effects = result["paired_effects"]
    except (KeyError, TypeError) as error:
        raise ValueError("audience result lacks adoption summaries") from error
    if not isinstance(baseline, (int, float)) or not math.isfinite(baseline) or not 0 < baseline <= 1:
        raise ValueError("baseline adoption share must be positive")
    lifts = {}
    for name, effect in effects.items():
        if not isinstance(name, str) or not name:
            raise ValueError("audience arm ids must be nonempty strings")
        try:
            difference = effect["adoption_share"]["mean"]
        except (KeyError, TypeError) as error:
            raise ValueError("audience effect lacks adoption share") from error
        if not isinstance(difference, (int, float)) or not math.isfinite(difference):
            raise ValueError("audience effect must be finite")
        lift = difference / baseline
        if not -0.9 <= lift <= 3:
            raise ValueError("relative audience lift is outside the reference model range")
        lifts[name] = lift
    return {
        "source": "audience-swarm-lab",
        "source_scenario_sha256": digest,
        "source_model_version": result.get("model_version", "unknown"),
        "evidence_label": "SYNTHETIC_SCENARIO",
        "relative_demand_lifts": lifts,
        "interpretation": "Relative synthetic adoption effects are used only as what-if demand assumptions, not forecasts or measured causal effects.",
    }
