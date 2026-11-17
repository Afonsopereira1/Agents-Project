"""A referência completa exige igualdade individual e agregada, sem simular."""

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("sensitivity_full_check", ROOT / "scripts/sensitivity.py")
sensitivity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sensitivity)


def typed_row(row):
    """Reconstruir os tipos que run_scenario devolve a partir do CSV publicado."""
    result = {}
    for name, value in row.items():
        if value == "N/A":
            result[name] = None
        elif value in ("True", "False"):
            result[name] = value == "True"
        else:
            try:
                result[name] = json.loads(value)
            except json.JSONDecodeError:
                result[name] = value
    return result


class TestSensitivityFullCheck(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.configs = [sensitivity.load_scenario(ROOT / f"config/scenarios/{name}.json")
                        for name in ("A", "B", "C")]
        self.rows = [typed_row(row) for row in sensitivity.read_csv(ROOT / "results/experiments/runs.csv")
                     if row["variant"] == "full"]

    def mocked_scenarios(self, rows):
        async def simulate(config, variant, *, repetitions, output):
            self.assertEqual(variant, "full")
            self.assertIsNone(repetitions)
            return deepcopy([row for row in rows if row["scenario"] == config["scenario_id"]])
        return AsyncMock(side_effect=simulate)

    async def check(self, rows, *, configs=None):
        fake = self.mocked_scenarios(rows)
        with TemporaryDirectory() as temporary, patch.object(sensitivity, "run_scenario", fake):
            result = await sensitivity.self_check("full", configs or self.configs, Path(temporary))
            individual = sensitivity.read_csv(Path(temporary, "actual-runs.csv"))
            aggregated = sensitivity.read_csv(Path(temporary, "actual.csv"))
            persisted = json.loads(Path(temporary, "comparison.json").read_text())
        self.assertEqual(persisted["passed"], result["passed"])
        return result, individual, aggregated, fake

    async def test_full_reference_compares_all_140_runs_and_three_summaries(self):
        result, individual, aggregated, fake = await self.check(self.rows)
        self.assertTrue(result["passed"])
        self.assertEqual(result["run_count"], 140)
        self.assertEqual(result["compared_rows"], 3)
        self.assertEqual(result["run_comparison"]["compared_rows"], 140)
        self.assertEqual(result["summary_comparison"]["compared_rows"], 3)
        self.assertEqual(result["references"], ["runs.csv", "summary.csv"])
        self.assertEqual(result["differences"], [])
        self.assertEqual((len(individual), len(aggregated)), (140, 3))
        self.assertEqual([call.args[0]["scenario_id"] for call in fake.call_args_list], ["A", "B", "C"])
        self.assertEqual([row["episode"] for row in individual[:4]], ["threat", "empty", "threat", "empty"])
        self.assertEqual([row["seed"] for row in individual[:4]], ["1000", "1000", "1001", "1001"])

    async def test_equal_aggregates_do_not_hide_swapped_individual_measurements(self):
        changed = deepcopy(self.rows)
        changed[0]["messages_sent"], changed[1]["messages_sent"] = (
            changed[1]["messages_sent"], changed[0]["messages_sent"])
        result, _, _, _ = await self.check(changed)
        self.assertFalse(result["passed"])
        self.assertTrue(result["summary_comparison"]["passed"])
        self.assertFalse(result["run_comparison"]["passed"])
        differences = result["run_comparison"]["differences"]
        self.assertEqual([item["field"] for item in differences], ["messages_sent", "messages_sent"])
        self.assertTrue(all(item["level"] == "runs" for item in result["differences"]))

    async def test_patrol_and_reputation_are_compared_even_without_summary_columns(self):
        for field, value in (("first_patrol", "drone"), ("reputation_sensor_1", 0.5)):
            changed = deepcopy(self.rows)
            changed[0][field] = value
            with self.subTest(field=field):
                result, _, _, _ = await self.check(changed)
                self.assertFalse(result["passed"])
                self.assertTrue(result["summary_comparison"]["passed"])
                self.assertEqual(result["run_comparison"]["differences"][0]["field"], field)

    async def test_wrong_execution_order_is_not_hidden_by_identity_matching(self):
        changed = deepcopy(self.rows)
        changed[0], changed[1] = changed[1], changed[0]
        result, _, _, _ = await self.check(changed)
        self.assertFalse(result["passed"])
        self.assertTrue(result["summary_comparison"]["passed"])
        self.assertEqual([item["field"] for item in result["run_comparison"]["differences"]],
                         ["execution_order"])

    async def test_wrong_seed_is_reported_even_if_metrics_aggregate_identically(self):
        changed = deepcopy(self.rows)
        changed[0]["seed"] = 2000
        result, _, _, _ = await self.check(changed)
        self.assertFalse(result["passed"])
        self.assertTrue(result["summary_comparison"]["passed"])
        self.assertIn("row", [item["field"] for item in result["run_comparison"]["differences"]])

    async def test_equal_individual_runs_do_not_hide_an_aggregate_difference(self):
        original_summary = sensitivity.flat_summary

        def wrong_summary(scenario, variant, rows):
            summary = original_summary(scenario, variant, rows)
            if scenario == "A":
                summary["energy_used_mean"] += 1
            return summary

        with patch.object(sensitivity, "flat_summary", wrong_summary):
            result, _, _, _ = await self.check(self.rows)
        self.assertFalse(result["passed"])
        self.assertTrue(result["run_comparison"]["passed"])
        self.assertFalse(result["summary_comparison"]["passed"])
        self.assertEqual(result["differences"][0]["level"], "summary")

    async def test_selected_scenarios_keep_their_full_sequences_in_requested_order(self):
        result, individual, aggregated, fake = await self.check(
            self.rows, configs=[self.configs[2], self.configs[0]])
        self.assertTrue(result["passed"])
        self.assertEqual(result["run_count"], 80)
        self.assertEqual(result["compared_rows"], 2)
        self.assertEqual([call.args[0]["scenario_id"] for call in fake.call_args_list], ["C", "A"])
        self.assertEqual([row["scenario"] for row in aggregated], ["C", "A"])
        self.assertEqual((individual[0]["scenario"], individual[40]["scenario"]), ("C", "A"))

    async def test_reference_seed_mismatch_is_rejected_before_running(self):
        self.configs[0]["base_seed"] = 1001
        with TemporaryDirectory() as temporary, patch.object(sensitivity, "run_scenario", AsyncMock()) as run:
            with self.assertRaisesRegex(ValueError, "mesma ordem"):
                await sensitivity.self_check("full", self.configs, Path(temporary))
            run.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
