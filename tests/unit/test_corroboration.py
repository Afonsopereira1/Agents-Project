import unittest

from isia.domain.models import Observation, Position
from isia.reasoning.corroboration import (
    are_observations_compatible,
    select_eligible_sources,
)
from isia.simulation.scenario import Source


def make_observation(event_id, position, observed_at, source_id=None):
    return Observation(
        event_id=event_id,
        source_id=source_id or f"sensor-{event_id}",
        event_type="possible_incident",
        position=Position(*position),
        observed_at=observed_at,
        confidence_score=0.8,
    )


def make_sources():
    return {
        "sensor-own": Source("acoustic", 10),
        "sensor-edge": Source("visual", 5),
        "sensor-near": Source("human", 3),
        "sensor-far": Source("acoustic", 2),
    }


class TestObservationCompatibility(unittest.TestCase):

    def test_observacoes_proximas_e_no_mesmo_intervalo_sao_compativeis(self):
        first = make_observation("event-1", (0, 0), 10.0)
        second = make_observation("event-2", (3, 4), 12.0)

        self.assertTrue(are_observations_compatible(first, second, 5.0, 2.0))

    def test_observacoes_distantes_nao_sao_compativeis(self):
        first = make_observation("event-1", (0, 0), 10.0)
        second = make_observation("event-2", (6, 8), 10.0)

        self.assertFalse(are_observations_compatible(first, second, 5.0, 2.0))

    def test_observacoes_temporalmente_afastadas_nao_sao_compativeis(self):
        first = make_observation("event-1", (0, 0), 10.0)
        second = make_observation("event-2", (0, 0), 13.0)

        self.assertFalse(are_observations_compatible(first, second, 1.0, 2.0))

    def test_observacao_repetida_por_event_id_nao_e_contada_duas_vezes(self):
        first = make_observation("event-1", (0, 0), 10.0)
        repeated = make_observation("event-1", (0, 0), 10.0)

        self.assertFalse(
            are_observations_compatible(first, repeated, 1.0, 1.0)
        )

    def test_limites_invalidos_sao_rejeitados(self):
        first = make_observation("event-1", (0, 0), 10.0)
        second = make_observation("event-2", (0, 0), 10.0)

        with self.assertRaises(ValueError):
            are_observations_compatible(first, second, -1.0, 1.0)
        with self.assertRaises(ValueError):
            are_observations_compatible(first, second, 1.0, float("inf"))


class TestEligibleSources(unittest.TestCase):

    def setUp(self):
        self.observation = make_observation("event-1", (5, 0), 10.0, "sensor-own")
        self.positions = {
            "sensor-own": Position(0, 0),
            "sensor-edge": Position(0, 0),
            "sensor-near": Position(3, 0),
            "sensor-far": Position(0, 0),
        }
        self.sources = make_sources()

    def test_seleciona_sensores_dentro_e_no_limite_do_alcance(self):
        self.assertEqual(
            select_eligible_sources(self.observation, self.positions, self.sources),
            ("sensor-edge", "sensor-near"),
        )

    def test_exclui_a_fonte_original_e_considera_modalidades_diferentes(self):
        observation = make_observation("event-1", (0, 0), 10.0, "sensor-own")

        self.assertEqual(
            select_eligible_sources(observation, self.positions, self.sources),
            ("sensor-edge", "sensor-far", "sensor-near"),
        )

    def test_nao_seleciona_sensor_fora_do_alcance(self):
        observation = make_observation("event-1", (5, 0), 10.0, "sensor-own")

        self.assertNotIn(
            "sensor-far",
            select_eligible_sources(observation, self.positions, self.sources),
        )

    def test_sem_sensores_elegiveis_devolve_tuplo_vazio(self):
        observation = make_observation("event-1", (5, 5), 10.0, "sensor-own")

        self.assertEqual(
            select_eligible_sources(observation, self.positions, self.sources),
            (),
        )

    def test_resultado_e_deterministico_e_sem_duplicacoes(self):
        positions = {"sensor-z": Position(0, 0), "sensor-a": Position(0, 0)}
        sources = {"sensor-z": Source("visual", 10), "sensor-a": Source("human", 10)}
        observation = make_observation("event-1", (0, 0), 10.0)

        self.assertEqual(
            select_eligible_sources(observation, positions, sources),
            ("sensor-a", "sensor-z"),
        )


if __name__ == "__main__":
    unittest.main()
