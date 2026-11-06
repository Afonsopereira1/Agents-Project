
from dataclasses import dataclass


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

    def __post_init__(self):
        if not self.event_id.strip():
            raise ValueError("O identificador não pode estar vazio.")

        if not self.source_id.strip():
            raise ValueError("A fonte não pode estar vazia.")

        if not self.event_type.strip():
            raise ValueError("O tipo de evento não pode estar vazio.")

        if not isinstance(self.position, Position):
            raise TypeError("A posição deve ser do tipo Position.")

        if isinstance(self.observed_at, bool) or not isinstance(
            self.observed_at, (int, float)
        ) or not 0 <= self.observed_at < float("inf"):
            raise ValueError("O instante deve ser finito e não negativo.")

        if isinstance(self.confidence_score, bool) or not isinstance(
            self.confidence_score, (int, float)
        ) or not 0 <= self.confidence_score <= 1:
            raise ValueError("A confiança deve estar entre 0 e 1.")



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
