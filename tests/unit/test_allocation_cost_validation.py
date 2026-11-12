import math
import unittest

from isia.domain.models import Mission, Position, ResourceState
from isia.reasoning.allocation import (
    build_cfp_message,
    evaluate_cfp,
    select_best_proposal,
)


class TestAllocationCostValidation(unittest.TestCase):
    def setUp(self):
        mission = Mission(
            "mission-1", "incident-1", "verify_incident", Position(1, 1),
            "mobile_verification", 0,
        )
        self.cfp = build_cfp_message(mission, 20.0, 35.0)

    def proposal(self, name, *, eta=4.0, energy=1.0, load=0.5):
        return evaluate_cfp(
            self.cfp, ResourceState(name, "drone", Position(0, 0), True, 100.0),
            ("mobile_verification",), current_time=20.0,
            minimum_autonomy_percent=0.0, eta_seconds=eta,
            energy_cost_percent=energy, load=load,
        )

    def assert_order_independent(self, proposals, expected, **parameters):
        for order in (proposals, tuple(reversed(proposals))):
            result = select_best_proposal(self.cfp, order, **parameters)
            self.assertEqual(result.winner_bid.resource_id, expected)
            self.assertTrue(math.isfinite(result.winner_cost))

    def test_zero_eta_weight_skips_extreme_normalization(self):
        proposals = (self.proposal("resource-a", energy=1.0),
                     self.proposal("resource-b", energy=2.0))
        self.assert_order_independent(
            proposals, "resource-a", eta_weight=0.0,
            eta_scale_seconds=5e-324,
        )

    def test_zero_energy_weight_skips_extreme_normalization(self):
        proposals = (self.proposal("resource-a", eta=4.0),
                     self.proposal("resource-b", eta=8.0))
        self.assert_order_independent(
            proposals, "resource-a", energy_weight=0.0,
            energy_scale_percent=5e-324,
        )

    def test_zero_load_weight_skips_extreme_normalization(self):
        proposals = (self.proposal("resource-a", eta=4.0),
                     self.proposal("resource-b", eta=8.0))
        self.assert_order_independent(
            proposals, "resource-a", load_weight=0.0,
            load_scale=5e-324,
        )

    def test_nonfinite_cost_is_rejected_before_ordering(self):
        proposals = (self.proposal("resource-a"), self.proposal("resource-b"))
        for parameters in (
            {"eta_scale_seconds": 5e-324},
            {"energy_scale_percent": 5e-324},
            {"load_scale": 5e-324},
            {"eta_weight": 1e308, "eta_scale_seconds": 1.0},
            {"eta_weight": 1e308, "energy_weight": 1e308,
             "load_weight": 1e308, "eta_scale_seconds": 4.0,
             "energy_scale_percent": 1.0, "load_scale": 0.5},
        ):
            for order in (proposals, tuple(reversed(proposals))):
                with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                    select_best_proposal(self.cfp, order, **parameters)

    def test_normal_formula_and_tiebreaker_are_preserved(self):
        proposals = (self.proposal("resource-b"), self.proposal("resource-a"))
        self.assert_order_independent(proposals, "resource-a")
        result = select_best_proposal(self.cfp, proposals)
        self.assertAlmostEqual(result.winner_cost, 4.0 / 60.0 + 1.0 / 100.0 + 0.5)

    def test_extreme_finite_scale_can_still_produce_a_valid_cost(self):
        proposals = (self.proposal("resource-a"), self.proposal("resource-b"))
        self.assert_order_independent(proposals, "resource-a", eta_scale_seconds=1e308)
