"""Seletores válidos e isolamento da configuração de falhas entre execuções."""

from copy import deepcopy
import unittest

from isia.communication.messages import MessageType

try:
    from isia.simulation.runner import FAULT_DEFAULTS, fault_settings, run_mvp
except ImportError:
    fault_settings = run_mvp = None


@unittest.skipUnless(fault_settings, "SPADE não está instalado")
class TestFaultSettingsRegressions(unittest.TestCase):
    def test_defaults_preserve_the_contract_and_none_disables_injection(self):
        self.assertIsNone(fault_settings(None))
        self.assertEqual(fault_settings({}), {
            "seed": 0, "loss": 0.0, "delay": {}, "drop": [], "duplicate": [],
            "unavailable_agents": [], "occupied_after_proposal": [],
        })

    def test_message_contract_names_are_valid_for_all_message_selectors(self):
        names = [kind.value for kind in MessageType]
        supplied = {"drop": names, "duplicate": names,
                    "delay": {name: 0.05 for name in names}}
        settings = fault_settings(supplied)
        self.assertEqual(settings["drop"], names)
        self.assertEqual(settings["duplicate"], names)
        self.assertEqual(settings["delay"], supplied["delay"])

    def test_effective_agent_and_resource_identifiers_are_accepted(self):
        supplied = {
            "unavailable_agents": ["sensor-mvp", "sensor-peer-mvp", "drone-mvp",
                                   "vehicle-mvp", "ranger-mvp"],
            "occupied_after_proposal": ["drone", "vehicle", "ranger"],
        }
        settings = fault_settings(supplied)
        self.assertEqual(settings["unavailable_agents"], supplied["unavailable_agents"])
        self.assertEqual(settings["occupied_after_proposal"], supplied["occupied_after_proposal"])

    def test_unknown_empty_and_misspelled_message_selectors_are_rejected(self):
        for selector in ("", " ", "cfp", "MISSION_RESUT", "PROPOSLA", "UNKNOWN"):
            for key in ("drop", "duplicate", "delay"):
                values = {selector: 0.05} if key == "delay" else [selector]
                with self.subTest(key=key, selector=selector):
                    with self.assertRaisesRegex(ValueError, "faults\\." + key):
                        fault_settings({key: values})
        with self.assertRaisesRegex(ValueError, "faults\\.delay"):
            fault_settings({"delay": {1: 0.05}})

    def test_agent_names_and_resource_names_do_not_have_ambiguous_aliases(self):
        invalid = {
            "unavailable_agents": ("", " ", "drone", "Drone-mvp", "unknown-mvp",
                                   "drone-mvp@localhost"),
            "occupied_after_proposal": ("", " ", "drone-mvp", "Drone", "sensor-1",
                                        "unknown"),
        }
        for key, selectors in invalid.items():
            for selector in selectors:
                with self.subTest(key=key, selector=selector):
                    with self.assertRaisesRegex(ValueError, "faults\\." + key):
                        fault_settings({key: [selector]})

    def test_mutating_each_default_collection_preserves_other_configurations(self):
        original = deepcopy(FAULT_DEFAULTS)
        changes = {"drop": ["CFP"], "duplicate": ["ACCEPT"],
                   "delay": {"STATUS": 0.1},
                   "unavailable_agents": ["drone-mvp"],
                   "occupied_after_proposal": ["vehicle"]}
        for key, value in changes.items():
            with self.subTest(key=key):
                first, second = fault_settings({}), fault_settings({})
                if key == "delay":
                    first[key].update(value)
                else:
                    first[key].extend(value)
                self.assertEqual(second, original)
                self.assertEqual(fault_settings({}), original)
                self.assertEqual(FAULT_DEFAULTS, original)

    def test_supplied_collections_are_isolated_in_both_directions(self):
        supplied = {"drop": ["CFP"], "duplicate": ["ACCEPT"],
                    "delay": {"STATUS": 0.1},
                    "unavailable_agents": ["drone-mvp"],
                    "occupied_after_proposal": ["vehicle"]}
        original = deepcopy(supplied)
        normalized = fault_settings(supplied)
        for key in supplied:
            with self.subTest(key=key):
                normalized[key].clear()
                self.assertEqual(supplied, original)
        normalized = fault_settings(supplied)
        for value in supplied.values():
            value.clear()
        for key in original:
            self.assertEqual(normalized[key], original[key])


@unittest.skipUnless(run_mvp, "SPADE não está instalado")
class TestFaultSettingsExecutionIsolation(unittest.IsolatedAsyncioTestCase):
    async def test_normalized_mutation_does_not_contaminate_later_execution(self):
        first = await run_mvp(faults={})
        normalized = fault_settings({})
        normalized["drop"].append("CFP")
        normalized["duplicate"].append("ACCEPT")
        normalized["delay"]["STATUS"] = 0.1
        normalized["unavailable_agents"].append("drone-mvp")
        normalized["occupied_after_proposal"].append("vehicle")
        second = await run_mvp(faults={})
        for report in (first, second):
            self.assertEqual((report["incident_status"], report["reason"]), ("closed", "confirmed"))
            self.assertEqual([result["source_id"] for result in report["results"]], ["drone", "ranger"])
            self.assertEqual(report["fault_log"], [])
            self.assertEqual(report["reservations"], [None, None, None])


if __name__ == "__main__":
    unittest.main()
