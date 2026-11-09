
import unittest
from dataclasses import FrozenInstanceError, replace

from isia.domain.models import (
    Position,
    Observation,
    Incident,
    ResourceState,
    ResourceStatus,
    Mission,
    MissionStatus,
    Bid,
)



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

    def test_identificadores_com_tipo_invalido(self):
        argumentos = {
            "event_id": "obs-003",
            "source_id": "sensor_01",
            "event_type": "gunshot_like_sound",
            "position": Position(2, 3),
            "observed_at": 15.0,
            "confidence_score": 0.8,
        }

        for campo in ("event_id", "source_id", "event_type"):
            with self.subTest(campo=campo):
                dados = dict(argumentos)
                dados[campo] = 42
                with self.assertRaises(ValueError):
                    Observation(**dados)


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


class TestResourceState(unittest.TestCase):

    def test_recurso_valido(self):
        recurso = ResourceState(
            resource_id="drone_01",
            resource_type="drone",
            position=Position(5, 7),
            available=True,
            autonomy_percent=80.0,
        )

        self.assertEqual(recurso.resource_id, "drone_01")
        self.assertEqual(recurso.position, Position(5, 7))
        self.assertTrue(recurso.available)
        self.assertEqual(recurso.autonomy_percent, 80.0)

    def test_autonomia_invalida(self):
        with self.assertRaises(ValueError):
            ResourceState(
                resource_id="drone_01",
                resource_type="drone",
                position=Position(5, 7),
                available=True,
                autonomy_percent=150.0,
            )

    def test_recurso_sem_identificador(self):
        with self.assertRaises(ValueError):
            ResourceState(
                resource_id="",
                resource_type="drone",
                position=Position(5, 7),
                available=True,
                autonomy_percent=80.0,
            )

    def test_tipo_de_recurso_invalido(self):
        with self.assertRaises(ValueError):
            ResourceState("r1", "  ", Position(5, 7), True)

        with self.assertRaises(ValueError):
            ResourceState("r1", 42, Position(5, 7), True)

    def test_identificador_de_recurso_com_tipo_invalido(self):
        with self.assertRaises(ValueError):
            ResourceState(42, "drone", Position(5, 7), True)

    def test_disponibilidade_invalida(self):
        with self.assertRaises(TypeError):
            ResourceState(
                resource_id="drone_01",
                resource_type="drone",
                position=Position(5, 7),
                available="sim",
                autonomy_percent=80.0,
            )

    def test_posicao_invalida(self):
        with self.assertRaises(TypeError):
            ResourceState(
                resource_id="drone_01",
                resource_type="drone",
                position=(5, 7),
                available=True,
                autonomy_percent=80.0,
            )

    def test_autonomia_nao_definida(self):
        recurso = ResourceState(
            resource_id="ranger_01",
            resource_type="ranger",
            position=Position(3, 2),
            available=True,
            autonomy_percent=None,
        )

        self.assertIsNone(recurso.autonomy_percent)

    def test_estado_por_omissao_mantem_compatibilidade(self):
        disponivel = ResourceState("r1", "drone", Position(1, 1), True)
        indisponivel = ResourceState("r2", "drone", Position(1, 1), False)

        self.assertIs(disponivel.status, ResourceStatus.AVAILABLE)
        self.assertIs(indisponivel.status, ResourceStatus.UNAVAILABLE)

    def test_todos_os_estados(self):
        self.assertEqual(
            {status.value for status in ResourceStatus},
            {"available", "reserved", "moving", "verifying", "returning", "unavailable"},
        )

    def test_estado_explicitamente_valido(self):
        recurso = ResourceState(
            "drone_01",
            "drone",
            Position(1, 1),
            False,
            status=ResourceStatus.RESERVED,
        )

        self.assertIs(recurso.status, ResourceStatus.RESERVED)
        self.assertFalse(recurso.available)

    def test_estado_tem_de_ser_resource_status(self):
        with self.assertRaises(TypeError):
            ResourceState("r1", "drone", Position(1, 1), False, status="reserved")

    def test_estado_e_disponibilidade_coerentes(self):
        with self.assertRaises(ValueError):
            ResourceState(
                "r1",
                "drone",
                Position(1, 1),
                True,
                status=ResourceStatus.RESERVED,
            )

        with self.assertRaises(ValueError):
            ResourceState(
                "r1",
                "drone",
                Position(1, 1),
                False,
                status=ResourceStatus.AVAILABLE,
            )

    def test_transicoes_permitidas(self):
        caminhos = (
            (ResourceStatus.AVAILABLE, ResourceStatus.RESERVED),
            (ResourceStatus.RESERVED, ResourceStatus.MOVING),
            (ResourceStatus.MOVING, ResourceStatus.VERIFYING),
            (ResourceStatus.VERIFYING, ResourceStatus.RETURNING),
            (ResourceStatus.RETURNING, ResourceStatus.AVAILABLE),
            (ResourceStatus.RESERVED, ResourceStatus.AVAILABLE),
            (ResourceStatus.MOVING, ResourceStatus.UNAVAILABLE),
            (ResourceStatus.VERIFYING, ResourceStatus.UNAVAILABLE),
            (ResourceStatus.UNAVAILABLE, ResourceStatus.AVAILABLE),
        )

        for origem, destino in caminhos:
            with self.subTest(origem=origem, destino=destino):
                recurso = ResourceState(
                    "r1",
                    "drone",
                    Position(1, 1),
                    origem is ResourceStatus.AVAILABLE,
                    status=origem,
                )
                resultado = recurso.change_status(destino)

                self.assertIs(resultado.status, destino)
                self.assertEqual(resultado.available, destino is ResourceStatus.AVAILABLE)
                self.assertIs(recurso.status, origem)

    def test_transicoes_proibidas(self):
        for origem in ResourceStatus:
            for destino in ResourceStatus:
                permitida = {
                    (ResourceStatus.AVAILABLE, ResourceStatus.RESERVED),
                    (ResourceStatus.RESERVED, ResourceStatus.MOVING),
                    (ResourceStatus.RESERVED, ResourceStatus.AVAILABLE),
                    (ResourceStatus.MOVING, ResourceStatus.VERIFYING),
                    (ResourceStatus.MOVING, ResourceStatus.UNAVAILABLE),
                    (ResourceStatus.VERIFYING, ResourceStatus.RETURNING),
                    (ResourceStatus.VERIFYING, ResourceStatus.UNAVAILABLE),
                    (ResourceStatus.RETURNING, ResourceStatus.AVAILABLE),
                    (ResourceStatus.UNAVAILABLE, ResourceStatus.AVAILABLE),
                }
                if (origem, destino) in permitida:
                    continue

                with self.subTest(origem=origem, destino=destino):
                    recurso = ResourceState(
                        "r1",
                        "drone",
                        Position(1, 1),
                        origem is ResourceStatus.AVAILABLE,
                        status=origem,
                    )
                    with self.assertRaises(ValueError):
                        recurso.change_status(destino)

    def test_transicao_tem_de_receber_resource_status(self):
        recurso = ResourceState("r1", "drone", Position(1, 1), True)

        with self.assertRaises(TypeError):
            recurso.change_status("reserved")

    def test_resource_state_e_imutavel(self):
        recurso = ResourceState("r1", "drone", Position(1, 1), True)

        with self.assertRaises(FrozenInstanceError):
            recurso.status = ResourceStatus.RESERVED

    def test_autonomia_rejeita_valores_invalidos(self):
        for autonomia in (-1, 101, float("nan"), float("inf"), float("-inf"), True, "80"):
            with self.subTest(autonomia=autonomia):
                with self.assertRaises(ValueError):
                    ResourceState("r1", "drone", Position(1, 1), True, autonomia)


