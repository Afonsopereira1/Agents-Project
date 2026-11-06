"""Contrato do ciclo de incidentes, sem servidor ou modelos dos colegas."""

import unittest
from itertools import pairwise, product

from isia.domain.incident_state import IncidentState, validate_transition


class IncidentStateTests(unittest.TestCase):
    def test_known_states(self):
        self.assertEqual(
            {state.value for state in IncidentState},
            {
                "DETECTED", "VERIFYING", "ASSESSING", "WATCHING", "ALLOCATING",
                "RESPONDING", "CLOSED", "EXPIRED", "UNRESOLVED",
            },
        )

    def test_documented_paths(self):
        paths = (
            "DETECTED VERIFYING ASSESSING ALLOCATING RESPONDING CLOSED",
            "DETECTED VERIFYING ASSESSING WATCHING EXPIRED",
            "WATCHING VERIFYING ASSESSING ALLOCATING UNRESOLVED",
            "RESPONDING ALLOCATING RESPONDING CLOSED",
            "RESPONDING ALLOCATING UNRESOLVED",
        )
        for path in paths:
            with self.subTest(path=path):
                for current, target in pairwise(path.split()):
                    self.assertIsNone(validate_transition(current, target))

    def test_all_state_pairs(self):
        # Expectativa independente da tabela privada da implementação.
        allowed = {
            ("DETECTED", "VERIFYING"), ("VERIFYING", "ASSESSING"),
            ("ASSESSING", "WATCHING"), ("ASSESSING", "ALLOCATING"),
            ("WATCHING", "VERIFYING"), ("WATCHING", "EXPIRED"),
            ("ALLOCATING", "RESPONDING"), ("ALLOCATING", "UNRESOLVED"),
            ("RESPONDING", "CLOSED"), ("RESPONDING", "ALLOCATING"),
        }
        for current, target in product(IncidentState, repeat=2):
            for origin, destination in product(
                (current, current.value), (target, target.value)
            ):
                with self.subTest(origin=repr(origin), target=repr(destination)):
                    if (current.value, target.value) in allowed:
                        self.assertIsNone(validate_transition(origin, destination))
                    else:
                        # Inclui saltos, autorrepetição e todas as saídas terminais.
                        with self.assertRaises(ValueError):
                            validate_transition(origin, destination)

    def test_unknown_states_in_both_arguments(self):
        invalid = ("UNKNOWN", "", "detected", " DETECTED", "VERIFYING ",
                   None, True, 1, 1.0, [], {}, b"DETECTED")
        for value in invalid:
            for current, target in (
                (value, "VERIFYING"), ("DETECTED", value)
            ):
                with self.subTest(current=current, target=target):
                    with self.assertRaises(ValueError):
                        validate_transition(current, target)


if __name__ == "__main__":
    unittest.main()
