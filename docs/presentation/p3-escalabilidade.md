# P3 — Escalabilidade: folha de números

Números para os diapositivos «Escalabilidade Computacional», «Escalabilidade Situacional» e «Testes de Stress». Todos conferidos com os CSV de `results/` a 18-11-2026. Explicação, tabelas completas e limites em [scalability.md](../scalability.md); o que dizer em [notas-bloco-f.md](notas-bloco-f.md).

## Em resumo

- **Computacional:** uma ocorrência custa 3N + 9 mensagens com N patrulhas. Com o CFP só às 2 mais próximas fica em 15 para qualquer N.
- **Situacional:** em A, B e C só o `sensor-1` inicia; fora do alcance dele não há alerta e, com várias ameaças, só uma é atendida.
- **Depois das mudanças:** com vários iniciadores e fila, 8 ocorrências ao mesmo tempo fecham todas (80 de 80 em vez de 10); o cenário E fecha 132 de 152, sem reservas duplas.
- **Limite:** transporte local, 5 a 20 execuções por ponto, sem intervalos de confiança.

## Computacional: o custo quando o sistema cresce

Mensagens por ocorrência ([escala.csv](../../results/stress/escala.csv), uma ocorrência, 10 execuções):

| Patrulhas | 2 | 4 | 8 | 16 |
|---|---|---|---|---|
| CFP a todas | 15 | 21 | 33 | 57 |
| CFP só às 2 mais próximas (`cfp_limit=2`) | 15 | 15 | 15 | 15 |

Fecham as 10 ocorrências, aos 12 s simulados, nos oito casos.

Mensagens por ocorrência quando há fila ([fila.csv](../../results/stress/fila.csv), cenários D e E):

| Ocorrências ao mesmo tempo | 1 | 2 | 4 | 8 | D (6 ameaças) | E (16 ameaças) |
|---|---|---|---|---|---|---|
| Mensagens por ocorrência | 15 | 20 | 30 | 44 | 36 | 78 |

| Outra medida | Valor | Fonte |
|---|---|---|
| Candidato calado | 1,5 s → 5,5 s reais em 10 execuções, com o mesmo resultado | [scale.csv](../../results/scalability/scale.csv) |
| Memória | 1,3 kB por execução no histórico da reputação (1,3 MB em 1000) | [longa.csv](../../results/stress/longa.csv) |
| Mensagens inválidas | Até 300 por mensagem real, nenhuma decisão muda e nenhum agente termina com exceção | [invalidas.csv](../../results/stress/invalidas.csv) |

## Situacional: o resultado quando o mundo muda

Cenário A, só o `sensor-1` inicia ([dist.csv](../../results/scalability/dist.csv)):

```
   6 . . . . . . P .   P (6,6) e Q (7,0): só o sensor-2 os alcança → 0 de 10 alertas
   5 . p . . . R . .
   2 D . S X S . . .   S sensor-1 (único iniciador) · S sensor-2
   0 V . . . . . . Q
     0 1 2 3 4 5 6 7
```

| Situação | Resultado |
|---|---|
| Ameaça fora do alcance do `sensor-1` | 0 de 10 alertas |
| 1, 2 e 3 ameaças ao mesmo tempo | 8 de 10, 8 de 20 e 8 de 30 atendidas |
| Recursos longe (canto do mapa) | Mesmas 8 confirmadas; verificação 6 s → 9 s; energia 16 → 27 p.p. |
| Uma patrulha sem energia (15 %) | Mesmas 8 confirmadas |
| As duas patrulhas sem energia | 0 confirmadas, 8 não resolvidas |
| 10 % de perda, 2 patrulhas contra 1 | 13 de 20 contra 9 de 20 atendidas |

## Mecanismos: antes e depois

