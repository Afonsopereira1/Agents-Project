"""Intenção e causalidade na verificação e na confirmação de reserva."""

import json
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from isia.communication.messages import Message, MessageType
from isia.communication.transport import build_spade_message
from isia.reasoning.allocation import reservation_status_matches_accept

try:
    from isia.agents import informant, mobile
    from isia.agents.sensor import SensorAgent, response_matches_request
    from isia.simulation.runner import run_mvp
except ImportError:
    run_mvp = None


@unittest.skipUnless(run_mvp, "SPADE não está instalado")
class TestVerificationEnvelope(unittest.TestCase):
    def exchange(self, *, emitted_at=10.0, performative="inform", status="observations_available"):
        request = Message("request", MessageType.VERIFY_REQUEST, 10.0, {},
                          incident_id="incident", conversation_id="conversation")
        response = Message("response", MessageType.VERIFY_RESPONSE, emitted_at,
                           {"request_message_id": "request", "status": status, "observations": []},
                           incident_id="incident", conversation_id="conversation", source_id="peer")
        incoming = build_spade_message("sensor@localhost", response, performative=performative,
                                       conversation_id="conversation", in_reply_to="request")
        incoming.sender = "peer@localhost"
        return incoming, response, request

    def matches(self, *, now=10.0, **options):
        return response_matches_request(*self.exchange(**options), "peer@localhost", current_time=now)

    def test_inform_accepts_all_verification_statuses(self):
        for status in ("observations_available", "no_data", "informative_absence"):
            with self.subTest(status=status):
                self.assertTrue(self.matches(status=status))

    def test_incompatible_or_missing_performative_is_rejected(self):
        for performative in ("refuse", "request", "propose", ""):
            with self.subTest(performative=performative):
                self.assertFalse(self.matches(performative=performative))
        incoming, response, request = self.exchange()
        incoming._metadata.pop("performative")
        self.assertFalse(response_matches_request(incoming, response, request,
                                                  "peer@localhost", current_time=10.0))

    def test_simulated_emission_interval_is_inclusive(self):
        for at in (10.0, 10.5, 11.0):
            with self.subTest(at=at):
                self.assertTrue(self.matches(emitted_at=at, now=11.0))

    def test_reply_before_request_or_after_receiver_time_is_rejected(self):
        for at in (9.0, 11.0001, 1000000.0):
            with self.subTest(at=at):
                self.assertFalse(self.matches(emitted_at=at, now=11.0))

    def test_receiver_time_must_be_finite(self):
        for now in (None, float("nan"), float("inf")):
            with self.subTest(now=now):
                self.assertFalse(self.matches(now=now))


class TestReservationConfirmationChronology(unittest.TestCase):
    def matches(self, emitted_at, *, failed=False):
        accept = Message("accept", MessageType.ACCEPT, 10.0,
                         {"resource_id": "drone", "cfp_message_id": "cfp",
                          "proposal_message_id": "proposal"},
                         mission_id="mission", incident_id="incident", conversation_id="conversation")
        status = Message("status", MessageType.STATUS, emitted_at,
                         {"resource_id": "drone", "accept_message_id": "accept",
                          "status": "reservation_failed" if failed else "reserved",
                          "reservation_status": "resource_occupied" if failed else "reserved"},
                         source_id="drone", mission_id="mission", incident_id="incident",
                         conversation_id="conversation")
        return reservation_status_matches_accept(status, accept, "drone")

    def test_status_before_accept_is_rejected(self):
        for failed in (False, True):
            with self.subTest(failed=failed):
                self.assertFalse(self.matches(9.0, failed=failed))

    def test_contemporary_and_later_status_are_valid(self):
        for at in (10.0, 11.0):
            for failed in (False, True):
                with self.subTest(at=at, failed=failed):
                    self.assertTrue(self.matches(at, failed=failed))


