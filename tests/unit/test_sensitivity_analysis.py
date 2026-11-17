"""Análise emparelhada e calibração sem executar qualquer simulação."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from isia.evaluation.metrics import NUMERIC


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("sensitivity_analysis", ROOT / "scripts/analyze_sensitivity.py")
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


def row(seed, episode, *, threat=False, dispatched=False, verification=None, energy=0):
    return {"seed": seed, "repetition": seed - 1000, "episode": episode, "threat": threat,
            "alert": dispatched, "dispatched": dispatched, "confirmed": dispatched,
            "unresolved": False, "scenario": "A", "variant": "full",
            "decision": "request_mobile_verification" if dispatched else None,
            "status": "closed" if dispatched else None, "reason": "confirmed" if dispatched else "no_alert",
            "first_patrol": "vehicle" if dispatched else "N/A", "reputation_sensor_1": 0.6,
            **{name: 0 for name in NUMERIC}, "verification_time": verification,
            "response_time": None, "energy_used": energy}


def summary(rows, parameter="baseline", value="original"):
    return {"batch_id": "batch", "parametro": parameter, "valor": analysis.sensitivity.encoded(value), "cenario": "A",
            **analysis.sensitivity.flat_summary("A", "full", rows), "reputation_updates": 2,
            "reputation_sensor_1_final": 0.6}


class TestSensitivityAnalysis(unittest.TestCase):
    def setUp(self):
        self.baseline = [row(1000, "threat", threat=True, dispatched=True, verification=6, energy=20),
                         row(1000, "empty"), row(1001, "threat", threat=True), row(1001, "empty")]
        self.alternative = deepcopy(self.baseline)

    def compare(self):
        return analysis.compare_group(self.baseline, self.alternative, summary(self.baseline),
                                      summary(self.alternative, "receive_timeout", 0.1), samples=80, seed=17)

    def test_absolute_and_relative_differences_preserve_zero_and_na(self):
        self.assertEqual(analysis.delta(10, 15), (5, 0.5))
        self.assertEqual(analysis.delta(0, 2), (2, None))
        self.assertEqual(analysis.delta(None, 2), (None, None))
        self.assertEqual(analysis.delta(2, None), (None, None))

    def test_classification_is_recomputed_on_all_matched_runs(self):
        self.alternative[2].update(alert=True, dispatched=True, decision="request_mobile_verification")
        compared, effects = self.compare()
        self.assertEqual(compared["delta_TP"], 1)
        self.assertEqual(compared["delta_recall"], 0.5)
        self.assertEqual(compared["relative_recall"], 1)
        self.assertEqual(compared["changed_classification_runs"], 1)
        effect = next(item for item in effects if item["metric"] == "recall")
        self.assertEqual(effect["category"], "classification")
        self.assertEqual(effect["baseline_denominator"], 2)
        self.assertEqual(effect["alternative_denominator"], 2)
        self.assertEqual(effect["n_seed_clusters"], 2)
        self.assertFalse(effect["inferential_interval"])

    def test_operational_times_use_common_pairs_and_report_selection(self):
        self.alternative[0]["verification_time"] = 4
        self.alternative[2]["verification_time"] = 20
        compared, effects = self.compare()
        effect = next(item for item in effects if item["metric"] == "verification_time_mean")
        self.assertEqual((effect["baseline"], effect["alternative"]), (6, 12))
        self.assertEqual(effect["delta_absolute"], 6)
        self.assertEqual((effect["baseline_paired"], effect["alternative_paired"]), (6, 4))
        self.assertEqual(effect["paired_delta"], -2)
        self.assertEqual((effect["baseline_n"], effect["alternative_n"], effect["paired_n"]), (1, 2, 1))
        self.assertEqual(effect["coverage_delta"], 0.25)
        self.assertEqual(effect["interval_target"], "paired_delta")
        self.assertEqual(compared["paired_delta_verification_time"], -2)

    def test_no_eligible_time_pairs_are_not_imputed_zero(self):
        self.alternative[0]["verification_time"] = None
        _, effects = self.compare()
        effect = next(item for item in effects if item["metric"] == "verification_time_mean")
        self.assertEqual(effect["paired_n"], 0)
        self.assertEqual(effect["bootstrap_valid_samples"], 0)
        self.assertIsNone(effect["paired_delta"])
        self.assertIsNone(effect["descriptive_delta_p025"])

    def test_missing_or_duplicate_pairs_and_different_truth_are_rejected(self):
        for changed in (self.alternative[:-1], self.alternative + [self.alternative[0]]):
            with self.assertRaisesRegex(ValueError, "pares únicos"):
                analysis.paired_rows(self.baseline, changed)
        self.alternative[0]["threat"] = False
        with self.assertRaisesRegex(ValueError, "verdade"):
            analysis.paired_rows(self.baseline, self.alternative)

    def test_bootstrap_is_deterministic_and_keeps_seed_episodes_together(self):
        pairs = analysis.paired_rows(self.baseline, self.alternative)
        first = analysis.descriptive_intervals(pairs, samples=30, seed=7)
        second = analysis.descriptive_intervals(pairs, samples=30, seed=7)
        self.assertEqual(first, second)
        self.assertEqual(first["recall"]["descriptive_delta_p025"], 0)
        with self.assertRaises(ValueError):
            analysis.descriptive_intervals(pairs, samples=0, seed=7)
        # Um RNG espião confirma que cada escolha seleciona um bloco com os
        # dois episódios da mesma semente, não uma execução isolada.
        chosen = []

        class Spy:
            def choice(self, blocks):
                chosen.append([(item[0]["seed"], item[0]["episode"]) for item in blocks[0]])
                return blocks[0]

        with patch.object(analysis.random, "Random", return_value=Spy()):
            analysis.descriptive_intervals(pairs, samples=2, seed=7)
        self.assertEqual(chosen, [[(1000, "threat"), (1000, "empty")]] * 4)

    def test_null_probabilities_and_no_predicted_positives_remain_undefined(self):
        before = [row(1000, "threat", threat=True), row(1000, "empty")]
        compared, effects = analysis.compare_group(before, deepcopy(before), summary(before),
                                                   summary(before, "receive_timeout", 0.1), samples=10)
        self.assertIsNone(compared["baseline_precision"])
        self.assertIsNone(compared["delta_precision"])
        effect = next(item for item in effects if item["metric"] == "precision")
        self.assertEqual(effect["bootstrap_valid_samples"], 0)

    def test_patrols_and_reputation_updates_are_reported_separately(self):
        self.alternative[0]["first_patrol"] = "drone"
        before, after = summary(self.baseline), summary(self.alternative, "cost_weights", [0, 1, 0])
        after["reputation_updates"] = 5
        compared, effects = analysis.compare_group(self.baseline, self.alternative, before, after, samples=10)
        self.assertEqual(json.loads(compared["alternative_first_patrol_counts"]), {"drone": 1, "N/A": 3})
        self.assertEqual(compared["delta_reputation_updates"], 3)
        self.assertEqual(compared["changed_metric_runs"], 1)

    def test_override_audit_distinguishes_recorded_settings_from_source_configuration(self):
        report = {"response_settings": {"reputation": {"alpha": 0.5, "beta": 0.5}}, "receive_timeout": 2.0}
        self.assertEqual(analysis.report_application(report, "receive_timeout", 2), ("effective_report_setting", 2))
        self.assertEqual(analysis.report_application(report, "reputation_prior", 0.5)[0], "effective_report_setting")
        self.assertEqual(analysis.report_application(report, "sensor_quality", "noisy"),
                         ("configuration_and_code_provenance", None))
        with self.assertRaises(ValueError):
            analysis.report_application(report, "receive_timeout", 0.1)

    def test_wall_clock_deltas_are_descriptive_without_bootstrap(self):
        before = summary(self.baseline)
        after = summary(self.alternative, "receive_timeout", 2)
        before.update(tempo_real_total_s=0.8, tempo_real_medio_s=0.2)
        after.update(tempo_real_total_s=1.2, tempo_real_medio_s=0.3)
        compared, effects = analysis.compare_group(self.baseline, self.alternative, before, after, samples=5)
        self.assertAlmostEqual(compared["delta_tempo_real_total_s"], 0.4)
        self.assertAlmostEqual(compared["relative_tempo_real_total_s"], 0.5)
        self.assertAlmostEqual(compared["delta_tempo_real_medio_s"], 0.1)
        self.assertAlmostEqual(compared["relative_tempo_real_medio_s"], 0.5)
        for metric in ("tempo_real_total_s", "tempo_real_medio_s"):
            effect = next(item for item in effects if item["metric"] == metric)
            self.assertEqual(effect["category"], "operational")
            self.assertNotIn("interval_method", effect)
            self.assertNotIn("descriptive_delta_p025", effect)
        self.assertTrue(any("tempo real" in note and "sem bootstrap" in note for note in analysis.LIMITATIONS))

    def test_consolidated_csv_tampering_is_detected_before_analysis(self):
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            directory = Path(temporary) / "consolidated"
            source.mkdir()
            directory.mkdir()
            source_manifest = source / "manifest.json"
            source_manifest.write_text("original")
            manifest = {"mode": "consolidation", "status": "complete", "sources": [
                {"path": str(source), "sha256": {"manifest.json": analysis.consolidation._hash(source_manifest)}}]}
            (directory / "manifest.json").write_text(json.dumps(manifest))
            source_manifest.write_text("changed")
            with self.assertRaisesRegex(ValueError, "alterado"):
                analysis.load_consolidated(directory)

    def test_analysis_keeps_each_alternative_with_its_own_batch_baseline_and_never_overwrites(self):
        import csv

        runs, summaries = [], []
        for batch, value, initial_energy, final_energy in (("first", 0.1, 20, 12), ("second", 2, 100, 104)):
            before, after = deepcopy(self.baseline), deepcopy(self.baseline)
            before[0]["energy_used"], after[0]["energy_used"] = initial_energy, final_energy
            for parameter, setting, rows in (("baseline", "original", before), ("receive_timeout", value, after)):
                for record in rows:
                    record.update(batch_id=batch, parametro=parameter, valor=analysis.sensitivity.encoded(setting), cenario="A")
                runs.extend(rows)
                aggregate = summary(rows, parameter, setting)
                aggregate["batch_id"] = batch
                summaries.append(aggregate)
        manifest = {"selection_complete": False}
        with TemporaryDirectory() as temporary:
            source, output_root = Path(temporary) / "source", Path(temporary) / "sensitivity"
            source.mkdir()
            for name in ("manifest.json", "runs.csv", "summary.csv"):
                (source / name).write_text("original")
            with patch.object(analysis, "load_consolidated", return_value=(manifest, runs, summaries)), \
                    patch.object(analysis, "calibration_and_audit", return_value=([], [], [], [], [])), \
                    patch.object(analysis.sensitivity, "OUTPUT_ROOT", output_root):
                output = analysis.analyze(source, run_id="analysis", bootstrap_samples=5)
                with (output / "comparisons.csv").open(newline="") as stream:
                    results = list(csv.DictReader(stream))
                self.assertEqual([float(item["delta_energy_used_mean"]) for item in results], [-2, 1])
                saved = (output / "comparisons.csv").read_bytes()
                with self.assertRaises(FileExistsError):
                    analysis.analyze(source, run_id="analysis", bootstrap_samples=5)
                self.assertEqual((output / "comparisons.csv").read_bytes(), saved)
                state = json.loads((output / "manifest.json").read_text())
                self.assertEqual(state["total_simulations"], 0)
                self.assertFalse(state["bootstrap_inferential"])
                self.assertEqual(state["groups"], 2)


if __name__ == "__main__":
    unittest.main()
