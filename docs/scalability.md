# Escalabilidade — Etapa 9A (P3)

[Plano](development-plan.md#etapa-9a--escalabilidade-computacional-e-situacional) · [Experiências](experiments.md) · [Arquitetura](architecture.md) · [Pendentes](delivery-todo.md#bloco-c--p3-escalabilidade)

Resposta a P3: que limites de escala tem o sistema, quais foram medidos e o que se propõe para cada um. Os números vêm de [`results/scalability/`](../results/scalability/), gerados a 16-11-2026 com o código `src/` da `main` em `89c08a7`.

## Como reproduzir

A partir da raiz do repositório (não precisa de servidor XMPP nem da pasta `.git`):

```bash
PYTHONPATH=src python scripts/dist.py    # ~2 min, grava results/scalability/dist.csv
PYTHONPATH=src python scripts/scale.py   # ~20 s, grava results/scalability/scale.csv
```

- **Cenário:** A (fontes fiáveis), variante `full`, sementes 1000–1009 (10 repetições); os casos com perdas usam 1000–1019 (20).
- **Transporte:** local. As perdas são injetadas no transporte local e não validam a rede XMPP.
- **Tempo real** (`tempo_real_s`): depende da máquina. Comparar casos da mesma execução, nunca valores entre máquinas.
- **«Atendidos»** (`atendidos/ameacas`): ameaças reais em cuja posição uma patrulha confirmou a ameaça. É a métrica por caçador, calculada pela função `attended()` de [`scripts/dist.py`](../scripts/dist.py). Não conta intervenções concluídas pelo guarda.

## Montagem

```
   y
   7 . . . . . . . .
   6 . . . . . . P .     P = caçador fora de alcance (6,6)
   5 . p . . . R . .     p = caçador testado (2,5);  R = guarda (5,5)
   4 . . . . . . . .
   3 . . . . . . . .
   2 D . S X S . . .     S = sensor-1 (2,2), único iniciador; sensor-2 (4,2)
   1 . . . . . . . .     X = caçador base (3,2);  D = drone (0,2)
   0 V . . . . . . Q     V = veículo (0,0);  Q = ponto cego do iniciador (7,0)
     0 1 2 3 4 5 6 7  x
```

Os dois sensores têm alcance de 5 células. Em (7,0), o sensor-2 está a 3,6 células e vê o caçador; o sensor-1 está a 5,4 e não vê.

## Custo computacional (`scale.csv`)

Mensagens por missão com N candidatos: N CFP + N respostas + 1 `ACCEPT` + até N−1 rejeições + 1 `STATUS` + 1 resultado, ou seja, **no máximo 3N + 2**. Uma ocorrência completa = 2 (verificação) + 8 (patrulha, N = 2) + 5 (guarda, N = 1) = **15 mensagens**.

| Caso | Confirmadas | Não resolvidas | Mensagens por execução | Tempo real (10 execuções) |
|---|---|---|---|---|
| Base: 2 patrulhas, 1 guarda, 1 caçador | 8/10 | 0 | 15 (×8), 2 (×2) | 1,5 s |
| Drone silencioso | 8/10 | 0 | 13 (×8), 2 (×2) | 5,5 s |
| 0 patrulhas | 0/10 | 8 | 4 (×8), 2 (×2) | 4,1 s |
| 0 guardas | 8/10 | 8 | 11 (×8), 2 (×2) | 4,6 s |
| 3 caçadores | 8/10 | 0 | 15 (×8), 2 (×2) | 1,5 s |

- As execuções com 2 mensagens pararam na corroboração (`insufficient_corroboration`); por isso a média da base é 12,4 e não 15.
- **C2 medido:** um candidato calado faz cada ronda esperar o prazo inteiro. Nesta máquina, dez execuções passaram de 1,5 s para 5,5 s reais, sem qualquer ganho de resultado. O fator depende da máquina; reportam-se os dois tempos.
- Com 3 caçadores, as mensagens não mudam: só existe uma ocorrência (C7).

## Escalabilidade situacional (`dist.csv`)

**A) Onde estão os caçadores (recursos fixos)**

| Caso | Alertas | Atendidos | t verif. (s sim.) | O que mostra |
|---|---|---|---|---|
| 1 caçador em (3,2) | 10/10 | 8/10 | 4 | Referência; as 2 falhas vêm da corroboração |
| 1 caçador em (2,5) | 10/10 | 8/10 | 6 | Mais longe dos recursos, verificação mais lenta |
| 1 caçador em (7,0) | **0/10** | 0/10 | — | O sensor-2 vê, mas só o sensor-1 inicia |
| 1 caçador em (6,6) | 0/10 | 0/10 | — | Fora do alcance dos dois sensores |
| 2 caçadores | 10/10 | **8/20** | 4 | Uma ocorrência por janela (C7) |
| 3 caçadores | 10/10 | **8/30** | 4 | A métrica por execução (8 TP) esconde as ameaças sem resposta |

**B) Quantidade e posição dos recursos (1 caçador em (3,2), drone com carga 0,5)**

| Caso | Confirmadas | Não resolvidas | t verif. | t guarda | Energia (p.p.) |
|---|---|---|---|---|---|
| Recursos na base | 8 | 0 | 6 | 12 | 16,0 |
| Recursos no canto (7,7) | 8 | 0 | 9 | 19 | 27,2 |
| Só o guarda em (0,7) | 8 | 0 | 6 | 15 | 20,8 |
| Drone com 15 % (1 patrulha elegível) | 8 | 0 | 6 | 12 | 16,0 |
| Drone e veículo com 15 % (0 elegíveis) | 0 | 8 | — | — | 0 |

