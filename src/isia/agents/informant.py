"""Agente informador que responde a pedidos de verificação.

Por onde começar: `InformantAgent.VerificationBehaviour.run`, que responde a cada
VERIFY_REQUEST só com as suas observações locais recentes.
"""

from __future__ import annotations

import logging

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.template import Template

from isia.agents.sensor import _recent_observations
from isia.communication.messages import Message, MessageType, model_from_dict, model_to_dict
from isia.communication.transport import (
    ONTOLOGY,
    PERFORMATIVE_INFORM,
    PERFORMATIVE_REQUEST,
    VERIFICATION_PROTOCOL,
    build_spade_message,
    parse_spade_message,
)
from isia.domain.models import Position
from isia.domain.validation import is_finite_number
from isia.reasoning.corroboration import capability_supports_signal, positions_within_distance

logger = logging.getLogger(__name__)


class InformantAgent(Agent):
    """Agente que responde apenas com evidência do seu feed local.

    Attributes:
        observation_feed (ObservationFeed | None): Feed local de leituras; None até ser configurado.
        source_id (str | None): Identificador da fonte nas respostas; None usa
            ``informant-example``.
        created_at (float | None): Instante simulado local; só entram leituras até este instante.
        coverage_position (Position | None): Centro da área que o agente vigia.
        coverage_radius (float | None): Raio da área vigiada, em células.
        coverage_capability (str | None): Capacidade de deteção declarada.
        coverage_observed_from (float | None): Início da janela vigiada, em tempo simulado.
        coverage_observed_until (float | None): Fim da janela vigiada, em tempo simulado.
        coverage_opportunity_confirmed (bool): Se houve de facto oportunidade de detetar na janela.
    """

    def __init__(self, jid: str, password: str):
        """Inicializar o agente ainda sem feed local nem cobertura configurados.

        Args:
            jid (str): JID XMPP do informador.
            password (str): Palavra-passe XMPP.
        """
        super().__init__(jid, password)
        self.observation_feed = None
        self.source_id: str | None = None
        self.created_at: float | None = None
        self.coverage_position = None
        self.coverage_radius = None
        self.coverage_capability = None
        self.coverage_observed_from = None
        self.coverage_observed_until = None
        self.coverage_opportunity_confirmed = False

    def set_local_observation_feed(
        self,
        observation_feed,
        source_id: str,
        created_at: float,
        *,
        coverage_position=None,
        coverage_radius=None,
        coverage_capability=None,
        coverage_observed_from=None,
        coverage_observed_until=None,
        coverage_opportunity_confirmed=False,
    ) -> None:
        """Dar ao agente só o seu feed local e os metadados das suas mensagens.

        Os parâmetros ``coverage_*`` só servem para declarar ausência informativa; sem eles
        completos e válidos, uma resposta sem observações fica como ``no_data``.

        Args:
            observation_feed (ObservationFeed): Feed com as leituras recentes desta fonte.
            source_id (str): Identificador da fonte nas respostas.
            created_at (float): Instante simulado local, em segundos.
            coverage_position (Position | None): Centro da área vigiada.
            coverage_radius (float | None): Raio da área vigiada, em células.
            coverage_capability (str | None): Capacidade de deteção; tem de suportar o tipo de
                evento da hipótese.
            coverage_observed_from (float | None): Início da janela vigiada, em tempo simulado.
            coverage_observed_until (float | None): Fim da janela vigiada; não pode passar de
                ``created_at``.
            coverage_opportunity_confirmed (bool): True só se houve oportunidade real de deteção.
        """
        self.observation_feed = observation_feed
        self.source_id = source_id
        self.created_at = created_at
        self.coverage_position = coverage_position
        self.coverage_radius = coverage_radius
        self.coverage_capability = coverage_capability
        self.coverage_observed_from = coverage_observed_from
        self.coverage_observed_until = coverage_observed_until
        self.coverage_opportunity_confirmed = coverage_opportunity_confirmed

    class VerificationBehaviour(CyclicBehaviour):
        """Responder a cada VERIFY_REQUEST com as observações locais recentes."""
        async def run(self):
            """Responder a um VERIFY_REQUEST com VERIFY_RESPONSE; o resto é ignorado.

            Só entram observações até ao instante local do agente. O estado é
            ``observations_available``, ``no_data`` ou, sem observações e com
            cobertura demonstrada, ``informative_absence``. Um pedido emitido depois
            do instante local fica sem resposta.

            Overrides:
                spade.behaviour.CyclicBehaviour.run
            """
            incoming = await self.receive(timeout=10)
            if incoming is None:
                return
            try:
                request = parse_spade_message(incoming)
            except (TypeError, ValueError) as error:
                logger.warning("Pedido rejeitado: %s", error)
                return
            if request.message_type is not MessageType.VERIFY_REQUEST:
                return

            source_id = self.agent.source_id
            if not isinstance(source_id, str) or not source_id.strip():
                source_id = "informant-example"
            created_at = self.agent.created_at
            if not is_finite_number(created_at) or created_at < 0:
                created_at = request.created_at
            if created_at < request.created_at:
                logger.warning("Pedido posterior ao instante local do informador")
                return
            observations = tuple(
                observation for observation in _recent_observations(self.agent.observation_feed)
                if observation.observed_at <= created_at
            )

            status = "observations_available" if observations else "no_data"
            payload = {
                "request_message_id": request.message_id,
                "observations": [model_to_dict(observation) for observation in observations],
                "status": status,
            }
            if isinstance(request.payload.get("hypothesis"), dict):
                payload["hypothesis"] = request.payload["hypothesis"]
            absence = _informative_absence_payload(self.agent, request)
            if not observations and absence is not None:
                payload["status"] = "informative_absence"
                payload["absence"] = absence

            response = Message(
                message_id=f"response-{request.message_id}",
                message_type=MessageType.VERIFY_RESPONSE,
                created_at=created_at,
                payload=payload,
                event_id=request.event_id,
                incident_id=request.incident_id,
                source_id=source_id,
                conversation_id=request.conversation_id,
            )
            reply = build_spade_message(
                str(incoming.sender),
                response,
                performative=PERFORMATIVE_INFORM,
                conversation_id=request.conversation_id,
                in_reply_to=request.message_id,
            )
            await self.send(reply)
            logger.info("VERIFY_RESPONSE enviada para %s", incoming.sender)

    async def setup(self):
        """Registar o comportamento para pedidos ``request`` de verificação.

        Overrides:
            spade.agent.Agent.setup
        """
        template = Template(
            metadata={
                "performative": PERFORMATIVE_REQUEST,
                "ontology": ONTOLOGY,
                "protocol": VERIFICATION_PROTOCOL,
            }
        )
        self.add_behaviour(self.VerificationBehaviour(), template)


