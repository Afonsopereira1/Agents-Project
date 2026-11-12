"""Regressões da recolha de propostas no iniciador utilizado pelo MVP."""

import unittest
from unittest.mock import patch

from isia.communication.messages import Message, MessageType
from isia.domain.models import Mission, Position, ResourceState
from isia.reasoning.allocation import (
    LocalResourceReservation, build_reservation_status_message, evaluate_cfp,
)

try:
    from isia.agents.incident import IncidentSensorAgent
    from isia.communication.transport import build_spade_message, parse_spade_message
except ImportError:
    IncidentSensorAgent = None


@unittest.skipUnless(IncidentSensorAgent, "SPADE não está instalado")
class TestIncidentAllocationRegressions(unittest.IsolatedAsyncioTestCase):
    def prepare(self, resources=("drone",), *, timeout=1.0):
        self.agent = IncidentSensorAgent("sensor@localhost", "test", "peer@localhost")
        self.agent.configure_mvp({}, {}, receive_timeout=timeout)
        self.agent.simulated_time = 20.0
        self.behaviour = self.agent.IncidentBehaviour()
        self.behaviour.set_agent(self.agent)
        self.mission = Mission("mission", "incident", "verify_incident", Position(1, 0),
                               "mobile_verification", 0)
        self.candidates = {f"{resource}@localhost": resource for resource in resources}
        self.reservations = {
            resource: LocalResourceReservation(
                ResourceState(resource, resource, Position(0, 0), True, 100))
            for resource in resources
        }
        self.sent = []
        self.responses = lambda cfp: ()

        async def send(outgoing):
            body = parse_spade_message(outgoing, expected_protocol="contract-net")
            self.sent.append(body)
            if body.message_type is MessageType.CFP and len(self.sent) == len(resources):
                for response in self.responses(body):
                    self.behaviour.queue.put_nowait(response)
            elif body.message_type is MessageType.ACCEPT:
                resource = body.payload["resource_id"]
                status = build_reservation_status_message(
                    body, self.reservations[resource].reserve(body.mission_id),
                    resource_id=resource, created_at=self.agent.simulated_time)
                self.behaviour.queue.put_nowait(self.wire(status, body.message_id))

        self.behaviour.send = send

    def proposal(self, cfp, resource="drone"):
        return evaluate_cfp(
            cfp, self.reservations[resource].resource_state, ("mobile_verification",),
            current_time=20, minimum_autonomy_percent=0, eta_seconds=1,
            energy_cost_percent=2, load=0)

    def wire(self, body, reply_to):
        incoming = build_spade_message(
            str(self.agent.jid), body,
            performative="propose" if body.message_type is MessageType.PROPOSAL else "inform",
            conversation_id=body.conversation_id, in_reply_to=reply_to, protocol="contract-net")
        incoming.sender = f"{body.source_id}@localhost"
        return incoming

    async def allocate(self):
        return await self.behaviour.allocate(self.mission, self.candidates, 1)

    def assert_one_assignment(self, assignment, failure):
        self.assertIsNone(failure)
        self.assertIsNotNone(assignment)
        accepts = [body for body in self.sent if body.message_type is MessageType.ACCEPT]
        self.assertEqual(len(accepts), 1)
        self.assertEqual(accepts[0].mission_id, self.mission.mission_id)
        self.assertEqual(sum(r.reserved_mission_id == self.mission.mission_id
                             for r in self.reservations.values()), 1)

    async def test_invalid_proposal_does_not_consume_resource_response(self):
        for defect in ("missing_bid", "malformed_bid", "bid_mission", "bid_resource",
                       "negative_eta", "source", "incident", "mission", "cfp", "conversation",
                       "before_cfp", "future", "performative", "reply_to"):
            for same_id in (False, True):
                with self.subTest(defect=defect, same_id=same_id):
                    self.prepare()

                    def responses(cfp):
                        valid = self.proposal(cfp)
                        data = valid.to_dict()
                        data["payload"] = {**valid.payload, "bid": dict(valid.payload["bid"])}
                        if not same_id:
                            data["message_id"] = "invalid-proposal"
                        if defect == "missing_bid":
                            data["payload"].pop("bid")
                        elif defect == "malformed_bid":
                            data["payload"]["bid"] = {}
                        elif defect in ("bid_mission", "bid_resource", "negative_eta"):
                            key, value = {"bid_mission": ("mission_id", "foreign"),
                                          "bid_resource": ("resource_id", "foreign"),
                                          "negative_eta": ("eta", -1)}[defect]
                            data["payload"]["bid"][key] = value
                        elif defect in ("source", "incident", "mission", "conversation"):
                            data[f"{defect}_id"] = "foreign"
                        elif defect == "cfp":
                            data["payload"]["cfp_message_id"] = "foreign"
                        elif defect in ("before_cfp", "future"):
                            data["created_at"] = 19 if defect == "before_cfp" else 121
                        invalid = self.wire(Message.from_dict(data), cfp.message_id)
                        if defect == "performative":
                            invalid.set_metadata("performative", "inform")
                        elif defect == "reply_to":
                            invalid.set_metadata("in-reply-to", "foreign")
                        return invalid, self.wire(valid, cfp.message_id)

                    self.responses = responses
                    self.assert_one_assignment(*await self.allocate())

    async def test_invalid_proposals_from_all_resources_precede_valid_proposals(self):
        self.prepare(("drone", "vehicle"))

        def responses(cfp):
            valid = [self.proposal(cfp, resource) for resource in self.reservations]
            invalid = [Message.from_dict({**body.to_dict(), "payload": {
                "cfp_message_id": cfp.message_id, "bid": {}}}) for body in valid]
            return [self.wire(body, cfp.message_id) for body in (*invalid, *valid)]

        self.responses = responses
        self.assert_one_assignment(*await self.allocate())
        self.assertEqual(sum(body.message_type is MessageType.REJECT for body in self.sent), 1)

    async def test_valid_duplicate_does_not_replace_first_response(self):
        self.prepare(("drone", "vehicle"))

        def responses(cfp):
            drone, vehicle = self.proposal(cfp), self.proposal(cfp, "vehicle")
            return [self.wire(body, cfp.message_id) for body in (drone, drone, vehicle)]

        self.responses = responses
        self.assert_one_assignment(*await self.allocate())
        self.assertTrue(self.behaviour.queue.empty())

    async def test_invalid_responses_do_not_extend_global_timeout(self):
        self.prepare()
        self.responses = lambda cfp: [self.wire(Message.from_dict({
            **self.proposal(cfp).to_dict(), "payload": {"cfp_message_id": cfp.message_id, "bid": {}}}),
            cfp.message_id)] * 3 + [self.wire(self.proposal(cfp), cfp.message_id)]
        now, timeouts = [100.0], []
        receive = self.behaviour.receive

        async def timed_receive(timeout):
            timeouts.append(timeout)
            incoming = await receive(timeout=timeout)
            now[0] += 0.4
            return incoming

        self.behaviour.receive = timed_receive
        with patch("isia.agents.incident.monotonic", side_effect=lambda: now[0]):
            assignment, failure = await self.allocate()
        self.assertIsNone(assignment)
        self.assertEqual(failure, "no_eligible_proposals")
        self.assertEqual(len(timeouts), 3)
        for actual, expected in zip(timeouts, (1, 0.6, 0.2)):
            self.assertAlmostEqual(actual, expected)
        self.assertFalse(any(body.message_type is MessageType.ACCEPT for body in self.sent))

    async def test_accept_send_error_is_not_hidden(self):
        self.prepare()
        self.responses = lambda cfp: [self.wire(self.proposal(cfp), cfp.message_id)]
        send = self.behaviour.send

        async def fail_accept(outgoing):
            body = parse_spade_message(outgoing, expected_protocol="contract-net")
            if body.message_type is MessageType.ACCEPT:
                raise OSError("accept transport failure")
            await send(outgoing)

        self.behaviour.send = fail_accept
        with self.assertRaisesRegex(OSError, "accept transport failure"):
            await self.allocate()
        self.assertIsNone(self.reservations["drone"].reserved_mission_id)
