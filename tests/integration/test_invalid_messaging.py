import asyncio
import unittest
from unittest.mock import AsyncMock, Mock

from isia.communication.messages import Message, MessageType


try:
    from spade.message import Message as SpadeMessage
    from spade.template import Template

    from isia.agents.informant import InformantAgent
except ImportError:  # SPADE é necessário para estes testes de API SPADE.
    SpadeMessage = None


@unittest.skipUnless(SpadeMessage is not None, "SPADE 4.1.4 não está instalado")
class TestSpadeMessageFiltering(unittest.TestCase):
    def make_template(self):
        return Template(
            metadata={
                "performative": "request",
                "ontology": "isia",
                "protocol": "verification",
            }
        )

    def make_message(self):
        message = SpadeMessage(to="informant@localhost", body="{}")
        message.set_metadata("performative", "request")
        message.set_metadata("ontology", "isia")
        message.set_metadata("protocol", "verification")
        return message

    def test_template_aceita_metadados_corretos(self):
        self.assertTrue(self.make_template().match(self.make_message()))

    def test_template_rejeita_performative_incorreto(self):
        message = self.make_message()
        message.set_metadata("performative", "inform")
        self.assertFalse(self.make_template().match(message))

    def test_template_rejeita_ontology_incorreta(self):
        message = self.make_message()
        message.set_metadata("ontology", "other-ontology")
        self.assertFalse(self.make_template().match(message))

    def test_template_rejeita_protocol_incorreto(self):
        message = self.make_message()
        message.set_metadata("protocol", "other-protocol")
        self.assertFalse(self.make_template().match(message))


@unittest.skipUnless(SpadeMessage is not None, "SPADE 4.1.4 não está instalado")
class TestInformantInvalidMessage(unittest.IsolatedAsyncioTestCase):
    def make_incoming(self, body):
        message = SpadeMessage(
            to="informant@localhost",
            sender="sensor@localhost",
            body=body,
        )
        message.set_metadata("performative", "request")
        message.set_metadata("ontology", "isia")
        message.set_metadata("protocol", "verification")
        message.set_metadata("conversation-id", "conversation-001")
        return message

    async def run_invalid_request(self, body):
        agent_mock = Mock(loop=asyncio.get_running_loop())
        behaviour = InformantAgent.VerificationBehaviour()
        behaviour.set_agent(agent_mock)
        behaviour.receive = AsyncMock(return_value=self.make_incoming(body))
        behaviour.send = AsyncMock()

        await behaviour.run()

        behaviour.send.assert_not_awaited()

    async def test_informant_nao_responde_a_json_malformado(self):
        await self.run_invalid_request("not-json")

    async def test_informant_nao_responde_a_campos_em_falta(self):
        await self.run_invalid_request('{"schema_version": 1}')

    async def test_informant_nao_responde_a_conversa_incompativel(self):
        invalid = Message(
            "request-001",
            MessageType.VERIFY_REQUEST,
            0.0,
            {"question": "há evidência?"},
            conversation_id="body-conversation",
        ).to_json()
        await self.run_invalid_request(invalid)

    async def test_informant_responde_a_pedido_valido(self):
        valid = Message(
            "request-001",
            MessageType.VERIFY_REQUEST,
            0.0,
            {"question": "há evidência?"},
            conversation_id="conversation-001",
        ).to_json()
        agent_mock = Mock(loop=asyncio.get_running_loop())
        behaviour = InformantAgent.VerificationBehaviour()
        behaviour.set_agent(agent_mock)
        behaviour.receive = AsyncMock(return_value=self.make_incoming(valid))
        behaviour.send = AsyncMock()

        await behaviour.run()

        behaviour.send.assert_awaited_once()
