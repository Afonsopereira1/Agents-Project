"""Mensagens trocadas entre agentes e conversão JSON dos modelos de domínio.

Por onde começar:

- `MessageType`: os 10 tipos de mensagem (as performativas FIPA estão em `isia.communication.transport`).
- `Message`: o envelope comum (ids de conversa e de correlação, emissor, payload), validado na construção."""

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
from isia.domain.validation import is_finite_number


class MessageType(Enum):
    """Tipos de mensagem do protocolo; o valor é o texto usado no JSON.

    Attributes:
        ALERT (str): Aviso de uma ameaça observada, trocado entre agentes de incidente vizinhos.
        VERIFY_REQUEST (str): Pedido de verificação de um evento, enviado a um informador.
        VERIFY_RESPONSE (str): Resposta do informador a um ``VERIFY_REQUEST``.
        CFP (str): Pedido de propostas (Contract Net) para uma missão.
        PROPOSAL (str): Proposta de um recurso a um ``CFP``.
        ACCEPT (str): Aceitação da proposta escolhida; atribui a missão ao recurso.
        REJECT (str): Recusa de uma proposta pelo iniciador, ou de um ``CFP`` pelo recurso.
        MISSION_RESULT (str): Resultado de uma missão, enviado pelo recurso que a executou.
        STATUS (str): Confirmação (ou não) da reserva, enviada pelo recurso após um ``ACCEPT``.
        INCIDENT_CLOSED (str): Encerramento de um incidente.
    """
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


