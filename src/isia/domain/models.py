"""Modelos de domínio imutáveis, validados na construção."""

from dataclasses import dataclass, replace
from enum import Enum

from isia.domain.validation import is_finite_number


@dataclass(frozen=True)
class Position:
    """Célula da grelha com coordenadas inteiras não negativas.

    Attributes:
        x (int): Coluna, a contar da esquerda a partir de 0.
        y (int): Linha, a contar de baixo a partir de 0.
    """
    x: int
    y: int

    def __post_init__(self):
        """Exigir coordenadas ``int`` e não negativas.

        Raises:
            TypeError: Se alguma coordenada não for exatamente ``int`` (``bool`` também é recusado).
            ValueError: Se alguma coordenada for negativa.
        """
        if type(self.x) is not int or type(self.y) is not int:
            raise TypeError("As coordenadas devem ser números inteiros.")

        if self.x < 0 or self.y < 0:
            raise ValueError("As coordenadas não podem ser negativas.")



@dataclass(frozen=True)
class Observation:
    """Leitura de uma fonte: tipo de evento, posição, instante e confiança em [0, 1].

    Attributes:
        event_id (str): Identificador único da observação.
        source_id (str): Fonte que a produziu (sensor ou informador).
        event_type (str): Tipo de evento observado.
        position (Position): Célula onde o evento foi visto.
        observed_at (float): Instante da leitura, em segundos simulados.
        confidence_score (float): Confiança da fonte, em [0, 1].
        intensity_score (float | None): Intensidade em [0, 1]; ``None`` se a fonte não a mede.
    """
    event_id: str
    source_id: str
    event_type: str
    position: Position
    observed_at: float
    confidence_score: float
    intensity_score: float | None = None

    def __post_init__(self):
        """Validar identificadores não vazios, instante finito e pontuações em [0, 1].

        Raises:
            TypeError: Se a posição não for ``Position``.
            ValueError: Se um identificador ou o tipo estiver vazio, o instante for negativo ou
                não finito, ou uma pontuação estiver fora de [0, 1].
        """
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
    """Observações agrupadas sob um identificador de incidente.

    Attributes:
        incident_id (str): Identificador do incidente.
        observations (tuple[Observation, ...]): Observações, pelo menos uma e sem
            ``event_id`` repetidos.
    """
    incident_id: str
    observations: tuple[Observation, ...]

    def __post_init__(self):
        """Exigir um tuplo não vazio de ``Observation`` com ``event_id`` distintos.

        Raises:
            TypeError: Se ``observations`` não for tuplo ou tiver elementos que não são
                ``Observation``.
            ValueError: Se o identificador estiver vazio, não houver observações ou houver
                ``event_id`` repetidos.
        """
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
    """Estados do ciclo de um recurso móvel, da disponibilidade ao regresso.

    Attributes:
        AVAILABLE: Livre para receber uma missão.
        RESERVED: Reservado para uma missão que ainda não começou.
        MOVING: A deslocar-se para o alvo.
        VERIFYING: A inspecionar o alvo.
        RETURNING: A regressar à base.
        UNAVAILABLE: Fora de serviço (por exemplo, sem energia).
    """
    AVAILABLE = "available"
    RESERVED = "reserved"
    MOVING = "moving"
    VERIFYING = "verifying"
    RETURNING = "returning"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ResourceState:
    """Estado imutável de um recurso; ``available`` acompanha sempre ``status``.

    Attributes:
        resource_id (str): Identificador do recurso.
        resource_type (str): Tipo de recurso (ex.: ``drone``, ``vehicle``).
        position (Position): Célula atual.
        available (bool): ``True`` só quando ``status`` é ``AVAILABLE``.
        autonomy_percent (float | None): Energia restante, em % de 0 a 100; ``None`` se
            desconhecida.
        status (ResourceStatus | None): Estado do ciclo; se omitido, é deduzido de
            ``available``.
    """
    resource_id: str
    resource_type: str
    position: Position
    available: bool
    autonomy_percent: float | None = None
    status: ResourceStatus | None = None

    def __post_init__(self):
        """Validar os campos e deduzir ``status`` de ``available`` quando omitido.

        Raises:
            TypeError: Se ``position``, ``available`` ou ``status`` tiverem um tipo inválido.
            ValueError: Se um identificador ou o tipo estiver vazio, a autonomia estiver fora
                de [0, 100] ou ``available`` não coincidir com ``status is AVAILABLE``.
        """
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
        """Devolver uma cópia no novo estado, com ``available`` recalculado.

        Args:
            new_status (ResourceStatus): Estado pedido.

        Returns:
            ResourceState: Nova instância no estado pedido; a atual não muda.

        Raises:
            TypeError: Se o estado não for ``ResourceStatus``.
            ValueError: Se a transição não for permitida a partir do estado atual.
        """
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
    Estados possíveis de uma missão.

    Attributes:
        PROPOSED: Missão criada, à espera de um recurso.
        RESERVED: Atribuída a um recurso, mas ainda não iniciada.
        RUNNING: Em execução.
        DONE: Concluída com um resultado (confirmed, not_confirmed ou inconclusive).
        FAILED: Terminou com resultado ``failed``.
    """
    PROPOSED = "proposed"
    RESERVED = "reserved"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"



@dataclass(frozen=True)
class Mission:
    """
    Missão (verificação por patrulha ou resposta por ranger) criada em resposta a uma ocorrência.

    Attributes:
        mission_id (str): Identificador único da missão.
        incident_id (str): Identificador da ocorrência associada.
        task (str): Tarefa a executar.
        target (Position): Posição de destino.
        required_capability (str): Capacidade necessária para a executar.
        priority (int): Prioridade, inteiro não negativo.
        status (MissionStatus): Estado atual; começa em PROPOSED.
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
        Validar os atributos da missão depois de criada.

        Raises:
            ValueError: Se faltar um identificador, a tarefa ou a capacidade, ou se a
                prioridade não for um inteiro não negativo.
            TypeError: Se o destino ou o estado tiverem um tipo inválido.
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
        Devolver uma nova missão com o estado atualizado, se a transição for válida.

        Transições permitidas: PROPOSED → RESERVED → RUNNING → DONE ou FAILED.

        Args:
            new_status (MissionStatus): Novo estado pedido.

        Returns:
            Mission: Uma nova instância com o estado atualizado.

        Raises:
            TypeError: Se o novo estado não for um MissionStatus.
            ValueError: Se a transição não for permitida.
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
    Proposta de um recurso para executar uma missão.

    Attributes:
        mission_id (str): Missão a que a proposta se refere.
        resource_id (str): Recurso que faz a proposta.
        eta (float): Tempo estimado de chegada ao destino.
        energy_cost (float): Custo de energia estimado da missão.
        load (float): Carga de trabalho declarada pelo recurso, em [0, 1].
    """

    mission_id: str
    resource_id: str
    eta: float
    energy_cost: float
    load: float

    def __post_init__(self):
        """Validar os atributos da proposta depois de criada.

        Raises:
            ValueError: Se faltar um identificador, se ``eta`` ou ``energy_cost`` não forem
                finitos e não negativos, ou se ``load`` estiver fora de [0, 1].
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
