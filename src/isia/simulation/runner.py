"""Executar o MVP: transporte local de teste ou agentes ligados a XMPP."""

import argparse
import asyncio
import json
import os
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
from isia.reasoning.reputation import ReputationBook
from isia.simulation.world import World
from isia.simulation.scenario import Scenario, Source, Event


async def run_mvp(*, xmpp=False, password="local-demo", inspection_outcomes=None,
                  interrupt_resource=None, max_seconds=10.0,
                  response_settings=None, reputation=None):
    """O runner só fornece ambiente, relógio e transporte; agentes decidem.

    inspection_outcomes e interrupt_resource permitem testes determinísticos.
    O transporte local executa os mesmos comportamentos e contratos SPADE,
    mas não demonstra entrega pela rede XMPP.
    response_settings ativa a Etapa 7. reputation contém apenas aprendizagem
    previamente validada pelo avaliador; o sensor recebe uma cópia dos pesos.
    """
    world = World(8, 8, {"sensor-1": Position(2, 2), "sensor-2": Position(4, 2)})
    scenario = Scenario(world, {key: Source("acoustic", 5) for key in world.sensors},
                        (Event("event-mvp", "threat", Position(3, 2), 0, 1000),), seed=6)
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
    tasks, started, transcript = [], [], []

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

                    async def send(message, sender=str(agent.jid)):
                        message.sender = sender
                        transcript.append({"sender": sender, "to": str(message.to),
                                           "body": json.loads(message.body)})
                        for target in routes.get(str(message.to), ()):
                            if target.template is not None and target.template.match(message):
                                await target._local_inbox.put(message)
                    behaviour.receive, behaviour.send = receive, send
            tasks.extend(asyncio.create_task(local_behaviour(b)) for a in agents for b in a.behaviours)
        tasks.append(asyncio.create_task(clock_loop()))
        async with asyncio.timeout(max_seconds):
            while not sensor.cycle_done or any(a.execution and not a.execution.finished for a in mobiles):
                for task in tasks:
                    if task.done() and not task.cancelled() and task.exception():
                        raise task.exception()
                await asyncio.sleep(0.005)
        timeline = sorted([
            *sensor.timeline,
            *(entry for agent in mobiles for execution in agent.executions for entry in execution.timeline),
        ], key=lambda entry: entry["time"])
        return {"transport": "xmpp" if xmpp else "local",
                "response_settings": response_settings,
                "reputation_scores": sensor.reputation_scores,
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
    args = parser.parse_args()
    settings = None
    if args.policy:
        with open(args.policy, encoding="utf-8") as stream:
            settings = json.load(stream)
    password = os.environ.get("XMPP_PASSWORD", "local-demo")
    if args.xmpp and "XMPP_PASSWORD" not in os.environ:
        parser.error("Defina XMPP_PASSWORD para as cinco contas locais do MVP.")
    async def demo():
        print(json.dumps(await run_mvp(xmpp=args.xmpp, password=password,
                                      response_settings=settings), ensure_ascii=False, indent=2))
    if args.xmpp:
        import spade
        spade.run(demo())
    else:
        asyncio.run(demo())


if __name__ == "__main__":
    main()
