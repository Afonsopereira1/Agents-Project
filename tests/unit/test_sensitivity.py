"""Contratos experimentais: isolamento de fatores, referências e resultados."""

import csv
import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

from isia.evaluation.metrics import NUMERIC


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("sensitivity", ROOT / "scripts/sensitivity.py")
sensitivity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sensitivity)


def leaf_changes(before, after, prefix=()):
    """Enumerar folhas diferentes, incluindo introdução de opções do runner."""
    if isinstance(before, dict) and isinstance(after, dict):
        return {change for key in before.keys() | after.keys()
                for change in leaf_changes(before.get(key), after.get(key), (*prefix, key))}
    return set() if before == after else {prefix}


class TestSensitivityPlan(unittest.TestCase):
    def setUp(self):
        self.config = sensitivity.load_scenario(ROOT / "config/scenarios/A.json")

    def test_catalog_has_26_alternatives_and_only_unapproved_diversity_is_blocked(self):
        plan = sensitivity.plan_experiments([self.config], list(sensitivity.PARAMETERS))
        self.assertEqual(len(plan), 26)
        self.assertEqual([(item["parametro"], item["valor"]) for item in plan if item["status"] != "ready"],
                         [("source_diversity", 1)])
        self.assertIn("ResponsePolicy", next(item for item in plan if item["status"] == "blocked")["reason"])

    def test_each_alternative_changes_only_the_specified_factor(self):
        expected = {
            "corroboration_distance": {("options", "corroboration_settings")},
            "corroboration_window": {("options", "corroboration_settings")},
            "receive_timeout": {("options", "receive_timeout")},
            "minimum_autonomy": {("options", "minimum_autonomy_percent")},
            "cost_weights": {("options", "selection_weights")},
            "sensor_quality": {("config", "sources", source, field)
                               for source in ("sensor-1", "sensor-2")
                               for field in ("false_positive_rate", "false_negative_rate")},
            "reputation_prior": {("config", "response_settings", "reputation", field) for field in ("alpha", "beta")},
            "patrol_threshold": {("config", "response_settings", "policy", "patrol_threshold")},
            "ranger_threshold": {("config", "response_settings", "policy", "ranger_threshold")},
            "source_diversity": {("config", "response_settings", "policy", field)
                                 for field in ("ranger_min_groups", "ranger_min_modalities")},
            "severity": {("config", "response_settings", "severity")},
            "adjudication_distance": {("config", "response_settings", "adjudication", "max_distance")},
            "adjudication_delay": {("config", "response_settings", "adjudication", "max_delay_seconds")},
        }
        original = deepcopy(self.config)
        for name, spec in sensitivity.PARAMETERS.items():
            for value in spec["alternatives"]:
                if name == "source_diversity" and value == 1:
                    continue
                with self.subTest(parameter=name, value=value):
                    config, options = sensitivity.apply_experiment(self.config, name, value)
                    self.assertEqual(leaf_changes({"config": original, "options": {}},
                                                  {"config": config, "options": options}), expected[name])
                    self.assertEqual(self.config, original)
                    config["sources"]["sensor-1"]["confidence"] = 0.1
                    self.assertEqual(self.config["sources"]["sensor-1"]["confidence"], 0.8)

    def test_seeds_and_episode_order_match_stage9(self):
        [item] = sensitivity.plan_experiments([self.config], ["receive_timeout"], 0.1, 2)
        self.assertEqual(item["seeds"], [1000, 1001])
        self.assertEqual(item["episodes"], ["threat", "empty"])
        self.assertEqual(item["runs"], 4)

    def test_invalid_values_are_rejected_without_boolean_number_equivalence(self):
        cases = (("corroboration_distance", True), ("cost_weights", [False, 1, False]),
                 ("receive_timeout", None), ("receive_timeout", float("nan")),
                 ("receive_timeout", -1), ("unknown", 1))
        for name, value in cases:
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                sensitivity.apply_experiment(self.config, name, value)
        for name, value in cases[:-1]:
            with self.subTest(plan=name, value=value), self.assertRaises(ValueError):
                sensitivity.plan_experiments([self.config], [name], value)

    def test_policy_contract_is_not_relaxed_for_single_source_diversity(self):
        with self.assertRaises(sensitivity.BlockedExperiment):
            sensitivity.apply_experiment(self.config, "source_diversity", 1)
        self.assertEqual(self.config["response_settings"]["policy"]["ranger_min_groups"], 2)

    def test_invalid_configuration_is_labelled(self):
        self.config["response_settings"]["policy"]["ranger_min_modalities"] = 1
        plan = sensitivity.plan_experiments([self.config], ["receive_timeout"])
        self.assertEqual([item["status"] for item in plan], ["invalid", "invalid"])

    def test_cli_rejects_invalid_counts_and_null_values_before_output(self):
        for args in (["--repetitions", "0"], ["--repetitions", "21"],
                     ["--self-check", "full", "--repetitions", "1"],
                     ["--parameter", "corroboration_distance", "--value", "true"],
                     ["--parameter", "corroboration_distance", "--value", "null"],
                     ["--parameter", "cost_weights", "--value", "[false,1,false]"]):
            with self.subTest(args=args), patch.object(sensitivity, "create_output") as output:
                with patch("sys.stderr"), self.assertRaises(SystemExit):
                    sensitivity.main(args)
                output.assert_not_called()