def _informative_absence_payload(agent, request: Message) -> dict[str, object] | None:
    """Declarar a não deteção só se a cobertura local, configurada e com oportunidade
    confirmada, abranger a posição e a janela da hipótese; senão ``None``."""
    hypothesis = request.payload.get("hypothesis")
    if not isinstance(hypothesis, dict):
        return None
    coverage_position = getattr(agent, "coverage_position", None)
    coverage_radius = getattr(agent, "coverage_radius", None)
    coverage_capability = getattr(agent, "coverage_capability", None)
    observed_from = getattr(agent, "coverage_observed_from", None)
    observed_until = getattr(agent, "coverage_observed_until", None)
    created_at = getattr(agent, "created_at", None)
    if not is_finite_number(created_at) or created_at < 0:
        created_at = request.created_at
    opportunity_confirmed = getattr(agent, "coverage_opportunity_confirmed", False)
    if (
        not isinstance(coverage_position, Position)
        or type(coverage_radius) not in (int, float)
        or not isinstance(coverage_capability, str)
        or not coverage_capability.strip()
        or type(observed_from) not in (int, float)
        or type(observed_until) not in (int, float)
    ):
        return None
    if opportunity_confirmed is not True:
        return None
    # Um texto arbitrário não é demonstração de capacidade de deteção.
    if not capability_supports_signal(coverage_capability, hypothesis.get("event_type")):
        return None
    try:
        hypothesis_position = model_from_dict(hypothesis["position"], Position)
        hypothesis_from = hypothesis["valid_from"]
        hypothesis_until = hypothesis["valid_until"]
    except (KeyError, TypeError, ValueError):
        return None
    if (
        not is_finite_number(coverage_radius)
        or coverage_radius < 0
        or not is_finite_number(observed_from)
        or not is_finite_number(observed_until)
        or observed_from > observed_until
        or observed_until > created_at
        or not is_finite_number(hypothesis_from)
        or not is_finite_number(hypothesis_until)
        or hypothesis_from > hypothesis_until
        or observed_from > hypothesis_from
        or observed_until < hypothesis_until
    ):
        return None
    try:
        if not positions_within_distance(coverage_position, hypothesis_position, coverage_radius):
            return None
    except ValueError:
        return None
    return {
        "hypothesis_id": hypothesis.get("hypothesis_id"),
        "declared_non_detection": True,
        "observed_from": observed_from,
        "observed_until": observed_until,
        "coverage": {
            "position": {
                "x": coverage_position.x,
                "y": coverage_position.y,
            },
            "radius": coverage_radius,
            "capability": coverage_capability,
            "capability_validated": True,
            "opportunity_confirmed": True,
        },
    }
