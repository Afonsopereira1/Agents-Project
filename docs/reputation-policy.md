# Reputação e política de resposta

[README](../README.md) · [Arquitetura](architecture.md) · [Protocolos](protocols.md) · [Experiências](experiments.md)

> **Em resumo**
>
> - O sensor iniciador calcula um **score de suspeita** a partir da sua leitura e da resposta da fonte que corrobora. O score é uma heurística, não uma probabilidade.
> - A **política** compara o score com limiares e escolhe: observar, pedir verificação a uma patrulha ou chamar guardas.
> - A **reputação** de uma fonte é uma média Beta que pesa as suas leituras. Só o avaliador a atualiza, depois da execução, e só quando uma patrulha independente confirma a ameaça no local.
> - Limite principal: nada produz um resultado `refuted`, por isso **a reputação nunca desce**. Nos resultados publicados mudou uma decisão em 140 pares de execuções.

Verificado contra o código em 18-11-2026 (branch `fix/auditoria-correcoes`).

## Quem faz o quê

| Módulo | Responsabilidade | Quem o chama |
|---|---|---|
| [corroboration.py](../src/isia/reasoning/corroboration.py) | Classifica a resposta e calcula o score | O sensor iniciador |
| [policy.py](../src/isia/reasoning/policy.py) | Escolhe a resposta a partir do score | O sensor iniciador |
| [reputation.py](../src/isia/reasoning/reputation.py) | Guarda acertos e erros por fonte | O avaliador (`run_mvp`), depois da execução |

O sensor nunca recebe a verdade de referência. Recebe uma cópia dos pesos (`book.snapshot(...)`) antes de começar, e essa cópia não muda durante a execução.

A política é opcional. Sem ela (sem `--policy`), o sensor usa a regra preliminar: pede verificação se a fonte devolver pelo menos uma observação compatível; caso contrário, observa.

## Reputação

```text
reputação = (acertos + α) / (acertos + erros + α + β)        α = β = 2
```

| Histórico da fonte | Reputação |
|---|---|
| Nova | 2 / 4 = 0,50 |
| 1 acerto | 3 / 5 = 0,60 |
| 1 erro | 2 / 5 = 0,40 |
| 17 acertos (cenário A, fim da recolha) | 19 / 21 = 0,90 |

Mede a utilidade da fonte **como alerta de ameaça**, não a exatidão física do sensor: um microfone que deteta corretamente um trovão produziu um alerta de ameaça errado.

Porquê a média Beta: uma fonte nova começa neutra (0,5) e precisa de vários resultados para se afastar. A alternativa, a fração simples de acertos, daria 1,0 logo ao primeiro acerto.

## Score de suspeita

```text
peso        = reputação × confiança declarada × fator temporal × fator espacial
fator       = 1 / (1 + diferença / limite)          (tempo: limite 2,0 s; espaço: limite 3,0 células)
apoio       = soma, por grupo de correlação, do maior peso a favor
oposição    = soma, por grupo de correlação, do maior peso contra
diversidade = 0,5 + 0,25 × min(2, número de modalidades com apoio)
score       = clamp((apoio − oposição) / 2, 0, 1) × diversidade
```

Regras (`evaluate_reputation_corroboration`):