| Mecanismo | Antes → depois | CSV | Por omissão | Cenários |
|---|---|---|---|---|
| CFP aos K mais próximos | 57 → 15 mensagens (16 patrulhas) | escala | desligado | nenhum |
| Prazo dinâmico (teto 2,0 s) | Atraso de 1,5 s: 0 → 10 de 10 fechadas | prazo | **ligado** | D, E |
| Vários iniciadores | 1 ocorrência por execução → uma por iniciador | paralelo | desligado | D, E |
| Fila | 8 em simultâneo: 10 → 80 de 80 fechadas | fila | **ligado** | D, E |
| Fila por gravidade | Graves fecham aos 74 s → 23 s; leves aos 27 s → 76 s | prioridade | desligado | D, E |
| Prazo de validade | Patrulhas em vão: 40 → 12 (ameaças de 30 s) | validade | desligado | D, E |
| Recurso diz quando fica livre | 367 → 336 mensagens | ocupado | desligado | D, E |
| Encadear missões | Último fecho: 81 s → 54 s | encadear | desligado | D, E |
| Silêncio perante `ACCEPT` incoerente | Respostas a lixo: 5 → 1 por unidade (−80 %) | silencio | **ligado** | D, E |
| Reenvio | 10 % de perda: 7 → 17 de 20 fechadas | reenvio | desligado | E (sem perdas) |
| Aviso entre iniciadores | 4 iniciadores, 1 ameaça: 40 → 10 idas de patrulha | alerta | desligado | E (sem duplicados) |
| Um informador por iniciador | 10 → 40 de 40 mobilizadas | informadores | desligado | D, E |
| Informadores humanos | Fiável: 40 de 40; com 30 % de falhas: 30 de 40 | humano | — | E (2 de 4) |

A, B e C correm com tudo desligado (`PUBLISHED_CONDITIONS`). Zero reservas duplas em todos os CSV.

## Tudo junto: cenários D e E

| | D — dia movimentado | E — reserva alargada |
|---|---|---|
| Mapa e recursos | 12×8, 4 patrulhas, 2 guardas | 16×12, 4 patrulhas, 2 guardas |
| Ameaças (10 execuções) | 60 | 160 |
| Com alerta | 52 | 152 |
| Mobilizadas | 48 | 139 |
| Fechadas como confirmadas | 40 | 132 |
| Fechadas como não confirmadas | 5 (ameaça de 15 s) | 0 |
| Expiradas | 7 (4 sem corroboração, 3 pelo prazo de validade) | 13 (sem corroboração) |
| Não resolvidas | 0 | 7 (leves; guardas sem autonomia) |
| Reservas duplas | 0 | 0 |
| Fecho médio: grave · média · leve | 10 s · 21 s · 31 s | 30 s · 73 s · 110 s |
| Mensagens por execução | 186 | 1188 |

Por ameaça, fecham como confirmadas 67 % em D (40 de 60) e 83 % em E (132 de 160). Os cenários com fila não se repetem byte a byte: numa repetição, E fechou 136 e deixou 3 por resolver.

## Sugestões testadas

O ponto a partir do qual mais já não ajuda ([sugestoes.csv](../../results/stress/sugestoes.csv); detalhe em [scalability.md](../scalability.md)):

| Situação | Sugestão | Evidência |
|---|---|---|
| 16 ameaças ao mesmo tempo | 3 guardas | 139 chegam ao guarda e 0 por resolver; com 2 eram 136 e 3 |
| Mensagens perdidas | 1 reenvio até 10 % de perda; 3 a 20 % | fecham as 17 possíveis em 20 |
| Ameaça de 15 s | guarda a 7 células ou menos | 5 de 5 a tempo a 7 células; 0 de 5 a 8 |
| Ameaça fora do alcance de quem inicia | um sensor iniciador que a alcance | de 0 alertas para 9 de 10 que chegam ao guarda |
| Um informador para 4 ameaças | 1 informador por iniciador | 40 de 40 mobilizadas, em vez de 10 |

## Reproduzir

```bash
PYTHONPATH=src python scripts/scale.py    # ~20 s
PYTHONPATH=src python scripts/dist.py     # ~2 min
```

Os restantes comandos estão em [scalability.md](../scalability.md#como-reproduzir).
