"""Executar o MVP: transporte local de teste ou agentes ligados a XMPP."""

import argparse
import asyncio
import json
import os
import random
from contextlib import suppress

from spade.behaviour import OneShotBehaviour

from isia.agents.drone import DroneAgent
from isia.agents.vehicle import VehicleAgent
from isia.agents.ranger import RangerAgent
from isia.agents.incident import IncidentSensorAgent
from isia.agents.informant import InformantAgent
from isia.communication.messages import model_to_dict
from isia.domain.models import Position, ResourceState
from isia.reasoning.policy import ResponsePolicy
from isia.reasoning.reputation import ReputationBook, result_from_mission
from isia.simulation.world import World
from isia.simulation.scenario import Scenario, Source, Event


SCENARIO_SEED = 6
FAULT_DEFAULTS = {"seed": 0, "loss": 0.0, "delay": {}, "drop": [], "duplicate": [],
                  "unavailable_agents": [], "occupied_after_proposal": []}


def fault_settings(faults):
    """Validar a injeção de falhas do transporte local (Etapa 8)."""
    if faults is None:
        return None
    if not isinstance(faults, dict) or set(faults) - set(FAULT_DEFAULTS):
        raise ValueError(f"faults aceita apenas {sorted(FAULT_DEFAULTS)}.")
    settings = {**FAULT_DEFAULTS, **faults}
    if type(settings["seed"]) is not int:
        raise ValueError("faults.seed deve ser inteiro.")
    if type(settings["loss"]) not in (int, float) or not 0 <= settings["loss"] <= 1:
        raise ValueError("faults.loss deve estar entre 0 e 1.")
    if not isinstance(settings["delay"], dict) or any(
            type(value) not in (int, float) or not 0 <= value < 60 for value in settings["delay"].values()):
        raise ValueError("faults.delay associa tipos de mensagem a segundos em [0, 60[.")
    for key in ("drop", "duplicate", "unavailable_agents", "occupied_after_proposal"):
        if not isinstance(settings[key], list) or any(not isinstance(v, str) for v in settings[key]):
            raise ValueError(f"faults.{key} deve ser uma lista de nomes.")
    return settings


