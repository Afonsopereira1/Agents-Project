"""Consolidação conserva trajetórias completas e identifica a origem de cada linha."""

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from isia.evaluation.metrics import NUMERIC


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("consolidation", ROOT / "scripts/consolidate_sensitivity.py")
consolidation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(consolidation)
sensitivity = consolidation.sensitivity


class TestSensitivityConsolidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provenance = sensitivity.provenance()

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output_root = Path(self.temporary.name) / "sensitivity"
        self.output_root.mkdir()
        self.patch = patch.object(sensitivity, "OUTPUT_ROOT", self.output_root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def fixture(self, name, parameter="receive_timeout", value=0.1, *, scenario="A", baseline_energy=None):
        """Fixtures sintéticas; reutilizar métricas publicadas não executa simulações."""
        directory = self.output_root / name
        directory.mkdir()
        config = sensitivity.load_scenario(ROOT / f"config/scenarios/{scenario}.json")
        plan = sensitivity.plan_experiments([config], [parameter], value)
        stored = [row for row in sensitivity.read_csv(ROOT / "results/experiments/runs.csv")
                  if row["scenario"] == scenario and row["variant"] == "full"]
        rows, summaries = [], []
        for factor, setting in (("baseline", "original"), (parameter, value)):
            group = []
            for record in stored:
                row = dict(record)
                for field in ("threat", "alert", "dispatched", "confirmed", "unresolved"):
                    row[field] = row[field] == "True"
                for field in NUMERIC:
                    row[field] = None if row[field] == "N/A" else float(row[field])
                row.update(parametro=factor, valor=sensitivity.encoded(setting), cenario=scenario)
                group.append(row)
            if factor == "baseline" and baseline_energy is not None:
                group[0]["energy_used"] = baseline_energy
            rows.extend(group)
            summaries.append({"parametro": factor, "valor": sensitivity.encoded(setting), "cenario": scenario,
                              **sensitivity.flat_summary(scenario, "full", group), "repetitions": 20,
                              "seeds": sensitivity.encoded(list(range(1000, 1020))),
                              "episodes": sensitivity.encoded([episode["label"] for episode in config["episodes"]])})
        manifest = {"status": "complete", "variant": "full", "extensions_bloco_f": "disabled",
                    "self_check": {"passed": True}, "provenance": deepcopy(self.provenance),
                    "scenarios": [config], "plan": plan, "repetitions_override": None, "runs": len(rows)}
        sensitivity.write_json(directory / "manifest.json", manifest)
        sensitivity.write_csv(directory / "runs.csv", rows)
        sensitivity.write_csv(directory / "summary.csv", summaries)
        return directory

    def rewrite_manifest(self, directory, changes):
        path = directory / "manifest.json"
        manifest = json.loads(path.read_text())
        changes(manifest)
        path.write_text(json.dumps(manifest))

    def rewrite_csv(self, directory, name, changes):
        path = directory / name
        rows = sensitivity.read_csv(path)
        changes(rows)
        # O teste só substitui a sua fixture temporária.
        import csv
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def test_disjoint_groups_keep_baselines_per_batch_and_never_pool_statistics(self):
        first = self.fixture("first", value=0.1, scenario="C", baseline_energy=100)
        second = self.fixture("second", value=2, scenario="C", baseline_energy=200)
        output = consolidation.consolidate([first, second], "combined")
        rows = sensitivity.read_csv(output / "runs.csv")
        summaries = sensitivity.read_csv(output / "summary.csv")
        self.assertEqual((len(rows), len(summaries)), (160, 4))
        baselines = [row for row in rows if row["parametro"] == "baseline"]
        self.assertEqual(len(baselines), 80)
        self.assertEqual({row["batch_id"] for row in baselines}, {"first", "second"})
        self.assertEqual([row["energy_used"] for row in baselines if row["repetition"] == "0"
                          and row["episode"] == "threat"], ["100", "200"])
        manifest = json.loads((output / "manifest.json").read_text())
        self.assertEqual(manifest["total_simulations"], 0)
        self.assertFalse(manifest["selection_complete"])
        self.assertEqual(len(manifest["missing_groups"]), 73)
        self.assertEqual(manifest["sources"][0]["reports_path"], str(first / "runs"))

    def test_overlapping_alternatives_are_rejected_before_creating_output(self):
        first, second = self.fixture("first"), self.fixture("second")
        with self.assertRaisesRegex(ValueError, "sobreposta"):
            consolidation.consolidate([first, second], "invalid")
        self.assertFalse((self.output_root / "invalid").exists())

    def test_runtime_reference_or_version_mismatch_is_rejected(self):
        first, second = self.fixture("first"), self.fixture("second", value=2)
        original = (second / "manifest.json").read_text()
        for changes in (
            lambda manifest: manifest["provenance"]["sha256"].update({"scripts/sensitivity.py": "different"}),
            lambda manifest: manifest["provenance"]["reference_sha256"].update({"runs.csv": "different"}),
            lambda manifest: manifest["provenance"].update(python="different"),
        ):
            self.rewrite_manifest(second, changes)
            with self.assertRaisesRegex(ValueError, "proveniência incompatível"):
                consolidation.load_batches([first, second])
            (second / "manifest.json").write_text(original)

    def test_incomplete_failed_blocked_or_reference_only_runs_are_not_lots(self):
        first, second = self.fixture("first"), self.fixture("second", value=2)
        original = (second / "manifest.json").read_text()
        for changes in (
            lambda manifest: manifest.update(status="failed"),
            lambda manifest: manifest.update(status="blocked"),
            lambda manifest: manifest["self_check"].update(passed=False),
            lambda manifest: manifest.update(plan=[]),
            lambda manifest: manifest.update(mode="consolidation"),
            lambda manifest: manifest.update(extensions_bloco_f="enabled"),
        ):
            self.rewrite_manifest(second, changes)
            with self.assertRaises(ValueError):
                consolidation.load_batches([first, second])
            (second / "manifest.json").write_text(original)

    def test_reduced_repetition_prefixes_cannot_be_combined_into_full_collection(self):
        first, second = self.fixture("first"), self.fixture("second", value=2)
        self.rewrite_manifest(second, lambda manifest: manifest.update(repetitions_override=1))
        with self.assertRaisesRegex(ValueError, "pilotos"):
            consolidation.load_batches([first, second])

    def test_individual_runs_must_have_original_order_seeds_and_complete_coverage(self):
        first, second = self.fixture("first"), self.fixture("second", value=2)
        original = (second / "runs.csv").read_text()
        for changes in (
            lambda rows: rows.pop(),
            lambda rows: rows.reverse(),
            lambda rows: rows[0].update(seed="9999"),
            lambda rows: rows.__setitem__(1, dict(rows[0])),
        ):
            self.rewrite_csv(second, "runs.csv", changes)
            with self.assertRaisesRegex(ValueError, "incompletas"):
                consolidation.load_batches([first, second])
            (second / "runs.csv").write_text(original)

    def test_summary_must_correspond_to_individual_runs(self):
        first, second = self.fixture("first"), self.fixture("second", value=2)
        self.rewrite_csv(second, "summary.csv", lambda rows: rows[0].update(TP="999"))
        with self.assertRaisesRegex(ValueError, "resumo não corresponde"):
            consolidation.load_batches([first, second])

    def test_source_files_and_existing_consolidation_are_not_overwritten(self):
        first, second = self.fixture("first"), self.fixture("second", value=2)
        before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                  for batch in (first, second) for path in batch.iterdir()}
        output = consolidation.consolidate([first, second], "combined")
        previous = (output / "manifest.json").read_bytes()
        with self.assertRaises(FileExistsError):
            consolidation.consolidate([first, second], "combined")
        self.assertEqual((output / "manifest.json").read_bytes(), previous)
        self.assertEqual(before, {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in before})

    def test_duplicate_folders_nested_paths_and_single_folder_are_rejected(self):
        first, second = self.fixture("first"), self.fixture("second", value=2)
        for paths in ([first], [first, first], [first, second / "nested"]):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                consolidation.load_batches(paths)


if __name__ == "__main__":
    unittest.main()
