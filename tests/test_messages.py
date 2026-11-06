"""Contrato JSON proposto; sem modelos dos colegas, SPADE ou XMPP."""

import json
import re
import unittest
from copy import deepcopy
from pathlib import Path

from isia.communication.messages import (
    MessageType, from_json, to_json, validate_envelope, validate_message,
    validate_metadata, validate_reply,
)


class MessageEnvelopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        doc = Path(__file__).resolve().parents[1] / "docs" / "message-contract.md"
        cls.bodies = {}
        for block in re.findall(r"```json\n(.*?)\n```", doc.read_text(), re.S):
            value = json.loads(block)
            for candidate in value if isinstance(value, list) else [value]:
                if "message_type" in candidate:
                    cls.bodies[candidate["message_id"]] = candidate
        # Exemplos de contrato, sem modelos reais nem identidades autenticadas.
        cls.links = {
            "msg-003": "msg-002", "msg-004": "msg-002", "msg-023": "msg-002",
            "msg-015": "msg-014", "msg-024": "msg-014",
            "msg-016": "msg-015", "msg-017": "msg-015",
            "msg-018": "msg-016", "msg-019": "msg-016", "msg-020": "msg-018",
        }
        cls.metadata = {}
        for message_id, performative, protocol, expects_reply in (
            ("msg-001", "inform", "verification", False),
            ("msg-002", "request", "verification", True),
            ("msg-003", "inform", "verification", False),
            ("msg-004", "refuse", "verification", False),
            ("msg-014", "cfp", "task-allocation", True),
            ("msg-015", "propose", "task-allocation", True),
            ("msg-016", "accept-proposal", "task-allocation", True),
            ("msg-017", "reject-proposal", "task-allocation", False),
            ("msg-018", "agree", "task-allocation", True),
            ("msg-019", "failure", "task-allocation", False),
            ("msg-020", "inform", "mission-report", False),
            ("msg-021", "inform", "resource-status", False),
            ("msg-022", "inform", "incident-lifecycle", False),
            ("msg-023", "inform", "verification", False),
            ("msg-024", "refuse", "task-allocation", False),
        ):
            conversation = "verification-07-r1" if protocol == "verification" else "allocation-03-r1"
            if message_id in {"msg-001", "msg-021", "msg-022"}:
                conversation = "announcement-" + message_id
            metadata = {"performative": performative, "ontology": "wildlife-monitoring",
                        "protocol": protocol, "conversation-id": conversation}
            if expects_reply:
                metadata["reply-with"] = message_id
            if message_id in cls.links:
                metadata["in-reply-to"] = cls.links[message_id]
            cls.metadata[message_id] = metadata

    def setUp(self):
        self.message = {
            "schema_version": 1, "message_id": " msg-á-01 ",
            "message_type": "ALERT", "created_at": 120.25,
            "event_id": " obs-01 ", "source_id": "sensor_01",
            "payload": {
                "event_type": "ruído", "position": {"x": 6, "y": 9},
                "observed_at": 119.5, "confidence_score": 0.82,
            },
        }

    def assert_invalid(self, message):
        with self.assertRaises(ValueError):
            validate_message(message)
        with self.assertRaises(ValueError):
            to_json(message)
        with self.assertRaises(ValueError):
            from_json(json.dumps(message))

    def test_known_types(self):
        self.assertEqual({kind.value for kind in MessageType}, {
            "ALERT", "VERIFY_REQUEST", "VERIFY_RESPONSE", "CFP", "PROPOSAL",
            "ACCEPT", "REJECT", "REFUSAL", "RESERVATION_CONFIRMED",
            "RESERVATION_FAILED", "MISSION_RESULT", "STATUS", "INCIDENT_CLOSED",
        })

    def test_round_trip_preserves_values_and_input(self):
        original = deepcopy(self.message)
        for created_at in (0, 120, 120.25):
            with self.subTest(created_at=created_at):
                message = deepcopy(self.message)
                message["created_at"] = created_at
                message["payload"]["observed_at"] = min(119.5, created_at)
                self.assertIsNone(validate_envelope(message))
                result = from_json(to_json(message))
                self.assertEqual(result, message)
                self.assertIs(type(result["created_at"]), type(created_at))
                self.assertIsNot(result, message)
        self.assertEqual(self.message, original)
        self.message["message_type"] = MessageType.ALERT
        self.assertEqual(from_json(to_json(self.message))["message_type"], "ALERT")

    def test_documented_bodies_round_trip(self):
        # Os arrays documentais contêm corpos separados, nunca lotes aceites.
        bodies = list(self.bodies.values())
        self.assertEqual(len(bodies), 15)
        self.assertEqual({body["message_type"] for body in bodies}, set(MessageType))
        for body in bodies:
            with self.subTest(message_id=body["message_id"]):
                original = deepcopy(body)
                self.assertIsNone(validate_message(body))
                self.assertEqual(from_json(to_json(body)), body)
                self.assertEqual(body, original)

    def changed(self, message_id, path, value):
        message = deepcopy(self.bodies[message_id])
        target = message
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        return message

    def reply_args(self, message_id):
        request_id = self.links[message_id]
        return deepcopy([self.bodies[message_id], self.metadata[message_id],
                         self.bodies[request_id], self.metadata[request_id]])

    def test_metadata_and_reply_examples_preserve_inputs(self):
        original = deepcopy([self.bodies, self.metadata])
        for message_id, body in self.bodies.items():
            with self.subTest(message_id=message_id):
                self.assertIsNone(validate_metadata(body, self.metadata[message_id]))
        for message_id in self.links:
            with self.subTest(reply=message_id):
                args = self.reply_args(message_id)
                before = deepcopy(args)
                self.assertIsNone(validate_reply(*args, now=args[0]["created_at"]))
                self.assertIsNone(validate_reply(*args))
                self.assertEqual(args, before)
        self.assertEqual([self.bodies, self.metadata], original)

    def test_documented_metadata_examples(self):
        doc = (Path(__file__).resolve().parents[1] / "docs" / "message-contract.md").read_text()
        examples = []
        for block in re.findall(r"```json\n(.*?)\n```", doc, re.S):
            value = json.loads(block)
            if isinstance(value, dict) and "performative" in value:
                examples.append((value["reply-with"], value))
        for message_id, block in re.findall(r'\| `(msg-\d+)` \| `(\{"performative":.*?\})` \|', doc):
            examples.append((message_id, json.loads(block)))
        self.assertEqual(len(examples), 6)
        for message_id, metadata in examples:
            with self.subTest(message_id=message_id):
                self.assertEqual(metadata, self.metadata[message_id])
                validate_metadata(self.bodies[message_id], metadata)
                if message_id in self.links:
                    args = self.reply_args(message_id)
                    args[1] = metadata
                    validate_reply(*args)

    def test_metadata_exact_fields_and_text_types(self):
        for message_id, metadata in self.metadata.items():
            body = self.bodies[message_id]
            for value in (None, [], "text", 1, True):
                with self.subTest(message_id=message_id, shape=value):
                    with self.assertRaises(ValueError):
                        validate_metadata(body, value)
            for key in metadata:
                missing = dict(metadata)
                del missing[key]
                with self.subTest(message_id=message_id, missing=key):
                    with self.assertRaises(ValueError):
                        validate_metadata(body, missing)
                for value in (None, "", " \t", 1, True, [], {}):
                    with self.subTest(message_id=message_id, key=key, value=value):
                        with self.assertRaises(ValueError):
                            validate_metadata(body, {**metadata, key: value})
            for key in {"thread", "ground_truth", "unexpected", "message_id",
                        "reply-with", "in-reply-to"} - metadata.keys():
                with self.subTest(message_id=message_id, extra=key):
                    with self.assertRaises(ValueError):
                        validate_metadata(body, {**metadata, key: "extra"})
            if "reply-with" in metadata:
                with self.assertRaises(ValueError):
                    validate_metadata(body, {**metadata, "reply-with": "another-message"})

    def test_metadata_combinations_and_mission_failure(self):
        for message_id, metadata in self.metadata.items():
            for key, values in (
                ("performative", {item["performative"] for item in self.metadata.values()} | {"unknown"}),
                ("protocol", {item["protocol"] for item in self.metadata.values()} | {"unknown"}),
                ("ontology", {"wildlife-monitoring", "unknown"}),
            ):
                allowed = {metadata[key]}
                if key == "protocol" and self.bodies[message_id]["message_type"] == "REFUSAL":
                    allowed = {"verification", "task-allocation"}
                for value in values:
                    with self.subTest(message_id=message_id, key=key, value=value):
                        candidate = {**metadata, key: value}
                        if value in allowed:
                            validate_metadata(self.bodies[message_id], candidate)
                        else:
                            with self.assertRaises(ValueError):
                                validate_metadata(self.bodies[message_id], candidate)
        for outcome in ("confirmed", "not_confirmed", "inconclusive", "failed"):
            for performative in ("inform", "failure"):
                args = self.reply_args("msg-020")
                args[0]["payload"].update(outcome=outcome, observations=deepcopy(
                    self.bodies["msg-003"]["payload"]["observations"]))
                args[1]["performative"] = performative
                with self.subTest(outcome=outcome, performative=performative):
                    if (outcome == "failed") == (performative == "failure"):
                        validate_reply(*args)
                    else:
                        with self.assertRaises(ValueError):
                            validate_reply(*args)

    def test_reply_rejects_mismatched_correlation(self):
        for message_id in self.links:
            for index, key in ((1, "conversation-id"), (1, "in-reply-to"),
                               (0, "incident_id")):
                args = self.reply_args(message_id)
                args[index][key] = "mismatch"
                with self.subTest(message_id=message_id, key=key):
                    with self.assertRaises(ValueError):
                        validate_reply(*args)
            args = self.reply_args(message_id)
            if "mission_id" in args[2]:
                args[0]["mission_id"] = "another-mission"
                with self.subTest(message_id=message_id, key="mission_id"):
                    with self.assertRaises(ValueError):
                        validate_reply(*args)
            args = self.reply_args(message_id)
            if "resource_id" in args[2]["payload"]:
                args[0]["payload"]["resource_id"] = "another-resource"
                with self.subTest(message_id=message_id, key="resource_id"):
                    with self.assertRaises(ValueError):
                        validate_reply(*args)
            args = self.reply_args(message_id)
            args[0]["message_id"] = args[2]["message_id"]
            if "reply-with" in args[1]:
                args[1]["reply-with"] = args[0]["message_id"]
            with self.subTest(message_id=message_id, key="message_id"):
                with self.assertRaises(ValueError):
                    validate_reply(*args)

    def test_refusal_conditional_mission_and_protocol(self):
        for message_id in ("msg-004", "msg-024"):
            args = self.reply_args(message_id)
            if "mission_id" in args[0]:
                del args[0]["mission_id"]
            else:
                args[0]["mission_id"] = "mission-03"
            validate_metadata(args[0], args[1])  # Corpo isolado não conhece o pedido.
            with self.assertRaises(ValueError):
                validate_reply(*args)
            args = self.reply_args(message_id)
            args[1]["protocol"] = ("verification" if message_id == "msg-024"
                                    else "task-allocation")
            validate_metadata(args[0], args[1])
            with self.assertRaises(ValueError):
                validate_reply(*args)

    def test_reply_requires_expected_type_and_valid_stored_data(self):
        for message_id in self.links:
            for request_id in self.bodies:
                if request_id == self.links[message_id]:
                    continue
                args = self.reply_args(message_id)
                args[2:] = deepcopy([self.bodies[request_id], self.metadata[request_id]])
                with self.subTest(reply=message_id, request=request_id):
                    with self.assertRaises(ValueError):
                        validate_reply(*args)
        # Mesmo com conversa, IDs e encadeamento coerentes, saltar passos é inválido.
        args = self.reply_args("msg-018")
        args[2:] = deepcopy([self.bodies["msg-015"], self.metadata["msg-015"]])
        args[1]["in-reply-to"] = "msg-015"
        with self.assertRaises(ValueError):
            validate_reply(*args)
        for index in range(4):
            args = self.reply_args("msg-003")
            args[index] = {}
            with self.subTest(invalid_argument=index):
                with self.assertRaises(ValueError):
                    validate_reply(*args)

    def test_reply_deadlines_and_chronology(self):
        for message_id in ("msg-003", "msg-004", "msg-023", "msg-015", "msg-024"):
            args = self.reply_args(message_id)
            deadline = args[2]["payload"]["deadline"]
            with self.subTest(message_id=message_id):
                validate_reply(*args, now=deadline - 0.01)
                for now in (deadline, deadline + 1):
                    with self.assertRaises(ValueError):
                        validate_reply(*args, now=now)
                args[0]["created_at"] = deadline
                with self.assertRaises(ValueError):
                    validate_reply(*args)
        for now in (-1, True, False, "124", float("nan"), float("inf"),
                    -float("inf"), [], {}):
            with self.subTest(now=now):
                with self.assertRaises(ValueError):
                    validate_reply(*self.reply_args("msg-003"), now=now)
        args = self.reply_args("msg-023")  # Sem observações: isola a cronologia da resposta.
        args[0]["created_at"] = args[2]["created_at"] - 1
        with self.assertRaises(ValueError):
            validate_reply(*args)
        args[0]["created_at"] = args[2]["created_at"]
        validate_reply(*args, now=args[0]["created_at"])
        with self.assertRaises(ValueError):
            validate_reply(*self.reply_args("msg-003"), now=123.99)
        # O prazo do CFP não limita aceitação, reserva nem execução da missão.
        for message_id in ("msg-016", "msg-017", "msg-018", "msg-019", "msg-020"):
            validate_reply(*self.reply_args(message_id), now=1000)

    def test_envelope_remains_a_partial_check(self):
        message = deepcopy(self.message)
        message["payload"] = {}
        del message["event_id"]
        self.assertIsNone(validate_envelope(message))
        self.assert_invalid(message)

    def test_domain_ids_by_type(self):
        # REFUSAL depende do pedido guardado; ambas as formas isoladas são válidas.
        ids = {
            "ALERT": ({"event_id", "source_id"}, {"incident_id"}),
            "VERIFY_REQUEST": ({"incident_id"}, set()),
            "VERIFY_RESPONSE": ({"incident_id"}, set()),
            "CFP": ({"incident_id", "mission_id"}, set()),
            "PROPOSAL": ({"incident_id", "mission_id"}, set()),
            "ACCEPT": ({"incident_id", "mission_id"}, set()),
            "REJECT": ({"incident_id", "mission_id"}, set()),
            "REFUSAL": ({"incident_id"}, {"mission_id"}),
            "RESERVATION_CONFIRMED": ({"incident_id", "mission_id"}, set()),
            "RESERVATION_FAILED": ({"incident_id", "mission_id"}, set()),
            "MISSION_RESULT": ({"incident_id", "mission_id"}, set()),
            "STATUS": (set(), set()),
            "INCIDENT_CLOSED": ({"incident_id"}, {"mission_id"}),
        }
        for body in self.bodies.values():
            kind = body["message_type"]
            required, optional = ids[kind]
            allowed = required | optional
            for key in ("event_id", "incident_id", "mission_id", "source_id"):
                with self.subTest(kind=kind, key=key):
                    message = deepcopy(body)
                    message.pop(key, None)
                    if key in required:
                        self.assert_invalid(message)
                    else:
                        validate_message(message)
                    message[key] = "domain-01"
                    if key in allowed:
                        validate_message(message)
                    else:
                        self.assert_invalid(message)

    def test_required_and_unknown_payload_and_nested_fields(self):
        for body in self.bodies.values():
            paths = [("payload",)]
            for key in ("position", "target"):
                if key in body["payload"]:
                    paths.append(("payload", key))
            for index, _ in enumerate(body["payload"].get("observations", [])):
                paths.extend([("payload", "observations", index),
                              ("payload", "observations", index, "position")])
            for path in paths:
                container = body
                for key in path:
                    container = container[key]
                for key in container:
                    with self.subTest(message_id=body["message_id"], path=path, missing=key):
                        value = dict(container)
                        del value[key]
                        self.assert_invalid(self.changed(body["message_id"], path, value))
                for key in ("unexpected", "ground_truth", "incident_id", "mission_id",
                            "event_id", "source_id", "message_id", "request_id"):
                    if key not in container:
                        with self.subTest(message_id=body["message_id"], path=path, extra=key):
                            self.assert_invalid(self.changed(
                                body["message_id"], path, {**container, key: "extra"}))
                for value in ([], "text", 1, True, None):
                    with self.subTest(message_id=body["message_id"], path=path, value=value):
                        self.assert_invalid(self.changed(body["message_id"], path, value))

    def test_payload_numbers_text_and_boolean_types(self):
        for body in self.bodies.values():
            paths = [("payload", key) for key in body["payload"]]
            for key in ("position", "target"):
                if key in body["payload"]:
                    paths.extend(("payload", key, coord) for coord in ("x", "y"))
            for index, observation in enumerate(body["payload"].get("observations", [])):
                paths.extend(("payload", "observations", index, key) for key in observation)
                paths.extend(("payload", "observations", index, "position", coord)
                             for coord in ("x", "y"))
            for path in paths:
                original = body
                for key in path:
                    original = original[key]
                if type(original) in (int, float):
                    values = [-1, True, False, "1", None, float("nan"), float("inf"), -float("inf")]
                    if path[-1] in {"x", "y", "priority"}:
                        values.append(1.0)
                    if path[-1] in {"confidence_score", "energy_fraction", "energy_cost_fraction"}:
                        values.append(1.01)
                elif isinstance(original, str):
                    values = ["", " \t\n", 1, True, None, [], {}]
                elif type(original) is bool:
                    values = [0, 1, "false", None, [], {}]
                else:
                    continue
                for value in values:
                    with self.subTest(message_id=body["message_id"], path=path, value=value):
                        self.assert_invalid(self.changed(body["message_id"], path, value))

    def test_time_relationships(self):
        for message_id, path, value in (
            ("msg-001", ("observed_at",), 120.01),
            ("msg-003", ("observations", 0, "observed_at"), 124.01),
            ("msg-002", ("window_start",), 120.01),
            ("msg-002", ("window_end",), 121.01),
            ("msg-002", ("deadline",), 121),
            ("msg-014", ("deadline",), 128),
            ("msg-021", ("observed_at",), 140.01),
            ("msg-021", ("valid_until",), 138.99),
        ):
            with self.subTest(message_id=message_id, path=path):
                self.assert_invalid(self.changed(message_id, ("payload",) + path, value))

    def test_observation_lists_and_duplicates(self):
        observation = deepcopy(self.bodies["msg-003"]["payload"]["observations"][0])
        for value in (None, {}, "text", True, [None], [[]], [1], ["text"]):
            with self.subTest(value=value):
                self.assert_invalid(self.changed("msg-003", ("payload", "observations"), value))
        for confidence in (observation["confidence_score"], 0.1):
            duplicate = {**observation, "confidence_score": confidence}
            self.assert_invalid(self.changed("msg-003", ("payload", "observations"),
                                             [observation, duplicate]))
        # A mesma fonte pode fornecer duas observações; IDs não são normalizados.
        distinct = {**observation, "event_id": " " + observation["event_id"]}
        message = self.changed("msg-003", ("payload", "observations"), [observation, distinct])
        self.assertEqual(from_json(to_json(message)), message)

    def test_evidence_and_outcome_combinations(self):
        observations = self.bodies["msg-003"]["payload"]["observations"]
        for evidence in ("compatible", "contradictory", "informative_absence", "no_data", "UNKNOWN"):
            for items in ([], observations):
                message = self.changed("msg-003", ("payload", "evidence"), evidence)
                message["payload"]["observations"] = deepcopy(items)
                with self.subTest(evidence=evidence, has_observations=bool(items)):
                    if evidence != "UNKNOWN" and bool(items) == (evidence in {"compatible", "contradictory"}):
                        self.assertEqual(from_json(to_json(message)), message)
                    else:
                        self.assert_invalid(message)
        for outcome in ("confirmed", "not_confirmed", "inconclusive", "failed", "UNKNOWN"):
            for items in ([], observations):
                message = self.changed("msg-020", ("payload", "outcome"), outcome)
                message["payload"]["observations"] = deepcopy(items)
                with self.subTest(outcome=outcome, has_observations=bool(items)):
                    if outcome != "UNKNOWN" and (items or outcome in {"inconclusive", "failed"}):
                        self.assertEqual(from_json(to_json(message)), message)
                    else:
                        self.assert_invalid(message)
            for terminal in ("CLOSED", "EXPIRED", "UNRESOLVED", "RESPONDING", "UNKNOWN"):
                message = self.changed("msg-022", ("payload", "terminal_state"), terminal)
                message["payload"]["outcome"] = outcome
                with self.subTest(terminal=terminal, outcome=outcome):
                    if (terminal in {"CLOSED", "EXPIRED", "UNRESOLVED"}
                            and outcome != "UNKNOWN"
                            and (terminal == "CLOSED") == (outcome in {"confirmed", "not_confirmed"})):
                        self.assertEqual(from_json(to_json(message)), message)
                    else:
                        self.assert_invalid(message)

    def test_valid_numeric_boundaries(self):
        for message_id, updates in (
            ("msg-001", {"observed_at": 120, "confidence_score": 0, "position": {"x": 0, "y": 10**100}}),
            ("msg-001", {"observed_at": 0, "confidence_score": 1}),
            ("msg-002", {"window_start": 121, "window_end": 121, "deadline": 121.01}),
            ("msg-014", {"priority": 10**100, "deadline": 128.01}),
            ("msg-015", {"eta_seconds": 0, "cost": 0, "energy_cost_fraction": 0}),
            ("msg-015", {"cost": 10**100, "energy_cost_fraction": 1}),
            ("msg-021", {"observed_at": 140, "valid_until": 140, "energy_fraction": 0, "available": True}),
            ("msg-021", {"observed_at": 0, "valid_until": 0, "energy_fraction": 1}),
        ):
            with self.subTest(message_id=message_id, updates=updates):
                message = deepcopy(self.bodies[message_id])
                message["payload"].update(updates)
                self.assertEqual(from_json(to_json(message)), message)

    def test_wrong_envelope_or_payload_shape(self):
        for value in (None, [], "text", 1, True):
            with self.subTest(value=value):
                self.assert_invalid(value)
                message = deepcopy(self.message)
                message["payload"] = value
                self.assert_invalid(message)

    def test_required_fields(self):
        for key in ("schema_version", "message_id", "message_type", "created_at", "payload"):
            with self.subTest(key=key):
                message = deepcopy(self.message)
                del message[key]
                self.assert_invalid(message)

    def test_present_ids_are_nonempty_strings(self):
        for key in ("message_id", "event_id", "incident_id", "mission_id", "source_id"):
            for value in ("", " \t\n", None, 1, True, [], {}):
                with self.subTest(key=key, value=value):
                    message = deepcopy(self.message)
                    message[key] = value
                    self.assert_invalid(message)

    def test_unknown_version_and_type(self):
        for key, values in (
            ("schema_version", (0, 2, 1.0, True, "1", None)),
            ("message_type", ("UNKNOWN", "alert", " ALERT", "ALERT ", "", None, 1, [], {})),
        ):
            for value in values:
                with self.subTest(key=key, value=value):
                    message = deepcopy(self.message)
                    message[key] = value
                    self.assert_invalid(message)

    def test_created_at_is_finite_nonnegative_number(self):
        for value in (-1, True, False, "120", None, float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                message = deepcopy(self.message)
                message["created_at"] = value
                self.assert_invalid(message)

    def test_unknown_envelope_fields(self):
        for key in ("metadata", "performative", "conversation-id", "unexpected"):
            with self.subTest(key=key):
                message = deepcopy(self.message)
                message[key] = "value"
                self.assert_invalid(message)

    def test_malformed_json_and_nontext_input(self):
        for body in ("", '{"schema_version":1,}', '{"payload":',
                     to_json(self.message) + " {}", b"{}", None, {}):
            with self.subTest(body=body):
                with self.assertRaises(ValueError):
                    from_json(body)

    def test_duplicate_keys_at_every_depth(self):
        body = to_json(self.message)
        for duplicate in (
            body.replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'),
            body.replace('"event_type": "ruído"', '"event_type": "ruído", "event_type": "outro"'),
            body.replace('"x": 6', '"x": 6, "x": 6'),
        ):
            with self.subTest(body=duplicate):
                with self.assertRaises(ValueError):
                    from_json(duplicate)

    def test_json_values_and_ground_truth(self):
        for value in (None, float("nan"), float("inf"), -float("inf"),
                      {"ground_truth": True}, [{"ground_truth": False}]):
            with self.subTest(value=value):
                message = deepcopy(self.message)
                message["payload"]["position"]["x"] = value
                self.assert_invalid(message)
        for value in ((1, 2), {1: "value"}, object()):
            with self.subTest(value=value):
                message = deepcopy(self.message)
                message["payload"]["position"] = value
                with self.assertRaises(ValueError):
                    to_json(message)
        body = to_json(self.message).replace('"created_at": 120.25', '"created_at": 1e999')
        with self.assertRaises(ValueError):
            from_json(body)


if __name__ == "__main__":
    unittest.main()
