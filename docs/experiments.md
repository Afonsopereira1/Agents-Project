# Experiências — Etapa 9

[Plano](development-plan.md) · [Plano de avaliação](evaluation.md) · [Falhas](faults.md) · [Reputação e política](reputation-policy.md)

Os números abaixo vêm das **560 execuções** registadas em
[`results/experiments/`](../results/experiments/), feitas no commit
`667cba2`, sem alterações por fazer commit (ver `commit` e `dirty` em `manifest.json`). Os relatórios completos de cada execução
(`results/experiments/runs/`) não são versionados. Para os regenerar:

```bash
PYTHONPATH=src python -m isia.evaluation.collector config/scenarios/*.json --output results/experiments
# A pasta runs/ é apagada e recriada; summary.csv inclui média, mediana, desvio-padrão e n.
PYTHONPATH=src python -m unittest tests.unit.test_metrics tests.scenarios.test_experiments -v
```

## Unidade de avaliação e métricas

- **Unidade:** uma execução, ou seja, a zona 8×8 do MVP numa janela única. Não se avaliam observações isoladas.
- **Positivo real:** o cenário tem pelo menos um evento `threat`. **Positivo previsto:** a política mobiliza recursos (`request_mobile_verification` ou `request_rangers`). Uma execução sem alerta conta como negativo previsto.
- `TN` existe porque metade dos episódios (ou dois terços no B) não tem ameaça: `empty`, `thunder` ou `thunder+tourist`.
- Precision, recall e FPR ficam `N/A` quando o denominador é zero (`metrics.ratio`).
- **Tempos:** segundos simulados desde `t=0`, que é simultaneamente o início dos eventos e o instante do alerta. O tempo de deteção é sempre 0 nesta janela única, por isso não se reporta. `t verificação` é o `completed_at` do primeiro `MISSION_RESULT` recebido de `verify_incident`; `t resposta guarda` é o do `respond_incident`. Podem incluir resultados falhados. Resultados não recebidos ficam sem tempo e não entram na média; `n` indica os valores utilizados.
- **Energia:** soma dos pontos percentuais de autonomia gastos pelos recursos, não percentagem da capacidade energética total nem energia física. Se alguma autonomia inicial ou final for desconhecida, `energy_used` fica `N/A` e não entra nas estatísticas dessa métrica. **Mensagens:** tentativas de envio pela aplicação, incluindo as perdidas. **Perdidas** e **duplicadas** vêm do `fault_log`, não de confirmações individuais de entrega.
- **Missões:** `missions_done` e `missions_failed` contam estados terminais conhecidos pelo coordenador através dos resultados recebidos. Não contam todas as conclusões locais da timeline móvel: uma missão pode terminar e libertar a reserva, mas continuar desconhecida pelo coordenador se o resultado se perder. Os nomes dos campos CSV mantêm este significado.
- **Confirmadas:** execuções com resultado recebido de `verify_incident` confirmado. **Não resolvidos:** incidentes com estado `unresolved`.

## Cenários (`config/scenarios/*.json`)

Todos usam o mundo do MVP: `sensor-1` acústico em (2,2), que inicia o incidente, e `sensor-2` visual em (4,2), que corrobora. Recursos: drone em (0,2), veículo em (0,0) e guarda em (5,5). Os eventos ficam em (3,2). Cada cenário tem 20 repetições (sementes 1000–1019) × episódios.

| Cenário | Episódios | Fontes | Recursos / falhas |
|---|---|---|---|
| **A** — normal | `threat`, `empty` | FP 5 %, FN 5–10 %, sem erro de posição | Drone com carga 0.5; sem falhas |
| **B** — ruído | `threat`, `thunder`, `thunder+tourist` | FP 50–60 %, FN 20–25 %, erro de posição ±1, confiança 0.7 | Drone com carga 0.5; sem falhas |
| **C** — falhas/escassez | `threat`, `empty` | Iguais às de A | Drone com 15 % de autonomia; perda de 10 %, atraso de 0.05 s em `PROPOSAL`/`MISSION_RESULT`, `MISSION_RESULT` duplicado |

A política e a reputação são as de `config/agents.json`. Os sensores pertencem a grupos e modalidades diferentes. Uma regra explícita, `compatibility_rules`, permite que `suspicious_movement` corrobore `gunshot_like_sound`.

## Variantes comparadas (`collector.VARIANTS`)

As variantes comparam as configurações abaixo. `no_corroboration` altera tanto
a evidência considerada como o limiar de mobilização; por isso, compara dois
pipelines e não constitui uma ablação estrita de uma única variável.

| Variante | Diferença |
|---|---|
| `full` | Reputação partilhada entre execuções sucessivas do cenário, atualizada só por adjudicação de missão (Etapa 7) |
| `no_reputation` | Reputação reiniciada no prior (0.5) em cada execução |
| `no_corroboration` | A resposta do par é ignorada (`eligible=()`) e o limiar de patrulha desce para 0.01, portanto qualquer alerta isolado mobiliza |
| `nearest` | Seleção apenas por ETA (`energy_weight=load_weight=0`); com velocidades iguais, ganha a patrulha elegível mais próxima |

