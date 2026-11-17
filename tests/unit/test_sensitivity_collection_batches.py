"""O coletor executa apenas lotes em falta e preserva checkpoints de falha."""

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "collection_batches", ROOT / "scripts/collect_sensitivity_batches.py")
collection = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collection)


class TestMissingSensitivityJobs(unittest.TestCase):
    def all_groups(self):
        return {collection._key(parameter, value, scenario)
                for parameter, spec in collection.sensitivity.PARAMETERS.items()
                for value in spec["alternatives"]
                if not (parameter == "source_diversity" and value == 1)
                for scenario in ("A", "B", "C")}

    def test_completed_cost_groups_and_blocked_diversity_are_never_scheduled(self):
        completed = {collection._key("cost_weights", value, scenario)
                     for value in ([0, 1, 0], [1, 1, 5]) for scenario in ("A", "B", "C")}
        signature = {"commit": "same"}
        with patch.object(collection, "load_batches", return_value=([], signature, completed)), \
                patch.object(collection.sensitivity, "provenance", return_value=signature):
            _, _, jobs = collection.missing_jobs(["old-a", "old-b"])
        self.assertEqual(len(jobs), 36)
        self.assertEqual(sum(len(job["values"]) for job in jobs), 69)
        self.assertFalse(any(job["parameter"] == "cost_weights" for job in jobs))
        self.assertEqual([job["values"] for job in jobs if job["parameter"] == "source_diversity"],
                         [[3], [3], [3]])

    def test_partial_configuration_schedules_only_its_missing_value(self):
        remaining = collection._key("corroboration_distance", 1.0, "A")
        completed = self.all_groups() - {remaining}
        signature = {"commit": "same"}
        with patch.object(collection, "load_batches", return_value=([], signature, completed)), \
                patch.object(collection.sensitivity, "provenance", return_value=signature):
            _, _, jobs = collection.missing_jobs(["old-a", "old-b"])
        self.assertEqual(jobs, [{"parameter": "corroboration_distance", "scenario": "A", "values": [1.0]}])

    def test_incompatible_provenance_stops_before_creating_output_or_launching(self):
        with patch.object(collection, "load_batches", return_value=([], {"commit": "old"}, set())), \
                patch.object(collection.sensitivity, "provenance", return_value={"commit": "new"}), \
                patch.object(collection.sensitivity, "create_output") as output, \
                patch.object(collection.subprocess, "run") as process, \
                redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            collection.main(["old-a", "old-b"])
        self.assertEqual(error.exception.code, 2)
        output.assert_not_called()
        process.assert_not_called()


