import json
from dataclasses import fields, is_dataclass
from enum import Enum
from math import isfinite
from typing import Any, TypeVar

from isia.domain.models import (
    Bid,
    Incident,
    Mission,
    MissionStatus,
    Observation,
    Position,
    ResourceState,
    ResourceStatus,
)


class MessageType(Enum):
    ALERT = "ALERT"
    VERIFY_REQUEST = "VERIFY_REQUEST"
    VERIFY_RESPONSE = "VERIFY_RESPONSE"
    CFP = "CFP"
    PROPOSAL = "PROPOSAL"
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    MISSION_RESULT = "MISSION_RESULT"
    STATUS = "STATUS"
    INCIDENT_CLOSED = "INCIDENT_CLOSED"


DEFAULT_DEDUPLICATION_RETENTION_SECONDS = 600.0


def _require_identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} deve ser uma string não vazia.")
    return value


def _validate_json_value(value: Any, path: str = "payload") -> None:
    """Valida valores JSON estritos antes de serializar ou aceitar payloads."""
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"{path} não pode conter NaN ou infinito.")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} só pode ter chaves string.")
            _validate_json_value(item, f"{path}.{key}")
        return
    raise TypeError(f"{path} contém um valor não serializável.")


def _reject_json_constant(value: str):
    raise ValueError(f"Constante JSON inválida: {value}.")


def _validate_cfp(message_ids: dict[str, str | None], payload: dict[str, Any]) -> None:
    for name in ("mission_id", "incident_id", "conversation_id"):
        _require_identifier(message_ids[name], name)

    required = {"task", "target", "required_capability", "priority", "deadline"}
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"Campos obrigatórios em CFP em falta: {', '.join(sorted(missing))}.")
    if not isinstance(payload["task"], str) or not payload["task"].strip():
        raise ValueError("task deve ser uma string não vazia.")
    if not isinstance(payload["required_capability"], str) or not payload["required_capability"].strip():
        raise ValueError("required_capability deve ser uma string não vazia.")
    if type(payload["priority"]) is not int or payload["priority"] < 0:
        raise ValueError("priority deve ser um inteiro não negativo.")
    deadline = payload["deadline"]
    if type(deadline) not in (int, float) or not isfinite(deadline) or deadline < 0:
        raise ValueError("deadline deve ser finito e não negativo.")
    if "round_number" in payload:
        round_number = payload["round_number"]
        if type(round_number) is not int or round_number < 1:
            raise ValueError("round_number deve ser um inteiro positivo.")
    target = payload["target"]
    if not isinstance(target, dict) or type(target.get("x")) is not int or type(target.get("y")) is not int:
        raise ValueError("target deve conter coordenadas inteiras.")
    if target["x"] < 0 or target["y"] < 0:
        raise ValueError("target não pode conter coordenadas negativas.")


def model_to_dict(model: Any) -> dict[str, Any]:
    """Converte um modelo de domínio num dicionário JSON-compatível."""
    if not is_dataclass(model) or isinstance(model, type):
        raise TypeError("O valor deve ser uma instância de um modelo dataclass.")
    return {field.name: _to_json_value(getattr(model, field.name)) for field in fields(model)}


def _to_json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return model_to_dict(value)
    if isinstance(value, tuple):
        return [_to_json_value(item) for item in value]
    if isinstance(value, list):
        return [_to_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_json_value(item) for key, item in value.items()}
    return value


T = TypeVar("T")


def model_from_dict(data: dict[str, Any], model_type: type[T]) -> T:
    """Reconstrói um modelo de domínio a partir de um dicionário validado."""
    if not isinstance(data, dict):
        raise TypeError("Os dados do modelo devem ser um objeto JSON.")

    try:
        if model_type is Position:
            return Position(**data)
        if model_type is Observation:
            values = dict(data)
            values["position"] = model_from_dict(values["position"], Position)
            return Observation(**values)
        if model_type is Incident:
            values = dict(data)
            values["observations"] = tuple(
                model_from_dict(item, Observation) for item in values["observations"]
            )
            return Incident(**values)
        if model_type is ResourceState:
            values = dict(data)
            if values.get("status") is not None:
                values["status"] = ResourceStatus(values["status"])
            values["position"] = model_from_dict(values["position"], Position)
            return ResourceState(**values)
        if model_type is Mission:
            values = dict(data)
            values["target"] = model_from_dict(values["target"], Position)
            if "status" in values:
                values["status"] = MissionStatus(values["status"])
            return Mission(**values)
        if model_type is Bid:
            return Bid(**data)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Dados inválidos para {model_type.__name__}.") from error

    raise TypeError(f"Modelo não suportado: {model_type.__name__}.")