## Resultados

### Classificação

| Cen. | Variante | Exec. | TP | FP | TN | FN | Precision | Recall | FPR | Confirmadas | Não resolvidos |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | full | 40 | 17 | 0 | 20 | 3 | 1.00 | 0.85 | 0.00 | 17 | 0 |
| A | no_reputation | 40 | 17 | 0 | 20 | 3 | 1.00 | 0.85 | 0.00 | 17 | 0 |
| A | no_corroboration | 40 | 19 | 0 | 20 | 1 | 1.00 | 0.95 | 0.00 | 19 | 0 |
| A | nearest | 40 | 17 | 0 | 20 | 3 | 1.00 | 0.85 | 0.00 | 17 | 0 |
| B | full | 60 | 13 | 10 | 30 | 7 | 0.57 | 0.65 | 0.25 | 2 | 0 |
| B | no_reputation | 60 | 13 | 10 | 30 | 7 | 0.57 | 0.65 | 0.25 | 2 | 0 |
| B | no_corroboration | 60 | 16 | 30 | 10 | 4 | 0.35 | 0.80 | 0.75 | 2 | 0 |
| B | nearest | 60 | 13 | 10 | 30 | 7 | 0.57 | 0.65 | 0.25 | 2 | 0 |
| C | full | 40 | 16 | 0 | 20 | 4 | 1.00 | 0.80 | 0.00 | 10 | 10 |
| C | no_reputation | 40 | 15 | 0 | 20 | 5 | 1.00 | 0.75 | 0.00 | 9 | 10 |
| C | no_corroboration | 40 | 19 | 0 | 20 | 1 | 1.00 | 0.95 | 0.00 | 13 | 11 |
| C | nearest | 40 | 16 | 0 | 20 | 4 | 1.00 | 0.80 | 0.00 | 10 | 10 |

### Rapidez e custo (média ± desvio-padrão; n = execuções com esse valor)

| Cen. | Variante | t verificação (s) | t resposta guarda (s) | Autonomia gasta/exec. (p.p.) | Mensagens/exec. | Perdidas/exec. | Duplicadas/exec. |
|---|---|---|---|---|---|---|---|
| A | full | 6.00 ± 0.00 (n=17) | 12.00 ± 0.00 (n=17) | 8.5 | 6.5 | 0.00 | 0.00 |
| A | no_reputation | 6.00 ± 0.00 (n=17) | 12.00 ± 0.00 (n=17) | 8.5 | 6.5 | 0.00 | 0.00 |
| A | no_corroboration | 6.00 ± 0.00 (n=19) | 12.00 ± 0.00 (n=19) | 9.5 | 7.1 | 0.00 | 0.00 |
| A | nearest | 4.00 ± 0.00 (n=17) | 10.00 ± 0.00 (n=17) | 6.8 | 6.5 | 0.00 | 0.00 |
| B | full | 6.00 ± 1.00 (n=23) | 12.00 ± 0.00 (n=2) | 4.2 | 4.8 | 0.00 | 0.00 |
| B | no_reputation | 6.00 ± 1.00 (n=23) | 12.00 ± 0.00 (n=2) | 4.2 | 4.8 | 0.00 | 0.00 |
| B | no_corroboration | 5.80 ± 1.11 (n=46) | 12.00 ± 0.00 (n=2) | 7.7 | 7.8 | 0.00 | 0.00 |
| B | nearest | 4.17 ± 0.98 (n=23) | 10.00 ± 0.00 (n=2) | 2.8 | 4.8 | 0.00 | 0.00 |
| C | full | 6.00 ± 0.00 (n=10) | 17.00 ± 0.00 (n=6) | 4.5 | 4.2 | 0.42 | 0.42 |
| C | no_reputation | 6.00 ± 0.00 (n=9) | 17.00 ± 0.00 (n=5) | 4.0 | 3.9 | 0.42 | 0.38 |
| C | no_corroboration | 6.00 ± 0.00 (n=13) | 17.00 ± 0.00 (n=8) | 6.0 | 5.1 | 0.47 | 0.55 |
| C | nearest | 6.00 ± 0.00 (n=10) | 17.00 ± 0.00 (n=6) | 4.5 | 4.2 | 0.42 | 0.42 |

### Desfechos observados

- **A:** em todas as variantes, 1 das 20 ameaças não gerou alerta (FN do sensor). Em `full`, `no_reputation` e `nearest`, 2 ameaças terminaram `expired` por falta de corroboração (repetições 1 e 5): o sensor visual não detetou. Os 20 episódios vazios nunca geraram alerta.
- **B:** das 13 ameaças mobilizadas em `full`, só 2 foram confirmadas. As outras 11 terminaram `not_confirmed` porque o erro de posição ±1 mandou a patrulha inspecionar a célula errada. Em `full`, o episódio `thunder` nunca mobilizou, porque o sensor visual não vê trovão. Já `thunder+tourist` mobilizou 10 vezes, porque cada fonte deu um falso positivo, de origens diferentes, e as duas pareceram corroborar-se.
- **C:** o drone recusou sempre (`autonomy_insufficient`). Por isso, nas 20 ameaças de `full`, houve 6 `no_eligible_proposals`, 3 `confirmation_unknown` e 1 `mission_result_unknown`. Todos os casos analisados coincidem com uma única mensagem perdida (`CFP`, `PROPOSAL`, `ACCEPT`/`STATUS` ou `MISSION_RESULT`) no único recurso elegível. Não há retransmissões (Etapa 8). Houve 12 pedidos ou respostas de corroboração perdidos (linhas `Timeout à espera de VERIFY_RESPONSE`). Sem resposta, o sensor decide só com a evidência local. Em `full`, `no_reputation` e `nearest`, 7 terminaram `observe`/`expired` e 2 mobilizaram na mesma: em `full` e `nearest`, já com a reputação do `sensor-1` alta o suficiente. Em `no_corroboration`, os 3 casos mobilizaram.

