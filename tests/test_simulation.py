import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from isia.domain.models import Observation, Position, ResourceState
from isia.simulation.clock import SimulationClock
from isia.simulation.world import World


CONFIG = Path(__file__).resolve().parents[1] / "config" / "environment.json"


class TestSimulation(unittest.TestCase):
    def test_ambiente_inicial_e_repeticao_independente(self):
        world = World.from_config(CONFIG)
        repeated = World.from_config(CONFIG)
        self.assertEqual((world.width, world.height), (12, 10))
        self.assertEqual(world.sensors, {
            "sensor_01": Position(4, 6), "sensor_02": Position(7, 6),
        })
        self.assertEqual(
            [(patrol.resource_id, patrol.position) for patrol in world.patrols],
            [("drone_01", Position(1, 1)), ("vehicle_01", Position(10, 1))],
        )
        self.assertTrue(all(patrol.available for patrol in world.patrols))
        self.assertEqual(world.render(), repeated.render())
        world.clock.advance(2.5)
        self.assertEqual(repeated.clock.now, 0.0)
        repeated.clock.advance(2.5)
        self.assertEqual(world.render(), repeated.render())

    def test_fronteiras_retangulares_e_mapa_minimo(self):
        world = World(3, 2)
        for position in (Position(0, 0), Position(2, 0), Position(0, 1), Position(2, 1)):
            with self.subTest(position=position):
                self.assertTrue(world.contains(position))
                world.validate_position(position)
        for position in (Position(3, 0), Position(0, 2), Position(3, 2)):
            with self.subTest(position=position):
                self.assertFalse(world.contains(position))
                with self.assertRaises(ValueError):
                    world.validate_position(position)
        self.assertTrue(World(1, 1).contains(Position(0, 0)))
        with self.assertRaises(TypeError):
            world.validate_position((1, 1))

    def test_dimensoes_invalidas(self):
        for value in (0, -1, 2.5, True, "3", None, float("inf"), float("nan")):
            for dimensions in ((value, 2), (3, value)):
                with self.subTest(dimensions=dimensions):
                    with self.assertRaises(ValueError):
                        World(*dimensions)

    def test_posicoes_iniciais_fora_do_mapa(self):
        for position in (Position(3, 0), Position(0, 2)):
            with self.subTest(position=position):
                with self.assertRaises(ValueError):
                    World(3, 2, sensors={"s1": position})
                with self.assertRaises(ValueError):
                    World(3, 2, patrols=(ResourceState("p1", "drone", position, True),))

    def test_identificadores_invalidos_e_repetidos(self):
        for sensor_id in ("", " ", 5):
            with self.subTest(sensor_id=sensor_id):
                with self.assertRaises(ValueError):
                    World(3, 2, sensors={sensor_id: Position(1, 1)})
        patrol = ResourceState("p1", "drone", Position(1, 1), True)
        with self.assertRaises(ValueError):
            World(3, 2, sensors={"p1": Position(0, 0)}, patrols=(patrol,))
        with self.assertRaises(ValueError):
            World(3, 2, patrols=(patrol, patrol))
        with self.assertRaises(TypeError):
            World(3, 2, sensors={"s1": (1, 1)})
        with self.assertRaises(TypeError):
            World(3, 2, patrols=("p1",))

    def test_configuracao_rejeita_dados_invalidos(self):
        original = json.loads(CONFIG.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "environment.json"
            for coordinate in (-1, 0.5, True, "2", None, float("inf"), float("nan")):
                for axis in ("x", "y"):
                    with self.subTest(coordinate=coordinate, axis=axis):
                        data = dict(original, sensors={"s1": {"x": 0, "y": 0}})
                        data["sensors"]["s1"][axis] = coordinate
                        path.write_text(json.dumps(data), encoding="utf-8")
                        with self.assertRaises(ValueError):
                            World.from_config(path)
            for data in ([], {}, dict(original, sensors=[]), dict(original, patrols={}),
                         dict(original, extra=1)):
                with self.subTest(data=data):
                    path.write_text(json.dumps(data), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        World.from_config(path)
            path.write_text('{"width": 2, "width": 3}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Chave repetida"):
                World.from_config(path)

    def test_posicoes_validadas_nao_podem_ser_alteradas(self):
        sensors = {"s1": Position(1, 1)}
        world = World(3, 2, sensors=sensors)
        sensors["s1"] = Position(100, 100)
        self.assertEqual(world.sensors["s1"], Position(1, 1))
        with self.assertRaises(TypeError):
            world.sensors["s1"] = Position(100, 100)
        with self.assertRaises(FrozenInstanceError):
            world.width = 0

    def test_relogio_e_instantes_do_dominio(self):
        clock = SimulationClock()
        self.assertEqual(clock.now, 0.0)
        self.assertEqual(clock.advance(), 1.0)
        self.assertEqual(clock.advance(0.25), 1.25)
        observation = Observation("obs1", "s1", "sound", Position(0, 0), clock.now, 0.8)
        clock.advance(4)
        self.assertEqual(clock.now, 5.25)
        self.assertEqual(observation.observed_at, 1.25)
        with self.assertRaises(AttributeError):
            clock.now = -1

    def test_avanco_invalido_preserva_relogio(self):
        clock = SimulationClock()
        clock.advance(2)
        for seconds in (0, -1, True, False, "1", None, float("nan"), float("inf"),
                        float("-inf"), 10 ** 400):
            with self.subTest(seconds=seconds):
                with self.assertRaises(ValueError):
                    clock.advance(seconds)
                self.assertEqual(clock.now, 2.0)
        clock.advance(1e308)
        for seconds in (1e308, 1e-10):
            with self.subTest(seconds=seconds):
                with self.assertRaises(ValueError):
                    clock.advance(seconds)
                self.assertEqual(clock.now, 1e308)

    def test_mapa_mostra_eixos_tempo_e_ocupacao_partilhada(self):
        world = World(3, 2, {"s1": Position(0, 0), "s2": Position(2, 1)}, (
            ResourceState("p1", "drone", Position(0, 0), True),
            ResourceState("p2", "vehicle", Position(1, 0), True),
        ))
        world.clock.advance(0.5)
        rendered = world.render()
        self.assertIn("t = 0.5 s", rendered)
        self.assertIn("1 |  .  .  S\n0 |  *  P  .", rendered)
        self.assertIn("0  1  2  x", rendered)


if __name__ == "__main__":
    unittest.main()
