"""Eventos de referência e perceção local, sem dependências de SPADE."""

import json
import random
from dataclasses import dataclass
from math import hypot
from pathlib import Path

from isia.communication.messages import model_from_dict, model_to_dict
from isia.domain.models import Observation, Position
from isia.simulation.movement import nonnegative, position_at
from isia.simulation.world import World, _unique_keys


# O sinal percebido não identifica se a origem é criminosa.
SIGNALS = {"acoustic": "gunshot_like_sound", "visual": "suspicious_movement",
           "human": "suspicious_activity_report"}
CHANNELS = {"threat": frozenset(SIGNALS), "thunder": {"acoustic"},
            "tourist": {"visual", "human"}}


@dataclass(frozen=True)
class Source:
    kind: str
    detection_range: float
    sensitivity: float = 1.0
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    position_error: int = 0
    confidence: float = 0.8

    def __post_init__(self):
        if not isinstance(self.kind, str) or self.kind not in SIGNALS:
            raise ValueError("Fonte deve ser acoustic, visual ou human.")
        nonnegative(self.detection_range, "detection_range")
        for name in ("sensitivity", "false_positive_rate", "false_negative_rate", "confidence"):
            value = getattr(self, name)
            nonnegative(value, name)
            if value > 1:
                raise ValueError(f"{name} deve estar entre 0 e 1.")
        if type(self.position_error) is not int or self.position_error < 0:
            raise ValueError("position_error deve ser um inteiro não negativo.")


@dataclass(frozen=True)
class Event:
    event_id: str
    kind: str
    position: Position
    starts_at: float
    duration: float
    destination: Position | None = None
    speed: float = 1.0

    def __post_init__(self):
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ValueError("O evento precisa de um identificador.")
        if not isinstance(self.kind, str) or self.kind not in CHANNELS:
            raise ValueError("Evento deve ser threat, thunder ou tourist.")
        if not isinstance(self.position, Position):
            raise TypeError("A posição do evento deve ser Position.")
        if self.destination is not None and not isinstance(self.destination, Position):
            raise TypeError("O destino deve ser Position.")
        for name in ("starts_at", "duration", "speed"):
            nonnegative(getattr(self, name), name)
        try:
            end = self.starts_at + self.duration
        except OverflowError as error:
            raise ValueError("Duração do evento fora da capacidade do relógio.") from error
        if not self.starts_at < end < float("inf"):
            raise ValueError("O evento precisa de duração positiva e fim finito.")

    def active(self, now: float) -> bool:
        return self.starts_at <= now < self.starts_at + self.duration

    def position_at(self, now: float) -> Position:
        elapsed = min(self.duration, max(0, now - self.starts_at))
        return position_at(self.position, self.destination or self.position, self.speed, elapsed)


class ObservationFeed:
    """API entregue a uma fonte: apenas as suas observações, sem eventos reais."""

    def __init__(self, clock, window: float):
        self._clock = clock
        self._window = window
        self._history: list[Observation] = []

    def recent(self) -> tuple[Observation, ...]:
        """Janela inclusiva [agora - window, agora], no tempo da simulação."""
        return tuple(obs for obs in self._history
                     if self._clock.now - self._window <= obs.observed_at <= self._clock.now)


