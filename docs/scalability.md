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
| C1 | CFP enviado a todos os candidatos: O(N) por missão | [incident.py:139](../src/isia/agents/incident.py#L139) | **Implementado e medido (Bloco F)** | `cfp_limit=K` envia o CFP só às K patrulhas com base mais próxima do alvo. Com 16 patrulhas: 57 → 15 mensagens por ocorrência, mesma decisão. Opcional: sem `cfp_limit`, o comportamento é o anterior. Usa a posição base, não a atual |
| C2 | Candidato calado obriga a esperar o prazo inteiro | [incident.py:142](../src/isia/agents/incident.py#L142) | **Medido** | 1,5 s → 5,5 s reais nesta máquina. Proposta: não voltar a chamar quem ficou calado na ronda seguinte |
| C3 | Prazos reais com tempo simulado | [runner.py:215](../src/isia/simulation/runner.py#L215), [incident.py:142](../src/isia/agents/incident.py#L142) | Adiado | Obriga a avançar o relógio simulado durante a negociação; trabalho futuro |
| C4 | Recursos e sensores fixos no runner | [runner.py:66](../src/isia/simulation/runner.py#L66), [:82](../src/isia/simulation/runner.py#L82), [:176](../src/isia/simulation/runner.py#L176) | **Mínimo implementado (Bloco F)** | `run_mvp(extra_patrols=..., extra_initiators=...)` acrescenta drones e sensores iniciadores sem mudar o código. Os ficheiros de cenário continuam com os três recursos fixos |
| C5 | `ObservationFeed.recent()` percorre todo o histórico, O(H) | [scenario.py:98](../src/isia/simulation/scenario.py#L98) | Proposto | O feed é lido uma vez por execução; o ganho não é mensurável neste sistema. Proposta: `bisect` ou `deque` da janela |
| C6 | Corroboração com um único par fixo | [runner.py:153](../src/isia/simulation/runner.py#L153) | Proposto | Perguntar aos k vizinhos com alcance e decidir com as respostas até ao prazo |
| C7 | Uma ocorrência por janela, ancorada na primeira observação | [incident.py:265](../src/isia/agents/incident.py#L265), [allocation.py:804](../src/isia/reasoning/allocation.py#L804) | **Medido** | 8/10, 8/20, 8/30 atendidos. Proposta: agrupar observações por proximidade e criar uma ocorrência por grupo |
| C8 (reputação) | Histórico da reputação cresce em memória | [reputation.py:128](../src/isia/reasoning/reputation.py#L128) | **Medido (Bloco F)** | 1000 execuções: 1824 registos, 1,3 MB serializados, crescimento linear (~1,3 kB por execução). Irrelevante à escala do projeto; a proposta de truncar ou gravar em JSONL mantém-se para execuções muito longas |
| C8 (processos) | Todos os agentes num processo | [runner.py](../src/isia/simulation/runner.py) | Adiado | Um processo por agente ligado ao XMPP; mudança grande, trabalho futuro |

**Situacionais, também propostos:** qualquer sensor poder iniciar (elimina o ponto cego de (7,0), mas exige evitar ocorrências duplicadas); fila de ocorrências por gravidade, só depois de C7. A métrica por caçador está feita em `attended()`.

## Correções a afirmações anteriores

- **C1 — o iniciador não conhece a posição base dos recursos.** `candidates` só tem `{jid: resource_id}` ([runner.py:195](../src/isia/simulation/runner.py#L195)). Filtrar pelos K mais próximos obriga o runner a passar as posições ou os recursos a anunciá-las; a posição só chega ao iniciador na `PROPOSAL`, depois do CFP. **Resolvido no Bloco F** pela primeira via: o runner passa as posições base em `configure_mvp(base_positions=...)`.
- **C2 — o fator de lentidão não é constante.** A análise de 13-11 indicava «3,4×» (1,6 s → 5,5 s); a medição de 16-11 deu 1,5 s → 5,5 s. Reportam-se os tempos e a máquina, não um fator.
- **Recursos — «menos recursos só prejudica com falhas» é forte demais.** Sem perdas, retirar todas as patrulhas elegíveis já impede qualquer confirmação; e a diferença 13/20 contra 9/20 vem de 20 repetições sem intervalo de confiança.

## Limites da evidência

- 10–20 repetições, sem intervalos de confiança; um cenário (A) e uma variante (`full`).
- O drone com 15 % de autonomia continua a receber CFP; simula um recurso inelegível, não um recurso ausente.
- O aumento do número de drones (C4) só foi medido em mensagens, com uma ocorrência e drones adicionais com 100 % de autonomia (Bloco F).
- Os resultados não demonstram escalabilidade geral.

## Testes de stress (Bloco F)

Onde o sistema deixa de atender, em várias dimensões. Os números vêm de [`results/stress/`](../results/stress/), gerados a 16-11-2026 na branch `feature/bloco-f-stress`, com o transporte local.

```bash
PYTHONPATH=src python scripts/stress_f1.py     # ~8 min: perda, latencia, cascata, autonomia, combinadas
PYTHONPATH=src python scripts/stress_f2.py     # ~1 min: paralelo, invalidas, escala
PYTHONPATH=src python scripts/stress_long.py   # ~3 min: longa
```

- **F1** usa o cenário A (1 caçador em (3,2), fontes com ruído) e a variante `full`, com reputação nova em cada execução. Em 10 execuções, 2 param na corroboração; por isso o máximo é 8/10 (17/20 com 20 execuções).
- **F2** usa fontes sem ruído (alcance 1) e política sem corroboração, com um caçador na célula de cada sensor iniciador. Assim, a única variável é a disputa pelos recursos.
- **«Fechadas»** = ocorrências em que a patrulha confirmou e o guarda interveio (`closed`). **«Confirmadas»** = só a verificação pela patrulha.

### Mapa de limites

| Teste | CSV | Onde deixa de atender |
|---|---|---|
| Perda de mensagens | [perda.csv](../results/stress/perda.csv) | Com 10 % de perda fecha 7/20 (17/20 sem perda); com 20 %, 1/20; a partir de 30 %, nenhuma |
| Latência de `PROPOSAL` e `STATUS` | [latencia.csv](../results/stress/latencia.csv) | Até 0,4 s de atraso, 8/8; a partir de 0,5 s (o `receive_timeout`), 0/8. Não há degradação gradual |
| Recursos a cair | [cascata.csv](../results/stress/cascata.csv) | Sem o drone, igual (8/8); sem as duas patrulhas, 0 confirmadas; sem o guarda, 8 confirmadas e 0 fechadas |
| Escassez de autonomia | [autonomia.csv](../results/stress/autonomia.csv) | Até 20 %, ganha o veículo; de 19 % a 16 %, o veículo recusa e ganha o drone; a partir de 15 %, os dois recusam e nada é atendido |
| Falhas combinadas | [combinadas.csv](../results/stress/combinadas.csv) | 0 duplas reservas e 0 fechos duplicados em 20 execuções; 6 confirmadas, 0 fechadas |
| Ocorrências em paralelo e rajada | [paralelo.csv](../results/stress/paralelo.csv) | Por janela, o sistema fecha 1 ocorrência (1 guarda) e confirma 2 (2 patrulhas), sejam 2, 4 ou 8 as ocorrências. 0 duplas reservas |
| Mensagens inválidas | [invalidas.csv](../results/stress/invalidas.csv) | Até 300 mensagens inválidas de cada tipo por mensagem real (12 600 por execução), resultado igual em 10/10; com 1000, 0/10. Nenhuma exceção |
| Execução longa | [longa.csv](../results/stress/longa.csv) | Não deixa de atender em 1000 execuções; o histórico da reputação cresce 1,3 kB por execução |
| Mensagens em função de N (C4 + C1) | [escala.csv](../results/stress/escala.csv) | Sem limite: 15, 21, 33 e 57 mensagens com 2, 4, 8 e 16 patrulhas. Com K = 2: 15 em todos os casos |

### F1 — só parâmetros

**Perda (20 execuções por ponto)**

| Perda | Mobilizou | Confirmadas | Fechadas | Não resolvidas | Mensagens (média) |
|---|---|---|---|---|---|
| 0 % | 17 | 17 | 17 | 0 | 13,0 |
| 10 % | 15 | 13 | 7 | 8 | 9,6 |
| 20 % | 12 | 8 | 1 | 11 | 6,8 |
| 30 % | 10 | 4 | 0 | 10 | 5,0 |
| 50 % | 4 | 0 | 0 | 4 | 2,0 |

- Os agentes não retransmitem. Uma ocorrência completa precisa de 15 mensagens seguidas, por isso a perda de uma só já a deixa por fechar.
- A perda atinge primeiro a corroboração: com 50 %, 15 das 20 execuções param em `insufficient_corroboration` e nem chegam a negociar.

**Latência (10 execuções por ponto).** O limite é o prazo fixo de 0,5 s reais. Atraso na `PROPOSAL` ≥ 0,5 s dá `no_eligible_proposals`; atraso no `STATUS` ≥ 0,5 s dá `confirmation_unknown`, com o recurso já reservado. O prazo fixo é frágil: 0,4 s funciona sempre e 0,5 s nunca.

**Cascata (10 execuções por caso).** Retirar o drone não muda o resultado, mas o tempo real passa de 1,5 s para 5,5 s (o candidato calado esgota o prazo, C2). O guarda é ponto único de falha da intervenção: sem ele, as 8 ameaças confirmadas ficam `unresolved`.

**Autonomia (drone e veículo com o mesmo valor).** A recusa é local e segue a conta de cada recurso: autonomia mínima de 10 % mais a ida e volta (veículo a 5 células, 10 p.p.; drone a 3 células, 6 p.p.).

| Autonomia | `REJECT` dos recursos | Quem verifica | Fechadas |
|---|---|---|---|
| 100 % a 20 % | 0 | veículo | 8 |
| 19 % a 16 % | 8 (veículo) | drone | 8 |
| 15 % e 10 % | 16 (os dois) | ninguém | 0 |

**Falhas combinadas.** Perda de 20 %, `MISSION_RESULT` duplicado e drone ocupado depois da proposta, na mesma execução. As garantias mantêm-se (nenhum recurso com duas missões, nenhum incidente fechado duas vezes), mas nenhuma ocorrência chega ao fim: 12 de 20 ficam `unresolved`.

### F2 — com código novo no runner

`run_mvp` ganhou três parâmetros opcionais, só no transporte local: `extra_initiators`, `extra_patrols` e `cfp_limit`, e a chave `flood` em [`faults`](faults.md). Sem eles, o comportamento é o anterior.

**Ocorrências em paralelo e rajada (10 execuções por caso).** Cada iniciador trata só o que o seu sensor deteta; o runner não escolhe quem trata cada ameaça.

| Ocorrências | Confirmadas | Fechadas | Não resolvidas | `STATUS` `reservation_failed` | CFP de 2.ª ronda | Duplas reservas | Mensagens (média) |
|---|---|---|---|---|---|---|---|
| 1 | 10/10 | 10/10 | 0 | 0 | 0 | 0 | 15 |
| 2 | 20/20 | 10/20 | 10 | 10 | 20 | 0 | 33 |
| 4 | 20/40 | 10/40 | 30 | 50 | 60 | 0 | 63 |
| 8 | 20/80 | 10/80 | 70 | 130 | 140 | 0 | 123 |

- **O `STATUS` resolve a corrida.** Com 2 ocorrências, os dois iniciadores aceitam a mesma patrulha; um recebe `reservation_failed`, renegocia e fica com a outra. Nunca houve dupla reserva.
- **Saturação: 2 verificações e 1 intervenção por janela.** Não há fila: quem perde a corrida fica `unresolved` (`reservation_rejected` ou `no_eligible_proposals`) e não volta a tentar quando o recurso regressa.
- O tempo simulado das ocorrências fechadas não muda (12 s com 1 ou com 8).

**Mensagens inválidas (10 execuções por ponto)**

| Inválidas por mensagem real (de cada tipo) | Inválidas por execução | Resultado igual ao de referência | Exceções | Tempo real |
|---|---|---|---|---|
| 0 | 0 | 10/10 | 0 | 2,0 s |
| 10 | 420 | 10/10 | 0 | 2,2 s |
| 100 | 4 200 | 10/10 | 0 | 4,9 s |
| 300 | 12 600 | 10/10 | 0 | 11,2 s |
| 1000 | 17 200 | 0/10 | 0 | 13,8 s |

- A validação aguenta a carga: nenhum agente termina com exceção e nenhuma mensagem inválida muda uma decisão.
- Com 1000, a negociação legítima falha por tempo, não por erro: processar o lixo demora mais do que o prazo de 0,5 s.
- **Achado:** os agentes respondem a parte do lixo (5 respostas por unidade de `flood`). O `InformantAgent` responde a um `VERIFY_REQUEST` com data no futuro, e os recursos respondem `reservation_failed` a um `ACCEPT` de missão desconhecida. São respostas corretas, mas dão a um atacante um amplificador de tráfego.

**Execução longa.** 1000 execuções com o mesmo `ReputationBook` em 176 s: 1824 registos em `book.history`, 1,3 MB serializados. O pico de memória do processo passou de 85 MB para 104 MB, dos quais 12 MB nas primeiras 100 execuções. A reputação do sensor-1 estabiliza em 0,998.

**Mensagens em função do número de patrulhas (C4 mínimo + C1, 10 execuções por caso)**

| Patrulhas | Sem limite | Com `cfp_limit=2` |
|---|---|---|
| 2 | 15 | 15 |
| 4 | 21 | 15 |
| 8 | 33 | 15 |
| 16 | 57 | 15 |

Cada patrulha a mais custa 3 mensagens (CFP, `PROPOSAL`, `REJECT`). Com K = 2, o custo é constante e as 10 ocorrências fecham no mesmo tempo simulado (12 s).

### Limites destes testes

- 10 a 20 execuções por ponto, sem intervalos de confiança; um cenário.
- Tudo no transporte local; nada disto valida a rede XMPP.
- Os iniciadores adicionais não corroboram nem atualizam a reputação.
- `cfp_limit` usa a posição base dos recursos, não a atual.
- Os valores de tempo real e o limite das mensagens inválidas (entre 300 e 1000) dependem da máquina.
- Repetição: o F1 foi corrido duas vezes com as mesmas sementes (17-11-2026, mesma máquina) e os cinco CSV saíram iguais em todas as colunas, exceto `tempo_real_s` (diferenças até 0,2 s). O F2 e a execução longa só foram corridos uma vez.
