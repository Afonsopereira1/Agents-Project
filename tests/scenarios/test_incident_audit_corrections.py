"""Regressões das ações e dos resultados fora de ordem do coordenador local."""

import asyncio
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from isia.communication.messages import Message, MessageType
from isia.domain.models import Mission, Position, ResourceState
from isia.reasoning.allocation import (
    LocalResourceReservation, build_reservation_status_message, evaluate_cfp,
)

try:
    from isia.agents.incident import IncidentSensorAgent
    from isia.agents.sensor import SensorAgent
    from isia.communication.transport import build_spade_message, parse_spade_message
    from isia.simulation.runner import run_mvp
except ImportError:
    IncidentSensorAgent = run_mvp = None


@unittest.skipUnless(run_mvp, "SPADE não está instalado")
class TestIncidentWithoutMission(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2]
        self.settings = json.loads((root / "config/agents.json").read_text())

    def assert_no_assignment(self, report):
        self.assertEqual(report["missions"], [])
        self.assertEqual(report["results"], [])
        self.assertEqual(report["reservations"], [None, None, None])
        self.assertFalse(any(m["body"]["message_type"] == "CFP" for m in report["messages"]))

    async def test_close_claimed_by_a_decision_dict_never_closes_the_incident(self):
        # Nada produz «close»: um dicionário que o afirme não fecha a ocorrência nem pede recursos.
        async def assess(behaviour):
            behaviour.agent.decision = {"decision": "close", "reason": "independent_mission_refuted"}

        with patch.object(SensorAgent.VerificationBehaviour, "run", assess):
            report = await run_mvp(response_settings=self.settings)
        self.assertEqual((report["incident_status"], report["reason"]),
                         ("expired", "insufficient_corroboration"))
        self.assert_no_assignment(report)

    async def test_observe_keeps_single_window_expiration(self):
        report = await run_mvp(response_settings=self.settings)
        self.assertEqual((report["incident_status"], report["reason"]),
                         ("expired", "insufficient_corroboration"))
        self.assertEqual(report["decision"]["decision"], "observe")
        self.assert_no_assignment(report)


