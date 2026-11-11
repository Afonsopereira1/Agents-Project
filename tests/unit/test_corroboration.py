import unittest

from isia.domain.models import Observation, Position
from isia.reasoning.corroboration import are_observations_compatible


def make_observation(event_id, position, observed_at):
    return Observation(
        event_id=event_id,
        source_id=f"sensor-{event_id}",
        event_type="possible_incident",
        position=Position(*position),
        observed_at=observed_at,
        confidence_score=0.8,
    )


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


if __name__ == "__main__":
    unittest.main()
