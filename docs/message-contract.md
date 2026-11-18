# Contrato de mensagens anterior — referência histórica

[README](../README.md) · [Contrato atual: protocols.md](protocols.md) · [Arquitetura](architecture.md)

> **Em resumo**
>
> - Este ficheiro guardava a **primeira proposta** de contrato de mensagens (ramo `gui-batista`, commit `deca29f`), anterior à implementação dos agentes.
> - **Não descreve o código atual.** Confirmado a 18-11-2026: tipos, ontologia, protocolos, payloads e funções de validação são diferentes.
> - Para estudar ou implementar, usar [protocols.md](protocols.md) e [src/isia/communication/](../src/isia/communication/).
> - O texto integral da proposta foi retirado daqui para ninguém o estudar por engano. Continua no histórico do Git (comando no fim).

## O que mudou entre a proposta e o código

| Tema | Proposta histórica | Código atual |
|---|---|---|
| Tipos de mensagem | 13, incluindo `REFUSAL`, `RESERVATION_CONFIRMED` e `RESERVATION_FAILED` | 10 (`MessageType`, [messages.py](../src/isia/communication/messages.py)). Esses três não existem |
| Recusa de um CFP | Tipo `REFUSAL`, performativa `refuse` | Tipo `REJECT`, performativa `refuse` |
| Recusa de verificação | `REFUSAL` / `refuse` | Não existe: a fonte responde sempre `inform`, com `status=no_data` |
| Confirmação de reserva | `RESERVATION_CONFIRMED` (`agree`) ou `RESERVATION_FAILED` (`failure`) | `STATUS` (`inform`) com `status` `reserved` ou `reservation_failed` |
| `STATUS` | Anúncio do estado do recurso (posição, energia, validade) | Só a confirmação de reserva depois do `ACCEPT` |
| Falha de missão | `MISSION_RESULT` com performativa `failure` | Sempre `inform`, com `outcome=failed` |
| `INCIDENT_CLOSED` | Enviado aos envolvidos | Nunca enviado; fica na linha temporal do iniciador |
| `ALERT` | Enviado a vizinhos elegíveis | Só enviado entre iniciadores, com a opção `alert_distance` |
| Ontologia | `wildlife-monitoring` | `isia` |
| Protocolos | `verification`, `task-allocation`, `mission-report`, `resource-status`, `incident-lifecycle` | `verification` e `contract-net` |
| `conversation-id` | Só nos metadados | Nos metadados **e** no corpo (`conversation_id`); têm de coincidir |
| `reply-with` | Em todas as mensagens que esperam resposta | Só no `VERIFY_REQUEST` |
| Payload de `VERIFY_REQUEST` | `event_type`, `position`, `window_start`, `window_end`, `deadline` | `observation`, `hypothesis`, `question` |
| Payload de `VERIFY_RESPONSE` | `evidence`, `observations`, `reason` | `request_message_id`, `observations`, `status` (e, quando aplicável, `hypothesis` e `absence`) |
| Payload de `PROPOSAL` | `resource_id`, `eta_seconds`, `energy_cost_fraction`, `cost` | `cfp_message_id` e `bid` (`eta`, `energy_cost` em pontos percentuais, `load`). O custo é calculado pelo iniciador |
| Payload de `MISSION_RESULT` | `resource_id`, `outcome`, `observations`, `reason` | `accept_message_id`, `resource_id`, `task`, `outcome`, `reason`, `completed_at`, `position` |
| Prazo do CFP | Exclusivo | Inclusivo: `created_at == deadline` é válido |
| Campos extra e `null` | Rejeitados | Aceites; só `CFP` e `MISSION_RESULT` têm campos obrigatórios validados |
| Chaves JSON repetidas, `ground_truth` no corpo | Rejeitados pelo validador | Sem verificação específica nas mensagens |
| API de validação | Funções `validate_envelope`, `validate_message`, `validate_metadata`, `validate_reply`, `to_json`, `from_json` sobre dicionários | Classe `Message` (`to_dict`, `to_json`, `from_dict`, `from_json`) e `build_spade_message` / `parse_spade_message` |
| Transições de estado | Função `validate_transition(current, target)` | `IncidentState.change_status(...)` ([incident_state.py](../src/isia/domain/incident_state.py)) |

## O que se manteve

- O envelope: `schema_version` 1, `message_id`, `message_type`, `created_at` em segundos simulados e `payload`.
- As performativas de `VERIFY_REQUEST` (`request`), `VERIFY_RESPONSE` (`inform`), `CFP` (`cfp`), `PROPOSAL` (`propose`), `ACCEPT` (`accept-proposal`) e `REJECT` aos perdedores (`reject-proposal`).
- A ideia central: aceitar uma proposta não reserva o recurso; é preciso uma confirmação explícita.
- Os nove estados da ocorrência e os cinco da missão, com pequenas alterações nas transições ([architecture.md](architecture.md#5-ciclo-de-vida-de-um-incidente)).
- Os princípios: silêncio não prova nada, `no_data` não é evidência negativa, repetições não produzem segundo efeito.

## Ler a proposta original

```bash
git show d99ede4:docs/message-contract.md
```
