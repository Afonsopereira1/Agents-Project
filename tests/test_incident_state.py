import unittest
from dataclasses import FrozenInstanceError

from isia.domain.incident_state import IncidentState, IncidentStatus, allowed_transitions


class TestIncidentState(unittest.TestCase):
    def test_estado_inicial(self):
        state = IncidentState("incident-001")

        self.assertIs(state.status, IncidentStatus.DETECTED)

    def test_todos_os_estados_estao_representados(self):
        self.assertEqual(
            {status.value for status in IncidentStatus},
            {
                "detected",
                "verifying",
                "assessing",
                "watching",
                "allocating",
                "responding",
                "closed",
                "expired",
                "unresolved",
            },
        )

    def test_transicoes_validas(self):
        transitions = {
            IncidentStatus.DETECTED: IncidentStatus.VERIFYING,
            IncidentStatus.VERIFYING: IncidentStatus.ASSESSING,
            IncidentStatus.ASSESSING: IncidentStatus.ALLOCATING,
            IncidentStatus.WATCHING: IncidentStatus.VERIFYING,
            IncidentStatus.ALLOCATING: IncidentStatus.RESPONDING,
            IncidentStatus.RESPONDING: IncidentStatus.CLOSED,
        }

        for origin, destination in transitions.items():
            with self.subTest(origin=origin, destination=destination):
                state = IncidentState("incident-001", origin)
                result = state.change_status(destination)

                self.assertIs(result.status, destination)
                self.assertIs(state.status, origin)

    def test_ramos_alternativos_validos(self):
        self.assertIn(IncidentStatus.WATCHING, allowed_transitions(IncidentStatus.ASSESSING))
        self.assertIn(IncidentStatus.EXPIRED, allowed_transitions(IncidentStatus.WATCHING))
        self.assertIn(IncidentStatus.UNRESOLVED, allowed_transitions(IncidentStatus.ALLOCATING))
        self.assertIn(IncidentStatus.ALLOCATING, allowed_transitions(IncidentStatus.RESPONDING))

    def test_transicao_invalida_e_estado_terminal(self):
        state = IncidentState("incident-001", IncidentStatus.CLOSED)

        with self.assertRaises(ValueError):
            state.change_status(IncidentStatus.DETECTED)

    def test_validacao(self):
        with self.assertRaises(ValueError):
            IncidentState("", IncidentStatus.DETECTED)
        with self.assertRaises(TypeError):
            IncidentState("incident-001", "detected")
        with self.assertRaises(TypeError):
            IncidentState("incident-001").change_status("verifying")

    def test_immutabilidade(self):
        state = IncidentState("incident-001")

        with self.assertRaises(FrozenInstanceError):
            state.status = IncidentStatus.VERIFYING


if __name__ == "__main__":
    unittest.main()
