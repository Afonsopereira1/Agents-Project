"""Energia ausente e contagens operacionais preservam o contrato da avaliação."""

from copy import deepcopy
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from isia.evaluation.metrics import run_metrics, summarize

try:
    from isia.evaluation.collector import flat_summary, load_scenario, run_scenario, write_csv
except ImportError:
    run_scenario = None


def report():
    return {
        "ground_truth": {"events": [{"is_threat": True}]},
        "decision": {"decision": "request_mobile_verification"},
        "results": [],
        "initial_resources": [{"resource_id": "drone", "autonomy_percent": 100.0},
                              {"resource_id": "ranger", "autonomy_percent": 100.0}],
        "resources": [{"resource_id": "drone", "autonomy_percent": 94.0},
                      {"resource_id": "ranger", "autonomy_percent": 90.0}],
        "fault_log": [], "messages": [{}, {}],
        "missions": [{"status": "done"}, {"status": "failed"}],
        "incident_status": "closed", "reason": "confirmed",
        "timeline": [{"event": "ALERT", "time": 0.0}],
    }


class TestEnergyAvailability(unittest.TestCase):
    def test_numeric_resources_keep_the_existing_total(self):
        metrics = run_metrics(report())
        self.assertEqual(metrics["energy_used"], 16.0)
        self.assertEqual((metrics["missions_done"], metrics["missions_failed"]), (1, 1))

    def test_unknown_initial_or_final_autonomy_is_not_zero_or_a_partial_total(self):
        expected = run_metrics(report())
        for initial_unknown, final_unknown in ((True, False), (False, True), (True, True)):
            for resource in (0, 1):
                with self.subTest(initial=initial_unknown, final=final_unknown, resource=resource):
                    data = report()
                    if initial_unknown:
                        data["initial_resources"][resource]["autonomy_percent"] = None
                    if final_unknown:
                        data["resources"][resource]["autonomy_percent"] = None
                    metrics = run_metrics(data)
                    self.assertIsNone(metrics["energy_used"])
                    self.assertEqual({k: v for k, v in metrics.items() if k != "energy_used"},
                                     {k: v for k, v in expected.items() if k != "energy_used"})

    def test_summaries_count_only_runs_with_known_total_energy(self):
        unknown = report()
        unknown["resources"][0]["autonomy_percent"] = None
        known_metrics, unknown_metrics = run_metrics(report()), run_metrics(unknown)
        mixed = summarize([known_metrics, unknown_metrics])
        self.assertEqual(mixed["energy_used"],
                         {"n": 1, "mean": 16.0, "median": 16.0, "stdev": None})
        self.assertEqual(mixed["messages_sent"]["n"], 2)
        self.assertEqual(summarize([unknown_metrics])["energy_used"],
                         {"n": 0, "mean": None, "median": None, "stdev": None})

    def test_local_completion_without_received_result_is_not_counted_as_known(self):
        data = report()
        data["missions"] = []
        data["incident_status"] = "unresolved"
        data["reason"] = "mission_result_unknown"
        data["timeline"].append({"event": "MISSION_RESULT", "time": 6,
                                 "resource_id": "vehicle", "mission_id": "mission",
                                 "position": {"x": 3, "y": 2}, "outcome": "confirmed"})
        metrics = run_metrics(data)
        self.assertEqual((metrics["missions_done"], metrics["missions_failed"]), (0, 0))
        self.assertFalse(metrics["confirmed"])
        self.assertTrue(metrics["unresolved"])

    @unittest.skipUnless(run_scenario, "SPADE não está instalado")
    def test_csv_preserves_unavailable_energy_and_valid_sample_count(self):
        unknown = report()
        unknown["resources"][0]["autonomy_percent"] = None
        rows = [run_metrics(report()), run_metrics(unknown)]
        summary = flat_summary("energy", "full", rows)
        with TemporaryDirectory() as directory:
            runs_path, summary_path = Path(directory, "runs.csv"), Path(directory, "summary.csv")
            write_csv(runs_path, rows)
            write_csv(summary_path, [summary])
            with runs_path.open(newline="") as stream:
                stored_rows = list(csv.DictReader(stream))
            with summary_path.open(newline="") as stream:
                [stored_summary] = list(csv.DictReader(stream))
        self.assertEqual([row["energy_used"] for row in stored_rows], ["16.0", "N/A"])
        self.assertEqual(stored_summary["energy_used_n"], "1")
        self.assertEqual(stored_summary["energy_used_mean"], "16.0")
        self.assertEqual(stored_summary["energy_used_median"], "16.0")
        self.assertEqual(stored_summary["energy_used_stdev"], "N/A")


@unittest.skipUnless(run_scenario, "SPADE não está instalado")
class TestUnknownAutonomyExperiment(unittest.IsolatedAsyncioTestCase):
    async def test_accepted_unknown_autonomy_does_not_interrupt_collection(self):
        root = Path(__file__).resolve().parents[2]
        config = deepcopy(load_scenario(root / "config/scenarios/A.json"))
        config["episodes"] = config["episodes"][:1]
        config["resources"]["drone"]["autonomy_percent"] = None
        with TemporaryDirectory() as directory:
            [row] = await run_scenario(config, "full", repetitions=1, output=directory)
            [path] = list(Path(directory).rglob("*.json"))
            stored = json.loads(path.read_text())
        self.assertEqual((row["status"], row["reason"]), ("closed", "confirmed"))
        self.assertEqual(row["first_patrol"], "vehicle")
        self.assertIsNone(row["energy_used"])
        self.assertIsNone(stored["metrics"]["energy_used"])
        self.assertEqual(stored["report"]["reservations"], [None, None, None])
        self.assertEqual(flat_summary("A", "full", [row])["energy_used_n"], 0)


if __name__ == "__main__":
    unittest.main()