class TestSensitivityFiles(unittest.TestCase):
    def test_exclusive_directories_and_files_preserve_old_results(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "results/sensitivity"
            with patch.object(sensitivity, "OUTPUT_ROOT", root):
                first = sensitivity.create_output("existing")
                (first / "sentinel.txt").write_text("original")
                with self.assertRaises(FileExistsError):
                    sensitivity.create_output("existing")
                self.assertEqual((first / "sentinel.txt").read_text(), "original")
                for name in ("../experiments", "a/b", "..", "."):
                    with self.subTest(name=name), self.assertRaises(ValueError):
                        sensitivity.create_output(name)
                csv_path = first / "runs.csv"
                sensitivity.write_csv(csv_path, [{"a": 1, "b": None}])
                with self.assertRaises(FileExistsError):
                    sensitivity.write_csv(csv_path, [{"a": 2}])
                self.assertEqual(csv_path.read_text(), "a,b\n1,N/A\n")

    def test_symlink_output_cannot_escape_sensitivity(self):
        with TemporaryDirectory() as temporary:
            root, target = Path(temporary) / "sensitivity", Path(temporary) / "experiments"
            target.mkdir()
            root.symlink_to(target, target_is_directory=True)
            with patch.object(sensitivity, "OUTPUT_ROOT", root), self.assertRaises(ValueError):
                sensitivity.create_output("new")
            self.assertEqual(list(target.iterdir()), [])

    def test_comparison_handles_na_rounding_and_reports_different_fields(self):
        expected = [{"id": "1", "bool": "False", "time": "N/A", "score": "0.6"}]
        actual = [{"id": 1, "bool": False, "time": None, "score": 0.6000000000000001}]
        self.assertEqual(sensitivity.compare_rows(actual, expected, identity=("id",)), [])
        actual[0]["bool"] = True
        self.assertEqual(sensitivity.compare_rows(actual, expected, identity=("id",))[0]["field"], "bool")
        with self.assertRaises(ValueError):
            sensitivity.compare_rows(actual * 2, expected, identity=("id",))


class TestSensitivityCollection(unittest.IsolatedAsyncioTestCase):
    async def test_initial_self_check_compares_saved_runs_not_published_mean(self):
        config = sensitivity.load_scenario(ROOT / "config/scenarios/A.json")
        reference = sensitivity.read_csv(ROOT / "results/experiments/runs.csv")
        expected = [row for row in reference if row["scenario"] == "A" and row["variant"] == "full"
                    and row["repetition"] == "0"]
        fake = AsyncMock(return_value=expected)
        with TemporaryDirectory() as temporary, patch.object(sensitivity, "run_scenario", fake):
            result = await sensitivity.self_check("initial", [config], Path(temporary))
            self.assertTrue(result["passed"])
            self.assertEqual(result["run_count"], 2)
            self.assertEqual(result["reference"], "runs.csv")
            self.assertEqual(fake.call_args.kwargs["repetitions"], 1)
            self.assertEqual(fake.call_args.args[0]["episodes"], config["episodes"])

    async def test_full_check_cannot_compare_a_reduced_reference(self):
        config = sensitivity.load_scenario(ROOT / "config/scenarios/A.json")
        config["repetitions"] = 1
        with TemporaryDirectory() as temporary, patch.object(sensitivity, "run_scenario") as run:
            with self.assertRaisesRegex(ValueError, "mesma ordem"):
                await sensitivity.self_check("full", [config], Path(temporary))
            run.assert_not_called()

    async def test_collection_reuses_whole_scenario_and_tags_csv(self):
        config = sensitivity.load_scenario(ROOT / "config/scenarios/A.json")
        plan = sensitivity.plan_experiments([config], ["receive_timeout"], 0.1, 1)
        row = {"scenario": "A", "variant": "full", "repetition": 0, "episode": "threat", "seed": 1000,
               "threat": True, "alert": True, "dispatched": True, "decision": "request_mobile_verification",
               "confirmed": True, "status": "closed", "reason": "confirmed", "unresolved": False,
               "verification_time": 6.0, "response_time": 12.0, "energy_used": 20.0, "messages_sent": 15,
               "messages_lost": 0, "messages_duplicated": 0, "missions_done": 2, "missions_failed": 0,
               "first_patrol": "vehicle", "reputation_sensor_1": 0.6}
        fake = AsyncMock(return_value=[row])
        with TemporaryDirectory() as temporary, patch.object(sensitivity, "run_scenario", fake):
            count = await sensitivity.collect(plan, [config], 1, Path(temporary))
            self.assertEqual(count, 2)
            calls = fake.call_args_list
            self.assertEqual([call.kwargs["runner_options"] for call in calls], [{}, {"receive_timeout": 0.1}])
            self.assertTrue(all(call.args[1] == "full" for call in calls))
            self.assertTrue(all(call.args[0]["episodes"] == config["episodes"] for call in calls))
            with Path(temporary, "runs.csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([(r["parametro"], r["valor"], r["cenario"]) for r in rows],
                             [("baseline", '"original"', "A"), ("receive_timeout", "0.1", "A")])
            summaries = sensitivity.read_csv(Path(temporary, "summary.csv"))
            self.assertEqual(summaries[1]["TP"], "1")
            self.assertEqual(summaries[1]["verification_time_mean"], "6.0")
            self.assertEqual(summaries[1]["seeds"], "[1000]")

    async def test_new_reports_keep_parameter_tags_for_future_calibration(self):
        config = sensitivity.load_scenario(ROOT / "config/scenarios/A.json")
        plan = sensitivity.plan_experiments([config], ["receive_timeout"], 0.1, 1)
        row = {"scenario": "A", "variant": "full", "seed": 1000, "repetition": 0, "episode": "empty",
               "threat": False, "dispatched": False, "confirmed": False, "unresolved": False,
               "reputation_sensor_1": 0.5,
               **{name: 0 for name in NUMERIC}}

        async def stored(config, variant, *, output, **kwargs):
            path = output / "A/full/A-full-000-empty.json"
            path.parent.mkdir(parents=True)
            report = {"run_id": "A-full-000-empty", "verification": {}, "ground_truth": {"events": []},
                      "reason": "no_alert", "incident_status": None, "messages": [], "missions": [],
                      "reputation_updates": []}
            sensitivity.write_json(path, {"metrics": row, "report": report})
            return [row]

        with TemporaryDirectory() as temporary, patch.object(sensitivity, "run_scenario", stored):
            await sensitivity.collect(plan, [config], 1, Path(temporary))
            records = [json.loads(path.read_text()) for path in Path(temporary).glob("runs/**/*.json")]
            self.assertEqual({record["metrics"]["parametro"] for record in records}, {"baseline", "receive_timeout"})
            from isia.evaluation.calibration import calibration_tables
            _, coverage = calibration_tables(records)
            self.assertEqual(len(coverage), 2)

    def test_mismatched_reference_stops_before_any_alternatives(self):
        mismatch = {"passed": False, "run_count": 2, "differences": [{"field": "messages_sent"}]}
        with TemporaryDirectory() as temporary, patch.object(sensitivity, "OUTPUT_ROOT", Path(temporary) / "sensitivity"):
            with patch.object(sensitivity, "self_check", AsyncMock(return_value=mismatch)), \
                    patch.object(sensitivity, "collect", AsyncMock()) as collect:
                result = sensitivity.main(["--parameter", "receive_timeout", "--value", "0.1", "--scenario", "A",
                                           "--repetitions", "1", "--run-id", "mismatch"])
                self.assertEqual(result, 1)
                collect.assert_not_called()
            manifest = json.loads(Path(temporary, "sensitivity/mismatch/manifest.json").read_text())
            self.assertEqual(manifest["status"], "reference_mismatch")
            self.assertEqual(manifest["total_simulations"], 2)

    def test_extra_reputation_count_uses_actual_updated_flag(self):
        report = {"reason": "confirmed", "incident_status": "closed", "messages": [], "missions": [],
                  "reputation_updates": [{"updated": True}, {"updated": False}]}
        self.assertEqual(sensitivity.report_extras([{"report": report}])["reputation_updates"], 1)

    def test_exclusively_blocked_selection_records_failure_without_running_references(self):
        with TemporaryDirectory() as temporary, \
                patch.object(sensitivity, "OUTPUT_ROOT", Path(temporary) / "sensitivity"), \
                patch.object(sensitivity, "self_check", AsyncMock()) as check, \
                patch.object(sensitivity, "collect", AsyncMock()) as collect:
            result = sensitivity.main([
                "--parameter", "source_diversity", "--value", "1", "--run-id", "blocked"])
            self.assertEqual(result, 1)
            check.assert_not_called()
            collect.assert_not_called()
            output = Path(temporary, "sensitivity/blocked")
            self.assertEqual({path.name for path in output.iterdir()}, {"plan.json", "manifest.json"})
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "blocked")
            for key in ("runs", "baseline_runs", "alternative_runs", "total_simulations"):
                self.assertEqual(manifest[key], 0)
            self.assertEqual([item["cenario"] for item in manifest["plan"]], ["A", "B", "C"])
            self.assertTrue(all(item["status"] == "blocked" for item in manifest["plan"]))
            self.assertTrue(all("ResponsePolicy" in item["reason"] for item in manifest["plan"]))

    def test_exclusively_blocked_dry_run_does_not_advertise_a_self_check(self):
        from contextlib import redirect_stdout
        import io

        captured = io.StringIO()
        with redirect_stdout(captured), patch.object(sensitivity, "create_output") as output, \
                patch.object(sensitivity, "self_check", AsyncMock()) as check, \
                patch.object(sensitivity, "collect", AsyncMock()) as collect:
            result = sensitivity.main([
                "--parameter", "source_diversity", "--value", "1", "--dry-run"])
        self.assertEqual(result, 1)
        plan = json.loads(captured.getvalue())
        self.assertEqual(plan["status"], "blocked")
        self.assertIsNone(plan["self_check"])
        output.assert_not_called()
        check.assert_not_called()
        collect.assert_not_called()

    def test_mixed_selection_still_executes_the_valid_alternative(self):
        with TemporaryDirectory() as temporary, \
                patch.object(sensitivity, "OUTPUT_ROOT", Path(temporary) / "sensitivity"), \
                patch.object(sensitivity, "self_check", AsyncMock(return_value={
                    "passed": True, "run_count": 2, "differences": []})) as check, \
                patch.object(sensitivity, "collect", AsyncMock(return_value=4)) as collect:
            result = sensitivity.main([
                "--parameter", "source_diversity", "--scenario", "A", "--repetitions", "1",
                "--run-id", "mixed"])
            self.assertEqual(result, 0)
            check.assert_awaited_once()
            collect.assert_awaited_once()
            self.assertEqual([item["status"] for item in collect.call_args.args[0]], ["blocked", "ready"])
            manifest = json.loads(Path(temporary, "sensitivity/mixed/manifest.json").read_text())
            self.assertEqual(manifest["status"], "complete_with_blocked")
            self.assertEqual((manifest["baseline_runs"], manifest["alternative_runs"]), (2, 2))


if __name__ == "__main__":
    unittest.main()
