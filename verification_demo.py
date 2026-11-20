"""Demonstração da Etapa 4 com observações reais do simulador e SPADE."""

from __future__ import annotations

import logging
import os
from math import isfinite
from pathlib import Path

import spade

from isia.agents.informant import InformantAgent
from isia.agents.sensor import SensorAgent
from isia.reasoning.corroboration import select_eligible_sources
from isia.simulation.scenario import Scenario


ROOT = Path(__file__).resolve().parent


def required_env(name: str) -> str:
    """Devolver a variável de ambiente; em falta ou vazia, terminar com SystemExit.

    Args:
        name (str): Nome da variável de ambiente.

    Returns:
        str: Valor da variável, não vazio.

    Raises:
        SystemExit: Se a variável não existir ou estiver vazia.
    """
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Defina a variável de ambiente {name}.")
    return value


def configurable_float(name: str, default: float) -> float:
    """Ler do ambiente um número finito e não negativo; sem variável, usar ``default``.

    O valor por omissão passa pela mesma validação.

    Args:
        name (str): Nome da variável de ambiente.
        default (float): Valor usado quando a variável não existe.

    Returns:
        float: Valor lido (ou ``default``), finito e não negativo.

    Raises:
        SystemExit: Se o valor não for numérico, ou não for finito e não negativo.
    """
    value = os.environ.get(name)
    try:
        parsed = float(default if value is None else value)
    except (TypeError, ValueError, OverflowError) as error:
        raise SystemExit(f"A variável {name} deve ser numérica.") from error
    if not isfinite(parsed) or parsed < 0:
        raise SystemExit(f"A variável {name} deve ser finita e não negativa.")
    return parsed


def configurable_positive_int(name: str, default: int) -> int:
    """Ler do ambiente um inteiro positivo; um valor inválido termina com SystemExit.

    Sem variável, devolve ``default`` sem o validar.

    Args:
        name (str): Nome da variável de ambiente.
        default (int): Valor devolvido quando a variável não existe.

    Returns:
        int: Valor lido, positivo, ou ``default``.

    Raises:
        SystemExit: Se o valor não for um inteiro positivo.
    """
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as error:
        raise SystemExit(f"A variável {name} deve ser um inteiro positivo.") from error
    if parsed <= 0:
        raise SystemExit(f"A variável {name} deve ser um inteiro positivo.")
    return parsed


def load_observable_scenario(max_steps: int = 60) -> tuple[Scenario, str, str]:
    """Carregar config/environment.json e avançar até sensor_01 ter observações.

    Avança 1 segundo simulado de cada vez.

    Args:
        max_steps (int): Número máximo de avanços de 1 segundo.

    Returns:
        tuple[Scenario, str, str]: Cenário, id do sensor iniciador e id do informador.

    Raises:
        ValueError: Se ``max_steps`` não for um inteiro não negativo.
        RuntimeError: Se sensor_01 ou sensor_02 ficarem sem observações na janela recente.
    """
    if type(max_steps) is not int or max_steps < 0:
        raise ValueError("max_steps deve ser um inteiro não negativo.")
    scenario = Scenario.from_config(ROOT / "config" / "environment.json")
    sensor_id, informant_id = "sensor_01", "sensor_02"

    for _ in range(max_steps):
        if scenario.source(sensor_id).recent():
            break
        scenario.advance(1.0)

    # The agents receive only these local feeds, never the Scenario object.
    # Keep this access through source(...).recent() as the simulator API.
    sensor_observations = scenario.source(sensor_id).recent()
    informant_observations = scenario.source(informant_id).recent()
    if not sensor_observations:
        raise RuntimeError(
            f"O sensor iniciador {sensor_id} não tem observações locais "
            f"após o limite de {max_steps} avanços de 1 segundo."
        )
    if not informant_observations:
        raise RuntimeError(f"O informador {informant_id} não tem observações locais.")
    return scenario, sensor_id, informant_id


async def main():
    """Correr um pedido de verificação entre dois agentes com observações do simulador.

    Cada agente recebe apenas o seu feed local. O contexto de corroboração vem
    das fontes elegíveis e das variáveis CORROBORATION_MAX_DISTANCE,
    CORROBORATION_MAX_TIME_DIFFERENCE e MINIMUM_COMPATIBLE_SOURCES. No fim,
    param apenas os agentes que chegaram a arrancar.

    Raises:
        SystemExit: Se faltar uma palavra-passe ou uma variável de corroboração for inválida.
        RuntimeError: Se os sensores do cenário não tiverem observações.
    """
    scenario, sensor_id, informant_id = load_observable_scenario()
    sensor_jid = os.environ.get("SENSOR_JID", "sensor@localhost")
    informant_jid = os.environ.get("INFORMANT_JID", "informant@localhost")

    sensor = SensorAgent(sensor_jid, required_env("SENSOR_PASSWORD"), informant_jid)
    informant = InformantAgent(informant_jid, required_env("INFORMANT_PASSWORD"))
    simulation_time = scenario.world.clock.now
    sensor.set_local_observation_feed(scenario.source(sensor_id), simulation_time)
    initial_observation = scenario.source(sensor_id).recent()[0]
    eligible_source_ids = select_eligible_sources(
        initial_observation,
        scenario.world.sensors,
        scenario._sources,
    )
    sensor.set_corroboration_context(
        eligible_source_ids,
        max_distance=configurable_float("CORROBORATION_MAX_DISTANCE", 3.0),
        max_time_difference=configurable_float("CORROBORATION_MAX_TIME_DIFFERENCE", 2.0),
        minimum_compatible_sources=configurable_positive_int(
            "MINIMUM_COMPATIBLE_SOURCES", 1
        ),
    )
    logging.info(
        "Fontes elegíveis=%s; mínimo=%s (regra operacional da demonstração)",
        eligible_source_ids,
        sensor.minimum_compatible_sources,
    )
    informant.set_local_observation_feed(
        scenario.source(informant_id), informant_id, simulation_time
    )

    informant_started = False
    sensor_started = False
    try:
        await informant.start(auto_register=True)
        informant_started = True
        await sensor.start(auto_register=True)
        sensor_started = True
        await sensor.behaviour.join()
        if sensor.response is not None:
            logging.info("Resposta real recebida: %s", sensor.response.payload)
    finally:
        if sensor_started:
            await sensor.stop()
        if informant_started:
            await informant.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    spade.run(main())
