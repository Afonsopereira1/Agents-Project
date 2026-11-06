"""Contrato JSON v1 proposto, sem transporte nem conversões de modelos.

Corpos e metadados são dicts separados. Valida dados e respostas contra a
mensagem guardada; histórico, transporte e reserva são do consumidor.
"""

import json
from enum import StrEnum
from math import isfinite


class MessageType(StrEnum):
    """Tipos exatos de conteúdo; não são performatives do transporte."""

    ALERT = "ALERT"
    VERIFY_REQUEST = "VERIFY_REQUEST"
    VERIFY_RESPONSE = "VERIFY_RESPONSE"
    CFP = "CFP"
    PROPOSAL = "PROPOSAL"
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    REFUSAL = "REFUSAL"
    RESERVATION_CONFIRMED = "RESERVATION_CONFIRMED"
    RESERVATION_FAILED = "RESERVATION_FAILED"
    MISSION_RESULT = "MISSION_RESULT"
    STATUS = "STATUS"
    INCIDENT_CLOSED = "INCIDENT_CLOSED"


_REQUIRED = {"schema_version", "message_id", "message_type", "created_at", "payload"}
_DOMAIN_IDS = {"event_id", "incident_id", "mission_id", "source_id"}
_PAYLOAD_FIELDS = {
    "ALERT": "event_type position observed_at confidence_score",
    "VERIFY_REQUEST": "event_type position window_start window_end deadline",
    "VERIFY_RESPONSE": "evidence observations reason",
    "CFP": "task required_capability target priority deadline",
    "PROPOSAL": "resource_id eta_seconds energy_cost_fraction cost",
    "ACCEPT": "resource_id",
    "REJECT": "resource_id reason",
    "REFUSAL": "reason",
    "RESERVATION_CONFIRMED": "resource_id",
    "RESERVATION_FAILED": "resource_id reason",
    "MISSION_RESULT": "resource_id outcome observations reason",
    "STATUS": "resource_id position available energy_fraction observed_at valid_until",
    "INCIDENT_CLOSED": "terminal_state outcome reason",
}
_METADATA_RULES = {
    "ALERT": ("inform", {"verification"}),
    "VERIFY_REQUEST": ("request", {"verification"}),
    "VERIFY_RESPONSE": ("inform", {"verification"}),
    "CFP": ("cfp", {"task-allocation"}),
    "PROPOSAL": ("propose", {"task-allocation"}),
    "ACCEPT": ("accept-proposal", {"task-allocation"}),
    "REJECT": ("reject-proposal", {"task-allocation"}),
    "REFUSAL": ("refuse", {"verification", "task-allocation"}),
    "RESERVATION_CONFIRMED": ("agree", {"task-allocation"}),
    "RESERVATION_FAILED": ("failure", {"task-allocation"}),
    "MISSION_RESULT": ("inform", {"mission-report"}),
    "STATUS": ("inform", {"resource-status"}),
    "INCIDENT_CLOSED": ("inform", {"incident-lifecycle"}),
}
_REPLIES = {
    "VERIFY_REQUEST": {"VERIFY_RESPONSE", "REFUSAL"},
    "CFP": {"PROPOSAL", "REFUSAL"},
    "PROPOSAL": {"ACCEPT", "REJECT"},
    "ACCEPT": {"RESERVATION_CONFIRMED", "RESERVATION_FAILED"},
    "RESERVATION_CONFIRMED": {"MISSION_RESULT"},
}
_RESPONSE_TYPES = set().union(*_REPLIES.values())


def _fields(value: object, required: set[str]) -> None:
    if not isinstance(value, dict) or value.keys() != required:
        raise ValueError(f"Objeto deve conter exatamente os campos: {sorted(required)}")


def _text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} deve ser texto não vazio")


def _number(value: object, name: str) -> None:
    if type(value) not in (int, float) or value < 0:
        raise ValueError(f"{name} deve ser número não negativo, sem booleanos")
    if type(value) is float and not isfinite(value):
        raise ValueError(f"{name} deve ser finito")


def _integer(value: object, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} deve ser inteiro não negativo, sem booleanos")


def _position(value: object) -> None:
    _fields(value, {"x", "y"})
    for key, coordinate in value.items():
        _integer(coordinate, key)


def _observation(value: dict, created_at: int | float) -> None:
    _fields(value, {"event_id", "source_id", "event_type", "position",
                    "observed_at", "confidence_score"})
    for key in ("event_id", "source_id", "event_type"):
        _text(value[key], key)
    _position(value["position"])
    for key in ("observed_at", "confidence_score"):
        _number(value[key], key)
    if value["observed_at"] > created_at or value["confidence_score"] > 1:
        raise ValueError("Observação futura ou confiança fora de [0, 1]")


