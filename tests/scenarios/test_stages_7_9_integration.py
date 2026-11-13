"""Contratos combinados do runner, da adjudicação e dos cenários parametrizados."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from isia.reasoning.reputation import ReputationBook

try:
    from isia.evaluation.collector import load_scenario, run_scenario
    from isia.simulation.runner import run_mvp
except ImportError:
    run_mvp = None


ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(run_mvp, "SPADE não está instalado")
class TestStagesSevenToNine(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = load_scenario(ROOT / "config/scenarios/A.json")

    def scenario(self, run_id):
        return {
            "run_id": run_id, "seed": 1000, "sources": deepcopy(self.config["sources"]),
            "events": deepcopy(self.config["episodes"][0]["events"]),
            "resources": deepcopy(self.config["resources"]),
        }

    async def test_scenario_identity_scopes_learning_and_preserves_replay(self):
        book = ReputationBook()
        reports = []
        for run_id in ("sample-a", "sample-b", "sample-a"):
            reports.append(await run_mvp(
                scenario=self.scenario(run_id), response_settings=self.config["response_settings"],
                reputation=book,
            ))
        self.assertEqual([r["run_id"] for r in reports], ["sample-a", "sample-b", "sample-a"])
        self.assertEqual([r["reputation_updates"][0]["reason"] for r in reports],
                         ["grounded_result", "grounded_result", "already_evaluated"])
        self.assertEqual(reports[0]["reputation_scores"]["sensor-1"], 0.5)
        self.assertEqual(reports[1]["reputation_scores"]["sensor-1"], 0.6)
        self.assertEqual(book.score("sensor-1"), 4 / 6)
        for report in reports:
            self.assertEqual(report["incident_status"], "closed")
            self.assertEqual(report["reservations"], [None, None, None])
            for update in report["reputation_updates"]:
                self.assertEqual(update["run_id"], report["run_id"])
                self.assertTrue(update["event_id"].startswith(report["run_id"] + "-obs-"))
                self.assertEqual(update["incident_id"], report["decision"]["incident_id"])

    async def test_matching_explicit_identity_keeps_observation_prefix(self):
        scenario = self.scenario("explicit-sample")
        original = deepcopy(scenario)
        report = await run_mvp(
            scenario=scenario, run_id="explicit-sample",
            response_settings=self.config["response_settings"],
        )
        self.assertEqual(scenario, original)
        self.assertEqual(report["run_id"], "explicit-sample")
        self.assertTrue(all(key.startswith("explicit-sample-obs-")
                            for key in report["ground_truth"]["observations"]))

    async def test_conflicting_identities_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "scenario.run_id"):
            await run_mvp(scenario=self.scenario("scenario-sample"), run_id="other-sample")

    async def test_parameterized_resources_and_selection_survive_integration(self):
        scenario = self.scenario("limited-resource")
        scenario["resources"]["drone"]["autonomy_percent"] = 15
        weights = {"energy_weight": 0.0, "load_weight": 0.0}
        report = await run_mvp(
            scenario=scenario, response_settings=self.config["response_settings"],
            selection_weights=weights,
        )
        self.assertEqual(report["selection_weights"], weights)
        self.assertTrue(report["corroborate"])
        self.assertEqual(report["scenario_seed"], 1000)
        self.assertEqual(report["initial_resources"][0]["autonomy_percent"], 15)
        self.assertTrue(any(event["is_threat"] for event in report["ground_truth"]["events"]))
        self.assertEqual([result["source_id"] for result in report["results"]], ["vehicle", "ranger"])
        self.assertEqual(report["resources"][0]["autonomy_percent"], 15)
        self.assertEqual(report["reservations"], [None, None, None])

    async def test_collector_uses_one_identity_for_report_observations_and_evaluation(self):
        with tempfile.TemporaryDirectory() as output:
            rows = await run_scenario(self.config, "full", repetitions=1, output=output)
            files = sorted(Path(output).rglob("*.json"))
            self.assertEqual(len(files), len(rows))
            for path in files:
                data = json.loads(path.read_text())
                report = data["report"]
                self.assertEqual(report["run_id"], path.stem)
                for update in report["reputation_updates"]:
                    self.assertEqual(update["run_id"], path.stem)
                    self.assertTrue(update["event_id"].startswith(path.stem + "-obs-"))


if __name__ == "__main__":
    unittest.main()
