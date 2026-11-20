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
    """Perfil de perceção de um sensor: canal, alcance, taxas de erro e confiança.

    Attributes:
        kind (str): Canal: ``acoustic``, ``visual`` ou ``human``.
        detection_range (float): Alcance euclidiano, em células.
        sensitivity (float): Fator de deteção, em [0, 1].
        false_positive_rate (float): Taxa de falsos positivos (multiplicada por
            ``sensitivity``) para eventos que não são ameaça, em [0, 1].
        false_negative_rate (float): Taxa de falsos negativos; uma ameaça é lida com
            probabilidade sensitivity × (1 − taxa), em [0, 1].
        position_error (int): Ruído máximo da posição lida, em células por eixo.
        confidence (float): Confiança atribuída às observações geradas, em [0, 1].
    """
    kind: str
    detection_range: float
    sensitivity: float = 1.0
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    position_error: int = 0
    confidence: float = 0.8

    def __post_init__(self):
        """Validar canal, alcance, taxas e confiança em [0, 1] e erro de posição.

        Raises:
            ValueError: Se o canal for desconhecido, um valor for negativo ou não finito,
                uma taxa ou a confiança passar de 1, ou ``position_error`` não for um
                inteiro não negativo.
        """
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
    """Evento de referência (threat, thunder ou tourist), fixo ou em movimento.

    Attributes:
        event_id (str): Identificador único do evento.
        kind (str): Tipo real: ``threat``, ``thunder`` ou ``tourist``.
        position (Position): Posição inicial.
        starts_at (float): Instante de início, em segundos simulados.
        duration (float): Duração, em segundos simulados; positiva.
        destination (Position | None): Destino do movimento; ``None`` se o evento é fixo.
        speed (float): Velocidade em direção ao destino, em células por segundo.
    """
    event_id: str
    kind: str
    position: Position
    starts_at: float
    duration: float
    destination: Position | None = None
    speed: float = 1.0

    def __post_init__(self):
        """Validar identificador, tipo, posições e tempos; exige duração positiva.

        Raises:
            ValueError: Se o identificador estiver vazio, o tipo for desconhecido, um tempo
                ou a velocidade for negativo ou não finito, ou o fim não for finito e posterior
                ao início.
            TypeError: Se ``position`` ou ``destination`` não forem ``Position``.
        """
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
        """Indicar se ``now`` pertence a [starts_at, starts_at + duration[.

        Args:
            now (float): Instante, em segundos simulados.

        Returns:
            bool: ``True`` se o evento estiver ativo nesse instante.
        """
        return self.starts_at <= now < self.starts_at + self.duration

    def position_at(self, now: float) -> Position:
        """Devolver a posição real do evento em ``now``.

        Sem destino ou antes do início é a posição inicial; depois do fim mantém
        a posição alcançada no último instante da duração.

        Args:
            now (float): Instante, em segundos simulados.

        Returns:
            Position: Célula onde o evento está.
        """
        elapsed = min(self.duration, max(0, now - self.starts_at))
        return position_at(self.position, self.destination or self.position, self.speed, elapsed)


def event_from_dict(item) -> Event:
    """Converter um evento JSON (posições como objetos {x, y}) em Event.

    Args:
        item (dict[str, object]): Evento lido do JSON, com os campos de ``Event``.

    Returns:
        Event: Evento validado.
    """
    values = dict(item)
    values["position"] = model_from_dict(values["position"], Position)
    if values.get("destination") is not None:
        values["destination"] = model_from_dict(values["destination"], Position)
    return Event(**values)


class ObservationFeed:
    """API entregue a uma fonte: apenas as suas observações, sem eventos reais."""

    def __init__(self, clock, window: float):
        """Inicializar o feed com o histórico vazio.

        Args:
            clock (SimulationClock): Relógio da simulação, para saber o instante atual.
            window (float): Largura da janela de leituras recentes, em segundos simulados.
        """
        self._clock = clock
        self._window = window
        self._history: list[Observation] = []

    def recent(self) -> tuple[Observation, ...]:
        """Devolver as leituras da janela inclusiva [agora - window, agora].

        Returns:
            tuple[Observation, ...]: Observações da fonte nessa janela, por ordem de geração.
        """
        return tuple(obs for obs in self._history
                     if self._clock.now - self._window <= obs.observed_at <= self._clock.now)