**C) Recursos com 10 % de perda (20 repetições)**

| Caso | Alertas | Atendidos | Não resolvidas | t guarda |
|---|---|---|---|---|
| 2 patrulhas elegíveis | 19/20 | 13/20 | 8 | 15,9 |
| 1 patrulha elegível | 19/20 | 9/20 | 10 | 17,0 |

**Leitura, com o alcance que a amostra permite:**

1. **A cobertura do iniciador limita mais do que os recursos.** Um caçador fora do alcance do sensor-1 nunca gera alerta, mesmo que o sensor-2 o veja.
2. **Recursos mais longe aumentam tempo e energia, não mudaram decisões** nestes casos.
3. **Menos recursos:** sem perdas, uma patrulha elegível obteve as mesmas confirmações que duas; sem nenhuma, 0 confirmações e 8 não resolvidas. Com 10 % de perda, duas patrulhas atenderam 13/20 e uma atendeu 9/20. Com 20 repetições e sem intervalos de confiança, isto sugere que a redundância ajuda sob perdas; não prova que menos recursos só prejudicam quando há perdas.
4. **Mais caçadores do que ocorrências:** com 2 ou 3 caçadores só um é atendido.

## Estado de C1–C8

| Ref. | Limite | Onde | Estado | Justificação |
|---|---|---|---|---|
| C1 | CFP enviado a todos os candidatos: O(N) por missão | [incident.py:128](../src/isia/agents/incident.py#L128) | Proposto | Com duas patrulhas e K ≥ 2, o «antes» é igual ao «depois». Exige C4 para ter efeito, e o iniciador não conhece posições (ver abaixo) |
| C2 | Candidato calado obriga a esperar o prazo inteiro | [incident.py:131](../src/isia/agents/incident.py#L131) | **Medido** | 1,5 s → 5,5 s reais nesta máquina. Proposta: não voltar a chamar quem ficou calado na ronda seguinte |
| C3 | Prazos reais com tempo simulado | [runner.py:183](../src/isia/simulation/runner.py#L183), [incident.py:131](../src/isia/agents/incident.py#L131) | Adiado | Obriga a avançar o relógio simulado durante a negociação; trabalho futuro |
| C4 | Recursos e sensores fixos no runner | [runner.py:64](../src/isia/simulation/runner.py#L64), [:80](../src/isia/simulation/runner.py#L80), [:148](../src/isia/simulation/runner.py#L148) | Proposto | Impede testar «mais drones» sem mudar o código. Ler a lista de recursos do cenário |
| C5 | `ObservationFeed.recent()` percorre todo o histórico, O(H) | [scenario.py:98](../src/isia/simulation/scenario.py#L98) | Proposto | O feed é lido uma vez por execução; o ganho não é mensurável neste sistema. Proposta: `bisect` ou `deque` da janela |
| C6 | Corroboração com um único par fixo | [runner.py:135](../src/isia/simulation/runner.py#L135) | Proposto | Perguntar aos k vizinhos com alcance e decidir com as respostas até ao prazo |
| C7 | Uma ocorrência por janela, ancorada na primeira observação | [incident.py:254](../src/isia/agents/incident.py#L254), [allocation.py:804](../src/isia/reasoning/allocation.py#L804) | **Medido** | 8/10, 8/20, 8/30 atendidos. Proposta: agrupar observações por proximidade e criar uma ocorrência por grupo |
| C8 (reputação) | Histórico da reputação cresce em memória | [reputation.py:128](../src/isia/reasoning/reputation.py#L128) | Proposto | Pelo menos quatro testes usam `book.history`; o crescimento de memória não foi medido |
| C8 (processos) | Todos os agentes num processo | [runner.py](../src/isia/simulation/runner.py) | Adiado | Um processo por agente ligado ao XMPP; mudança grande, trabalho futuro |

**Situacionais, também propostos:** qualquer sensor poder iniciar (elimina o ponto cego de (7,0), mas exige evitar ocorrências duplicadas); fila de ocorrências por gravidade, só depois de C7. A métrica por caçador está feita em `attended()`.

## Correções a afirmações anteriores

- **C1 — o iniciador não conhece a posição base dos recursos.** `candidates` só tem `{jid: resource_id}` ([runner.py:165](../src/isia/simulation/runner.py#L165)). Filtrar pelos K mais próximos obriga o runner a passar as posições ou os recursos a anunciá-las; a posição só chega ao iniciador na `PROPOSAL`, depois do CFP.
- **C2 — o fator de lentidão não é constante.** A análise de 13-11 indicava «3,4×» (1,6 s → 5,5 s); a medição de 16-11 deu 1,5 s → 5,5 s. Reportam-se os tempos e a máquina, não um fator.
- **Recursos — «menos recursos só prejudica com falhas» é forte demais.** Sem perdas, retirar todas as patrulhas elegíveis já impede qualquer confirmação; e a diferença 13/20 contra 9/20 vem de 20 repetições sem intervalo de confiança.

## Limites da evidência

- 10–20 repetições, sem intervalos de confiança; um cenário (A) e uma variante (`full`).
- O drone com 15 % de autonomia continua a receber CFP; simula um recurso inelegível, não um recurso ausente.
- Não se testou aumentar o número de drones (C4).
- Os resultados não demonstram escalabilidade geral.
