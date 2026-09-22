import copy
import json
import unittest
from pathlib import Path

from decision_world.audience import import_audience_result
from decision_world.contracts import validate
from decision_world.planner import plan


WORLD = json.loads((Path(__file__).resolve().parents[1] / "fixtures/product-launch-world.json").read_text())


class PlannerTests(unittest.TestCase):
    def test_replay_is_exact_and_selects_feasible_plan(self):
        first = plan(WORLD)
        self.assertEqual(first, plan(WORLD))
        self.assertEqual(first["evidence_label"], "SYNTHETIC_SCENARIO")
        selected = next(p for p in first["plans"] if p["plan_id"] == first["selected_plan_id"])
        self.assertTrue(selected["feasible"])
        self.assertEqual(selected["execution_status"], "ADVISORY_ONLY_NOT_AUTHORIZED")

    def test_no_op_is_zero_paired_effect(self):
        world = copy.deepcopy(WORLD)
        world["interventions"] = [{"id": "noop", "demand_lift": 0, "price_delta": 0, "ticket_rate_delta": 0, "support_capacity_delta": 0, "setup_cost": 0, "daily_cost": 0, "required_capability": "demo.none"}]
        world["limits"]["max_interventions"] = 1
        no_op = next(p for p in plan(world)["plans"] if p["plan_id"] == "noop")
        self.assertEqual(no_op["paired_effects"]["net_value"]["mean"], 0)

    def test_budget_and_physical_constraints_are_enforced(self):
        result = plan(WORLD)
        bundle = next(p for p in result["plans"] if p["plan_id"] == "pro-quality+marketing-push")
        self.assertFalse(bundle["feasible"])
        self.assertIn("daily_budget_exceeded", bundle["reasons"])
        world = copy.deepcopy(WORLD)
        world["interventions"][0]["price_delta"] = -60
        bad = next(p for p in plan(world)["plans"] if p["plan_id"] == "basic-discount")
        self.assertIn("nonpositive_price", bad["reasons"])

    def test_contract_rejects_unbounded_world(self):
        world = copy.deepcopy(WORLD)
        world["runs"] = 500
        world["horizon_days"] = 90
        world["interventions"].extend({**WORLD["interventions"][0], "id": f"extra-{index}"} for index in range(4))
        with self.assertRaisesRegex(ValueError, "work budget"):
            validate(world)

    def test_imported_audience_signal_is_labeled_and_reproducible(self):
        source = {
            "evidence_label": "SYNTHETIC_SCENARIO",
            "scenario_sha256": "a" * 64,
            "model_version": "0.1.0",
            "arms": {"baseline": {"adoption_share": {"mean": 0.5}}},
            "paired_effects": {"basic-discount": {"adoption_share": {"mean": 0.02}}},
        }
        signal = import_audience_result(source)
        self.assertAlmostEqual(signal["relative_demand_lifts"]["basic-discount"], 0.04)
        result = plan(WORLD, source)
        self.assertEqual(result["audience_signal"]["source_scenario_sha256"], "a" * 64)
        bad = copy.deepcopy(source)
        bad["evidence_label"] = "ONLINE_EXPERIMENT"
        with self.assertRaisesRegex(ValueError, "SYNTHETIC_SCENARIO"):
            import_audience_result(bad)

    def test_inventory_and_backlog_change_value(self):
        world = copy.deepcopy(WORLD)
        world["baseline"]["inventory"] = 30
        constrained = plan(world)
        base = next(p for p in constrained["plans"] if p["plan_id"] == "baseline")
        self.assertLessEqual(base["outcomes"]["units_sold"]["mean"], 30)
        self.assertGreater(base["outcomes"]["unmet_demand"]["mean"], 0)
        world = copy.deepcopy(WORLD)
        world["baseline"]["support_capacity_per_day"] = 0
        zero_support = plan(world)
        zero_base = next(p for p in zero_support["plans"] if p["plan_id"] == "baseline")
        self.assertGreater(zero_base["outcomes"]["ticket_days"]["mean"], 0)


if __name__ == "__main__":
    unittest.main()
