"""Máquina de estados de um incidente e as transições permitidas."""

from dataclasses import dataclass, replace
from enum import Enum


class IncidentStatus(Enum):
    """Fases de um incidente; ``CLOSED``, ``EXPIRED`` e ``UNRESOLVED`` são finais.

    Attributes:
        DETECTED: Alerta recebido, ainda por verificar.
        VERIFYING: À espera de corroboração das fontes.
        ASSESSING: Corroboração feita; a decidir se cria uma missão.
        WATCHING: Corroboração insuficiente para uma missão; à espera de nova evidência
            (no MVP passa logo a ``EXPIRED``).
        ALLOCATING: À procura de um recurso para a missão.
        RESPONDING: Com uma missão em curso.
        CLOSED: Encerrado com o resultado de uma missão ou como alerta duplicado.
        EXPIRED: A ameaça deixou de ser vista dentro do prazo, ou a corroboração foi
            insuficiente e não surgiu nova evidência.
        UNRESOLVED: Nenhuma missão chegou a um resultado conclusivo (sem recurso, sem
            resposta ou só ``inconclusive``/``failed``).
    """
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
    IncidentStatus.DETECTED: {
        IncidentStatus.VERIFYING,
        IncidentStatus.CLOSED,  # alerta duplicado: um iniciador vizinho fica com a mesma ameaça
        IncidentStatus.EXPIRED,  # a ameaça deixou de ser vista durante o aviso aos vizinhos
    },
    IncidentStatus.VERIFYING: {IncidentStatus.ASSESSING},
    IncidentStatus.ASSESSING: {
        IncidentStatus.WATCHING,
        IncidentStatus.ALLOCATING,
        IncidentStatus.CLOSED,
    },
    IncidentStatus.WATCHING: {
        IncidentStatus.VERIFYING,
        IncidentStatus.EXPIRED,
    },
    IncidentStatus.ALLOCATING: {
        IncidentStatus.RESPONDING,
        IncidentStatus.UNRESOLVED,
        IncidentStatus.EXPIRED,  # prazo de validade: a ameaça deixou de ser vista
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
    """Estado imutável de um incidente; começa em ``DETECTED`` por omissão.

    Attributes:
        incident_id (str): Identificador do incidente.
        status (IncidentStatus): Fase atual.
    """
    incident_id: str
    status: IncidentStatus = IncidentStatus.DETECTED

    def __post_init__(self):
        """Exigir identificador não vazio e estado válido.

        Raises:
            ValueError: Se o identificador estiver vazio.
            TypeError: Se o estado não for ``IncidentStatus``.
        """
        if not isinstance(self.incident_id, str) or not self.incident_id.strip():
            raise ValueError("O identificador do incidente não pode estar vazio.")
        if not isinstance(self.status, IncidentStatus):
            raise TypeError("O estado do incidente deve ser IncidentStatus.")

    def change_status(self, new_status: IncidentStatus):
        """Devolver uma cópia no novo estado, sem alterar a instância atual.

        Args:
            new_status (IncidentStatus): Fase pedida.

        Returns:
            IncidentState: Nova instância na fase pedida.

        Raises:
            TypeError: Se o estado não for ``IncidentStatus``.
            ValueError: Se a transição não constar de ``_ALLOWED_TRANSITIONS``.
        """
        if not isinstance(new_status, IncidentStatus):
            raise TypeError("O novo estado deve ser IncidentStatus.")
        if new_status not in _ALLOWED_TRANSITIONS[self.status]:
            raise ValueError("Transição de estado do incidente não permitida.")
        return replace(self, status=new_status)