class Scenario:
    """O avaliador conserva este objeto; agentes recebem apenas source(id).

    Attributes:
        world (World): Mundo do cenário, com o relógio da execução.
    """

    def __init__(self, world: World, sources: dict[str, Source], events: tuple[Event, ...],
                 seed: int, corroboration_window: float = 5.0, observation_prefix: str = "obs"):
        """Inicializar o cenário: validar mundo, fontes e eventos e amostrar o instante zero.

        Fontes e eventos ficam ordenados por identificador, pelo que a amostragem
        não depende da ordem de entrada.

        Args:
            world (World): Mundo com o relógio ainda em zero.
            sources (dict[str, Source]): Perfil de cada sensor do mundo, exatamente um por
                sensor.
            events (tuple[Event, ...]): Eventos de referência, com identificadores únicos.
            seed (int): Semente do gerador aleatório da amostragem.
            corroboration_window (float): Largura da janela dos feeds, em segundos simulados.
            observation_prefix (str): Prefixo dos identificadores das observações geradas.

        Raises:
            TypeError: Se ``world`` não for ``World`` ou houver perfis ou eventos de tipo
                errado.
            ValueError: Se o relógio não estiver em zero, ``seed`` não for inteira, a janela
                for inválida, as fontes não coincidirem com os sensores, houver eventos
                repetidos ou posições fora do mapa.
        """
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
        """Ler mundo e cenário de um JSON; aqui a secção ``scenario`` é obrigatória.

        Exige exatamente seed, corroboration_window, sources e events.

        Args:
            path (str | Path): Ficheiro JSON com o mundo e a secção ``scenario``.

        Returns:
            Scenario: Cenário pronto, já amostrado no instante zero.

        Raises:
            ValueError: Se houver chaves em falta, a mais ou repetidas, ou tipos errados.
        """
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
            events = tuple(event_from_dict(item) for item in config["events"])
            return cls(world, sources, events, config["seed"], config["corroboration_window"])
        except (KeyError, TypeError) as error:
            raise ValueError("Configuração de cenário inválida ou incompleta.") from error

    def source(self, source_id: str) -> ObservationFeed:
        """Devolver o feed local da fonte.

        Args:
            source_id (str): Identificador do sensor.

        Returns:
            ObservationFeed: Feed só com as observações dessa fonte.

        Raises:
            KeyError: Se o identificador não existir.
        """
        return self._feeds[source_id]

    def advance(self, seconds: float = 1.0) -> float:
        """Avançar e amostrar no novo instante; eventos saltados não geram leituras.

        Args:
            seconds (float): Duração do avanço, em segundos simulados.

        Returns:
            float: Novo instante atual.

        Raises:
            ValueError: Se o relógio tiver sido avançado fora do cenário ou ``seconds`` não
                for finito e positivo.
        """
        if self.world.clock.now != self._sampled_at:
            raise ValueError("Usar scenario.advance() para manter tempo e amostras sincronizados.")
        now = self.world.clock.advance(seconds)
        self._steps.append(seconds)
        self._sample()
        self._sampled_at = now
        return now

    def inspect(self, position: Position, now: float, task: str) -> str:
        """Inspecionar localmente, de forma idealizada, uma posição.

        Não expõe eventos nem ground_truth: só classifica a célula visitada no
        instante indicado. A intervenção do guarda só é bem-sucedida se a ameaça
        ainda lá estiver; um guarda que chega tarde devolve not_confirmed. Não
        remove eventos globais.
        Sensibilidade e falhas de inspeção ficam para os cenários posteriores.

        Args:
            position (Position): Célula inspecionada.
            now (float): Instante da inspeção, em segundos simulados; não pode ser futuro.
            task (str): Tarefa da missão: ``verify_incident`` ou ``respond_incident``.

        Returns:
            str: ``confirmed`` se houver uma ameaça ativa na célula, ``not_confirmed`` se
                não, ou ``failed`` para uma tarefa desconhecida.

        Raises:
            ValueError: Se a posição estiver fora do mapa ou ``now`` for inválido ou futuro.
        """
        self.world.validate_position(position)
        nonnegative(now, "now")
        if now > self.world.clock.now:
            raise ValueError("A inspeção não pode consultar o futuro.")
        if task not in ("verify_incident", "respond_incident"):
            return "failed"
        return "confirmed" if any(
            event.kind == "threat" and event.active(now) and event.position_at(now) == position
            for event in self._events
        ) else "not_confirmed"

    def _sample(self) -> None:
        """Gerar as observações do instante atual para cada evento ativo e cada fonte.

        Só contam fontes de canal compatível com o evento dentro do alcance
        euclidiano. A probabilidade de leitura é sensitivity × (1 −
        false_negative_rate) para ameaças e sensitivity × false_positive_rate
        para os outros eventos. A posição observada leva ruído inteiro até
        ``position_error`` por eixo, limitado ao mapa. A ligação entre observação
        e evento fica apenas em ``_attributions``, para o avaliador.
        """
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
        """Devolver uma cópia da verdade para avaliação.

        Returns:
            dict: ``events`` (rótulo, posição real e estado de cada evento) e
                ``observations`` (ligação de cada leitura ao evento que a gerou).
        """
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
        """Gravar a configuração inicial, os avanços e os resultados.

        Nunca substitui uma execução: o ficheiro é aberto em modo ``x``.

        Args:
            path (str | Path): Novo ficheiro JSON; não pode existir.

        Raises:
            ValueError: Se o relógio tiver sido avançado fora do cenário.
        """
        if self.world.clock.now != self._sampled_at:
            raise ValueError("O relógio foi avançado fora do cenário.")
        data = {"config": self._config, "steps": self._steps,
                "finished_at": self.world.clock.now, "ground_truth": self.ground_truth,
                "observations": [model_to_dict(obs) for feed in self._feeds.values()
                                 for obs in feed._history]}
        with open(path, "x", encoding="utf-8") as output:
            json.dump(data, output, ensure_ascii=False, indent=2, allow_nan=False)
            output.write("\n")
