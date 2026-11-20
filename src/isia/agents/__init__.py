"""Agentes SPADE: comportamentos, Templates e troca de mensagens (P1).

As decisões não estão aqui: os comportamentos chamam funções de `isia.reasoning`.

- `isia.agents.incident`: `IncidentSensorAgent`, o sensor que inicia e coordena uma ocorrência.
- `isia.agents.sensor`: `SensorAgent`, a base do iniciador; pede e avalia a verificação.
- `isia.agents.informant`: `InformantAgent`, responde a pedidos de verificação com as suas observações.
- `isia.agents.mobile`: `MobileResourceAgent`, responde a CFP, reserva e executa missões.
- `isia.agents.drone`, `isia.agents.vehicle`, `isia.agents.ranger`: subclasses vazias de
  `MobileResourceAgent`; a capacidade e os parâmetros de cada uma vêm do runner.
"""

from isia.agents.informant import InformantAgent
from isia.agents.mobile import MobileResourceAgent
from isia.agents.sensor import SensorAgent

__all__ = ["InformantAgent", "MobileResourceAgent", "SensorAgent"]
