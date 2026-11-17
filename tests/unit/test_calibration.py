"""A calibração descreve scores iniciais e torna visíveis as exclusões."""

import unittest
from copy import deepcopy

from isia.evaluation.calibration import calibration_tables, initial_score


def record(run_id, score, *, threat=False, scenario="A", variant="full"):
    policy = {"suspicion_score": score, "mission_result": None}
    return {
        "metrics": {"scenario": scenario, "variant": variant},
        "report": {
            "run_id": run_id, "ground_truth": {"events": [{"is_threat": threat}]},
            "decision": {"suspicion_score": 0.99, "mission_result": {"outcome": "confirmed"}},
            "verification": ({"conversation": {"request": {"response_policy": policy}}}
                             if score is not None else {}),
        },
    }


class TestCalibration(unittest.TestCase):
    def test_interval_boundaries_and_frequencies(self):
        bins, coverage = calibration_tables([
            record("zero", 0, threat=True), record("first-upper", 0.25),
            record("middle", 0.5, threat=True), record("last-lower", 0.75),
            record("one", 1, threat=True),
        ])
        self.assertEqual([row["n"] for row in bins], [1, 1, 1, 2])
        self.assertEqual([row["observed_threat_frequency"] for row in bins], [1, 0, 1, 0.5])
        self.assertEqual(bins[-1]["interval"], "[0.75,1.00]")
        self.assertEqual(coverage[0]["score_coverage"], 1)

    def test_initial_score_precedes_mission_and_truth_is_only_from_evaluator(self):
        entry = record("initial", 0.3, threat=False)
        entry["metrics"]["threat"] = True
        self.assertEqual(initial_score(entry["report"]), 0.3)
        bins, _ = calibration_tables([entry])
        self.assertEqual(bins[1]["threats"], 0)
        self.assertEqual(bins[3]["n"], 0)

    def test_missing_scores_are_counted_but_never_imputed_zero(self):
        bins, coverage = calibration_tables([
            record("present", 0.6, threat=True), record("missing-positive", None, threat=True),
            record("missing-negative", None),
        ])
        self.assertEqual(sum(row["n"] for row in bins), 1)
        self.assertIsNone(bins[0]["observed_threat_frequency"])
        self.assertEqual(coverage[0], {
            "scenario": "A", "variant": "full", "parametro": "reference", "valor": "current",
            "n_reports": 3, "n_with_score": 1, "n_without_score": 2,
            "threats_with_score": 1, "threats_without_score": 1, "score_coverage": 1 / 3,
        })

    def test_groups_and_inputs_remain_independent(self):
        first = record("same-id", 0.2)
        second = deepcopy(first)
        second["metrics"].update(parametro="threshold", valor=0.35)
        third = record("other-scenario", 0.7, scenario="B")
        records = [first, second, third]
        original = deepcopy(records)
        bins, coverage = calibration_tables(records)
        self.assertEqual((len(bins), len(coverage)), (12, 3))
        self.assertEqual(records, original)

    def test_duplicate_report_is_rejected(self):
        entry = record("repeated", 0.4)
        with self.assertRaisesRegex(ValueError, "duplicado"):
            calibration_tables([entry, deepcopy(entry)])

    def test_scores_outside_contract_are_rejected(self):
        for invalid in (-0.01, 1.01, float("nan"), float("inf"), True, "0.5"):
            with self.subTest(score=invalid), self.assertRaises(ValueError):
                initial_score(record("invalid", invalid)["report"])

    def test_multiple_initial_scores_and_postmission_score_are_rejected(self):
        report = record("ambiguous", 0.3)["report"]
        report["verification"]["conversation"]["other"] = {"response_policy": {"suspicion_score": 0.5}}
        with self.assertRaisesRegex(ValueError, "Vários scores"):
            initial_score(report)
        report = record("postmission", 0.3)["report"]
        report["verification"]["conversation"]["request"]["response_policy"]["mission_result"] = {}
        with self.assertRaisesRegex(ValueError, "preceder"):
            initial_score(report)

    def test_ground_truth_and_verification_are_required(self):
        for field in ("ground_truth", "verification"):
            entry = record("missing-field", 0.4)
            del entry["report"][field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                calibration_tables([entry])
        entry = record("string-truth", 0.4)
        entry["report"]["ground_truth"]["events"][0]["is_threat"] = "False"
        with self.assertRaisesRegex(ValueError, "booleano"):
            calibration_tables([entry])

    def test_no_reports_produces_no_results(self):
        self.assertEqual(calibration_tables([]), ([], []))


if __name__ == "__main__":
    unittest.main()
