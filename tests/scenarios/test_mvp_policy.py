"""A Etapa 7 usa a negociação, execução e contratos do MVP existente."""

import json
from pathlib import Path
import unittest
from unittest.mock import patch

from isia.domain.models import Incident, Observation, Position
from isia.reasoning.allocation import MissionRegistry
from isia.reasoning.reputation import EvaluationResult, ReputationBook

try:
    from isia.agents.sensor import SensorAgent
    from isia.simulation.runner import run_mvp
except ImportError:
    run_mvp = None


@unittest.skipUnless(run_mvp, "SPADE não está instalado")
class TestMvpPolicy(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2]
        self.settings = json.loads((root / "config/agents.json").read_text())

    async def test_correlated_sources_observe_without_allocating(self):
        report = await run_mvp(response_settings=self.settings)
        self.assertEqual(report["decision"]["decision"], "observe")
        self.assertEqual(report["decision"]["supporting_group_count"], 1)
        self.assertEqual(report["incident_status"], "expired")
        self.assertEqual(report["missions"], [])
        self.assertFalse(any(m["body"]["message_type"] == "CFP" for m in report["messages"]))

    async def test_severity_uses_existing_patrol_return_and_ranger_cycle(self):
        self.settings["severity"] = 0.8
        report = await run_mvp(response_settings=self.settings)
        self.assertEqual(report["decision"]["decision"], "request_mobile_verification")
        self.assertEqual(report["incident_status"], "closed")
        self.assertEqual([r["source_id"] for r in report["results"]], ["drone", "ranger"])
        self.assertEqual(report["reservations"], [None, None, None])
        self.assertEqual([r["autonomy_percent"] for r in report["resources"]], [94, 100, 90])
        self.assertTrue(all("outcome" in r["payload"] and "finding" not in r["payload"]
                            for r in report["results"]))

    async def test_learned_weights_change_dispatch_without_learning_from_non_detection(self):
        book = ReputationBook()
        for index in range(10):
            for source in self.settings["sources"]:
                obs = Observation(f"past-{source}-{index}", source, "gunshot_like_sound",
                                  Position(2, 2), 0, 0.8)
                incident_id = f"past-incident-{index}"
                result = EvaluationResult(
                    f"assessment-{index}", incident_id, (obs.event_id,), "confirmed",
                    "independent_mission", 1, evidence_ids=(f"inspection-{index}",),
                    evidence_source_ids=("independent-patrol",), final=True, sufficient_coverage=True,
                )
                book.update(obs, incident_id, result)
        before = book.snapshot(self.settings["sources"])
        report = await run_mvp(response_settings=self.settings, reputation=book,
                               inspection_outcomes={"drone": "not_confirmed"})
        self.assertEqual(report["decision"]["decision"], "request_mobile_verification")
        self.assertEqual(report["reason"], "not_confirmed")
        self.assertEqual(len(report["results"]), 1)
        self.assertEqual(report["reputation_scores"], before)
        self.assertEqual(book.snapshot(self.settings["sources"]), before)
        self.assertEqual(len(book.history), 20)

    async def test_ranger_decision_uses_existing_capability_and_dispatches_once(self):
        # A política é testada com evidência diversa em test_policy. Aqui isolamos
        # a ponte da decisão para os agentes reais do MVP (transporte local).
        decision = {"decision": "request_rangers"}
        initial = Observation("alert", "sensor-1", "gunshot_like_sound", Position(2, 2), 0, 1)
        registry = MissionRegistry()
        incident = Incident("incident", (initial,))
        mission = registry.create_from_decision(incident, decision)
        self.assertEqual(mission.required_capability, "incident_response")
        self.assertIs(mission, registry.create_from_decision(incident, decision))

        async def assess(behaviour):
            behaviour.agent.decision = decision

        with patch.object(SensorAgent.VerificationBehaviour, "run", assess):
            report = await run_mvp(response_settings=self.settings)
        self.assertEqual(report["incident_status"], "closed")
        self.assertEqual([r["source_id"] for r in report["results"]], ["ranger"])
        self.assertEqual([m["task"] for m in report["missions"]], ["respond_incident"])
        self.assertEqual(report["reservations"], [None, None, None])


if __name__ == "__main__":
    unittest.main()
