"""Demonstração local: python -m isia.simulation config/environment.json."""

import argparse
import json
from pathlib import Path
from tempfile import mkdtemp

from isia.communication.messages import model_to_dict
from isia.simulation.scenario import Scenario


def main():
    parser = argparse.ArgumentParser(description="Ambiente 2D e observações da reserva.")
    parser.add_argument("config", type=Path, help="Ficheiro JSON do ambiente.")
    parser.add_argument("--steps", type=int, default=0, help="Número de avanços do relógio.")
    parser.add_argument("--step-seconds", type=float, default=1.0, help="Segundos por avanço.")
    parser.add_argument("--output", type=Path, help="Novo JSON para registar a execução.")
    args = parser.parse_args()
    if args.steps < 0:
        parser.error("--steps deve ser não negativo.")
    if not 0 < args.step_seconds < float("inf"):
        parser.error("--step-seconds deve ser finito e positivo.")

    try:
        scenario = Scenario.from_config(args.config)
        world = scenario.world
        print(world.render())
        for sensor_id, position in world.sensors.items():
            print(f"{sensor_id}: ({position.x}, {position.y})")
        for patrol in world.patrols:
            print(f"{patrol.resource_id} [{patrol.resource_type}]: "
                  f"({patrol.position.x}, {patrol.position.y})")
        for step in range(args.steps + 1):
            if step:
                scenario.advance(args.step_seconds)
            print(f"t = {world.clock.now:g} s")
            for source_id in world.sensors:
                for observation in scenario.source(source_id).recent():
                    if observation.observed_at == world.clock.now:
                        print(json.dumps(model_to_dict(observation), ensure_ascii=False))
        output = args.output
        if output is None:
            directory = Path("results/simulation")
            directory.mkdir(parents=True, exist_ok=True)
            output = Path(mkdtemp(prefix="run-", dir=directory)) / "run.json"
        scenario.save_run(output)
        print(f"Registo para avaliação: {output}")
    except (OSError, TypeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
