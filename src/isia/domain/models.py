
from dataclasses import dataclass, replace
from enum import Enum

from isia.domain.validation import is_finite_number


@dataclass(frozen=True)
class Position:
    x: int
    y: int

    def __post_init__(self):
        if type(self.x) is not int or type(self.y) is not int:
            raise TypeError("As coordenadas devem ser números inteiros.")

        if self.x < 0 or self.y < 0:
            raise ValueError("As coordenadas não podem ser negativas.")



@dataclass(frozen=True)
class Observation:
    event_id: str
    source_id: str
    event_type: str
    position: Position
    observed_at: float
    confidence_score: float
    intensity_score: float | None = None

    def __post_init__(self):
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ValueError("O identificador não pode estar vazio.")

        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("A fonte não pode estar vazia.")

        if not isinstance(self.event_type, str) or not self.event_type.strip():
            raise ValueError("O tipo de evento não pode estar vazio.")

        if not isinstance(self.position, Position):
            raise TypeError("A posição deve ser do tipo Position.")

        if not is_finite_number(self.observed_at) or self.observed_at < 0:
            raise ValueError("O instante deve ser finito e não negativo.")

        if isinstance(self.confidence_score, bool) or not isinstance(
            self.confidence_score, (int, float)
        ) or not 0 <= self.confidence_score <= 1:
            raise ValueError("A confiança deve estar entre 0 e 1.")

        if self.intensity_score is not None and (
            not is_finite_number(self.intensity_score)
            or not 0 <= self.intensity_score <= 1
        ):
            raise ValueError("A intensidade deve estar entre 0 e 1.")



@dataclass(frozen=True)
class Incident:
    incident_id: str
    observations: tuple[Observation, ...]

    def __post_init__(self):
        if not isinstance(self.incident_id, str) or not self.incident_id.strip():
            raise ValueError("O identificador do incidente não pode estar vazio.")

        if not isinstance(self.observations, tuple):
            raise TypeError("As observações devem estar num tuplo.")

        if not self.observations:
            raise ValueError("O incidente precisa de pelo menos uma observação.")

        if any(not isinstance(obs, Observation) for obs in self.observations):
            raise TypeError("Todas as observações devem ser do tipo Observation.")

        ids = [obs.event_id for obs in self.observations]

        if len(ids) != len(set(ids)):
            raise ValueError("Não podem existir observações repetidas.")