async def run_mvp(*, xmpp=False, password="local-demo", inspection_outcomes=None,
                  interrupt_resource=None, max_seconds=10.0,
                  response_settings=None, reputation=None, faults=None):
    """O runner só fornece ambiente, relógio e transporte; agentes decidem.

    inspection_outcomes e interrupt_resource permitem testes determinísticos.
    O transporte local executa os mesmos comportamentos e contratos SPADE,
    mas não demonstra entrega pela rede XMPP.
    response_settings ativa a Etapa 7. reputation contém apenas aprendizagem
    previamente validada pelo avaliador; o sensor recebe uma cópia dos pesos.
    Com ``response_settings["adjudication"]``, o avaliador atualiza ``reputation``
    após a execução a partir dos MISSION_RESULT com cobertura suficiente.
    faults injeta perda, atraso, duplicação e indisponibilidade só no transporte
    local; não altera nem valida o servidor XMPP.
    """
    faults = fault_settings(faults)
    if faults is not None and xmpp:
        raise ValueError("A injeção de falhas só existe no transporte local.")
    world = World(8, 8, {"sensor-1": Position(2, 2), "sensor-2": Position(4, 2)})
    scenario = Scenario(world, {key: Source("acoustic", 5) for key in world.sensors},
                        (Event("event-mvp", "threat", Position(3, 2), 0, 1000),), seed=SCENARIO_SEED)
    sensor = IncidentSensorAgent("sensor-mvp@localhost", password, "sensor-peer-mvp@localhost")
    peer = InformantAgent("sensor-peer-mvp@localhost", password)
    sensor.set_local_observation_feed(scenario.source("sensor-1"), 0.0)
    sensor.set_corroboration_context(("sensor-2",), 3.0, 2.0, 1)
    if response_settings is not None:
        if reputation is None:
            reputation = ReputationBook(**response_settings["reputation"])
        sensor.set_response_policy(
            ResponsePolicy(**response_settings["policy"]),
            reputation.snapshot(world.sensors), response_settings["sources"],
            severity=response_settings["severity"],
            default_reputation=reputation.score("sensor-1"),
        )
    peer.set_local_observation_feed(scenario.source("sensor-2"), "sensor-2", 0.0)
    mobiles = []
    for agent_class, name, origin, capability in (
        (DroneAgent, "drone", Position(0, 2), "mobile_verification"),
        (VehicleAgent, "vehicle", Position(0, 0), "mobile_verification"),
        (RangerAgent, "ranger", Position(5, 5), "incident_response"),
    ):
        agent = agent_class(f"{name}-mvp@localhost", password,
                            ResourceState(name, name, origin, True, 100.0), (capability,),
                            minimum_autonomy_percent=10.0, eta_seconds=0.0,
                            energy_cost_percent=0.0, load=0.0)
        outcome = (inspection_outcomes or {}).get(name)
        inspect = scenario.inspect if outcome is None else lambda position, now, task, value=outcome: value
        agent.configure_execution(world, inspect)
        mobiles.append(agent)
    sensor.configure_mvp({str(a.jid): a.resource.resource_id for a in mobiles[:2]},
                         {str(mobiles[2].jid): "ranger"}, receive_timeout=0.5 if not xmpp else 2.0)
    agents = [*mobiles, peer, sensor]
    tasks, started, transcript, fault_log = [], [], [], []
    rng = random.Random(faults["seed"] if faults else 0)
    by_resource = {agent.resource.resource_id: agent for agent in mobiles}

    async def clock_loop():
        interrupted = False
        while True:
            await asyncio.sleep(0.01)
            # O tempo físico só avança enquanto existe uma missão em execução.
            # A negociação continua a ter timeout real independente.
            if any(a.execution is not None and not a.execution.finished for a in mobiles):
                now = scenario.advance(1.0)
                sensor.simulated_time = now
                for agent in mobiles:
                    agent.set_simulated_time(now)
                    if (not interrupted and agent.resource.resource_id == interrupt_resource
                            and agent.execution is not None and not agent.execution.finished
                            and agent.execution.resource.position != agent.execution.home):
                        agent.execution.interrupt()
                        interrupted = True

    async def local_behaviour(behaviour):
        while True:
            await behaviour.run()
            if isinstance(behaviour, OneShotBehaviour):
                return

    try:
        if xmpp:
            for agent in agents:
                await agent.start(auto_register=True)
                started.append(agent)
        else:
            for agent in agents:
                await agent.setup()
            routes = {str(agent.jid): agent.behaviours for agent in agents}
            for agent in agents:
                for behaviour in agent.behaviours:
                    inbox = asyncio.Queue()
                    behaviour._local_inbox = inbox

                    async def receive(timeout=None, queue=inbox):
                        try:
                            return await asyncio.wait_for(queue.get(), timeout)
                        except TimeoutError:
                            return None

                    async def deliver(message, delay=0.0):
                        if delay:
                            await asyncio.sleep(delay)
                        for target in routes.get(str(message.to), ()):
                            if target.template is not None and target.template.match(message):
                                await target._local_inbox.put(message)

                    async def send(message, sender=str(agent.jid)):
                        message.sender = sender
                        body = json.loads(message.body)
                        transcript.append({"sender": sender, "to": str(message.to), "body": body})
                        if faults is None:
                            return await deliver(message)
                        kind = body["message_type"]
                        ends = {sender.split("@")[0], str(message.to).split("@")[0]}
                        entry = {"message_id": body["message_id"], "type": kind, "to": str(message.to)}
                        if (kind in faults["drop"] or ends & set(faults["unavailable_agents"])
                                or (faults["loss"] and rng.random() < faults["loss"])):
                            fault_log.append({"fault": "lost", **entry})
                            return
                        if kind == "PROPOSAL" and body["source_id"] in faults["occupied_after_proposal"]:
                            # O recurso é tomado por outra missão entre PROPOSAL e ACCEPT.
                            by_resource[body["source_id"]].reservation.reserve(
                                "external-mission", resource_id=body["source_id"])
                            fault_log.append({"fault": "occupied", **entry})
                        copies = 2 if kind in faults["duplicate"] else 1
                        delay = faults["delay"].get(kind, 0.0)
                        if copies == 2:
                            fault_log.append({"fault": "duplicated", **entry})
                        if delay:
                            fault_log.append({"fault": "delayed", "seconds": delay, **entry})
                        for _ in range(copies):
                            if delay:
                                tasks.append(asyncio.create_task(deliver(message, delay)))
                            else:
                                await deliver(message)
                    behaviour.receive, behaviour.send = receive, send
            tasks.extend(asyncio.create_task(local_behaviour(b)) for a in agents for b in a.behaviours)
        tasks.append(asyncio.create_task(clock_loop()))
        async with asyncio.timeout(max_seconds):
            while not sensor.cycle_done or any(a.execution and not a.execution.finished for a in mobiles):
                for task in tasks:
                    if task.done() and not task.cancelled() and task.exception():
                        raise task.exception()
                await asyncio.sleep(0.005)
        updates = []
        adjudication = (response_settings or {}).get("adjudication")
        if adjudication is not None and sensor.incident_state is not None:
            incident_id = sensor.incident_state.incident_id
            # Avaliador: o sensor já terminou; nenhuma atualização volta à decisão desta execução.
            updates = [reputation.update(obs, incident_id,
                                         result_from_mission(result, obs, incident_id, **adjudication))
                       for result in sensor.results for obs in sensor.incident_observations]
        timeline = sorted([
            *sensor.timeline,
            *(entry for agent in mobiles for execution in agent.executions for entry in execution.timeline),
        ], key=lambda entry: entry["time"])
        return {"transport": "xmpp" if xmpp else "local",
                "response_settings": response_settings,
                "scenario_seed": SCENARIO_SEED, "faults": faults, "fault_log": fault_log,
                "reputation_scores": sensor.reputation_scores,
                "reputation_updates": updates,
                "decision": sensor.decision, "verification": sensor.verification_history,
                "incident_status": sensor.incident_state.status.value if sensor.incident_state else None,
                "reason": sensor.close_reason,
                "results": [result.to_dict() for result in sensor.results],
                "missions": [model_to_dict(mission) for mission in sensor.missions],
                "resources": [model_to_dict(agent.reservation.resource_state) for agent in mobiles],
                "reservations": [agent.reservation.reserved_mission_id for agent in mobiles],
                "timeline": timeline, "messages": transcript}
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
        for agent in reversed(started):
            await agent.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xmpp", action="store_true", help="Usar servidor XMPP em localhost")
    parser.add_argument("--policy", metavar="JSON", help="Ativar a política da Etapa 7 com esta configuração")
    parser.add_argument("--faults", metavar="JSON", help="Injetar falhas da Etapa 8 no transporte local")
    args = parser.parse_args()
    settings = faults = None
    if args.policy:
        with open(args.policy, encoding="utf-8") as stream:
            settings = json.load(stream)
    if args.faults:
        if args.xmpp:
            parser.error("--faults só funciona com o transporte local.")
        with open(args.faults, encoding="utf-8") as stream:
            faults = json.load(stream)
    password = os.environ.get("XMPP_PASSWORD", "local-demo")
    if args.xmpp and "XMPP_PASSWORD" not in os.environ:
        parser.error("Defina XMPP_PASSWORD para as cinco contas locais do MVP.")
    async def demo():
        print(json.dumps(await run_mvp(xmpp=args.xmpp, password=password,
                                      response_settings=settings, faults=faults),
                         ensure_ascii=False, indent=2))
    if args.xmpp:
        import spade
        spade.run(demo())
    else:
        asyncio.run(demo())


if __name__ == "__main__":
    main()