class TestMission(unittest.TestCase):

    def test_mission_valida(self):
        mission = Mission(
            mission_id="mission-001",
            incident_id="inc-001",
            task="verify_incident",
            target=Position(2, 3),
            required_capability="mobile_verification",
            priority=2
        )

        self.assertEqual(mission.mission_id, "mission-001")
        self.assertEqual(mission.incident_id, "inc-001")
        self.assertEqual(mission.task, "verify_incident")
        self.assertEqual(mission.target, Position(2, 3))
        self.assertEqual(mission.required_capability, "mobile_verification")
        self.assertEqual(mission.priority, 2)
        self.assertEqual(mission.status, MissionStatus.PROPOSED)

    def test_identificador_vazio(self):
        with self.assertRaises(ValueError):
            Mission(
                mission_id="",
                incident_id="inc-001",
                task="verify_incident",
                target=Position(2, 3),
                required_capability="mobile_verification",
                priority=2
            )

    def test_incident_id_vazio(self):
        with self.assertRaises(ValueError):
            Mission(
                "M1",
                "",
                "verify",
                Position(2, 3),
                "mobile_verification",
                2
            )

    def test_task_vazia(self):
        with self.assertRaises(ValueError):
            Mission(
                "M1",
                "I1",
                "",
                Position(2, 3),
                "mobile_verification",
                2
            )

    def test_target_invalido(self):
        with self.assertRaises(TypeError):
            Mission(
                "M1",
                "I1",
                "verify",
                (2, 3),
                "mobile_verification",
                2
            )

    def test_capacidade_vazia(self):
        with self.assertRaises(ValueError):
            Mission(
                "M1",
                "I1",
                "verify",
                Position(2, 3),
                "",
                2
            )

    def test_prioridade_negativa(self):
        with self.assertRaises(ValueError):
            Mission(
                "M1",
                "I1",
                "verify",
                Position(2, 3),
                "mobile_verification",
                -1
            )

    def test_transicao_valida(self):
        mission = Mission(
            "mission-001",
            "inc-001",
            "verify_incident",
            Position(2, 3),
            "mobile_verification",
            2
        )

        new_mission = mission.change_status(MissionStatus.RESERVED)

        self.assertEqual(new_mission.status, MissionStatus.RESERVED)

        self.assertEqual(mission.status, MissionStatus.PROPOSED)

    def test_transicao_invalida(self):
        mission = Mission(
            "mission-001",
            "inc-001",
            "verify_incident",
            Position(2, 3),
            "mobile_verification",
            2
        )

        with self.assertRaises(ValueError):
            mission.change_status(MissionStatus.RUNNING)

    def test_missao_concluida(self):
        mission = Mission(
            "mission-001",
            "inc-001",
            "verify_incident",
            Position(2, 3),
            "mobile_verification",
            1
        )

        mission = mission.change_status(MissionStatus.RESERVED)
        mission = mission.change_status(MissionStatus.RUNNING)
        mission = mission.change_status(MissionStatus.DONE)

        self.assertEqual(mission.status, MissionStatus.DONE)

    def test_missao_falhada(self):
        mission = Mission(
            "mission-001",
            "inc-001",
            "verify_incident",
            Position(2, 3),
            "mobile_verification",
            2
        )

        mission = mission.change_status(MissionStatus.RESERVED)
        mission = mission.change_status(MissionStatus.RUNNING)
        mission = mission.change_status(MissionStatus.FAILED)

        self.assertEqual(mission.status, MissionStatus.FAILED)

    def test_missao_concluida_nao_muda_estado(self):
        mission = Mission(
            "mission-001",
            "inc-001",
            "verify_incident",
            Position(2, 3),
            "mobile_verification",
            2
        )

        mission = mission.change_status(MissionStatus.RESERVED)
        mission = mission.change_status(MissionStatus.RUNNING)
        mission = mission.change_status(MissionStatus.DONE)

        with self.assertRaises(ValueError):
            mission.change_status(MissionStatus.FAILED)

        self.assertEqual(mission.status, MissionStatus.DONE)

    def test_transicao_tipo_invalido(self):
        mission = Mission(
            "mission-001",
            "inc-001",
            "verify_incident",
            Position(2, 3),
            "mobile_verification",
            2
        )

        with self.assertRaises(TypeError):
            mission.change_status("RUNNING")

    def test_status_invalido(self):
        with self.assertRaises(TypeError):
            Mission(
                "mission-001",
                "inc-001",
                "verify_incident",
                Position(2, 3),
                "mobile_verification", 2,
                "running"
            )

    def test_missao_falhada_nao_muda_estado(self):
        mission = Mission(
            "mission-001",
            "inc-001",
            "verify_incident",
            Position(2, 3),
            "mobile_verification",
            2
        )

        mission = mission.change_status(MissionStatus.RESERVED)
        mission = mission.change_status(MissionStatus.RUNNING)
        mission = mission.change_status(MissionStatus.FAILED)

        with self.assertRaises(ValueError):
            mission.change_status(MissionStatus.DONE)

    def test_prioridade_booleana(self):
        with self.assertRaises(ValueError):
            Mission(
                "mission-001",
                "inc-001",
                "verify_incident",
                Position(2, 3),
                "mobile_verification",
                True
            )

    def test_todas_as_transicoes(self):
        base = Mission(
            mission_id="mission-001",
            incident_id="inc-001",
            task="verify_incident",
            target=Position(2, 3),
            required_capability="mobile_verification",
            priority=2
        )

        permitidas = {
            (MissionStatus.PROPOSED, MissionStatus.RESERVED),
            (MissionStatus.RESERVED, MissionStatus.RUNNING),
            (MissionStatus.RUNNING, MissionStatus.DONE),
            (MissionStatus.RUNNING, MissionStatus.FAILED),
        }

        for origem in MissionStatus:
            for destino in MissionStatus:
                with self.subTest(origem=origem, destino=destino):
                    mission = replace(base, status=origem)

                    if (origem, destino) in permitidas:
                        resultado = mission.change_status(destino)

                        self.assertEqual(
                            resultado,
                            replace(mission, status=destino)
                        )
                    else:
                        with self.assertRaises(ValueError):
                            mission.change_status(destino)

                    self.assertEqual(mission.status, origem)


