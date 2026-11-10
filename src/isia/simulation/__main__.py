"""Demonstração local: python -m isia.simulation config/environment.json."""

import argparse
from pathlib import Path

from isia.simulation.world import World


def main():
    parser = argparse.ArgumentParser(description="Mapa 2D e relógio da reserva.")
    parser.add_argument("config", type=Path, help="Ficheiro JSON do ambiente.")
    parser.add_argument("--steps", type=int, default=0, help="Número de avanços do relógio.")
    parser.add_argument("--step-seconds", type=float, default=1.0, help="Segundos por avanço.")
    args = parser.parse_args()
    if args.steps < 0:
        parser.error("--steps deve ser não negativo.")
    if not 0 < args.step_seconds < float("inf"):
        parser.error("--step-seconds deve ser finito e positivo.")

    try:
        world = World.from_config(args.config)
        print(world.render())
        for sensor_id, position in world.sensors.items():
            print(f"{sensor_id}: ({position.x}, {position.y})")
        for patrol in world.patrols:
            print(f"{patrol.resource_id} [{patrol.resource_type}]: "
                  f"({patrol.position.x}, {patrol.position.y})")
        for _ in range(args.steps):
            print(f"t = {world.clock.advance(args.step_seconds):g} s")
    except (OSError, TypeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
