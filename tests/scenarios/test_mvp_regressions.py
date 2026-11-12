"""Regressões de negociação verificadas no ciclo completo do MVP local."""

import copy
import json
import unittest
from unittest.mock import patch

try:
    from isia.agents.incident import IncidentSensorAgent
    from isia.agents.mobile import MobileResourceAgent
    from isia.communication.messages import MessageType
    from isia.simulation.runner import run_mvp
except ImportError:
    run_mvp = None


@unittest.skipUnless(run_mvp, "SPADE não está instalado")
class TestMVPRegressions(unittest.IsolatedAsyncioTestCase):
    def assert_completed_once(self, report):
        self.assertEqual(report["incident_status"], "closed")
        self.assertEqual(report["reason"], "confirmed")
        self.assertEqual([r["source_id"] for r in report["results"]], ["drone", "ranger"])
        self.assertEqual(len(report["missions"]), 2)
        self.assertTrue(all(m["status"] == "done" for m in report["missions"]))
        accepts = [m["body"] for m in report["messages"] if m["body"]["message_type"] == "ACCEPT"]
        self.assertEqual(len(accepts), 2)
        self.assertEqual(len({m["mission_id"] for m in accepts}), 2)
        self.assertEqual(report["reservations"], [None, None, None])
        self.assertTrue(all(r["available"] for r in report["resources"]))
        self.assertEqual([r["autonomy_percent"] for r in report["resources"]], [94, 100, 90])

    async def test_invalid_proposals_before_valid_ones_complete_mvp_once(self):
        original = MobileResourceAgent.ContractNetBehaviour.run

        async def inject_invalid(self):
            send = self.send

            async def send_with_invalid(outgoing):
                body = json.loads(outgoing.body)
                if body["message_type"] == "PROPOSAL":
                    invalid = copy.deepcopy(outgoing)
                    body["payload"]["bid"] = {}
                    invalid.body = json.dumps(body)
                    await send(invalid)
                await send(outgoing)

            self.send = send_with_invalid
            try:
                await original(self)
            finally:
                self.send = send

        with patch.object(MobileResourceAgent.ContractNetBehaviour, "run", inject_invalid):
            report = await run_mvp()
        self.assert_completed_once(report)
        proposals = [m["body"] for m in report["messages"] if m["body"]["message_type"] == "PROPOSAL"]
        self.assertEqual({m["source_id"] for m in proposals if not m["payload"]["bid"]},
                         {"drone", "vehicle", "ranger"})

    async def test_reject_transport_error_preserves_winner_and_closes_mvp(self):
        original = IncidentSensorAgent.IncidentBehaviour.send_body
        failures = []

        async def fail_reject(self, recipient, body, performative, reply_to=None):
            if body.message_type is not MessageType.REJECT:
                return await original(self, recipient, body, performative, reply_to)
            # Falha no transporte real do comportamento, depois de construir o REJECT.
            async def fail_send(message):
                failures.append((recipient, json.loads(message.body)))
                raise OSError("reject transport failure")

            with patch.object(self, "send", fail_send):
                await original(self, recipient, body, performative, reply_to)

        with patch.object(IncidentSensorAgent.IncidentBehaviour, "send_body", fail_reject):
            with self.assertLogs("isia.agents.incident", level="WARNING") as logs:
                report = await run_mvp()
        self.assert_completed_once(report)
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0][0], "vehicle-mvp@localhost")
        self.assertIn("reject transport failure", " ".join(logs.output))
