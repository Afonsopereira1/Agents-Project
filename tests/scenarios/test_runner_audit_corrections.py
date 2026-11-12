"""Regressões dos âmbitos de avaliação e dos prazos públicos do runner."""

import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
from time import monotonic
import unittest

from isia.reasoning.reputation import ReputationBook

try:
    from isia.simulation.runner import run_mvp
except ImportError:
    run_mvp = None


ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(run_mvp, "SPADE não está instalado")
class TestRunnerEvaluationScope(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.settings = json.loads((ROOT / "config/agents.json").read_text())
        self.settings["severity"] = 0.8

    async def test_distinct_runs_learn_without_changing_internal_correlation(self):
        book = ReputationBook()
        first = await run_mvp(response_settings=self.settings, reputation=book, run_id="sample-a")
        second = await run_mvp(response_settings=self.settings, reputation=book, run_id="sample-b")
        replay = await run_mvp(response_settings=self.settings, reputation=book, run_id="sample-a")
        self.assertEqual([r["run_id"] for r in (first, second, replay)],
                         ["sample-a", "sample-b", "sample-a"])
        self.assertEqual(first["reputation_scores"]["sensor-1"], 0.5)
        self.assertEqual(second["reputation_scores"]["sensor-1"], 0.6)
        self.assertEqual(book.score("sensor-1"), 4 / 6)
        self.assertEqual([r["reputation_updates"][0]["reason"] for r in (first, second, replay)],
                         ["grounded_result", "grounded_result", "already_evaluated"])
        self.assertEqual(first["reputation_updates"][0]["event_id"],
                         second["reputation_updates"][0]["event_id"])
        for report in (first, second, replay):
            self.assertEqual(report["incident_status"], "closed")
            self.assertEqual(report["reservations"], [None, None, None])
            self.assertEqual(len(report["results"]), 2)
            for result in report["results"]:
                self.assertIn(result["mission_id"], [mission["mission_id"] for mission in report["missions"]])
                self.assertEqual(result["incident_id"], report["decision"]["incident_id"])

    async def test_default_sample_replay_does_not_inflate_reputation(self):
        book = ReputationBook()
        first = await run_mvp(response_settings=self.settings, reputation=book)
        second = await run_mvp(response_settings=self.settings, reputation=book)
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertEqual(second["reputation_updates"][0]["reason"], "already_evaluated")
        self.assertEqual(book.score("sensor-1"), 0.6)

    async def test_fixed_seed_and_sample_id_preserve_operational_reproduction(self):
        reports = [await run_mvp(response_settings=self.settings, run_id="repeatable-sample")
                   for _ in range(2)]
        self.assertEqual(reports[0]["scenario_seed"], reports[1]["scenario_seed"])
        self.assertEqual(reports[0]["decision"], reports[1]["decision"])
        self.assertEqual(reports[0]["resources"], reports[1]["resources"])
        self.assertEqual(reports[0]["reservations"], reports[1]["reservations"])
        def outcomes(report):
            return [{key: result["payload"][key]
                     for key in ("outcome", "reason", "completed_at", "position", "task", "resource_id")}
                    for result in report["results"]]
        self.assertEqual(outcomes(reports[0]), outcomes(reports[1]))

    async def test_invalid_sample_ids_are_rejected(self):
        for run_id in ("", " ", True, 1):
            with self.subTest(run_id=run_id), self.assertRaises(ValueError):
                await run_mvp(run_id=run_id)


@unittest.skipUnless(run_mvp, "SPADE não está instalado")
class TestRunnerDefaultTimeouts(unittest.IsolatedAsyncioTestCase):
    async def assert_verification_timeout_report(self, faults):
        # Sem patch de prazos: exercita os valores públicos usados pela CLI.
        report = await run_mvp(faults=faults)
        self.assertEqual((report["incident_status"], report["decision"]["reason"]),
                         ("expired", "timeout"))
        self.assertEqual(report["decision"]["decision"], "observe")
        self.assertEqual(report["reason"], "insufficient_corroboration")
        self.assertEqual(report["missions"], [])
        self.assertEqual(report["reservations"], [None, None, None])
        self.assertTrue(report["fault_log"])
        return report

    async def test_lost_verification_request_with_public_defaults(self):
        await self.assert_verification_timeout_report({"drop": ["VERIFY_REQUEST"]})

    async def test_unavailable_peer_with_public_defaults(self):
        await self.assert_verification_timeout_report({"unavailable_agents": ["sensor-peer-mvp"]})

    async def test_total_loss_with_public_defaults(self):
        report = await self.assert_verification_timeout_report({"loss": 1, "seed": 3})
        self.assertEqual((report["faults"]["loss"], report["faults"]["seed"]), (1, 3))

    async def test_explicit_watchdog_still_limits_execution(self):
        started = monotonic()
        with self.assertRaises(TimeoutError):
            await run_mvp(faults={"drop": ["VERIFY_REQUEST"]}, max_seconds=0.02)
        self.assertLess(monotonic() - started, 1.0)

    async def test_cli_total_loss_produces_json_with_public_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "faults.json"
            config.write_text(json.dumps({"loss": 1, "seed": 3}))
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-B", "-m", "isia.simulation.runner", "--faults", str(config),
                "--run-id", "cli-sample",
                cwd=ROOT, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=45)
            finally:
                if process.returncode is None:
                    process.kill()
                    await process.wait()
        self.assertEqual(process.returncode, 0, stderr.decode())
        report = json.loads(stdout)
        self.assertEqual(report["run_id"], "cli-sample")
        self.assertEqual((report["incident_status"], report["decision"]["reason"]),
                         ("expired", "timeout"))
        self.assertEqual(report["reservations"], [None, None, None])
        self.assertTrue(report["fault_log"])
        self.assertNotIn(b"Traceback", stderr)
