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
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Defina a variável de ambiente {name}.")
    return value


def configurable_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    try:
        parsed = float(default if value is None else value)
    except (TypeError, ValueError, OverflowError) as error:
        raise SystemExit(f"A variável {name} deve ser numérica.") from error
    if not isfinite(parsed) or parsed < 0:
        raise SystemExit(f"A variável {name} deve ser finita e não negativa.")
    return parsed


def configurable_positive_int(name: str, default: int) -> int:
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
