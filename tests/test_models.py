
import unittest
from dataclasses import FrozenInstanceError

from isia.domain.models import Position, Observation, Incident



class TestPosition(unittest.TestCase):

    def test_posicao_valida(self):
        posicao = Position(2, 3)

        self.assertEqual(posicao.x, 2)
        self.assertEqual(posicao.y, 3)

    def test_coordenadas_negativas(self):
        with self.assertRaises(ValueError):
            Position(-1, 3)

    def test_coordenadas_nao_inteiras(self):
        with self.assertRaises(TypeError):
            Position(2.5, 3)

    def test_posicao_imutavel(self):
        posicao = Position(2, 3)

        with self.assertRaises(FrozenInstanceError):
            posicao.x = 5
            

class TestObservation(unittest.TestCase):

    def test_observacao_valida(self):
        observacao = Observation(
            event_id="obs-001",
            source_id="sensor_01",
            event_type="gunshot_like_sound",
            position=Position(2, 3),
            observed_at=15.0,
            confidence_score=0.8
        )

        self.assertEqual(observacao.source_id, "sensor_01")
        self.assertEqual(observacao.position, Position(2, 3))
        self.assertEqual(observacao.confidence_score, 0.8)

    def test_confianca_invalida(self):
        with self.assertRaises(ValueError):
            Observation(
                event_id="obs-002",
                source_id="sensor_01",
                event_type="gunshot_like_sound",
                position=Position(2, 3),
                observed_at=15.0,
                confidence_score=1.5
            )
            
    
    def test_identificador_vazio(self):
        with self.assertRaises(ValueError):
            Observation(
                event_id="",
                source_id="sensor_01",
                event_type="gunshot_like_sound",
                position=Position(2, 3),
                observed_at=15.0,
                confidence_score=0.8
            )

    def test_posicao_incorreta(self):
        with self.assertRaises(TypeError):
            Observation(
                event_id="obs-003",
                source_id="sensor_01",
                event_type="gunshot_like_sound",
                position=(2, 3),
                observed_at=15.0,
                confidence_score=0.8
            )


class TestIncident(unittest.TestCase):

    def test_incidente_valido(self):
        obs1 = Observation(
            "obs-001", "sensor_01", "gunshot_like_sound",
            Position(2, 3), 15.0, 0.8
        )

        obs2 = Observation(
            "obs-002", "sensor_02", "gunshot_like_sound",
            Position(3, 3), 16.0, 0.7
        )

        incidente = Incident("inc-001", (obs1, obs2))

        self.assertEqual(incidente.incident_id, "inc-001")
        self.assertEqual(len(incidente.observations), 2)

    def test_observacoes_duplicadas(self):
        obs1 = Observation(
            "obs-001", "sensor_01", "gunshot_like_sound",
            Position(2, 3), 15.0, 0.8
        )

        with self.assertRaises(ValueError):
            Incident("inc-001", (obs1, obs1))
            
    
    def test_incidente_sem_identificador(self):
        obs = Observation(
            "obs-001", "sensor_01", "gunshot_like_sound",
            Position(2, 3), 15.0, 0.8
        )

        with self.assertRaises(ValueError):
            Incident("", (obs,))

    def test_incidente_sem_observacoes(self):
        with self.assertRaises(ValueError):
            Incident("inc-001", ())





if __name__ == "__main__":
    unittest.main()
