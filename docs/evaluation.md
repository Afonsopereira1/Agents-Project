# Plano de testes, cenários e avaliação experimental

> **Estado:** plano cumprido. Este documento diz o que se avalia e como. Os números estão em [experiências](experiments.md) e em [sensibilidade](sensitivity.md).

[README](../README.md) · [Plano](development-plan.md) · [Estratégia](architecture.md#estratégia-técnica-e-algoritmos) · [Requisitos e fontes](../README.md#requisitos-e-fontes)

## Em resumo

- O enunciado pede pelo menos três cenários contrastantes, métricas, trade-offs e limitações. Temos **três cenários (A normal, B ruído, C falhas e escassez) × 4 variantes × 20 sementes = 560 execuções**, mais 3500 execuções de sensibilidade.
- A unidade é a execução. Medimos TP, FP, TN e FN, precision, recall e FPR, tempo até à verificação e até ao guarda, energia, mensagens e ocorrências não resolvidas.
- A corroboração corta falsos alarmes em B (FPR 0,25 contra 0,75) e custa recall (0,65 contra 0,80). A reputação quase não muda decisões (1 execução em 140 pares). O custo composto não se distingue de `nearest` na classificação.
- Com falhas e escassez (C), 10 das 16 ameaças mobilizadas ficam por resolver.
- A amostra é pequena (20 ameaças por cenário) e não há testes de significância.

## 1. Questões de investigação e respostas

| # | Pergunta | Resposta medida | Onde |
|---:|---|---|---|
| 1 | A corroboração reduz os falsos alertas sem perder demasiada deteção? | Em B: 10 falsos alarmes em vez de 30 (FPR 0,25 contra 0,75); recall 0,65 em vez de 0,80. A comparação muda também o limiar, por isso não isola a corroboração. | [Discussão](experiments.md#discussão) |
| 2 | A reputação melhora as decisões? | Não se observa. `full` e `no_reputation` diferem numa execução em 140 pares (C, repetição 19). | [Discussão](experiments.md#discussão) |
| 3 | Negociar por custo composto é melhor do que escolher a patrulha mais próxima? | Não se mede vantagem. A classificação é igual; `nearest` verifica aos 4 s em vez de 6 s e gasta 6,8 p.p. em vez de 8,5 (A). A carga que o custo composto evita não tem custo físico no simulador. | [Discussão](experiments.md#discussão) |
| 4 | Como se degrada o sistema com atrasos, perdas e recursos limitados? | Em C, 6 ameaças chegam à intervenção do guarda, contra 17 em A; 10 ficam `unresolved`; o guarda responde aos 17 s em vez de 12 s. | [Desfechos](experiments.md#desfechos-observados) |
| 5 | Que compromisso existe entre rapidez, precisão, energia e mensagens? | Menos falsos alarmes custa recall. Em B, subir o limiar de patrulha de 0,25 para 0,35 leva o FPR a 0,025 e o recall a 0,10. Menos energia significa muitas vezes menos ameaças atendidas. | [Sensibilidade](sensitivity.md#resultados-por-parâmetro) |

As respostas valem para estes cenários e estes parâmetros. Não são efeitos demonstrados em geral.

## 2. Cenários contrastantes

| Cenário | O que configura | Pergunta principal |
|---|---|---|
| **A — Operação normal** | Fontes pouco ruidosas (FP 5 %, FN 5 % e 10 %), sem falhas, recursos com 100 % de autonomia | Linha de base de deteção e resposta |
| **B — Sensores ruidosos** | FP 60 % e 50 %, FN 20 % e 25 %, erro de posição ±1, confiança 0,7; episódios benignos `thunder` e `thunder+tourist` | Robustez da corroboração e da reputação |
| **C — Falhas e escassez** | Fontes de A; perda de 10 % das mensagens, atraso de 0,05 s, resultados duplicados; drone com 15 % de autonomia | Degradação, coordenação e recuperação |

Os três vivem em `config/scenarios/{A,B,C}.json` e correm 20 repetições com as sementes 1000 a 1019. Os valores foram escolhidos pela equipa; não são medições de campo. O detalhe está em [cenários](experiments.md#cenários-configscenariosjson).

Os cenários D e E (várias ocorrências em simultâneo e informadores humanos) são demonstrações à parte, descritas em [escalabilidade](scalability.md).

## 3. Variantes de comparação

Cada cenário corre em quatro variantes, com as mesmas sementes e os mesmos episódios ([`collector.VARIANTS`](../src/isia/evaluation/collector.py)):

| Variante | Para que serve |
|---|---|
| `full` | Solução completa |
| `no_corroboration` | Ignora o par e baixa o limiar de patrulha para 0,01: um alerta isolado mobiliza |
| `no_reputation` | Reputação reposta no prior em cada execução |
| `nearest` | Escolhe a patrulha só por ETA, sem energia nem carga |

Duas ressalvas:

- `no_corroboration` muda a evidência e o limiar ao mesmo tempo. Compara dois pipelines; não é uma ablação de uma só variável.
- Não há uma variante «sem falhas». O efeito das falhas lê-se comparando C com A, que têm as mesmas fontes. C muda também a autonomia e a carga do drone, por isso a comparação não isola as falhas.

Sementes comuns reduzem a variabilidade do ambiente. Não garantem a mesma ordem de envios assíncronos em C.

## 4. Métricas

As definições completas estão em [unidade de avaliação e métricas](experiments.md#unidade-de-avaliação-e-métricas). O que ficou do plano:

| Métrica planeada | Como ficou implementada (`metrics.py`) |
|---|---|
| TP, FP, TN, FN | Por execução. Positivo real: o episódio tem um evento `threat`. Positivo previsto: a decisão mobiliza patrulha ou guarda. |
| Precision, recall, FPR | `TP/(TP+FP)`, `TP/(TP+FN)`, `FP/(FP+TN)`; `N/A` com denominador zero |
| Tempo de deteção | Não se reporta: eventos e alerta começam em `t=0`, logo é sempre 0 |
| Tempo de resposta | Dois tempos em segundos simulados: até ao resultado da verificação e até ao resultado do guarda |
| Sucesso das missões | Contagens `missions_done` e `missions_failed` conhecidas pelo coordenador; não é uma taxa |
| Energia consumida | Soma dos pontos percentuais de autonomia gastos pelos três recursos; `N/A` se alguma autonomia for desconhecida |
| Mensagens por incidente | Tentativas de envio por execução, incluindo as perdidas; perdidas e duplicadas contam-se à parte |
| Conflitos de missão | Não se calcula em A, B e C: há um só iniciador, logo não há concorrência pelos recursos |
| Não resolvidos | Execuções que terminam com a ocorrência em `unresolved` |

Os verdadeiros negativos existem porque metade dos episódios de A e C, e dois terços dos de B, não têm ameaça.

## 5. Protocolo seguido

1. Cenários, sementes e parâmetros ficam em ficheiros versionados antes da recolha.
2. O coletor corre cenário × variante × repetição × episódio, em sequência. Em `full`, a reputação passa de uma execução para a seguinte.
3. Guarda-se uma linha por execução (`runs.csv`), o resumo com média, mediana, desvio-padrão e `n` (`summary.csv`) e o commit usado (`manifest.json`).
4. Os testes verificam as métricas e a repetição com a mesma semente.
5. A sensibilidade varia um parâmetro de cada vez sobre os mesmos cenários.

```text
results/experiments/
  runs.csv  summary.csv  manifest.json
  charts/taxas.svg  charts/custo.svg
  runs/<cenário>/<variante>/<run_id>.json   (relatórios completos, não versionados)
results/sensitivity/
  summary.csv  completion-manifest.json
```

Comandos em [como reproduzir](experiments.md#como-reproduzir).

## 6. Testes automáticos

O enunciado considera os testes opcionais. O repositório tem 560 funções de teste em `tests/` (unitários, integração e cenários).

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

Onde estão os casos previstos no plano:

| Caso | Teste |
|---|---|
| Posição inválida é rejeitada | `tests/test_models.py` (`test_coordenadas_negativas`) |
| Mensagem sem campo obrigatório é rejeitada | `tests/test_messages.py` (`test_campos_obrigatorios`) |
| Observação repetida conta uma vez | `tests/unit/test_policy.py` (`test_duplicate_forwarded_and_reordered_observations_do_not_change_score`) |
| Reputação com poucos dados não vai a extremos | `tests/unit/test_reputation.py` (`test_new_source_and_small_sample_are_smoothed`) |
| Denominador zero dá `N/A` | `tests/unit/test_metrics.py` (`test_zero_denominators_are_none`) |
| Recurso sem autonomia não parte | `tests/scenarios/test_mvp.py` (`test_outside_map_and_insufficient_round_trip_never_move`) |
| Proposta atrasada ou duplicada é ignorada | `tests/unit/test_allocation.py` (`test_ignores_invalid_duplicate_and_late_proposals`) |
| Mensagem perdida termina em timeout | `tests/test_sensor_timeout.py` (`test_termina_sem_resposta_e_regista_timeout`) |
| Dois iniciadores sem dupla reserva | `tests/integration/test_stress_extensions.py` (`test_two_initiators_share_resources_without_double_booking`) |
| Ocorrência completa, do alerta ao fecho | `tests/scenarios/test_mvp.py` (`test_alert_to_closure_two_sensors_two_candidates_and_ranger`) |
| Falso positivo fecha sem chamar o guarda | `tests/scenarios/test_mvp.py` (`test_not_confirmed_closes_without_ranger`) |
| Mesma semente, mesmas métricas | `tests/scenarios/test_experiments.py` (`test_same_seed_repeats_same_metrics_and_stores_runs`) |

O caso «iniciador indisponível» do plano não tem teste dedicado. Existe o do par indisponível, em `tests/scenarios/test_runner_audit_corrections.py`.

## 7. Matriz requisito → evidência

| Requisito | Evidência |
|---|---|
| Tema C — descentralização | Não há despacho global: o runner não escolhe vencedores nem fecha ocorrências. Em A, B e C há um só iniciador (`sensor-1`); vários iniciadores em paralelo só são medidos no [cenário D](scalability.md#cenário-d--dia-movimentado). |
| Tema C — deteção | TP e FN por cenário: recall 0,85 (A), 0,65 (B) e 0,80 (C) em `full` |
| Tema C — corroboração | `full` contra `no_corroboration` em B: FPR 0,25 contra 0,75 |
| RF3 — reputação | `full` contra `no_reputation`: uma decisão diferente em 140 pares; reputação final do `sensor-1` de 0,90 (A), 0,67 (B) e 0,86 (C) |
| Tema C — coordenação de patrulhas | Contract Net com custo composto contra `nearest`: veículo contra drone, mesma classificação |
| Tema C — falsos positivos | Cenário B: precision 0,57, FPR 0,25; os 10 FP vêm todos de `thunder+tourist` |
| Tema C — conectividade intermitente | Cenário C: 10 ocorrências `unresolved`, cada uma com uma mensagem perdida |
| Tema C — recursos limitados | Cenário C: o drone com 15 % recusa os 12 pedidos que recebe |
| Enunciado — três cenários | `config/scenarios/{A,B,C}.json` e [`results/experiments/`](../results/experiments/) |
| Enunciado — trade-offs e limitações | [Discussão](experiments.md#discussão), [limitações](experiments.md#limitações-e-incerteza) e [sensibilidade](sensitivity.md) |

## 8. Como interpretar os resultados

- Um ganho de precision só conta se o recall não cair demasiado. Ler sempre os dois.
- Menos energia ou menos mensagens pode ser só menos ameaças atendidas.
- Em cenários com perdas, as mensagens contadas são tentativas de envio, não entregas.
- Os tempos médios só incluem execuções cujo resultado chegou. Ver sempre o `n`.
- Uma diferença de uma ou duas execuções em 20 não é um efeito. Não há testes de significância.
- Limites de validade: sensores simulados, mundo 8×8, probabilidades escolhidas pela equipa, falhas só no transporte local.
