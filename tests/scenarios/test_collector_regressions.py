"""Validação de entradas e proveniência antes de escrever resultados experimentais."""

from contextlib import redirect_stderr
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch

try:
    from isia.evaluation import collector
except ImportError:
    collector = None


ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "config/scenarios/A.json"


@unittest.skipUnless(collector, "SPADE não está instalado")
class TestCollectorApiRegressions(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = collector.load_scenario(SCENARIO)
        self.config["repetitions"] = 2
        self.config["episodes"] = [{"label": "quiet", "events": []}]

    async def test_invalid_repetition_override_does_not_run_or_write(self):
        with TemporaryDirectory() as output:
            marker = Path(output, "previous.json")
            marker.write_text("preservar")
            for repetitions in (0, -1, True, False, 1.5, "1"):
                with self.subTest(repetitions=repetitions):
                    with patch.object(collector, "run_mvp", new_callable=AsyncMock) as run:
                        with self.assertRaisesRegex(ValueError, "repetitions"):
                            await collector.run_scenario(
                                self.config, "full", repetitions=repetitions, output=output,
                            )
                        run.assert_not_awaited()
                    self.assertEqual(marker.read_text(), "preservar")
                    self.assertEqual(list(Path(output).iterdir()), [marker])

    async def test_none_and_positive_overrides_preserve_seeds_and_empty_events(self):
        default = await collector.run_scenario(self.config, "full")
        explicit = await collector.run_scenario(self.config, "full", repetitions=1)
        self.assertEqual([row["seed"] for row in default], [1000, 1001])
        self.assertEqual([row["seed"] for row in explicit], [1000])
        for row in default + explicit:
            self.assertFalse(row["threat"] or row["alert"] or row["dispatched"])
            self.assertEqual(row["energy_used"], 0)

    async def test_api_rejects_empty_or_duplicate_identifiers_before_running(self):
        variants = (
            {"scenario_id": ""}, {"scenario_id": " "}, {"scenario_id": 1},
            {"episodes": [{"label": "", "events": []}]},
            {"episodes": [{"label": " ", "events": []}]},
            {"episodes": [{"label": [], "events": []}]},
            {"episodes": [{"label": "same", "events": []},
                          {"label": "same", "events": self.config["episodes"][0]["events"]}]},
        )
        for changes in variants:
            with self.subTest(changes=changes):
                with patch.object(collector, "run_mvp", new_callable=AsyncMock) as run:
                    with self.assertRaises(ValueError):
                        await collector.run_scenario({**self.config, **changes}, "full")
                    run.assert_not_awaited()

    async def test_unknown_api_variant_is_rejected_before_running(self):
        for variant in ("", "Full", "unknown", None, []):
            with self.subTest(variant=variant):
                with patch.object(collector, "run_mvp", new_callable=AsyncMock) as run:
                    with self.assertRaisesRegex(ValueError, "variant"):
                        await collector.run_scenario(self.config, variant)
                    run.assert_not_awaited()

    async def test_valid_episode_names_keep_one_report_per_row(self):
        self.config["repetitions"] = 1
        self.config["episodes"] = [{"label": "quiet+tourist", "events": []},
                                   {"label": "outra janela", "events": []}]
        with TemporaryDirectory() as output:
            rows = await collector.run_scenario(self.config, "full", output=output)
            files = sorted(Path(output, "A", "full").glob("*.json"))
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(files), 2)
            self.assertEqual({json.loads(path.read_text())["metrics"]["episode"] for path in files},
                             {row["episode"] for row in rows})


