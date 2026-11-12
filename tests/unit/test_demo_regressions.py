"""Regressões de configuração e terminação dos demonstradores."""

import os
import unittest
from unittest.mock import Mock, patch, sentinel

try:
    import spade
except ModuleNotFoundError as error:
    if error.name != "spade":
        raise
    spade = None

if spade is not None:
    import contract_net_demo
    import verification_demo


@unittest.skipUnless(spade is not None, "SPADE não está instalado")
class TestDemoFloatConfiguration(unittest.TestCase):
    variable = "ISIA_DEMO_TEST_FLOAT"

    def test_nonfinite_environment_values_are_rejected_in_both_demos(self):
        for module in (verification_demo, contract_net_demo):
            for value in ("nan", "inf", "-inf", "1e999"):
                with self.subTest(module=module.__name__, value=value):
                    with patch.dict(os.environ, {self.variable: value}):
                        with self.assertRaisesRegex(SystemExit, self.variable):
                            module.configurable_float(self.variable, 1.0)

    def test_nonfinite_and_negative_defaults_are_rejected_in_both_demos(self):
        with patch.dict(os.environ, {}, clear=True):
            for module in (verification_demo, contract_net_demo):
                for default in (float("nan"), float("inf"), -float("inf"), -1.0):
                    with self.subTest(module=module.__name__, default=default):
                        with self.assertRaisesRegex(SystemExit, self.variable):
                            module.configurable_float(self.variable, default)

    def test_positive_timeout_rejects_zero_in_environment_and_default(self):
        with patch.dict(os.environ, {self.variable: "0"}):
            with self.assertRaisesRegex(SystemExit, self.variable):
                contract_net_demo.configurable_float(self.variable, 1.0, positive=True)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(SystemExit, self.variable):
                contract_net_demo.configurable_float(self.variable, 0.0, positive=True)

    def test_finite_nonnegative_environment_values_and_defaults_are_preserved(self):
        for module in (verification_demo, contract_net_demo):
            for value in (0.0, 2.5):
                with self.subTest(module=module.__name__, value=value):
                    with patch.dict(os.environ, {self.variable: str(value)}):
                        self.assertEqual(module.configurable_float(self.variable, 1.0), value)
                    with patch.dict(os.environ, {}, clear=True):
                        self.assertEqual(module.configurable_float(self.variable, value), value)

    def test_invalid_environment_values_are_rejected_in_both_demos(self):
        for module in (verification_demo, contract_net_demo):
            for value in ("invalid", "-1"):
                with self.subTest(module=module.__name__, value=value):
                    with patch.dict(os.environ, {self.variable: value}):
                        with self.assertRaisesRegex(SystemExit, self.variable):
                            module.configurable_float(self.variable, 1.0)


@unittest.skipUnless(spade is not None, "SPADE não está instalado")
class TestObservableScenarioTermination(unittest.TestCase):
    def scenario(self, *, sensor_appears_at=None, informant_has_data=True):
        scenario = Mock()
        sensor_feed = Mock()
        sensor_feed.recent.side_effect = lambda: (
            (sentinel.sensor_observation,)
            if sensor_appears_at is not None
            and scenario.advance.call_count >= sensor_appears_at
            else ()
        )
        informant_feed = Mock()
        informant_feed.recent.return_value = (
            (sentinel.informant_observation,) if informant_has_data else ()
        )
        feeds = {"sensor_01": sensor_feed, "sensor_02": informant_feed}
        scenario.source.side_effect = feeds.__getitem__
        return scenario

    def test_missing_observations_stop_at_limit_with_source_diagnostic(self):
        scenario = self.scenario()
        with patch.object(verification_demo.Scenario, "from_config", return_value=scenario):
            with self.assertRaisesRegex(RuntimeError, "sensor_01.*3"):
                verification_demo.load_observable_scenario(max_steps=3)
        self.assertEqual(scenario.advance.call_count, 3)
        scenario.advance.assert_called_with(1.0)

    def test_initial_observation_does_not_require_an_advance(self):
        scenario = self.scenario(sensor_appears_at=0)
        with patch.object(verification_demo.Scenario, "from_config", return_value=scenario):
            self.assertEqual(
                verification_demo.load_observable_scenario(max_steps=0),
                (scenario, "sensor_01", "sensor_02"),
            )
        scenario.advance.assert_not_called()

    def test_observation_on_last_allowed_advance_is_accepted(self):
        scenario = self.scenario(sensor_appears_at=2)
        with patch.object(verification_demo.Scenario, "from_config", return_value=scenario):
            self.assertEqual(
                verification_demo.load_observable_scenario(max_steps=2),
                (scenario, "sensor_01", "sensor_02"),
            )
        self.assertEqual(scenario.advance.call_count, 2)

    def test_missing_informant_data_has_explicit_diagnostic(self):
        scenario = self.scenario(sensor_appears_at=0, informant_has_data=False)
        with patch.object(verification_demo.Scenario, "from_config", return_value=scenario):
            with self.assertRaisesRegex(RuntimeError, "informador"):
                verification_demo.load_observable_scenario(max_steps=0)
        scenario.advance.assert_not_called()

    def test_invalid_step_limits_are_rejected_before_loading(self):
        with patch.object(verification_demo.Scenario, "from_config") as load:
            for max_steps in (-1, 1.5, True, "3"):
                with self.subTest(max_steps=max_steps):
                    with self.assertRaisesRegex(ValueError, "max_steps"):
                        verification_demo.load_observable_scenario(max_steps=max_steps)
        load.assert_not_called()


if __name__ == "__main__":
    unittest.main()