def _observations(value: object, created_at: int | float) -> None:
    if not isinstance(value, list):
        raise ValueError("observations deve ser uma lista")
    seen = set()
    for observation in value:
        _observation(observation, created_at)
        event_id = observation["event_id"]
        if event_id in seen:
            raise ValueError("event_id repetido na lista de observações")
        seen.add(event_id)


def _validate_json_value(value: object) -> None:
    """Rejeita dados que o JSON converteria com perda e verdade do simulador."""
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or key == "ground_truth":
                raise ValueError("Chave JSON inválida ou ground_truth proibido")
            _validate_json_value(item)
    elif isinstance(value, list):
        for item in value:
            _validate_json_value(item)
    elif type(value) is float:
        if not isfinite(value):
            raise ValueError("Número JSON não finito")
    elif not isinstance(value, (str, bool, int)):
        raise ValueError("Valor deve ser JSON, sem null, tuplos ou objetos de domínio")


def validate_envelope(message: dict) -> None:
    """Lança ValueError para envelope inválido; não altera o dicionário.

    Valida campos comuns, IDs presentes e valores JSON. A presença dos IDs
    por tipo e os campos internos do payload exigem validação adicional.
    """
    if not isinstance(message, dict):
        raise ValueError("Envelope deve ser um objeto JSON")
    _validate_json_value(message)
    fields = message.keys()
    if not _REQUIRED <= fields or fields - (_REQUIRED | _DOMAIN_IDS):
        raise ValueError("Campos comuns ausentes ou campos desconhecidos no envelope")
    if type(message["schema_version"]) is not int or message["schema_version"] != 1:
        raise ValueError("schema_version deve ser o inteiro 1")
    for key in {"message_id"} | (_DOMAIN_IDS & fields):
        _text(message[key], key)
    MessageType(message["message_type"])
    _number(message["created_at"], "created_at")
    if not isinstance(message["payload"], dict):
        raise ValueError("payload deve ser um objeto JSON")


def validate_message(message: dict) -> None:
    """Valida envelope, IDs aplicáveis e payload; lança ValueError sem alterar dados.

    REFUSAL admite mission_id opcionalmente: o pedido guardado determina se
    é obrigatório ou inaplicável. Não confere metadados nem dados históricos.
    """
    validate_envelope(message)
    kind = message["message_type"]
    required_ids = {"incident_id"}
    allowed_ids = required_ids.copy()
    if kind == "ALERT":
        required_ids = {"event_id", "source_id"}
        allowed_ids = required_ids | {"incident_id"}
    elif kind == "STATUS":
        required_ids = allowed_ids = set()
    elif kind in {"REFUSAL", "INCIDENT_CLOSED"}:
        allowed_ids.add("mission_id")
    elif kind not in {"VERIFY_REQUEST", "VERIFY_RESPONSE"}:
        required_ids.add("mission_id")
        allowed_ids.add("mission_id")
    if not required_ids <= message.keys() or (_DOMAIN_IDS & message.keys()) - allowed_ids:
        raise ValueError(f"IDs obrigatórios ausentes ou IDs inaplicáveis em {kind}")

    payload = message["payload"]
    created_at = message["created_at"]
    _fields(payload, set(_PAYLOAD_FIELDS[kind].split()))
    for key, value in payload.items():
        if key in {"event_type", "task", "required_capability", "resource_id",
                   "reason", "evidence", "outcome", "terminal_state"}:
            _text(value, key)
        elif key in {"position", "target"}:
            _position(value)
        elif key == "observations":
            _observations(value, created_at)
        elif key == "available":
            if type(value) is not bool:
                raise ValueError("available deve ser booleano")
        elif key == "priority":
            _integer(value, key)
        else:
            _number(value, key)
            if key in {"confidence_score", "energy_cost_fraction", "energy_fraction"} and value > 1:
                raise ValueError(f"{key} deve estar em [0, 1]")

    if "observed_at" in payload and payload["observed_at"] > created_at:
        raise ValueError("observed_at não pode ser posterior a created_at")
    if kind == "VERIFY_REQUEST" and not payload["window_start"] <= payload["window_end"] <= created_at:
        raise ValueError("Janela deve respeitar window_start <= window_end <= created_at")
    if kind in {"VERIFY_REQUEST", "CFP"} and payload["deadline"] <= created_at:
        raise ValueError("deadline deve ser posterior a created_at")
    if kind == "STATUS" and payload["valid_until"] < payload["observed_at"]:
        raise ValueError("valid_until deve ser igual ou posterior a observed_at")
    if kind == "VERIFY_RESPONSE":
        evidence = payload["evidence"]
        if evidence not in {"compatible", "contradictory", "informative_absence", "no_data"}:
            raise ValueError("evidence desconhecida")
        if bool(payload["observations"]) != (evidence in {"compatible", "contradictory"}):
            raise ValueError("Lista de observações incompatível com evidence")
    if kind in {"MISSION_RESULT", "INCIDENT_CLOSED"}:
        outcome = payload["outcome"]
        if outcome not in {"confirmed", "not_confirmed", "inconclusive", "failed"}:
            raise ValueError("outcome desconhecido")
        if kind == "MISSION_RESULT":
            if outcome in {"confirmed", "not_confirmed"} and not payload["observations"]:
                raise ValueError("Resultado conclusivo exige observações")
        else:
            terminal = payload["terminal_state"]
            if terminal not in {"CLOSED", "EXPIRED", "UNRESOLVED"}:
                raise ValueError("terminal_state desconhecido ou não terminal")
            if (terminal == "CLOSED") != (outcome in {"confirmed", "not_confirmed"}):
                raise ValueError("Estado terminal incompatível com outcome")