@unittest.skipUnless(collector, "SPADE não está instalado")
class TestCollectorSelectionAndProvenance(unittest.TestCase):
    def setUp(self):
        self.config = collector.load_scenario(SCENARIO)

    def previous_output(self, output):
        for name in ("runs.csv", "summary.csv", "manifest.json", "runs/A/full/old.json"):
            path = Path(output, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("preservar " + name)
        return {str(path.relative_to(output)): path.read_bytes()
                for path in Path(output).rglob("*") if path.is_file()}

    def assert_selection_rejected(self, argv, output, *, check_provenance=False):
        before = self.previous_output(output)
        with patch.object(sys, "argv", argv), redirect_stderr(io.StringIO()) as errors:
            with patch.object(collector, "git_provenance", wraps=collector.git_provenance) as provenance:
                with self.assertRaises(SystemExit) as raised:
                    collector.main()
                if check_provenance:
                    provenance.assert_not_called()
        self.assertEqual(raised.exception.code, 2)
        self.assertNotIn("Traceback", errors.getvalue())
        after = {str(path.relative_to(output)): path.read_bytes()
                 for path in Path(output).rglob("*") if path.is_file()}
        self.assertEqual(after, before)

    def test_repeated_variants_are_rejected_before_cleanup(self):
        with TemporaryDirectory() as output:
            self.assert_selection_rejected(
                ["collector", str(SCENARIO), "--variants", "full", "full", "--output", output],
                output, check_provenance=True,
            )

    def test_nonpositive_cli_repetitions_are_rejected_before_cleanup(self):
        for repetitions in ("0", "-1"):
            with self.subTest(repetitions=repetitions), TemporaryDirectory() as output:
                self.assert_selection_rejected(
                    ["collector", str(SCENARIO), "--repetitions", repetitions, "--output", output],
                    output, check_provenance=True,
                )

    def test_repeated_scenario_selection_is_rejected_before_cleanup(self):
        with TemporaryDirectory() as output:
            self.assert_selection_rejected(
                ["collector", str(SCENARIO), str(SCENARIO), "--output", output],
                output, check_provenance=True,
            )

    def test_distinct_files_with_same_scenario_id_are_rejected_before_cleanup(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as output:
            duplicate = Path(directory, "duplicate.json")
            duplicate.write_text(json.dumps(self.config))
            self.assert_selection_rejected(
                ["collector", str(SCENARIO), str(duplicate), "--output", output],
                output, check_provenance=True,
            )

    def test_duplicate_episode_labels_are_rejected_by_loader_before_cleanup(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as output:
            malformed = deepcopy(self.config)
            malformed["episodes"][1]["label"] = malformed["episodes"][0]["label"]
            path = Path(directory, "duplicate-episodes.json")
            path.write_text(json.dumps(malformed))
            self.assert_selection_rejected(
                ["collector", str(path), "--output", output], output, check_provenance=True,
            )

    def test_git_failure_is_reported_before_cleanup(self):
        with TemporaryDirectory() as output:
            failure = subprocess.CalledProcessError(128, ["git", "rev-parse", "HEAD"])
            with patch.object(collector.subprocess, "run", side_effect=failure):
                self.assert_selection_rejected(
                    ["collector", str(SCENARIO), "--output", output], output,
                )

    def test_cli_from_other_directory_reports_code_repository(self):
        expected_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        ).strip()
        expected_dirty = bool(subprocess.check_output(
            ["git", "status", "--porcelain", "--", "src", "config"], cwd=ROOT, text=True,
        ).strip())
        with TemporaryDirectory() as caller, TemporaryDirectory() as output:
            result = subprocess.run(
                [sys.executable, "-B", "-m", "isia.evaluation.collector", str(SCENARIO),
                 "--variants", "full", "--repetitions", "1", "--output", output],
                cwd=caller, capture_output=True, text=True, timeout=30,
                env={**os.environ, "PYTHONPATH": str(ROOT / "src"),
                     "PYTHONDONTWRITEBYTECODE": "1", "GIT_OPTIONAL_LOCKS": "0"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads(Path(output, "manifest.json").read_text())
            self.assertEqual(manifest["commit"], expected_commit)
            self.assertEqual(manifest["dirty"], expected_dirty)
            self.assertEqual(manifest["runs"], 2)
            self.assertEqual(len(list(Path(output, "runs").rglob("*.json"))), 2)


if __name__ == "__main__":
    unittest.main()
