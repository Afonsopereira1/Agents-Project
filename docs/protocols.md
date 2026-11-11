# Comunicação, mensagens e protocolos — proposta

> **Estado revisto (11-11-2026):** modelos e contratos da Etapa 1 implementados e testados; comunicação `VERIFY_REQUEST`/`VERIFY_RESPONSE` real por SPADE/XMPP integrada na `main` na Etapa 3; corroboração e decisão preliminar implementadas na branch da Etapa 4. Contratos de negociação/missões, classificação explícita de evidência negativa e aprovação formal do grupo continuam pendentes. Os nomes de mensagens não são exigências literais do docente.

[README](../README.md) · [Arquitetura](architecture.md) · [Plano](development-plan.md) · [Decisões](architecture.md#decisões-pendentes)

## 1. Camadas da comunicação

| Camada | Responsabilidade | Proposta |
|---|---|---|
| Transporte | Entrega assíncrona entre identidades | SPADE + XMPP |
| Metadados da mensagem | Intenção, protocolo e associação à conversa | Campos/`metadata` com semântica FIPA-ACL |
| Corpo da mensagem | Dados do domínio | JSON UTF-8 validado e versionado |
| Protocolo | Ordem de mensagens, prazos, recusa e falhas | `verification`, `task-allocation`, `mission-report` |
| Lógica de domínio | Corroboração, reputação e decisões | Funções locais em `reasoning/`, sem gestor global |

**Nota:** `ALERT`, `VERIFY_REQUEST` etc. são **tipos de conteúdo do domínio**. `inform`, `request`, `cfp`, `propose`, `accept-proposal`, `reject-proposal` são *performatives* FIPA. Não devem ser confundidos.

## 2. Modelo base para mensagens

Proposta de contrato para o **corpo JSON** (campos obrigatórios mínimos marcados com `*`):

| Campo | Tipo | Significado |
|---|---|---|
| `schema_version`* | inteiro | Versão do contrato: começa em 1 |
| `message_id`* | string | Identificador global da mensagem, para deduplicar |
| `message_type`* | string | Tipo do conteúdo: `ALERT`, `CFP`, `PROPOSAL`, ... |
| `created_at`* | número finito não negativo | Instante da emissão em segundos simulados |
| `event_id` | string | Identificador de uma observação, **não** do incidente |
| `incident_id` | string | Identificador de ocorrência agrupando evidência relacionada |
| `mission_id` | string | Identificador da missão negociada/executada |
| `source_id` | string | Fonte original da observação, quando aplicável |
| `payload`* | objeto JSON | Dados específicos do tipo de mensagem |

### Contrato implementado na Etapa 1

O módulo `isia.communication.messages` implementa este contrato sem depender de
SPADE ou XMPP. A versão atual usa:

- `schema_version`: inteiro `1`.
- `message_id`, `event_id`, `incident_id`, `mission_id`, `source_id` e
  `conversation_id`: strings não vazias; cada identificador tem o seu domínio
  semântico e não deve ser reutilizado entre entidades.
- `message_type`: um dos tipos `ALERT`, `VERIFY_REQUEST`, `VERIFY_RESPONSE`,
  `CFP`, `PROPOSAL`, `ACCEPT`, `REJECT`, `MISSION_RESULT`, `STATUS` ou
  `INCIDENT_CLOSED`.
- `conversation_id`: identificador da conversa; é obrigatório em `CFP` e
  correlaciona mensagens relacionadas sem substituir `message_id`.
- `created_at`: número finito e não negativo em segundos de tempo simulado. O
  relógio começa em `0.0`; este campo não é um timestamp de parede nem uma data
  ISO-8601. Valores negativos, `NaN` e infinitos são inválidos.
- `payload`: objeto JSON, validado como dicionário no limite do contrato. A
  validação rejeita valores não serializáveis, chaves que não sejam strings,
  `NaN` e infinito. A validação específica do conteúdo de cada tipo será
  aprofundada nas etapas de verificação e negociação.

As mensagens podem ser convertidas com `Message.to_json()` e
`Message.from_json()`. Os modelos de domínio suportados podem ser convertidos
com `serialize_model()`/`deserialize_model()`, usando enums pelos seus valores
JSON e tuplos como listas JSON. `MessageDeduplicator` considera repetida uma
mensagem cujo `message_id` já foi aceite; não deduplica por conteúdo nem por
`event_id`. A política proposta para a futura retenção do registo local é de
`600.0` segundos simulados, mas a expiração operacional pertence a uma etapa
posterior.

As unidades partilhadas dos modelos são: posições inteiras não negativas numa
grelha 2D; distância euclidiana em unidades da grelha; tempo simulado e ETA em
segundos, iniciados em `0.0` e separados dos timeouts reais do SPADE; autonomia
como percentagem entre `0` e `100`; `Bid.energy_cost` em pontos percentuais de
autonomia, podendo exceder `100` quando a missão é estimada como inviável;
`Mission.priority` como inteiro não negativo, em que valores maiores são mais
urgentes; e `Bid.load` entre `0` e `1`.

`Observation.confidence_score` é uma pontuação entre `0` e `1` sobre a
confiança da fonte no sinal. `intensity_score`, quando representado, é um
campo opcional separado entre `0` e `1`; a relação semântica entre ambos deve
ser mantida distinta. Os IDs devem ser únicos dentro da sua entidade e podem
usar UUID quando forem gerados novos; os IDs históricos legíveis continuam
compatíveis.

Os estados de incidente implementados em `domain.incident_state` são
`DETECTED`, `VERIFYING`, `ASSESSING`, `WATCHING`, `ALLOCATING`, `RESPONDING`,
`CLOSED`, `EXPIRED` e `UNRESOLVED`. As transições seguem o diagrama da
arquitetura e são imutáveis: cada mudança devolve um novo `IncidentState`.

`CFP` exige `mission_id`, `incident_id` e `conversation_id`, além de um
`payload` com `task`, `target` (`x`/`y`), `required_capability`, `priority` e
`deadline` em segundos simulados. Esta validação é estrutural; a negociação e
a reserva pertencem a etapas posteriores.

**Aprovação formal ainda pendente dos três elementos:** confirmar estes
contratos e a política proposta de retenção de `600.0` segundos. Esta
implementação não impõe UUID aos IDs existentes, não implementa expiração
operacional, transporte, agentes SPADE, corroboração ou Contract Net.

Metadados SPADE recomendados: `performative`, `ontology`, `protocol`, `conversation-id` (ou correlação por `thread`, a validar no SPADE escolhido), `reply-with` e `in-reply-to` quando aplicáveis. O endereço do remetente/destinatário deverá ser obtido e validado pela infraestrutura SPADE, evitando confiar cegamente num `source_id` declarado no corpo.

### Exemplo — observação de um sensor

```json
{
  "schema_version": 1,
  "message_id": "msg-001",
  "message_type": "ALERT",
  "created_at": 120.0,
  "event_id": "obs-001",
  "incident_id": "incident-07",
  "source_id": "sensor_01",
  "payload": {
    "event_type": "gunshot_like_sound",
    "position": {"x": 6, "y": 9},
    "confidence_score": 0.82,
    "intensity_score": 0.65,
    "sensor_modality": "acoustic"
  }
}
```

Aqui `confidence_score` é a pontuação atribuída pela fonte ao sinal e **não** uma probabilidade calibrada de caça furtiva; a sua relação final com intensidade ainda requer aprovação. `created_at` usa segundos de tempo simulado, iniciado em zero.

Exemplo inválido (não pode ser aceite pelo contrato):

```json
{"schema_version": 1, "message_id": "msg-err", "message_type": "ALERT", "created_at": -1.0, "payload": {"value": NaN}}
```

Além do instante negativo, `NaN` não pertence ao JSON estrito. A implementação
rejeita ambos, bem como `Infinity`, objetos Python não serializáveis e JSON
malformado.

### Exemplo — pedido de propostas

```json
{
  "schema_version": 1,
  "message_id": "msg-014",
  "message_type": "CFP",
  "created_at": 128.0,
  "conversation_id": "conversation-03",
  "incident_id": "incident-07",
  "mission_id": "mission-03",
  "payload": {
    "task": "verify_incident",
    "target": {"x": 6, "y": 9},
    "required_capability": "mobile_verification",
    "deadline": 138.0,
    "priority": 2
  }
}
```

A prioridade é um inteiro não negativo no modelo atual, mas a unidade/escala e
os campos obrigatórios específicos de `CFP` continuam por aprovar; não significa
que exista atualmente uma escala de severidade aprovada.

## 3. Tipos de mensagens e intenção

| Tipo lógico | Performative sugerida | Emissor → destinatário | Resposta esperada |
|---|---|---|---|
| `ALERT` | `inform` | Sensor/informador → vizinhos elegíveis | Opcional: verificação |
| `VERIFY_REQUEST` | `request` | Iniciador local → fontes próximas | `VERIFY_RESPONSE` / `refuse` / timeout |
| `VERIFY_RESPONSE` | `inform` ou `refuse` | Fonte → iniciador | Evidência/ausência; referência ao pedido |
| `CFP` | `cfp` | Iniciador → recursos candidatos | `PROPOSAL` / `refuse` |
| `PROPOSAL` | `propose` | Recurso → iniciador | `ACCEPT` / `REJECT` |
| `ACCEPT` | `accept-proposal` | Iniciador → recurso | Confirmação de reserva ou falha |
| `REJECT` | `reject-proposal` | Iniciador → recurso | Nenhuma; libertar eventual reserva provisória |
| `MISSION_RESULT` | `inform` / `failure` | Patrulha/ranger → iniciador ou pares relevantes | Atualização de estado |
| `STATUS` | `inform` | Recurso → agentes interessados | Atualização temporizada |
| `INCIDENT_CLOSED` | `inform` | Agente que encerra → envolvidos | Deduplicação e fecho local |

Nem todos os esquemas propostos correspondem formalmente a um protocolo FIPA completo. Devemos dizer **«inspirado em FIPA»** salvo quando respeitarmos integralmente as sequências e a semântica documentadas.

## 4. Verificação distribuída

```mermaid
sequenceDiagram
  participant S1 as Sensor 1 / iniciador local
  participant S2 as Sensor 2
  participant I as Informador
  S1->>S2: request / VERIFY_REQUEST
  S1->>I: request / VERIFY_REQUEST
  alt Evidência existente
    S2-->>S1: inform / VERIFY_RESPONSE
  else Não tem dados ou não consegue observar
    S2-->>S1: inform (ausência) ou refuse
  end
  opt Informador responde dentro do prazo
    I-->>S1: inform / VERIFY_RESPONSE
  end
  Note over S1: Validar janela temporal, área e IDs; tratar timeout
  Note over S1: Calcular evidência local sem acesso à verdade
```

**Critérios de compatibilidade a parametrizar:** raio espacial, janela temporal, modalidades, independência aproximada e validade das fontes. Duas mensagens da **mesma observação** nunca contam como fontes distintas. A falta de deteção só pesa contra a hipótese de ameaça se o sensor tinha capacidade e oportunidade de observar.

## 5. Atribuição distribuída: Contract Net simplificado

```mermaid
sequenceDiagram
  participant M as Iniciador do incidente
  participant D as Drone
  participant V as Veículo
  M->>D: cfp / CFP
  M->>V: cfp / CFP
  D-->>M: propose / PROPOSAL ou refuse
  V-->>M: propose / PROPOSAL ou refuse
  Note over M: Prazo: ignorar propostas tardias e avaliar elegibilidade
  alt Proposta válida aceite
    M->>D: accept-proposal / ACCEPT
    M->>V: reject-proposal / REJECT
    D-->>M: agree / reserva confirmada
    D-->>M: inform ou failure / MISSION_RESULT
  else Sem proposta elegível
    Note over M: Marcar incidente não resolvido ou tentar nova ronda
  end
```

### Regras operacionais

1. Cada CFP contém `conversation-id`, `mission_id`, capacidades mínimas e `deadline`.
2. O recurso avalia localmente se pode executar, rejeitando missões incompatíveis com a sua disponibilidade ou autonomia.
3. A proposta calcula ETA, consumo energético e custo dentro de unidades explicitadas.
4. O iniciador ignora propostas tardias, duplicadas e de missões diferentes.
5. A aceitação só se torna **missão confirmada** após o recurso garantir uma reserva válida.
6. A ausência de confirmação ou falha é tratada com timeout, estado explícito e eventual negociação alternativa.
7. A perda do iniciador deve ter uma política de recuperação acordada (p. ex. expiração de liderança local e novo iniciador determinístico). **Ainda não está definida.**
8. O encerramento deve ser idempotente: mensagens repetidas não criam novas missões.

## 6. Estado e ordenação

- `Observation`: identificada por `event_id`; permanece imutável após emissão.
- `Incident`: agrupa observações; pode ter revisões de avaliação.
- `Mission`: tem `mission_id` único e transições validadas (`PROPOSED` → `RESERVED` → `RUNNING` → `DONE`/`FAILED`).
- Guardar `message_id` processados por uma janela finita para evitar duplicação, com política de expiração.
- Mensagens fora de ordem devem ser rejeitadas ou reconciliadas com base em estado/versão.
- O transporte não garante, por si só, execução de missão; distinguir **mensagem recebida**, **pedido aceite** e **tarefa concluída**.

## 7. Gestão de erros e falhas

| Falha | Tratamento proposto | Teste |
|---|---|---|
| Fonte indisponível | Prazo de verificação e marcação de evidência incompleta | Desligar sensor durante pedido |
| Mensagem duplicada | Deduplicação por `message_id`/`event_id` | Reenviar mensagem idêntica |
| Mensagem tardia | Conferir `deadline` e estado da conversa | Atrasar uma proposta após o fecho |
| Dupla atribuição | Reserva atómica por recurso | Duas conversas concorrentes |
| Recurso sem energia | `refuse` com motivo | Bateria inferior à reserva mínima |
| Falha de missão | `failure`, libertação/reavaliação | Interromper recurso em movimento |
| Falha do iniciador | Política de substituição ainda pendente | Simular desaparecimento do iniciador |
| Mensagem inválida | Validação + rejeição sem crash | JSON malformado ou campos ausentes |
| Conectividade degradada | Perda/atraso no adaptador de transporte | Comparar cenários de rede |

## 8. Implementação e compatibilidade SPADE

Na Etapa 3 foram verificados com SPADE 4.1.4: `spade.agent.Agent`, `OneShotBehaviour`, `CyclicBehaviour`, `spade.message.Message`, `Template`, `send`/`receive` e metadados, com demonstração real XMPP. `PeriodicBehaviour` não foi necessário. O suporte de mensagens com metadados não implica validação integral de conformidade FIPA-ACL, que exigiria teste específico.

Os contratos atuais estão implementados em `communication/messages.py`, o adaptador SPADE/XMPP em `communication/transport.py`, e a correlação de conversas nos comportamentos dos agentes. `communication/protocols.py` e a injeção parametrizada de perda/latência permanecem propostas para etapas posteriores. Os testes de serialização e mocks não substituem testes de entrega real XMPP; ambos foram executados separadamente para as Etapas 3–4.

## 9. Checklist de aprovação

- [ ] Escolher versão final do contrato e unidade do relógio.
- [ ] Acordar IDs, destinatários, convenção de correlação e prazos.
- [ ] Definir campos mínimos de `Observation`, `Mission` e `Bid`.
- [ ] Confirmar performatives/protocolos suportados pela versão SPADE usada.
- [ ] Documentar recusa, timeout, deduplicação, reserva e recuperação.
- [ ] Escrever primeiro os testes dos fluxos de verificação e de atribuição.
