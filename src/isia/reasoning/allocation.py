"""Ponte local entre a decisão de corroboração e uma missão de verificação.

Este módulo ainda não negocia nem reserva recursos. Apenas materializa, de
forma idempotente, a missão que poderá ser usada por uma futura ronda de
Contract Net.
"""

from collections.abc import Mapping
from math import isfinite
from uuid import uuid4

from isia.communication.messages import Message, MessageType, model_to_dict
from isia.domain.models import Incident, Mission, Position


MOBILE_VERIFICATION_DECISION = "request_mobile_verification"
MOBILE_VERIFICATION_TASK = "verify_incident"
MOBILE_VERIFICATION_CAPABILITY = "mobile_verification"


def _validate_simulated_time(value: object, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or value < 0
    ):
        raise ValueError(
            f"{name} deve ser um número finito e não negativo em segundos simulados."
        )
    return float(value)


def build_cfp_message(
    mission: Mission,
    created_at: float,
    deadline: float,
    *,
    message_id: str | None = None,
    conversation_id: str | None = None,
) -> Message:
    """Construir um ``CFP`` para uma missão existente.

    ``created_at`` e ``deadline`` são instantes absolutos em segundos de tempo
    simulado, usando a mesma referência temporal do relógio da simulação. O
    prazo tem de ser igual ou posterior à emissão. IDs omitidos são gerados
    localmente; IDs fornecidos pelo iniciador são mantidos para correlacionar
    futuras ``PROPOSAL``/respostas com este CFP.
    """
    if not isinstance(mission, Mission):
        raise TypeError("mission deve ser Mission.")

    created_at_value = _validate_simulated_time(created_at, "created_at")
    deadline_value = _validate_simulated_time(deadline, "deadline")
    if deadline_value < created_at_value:
        raise ValueError("deadline não pode ser anterior a created_at.")

    mission_data = model_to_dict(mission)
    payload = {
        field: mission_data[field]
        for field in ("task", "target", "required_capability", "priority")
    }
    payload["deadline"] = deadline_value

    return Message(
        message_id if message_id is not None else f"message-{uuid4()}",
        MessageType.CFP,
        created_at_value,
        payload,
        incident_id=mission.incident_id,
        mission_id=mission.mission_id,
        conversation_id=(
            conversation_id
            if conversation_id is not None
            else f"conversation-{uuid4()}"
        ),
    )


class MissionRegistry:
    """Registo local de missões criadas por um iniciador de ocorrência.

    A chave da decisão é a ocorrência e o tipo de decisão. Assim, repetir a
    mesma decisão do ``SensorAgent`` devolve a missão já criada em vez de
    criar uma segunda missão para o mesmo incidente.
    """

    def __init__(self) -> None:
        self._missions: dict[tuple[str, str], Mission] = {}

    def create_from_decision(
        self,
        incident: Incident,
        decision: Mapping[str, object],
        *,
        mission_id: str | None = None,
        priority: int = 0,
        target: Position | None = None,
    ) -> Mission | None:
        """Criar a missão móvel correspondente à decisão, se aplicável.

        ``None`` representa uma decisão que não pede verificação móvel. Para
        manter a ponte mínima, o destino default é a posição da primeira
        observação do incidente, usada como âncora determinística da
        ocorrência. O chamador pode fornecer um ``target`` explícito.
        """
        if not isinstance(incident, Incident):
            raise TypeError("incident deve ser Incident.")
        if not isinstance(decision, Mapping):
            raise TypeError("decision deve ser um mapping.")

        if decision.get("decision") != MOBILE_VERIFICATION_DECISION:
            return None

        key = (incident.incident_id, MOBILE_VERIFICATION_DECISION)
        existing = self._missions.get(key)
        if existing is not None:
            return existing

        mission = Mission(
            mission_id=mission_id or f"mission-{incident.incident_id}-mobile-verification",
            incident_id=incident.incident_id,
            task=MOBILE_VERIFICATION_TASK,
            target=target or incident.observations[0].position,
            required_capability=MOBILE_VERIFICATION_CAPABILITY,
            priority=priority,
        )
        self._missions[key] = mission
        return mission

