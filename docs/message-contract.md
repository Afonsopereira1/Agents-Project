# Contrato de mensagens anterior — referência histórica

> **Histórico de `gui-batista` (`deca29f`).** Esta proposta descreve a implementação
> anterior à integração de `origin/main` (`c07b946`). Os validadores, formatos e
> comandos abaixo não correspondem à base ativa. Para trabalhar no projeto, seguir
> [o contrato atual](protocols.md) e o código em `src/isia/`.

Esta referência preserva os formatos e exemplos dos validadores existentes. Consultar apenas os tipos necessários à entrega em curso. Para começar, seguir o [guia de comunicação](protocols.md). Ter um validador não significa que o respetivo fluxo entre agentes esteja implementado.

**Proposta v1, ainda a validar pelo grupo.** Já existem validadores de mensagens e estados, testados sem SPADE. A troca de mensagens entre agentes, as reservas e a integração com os modelos ainda estão por implementar.

[README](../README.md) · [Arquitetura](architecture.md) · [Plano](development-plan.md) · [Decisões](architecture.md#decisões-pendentes)

## 1. Como funciona

Um agente deteta um sinal, pede confirmação a outras fontes e avalia a evidência. Se for necessária uma missão, pede propostas aos recursos disponíveis. O recurso escolhido confirma a reserva, executa a missão e comunica o resultado.

Cada mensagem tem duas partes:

- **Corpo JSON:** o que aconteceu e os dados necessários, como incidente, missão e observações.
- **Metadados:** a intenção da mensagem e a ligação à conversa e ao pedido anterior.

Por exemplo, `PROPOSAL` é o tipo do corpo; `propose` é a intenção, chamada *performative*. O transporte previsto é SPADE + XMPP. As decisões são locais, sem gestor global.

O protocolo é **inspirado em FIPA**. Os nomes, formatos e passos adicionais são propostas do projeto, não exigências literais do docente nem prova de conformidade FIPA.

## 2. Formato das mensagens

### Corpo JSON

Os campos marcados com * são obrigatórios em todas as mensagens.

| Campo | Significado |
|---|---|
| `schema_version`* | Inteiro exato `1`; `true` e `1.0` são inválidos. |
| `message_id`* | ID da mensagem. Mantém-se numa retransmissão. |
| `message_type`* | Um dos 13 tipos da secção 3. |
| `created_at`* | Instante de emissão, em segundos de simulação. |
| `event_id` | ID da observação original. |
| `incident_id` | ID do incidente que reúne a evidência. |
| `mission_id` | ID de uma missão desse incidente. |
| `source_id` | Fonte original da observação, mesmo quando outro agente a reencaminha. |
| `payload`* | Objeto com os dados específicos do tipo de mensagem. |

**Regras comuns:**

- Textos e IDs têm de conter algum carácter além de espaços. Preservar o valor exato, sem corrigir espaços ou maiúsculas.
- Números são finitos e não negativos; booleanos não contam como números. Tempos e durações usam segundos de simulação. O timeout real do transporte usa outra medida.
- Posições têm apenas `x` e `y`, inteiros não negativos. Os limites da grelha dependem do ambiente.
- Aceitar apenas os campos definidos neste documento, incluindo nos objetos internos. Todos os campos de cada payload são obrigatórios.
- Rejeitar `null`, chaves JSON repetidas, chaves não textuais e valores sem representação JSON. `ground_truth`, a verdade interna do simulador, é proibido em qualquer nível.
- Omitir IDs opcionais desconhecidos. Não usar texto vazio ou `null` como substituto.

O remetente e o destinatário vêm do transporte. Declarar `source_id` não autentica quem enviou a mensagem.

### IDs por tipo

Esta tabela refere-se aos IDs fora de `payload`: **O** = obrigatório; **P** = opcional; **—** = deve estar ausente; **C** = depende do pedido.

| `message_type` | `event_id` | `incident_id` | `mission_id` | `source_id` |
|---|---|---|---|---|
| `ALERT` | O | P | — | O |
| `VERIFY_REQUEST` | — | O | — | — |
| `VERIFY_RESPONSE` | — | O | — | — |
| `CFP` | — | O | O | — |
| `PROPOSAL` | — | O | O | — |
| `ACCEPT` | — | O | O | — |
| `REJECT` | — | O | O | — |
| `REFUSAL` | — | O | C | — |
| `RESERVATION_CONFIRMED` | — | O | O | — |
| `RESERVATION_FAILED` | — | O | O | — |
| `MISSION_RESULT` | — | O | O | — |
| `STATUS` | — | — | — | — |
| `INCIDENT_CLOSED` | — | O | P | — |

`REFUSAL` inclui `mission_id` ao recusar um CFP e omite-o ao recusar verificação. É preciso comparar com o pedido guardado para validar esta regra.

Um `ALERT` pode existir antes de ser associado a um incidente. `INCIDENT_CLOSED` só inclui missão se o encerramento estiver ligado a uma. `STATUS` identifica o recurso em `payload.resource_id`.

Não repetir no payload os IDs da mensagem, incidente, missão ou pedido. As observações completas dentro de uma lista têm os seus próprios `event_id` e `source_id`.

### Metadados e ligação entre mensagens

Os metadados são um dicionário de textos separado do corpo JSON. As chaves e valores fixos são exatos; campos inaplicáveis ficam ausentes.

| Chave | Regra |
|---|---|
| `performative` | Intenção indicada na secção 3. |
| `ontology` | Sempre `wildlife-monitoring`. |
| `protocol` | Protocolo indicado na secção 3. |
| `conversation-id` | ID da conversa/ronda. Não substitui incidente ou missão. |
| `reply-with` | Só em mensagens que esperam resposta; igual ao próprio `message_id`. |
| `in-reply-to` | Só em respostas; igual ao `reply-with` da mensagem anterior. |

As primeiras quatro chaves são sempre obrigatórias. Não acrescentar `message_type` nem uma chave alternativa `thread`. O mapeamento para SPADE será verificado na integração.

| Mensagem | Responde a | Espera resposta |
|---|---|---|
| `ALERT`, `STATUS`, `INCIDENT_CLOSED` | — | Não |
| `VERIFY_REQUEST` | — | `VERIFY_RESPONSE` ou `REFUSAL` |
| `VERIFY_RESPONSE` | `VERIFY_REQUEST` | Não |
| `CFP` | — | `PROPOSAL` ou `REFUSAL` |
| `PROPOSAL` | `CFP` | `ACCEPT` ou `REJECT` |
| `ACCEPT` | `PROPOSAL` | `RESERVATION_CONFIRMED` ou `RESERVATION_FAILED` |
| `REJECT` | `PROPOSAL` | Não |
| `REFUSAL` | `VERIFY_REQUEST` ou `CFP` | Não |
| `RESERVATION_CONFIRMED` | `ACCEPT` | `MISSION_RESULT` |
| `RESERVATION_FAILED` | `ACCEPT` | Não |
| `MISSION_RESULT` | `RESERVATION_CONFIRMED` | Não |

Cada resposta tem um `message_id` próprio. A conversa, os IDs de domínio e o recurso têm de corresponder ao pedido guardado. O protocolo também se mantém, exceto em `MISSION_RESULT`: muda de `task-allocation` para `mission-report`, mantendo a conversa da reserva. `REFUSAL` usa o protocolo do pedido recusado.

Uma nova ronda usa outra `conversation-id`. Passar de verificação a negociação também inicia outra conversa. Uma nova missão recebe outro `mission_id`, mantendo o incidente. Cada anúncio (`ALERT`, `STATUS`, `INCIDENT_CLOSED`) tem conversa própria; retransmiti-lo preserva corpo e metadados. A verificação motivada por um alerta não é uma resposta ACL ao alerta.

**Prazos:** respostas diretas a `VERIFY_REQUEST` e `CFP`, incluindo recusas, têm de ser emitidas e recebidas antes de `payload.deadline`. No instante limite já são tardias. Esse prazo não se aplica à aceitação, reserva ou execução da missão; esses passos precisam de prazos próprios.

Metadados do CFP `msg-014`:

```json
{
  "performative": "cfp",
  "ontology": "wildlife-monitoring",
  "protocol": "task-allocation",
  "conversation-id": "allocation-03-r1",
  "reply-with": "msg-014"
}
```

Metadados da proposta `msg-015`, em resposta ao CFP:

```json
{
  "performative": "propose",
  "ontology": "wildlife-monitoring",
  "protocol": "task-allocation",
  "conversation-id": "allocation-03-r1",
  "reply-with": "msg-015",
  "in-reply-to": "msg-014"
}
```

### Exemplo: observação de um sensor

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
    "observed_at": 119.0,
    "confidence_score": 0.82
  }
}
```

`observed_at` é o instante da observação; `created_at`, o da emissão. `confidence_score` é a pontuação da fonte para o sinal, não uma probabilidade calibrada de caça furtiva.

### Exemplo: pedido de propostas

```json
{
  "schema_version": 1,
  "message_id": "msg-014",
  "message_type": "CFP",
  "created_at": 128.0,
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

O CFP pede um recurso para verificar o incidente. `deadline` limita a chegada de propostas. A escala de prioridade ainda precisa de acordo do grupo.

## 3. Tipos e conteúdo

### Intenção e destinatários

| Tipo | `performative` | `protocol` | Quem envia → quem recebe |
|---|---|---|---|
| `ALERT` | `inform` | `verification` | Sensor/informador → vizinhos elegíveis |
| `VERIFY_REQUEST` | `request` | `verification` | Iniciador → fontes próximas |
| `VERIFY_RESPONSE` | `inform` | `verification` | Fonte → iniciador |
| `CFP` | `cfp` | `task-allocation` | Iniciador → recursos candidatos |
| `PROPOSAL` | `propose` | `task-allocation` | Recurso → iniciador |
| `ACCEPT` | `accept-proposal` | `task-allocation` | Iniciador → recurso escolhido |
| `REJECT` | `reject-proposal` | `task-allocation` | Iniciador → recurso não escolhido |
| `REFUSAL` | `refuse` | Protocolo do pedido | Fonte/recurso → iniciador |
| `RESERVATION_CONFIRMED` | `agree` | `task-allocation` | Recurso → iniciador |
| `RESERVATION_FAILED` | `failure` | `task-allocation` | Recurso → iniciador |
| `MISSION_RESULT` | `failure` se `failed`; senão `inform` | `mission-report` | Executor → iniciador |
| `STATUS` | `inform` | `resource-status` | Recurso → interessados |
| `INCIDENT_CLOSED` | `inform` | `incident-lifecycle` | Agente que encerra → envolvidos |

`REFUSAL` recusa um pedido; `REJECT` rejeita uma proposta recebida. `RESERVATION_FAILED` indica falha de reserva após aceitação; `MISSION_RESULT` com `failed` indica falha de execução.

### Campos do payload

Todos os campos abaixo são obrigatórios, mesmo quando `observations` está vazia. Não são permitidos campos extra.

Uma **observação completa** contém `event_id`, `source_id`, `event_type`, `position`, `observed_at` e `confidence_score`. Os três primeiros são textos; a confiança está em `[0, 1]`. Numa lista, `event_id` não se repete e cada `observed_at <= created_at`. Várias observações podem vir da mesma fonte.

| Tipo | Campos e regras |
|---|---|
| `ALERT` | `event_type` (texto), `position`, `observed_at <= created_at`, `confidence_score` em `[0, 1]`. Os IDs da observação estão fora do payload. |
| `VERIFY_REQUEST` | `event_type`, `position`, `window_start`, `window_end`, `deadline`. Janela inclusiva: `window_start <= window_end <= created_at`; `deadline > created_at`. |
| `VERIFY_RESPONSE` | `evidence`, `observations`, `reason`. `compatible` e `contradictory` exigem observações; `informative_absence` e `no_data` exigem lista vazia. |
| `CFP` | `task` e `required_capability` (textos), `target` (posição), `priority` (inteiro não negativo), `deadline > created_at`. Proposta: maior valor indica maior prioridade, sem máximo fixado. |
| `PROPOSAL` | `resource_id`, `eta_seconds`, `energy_cost_fraction`, `cost`. ETA conta desde a emissão. Energia em `[0, 1]`: fração da capacidade total estimada para executar e regressar. Custo é uma pontuação não negativa, sem unidade; a fórmula ainda precisa de acordo. |
| `ACCEPT` | `resource_id` da proposta escolhida. Ainda não confirma reserva. |
| `REJECT` | `resource_id`, `reason`. |
| `REFUSAL` | `reason`. O pedido recusado é identificado nos metadados. |
| `RESERVATION_CONFIRMED` | `resource_id`. Declara a reserva para a missão indicada no corpo. |
| `RESERVATION_FAILED` | `resource_id`, `reason`. |
| `MISSION_RESULT` | `resource_id`, `outcome`, `observations`, `reason`. Resultados: `confirmed`, `not_confirmed`, `inconclusive`, `failed`. Os dois primeiros exigem observações; os restantes admitem lista vazia. |
| `STATUS` | `resource_id`, `position`, `available` (booleano), `energy_fraction` em `[0, 1]`, `observed_at <= created_at`, `valid_until >= observed_at`. Energia é a fração restante da capacidade total. |
| `INCIDENT_CLOSED` | `terminal_state`, `outcome`, `reason`. `CLOSED` exige `confirmed` ou `not_confirmed`; `EXPIRED` e `UNRESOLVED` exigem `inconclusive` ou `failed`. |

`confirmed` e `not_confirmed` são conclusões locais sobre a ameaça. `not_confirmed` exige evidência que sustente a sua ausência; falta de dados não basta. `inconclusive` preserva a incerteza e `failed` indica falha operacional. Nenhum resultado representa a verdade interna do simulador.

Quem recebe ainda precisa de avaliar a evidência e o contexto. Por exemplo, deve verificar se um `STATUS` já expirou e se as observações são pertinentes para a área e o período pedidos. Evidência contraditória não tem de repetir exatamente a posição ou o tipo de evento do pedido.

### Exemplos dos restantes tipos

Cada elemento abaixo é uma mensagem separada. `from_json` não aceita este array como lote. São exemplos do formato, não registos de uma execução.

Alguns mostram alternativas: aceitar ou rejeitar a proposta; confirmar ou falhar a reserva. `MISSION_RESULT` só responde ao ramo com reserva confirmada.

```json
[
  {
    "schema_version": 1, "message_id": "msg-002", "message_type": "VERIFY_REQUEST", "created_at": 121.0,
    "incident_id": "incident-07",
    "payload": {"event_type": "gunshot_like_sound", "position": {"x": 6, "y": 9}, "window_start": 110.0, "window_end": 120.0, "deadline": 126.0}
  },
  {
    "schema_version": 1, "message_id": "msg-003", "message_type": "VERIFY_RESPONSE", "created_at": 124.0,
    "incident_id": "incident-07",
    "payload": {"evidence": "compatible", "observations": [{"event_id": "obs-002", "source_id": "sensor_02", "event_type": "gunshot_like_sound", "position": {"x": 6, "y": 9}, "observed_at": 119.5, "confidence_score": 0.7}], "reason": "Sinal compatível observado dentro da janela pedida."}
  },
  {
    "schema_version": 1, "message_id": "msg-004", "message_type": "REFUSAL", "created_at": 123.0,
    "incident_id": "incident-07",
    "payload": {"reason": "Fonte indisponível para executar a verificação pedida."}
  },
  {
    "schema_version": 1, "message_id": "msg-015", "message_type": "PROPOSAL", "created_at": 130.0,
    "incident_id": "incident-07", "mission_id": "mission-03",
    "payload": {"resource_id": "drone_01", "eta_seconds": 12.0, "energy_cost_fraction": 0.2, "cost": 3.5}
  },
  {
    "schema_version": 1, "message_id": "msg-016", "message_type": "ACCEPT", "created_at": 138.0,
    "incident_id": "incident-07", "mission_id": "mission-03",
    "payload": {"resource_id": "drone_01"}
  },
  {
    "schema_version": 1, "message_id": "msg-017", "message_type": "REJECT", "created_at": 138.0,
    "incident_id": "incident-07", "mission_id": "mission-03",
    "payload": {"resource_id": "drone_01", "reason": "Selecionada outra proposta elegível."}
  },
  {
    "schema_version": 1, "message_id": "msg-018", "message_type": "RESERVATION_CONFIRMED", "created_at": 139.0,
    "incident_id": "incident-07", "mission_id": "mission-03",
    "payload": {"resource_id": "drone_01"}
  },
  {
    "schema_version": 1, "message_id": "msg-019", "message_type": "RESERVATION_FAILED", "created_at": 139.0,
    "incident_id": "incident-07", "mission_id": "mission-03",
    "payload": {"resource_id": "drone_01", "reason": "Recurso ficou indisponível antes da reserva."}
  },
  {
    "schema_version": 1, "message_id": "msg-020", "message_type": "MISSION_RESULT", "created_at": 146.0,
    "incident_id": "incident-07", "mission_id": "mission-03",
    "payload": {"resource_id": "drone_01", "outcome": "inconclusive", "observations": [], "reason": "Visibilidade insuficiente para concluir; objetivo ainda exige ação."}
  },
  {
    "schema_version": 1, "message_id": "msg-021", "message_type": "STATUS", "created_at": 140.0,
    "payload": {"resource_id": "drone_01", "position": {"x": 6, "y": 8}, "available": false, "energy_fraction": 0.7, "observed_at": 139.0, "valid_until": 149.0}
  },
  {
    "schema_version": 1, "message_id": "msg-022", "message_type": "INCIDENT_CLOSED", "created_at": 150.0,
    "incident_id": "incident-08",
    "payload": {"terminal_state": "EXPIRED", "outcome": "inconclusive", "reason": "Prazo de observação terminou sem evidência suficiente; nenhuma missão atribuída."}
  }
]
```

### Sem dados e recusa

`msg-023` responde sem dados ao pedido de verificação. `msg-024` recusa o CFP e, por isso, inclui `mission_id`.

```json
[
  {
    "schema_version": 1, "message_id": "msg-023", "message_type": "VERIFY_RESPONSE", "created_at": 124.0,
    "incident_id": "incident-07",
    "payload": {"evidence": "no_data", "observations": [], "reason": "Sem registos disponíveis para a janela pedida."}
  },
  {
    "schema_version": 1, "message_id": "msg-024", "message_type": "REFUSAL", "created_at": 130.0,
    "incident_id": "incident-07", "mission_id": "mission-03",
    "payload": {"reason": "Energia insuficiente para executar a missão e regressar."}
  }
]
```

Metadados de quatro respostas. Nenhuma espera nova resposta, pelo que `reply-with` fica ausente.

| Corpo | Metadados válidos | Mensagem original guardada |
|---|---|---|
| `msg-004` | `{"performative":"refuse","ontology":"wildlife-monitoring","protocol":"verification","conversation-id":"verification-07-r1","in-reply-to":"msg-002"}` | `msg-002`, com `conversation-id=verification-07-r1` e `reply-with=msg-002` |
| `msg-023` | `{"performative":"inform","ontology":"wildlife-monitoring","protocol":"verification","conversation-id":"verification-07-r1","in-reply-to":"msg-002"}` | O mesmo pedido `msg-002` |
| `msg-024` | `{"performative":"refuse","ontology":"wildlife-monitoring","protocol":"task-allocation","conversation-id":"allocation-03-r1","in-reply-to":"msg-014"}` | CFP `msg-014`, com os metadados do § 2 |
| `msg-019` | `{"performative":"failure","ontology":"wildlife-monitoring","protocol":"task-allocation","conversation-id":"allocation-03-r1","in-reply-to":"msg-016"}` | `msg-016`, com `conversation-id=allocation-03-r1`, `reply-with=msg-016` e `in-reply-to=msg-015` |

### Exemplos inválidos

Cada linha altera apenas um exemplo válido. `metadata.` refere-se ao dicionário separado.

| Base | Alteração | Motivo da rejeição |
|---|---|---|
| `msg-023` | Remover `payload.reason` | Campo obrigatório. |
| `msg-023` | Usar `observations=null` | É necessária uma lista, mesmo vazia. |
| `msg-023` | Usar `evidence="compatible"` com lista vazia | Evidência compatível exige observações. |
| `msg-003` | Usar `evidence="no_data"` mantendo observações | Sem dados exige lista vazia. |
| `msg-004` | Acrescentar `mission_id` | A recusa de verificação não tem missão; conferir com o pedido. |
| `msg-024` | Remover `mission_id` | A recusa de CFP exige missão; conferir com o pedido. |
| `msg-019` | Usar `metadata.performative="agree"` | Falha de reserva usa `failure`. |
| `msg-019` | Usar `metadata.in-reply-to="msg-015"` | Responde à aceitação `msg-016`, não à proposta. |
| `msg-019` | Usar `resource_id="drone_02"` | Não corresponde ao recurso aceite. |
| `msg-024` | Usar `mission_id="mission-99"` | Não corresponde ao CFP. |
| `msg-023` | Usar outra `conversation-id` | Não corresponde à ronda do pedido. |
| Qualquer | Usar ID/motivo só com espaços, versão `true`, tipo desconhecido ou instante negativo | Viola as regras comuns. |
| Qualquer | Acrescentar `ground_truth` ou repetir uma chave JSON | Conteúdo proibido, mesmo se a chave repetida tiver o mesmo valor. |

JSON malformado, como `{"schema_version":1,}`, falha antes da validação dos campos.

## 4. Verificação distribuída

O **iniciador** é o agente que acompanha localmente aquele incidente.

1. Envia `VERIFY_REQUEST` às fontes elegíveis, com pedido próprio por fonte, área, janela temporal e prazo. Pode enviá-los em paralelo.
2. Cada fonte envia `VERIFY_RESPONSE` ou `REFUSAL`.
3. O iniciador confere remetente, pedido, conversa, incidente e prazo de receção.
4. Quando recebe todas as respostas ou o prazo termina, passa de `VERIFYING` para `ASSESSING`. Avalia a evidência e regista o que ficou em falta.

| Resposta da fonte | Como interpretar |
|---|---|
| `compatible` | Há observações a favor da hipótese. |
| `contradictory` | Há observações contra a hipótese; não são prova definitiva de ausência de ameaça. |
| `informative_absence` | Não houve deteção, mas a fonte tinha capacidade, cobertura e oportunidade de observar. `reason` deve justificar isso. |
| `no_data` | A fonte respondeu, mas não tem dados utilizáveis. Não conta como evidência negativa. |
| `REFUSAL` | A fonte não aceita o pedido e explica porquê. Não confirma nem refuta a ameaça. |
| Sem resposta no prazo | Registar a lacuna. O timeout é local, não uma mensagem nem prova de ausência de ameaça. |

Uma resposta ou recusa válida termina a espera por essa fonte. Os quatro valores de `evidence` usam `VERIFY_RESPONSE`/`inform`; a recusa usa outro tipo. Não inventar observações para preencher listas vazias.

O agente ainda terá de avaliar distância, janela temporal, modalidade do sensor, validade e independência das fontes. Os validadores não comprovam o significado da evidência. Duas mensagens da mesma observação não são duas fontes independentes.

## 5. Atribuição distribuída: Contract Net simplificado

```mermaid
sequenceDiagram
  participant I as Iniciador
  participant R as Recursos candidatos
  I->>R: CFP — pedir propostas
  R-->>I: PROPOSAL ou REFUSAL
  I->>R: ACCEPT ao escolhido; REJECT aos restantes
  alt Recurso garante a reserva
    R-->>I: RESERVATION_CONFIRMED
    Note over I: ALLOCATING → RESPONDING
    R-->>I: MISSION_RESULT
    Note over I: Avaliar resultado e necessidade de mais ação
  else Reserva falha
    R-->>I: RESERVATION_FAILED
    Note over I: Continuar em ALLOCATING e avaliar alternativas
  end
```

O mesmo CFP pode ir para vários candidatos. Cada proposta tem ID próprio. `ACCEPT` e `REJECT` respondem à proposta de cada recurso; a confirmação/falha de reserva responde ao `ACCEPT`; o resultado responde à confirmação. Só o escolhido reserva e executa. Um rejeitado liberta eventual reserva provisória.

O recurso avalia disponibilidade, autonomia e compromissos antes de propor. O iniciador escolhe entre propostas elegíveis recebidas dentro do prazo. Sem proposta elegível, avalia alternativas e os limites da secção 6.

**Aceitar uma proposta não reserva o recurso.** Depois de `ACCEPT`, o recurso volta a verificar as condições e garante que não há outra reserva incompatível antes de emitir `RESERVATION_CONFIRMED`. Essa garantia é a reserva atómica, ainda por implementar.

O iniciador só passa a `RESPONDING` após validar a confirmação, o remetente, a missão, o recurso, a ronda e o prazo operacional. Uma proposta antiga, um `STATUS` disponível ou JSON válido não comprovam a reserva real.

Se a reserva falhar ou não chegar confirmação, o incidente continua em `ALLOCATING`. **Silêncio não prova que o recurso ficou livre:** é preciso esclarecer a reserva antes de outra atribuição. Os prazos de aceitação, reserva e execução ainda estão por definir; o prazo do CFP limita apenas propostas e recusas.

A confirmação após aceitação é uma extensão proposta pelo projeto ao Contract Net dos slides da UC.

## 6. Estado e ordenação

O estado indica a fase do incidente; o resultado indica o que foi apurado. Terminar uma missão não significa cumprir o objetivo do incidente.

### Mensagens e observações repetidas

Validar corpo, metadados e ligação ao pedido antes de aplicar efeitos. Comparar IDs e conteúdo pelo valor exato, independentemente do remetente ou conversa. A ordem das chaves JSON não altera o conteúdo.

| Caso | Ação do agente que recebe |
|---|---|
| Mesmo `message_id`, corpo e metadados iguais | Retransmissão: não repetir avaliação, transição, missão ou reserva. |
| Mesmo `message_id`, conteúdo diferente | Rejeitar e registar o conflito; preservar o registo anterior. |
| Nova mensagem, mesma observação | Validar a função da mensagem, mas contar a observação apenas uma vez. |
| Mesmo `event_id`, observação alterada | Rejeitar o conflito; preservar a observação original. |
| `event_id` repetido na mesma lista | Rejeitar o corpo; não apagar itens para o tornar válido. |

Comparar os seis campos da observação definidos na secção 3. Em `ALERT`, juntar os IDs do corpo aos quatro campos do payload. Reencaminhar uma observação pode criar outra mensagem, mas preserva a fonte, o ID e os restantes dados da observação.

IDs de evento diferentes também não provam independência: os dados podem vir da mesma fonte ou sinal. Não aumentar a confiança só porque chegaram mais mensagens.

A cache e o histórico ainda não existem. Será preciso definir quanto tempo guardar IDs/conteúdo e como tratar mensagens após essa retenção; uma cache finita não garante que uma mensagem antiga nunca volte a produzir efeitos.

### Respostas tardias ou fora do contexto

Uma resposta pode corresponder a um pedido antigo e já não ser aplicável. Antes de alterar estado, seleção ou reserva, conferir também a ronda, missão e recurso **ainda ativos**.

| Situação | Ação |
|---|---|
| Resposta de verificação/CFP recebida no limite ou depois | Não usar na ronda nem na seleção; registar o atraso e a informação em falta. |
| Conversa, incidente, missão ou recurso diferentes | Rejeitar a associação. Não corrigir IDs para aceitar a resposta. |
| Resposta válida, mas fase local incompatível | Não aplicar efeitos. O resultado de uma missão anterior não encerra a missão atual. |
| Confirmação ou resultado após o prazo operacional | Não ativar/encerrar automaticamente. Esclarecer reservas incertas antes de considerar o recurso livre. |
| Mensagem para incidente terminal | Preservar estado e resultado. Guardar apenas para diagnóstico, sem reabrir nem repetir efeitos. |

Exemplo: `msg-003` foi emitida em `124.0`, mas é tardia se chegar em `126.0`, limite do pedido `msg-002`. Uma futura utilização dessa evidência exige nova avaliação, sem contagem duplicada, e uma ronda permitida pelo estado. Não altera retroativamente a ronda encerrada.

Rejeitar significa registar o motivo sem aplicar efeitos; não exige enviar `REFUSAL` fora das ligações previstas na secção 2.

### Transições do incidente

O iniciador local verifica estas condições e atualiza o estado. O [ciclo da arquitetura](architecture.md#5-ciclo-de-vida-de-um-incidente) mantém-se.

| De | Para | Condição |
|---|---|---|
| `DETECTED` | `VERIFYING` | Observação associada; iniciar verificação com fontes elegíveis e prazo. |
| `VERIFYING` | `ASSESSING` | Respostas recolhidas ou prazo atingido; registar dados/respostas em falta. |
| `ASSESSING` | `WATCHING` | Evidência insuficiente para missão; registar motivo e prazo de observação. |
| `ASSESSING` | `ALLOCATING` | Missão justificada; definir objetivo, alvo e capacidade necessária. |
| `WATCHING` | `VERIFYING` | Nova evidência pertinente justifica outra ronda. |
| `WATCHING` | `EXPIRED` | Prazo terminado sem evidência suficiente; registar motivo e dados disponíveis. |
| `ALLOCATING` | `RESPONDING` | Reserva confirmada e válida para a missão, recurso e ronda atuais. |
| `ALLOCATING` | `UNRESOLVED` | Sem reserva válida e sem alternativas, tentativas ou prazo disponíveis. |
| `RESPONDING` | `CLOSED` | Resultado validado, objetivo cumprido e nenhuma ação adicional necessária; registar resultado, motivo e evidência. |
| `RESPONDING` | `ALLOCATING` | Resultado inconclusivo, intervenção adicional ou falha exige reavaliar alternativas. |
| `CLOSED`, `EXPIRED`, `UNRESOLVED` | — | Estados terminais; não reabrir o mesmo incidente. |

`CLOSED` também pode significar uma conclusão fundamentada de ausência de ameaça. `EXPIRED` e `UNRESOLVED` não contam como resolução bem-sucedida.

### Novas tentativas

- Uma recusa, falha de reserva ou falta de propostas não encerra o incidente se ainda houver alternativas dentro dos limites. Continuar em `ALLOCATING`; outra ronda recebe outra conversa.
- Uma missão inconclusiva, uma falha ou a necessidade de enviar rangers pode levar de `RESPONDING` a `ALLOCATING`. Preservar incidente e evidência; dar ID próprio à nova missão.
- Se os limites já estiverem esgotados, seguir `RESPONDING` → `ALLOCATING` → `UNRESOLVED`, sem enviar outro CFP. Não existe salto direto.

Ainda é preciso definir o que conta como tentativa, o máximo de tentativas e o prazo total. As repetições de ronda não exigem transições de um estado para si próprio. O ciclo proposto para uma missão é `PROPOSED` → `RESERVED` → `RUNNING` → `DONE`/`FAILED`, mas depende do modelo `Mission` e ainda não está implementado.

## 7. Falhas a testar na integração

Estes testes exigem agentes e transporte reais; os testes atuais verificam apenas os contratos de dados.

| Cenário | Resultado a verificar |
|---|---|
| Fonte desligada ou resposta atrasada | Terminar a espera no prazo e registar evidência incompleta. |
| Mensagem repetida | Não duplicar evidência, transições, missões ou reservas. |
| Duas missões disputam o mesmo recurso | Impedir reservas incompatíveis. |
| Recurso sem energia | Recusar com motivo e permitir avaliar alternativas. |
| Falha durante a missão | Registar falha, tratar a reserva e reavaliar o objetivo. |
| Mensagem inválida | Rejeitar sem interromper o agente. |
| Rede com perdas/atrasos | Aplicar prazos e reenvios sem repetir efeitos. |
| Iniciador desaparece | Recuperação ainda por definir; silêncio não liberta reservas. |

## 8. O que está implementado

### API e testes

[messages.py](../src/isia/communication/messages.py) trabalha com dicionários, sem transporte ou modelos externos.

| Função | O que verifica ou devolve |
|---|---|
| `validate_envelope(message)` | Campos comuns, IDs presentes e valores JSON. Não valida o payload nem exige todos os IDs específicos do tipo. |
| `validate_message(message)` | Acrescenta IDs por tipo, campos do payload, números, tempos, observações e combinações de evidência/resultado. |
| `validate_metadata(message, metadata)` | Valida corpo e metadados, incluindo intenção, protocolo e campos de resposta. |
| `validate_reply(response, metadata, request, request_metadata, *, now=None)` | Valida ambos os pares e compara tipo de resposta, conversa, protocolo, IDs e recurso com a mensagem guardada. Verifica cronologia e prazo direto. |
| `to_json(message)` | Valida a mensagem e devolve texto JSON. |
| `from_json(body)` | Lê JSON, rejeita chaves repetidas, valida e devolve novo dicionário. |

Os validadores devolvem `None` ou lançam `ValueError`; não alteram os dados. A conversão preserva IDs e instantes. Metadados não fazem parte do texto produzido por `to_json`.

Em `validate_reply`, a resposta tem ID próprio e não pode ser anterior ao pedido. Passar `now` com o instante de receção/processamento, finito, não negativo e não anterior à emissão. Sem `now`, a função usa o instante de emissão e **não prova chegada dentro do prazo**. Não conhece a ronda ativa, participantes autenticados, reserva ou estado local, nem agenda timeouts.

[incident_state.py](../src/isia/domain/incident_state.py) define `IncidentState` e `validate_transition(current, target)`. Aceita enum ou texto exato; devolve `None` para pares permitidos e lança `ValueError` para estados desconhecidos, saltos, repetição do estado ou saída de terminais. Não altera o incidente nem verifica as condições operacionais da secção 6.

Os testes cobrem os 15 corpos de exemplo, os 13 tipos, os metadados, as ligações entre mensagens, os prazos e as transições. Para executar na raiz:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

### Integração com os modelos

Na base inspecionada em 2026-11-06 (`gui-batista`, HEAD `867c519`), os seis modelos abaixo ainda não estavam em `src/`. `Position`, `Observation` e `Incident` foram apenas lidos na referência local `origin/feature/etapa1-modelos`, commit `6575e12827d4d50fe78e4ee33d1f7a59e3b7b94b`. Não houve fetch, integração ou execução dos 12 testes dessa referência; isto não confirma o estado atual do remoto.

| Modelo | Conversão a fazer com a classe real |
|---|---|
| `Position` | `x`, `y` nas posições e alvos. O modelo inspecionado exige inteiros não negativos, sem booleanos ou limite superior do mapa. |
| `Observation` | Os seis campos da secção 3; em `ALERT`, juntar IDs do corpo ao payload. Conferir posição, instantes e confiança. |
| `Incident` | ID e tuplo não vazio de observações, sem `event_id` repetido. Não há mensagem que serialize o incidente inteiro. |
| `ResourceState` | `STATUS`; acordar nomes, disponibilidade, energia e validade. |
| `Mission` | `CFP`; acordar tarefa, capacidade, prioridade e estados. Distinguir prazo de propostas de prazo de execução. |
| `Bid` | `PROPOSAL`; acordar nomes, ETA, energia e fórmula de custo. A ligação ao CFP fica nos metadados. |

Os três modelos inspecionados são imutáveis (`dataclass(frozen=True)`). `Incident` não contém estado, resultado ou missão; não acrescentar esses campos para fazer a conversão. `Observation` chama `strip()` sem verificar previamente o tipo dos textos; o validador JSON já verifica esse tipo.

Os testes atuais fazem dicionário → JSON → dicionário. Ainda não demonstram compatibilidade com as classes reais. Não foram criados modelos substitutos; as conversões continuam pendentes na secção 5 do TODO ativo.

### Execução ainda pendente

| Trabalho | Regra a preservar |
|---|---|
| Integração SPADE/XMPP | Verificar `Agent`, comportamentos, `Message`, `Template`, envio/receção e mapeamento dos metadados, incluindo `conversation-id` para `Message.thread`/metadata. |
| Conversas e transporte | Implementar os fluxos previstos em `communication/protocols.py` e perdas/latência em `communication/transport.py`. |
| Histórico/cache | Guardar IDs e conteúdo para impedir efeitos repetidos e detetar conflitos; definir retenção. |
| Temporizadores | Executar os prazos de verificação, propostas, observação, reserva e missão. |
| Reserva atómica | O recurso impede reservas incompatíveis antes de confirmar. |
| Reenvios | Definir intervalos e limites; preservar corpo e metadados da mesma mensagem. |
| Recuperação do iniciador | Definir deteção de falha, substituição e reconciliação de conversas, missões e reservas. |

### Gerar documentação da API

Na raiz, com o ambiente Python ativado:

```bash
pydoc_project="$PWD"
pydoc_dir="$(mktemp -d)"
(
  cd "$pydoc_dir" &&
  PYTHONPATH="$pydoc_project/src" python3 -m pydoc -w \
    isia.domain.incident_state isia.communication.messages
)
printf 'HTML: %s\n' "$pydoc_dir"
```

Abrir os dois ficheiros HTML no diretório indicado. O comando documenta os módulos e as docstrings sem iniciar SPADE/XMPP.

## 9. Decisões do grupo

- [ ] Aprovar formato v1, nomes, IDs, destinatários e unidade do relógio.
- [ ] Confirmar os campos dos modelos e as conversões.
- [ ] Acordar critérios de evidência, prioridade e custo das propostas.
- [ ] Definir prazos, tentativas, retenção de IDs e reenvios.
- [ ] Definir reserva e recuperação após falha do iniciador.
- [ ] Verificar a integração SPADE e testar os fluxos de verificação e atribuição.