@unittest.skipUnless(run_mvp, "SPADE não está instalado")
class TestRealIncidentValidation(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_sensor_without_feed_accepts_a_contemporary_reply(self):
        agent = SensorAgent("sensor@localhost", "test", "peer@localhost")
        behaviour = agent.VerificationBehaviour()
        behaviour.set_agent(agent)
        sent = []

        async def send(message):
            sent.append(message)

        async def receive(timeout):
            request = Message.from_json(sent[0].body)
            response = Message("response", MessageType.VERIFY_RESPONSE, 0.0,
                               {"request_message_id": request.message_id,
                                "status": "no_data", "observations": []},
                               incident_id=request.incident_id, conversation_id=request.conversation_id)
            incoming = build_spade_message(str(agent.jid), response, performative="inform",
                                           conversation_id=request.conversation_id, in_reply_to=request.message_id)
            incoming.sender = "peer@localhost"
            return incoming

        behaviour.send, behaviour.receive = send, receive
        await behaviour.run()
        self.assertEqual(agent.response.message_id, "response")

    async def test_two_different_replies_to_same_request_only_use_the_first_valid_one(self):
        original = informant.InformantAgent.VerificationBehaviour.run
        for empty_first in (False, True):
            with self.subTest(empty_first=empty_first):
                async def answer(behaviour):
                    send = behaviour.send

                    async def send_two_replies(outgoing):
                        empty = deepcopy(outgoing)
                        body = json.loads(empty.body)
                        body["payload"].update(status="no_data", observations=[])
                        empty.body = json.dumps(body)
                        for reply in ((empty, outgoing) if empty_first else (outgoing, empty)):
                            await send(reply)

                    behaviour.send = send_two_replies
                    try:
                        await original(behaviour)
                    finally:
                        behaviour.send = send

                with patch.object(informant.InformantAgent.VerificationBehaviour, "run", answer):
                    report = await run_mvp()
                self.assertEqual(report["incident_status"], "expired" if empty_first else "closed")
                self.assertEqual(len(report["missions"]), 0 if empty_first else 2)
                self.assertEqual(report["reservations"], [None, None, None])

    async def test_pre_accept_status_cannot_confirm_a_real_ranger_reservation(self):
        original = mobile.build_reservation_status_message

        def invalid_ranger_status(accept, *args, **kwargs):
            status = original(accept, *args, **kwargs)
            if kwargs["resource_id"] == "ranger":
                self.assertGreater(accept.created_at, 0)
                status.created_at = accept.created_at - 1
            return status

        with patch.object(mobile, "build_reservation_status_message", invalid_ranger_status):
            report = await run_mvp(max_receive_timeout=0.5, queue_rounds=0)
        self.assertEqual((report["incident_status"], report["reason"]),
                         ("unresolved", "confirmation_unknown"))
        self.assertEqual([r["source_id"] for r in report["results"]], ["drone"])
        self.assertEqual(report["reservations"], [None, None, None])
        self.assertTrue(all(r["available"] for r in report["resources"]))

    async def test_invalid_verification_never_dispatches_resources(self):
        original = informant.build_spade_message
        for kind in ("refuse", "request", "future"):
            with self.subTest(kind=kind):
                def invalid_reply(*args, **kwargs):
                    outgoing = original(*args, **kwargs)
                    if kind == "future":
                        body = json.loads(outgoing.body)
                        body["created_at"] = 1000000.0
                        outgoing.body = json.dumps(body)
                    else:
                        outgoing.set_metadata("performative", kind)
                    return outgoing

                with patch.object(informant, "build_spade_message", invalid_reply):
                    report = await run_mvp(receive_timeout=0.05, max_receive_timeout=0.05, queue_rounds=0)
                self.assertEqual((report["incident_status"], report["reason"]),
                                 ("expired", "insufficient_corroboration"))
                self.assertEqual(report["missions"], [])
                self.assertEqual(report["reservations"], [None, None, None])
                self.assertFalse(any(m["body"]["message_type"] == "CFP" for m in report["messages"]))

    async def test_valid_reply_after_invalid_reply_still_completes_the_mission(self):
        original = informant.InformantAgent.VerificationBehaviour.run

        async def answer(behaviour):
            send = behaviour.send

            async def send_with_invalid_predecessor(outgoing):
                invalid = deepcopy(outgoing)
                invalid.set_metadata("performative", "refuse")
                await send(invalid)
                await send(outgoing)

            behaviour.send = send_with_invalid_predecessor
            try:
                await original(behaviour)
            finally:
                behaviour.send = send

        with patch.object(informant.InformantAgent.VerificationBehaviour, "run", answer):
            report = await run_mvp()
        self.assertEqual((report["incident_status"], report["reason"]), ("closed", "confirmed"))
        self.assertEqual(len(report["missions"]), 2)
        self.assertEqual(report["reservations"], [None, None, None])
        history = next(iter(next(iter(report["verification"].values())).values()))
        self.assertEqual(len(history["rejected_responses"]), 1)

    async def test_normal_mvp_and_policy_keep_the_expected_outcomes(self):
        settings = json.loads((Path(__file__).resolve().parents[2] / "config/agents.json").read_text())
        for policy in (None, settings):
            with self.subTest(policy=policy is not None):
                report = await run_mvp(response_settings=policy)
                self.assertEqual((report["incident_status"], report["reason"]),
                                 ("expired", "insufficient_corroboration") if policy else ("closed", "confirmed"))
                self.assertEqual(len(report["messages"]), 2 if policy else 15)
                self.assertEqual(report["reservations"], [None, None, None])
                self.assertTrue(all(r["available"] for r in report["resources"]))


if __name__ == "__main__":
    unittest.main()