- A leitura inicial do sensor entra sempre, com os dois fatores a 1.
- Uma observação fora da distância ou da janela não contribui.
- Fontes do mesmo **grupo de correlação** contam uma vez (o maior peso). Evita que dois sensores que partilham o mesmo ponto cego valham por dois.
- `no_data` e prazo esgotado não reduzem o score. Contradição e ausência informativa reduzem, mas nenhuma delas ocorre nas execuções medidas ([protocolos](protocols.md#4-verificação-distribuída)): aí a oposição é sempre 0.
- Uma fonte sem perfil configurado vai para o grupo `unknown`, sem modalidade.

Os grupos e as modalidades vêm da configuração (`sources` em `response_settings`). São declarados, não medidos: não provam independência estatística.

### Três exemplos

Reputações a 0,5 e confiança 0,8, por isso cada leitura pesa 0,5 × 0,8 = 0,4.

| Caso | Apoio | Diversidade | Score | Decisão |
|---|---|---|---|---|
| Dois sensores acústicos do mesmo grupo ([config/agents.json](../config/agents.json)) | 0,4 (um grupo) | 0,75 | 0,15 | `observe` |
| Sensor acústico + câmara, grupos diferentes (cenário A) | 0,8 | 1,0 | 0,40 | `request_mobile_verification` |
| O mesmo, com o sensor acústico já com reputação 0,9 | 0,72 + 0,4 | 1,0 | 0,56 | `request_mobile_verification` |

O primeiro caso mostra a correlação a funcionar: duas leituras iguais do mesmo tipo de sensor não chegam para mobilizar.

## Política de resposta

Limiares em [config/agents.json](../config/agents.json), iguais em todos os cenários:

| Parâmetro | Valor | Significado |
|---|---|---|
| `patrol_threshold` | 0,25 | Score mínimo para pedir uma patrulha |
| `ranger_threshold` | 0,65 | Score mínimo para chamar guardas diretamente |
| `ranger_min_groups`, `ranger_min_modalities` | 2 e 2 | Diversidade exigida para chamar guardas |
| `severe_threshold` | 0,8 | Gravidade a partir da qual a ameaça é «grave» |
| `severe_patrol_threshold` | 0,08 | Limiar de patrulha para uma ameaça grave |
| `severity` | 0,5 | Gravidade por omissão |

Regra (`decide_response`), pela ordem:

1. Score ≥ 0,65, pelo menos 2 grupos e 2 modalidades a favor, e sem evidência em conflito: `request_rangers`.
2. Score ≥ limiar de patrulha (0,25, ou 0,08 se a gravidade for ≥ 0,8): `request_mobile_verification`.
3. Caso contrário: `observe`.

A política não fecha ocorrências. Um score baixo leva a `observe`, e a ocorrência termina como `expired`. Quando uma patrulha confirma, é o iniciador que pede guardas ([protocolos](protocols.md#missões-e-intervenção--etapa-6)).

A **gravidade** é configurada, não medida: `severity` para todos, ou `severity_by_source` por sensor (cenários D e E). Não é a intensidade do sinal. Também define a prioridade da missão: 0 leve (< 0,4), 1 média, 2 grave (≥ 0,8).

Exemplo: com gravidade 0,8, o primeiro caso da tabela acima (score 0,15) passa o limiar de 0,08 e mobiliza uma patrulha.

**O ramo `request_rangers` nunca dispara nos resultados publicados.** A reputação da fonte que corrobora fica em 0,5 (ver abaixo), por isso o score máximo é (1,0 × 0,8 + 0,5 × 0,8) / 2 = 0,60, abaixo de 0,65. Os guardas são sempre chamados depois de uma patrulha confirmar. O ramo está coberto por testes ([test_policy.py](../tests/unit/test_policy.py), [test_mvp_policy.py](../tests/scenarios/test_mvp_policy.py)).

Estes valores são de engenharia: estão testados (os limiares são inclusivos), mas **não foram calibrados com dados reais** nem aprovados formalmente. A sensibilidade a cada um está em [sensitivity.md](sensitivity.md).

## Adjudicação: quando a reputação é atualizada

Depois de o sensor terminar, o `run_mvp` converte cada `MISSION_RESULT` num `EvaluationResult` (`result_from_mission`) e tenta atualizar o livro. A atualização só é aceite se **tudo** isto for verdade:

| Condição | Valor |
|---|---|
| A missão é uma verificação (`verify_incident`) com `outcome=confirmed` | — |
| A célula inspecionada está perto da observação | ≤ 1 célula (`adjudication.max_distance`) |
| A inspeção é posterior à observação e recente | ≤ 30 s simulados (`adjudication.max_delay_seconds`) |
| Quem inspecionou não é a fonte avaliada | Uma patrulha não valida as suas próprias leituras |
| A observação ainda não foi avaliada nesta execução | Uma vez por observação e por par fonte/ocorrência |

O que **não** atualiza a reputação: `not_confirmed`, `failed`, `inconclusive`, a intervenção do guarda, a concordância entre sensores e o prazo esgotado. O relatório lista as atualizações aceites e recusadas em `reputation_updates`, com o motivo.

Exemplo real (`--policy` com gravidade 0,8): o drone confirma, a reputação de `sensor-1` passa de 0,5 para 0,6; o resultado do guarda é recusado com `unresolved_result`.

### Identidade da execução (`run_id`)

O livro não conta duas vezes a mesma observação dentro do mesmo `run_id`.

- Com cenário, o `run_id` é o do cenário.
- Sem cenário, é `mvp-seed-<semente>`: repetir a simulação não aumenta a reputação. Para contar como nova amostra, passar `--run-id` (ou `run_id=`).
- Um `run_id` diferente não prova que as amostras sejam independentes.

O livro vive em memória. Para aprender entre execuções, o mesmo `ReputationBook` é passado a várias chamadas de `run_mvp(reputation=book)`; é o que o coletor faz na variante `full`.

## Executar

```bash
PYTHONPATH=src python -m isia.simulation.runner --policy config/agents.json > /tmp/isia-policy.json
PYTHONPATH=src python -m unittest discover -s tests/scenarios -p test_mvp_policy.py -v
```

Resultado esperado do primeiro comando: decisão `observe`, score 0,15, nenhuma missão, ocorrência `expired`. Mudar `severity` para `0.8` no JSON mobiliza a patrulha e o guarda e fecha como `closed` / `confirmed`.

O JSON de saída traz a configuração, os pesos, cada fator do score, a decisão e a linha temporal.

## Limites assumidos

- **A reputação só sobe.** `result_from_mission` produz `confirmed` ou `inconclusive`, nunca `refuted`: uma patrulha que não encontra nada não prova que não havia ameaça. Um sensor com muitos falsos alarmes não é penalizado. No cenário B, a reputação de `sensor-1` sobe de 0,50 para 0,67.
- **Só `sensor-1` aprende.** São avaliadas as leituras do iniciador base. As da fonte que corrobora e as dos iniciadores adicionais (cenários D e E) ficam em 0,5.
- **Efeito pequeno.** Entre as variantes `full` e `no_reputation` muda uma decisão em 140 pares de execuções ([experiments.md](experiments.md#desfechos-observados)).
- **O score não é uma probabilidade.** Os limiares 0,25 e 0,65 não significam 25 % e 65 %.
- **Os grupos de correlação são declarados à mão.**
- **Sem persistência.** O livro perde-se quando o processo termina.
