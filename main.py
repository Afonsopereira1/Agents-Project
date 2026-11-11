"""Executa a demonstração mínima SensorAgent ↔ InformantAgent."""

from __future__ import annotations

import logging
import os

import spade

from isia.agents.informant import InformantAgent
from isia.agents.sensor import SensorAgent


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Defina a variável de ambiente {name}.")
    return value


async def main():
    sensor_jid = os.environ.get("SENSOR_JID", "sensor@localhost")
    informant_jid = os.environ.get("INFORMANT_JID", "informant@localhost")
    sensor = SensorAgent(sensor_jid, required_env("SENSOR_PASSWORD"), informant_jid)
    informant = InformantAgent(informant_jid, required_env("INFORMANT_PASSWORD"))

    informant_started = False
    sensor_started = False
    try:
        await informant.start(auto_register=True)
        informant_started = True
        await sensor.start(auto_register=True)
        sensor_started = True
        await sensor.behaviour.join()
    finally:
        if sensor_started:
            await sensor.stop()
        if informant_started:
            await informant.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    spade.run(main())
