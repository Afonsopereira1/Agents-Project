"""Unidades de classificação e compatibilidade dos resultados publicados A–E."""

import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from isia.evaluation.metrics import NUMERIC, run_metrics, summarize
from tests.unit.test_metrics import report

try:
    from isia.evaluation.collector import flat_summary, load_scenario, run_scenario, write_csv
except ImportError:
    run_scenario = None


ROOT = Path(__file__).resolve().parents[2]
CLASSIFICATION = ("TP", "FP", "TN", "FN", "precision", "recall", "fpr", "accuracy")


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def metric_rows(path):
    rows = read_csv(path)
    for row in rows:
        for key in ("threat", "dispatched", "confirmed", "unresolved"):
            row[key] = {"True": True, "False": False}[row[key]]
        for key in NUMERIC:
            row[key] = None if row[key] == "N/A" else float(row[key])
        for key in tuple(row):
            if key == "incidents" or key.startswith("incidents_"):
                row[key] = int(row[key])
    return rows


class TestMultipleInitiatorMetrics(unittest.TestCase):
    def test_secondary_response_does_not_become_a_global_false_negative(self):
        data = report(decision=None)
        data.update(incident_status=None, reason="no_alert", missions=[], results=[])
        data["extra_initiators"] = {"sensor-3": {
            "decision": {"decision": "request_mobile_verification"},
            "incident_status": "closed", "reason": "confirmed",
            "missions": [{"status": "done"}],
            "results": [{"payload": {"task": "verify_incident", "outcome": "confirmed"}}],
        }}
        row = run_metrics(data)
        self.assertTrue(row["threat"])
        self.assertFalse(row["dispatched"])
        self.assertFalse(row["confirmed"])  # Diagnóstico de sensor-1, não de todos.
        self.assertEqual((row["incidents"], row["incidents_closed"]), (1, 1))
        self.assertEqual(row["missions_done"], 0)
        summary = summarize([row])
        self.assertTrue(all(summary[key] is None for key in CLASSIFICATION))
        self.assertEqual(summary["confirmed_runs"], 0)

    def test_closed_not_confirmed_does_not_count_as_confirmation(self):
        data = report(decision=None)
        data.update(incident_status="closed", reason="not_confirmed")
        data["extra_initiators"] = {"sensor-3": {
            "incident_status": None, "reason": "no_alert",
        }}
        row = run_metrics(data)
        self.assertEqual(row["incidents_closed"], 1)
        self.assertFalse(row["confirmed"])
        self.assertEqual(summarize([row])["confirmed_runs"], 0)

    def test_incompatible_units_cannot_be_silently_mixed(self):
        single = run_metrics(report())
        multiple = {**single, "incidents": 1}
        for rows in ([single, multiple], [multiple, single]):
            with self.subTest(rows=rows), self.assertRaisesRegex(ValueError, "unidades"):
                summarize(rows)

    def test_unknown_duplicate_counts_are_not_invented(self):
        row = {**run_metrics(report()), "incidents": 1, "incidents_closed": 1,
               "incidents_expired": 0, "incidents_unresolved": 0}
        self.assertNotIn("incidents_duplicate", summarize([row]))
        self.assertNotIn("incidents_duplicate", summarize([row, {**row, "incidents_duplicate": 2}]))
        self.assertEqual(summarize([{**row, "incidents_duplicate": 2}])["incidents_duplicate"], 2)


@unittest.skipUnless(run_scenario, "SPADE não está instalado")
class TestPublishedMetricSummaries(unittest.TestCase):
    def assert_summary_matches(self, actual, published):
        self.assertEqual(set(actual), set(published))
        for key, value in actual.items():
            with self.subTest(column=key):
                if value is None:
                    self.assertEqual(published[key], "N/A")
                elif isinstance(value, (int, float)):
                    self.assertAlmostEqual(value, float(published[key]))
                else:
                    self.assertEqual(value, published[key])

    def test_all_official_abc_summaries_are_preserved(self):
        folder = ROOT / "results/experiments"
        rows = metric_rows(folder / "runs.csv")
        summaries = read_csv(folder / "summary.csv")
        self.assertEqual((len(rows), len(summaries)), (560, 12))
        for published in summaries:
            scenario, variant = published["scenario"], published["variant"]
            group = [row for row in rows if (row["scenario"], row["variant"]) == (scenario, variant)]
            with self.subTest(scenario=scenario, variant=variant):
                self.assert_summary_matches(flat_summary(scenario, variant, group), published)

    def test_historical_de_schemas_preserve_every_other_metric(self):
        for scenario in ("D", "E"):
            folder = ROOT / f"results/scenario-{scenario.lower()}"
            rows = metric_rows(folder / "runs.csv")
            [published] = read_csv(folder / "summary.csv")
            with self.subTest(scenario=scenario):
                self.assertEqual("incidents_duplicate" in rows[0], scenario == "E")
                actual = flat_summary(scenario, "full", rows)
                self.assertTrue(all(actual[key] is None for key in CLASSIFICATION))
                self.assert_summary_matches(actual, published)

    def test_csv_serializes_all_eight_unavailable_classification_metrics(self):
        rows = metric_rows(ROOT / "results/scenario-d/runs.csv")
        summary = flat_summary("D", "full", rows)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "summary.csv"
            write_csv(path, [summary])
            [stored] = read_csv(path)
        self.assertEqual({key: stored[key] for key in CLASSIFICATION},
                         dict.fromkeys(CLASSIFICATION, "N/A"))
        self.assertEqual(stored["incidents_closed"], "45")


@unittest.skipUnless(run_scenario, "SPADE não está instalado")
class TestSecondaryInitiatorResponse(unittest.IsolatedAsyncioTestCase):
    async def test_real_secondary_agents_respond_without_the_primary(self):
        config = load_scenario(ROOT / "config/scenarios/demo/D.json")
        config["sources"]["sensor-1"]["sensitivity"] = 0.0
        [row] = await run_scenario(config, "full", repetitions=1)
        self.assertTrue(row["threat"])
        self.assertFalse(row["dispatched"])
        self.assertEqual(row["reason"], "no_alert")
        self.assertGreater(row["incidents_closed"], 0)
        self.assertTrue(all(summarize([row])[key] is None for key in CLASSIFICATION))


if __name__ == "__main__":
    unittest.main()
