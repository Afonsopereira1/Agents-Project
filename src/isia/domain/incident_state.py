from dataclasses import dataclass, replace
from enum import Enum


class IncidentStatus(Enum):
    DETECTED = "detected"
    VERIFYING = "verifying"
    ASSESSING = "assessing"
    WATCHING = "watching"
    ALLOCATING = "allocating"
    RESPONDING = "responding"
    CLOSED = "closed"
    EXPIRED = "expired"
    UNRESOLVED = "unresolved"


_ALLOWED_TRANSITIONS = {
    IncidentStatus.DETECTED: {IncidentStatus.VERIFYING},
    IncidentStatus.VERIFYING: {IncidentStatus.ASSESSING},
    IncidentStatus.ASSESSING: {
        IncidentStatus.WATCHING,
        IncidentStatus.ALLOCATING,
    },
    IncidentStatus.WATCHING: {
        IncidentStatus.VERIFYING,
        IncidentStatus.EXPIRED,
    },
    IncidentStatus.ALLOCATING: {
        IncidentStatus.RESPONDING,
        IncidentStatus.UNRESOLVED,
    },
    IncidentStatus.RESPONDING: {
        IncidentStatus.CLOSED,
        IncidentStatus.ALLOCATING,
    },
    IncidentStatus.CLOSED: set(),
    IncidentStatus.EXPIRED: set(),
    IncidentStatus.UNRESOLVED: set(),
}


@dataclass(frozen=True)
class IncidentState:
    incident_id: str
    status: IncidentStatus = IncidentStatus.DETECTED

    def __post_init__(self):
        if not isinstance(self.incident_id, str) or not self.incident_id.strip():
            raise ValueError("O identificador do incidente não pode estar vazio.")
        if not isinstance(self.status, IncidentStatus):
            raise TypeError("O estado do incidente deve ser IncidentStatus.")

    def change_status(self, new_status: IncidentStatus):
        if not isinstance(new_status, IncidentStatus):
            raise TypeError("O novo estado deve ser IncidentStatus.")
        if new_status not in _ALLOWED_TRANSITIONS[self.status]:
            raise ValueError("Transição de estado do incidente não permitida.")
        return replace(self, status=new_status)


def allowed_transitions(status: IncidentStatus) -> frozenset[IncidentStatus]:
    if not isinstance(status, IncidentStatus):
        raise TypeError("O estado do incidente deve ser IncidentStatus.")
    return frozenset(_ALLOWED_TRANSITIONS[status])