class TestBid(unittest.TestCase):

    def test_bid_valido(self):
        bid = Bid(
            "mission-001",
            "drone-001",
            5.0,
            20.0,
            0.2
        )

        self.assertEqual(bid.mission_id, "mission-001")
        self.assertEqual(bid.resource_id, "drone-001")
        self.assertEqual(bid.eta, 5.0)
        self.assertEqual(bid.energy_cost, 20.0)
        self.assertEqual(bid.load, 0.2)

    def test_mission_id_invalido(self):
        with self.assertRaises(ValueError):
            Bid(
                "",
                "drone-001",
                5.0,
                20.0,
                0.2
            )

    def test_resource_id_invalido(self):
        with self.assertRaises(ValueError):
            Bid(
                "mission-001",
                "  ",
                5.0,
                20.0,
                0.2
            )

    def test_eta_negativo(self):
        with self.assertRaises(ValueError):
            Bid(
                "mission-001",
                "drone-001",
                -5.0,
                20.0,
                0.2
            )

    def test_energy_cost_negativo(self):
        with self.assertRaises(ValueError):
            Bid(
                "mission-001",
                "drone-001",
                5.0,
                -20.0,
                0.2
            )

    def test_load_negativo(self):
        with self.assertRaises(ValueError):
            Bid(
                "mission-001",
                "drone-001",
                5.0,
                20.0,
                -0.2
            )

    def test_eta_tipo_invalido(self):
        with self.assertRaises(ValueError):
            Bid(
                "mission-001",
                "drone-001",
                "cinco",
                20.0,
                0.2
            )

    def test_energy_cost_infinito(self):
        with self.assertRaises(ValueError):
            Bid(
                "mission-001",
                "drone-001",
                5.0,
                float("inf"),
                0.2
            )

    def test_load_nan(self):
        with self.assertRaises(ValueError):
            Bid(
                "mission-001",
                "drone-001",
                5.0,
                20.0,
                float("nan")
            )

    def test_eta_booleano(self):
        with self.assertRaises(ValueError):
            Bid(
                "mission-001",
                "drone-001",
                True,
                20.0,
                0.2
            )

    def test_valores_numericos_invalidos(self):
        invalidos = (
            -1,
            -0.5,
            True,
            False,
            "cinco",
            None,
            float("nan"),
            float("inf"),
            float("-inf"),
        )

        for campo in ("eta", "energy_cost", "load"):
            for valor in invalidos:
                with self.subTest(campo=campo, valor=valor):
                    dados = {
                        "mission_id": "mission-001",
                        "resource_id": "drone-001",
                        "eta": 5.0,
                        "energy_cost": 20.0,
                        "load": 0.2,
                    }
                    dados[campo] = valor

                    with self.assertRaises(ValueError):
                        Bid(**dados)

    def test_valores_numericos_validos(self):
        for campo in ("eta", "energy_cost", "load"):
            for valor in (0, 0.0, 1, 0.5):
                with self.subTest(campo=campo, valor=valor):
                    dados = {
                        "mission_id": "mission-001",
                        "resource_id": "drone-001",
                        "eta": 5.0,
                        "energy_cost": 20.0,
                        "load": 0.2,
                    }
                    dados[campo] = valor

                    bid = Bid(**dados)

                    self.assertEqual(getattr(bid, campo), valor)

if __name__ == "__main__":
    unittest.main()
