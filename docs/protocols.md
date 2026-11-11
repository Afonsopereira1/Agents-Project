# Comunicação, mensagens e protocolos — proposta

> **Estado revisto (11-11-2026):** as Etapas 1–5 estão integradas na `main` (PRs #7, #8 e #9). A última execução local no Ubuntu teve **249 testes, OK**; a verificação e o Contract Net foram demonstrados separadamente por SPADE/XMPP real, incluindo a reserva confirmada no fluxo normal. As correções recentes de ausência informativa e deduplicação foram validadas localmente nesta branch, aguardando integração final no PR. Falhas, timeouts, mensagens tardias e rondas limitadas têm testes unitários/mocks, não validação XMPP real em todos os cenários. A integração automática de missões e a execução pertencem à Etapa 6; as aprovações formais do grupo continuam pendentes.

[README](../README.md) · [Arquitetura](architecture.md) · [Plano](development-plan.md) · [Decisões](architecture.md#decisões-pendentes)

## 1. Camadas da comunicação

| Camada | Responsabilidade | Proposta |
|---|---|---|
| Transporte | Entrega assíncrona entre identidades | SPADE + XMPP |
| Metadados da mensagem | Intenção, protocolo e associação à conversa | Campos/`metadata` com semântica FIPA-ACL |
| Corpo da mensagem | Dados do domínio | JSON UTF-8 validado e versionado |
| Protocolo | Ordem de mensagens, prazos, recusa e falhas | `verification`, `contract-net` |
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

Os contratos de negociação usados atualmente estão implementados em
`src/isia/reasoning/allocation.py`, e o adaptador SPADE/XMPP está em
`src/isia/communication/transport.py`. A implementação não impõe UUID aos IDs
existentes, mas gera IDs locais únicos para CFPs, conversas, ACCEPTs e estados.

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

O `VERIFY_REQUEST` pode incluir o campo opcional `hypothesis`, sem alterar
`schema_version`, com `hypothesis_id`, `event_type`, `position`, `valid_from` e
`valid_until`. Pedidos antigos sem este campo continuam válidos. Uma resposta
`VERIFY_RESPONSE` pode ecoar a hipótese e declarar
`evidence_relation: "contradictory"`; essa relação só produz
`contradictory` quando o iniciador fornece uma regra de incompatibilidade
explícita. Tipos de evento diferentes não são contraditórios por omissão.
Para `compatible`, tipos diferentes também exigem uma regra explícita de
compatibilidade; por omissão, só tipos iguais são compatíveis. Sem essa regra,
a observação é preservada e classificada como `inconclusive`.

Uma fonte só pode produzir `status: "informative_absence"` quando declara
explicitamente `declared_non_detection: true` e fornece `absence` com a
hipótese, intervalo observado e `coverage` validada: posição, raio, capacidade
validada e oportunidade confirmada. `no_data`, timeout, `refuse` ou falha de
comunicação nunca são ausência informativa. A ausência pode contar para a
cobertura de informação, mas não é evidência compatível nem prova de
inexistência do evento; falsos negativos continuam a ser uma limitação.

Na versão atual do simulador, a capacidade é a modalidade `Source.kind`:
`acoustic` → `gunshot_like_sound`, `visual` → `suspicious_movement`,
`human` → `suspicious_activity_report` (constante `SIGNALS`). Para ausência
informativa, a modalidade declarada deve corresponder ao tipo de sinal
na hipótese. Tipos desconhecidos ou metadados antigos sem hipótese/capacidade
resultam conservadoramente em `no_data` no informador. Esta verificação
estabelece compatibilidade semântica, não sensibilidade perfeita ou uma
probabilidade calibrada; não utiliza `ground_truth`.

Quando a mesma avaliação contém evidência compatível e contraditória,
mesmo na mesma resposta, o resultado é `inconclusive`, preservando os
identificadores de ambas. A classificação é feita por observação: uma
`evidence_relation: "contradictory"` só habilita a categoria contraditória
para tipos cobertos por uma regra de incompatibilidade e hipótese correlacionada;
não elimina observações compatíveis presentes na resposta. A decisão
`request_mobile_verification` é uma ação para obter mais evidência, não uma
confirmação do incidente: também pode ser adequada perante conflito,
sem antecipar a reputação da Etapa 7. As regras
concretas de incompatibilidade, os limiares de cobertura e a interpretação das
taxas de falsos negativos continuam dependentes de aprovação do grupo.

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
    D-->>M: inform / STATUS(reserved)
    Note over M: Só depois da confirmação: Mission.PROPOSED → RESERVED
  else Reserva recusada explicitamente
    D-->>M: inform / STATUS(reservation_failed)
    Note over M: Nova ronda limitada, com novo CFP/conversa
  else Confirmação desconhecida
    Note over M: Timeout real; não enviar outro ACCEPT
  else Sem proposta elegível
    Note over M: Marcar incidente não resolvido ou tentar nova ronda
  end
```

### Regras operacionais

1. Cada CFP contém `conversation-id`, `mission_id`, `incident_id`, capacidades mínimas e `deadline`.
2. O recurso avalia localmente se pode executar, rejeitando missões incompatíveis com a sua disponibilidade ou autonomia.
3. A proposta calcula ETA, consumo energético e custo dentro de unidades explicitadas.
4. O iniciador ignora propostas tardias, duplicadas e de missões diferentes.
5. A aceitação só se torna **missão confirmada** após o recurso garantir uma reserva válida.
6. `STATUS(reserved)` confirma a reserva; `STATUS(reservation_failed)` é uma recusa explícita. Um timeout depois de `ACCEPT` produz `confirmation_unknown` e não autoriza outro `ACCEPT` automático.
7. O `deadline` do CFP é inclusivo em segundos simulados: uma resposta com `created_at == deadline` é válida; apenas uma resposta posterior é tardia. O timeout real de receção XMPP é independente.
7. A nova ronda só é permitida após recusa explícita, usa novos IDs e está limitada a duas rondas (`CONTRACT_MAX_ROUNDS`); ausência de propostas produz `no_eligible_proposals`.
8. O encerramento deve ser idempotente: mensagens repetidas não criam novas missões nem reservas incompatíveis. A perda do iniciador continua sem política de recuperação distribuída.

### Resultados da ronda

O iniciador expõe quatro resultados distintos, sem os converter
silenciosamente em estados de missão:

| Resultado | Condição | Estado da missão |
|---|---|---|
| `reservation_confirmed` | `STATUS/inform` válido com `status=reserved` | `RESERVED` |
| `no_eligible_proposals` | nenhuma `PROPOSAL` válida antes do `ACCEPT` | permanece `PROPOSED` |
| `reservation_rejected` | recurso respondeu `STATUS/inform` com `reservation_failed` | permanece `PROPOSED` |
| `confirmation_unknown` | nenhum `STATUS` correlacionado chegou no timeout real | permanece `PROPOSED`; não há novo `ACCEPT` automático |

As propostas são comparadas por custo normalizado:
`w_eta * ETA/eta_scale + w_energy * energy/energy_scale +
w_load * load/load_scale`. O desempate é determinístico por `resource_id` e
`message_id`. Uma proposta não reserva o recurso; a reserva ocorre apenas ao
processar `ACCEPT` no agente móvel através de `LocalResourceReservation`.

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

Na Etapa 3 foram verificados com SPADE 4.1.4: `spade.agent.Agent`, `OneShotBehaviour`, `CyclicBehaviour`, `spade.message.Message`, `Template`, `send`/`receive` e metadados, com demonstração real XMPP. Na Etapa 5, `MobileResourceAgent` reutiliza `CyclicBehaviour` e `Template` para `CFP` e `accept-proposal`; `contract_net_demo.py` usa `OneShotBehaviour` no iniciador. `PeriodicBehaviour` não foi necessário. O suporte de mensagens com metadados não implica validação integral de conformidade FIPA-ACL, que exigiria teste específico.

Os contratos atuais estão implementados em `src/isia/communication/messages.py`, o adaptador SPADE/XMPP em `src/isia/communication/transport.py`, a lógica de alocação em `src/isia/reasoning/allocation.py`, e a correlação nos comportamentos dos agentes e no demo. Não existe atualmente `communication/protocols.py` separado, nem módulos específicos `drone.py`, `vehicle.py` ou `ranger.py`; o recurso móvel comum está em `src/isia/agents/mobile.py`. A injeção parametrizada de perda/latência permanece proposta para etapas posteriores. Os testes de serialização e mocks não substituem testes de entrega real XMPP; na Etapa 5 o cenário normal foi executado com XMPP e os cenários de falha foram testados localmente com mocks/determinismo.

## 9. Checklist de aprovação

- [ ] Escolher versão final do contrato e unidade do relógio.
- [ ] Acordar IDs, destinatários, convenção de correlação e prazos.
- [ ] Definir campos mínimos de `Observation`, `Mission` e `Bid`.
- [ ] Confirmar performatives/protocolos suportados pela versão SPADE usada.
- [ ] Documentar recusa, timeout, deduplicação, reserva e recuperação.
- [ ] Escrever primeiro os testes dos fluxos de verificação e de atribuição.
