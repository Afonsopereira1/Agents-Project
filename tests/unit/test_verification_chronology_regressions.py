"""Regressões de causalidade e de distâncias nas respostas de verificação."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from isia.communication.messages import Message, MessageType, model_to_dict
from isia.communication.transport import build_spade_message, parse_spade_message
from isia.domain.models import Observation, Position
from isia.reasoning.corroboration import (
    aggregate_verification_responses,
    build_observation_hypothesis,
    select_eligible_sources,
)
from isia.simulation.scenario import Source

try:
    from isia.agents.informant import InformantAgent, _informative_absence_payload
    from isia.agents.sensor import SensorAgent
except ImportError:
    SensorAgent = None


def observation(event_id="initial", source_id="sensor-01", observed_at=10.0):
    return Observation(
        event_id, source_id, "gunshot_like_sound", Position(5, 5), observed_at, 0.8
    )


def response(initial, *, created_at=10.0, evidence_time=10.0, absence_until=None):
    payload = {"request_message_id": "request-1"}
    if absence_until is None:
        payload.update(
            status="observations_available",
            observations=[model_to_dict(observation("other", "sensor-02", evidence_time))],
        )
    else:
        hypothesis = build_observation_hypothesis(initial)
        payload.update(
            status="informative_absence", observations=[], hypothesis=hypothesis,
            absence={
                "hypothesis_id": hypothesis["hypothesis_id"],
                "declared_non_detection": True,
                "observed_from": 9.0,
                "observed_until": absence_until,
                "coverage": {
                    "position": {"x": 5, "y": 5}, "radius": 2.0,
                    "capability": "acoustic", "capability_validated": True,
                    "opportunity_confirmed": True,
                },
            },
        )
    return Message(
        "response-1", MessageType.VERIFY_RESPONSE, created_at, payload,
        incident_id="incident-1", source_id="sensor-02", conversation_id="conv-1",
    )


class TestVerificationEvidenceChronology(unittest.TestCase):
    def aggregate(self, item):
        return aggregate_verification_responses(
            observation(), [item], "conv-1", "request-1", 2.0, 2.0,
            expected_incident_id="incident-1",
        )

    def test_future_observation_is_rejected(self):
        with self.assertRaises(ValueError):
            self.aggregate(response(observation(), evidence_time=11.0))

    def test_future_absence_interval_is_rejected(self):
        with self.assertRaises(ValueError):
            self.aggregate(response(observation(), absence_until=11.0))

    def test_emission_time_is_inclusive_for_observation_and_absence(self):
        self.assertEqual(
            self.aggregate(response(observation()))["classification"], "compatible"
        )
        self.assertEqual(
            self.aggregate(response(observation(), absence_until=10.0))["classification"],
            "informative_absence",
        )

    def test_oversized_source_distance_is_a_validation_error(self):
        with self.assertRaises(ValueError):
            select_eligible_sources(
                observation(), {"sensor-02": Position(10**400, 5)},
                {"sensor-02": Source("acoustic", 2.0)},
            )


@unittest.skipUnless(SensorAgent is not None, "SPADE não está instalado")
class TestVerificationChronologyBehaviour(unittest.IsolatedAsyncioTestCase):
    def sensor(self):
        initial = observation()
        agent = Mock(
            loop=asyncio.get_running_loop(),
            observation_feed=SimpleNamespace(recent=lambda: (initial,)),
            created_at=10.0, informant_jid="informant@localhost", response=None,
            eligible_source_ids=("sensor-02",), max_distance=2.0,
            max_time_difference=2.0, minimum_compatible_sources=1,
            incompatibility_rules=None, compatibility_rules=None,
            verification_history={},
        )
        behaviour = SensorAgent.VerificationBehaviour()
        behaviour.set_agent(agent)
        behaviour.send = AsyncMock()
        return behaviour, agent

    async def test_invalid_chronology_does_not_consume_the_valid_reply(self):
        for kind in ("reply_before_request", "future_observation", "future_absence"):
            with self.subTest(kind=kind):
                behaviour, agent = self.sensor()

                async def receive(timeout):
                    request = parse_spade_message(behaviour.send.await_args.args[0])
                    first = behaviour.receive.await_count == 1
                    item = response(
                        observation(),
                        created_at=9.0 if first and kind == "reply_before_request" else 10.0,
                        evidence_time=11.0 if first and kind == "future_observation" else (
                            8.0 if first and kind == "reply_before_request" else 10.0
                        ),
                        absence_until=11.0 if first and kind == "future_absence" else None,
                    )
                    item.message_id = "invalid-response" if first else "valid-response"
                    item.payload["request_message_id"] = request.message_id
                    item.conversation_id = request.conversation_id
                    item.incident_id = request.incident_id
                    incoming = build_spade_message(
                        "sensor@localhost", item, performative="inform",
                        conversation_id=request.conversation_id,
                        in_reply_to=request.message_id,
                    )
                    incoming.sender = "informant@localhost"
                    return incoming

                behaviour.receive = AsyncMock(side_effect=receive)
                await behaviour.run()

                self.assertEqual(behaviour.receive.await_count, 2)
                self.assertEqual(agent.response.message_id, "valid-response")
                self.assertEqual(agent.decision["decision"], "request_mobile_verification")
                record = next(iter(agent.verification_history[agent.conversation_id].values()))
                self.assertEqual(len(record["rejected_responses"]), 1)
                self.assertFalse(record["response_wait_timed_out"])

    async def test_informant_does_not_emit_future_observations(self):
        request = Message(
            "request-1", MessageType.VERIFY_REQUEST, 10.0, {},
            incident_id="incident-1", conversation_id="conv-1",
        )
        incoming = build_spade_message(
            "informant@localhost", request, performative="request", conversation_id="conv-1"
        )
        incoming.sender = "sensor@localhost"
        agent = Mock(
            loop=asyncio.get_running_loop(), created_at=10.0, source_id="sensor-02",
            observation_feed=SimpleNamespace(
                recent=lambda: (observation("future", "sensor-02", 11.0),)
            ),
        )
        behaviour = InformantAgent.VerificationBehaviour()
        behaviour.set_agent(agent)
        behaviour.receive = AsyncMock(return_value=incoming)
        behaviour.send = AsyncMock()
        await behaviour.run()

        reply = parse_spade_message(behaviour.send.await_args.args[0])
        self.assertEqual(reply.created_at, 10.0)
        self.assertEqual(reply.payload["status"], "no_data")
        self.assertEqual(reply.payload["observations"], [])

    def test_informant_does_not_claim_future_coverage(self):
        agent = SimpleNamespace(
            created_at=10.0, coverage_position=Position(5, 5), coverage_radius=2.0,
            coverage_capability="acoustic", coverage_observed_from=9.0,
            coverage_observed_until=11.0, coverage_opportunity_confirmed=True,
        )
        request = Message(
            "request-1", MessageType.VERIFY_REQUEST, 10.0,
            {"hypothesis": build_observation_hypothesis(observation())},
            incident_id="incident-1", conversation_id="conv-1",
        )
        self.assertIsNone(_informative_absence_payload(agent, request))