## Discussão

- **Comparação `full` / `no_corroboration` (B):** `full` apresentou 10 falsos alarmes contra 30 em 40 negativos (FPR de 0.25 contra 0.75) e precision de 0.57 contra 0.35. Mobilizou menos 3 ameaças (recall de 0.65 contra 0.80), com menos autonomia gasta (4.2 contra 7.7 pontos percentuais por execução) e menos mensagens (4.8 contra 7.8). Estes valores medem a diferença conjunta de corroboração e limiar; não isolam o efeito causal da corroboração. Os 10 FP restantes vêm todos de `thunder+tourist`: dois falsos positivos de origens distintas parecem evidência independente.
- **Comparação `full` / `no_corroboration` (A, C):** o recall foi 0.85 contra 0.95 em A e 0.80 contra 0.95 em C. Em `full`, a falta de apoio do segundo sensor ou a perda da resposta podem impedir a mobilização; a baseline também aceita scores inferiores por usar outro limiar. Os negativos destes cenários são episódios vazios, que não geram falsos alertas neste simulador; FPR zero não demonstra robustez perante ruído.
- **Reputação:** sobe com cada missão confirmada (`sensor-1` chega a 0.90 em A, 0.86 em C e 0.67 em B), mas só muda **uma** decisão em 560 execuções. Foi em C, repetição 19: com reputação ≈ 0.86, o score isolado (0.86 × 0.8 / 2 × 0.75 ≈ 0.26) passa o limiar de 0.25. Com estes limiares é preciso reputação ≥ 0.84 para isso acontecer. Não aprende com `not_confirmed` (Etapa 7), por isso em B nunca desce. Não há evidência de que a reputação melhore a precisão nesta configuração.
- **Seleção da patrulha:** o custo composto evita o drone com carga 0.5 e escolhe o veículo, mais distante. `nearest` escolhe o drone e verifica mais cedo: 4.0 contra 6.0 s em A e 4.2 contra 6.0 s em B, com menos autonomia gasta (6.8 contra 8.5 pontos percentuais em A). O simulador não penaliza a carga, por isso o benefício de a evitar não é mensurável aqui. Em C o drone não tem autonomia e as duas regras coincidem.
- **Falhas (C contra A):** com a mesma qualidade de fontes, 10 das 20 ameaças em `full` ficaram `unresolved`, e só 6 tiveram resultado recebido da resposta do guarda (contra 17 em A). Nas execuções publicadas, o guarda respondeu aos 17 s simulados em vez de 12. A/full também seleciona o veículo: o aumento resulta das esperas de comunicação e da interação dos relógios, pois o tempo simulado pode continuar a avançar durante o regresso do veículo antes da atribuição ao guarda. A experiência combina falhas e escassez; não isola os seus efeitos individuais.

## Limitações e incerteza

- **Amostra pequena:** 20 repetições por episódio, sem intervalos de confiança. Diferenças de 1–2 execuções (por exemplo C `full` contra `no_reputation`) não devem ser lidas como efeitos.
- **Simulação simplificada:** janela única, `t=0` para eventos e alerta, mundo 8×8, um iniciador, dois sensores e eventos parados. Os tempos são, por isso, quase determinísticos (desvio-padrão 0 em A e C).
- **Parâmetros escolhidos pela equipa:** probabilidades, cargas, limiares e a regra de compatibilidade não estão calibrados nem aprovados formalmente (Etapa 7).
- **Baseline `no_corroboration`:** também baixa o limiar de patrulha. Sem isso, nenhum alerta isolado mobilizaria nestas configurações e o recall seria 0. A comparação permite avaliar os dois pipelines; uma conclusão causal sobre o efeito exclusivo da corroboração exigiria um controlo que separasse a alteração do limiar.
- **Reputação:** depende da ordem das execuções, porque `full` aprende sequencialmente.
- **Reprodutibilidade:** os cenários e a perda aleatória usam sementes fixas. A perda depende ainda da ordem de envios no `asyncio`, e os prazos de negociação são reais (0.5 s). `test_experiments` verifica que a mesma semente repete as métricas no cenário A. A injeção de falhas é só local; não valida XMPP.
- **Gráficos:** não foram produzidos, porque o projeto não depende de uma biblioteca de gráficos. As tabelas acima e `summary.csv` servem de base à Etapa 10.