class ResourceStatus(Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    MOVING = "moving"
    VERIFYING = "verifying"
    RETURNING = "returning"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ResourceState:
    resource_id: str
    resource_type: str
    position: Position
    available: bool
    autonomy_percent: float | None = None
    status: ResourceStatus | None = None

    def __post_init__(self):
        if not isinstance(self.resource_id, str) or not self.resource_id.strip():
            raise ValueError("O identificador do recurso não pode estar vazio.")

        if not isinstance(self.resource_type, str) or not self.resource_type.strip():
            raise ValueError("O tipo de recurso não pode estar vazio.")

        if not isinstance(self.position, Position):
            raise TypeError("A posição deve ser do tipo Position.")

        if not isinstance(self.available, bool):
            raise TypeError("A disponibilidade deve ser True ou False.")

        if self.autonomy_percent is not None and (
            not is_finite_number(self.autonomy_percent)
            or not 0 <= self.autonomy_percent <= 100
        ):
            raise ValueError("A autonomia deve estar entre 0 e 100.")

        status = self.status
        if status is None:
            status = (
                ResourceStatus.AVAILABLE
                if self.available
                else ResourceStatus.UNAVAILABLE
            )
            object.__setattr__(self, "status", status)
        elif not isinstance(status, ResourceStatus):
            raise TypeError("O estado do recurso deve ser do tipo ResourceStatus.")

        expected_available = status is ResourceStatus.AVAILABLE
        if self.available != expected_available:
            raise ValueError(
                "A disponibilidade não é coerente com o estado do recurso."
            )

    def change_status(self, new_status: ResourceStatus):
        allowed_transitions = {
            ResourceStatus.AVAILABLE: {ResourceStatus.RESERVED},
            ResourceStatus.RESERVED: {
                ResourceStatus.MOVING,
                ResourceStatus.AVAILABLE,
            },
            ResourceStatus.MOVING: {ResourceStatus.VERIFYING, ResourceStatus.RETURNING, ResourceStatus.UNAVAILABLE},
            ResourceStatus.VERIFYING: {
                ResourceStatus.RETURNING,
                ResourceStatus.UNAVAILABLE,
            },
            ResourceStatus.RETURNING: {ResourceStatus.AVAILABLE, ResourceStatus.UNAVAILABLE},
            ResourceStatus.UNAVAILABLE: {ResourceStatus.AVAILABLE},
        }

        if not isinstance(new_status, ResourceStatus):
            raise TypeError("O novo estado deve ser do tipo ResourceStatus.")

        if new_status not in allowed_transitions[self.status]:
            raise ValueError("Transição de estado não permitida.")

        return replace(
            self,
            available=new_status is ResourceStatus.AVAILABLE,
            status=new_status,
        )

class MissionStatus(Enum):
    """
    Represent the possible status of a patrol mission.

    Attributes:
        PROPOSED: Mission created and awaiting resource allocation.
        RESERVED: Mission assigned to a resource but not started yet.
        RUNNING: Mission currently being executed.
        DONE: Mission successfully completed.
        FAILED: Mission execution failed
    """
    PROPOSED = "proposed"
    RESERVED = "reserved"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"



@dataclass(frozen=True)
class Mission:
    """
    Represent a patrol mission created in response to an incident.

    Attributes:
        mission_id (str): Unique identifier of the mission.
        incident_id (str): Identifier of the associated incident.
        task (str): Task to be performed during the mission.
        target (Position): Target position of the mission.
        required_capability (str): Required capability to execute the mission.
        priority (int): Non-negative integer representing the priority of the mission.
        status (MissionStatus): Current mission status, initially PROPOSED.
    """

    mission_id: str
    incident_id: str
    task: str
    target: Position
    required_capability: str
    priority: int
    status: MissionStatus = MissionStatus.PROPOSED  #Inicia, por defeito, no estado "proposed"

    def __post_init__(self):
        """
        Validate the mission attributes after initialization.

        Raises:
            ValueError: If an identifier, task or required capability is missing or the priority is invalid.
            TypeError: If the target or status has an invalid type.
        """
        if not isinstance(self.mission_id, str) or not self.mission_id.strip():
            raise ValueError("O identificador da missão não pode estar vazio.")

        if not isinstance(self.incident_id, str) or not self.incident_id.strip():
            raise ValueError("O identificador do incidente não pode estar vazio.")

        if not isinstance(self.task, str) or not self.task.strip():
            raise ValueError("O tipo da tarefa não pode estar vazio.")

        if not isinstance(self.target, Position):
            raise TypeError("O destino deve ser do tipo Position.")

        if not isinstance(self.required_capability, str) or not self.required_capability.strip():
            raise ValueError("A capacidade necessária não pode estar vazia.")

        if type(self.priority) is not int or self.priority < 0:
            raise ValueError("A prioridade deve ser um inteiro não negativo.")

        if not isinstance(self.status, MissionStatus):
            raise TypeError("O estado da missão deve ser do tipo MissionStatus.")

    def change_status(self, new_status: MissionStatus):
        """
        Return a new mission with the updated status if the transition is valid.

        Args:
            new_status (MissionStatus): Requested new mission status.

        Returns:
            Mission: A new mission instance with updated status.

        Raises:
            TypeError: If the new status is not a MissionStatus.
            ValueError: If the requested status transition is invalid.
        """
        allowed_transitions = {
            MissionStatus.PROPOSED: {MissionStatus.RESERVED},
            MissionStatus.RESERVED: {MissionStatus.RUNNING},
            MissionStatus.RUNNING: {MissionStatus.DONE, MissionStatus.FAILED},
            MissionStatus.DONE: set(),
            MissionStatus.FAILED: set()
        }

        if not isinstance(new_status, MissionStatus):
            raise TypeError("O novo estado é inválido.")

        if new_status not in allowed_transitions[self.status]:
            raise ValueError("Transição de estado não permitida.")

        return replace(self, status=new_status)

@dataclass(frozen=True)
class Bid:
    """
    Represents a resource's bid to execute a patrol mission.

    Attributes:
        mission_id (str): Identifier of the mission being bid on.
        resource_id (str): Identifier of the resource submitting the bid.
        eta (float): Estimated time of arrival at the mission target.
        energy_cost (float): Estimated energy cost of executing the mission.
        load (float): Workload value reported by the resource.
    """

    mission_id: str
    resource_id: str
    eta: float
    energy_cost: float
    load: float

    def __post_init__(self):
        """Validate the bid attributes after initialization.

        Raises:
            ValueError: If an identifier is missing or if the eta, energy_cost and load is not a non-negative finite number.
        """

        if not isinstance(self.mission_id, str) or not self.mission_id.strip():
            raise ValueError("O identificador da missão não pode estar vazio.")

        if not isinstance(self.resource_id, str) or not self.resource_id.strip():
            raise ValueError("O identificador do recurso não pode estar vazio.")

        if not is_finite_number(self.eta) or self.eta < 0:
            raise ValueError("O tempo estimado deve ser finito e não negativo.")

        if not is_finite_number(self.energy_cost) or self.energy_cost < 0:
            raise ValueError("O custo energético deve ser finito e não negativo.")

        if (
            not is_finite_number(self.load)
            or not 0 <= self.load <= 1
        ):
            raise ValueError("A carga de trabalho deve estar entre 0 e 1.")