def serialize_model(model: Any) -> str:
    data = model_to_dict(model)
    _validate_json_value(data, "model")
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        allow_nan=False,
    )


def deserialize_model(payload: str, model_type: type[T]) -> T:
    try:
        data = json.loads(payload, parse_constant=_reject_json_constant)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("JSON inválido.") from error
    return model_from_dict(data, model_type)


class Message:
    schema_version = 1

    def __init__(
        self,
        message_id: str,
        message_type: MessageType,
        created_at: float,
        payload: dict[str, Any],
        *,
        event_id: str | None = None,
        incident_id: str | None = None,
        mission_id: str | None = None,
        source_id: str | None = None,
        conversation_id: str | None = None,
        schema_version: int = 1,
    ):
        self.message_id = _require_identifier(message_id, "message_id")
        if not isinstance(message_type, MessageType):
            raise TypeError("message_type deve ser MessageType.")
        if (
            type(created_at) not in (int, float)
            or not isfinite(created_at)
            or created_at < 0
        ):
            raise ValueError("created_at deve ser finito e não negativo.")
        if not isinstance(payload, dict):
            raise TypeError("payload deve ser um objeto JSON.")
        _validate_json_value(payload)
        if type(schema_version) is not int or schema_version != 1:
            raise ValueError("schema_version deve ser o inteiro 1.")
        for name, value in (
            ("event_id", event_id),
            ("incident_id", incident_id),
            ("mission_id", mission_id),
            ("source_id", source_id),
            ("conversation_id", conversation_id),
        ):
            if value is not None:
                _require_identifier(value, name)
        if message_type is MessageType.CFP:
            _validate_cfp(
                {
                    "mission_id": mission_id,
                    "incident_id": incident_id,
                    "conversation_id": conversation_id,
                },
                payload,
            )
        self.message_type = message_type
        self.created_at = created_at
        self.payload = payload
        self.event_id = event_id
        self.incident_id = incident_id
        self.mission_id = mission_id
        self.source_id = source_id
        self.conversation_id = conversation_id
        self.schema_version = schema_version

    def to_dict(self) -> dict[str, Any]:
        data = {
            "schema_version": self.schema_version,
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "created_at": self.created_at,
            "payload": self.payload,
        }
        for name in ("event_id", "incident_id", "mission_id", "source_id", "conversation_id"):
            value = getattr(self, name)
            if value is not None:
                data[name] = value
        return data

    def to_json(self) -> str:
        data = self.to_dict()
        _validate_json_value(data, "message")
        return json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        if not isinstance(data, dict):
            raise TypeError("A mensagem deve ser um objeto JSON.")
        required = {"schema_version", "message_id", "message_type", "created_at", "payload"}
        missing = required - data.keys()
        if missing:
            raise ValueError(f"Campos obrigatórios em falta: {', '.join(sorted(missing))}.")
        try:
            message_type = MessageType(data["message_type"])
        except (TypeError, ValueError) as error:
            raise ValueError("message_type inválido.") from error
        return cls(
            data["message_id"],
            message_type,
            data["created_at"],
            data["payload"],
            event_id=data.get("event_id"),
            incident_id=data.get("incident_id"),
            mission_id=data.get("mission_id"),
            source_id=data.get("source_id"),
            conversation_id=data.get("conversation_id"),
            schema_version=data["schema_version"],
        )

    @classmethod
    def from_json(cls, payload: str):
        try:
            data = json.loads(payload, parse_constant=_reject_json_constant)
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("JSON inválido.") from error
        return cls.from_dict(data)


class MessageDeduplicator:
    """Registo mínimo de mensagens já processadas por identificador."""

    def __init__(self):
        self._seen_ids: set[str] = set()

    def accept(self, message: Message) -> bool:
        if not isinstance(message, Message):
            raise TypeError("message deve ser Message.")
        if message.message_id in self._seen_ids:
            return False
        self._seen_ids.add(message.message_id)
        return True

    def is_duplicate(self, message_id: str) -> bool:
        _require_identifier(message_id, "message_id")
        return message_id in self._seen_ids

    def __len__(self) -> int:
        return len(self._seen_ids)
