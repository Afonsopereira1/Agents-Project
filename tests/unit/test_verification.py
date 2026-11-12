import unittest

from isia.domain.models import Observation, Position


try:
    from spade.message import Message as SpadeMessage

    from isia.agents.informant import InformantAgent
    from isia.agents.sensor import SensorAgent
    from isia.communication.messages import Message, MessageType, model_to_dict
    from isia.communication.transport import parse_spade_message
except ImportError:
    SpadeMessage = None


class LocalFeed:
    def __init__(self, observations):
        self.observations = tuple(observations)

    def recent(self):
        return self.observations


def observation(event_id, source_id, position=(5, 6), observed_at=1.0):
    return Observation(
        event_id, source_id, "gunshot_like_sound", Position(*position), observed_at, 0.8
    )


@unittest.skipUnless(SpadeMessage is not None, "SPADE não está instalado")
class TestRealObservationVerification(unittest.IsolatedAsyncioTestCase):
    def _agent(self, local, **context):
        from unittest.mock import Mock

        values = {
            "observation_feed": LocalFeed((local,)),
            "created_at": local.observed_at,
            "informant_jid": "informant@localhost",
            "conversation_id": None,
            "response": None,
            "eligible_source_ids": (),
            "max_distance": None,
            "max_time_difference": None,
            "minimum_compatible_sources": None,
            "incompatibility_rules": None,
            "compatibility_rules": None,
        }
        values.update(context)
        agent = Mock(**values)
        agent.loop = __import__("asyncio").get_running_loop()
        return agent

    async def _run_with_response(self, agent, response_factory):
        from unittest.mock import AsyncMock

        behaviour = SensorAgent.VerificationBehaviour()
        behaviour.set_agent(agent)
        sent = []

        async def send(message):
            sent.append(message)

        async def receive(timeout):
            if behaviour.receive.await_count > 1:
                return None
            request = parse_spade_message(sent[0])
            response = response_factory(request)
            incoming = SpadeMessage(
                to="sensor@localhost",
                sender="informant@localhost",
                body=response.to_json(),
            )
            for key, value in {
                "performative": "inform",
                "ontology": "isia",
                "protocol": "verification",
                "conversation-id": request.conversation_id,
                "in-reply-to": request.message_id,
            }.items():
                incoming.set_metadata(key, value)
            return incoming

        behaviour.send = AsyncMock(side_effect=send)
        behaviour.receive = AsyncMock(side_effect=receive)
        await behaviour.run()
        return agent

    async def test_sensor_request_transporta_observacao_do_feed_local(self):
        from unittest.mock import AsyncMock, Mock

        local = observation("obs-001", "sensor_01")
        agent = Mock(
            observation_feed=LocalFeed((local,)),
            created_at=1.0,
            informant_jid="informant@localhost",
            conversation_id=None,
            response=None,
        )
        agent.loop = __import__("asyncio").get_running_loop()
        behaviour = SensorAgent.VerificationBehaviour()
        behaviour.set_agent(agent)
        behaviour.send = AsyncMock()
        behaviour.receive = AsyncMock(return_value=None)

        await behaviour.run()

        outgoing = behaviour.send.await_args.args[0]
        request = parse_spade_message(outgoing)
        self.assertEqual(request.created_at, 1.0)
        self.assertEqual(request.payload["observation"]["event_id"], "obs-001")
        self.assertEqual(request.payload["observation"]["source_id"], "sensor_01")

    async def test_sensor_avalia_resposta_compatível_e_decide_verificacao_movel(self):
        local = observation("obs-001", "sensor_01", observed_at=1.0)
        corroborating = observation("obs-002", "sensor_02", position=(6, 6), observed_at=1.5)
        agent = self._agent(
            local,
            eligible_source_ids=("sensor_02",),
            max_distance=2.0,
            max_time_difference=1.0,
            minimum_compatible_sources=1,
        )

        def response_for(request):
            return Message(
                "response-001",
                MessageType.VERIFY_RESPONSE,
                1.5,
                {
                    "request_message_id": request.message_id,
                    "status": "observations_available",
                    "observations": [model_to_dict(corroborating)],
                },
                incident_id=request.incident_id,
                source_id="sensor_02",
                conversation_id=request.conversation_id,
            )

        await self._run_with_response(agent, response_for)

        self.assertEqual(agent.decision["decision"], "request_mobile_verification")
        self.assertEqual(agent.decision["compatible_observation_ids"], ("obs-002",))
        self.assertEqual(agent.evaluation_summary["information_coverage"], 1.0)
        history = agent.verification_history
        record = history[agent.conversation_id][agent.response.payload["request_message_id"]]
        self.assertEqual(record["initial_observation"]["event_id"], "obs-001")
        self.assertEqual(record["evidence_observation_ids"], ("obs-002",))
        self.assertEqual(record["compatible_source_ids"], ("sensor_02",))
        self.assertEqual(record["decision"], "request_mobile_verification")

    async def test_sensor_mantem_observe_quando_informante_nao_tem_dados(self):
        local = observation("obs-001", "sensor_01")
        agent = self._agent(
            local,
            eligible_source_ids=("sensor_02",),
            max_distance=2.0,
            max_time_difference=1.0,
            minimum_compatible_sources=1,
        )

        def response_for(request):
            return Message(
                "response-no-data",
                MessageType.VERIFY_RESPONSE,
                1.0,
                {
                    "request_message_id": request.message_id,
                    "status": "no_data",
                    "observations": [],
                },
                incident_id=request.incident_id,
                source_id="sensor_02",
                conversation_id=request.conversation_id,
            )

        await self._run_with_response(agent, response_for)

        self.assertEqual(agent.decision["decision"], "observe")
        self.assertEqual(agent.decision["reason"], "no_information")
        records = [
            record
            for requests in agent.verification_history.values()
            for record in requests.values()
        ]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["classification"], "no_data")
        self.assertEqual(records[0]["evidence_observation_ids"], ())

    async def test_sensor_regista_observe_em_timeout(self):
        from unittest.mock import AsyncMock

        local = observation("obs-timeout", "sensor_01")
        agent = self._agent(local)
        behaviour = SensorAgent.VerificationBehaviour()
        behaviour.set_agent(agent)
        behaviour.send = AsyncMock()
        behaviour.receive = AsyncMock(return_value=None)

        await behaviour.run()

        self.assertEqual(agent.decision["decision"], "observe")
        self.assertEqual(agent.decision["reason"], "timeout")

    async def test_sensor_rejeita_resposta_de_outra_conversa(self):
        local = observation("obs-invalid", "sensor_01")
        agent = self._agent(local)

        def response_for(request):
            return Message(
                "response-invalid-conversation",
                MessageType.VERIFY_RESPONSE,
                1.0,
                {
                    "request_message_id": request.message_id,
                    "status": "observations_available",
                    "observations": [],
                },
                incident_id=request.incident_id,
                source_id="sensor_02",
                conversation_id="another-conversation",
            )

        await self._run_with_response(agent, response_for)

        self.assertEqual(agent.decision["decision"], "observe")
        self.assertEqual(agent.decision["reason"], "invalid_correlation")

    async def test_sensor_classifica_corpo_malformado_como_invalid_response(self):
        from unittest.mock import AsyncMock

        local = observation("obs-malformed", "sensor_01")
        agent = self._agent(local)
        behaviour = SensorAgent.VerificationBehaviour()
        behaviour.set_agent(agent)
        sent = []

        async def send(message):
            sent.append(message)

        async def receive(timeout):
            if behaviour.receive.await_count > 1:
                return None
            request = parse_spade_message(sent[0])
            incoming = SpadeMessage(
                to="sensor@localhost",
                sender="informant@localhost",
                body="{malformed-json",
            )
            incoming.set_metadata("ontology", "isia")
            incoming.set_metadata("protocol", "verification")
            incoming.set_metadata("conversation-id", request.conversation_id)
            incoming.set_metadata("in-reply-to", request.message_id)
            return incoming

        behaviour.send = AsyncMock(side_effect=send)
        behaviour.receive = AsyncMock(side_effect=receive)
        await behaviour.run()

        self.assertEqual(agent.decision["decision"], "observe")
        self.assertEqual(agent.decision["reason"], "invalid_response")

    async def test_informant_responde_com_observacoes_do_seu_feed(self):
        from unittest.mock import AsyncMock, Mock

        local = observation("obs-002", "sensor_02", position=(6, 6))
        request = Message(
            "request-001",
            MessageType.VERIFY_REQUEST,
            1.0,
            {"observation": {"event_id": "obs-001"}},
            incident_id="incident-obs-001",
            conversation_id="conversation-001",
        )
        incoming = SpadeMessage(
            to="informant@localhost",
            sender="sensor@localhost",
            body=request.to_json(),
        )
        for key, value in {
            "performative": "request",
            "ontology": "isia",
            "protocol": "verification",
            "conversation-id": "conversation-001",
        }.items():
            incoming.set_metadata(key, value)

        agent = Mock(
            observation_feed=LocalFeed((local,)),
            source_id="sensor_02",
            created_at=1.0,
            loop=__import__("asyncio").get_running_loop(),
        )
        behaviour = InformantAgent.VerificationBehaviour()
        behaviour.set_agent(agent)
        behaviour.receive = AsyncMock(return_value=incoming)
        behaviour.send = AsyncMock()

        await behaviour.run()

        response = parse_spade_message(behaviour.send.await_args.args[0])
        self.assertEqual(response.payload["request_message_id"], "request-001")
        self.assertEqual(response.payload["status"], "observations_available")
        self.assertEqual(response.payload["observations"][0]["event_id"], "obs-002")
        self.assertNotIn("supports_event", response.payload)

    async def test_informant_indica_ausencia_sem_inventar_evidencia(self):
        from unittest.mock import AsyncMock, Mock

        request = Message(
            "request-002",
            MessageType.VERIFY_REQUEST,
            1.0,
            {"observation": {"event_id": "obs-001"}},
            incident_id="incident-obs-001",
            conversation_id="conversation-002",
        )
        incoming = SpadeMessage(
            to="informant@localhost",
            sender="sensor@localhost",
            body=request.to_json(),
        )
        for key, value in {
            "performative": "request",
            "ontology": "isia",
            "protocol": "verification",
            "conversation-id": "conversation-002",
        }.items():
            incoming.set_metadata(key, value)

        agent = Mock(
            observation_feed=LocalFeed(()),
            source_id="sensor_02",
            created_at=1.0,
            loop=__import__("asyncio").get_running_loop(),
        )
        behaviour = InformantAgent.VerificationBehaviour()
        behaviour.set_agent(agent)
        behaviour.receive = AsyncMock(return_value=incoming)
        behaviour.send = AsyncMock()

        await behaviour.run()

        response = parse_spade_message(behaviour.send.await_args.args[0])
        self.assertEqual(response.payload["status"], "no_data")
        self.assertEqual(response.payload["observations"], [])

    async def test_informant_declara_ausencia_informativa_com_cobertura_valida(self):
        from unittest.mock import AsyncMock, Mock

        request = Message(
            "request-absence",
            MessageType.VERIFY_REQUEST,
            1.0,
            {
                "observation": {"event_id": "obs-001"},
                "hypothesis": {
                    "hypothesis_id": "hypothesis-obs-001",
                    "event_type": "gunshot_like_sound",
                    "position": {"x": 5, "y": 6},
                    "valid_from": 1.0,
                    "valid_until": 1.0,
                },
            },
            incident_id="incident-obs-001",
            conversation_id="conversation-absence",
        )
        incoming = SpadeMessage(
            to="informant@localhost",
            sender="sensor@localhost",
            body=request.to_json(),
        )
        for key, value in {
            "performative": "request",
            "ontology": "isia",
            "protocol": "verification",
            "conversation-id": "conversation-absence",
        }.items():
            incoming.set_metadata(key, value)

        agent = Mock(
            observation_feed=LocalFeed(()),
            source_id="sensor_02",
            created_at=2.0,
            coverage_position=Position(5, 6),
            coverage_radius=2.0,
            coverage_capability="acoustic",
            coverage_observed_from=0.0,
            coverage_observed_until=2.0,
            coverage_opportunity_confirmed=True,
            loop=__import__("asyncio").get_running_loop(),
        )
        behaviour = InformantAgent.VerificationBehaviour()
        behaviour.set_agent(agent)
        behaviour.receive = AsyncMock(return_value=incoming)
        behaviour.send = AsyncMock()

        await behaviour.run()

        response = parse_spade_message(behaviour.send.await_args.args[0])
        self.assertEqual(response.payload["status"], "informative_absence")
        self.assertEqual(response.payload["observations"], [])
        self.assertEqual(response.payload["absence"]["declared_non_detection"], True)
        self.assertEqual(
            response.payload["absence"]["hypothesis_id"], "hypothesis-obs-001"
        )
        self.assertTrue(response.payload["absence"]["coverage"]["capability_validated"])

    async def test_informant_usa_no_data_sem_cobertura_ou_capacidade_validas(self):
        from unittest.mock import AsyncMock, Mock

        for capability, opportunity_confirmed in (
            ("visual", True),
            ("acoustic", False),
        ):
            with self.subTest(
                capability=capability,
                opportunity_confirmed=opportunity_confirmed,
            ):
                request = Message(
                    "request-invalid-absence",
                    MessageType.VERIFY_REQUEST,
                    1.0,
                    {
                        "observation": {"event_id": "obs-001"},
                        "hypothesis": {
                            "hypothesis_id": "hypothesis-obs-001",
                            "event_type": "gunshot_like_sound",
                            "position": {"x": 5, "y": 6},
                            "valid_from": 1.0,
                            "valid_until": 1.0,
                        },
                    },
                    incident_id="incident-obs-001",
                    conversation_id="conversation-invalid-absence",
                )
                incoming = SpadeMessage(
                    to="informant@localhost",
                    sender="sensor@localhost",
                    body=request.to_json(),
                )
                for key, value in {
                    "performative": "request",
                    "ontology": "isia",
                    "protocol": "verification",
                    "conversation-id": "conversation-invalid-absence",
                }.items():
                    incoming.set_metadata(key, value)

                agent = Mock(
                    observation_feed=LocalFeed(()),
                    source_id="sensor_02",
                    created_at=1.0,
                    coverage_position=Position(5, 6),
                    coverage_radius=2.0,
                    coverage_capability=capability,
                    coverage_observed_from=0.0,
                    coverage_observed_until=2.0,
                    coverage_opportunity_confirmed=opportunity_confirmed,
                    loop=__import__("asyncio").get_running_loop(),
                )
                behaviour = InformantAgent.VerificationBehaviour()
                behaviour.set_agent(agent)
                behaviour.receive = AsyncMock(return_value=incoming)
                behaviour.send = AsyncMock()

                await behaviour.run()

                response = parse_spade_message(behaviour.send.await_args.args[0])
                self.assertEqual(response.payload["status"], "no_data")
                self.assertEqual(response.payload["observations"], [])
                self.assertNotIn("absence", response.payload)