def validate_metadata(message: dict, metadata: dict) -> None:
    """Valida corpo e metadados lógicos, sem transporte ou pedido guardado.

    Lança ValueError sem alterar dados. REFUSAL admite dois protocolos;
    validate_reply confere o protocolo e a missão contra o pedido concreto.
    """
    validate_message(message)
    kind = message["message_type"]
    fields = {"performative", "ontology", "protocol", "conversation-id"}
    if kind in _REPLIES:
        fields.add("reply-with")
    if kind in _RESPONSE_TYPES:
        fields.add("in-reply-to")
    _fields(metadata, fields)
    for key, value in metadata.items():
        _text(value, key)
    performative, protocols = _METADATA_RULES[kind]
    if kind == "MISSION_RESULT" and message["payload"]["outcome"] == "failed":
        performative = "failure"
    if (metadata["performative"] != performative
            or metadata["ontology"] != "wildlife-monitoring"
            or metadata["protocol"] not in protocols):
        raise ValueError("Tipo, performative, ontology ou protocolo incompatíveis")
    if "reply-with" in metadata and metadata["reply-with"] != message["message_id"]:
        raise ValueError("reply-with deve ser igual ao próprio message_id")


def validate_reply(response: dict, metadata: dict, request: dict,
                   request_metadata: dict, *, now: int | float | None = None) -> None:
    """Confere resposta contra a mensagem guardada; lança ValueError sem mutação.

    now é o instante de receção/processamento. Se omitido, usa a emissão,
    sem provar chegada pontual. Prazo do pedido é exclusivo e só se aplica
    à resposta direta; não valida participantes, reserva nem estado local.
    """
    validate_metadata(request, request_metadata)
    validate_metadata(response, metadata)
    kind = response["message_type"]
    if kind not in _REPLIES.get(request["message_type"], set()):
        raise ValueError("Tipo de resposta não permitido para a mensagem guardada")
    if (metadata["conversation-id"] != request_metadata["conversation-id"]
            or metadata["in-reply-to"] != request_metadata["reply-with"]):
        raise ValueError("Conversa ou in-reply-to incompatível com o pedido")
    if kind != "MISSION_RESULT" and metadata["protocol"] != request_metadata["protocol"]:
        raise ValueError("Resposta deve manter o protocolo do pedido")
    if any(response.get(key) != request.get(key) for key in _DOMAIN_IDS):
        raise ValueError("IDs de domínio incompatíveis com o pedido")
    resource_id = request["payload"].get("resource_id")
    if resource_id is not None and response["payload"].get("resource_id") != resource_id:
        raise ValueError("Recurso incompatível com a proposta/aceitação/reserva")
    if response["message_id"] == request["message_id"]:
        raise ValueError("Resposta deve ter message_id próprio")
    if response["created_at"] < request["created_at"]:
        raise ValueError("Resposta não pode ser anterior ao pedido")
    if now is None:
        now = response["created_at"]
    _number(now, "now")
    if now < response["created_at"]:
        raise ValueError("Receção não pode ser anterior à emissão da resposta")
    deadline = request["payload"].get("deadline")
    if deadline is not None and now >= deadline:
        raise ValueError("Resposta tardia: deadline atingido")


def to_json(message: dict) -> str:
    """Valida envelope/payload e devolve JSON, preservando IDs e instantes."""
    validate_message(message)
    return json.dumps(message, ensure_ascii=False, allow_nan=False)


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Chave JSON repetida: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Constante inválida em JSON: {value}")


def from_json(body: str) -> dict:
    """Lê JSON e valida envelope/payload; JSON/contrato inválido lança ValueError.

    Rejeita chaves repetidas antes de formar os dicionários. Não valida
    metadados enviados separadamente nem a correlação com pedidos guardados.
    """
    if not isinstance(body, str):
        raise ValueError("Corpo deve ser texto JSON")
    message = json.loads(
        body, object_pairs_hook=_unique_object, parse_constant=_reject_constant
    )
    validate_message(message)
    return message
