"""Estados de incidente e transições permitidas, independentes de SPADE."""

from enum import StrEnum


class IncidentState(StrEnum):
    """Fase operacional do incidente; não representa o resultado da missão."""

    DETECTED = "DETECTED"
    VERIFYING = "VERIFYING"
    ASSESSING = "ASSESSING"
    WATCHING = "WATCHING"
    ALLOCATING = "ALLOCATING"
    RESPONDING = "RESPONDING"
    CLOSED = "CLOSED"
    EXPIRED = "EXPIRED"
    UNRESOLVED = "UNRESOLVED"


_TRANSITIONS = {
    IncidentState.DETECTED: (IncidentState.VERIFYING,),
    IncidentState.VERIFYING: (IncidentState.ASSESSING,),
    IncidentState.ASSESSING: (IncidentState.WATCHING, IncidentState.ALLOCATING),
    IncidentState.WATCHING: (IncidentState.VERIFYING, IncidentState.EXPIRED),
    IncidentState.ALLOCATING: (IncidentState.RESPONDING, IncidentState.UNRESOLVED),
    IncidentState.RESPONDING: (IncidentState.CLOSED, IncidentState.ALLOCATING),
    IncidentState.CLOSED: (),
    IncidentState.EXPIRED: (),
    IncidentState.UNRESOLVED: (),
}


def validate_transition(
    current: IncidentState | str, target: IncidentState | str
) -> None:
    """Aceita enum ou texto exato; lança ValueError para estados ou pares inválidos.

    Não altera o incidente. O consumidor verifica evidência, prazos, tentativas,
    correlação, reserva e resultado antes de aplicar a transição (docs/message-contract.md, § 6).
    Estados terminais não têm saída; repetir o estado também é inválido.
    """
    current = IncidentState(current)
    target = IncidentState(target)
    if target not in _TRANSITIONS[current]:
        raise ValueError(f"Transição de incidente inválida: {current} -> {target}")