@unittest.skipUnless(IncidentSensorAgent, "SPADE não está instalado")
class TestEarlyMissionResults(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.agent = IncidentSensorAgent("sensor@localhost", "test", "peer@localhost")
        self.agent.configure_mvp({}, {}, receive_timeout=0.02)
        self.agent.simulated_time = 20
        self.behaviour = self.agent.IncidentBehaviour()
        self.behaviour.set_agent(self.agent)
        self.mission = Mission("mission", "incident", "verify_incident", Position(1, 0),
                               "mobile_verification", 0)
        self.reservation = LocalResourceReservation(
            ResourceState("drone", "drone", Position(0, 0), True, 100))
        self.on_accept = lambda accept, status: (self.result(accept), status)

        async def send(outgoing):
            body = parse_spade_message(outgoing, expected_protocol="contract-net")
            if body.message_type is MessageType.CFP:
                proposal = evaluate_cfp(
                    body, self.reservation.resource_state, ("mobile_verification",),
                    current_time=20, minimum_autonomy_percent=0, eta_seconds=1,
                    energy_cost_percent=2, load=0,
                )
                self.behaviour.queue.put_nowait(self.wire(proposal, body.message_id, "propose"))
            elif body.message_type is MessageType.ACCEPT:
                status = build_reservation_status_message(
                    body, self.reservation.reserve(body.mission_id),
                    resource_id="drone", created_at=20,
                )
                for incoming in self.on_accept(body, self.wire(status, body.message_id)):
                    self.behaviour.queue.put_nowait(incoming)

        self.behaviour.send = send

    def wire(self, body, reply_to, performative="inform"):
        incoming = build_spade_message(
            str(self.agent.jid), body, performative=performative,
            conversation_id=body.conversation_id, in_reply_to=reply_to, protocol="contract-net",
        )
        incoming.sender = "drone@localhost"
        return incoming

    def result(self, accept, *, identifier="result", changes=None):
        data = dict(
            message_id=identifier, message_type=MessageType.MISSION_RESULT, created_at=20,
            payload={"outcome": "confirmed", "reason": "local_inspection", "completed_at": 20,
                     "position": {"x": 1, "y": 0}, "task": self.mission.task,
                     "resource_id": "drone", "accept_message_id": accept.message_id},
            incident_id=accept.incident_id, mission_id=accept.mission_id,
            conversation_id=accept.conversation_id, source_id="drone",
        )
        if changes:
            data.update({key: value for key, value in changes.items() if key != "payload"})
            data["payload"].update(changes.get("payload", {}))
        return self.wire(Message(**data), accept.message_id)

    async def allocate(self):
        return await self.behaviour.allocate(self.mission, {"drone@localhost": "drone"}, 1)

    async def test_early_result_is_applied_only_after_valid_confirmation_and_once(self):
        assignment, failure = await self.allocate()
        self.assertIsNone(failure)
        self.assertEqual(self.agent.results, [])
        result = await self.behaviour.mission_result(assignment, self.mission)
        self.assertEqual(result.message_id, "result")
        self.assertEqual(self.agent.results, [result])
        self.assertIsNone(self.behaviour._pending_mission_result)

    async def test_normal_status_then_result_still_works(self):
        self.on_accept = lambda accept, status: (status, self.result(accept))
        assignment, failure = await self.allocate()
        self.assertIsNone(failure)
        self.assertIsNone(self.behaviour._pending_mission_result)
        result = await self.behaviour.mission_result(assignment, self.mission)
        self.assertEqual(self.agent.results, [result])

    async def test_foreign_or_invalid_early_result_does_not_replace_valid_result(self):
        variants = (
            {"mission_id": "other-mission"}, {"incident_id": "other-incident"},
            {"conversation_id": "other-conversation"},
            {"source_id": "vehicle", "payload": {"resource_id": "vehicle"}},
            {"payload": {"accept_message_id": "other-accept"}},
            {"payload": {"task": "respond_incident"}},
            {"created_at": 19, "payload": {"completed_at": 19}},
            {"created_at": 21},
        )
        for changes in variants:
            with self.subTest(changes=changes):
                self.setUp()
                self.on_accept = lambda accept, status: (
                    self.result(accept, identifier="foreign", changes=changes),
                    self.result(accept), status,
                )
                assignment, failure = await self.allocate()
                self.assertIsNone(failure)
                result = await self.behaviour.mission_result(assignment, self.mission)
                self.assertEqual(result.message_id, "result")
                self.assertEqual(len(self.agent.results), 1)

    async def test_early_result_rejects_wrong_transport_identity(self):
        for defect in ("sender", "recipient", "performative", "reply"):
            with self.subTest(defect=defect):
                self.setUp()

                def responses(accept, status):
                    invalid = self.result(accept, identifier="foreign")
                    if defect == "sender":
                        invalid.sender = "vehicle@localhost"
                    elif defect == "recipient":
                        invalid.to = "other@localhost"
                    elif defect == "performative":
                        invalid.set_metadata("performative", "propose")
                    else:
                        invalid.set_metadata("in-reply-to", "other-accept")
                    return invalid, self.result(accept), status

                self.on_accept = responses
                assignment, failure = await self.allocate()
                self.assertIsNone(failure)
                result = await self.behaviour.mission_result(assignment, self.mission)
                self.assertEqual(result.message_id, "result")

    async def test_pending_result_retains_first_valid_sample_and_deduplicates(self):
        self.on_accept = lambda accept, status: (
            self.result(accept), self.result(accept),
            self.result(accept, identifier="second", changes={"payload": {"outcome": "not_confirmed"}}),
            status,
        )
        assignment, failure = await self.allocate()
        self.assertIsNone(failure)
        result = await self.behaviour.mission_result(assignment, self.mission)
        self.assertEqual((result.message_id, result.payload["outcome"]), ("result", "confirmed"))
        self.assertEqual(self.agent.results, [result])
        self.assertTrue(self.behaviour.queue.empty())

    async def test_missing_or_invalid_status_discards_pending_result(self):
        for invalid_status in (False, True):
            with self.subTest(invalid_status=invalid_status):
                self.setUp()

                def responses(accept, status):
                    if invalid_status:
                        status.set_metadata("in-reply-to", "other-accept")
                        return self.result(accept), status
                    return (self.result(accept),)

                self.on_accept = responses
                assignment, failure = await self.allocate()
                self.assertEqual((assignment, failure), (None, "confirmation_unknown"))
                self.assertEqual(self.agent.results, [])
                self.assertIsNone(self.behaviour._pending_mission_result)

    async def test_cancelled_confirmation_cleans_pending_context(self):
        self.agent.receive_timeout = 1
        self.on_accept = lambda accept, status: (self.result(accept),)
        task = asyncio.create_task(self.allocate())
        try:
            async with asyncio.timeout(1):
                while getattr(self.behaviour, "_pending_mission_result", None) is None:
                    await asyncio.sleep(0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertIsNone(self.behaviour._pending_mission_result)
            self.assertEqual(self.agent.results, [])
        finally:
            if not task.done():
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task

    async def test_rejected_reservation_discards_pending_result(self):
        def responses(accept, status):
            body = parse_spade_message(status, expected_protocol="contract-net")
            rejected = Message.from_dict({
                **body.to_dict(), "payload": {
                    **body.payload, "status": "reservation_failed",
                    "reservation_status": "resource_occupied", "reason": "external_mission",
                },
            })
            return self.result(accept), self.wire(rejected, accept.message_id)

        self.on_accept = responses
        assignment, failure = await self.allocate()
        self.assertEqual((assignment, failure), (None, "reservation_rejected"))
        self.assertEqual(self.agent.results, [])
        self.assertIsNone(self.behaviour._pending_mission_result)


@unittest.skipUnless(run_mvp, "SPADE não está instalado")
class TestReorderedResultMvp(unittest.IsolatedAsyncioTestCase):
    async def test_status_delayed_point_one_completes_both_missions(self):
        report = await run_mvp(faults={"delay": {"STATUS": 0.1}})
        self.assertEqual((report["incident_status"], report["reason"]), ("closed", "confirmed"))
        self.assertEqual([result["source_id"] for result in report["results"]], ["drone", "ranger"])
        self.assertEqual(len(report["missions"]), 2)
        self.assertEqual(report["reservations"], [None, None, None])

    async def test_early_duplicated_results_do_not_repeat_missions(self):
        report = await run_mvp(faults={"delay": {"STATUS": 0.1},
                                       "duplicate": ["STATUS", "MISSION_RESULT"]})
        self.assertEqual(report["incident_status"], "closed")
        self.assertEqual(len(report["results"]), 2)
        self.assertEqual(len(report["missions"]), 2)
        executions = [entry for entry in report["timeline"]
                      if entry["event"] == "reserved" and "position" in entry]
        self.assertEqual([entry["resource_id"] for entry in executions], ["drone", "ranger"])
        self.assertEqual(report["reservations"], [None, None, None])

    async def test_missing_status_does_not_apply_early_result_or_redispatch(self):
        report = await run_mvp(faults={"drop": ["STATUS"]})
        self.assertEqual((report["incident_status"], report["reason"]),
                         ("unresolved", "confirmation_unknown"))
        self.assertEqual(report["results"], [])
        self.assertEqual(report["missions"], [])
        self.assertEqual(report["reservations"], [None, None, None])
        executions = [entry for entry in report["timeline"]
                      if entry["event"] == "reserved" and "position" in entry]
        self.assertEqual([entry["resource_id"] for entry in executions], ["drone"])


if __name__ == "__main__":
    unittest.main()