class Scenario:
    """O avaliador conserva este objeto; agentes recebem apenas source(id)."""

    def __init__(self, world: World, sources: dict[str, Source], events: tuple[Event, ...],
                 seed: int, corroboration_window: float = 5.0, observation_prefix: str = "obs"):
        if not isinstance(world, World):
            raise TypeError("world deve ser World.")
        if world.clock.now != 0:
            raise ValueError("O cenário deve começar com o relógio em zero.")
        if type(seed) is not int:
            raise ValueError("seed deve ser um inteiro.")
        nonnegative(corroboration_window, "corroboration_window")
        if not isinstance(sources, dict) or sources.keys() != world.sensors.keys():
            raise ValueError("Cada sensor deve ter exatamente um perfil de fonte.")
        if any(not isinstance(source, Source) for source in sources.values()):
            raise TypeError("Os perfis devem ser Source.")
        events = tuple(events)
        identifiers = set()
        for event in events:
            if not isinstance(event, Event):
                raise TypeError("Os eventos devem ser Event.")
            if event.event_id in identifiers:
                raise ValueError("Identificador de evento repetido.")
            identifiers.add(event.event_id)
            world.validate_position(event.position)
            if event.destination is not None:
                world.validate_position(event.destination)
        self.world = world
        self._sources = dict(sorted(sources.items()))
        self._events = tuple(sorted(events, key=lambda event: event.event_id))
        self._rng = random.Random(seed)
        # IDs únicos entre execuções permitem à reputação aprender sem colisões.
        self._observation_prefix = observation_prefix
        self._feeds = {key: ObservationFeed(world.clock, corroboration_window)
                       for key in self._sources}
        self._attributions: dict[str, str] = {}
        self._steps: list[float] = []
        self._sampled_at = 0.0
        self._config = {
            "width": world.width, "height": world.height,
            "sensors": {key: model_to_dict(pos) for key, pos in world.sensors.items()},
            "patrols": [model_to_dict(patrol) for patrol in world.patrols],
            "scenario": {
                "seed": seed, "corroboration_window": corroboration_window,
                "sources": {key: model_to_dict(source) for key, source in self._sources.items()},
                "events": [model_to_dict(event) for event in self._events],
            },
        }
        self._sample()

    @classmethod
    def from_config(cls, path: str | Path) -> "Scenario":
        with open(path, encoding="utf-8") as source:
            data = json.load(source, object_pairs_hook=_unique_keys)
        world = World.from_dict(data)
        try:
            config = data["scenario"]
            if set(config) != {"seed", "corroboration_window", "sources", "events"}:
                raise ValueError("scenario exige seed, corroboration_window, sources e events.")
            if not isinstance(config["sources"], dict) or not isinstance(config["events"], list):
                raise ValueError("sources deve ser um objeto e events uma lista.")
            sources = {key: Source(**value) for key, value in config["sources"].items()}
            events = []
            for item in config["events"]:
                values = dict(item)
                values["position"] = model_from_dict(values["position"], Position)
                if values.get("destination") is not None:
                    values["destination"] = model_from_dict(values["destination"], Position)
                events.append(Event(**values))
            return cls(world, sources, tuple(events), config["seed"], config["corroboration_window"])
        except (KeyError, TypeError) as error:
            raise ValueError("Configuração de cenário inválida ou incompleta.") from error

    def source(self, source_id: str) -> ObservationFeed:
        return self._feeds[source_id]

    def advance(self, seconds: float = 1.0) -> float:
        """Avança e amostra no novo instante. Eventos saltados não geram leituras."""
        if self.world.clock.now != self._sampled_at:
            raise ValueError("Usar scenario.advance() para manter tempo e amostras sincronizados.")
        now = self.world.clock.advance(seconds)
        self._steps.append(seconds)
        self._sample()
        self._sampled_at = now
        return now

    def inspect(self, position: Position, now: float, task: str) -> str:
        """Inspeção local idealizada do MVP; não expõe eventos nem ground_truth.

        Só classifica a célula visitada no instante indicado. A intervenção
        do guarda é uma ação simulada bem-sucedida, não remove eventos globais.
        Sensibilidade e falhas de inspeção ficam para os cenários posteriores.
        """
        self.world.validate_position(position)
        nonnegative(now, "now")
        if now > self.world.clock.now:
            raise ValueError("A inspeção não pode consultar o futuro.")
        if task == "respond_incident":
            return "confirmed"
        if task != "verify_incident":
            return "failed"
        return "confirmed" if any(
            event.kind == "threat" and event.active(now) and event.position_at(now) == position
            for event in self._events
        ) else "not_confirmed"

    def _sample(self) -> None:
        now = self.world.clock.now
        for event in self._events:
            if not event.active(now):
                continue
            real = event.position_at(now)
            for source_id, source in self._sources.items():
                origin = self.world.sensors[source_id]
                if (source.kind not in CHANNELS[event.kind]
                        or hypot(real.x - origin.x, real.y - origin.y) > source.detection_range):
                    continue
                probability = source.sensitivity * (
                    1 - source.false_negative_rate if event.kind == "threat"
                    else source.false_positive_rate
                )
                if self._rng.random() >= probability:
                    continue
                error = source.position_error
                position = Position(
                    min(self.world.width - 1, max(0, real.x + self._rng.randint(-error, error))),
                    min(self.world.height - 1, max(0, real.y + self._rng.randint(-error, error))),
                )
                obs_id = f"{self._observation_prefix}-{len(self._attributions) + 1:06d}"
                observation = Observation(obs_id, source_id, SIGNALS[source.kind], position,
                                          now, source.confidence)
                self._feeds[source_id]._history.append(observation)
                self._attributions[obs_id] = event.event_id

    @property
    def ground_truth(self) -> dict:
        """Cópia para avaliação: rótulos, posições reais e ligação às leituras."""
        now = self.world.clock.now
        return {
            "events": [{"event_id": event.event_id, "kind": event.kind,
                        "is_threat": event.kind == "threat",
                        "position": model_to_dict(event.position_at(now)),
                        "state": ("pending" if now < event.starts_at else
                                  "active" if event.active(now) else "ended")}
                       for event in self._events],
            "observations": dict(self._attributions),
        }

    def save_run(self, path: str | Path) -> None:
        """Regista configuração inicial, avanços e resultados; nunca substitui uma execução."""
        if self.world.clock.now != self._sampled_at:
            raise ValueError("O relógio foi avançado fora do cenário.")
        data = {"config": self._config, "steps": self._steps,
                "finished_at": self.world.clock.now, "ground_truth": self.ground_truth,
                "observations": [model_to_dict(obs) for feed in self._feeds.values()
                                 for obs in feed._history]}
        with open(path, "x", encoding="utf-8") as output:
            json.dump(data, output, ensure_ascii=False, indent=2, allow_nan=False)
            output.write("\n")