class TestSensitivityBatchCheckpoints(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "sensitivity"
        self.output = self.root / "control"
        self.signature = {"commit": "same"}
        self.batches = [{"path": str(self.root / "existing")}]
        self.jobs = [{"parameter": "corroboration_distance", "scenario": "A", "values": [1.0]},
                     {"parameter": "corroboration_distance", "scenario": "B", "values": [1.0, 5.0]}]
        self.root_patch = patch.object(collection.sensitivity, "OUTPUT_ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def state(self):
        return json.loads((self.output / "collection.json").read_text())

    def missing(self):
        return self.batches, self.signature, deepcopy(self.jobs)

    def test_process_failure_stops_following_jobs_and_persists_the_error(self):
        with patch.object(collection, "missing_jobs", return_value=self.missing()), \
                patch.object(collection.sensitivity, "provenance", return_value=self.signature), \
                patch.object(collection.subprocess, "run", return_value=SimpleNamespace(returncode=7)) as process, \
                patch.object(collection, "validate_batch") as validate, \
                self.assertRaisesRegex(RuntimeError, "código 7"):
            collection.main(["old-a", "old-b", "--run-id", "control"])
        process.assert_called_once()
        validate.assert_not_called()
        state = self.state()
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["jobs"][0]["status"], "failed")
        self.assertEqual(state["jobs"][0]["returncode"], 7)
        self.assertNotIn("command", state["jobs"][1])
        self.assertTrue((self.output / "00.log").exists())
        self.assertFalse((self.output / "01.log").exists())

    def test_one_process_and_validation_per_lot_keep_complete_repetition_defaults(self):
        launches = []

        def process(command, **kwargs):
            state = self.state()
            if launches:
                self.assertEqual(state["jobs"][0]["status"], "complete")
            launches.append(command)
            return SimpleNamespace(returncode=0)

        with patch.object(collection, "missing_jobs", return_value=self.missing()), \
                patch.object(collection.sensitivity, "provenance", return_value=self.signature), \
                patch.object(collection.subprocess, "run", side_effect=process) as processes, \
                patch.object(collection, "validate_batch", return_value={"runs": 80}) as validate, \
                redirect_stdout(io.StringIO()):
            result = collection.main(["old-a", "old-b", "--run-id", "control"])
        self.assertEqual(result, 0)
        self.assertEqual((processes.call_count, validate.call_count), (2, 2))
        self.assertIn("--value", launches[0])
        self.assertEqual(launches[0][-2:], ["--value", "1.0"])
        self.assertNotIn("--value", launches[1])
        self.assertTrue(all("--repetitions" not in command for command in launches))
        self.assertTrue(all(command[1] == str(ROOT / "scripts/sensitivity.py") for command in launches))
        state = self.state()
        self.assertEqual(state["status"], "complete")
        self.assertTrue(all(job["status"] == "complete" for job in state["jobs"]))
        self.assertNotEqual(state["jobs"][0]["output"], state["jobs"][1]["output"])

    def test_validation_failure_preserves_lot_and_prevents_the_next_launch(self):
        with patch.object(collection, "missing_jobs", return_value=self.missing()), \
                patch.object(collection.sensitivity, "provenance", return_value=self.signature), \
                patch.object(collection.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as process, \
                patch.object(collection, "validate_batch", side_effect=ValueError("CSV divergente")), \
                self.assertRaisesRegex(ValueError, "CSV divergente"):
            collection.main(["old-a", "old-b", "--run-id", "control"])
        process.assert_called_once()
        state = self.state()
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["jobs"][0]["status"], "failed")
        self.assertEqual(state["jobs"][0]["returncode"], 0)
        self.assertNotIn("command", state["jobs"][1])

    def test_provenance_change_between_lots_stops_without_launching_the_next(self):
        with patch.object(collection, "missing_jobs", return_value=self.missing()), \
                patch.object(collection.sensitivity, "provenance",
                             side_effect=[self.signature, {"commit": "changed"}]), \
                patch.object(collection.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as process, \
                patch.object(collection, "validate_batch", return_value={"runs": 80}), \
                redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "proveniência mudou"):
            collection.main(["old-a", "old-b", "--run-id", "control"])
        process.assert_called_once()
        state = self.state()
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["jobs"][0]["status"], "complete")
        self.assertNotIn("command", state["jobs"][1])

    def test_existing_output_directory_is_never_reused(self):
        self.output.mkdir(parents=True)
        marker = self.output / "preserve.txt"
        marker.write_text("anterior")
        with patch.object(collection, "missing_jobs", return_value=self.missing()), \
                patch.object(collection.subprocess, "run") as process, \
                redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            collection.main(["old-a", "old-b", "--run-id", "control"])
        self.assertEqual(error.exception.code, 2)
        process.assert_not_called()
        self.assertEqual(marker.read_text(), "anterior")
        self.assertEqual(list(self.output.iterdir()), [marker])

    def test_dry_run_limit_only_describes_selected_jobs_without_writing(self):
        captured = io.StringIO()
        with patch.object(collection, "missing_jobs", return_value=self.missing()), \
                patch.object(collection.sensitivity, "create_output") as output, \
                patch.object(collection.subprocess, "run") as process, redirect_stdout(captured):
            result = collection.main(["old-a", "old-b", "--dry-run", "--limit", "1"])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(captured.getvalue()), self.jobs[:1])
        output.assert_not_called()
        process.assert_not_called()


if __name__ == "__main__":
    unittest.main()