def _require_identifier(value: Any, name: str) -> str:
    """Devolver ``value`` se for string não vazia; senão, ValueError com ``name``.

    Raises:
        ValueError: Se ``value`` não for uma string com conteúdo além de espaços.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} deve ser uma string não vazia.")
    return value


def _validate_json_value(value: Any, path: str = "payload") -> None:
    """Validar valores JSON estritos antes de serializar ou aceitar payloads.

    Raises:
        ValueError: Se houver um float NaN ou infinito.
        TypeError: Se houver uma chave de dicionário não string ou um valor não serializável.
    """
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
    """Recusar ``NaN`` e ``Infinity`` ao ler JSON, levantando ValueError.

    Raises:
        ValueError: Sempre, com a constante recebida na mensagem.
    """
    raise ValueError(f"Constante JSON inválida: {value}.")


def _validate_cfp(message_ids: dict[str, str | None], payload: dict[str, Any]) -> None:
    """Validar os identificadores e o payload de um CFP; ValueError se algo falhar.

    Exige ``mission_id``, ``incident_id`` e ``conversation_id`` e, no payload,
    ``task``, ``target``, ``required_capability``, ``priority`` e ``deadline``;
    ``round_number`` é opcional, mas tem de ser um inteiro positivo.

    Raises:
        ValueError: Se faltar um identificador ou campo, ou algum tiver tipo ou valor inválido.
    """
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
    if not is_finite_number(deadline) or deadline < 0:
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
    """Converter um modelo de domínio num dicionário compatível com JSON.

    Enums passam ao seu valor, tuplos a listas e dataclasses aninhadas a dicionários.

    Args:
        model (Any): Instância de um modelo dataclass (ex.: ``Incident``, ``Mission``).

    Returns:
        dict[str, Any]: Um item por campo do dataclass.

    Raises:
        TypeError: Se ``model`` não for uma instância de dataclass.
    """
    if not is_dataclass(model) or isinstance(model, type):
        raise TypeError("O valor deve ser uma instância de um modelo dataclass.")
    return {field.name: _to_json_value(getattr(model, field.name)) for field in fields(model)}


def _to_json_value(value: Any) -> Any:
    """Converter recursivamente um valor para JSON.

    Enums passam ao seu valor, dataclasses a dicionários e tuplos a listas; o
    resto é devolvido sem alteração.
    """
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
    """Reconstruir um modelo de domínio a partir de um dicionário validado.

    Suporta ``Position``, ``Observation``, ``Incident``, ``ResourceState``, ``Mission`` e
    ``Bid``; reconstrói as posições, observações e enums aninhados.

    Args:
        data (dict[str, Any]): Dicionário no formato produzido por ``model_to_dict``.
        model_type (type[T]): Classe do modelo a reconstruir.

    Returns:
        T: Instância de ``model_type``, validada pelo próprio modelo.

    Raises:
        TypeError: Se ``data`` não for um dicionário ou ``model_type`` não for suportado.
        ValueError: Se faltarem campos ou os valores forem inválidos para o modelo.
    """
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


class Message:
    """Envelope validado de uma mensagem entre agentes, serializável em JSON estrito.

    Attributes:
        message_id (str): Identificador único da mensagem.
        message_type (MessageType): Tipo de mensagem do protocolo.
        created_at (float): Tempo simulado de emissão, não negativo.
        payload (dict[str, Any]): Conteúdo específico do tipo, só com valores JSON.
        event_id (str | None): Evento observado a que a mensagem se refere.
        incident_id (str | None): Incidente a que a mensagem se refere.
        mission_id (str | None): Missão a que a mensagem se refere.
        source_id (str | None): Agente ou recurso emissor.
        conversation_id (str | None): Conversa (protocolo FIPA) a que a mensagem pertence.
        schema_version (int): Versão do formato; só é aceite ``1``.
    """
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
        """Validar o envelope e as regras próprias de CFP e MISSION_RESULT.

        Num MISSION_RESULT, ``resource_id`` tem de ser o ``source_id`` e ``completed_at``
        não pode ultrapassar ``created_at``.

        Args:
            message_id (str): Identificador único da mensagem, não vazio.
            message_type (MessageType): Tipo de mensagem do protocolo.
            created_at (float): Tempo simulado de emissão, finito e não negativo.
            payload (dict[str, Any]): Conteúdo da mensagem, só com valores JSON estritos.
            event_id (str | None): Evento observado; ``None`` se não se aplicar.
            incident_id (str | None): Incidente; obrigatório em CFP e MISSION_RESULT.
            mission_id (str | None): Missão; obrigatória em CFP e MISSION_RESULT.
            source_id (str | None): Emissor; obrigatório em MISSION_RESULT.
            conversation_id (str | None): Conversa; obrigatória em CFP e MISSION_RESULT.
            schema_version (int): Versão do formato; tem de ser ``1``.

        Raises:
            TypeError: Se ``message_type`` não for ``MessageType``, ``payload`` não for um
                dicionário ou contiver valores não serializáveis.
            ValueError: Se um identificador estiver vazio, ``created_at`` ou
                ``schema_version`` forem inválidos, ou o payload tiver NaN/infinito ou
                violar as regras do tipo.
        """
        self.message_id = _require_identifier(message_id, "message_id")
        if not isinstance(message_type, MessageType):
            raise TypeError("message_type deve ser MessageType.")
        if not is_finite_number(created_at) or created_at < 0:
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
        if message_type is MessageType.MISSION_RESULT:
            for name, value in (("mission_id", mission_id), ("incident_id", incident_id),
                                ("conversation_id", conversation_id), ("source_id", source_id)):
                _require_identifier(value, name)
            for name in ("accept_message_id", "resource_id", "reason", "task"):
                _require_identifier(payload.get(name), name)
            if payload.get("outcome") not in ("confirmed", "not_confirmed", "inconclusive", "failed"):
                raise ValueError("Resultado de missão desconhecido.")
            completed = payload.get("completed_at")
            if not is_finite_number(completed) or not 0 <= completed <= created_at:
                raise ValueError("completed_at deve anteceder ou coincidir com a emissão.")
            if payload["resource_id"] != source_id:
                raise ValueError("O resultado deve identificar o recurso emissor.")
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
        """Devolver o envelope como dicionário, sem os identificadores a None.

        Returns:
            dict[str, Any]: Campos do envelope, com ``message_type`` como texto.
        """
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
        """Serializar em JSON com chaves ordenadas, revalidando antes o conteúdo.

        A revalidação apanha um payload alterado depois da criação.

        Returns:
            str: JSON estrito, sem escapar caracteres não ASCII.

        Raises:
            ValueError: Se o conteúdo tiver NaN ou infinito.
            TypeError: Se o conteúdo tiver valores não serializáveis.
        """
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
        """Construir a mensagem a partir de um dicionário, validada pelo construtor.

        Args:
            data (dict[str, Any]): Dicionário no formato de ``to_dict``.

        Returns:
            Message: Mensagem reconstruída.

        Raises:
            TypeError: Se ``data`` não for um dicionário.
            ValueError: Se faltarem campos obrigatórios ou ``message_type`` for desconhecido.

        Propaga também os erros do construtor (TypeError/ValueError).
        """
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
        """Ler uma mensagem em JSON; ValueError se for inválido ou tiver NaN.

        Args:
            payload (str): Texto JSON, normalmente o corpo de uma mensagem SPADE.

        Returns:
            Message: Mensagem descodificada e validada.

        Raises:
            ValueError: Se o JSON for inválido ou tiver ``NaN``/``Infinity``.
            TypeError: Se o JSON não for um objeto ou o payload não for um dicionário.
        """
        try:
            data = json.loads(payload, parse_constant=_reject_json_constant)
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("JSON inválido.") from error
        return cls.from_dict(data)
