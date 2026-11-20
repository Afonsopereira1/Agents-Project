"""Grelha da reserva e posições iniciais validadas."""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from isia.communication.messages import model_from_dict
from isia.domain.models import Position, ResourceState
from isia.simulation.clock import SimulationClock


def _unique_keys(pairs):
    """Construir o dicionário de um objeto JSON; chave repetida levanta ValueError."""
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError(f"Chave repetida na configuração: {key}.")
        data[key] = value
    return data


@dataclass(frozen=True)
class World:
    """Mapa inicial: 0 <= x < width e 0 <= y < height, em células inteiras.

    Os sensores são fixos; patrols conserva as posições iniciais. O movimento
    atual pertence a cada agente móvel. Vários participantes podem ocupar
    a mesma célula. O relógio pertence a esta execução e avança explicitamente.

    Attributes:
        width (int): Número de colunas, inteiro positivo.
        height (int): Número de linhas, inteiro positivo.
        sensors (Mapping[str, Position]): Posição fixa de cada sensor, só de leitura.
        patrols (tuple[ResourceState, ...]): Estado inicial de cada recurso móvel.
        clock (SimulationClock): Relógio desta execução; não entra na comparação.
    """

    width: int
    height: int
    sensors: Mapping[str, Position] = field(default_factory=dict)
    patrols: tuple[ResourceState, ...] = ()
    clock: SimulationClock = field(default_factory=SimulationClock, init=False, compare=False)

    def __post_init__(self):
        """Validar dimensões, sensores e patrulhas e tornar as coleções imutáveis.

        Exige dimensões inteiras positivas, identificadores de sensor não vazios,
        posições dentro do mapa e identificadores únicos entre sensores e
        patrulhas. ``sensors`` passa a vista só de leitura e ``patrols`` a tuplo.

        Raises:
            ValueError: Se uma dimensão for inválida, um identificador de sensor estiver
                vazio, uma posição ficar fora do mapa ou houver identificadores repetidos.
            TypeError: Se ``sensors`` não for um mapeamento, uma posição de sensor não for
                ``Position`` ou uma patrulha não for ``ResourceState``.
        """
        for name, value in (("width", self.width), ("height", self.height)):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} deve ser um inteiro positivo.")
        if not isinstance(self.sensors, Mapping):
            raise TypeError("Os sensores devem associar identificadores a posições.")

        object.__setattr__(self, "sensors", MappingProxyType(dict(self.sensors)))
        object.__setattr__(self, "patrols", tuple(self.patrols))
        identifiers = set()
        for sensor_id, position in self.sensors.items():
            if not isinstance(sensor_id, str) or not sensor_id.strip():
                raise ValueError("O identificador do sensor não pode estar vazio.")
            self.validate_position(position)
            identifiers.add(sensor_id)
        for patrol in self.patrols:
            if not isinstance(patrol, ResourceState):
                raise TypeError("Cada patrulha deve ser um ResourceState.")
            if patrol.resource_id in identifiers:
                raise ValueError(f"Identificador repetido: {patrol.resource_id}.")
            self.validate_position(patrol.position)
            identifiers.add(patrol.resource_id)

    def contains(self, position: Position) -> bool:
        """Dizer se uma posição pertence à grelha, incluindo as células da borda.

        Args:
            position (Position): Célula a testar.

        Returns:
            bool: ``True`` se estiver dentro do mapa.

        Raises:
            TypeError: Se ``position`` não for ``Position``.
        """
        if not isinstance(position, Position):
            raise TypeError("A posição deve ser do tipo Position.")
        return 0 <= position.x < self.width and 0 <= position.y < self.height

    def validate_position(self, position: Position) -> None:
        """Rejeitar coordenadas fora da reserva, sem as corrigir em silêncio.

        Args:
            position (Position): Célula a validar.

        Raises:
            TypeError: Se ``position`` não for ``Position``.
            ValueError: Se a posição estiver fora do mapa.
        """
        if not self.contains(position):
            raise ValueError(
                f"Posição ({position.x}, {position.y}) fora do mapa "
                f"{self.width} x {self.height}."
            )

    @classmethod
    def from_config(cls, path: str | Path) -> "World":
        """Ler as dimensões e os participantes de um JSON, usando os modelos do domínio.

        Args:
            path (str | Path): Ficheiro JSON de configuração do ambiente.

        Returns:
            World: Mundo validado, com o relógio em zero.

        Raises:
            ValueError: Se o JSON tiver chaves repetidas ou a configuração for inválida.
        """
        with open(path, encoding="utf-8") as source:
            data = json.load(source, object_pairs_hook=_unique_keys)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "World":
        """Construir o mundo a partir de uma configuração já lida.

        Exige width, height, sensors (objeto) e patrols (lista); a única chave
        adicional aceite é ``scenario``, que tem de ser um objeto e não é usada
        aqui.

        Args:
            data (dict): Configuração já lida do JSON.

        Returns:
            World: Mundo validado, com o relógio em zero.

        Raises:
            ValueError: Se faltarem chaves, houver chaves desconhecidas, ou ``scenario``,
                ``sensors`` ou ``patrols`` tiverem um tipo inválido.
        """
        required = {"width", "height", "sensors", "patrols"}
        if (not isinstance(data, dict) or not required <= data.keys()
                or data.keys() - required - {"scenario"}):
            raise ValueError("A configuração deve conter width, height, sensors e patrols.")
        if "scenario" in data and not isinstance(data["scenario"], dict):
            raise ValueError("scenario deve ser um objeto.")
        if not isinstance(data["sensors"], dict) or not isinstance(data["patrols"], list):
            raise ValueError("sensors deve ser um objeto e patrols uma lista.")
        return cls(
            width=data["width"],
            height=data["height"],
            sensors={
                sensor_id: model_from_dict(position, Position)
                for sensor_id, position in data["sensors"].items()
            },
            patrols=tuple(model_from_dict(item, ResourceState) for item in data["patrols"]),
        )

    def render(self) -> str:
        """Mostrar o mapa no terminal, com a origem no canto inferior esquerdo.

        Returns:
            str: Grelha em texto com eixos e legenda (S: sensor, P: patrulha, *: vários).
        """
        cells = {}
        for position in self.sensors.values():
            cells[position] = "*" if position in cells else "S"
        for patrol in self.patrols:
            cells[patrol.position] = "*" if patrol.position in cells else "P"

        cell_width = max(2, len(str(self.width - 1)))
        label_width = len(str(self.height - 1))
        lines = [f"Reserva {self.width} x {self.height} | t = {self.clock.now:g} s", "y"]
        for y in reversed(range(self.height)):
            row = " ".join(
                f"{cells.get(Position(x, y), '.'):>{cell_width}}"
                for x in range(self.width)
            )
            lines.append(f"{y:>{label_width}} | {row}")
        axis = " ".join(f"{x:>{cell_width}}" for x in range(self.width))
        lines.append(f"{' ' * label_width}   {axis}  x")
        lines.append("S: sensor | P: patrulha | *: vários participantes | .: célula livre")
        return "\n".join(lines)
