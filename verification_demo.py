"""Demonstração da Etapa 4 com observações reais do simulador e SPADE."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import spade

from isia.agents.informant import InformantAgent
from isia.agents.sensor import SensorAgent
from isia.simulation.scenario import Scenario


ROOT = Path(__file__).resolve().parent


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Defina a variável de ambiente {name}.")
    return value


def load_observable_scenario() -> tuple[Scenario, str, str]:
    scenario = Scenario.from_config(ROOT / "config" / "environment.json")
    sensor_id, informant_id = "sensor_01", "sensor_02"

    while not scenario.source(sensor_id).recent():
        scenario.advance(1.0)

    # The agents receive only these local feeds, never the Scenario object.
    # Keep this access through source(...).recent() as the simulator API.
    sensor_observations = scenario.source(sensor_id).recent()
    informant_observations = scenario.source(informant_id).recent()
    if not sensor_observations:
        raise RuntimeError("O sensor iniciador não tem observações locais.")
    if not informant_observations:
        raise RuntimeError("O informador não tem observações locais.")
    return scenario, sensor_id, informant_id


async def main():
    scenario, sensor_id, informant_id = load_observable_scenario()
    sensor_jid = os.environ.get("SENSOR_JID", "sensor@localhost")
    informant_jid = os.environ.get("INFORMANT_JID", "informant@localhost")

    sensor = SensorAgent(sensor_jid, required_env("SENSOR_PASSWORD"), informant_jid)
    informant = InformantAgent(informant_jid, required_env("INFORMANT_PASSWORD"))
    simulation_time = scenario.world.clock.now
    sensor.set_local_observation_feed(scenario.source(sensor_id), simulation_time)
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
