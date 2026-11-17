# Ata de aprovação — parâmetros e contratos

> Preparada para o [Bloco E](delivery-todo.md#bloco-e--fecho-do-plano). Basta um elemento aprovar cada linha, com a data e o nome. Se um valor mudar, abrir uma issue em vez de alterar o código no momento.

**Data:** ____ · **Aprovado por:** ____

**Itens em exploração:** 4.1, 4.3, 5.1, 5.2 e 7.1–7.6 só se decidem depois de medido o efeito de dois valores alternativos ([Bloco G](delivery-todo.md#bloco-g--sensibilidade-dos-parâmetros-no-final)).

**Como decidir:** os valores abaixo são os que estão no código e produziram os resultados de `results/`. Alterar um valor obriga a repetir a recolha da Etapa 9. Por isso, a pergunta é «aceitamos estes valores para a entrega?», e não «são os ideais?».

## Etapa 0 — ambiente (fecha [development-plan.md:49](development-plan.md#L49) e [:53](development-plan.md#L53))

| # | Decisão | Valor atual | Aprovado |
|---|---|---|---|
| 0.1 | Documentação em `docs/` aceite como base da entrega | `main` atual | [ ] |
| 0.2 | Versões | Python 3.12, SPADE 4.1.4 ([requirements.txt](../requirements.txt)) | [ ] |
| 0.3 | Instalação testada: `PYTHONPATH=src python -m unittest discover -s tests` dá 496 testes OK | num computador | [ ] |

## Etapa 1 — contratos (fecha [development-plan.md:91](development-plan.md#L91))

| # | Decisão | Valor atual | Aprovado |
|---|---|---|---|
| 1.1 | Formato das mensagens e exemplos válidos e inválidos revistos por quem implementa agentes e simulação | [message-contract.md](message-contract.md), [protocols.md](protocols.md) | [x] 16-11-2026 (Guilherme) |
| 1.2 | Retenção para deduplicação por `message_id` | 600 s simulados ([messages.py:33](../src/isia/communication/messages.py#L33)) | [x] 16-11-2026 (Guilherme) |

## Etapas 4–5 — corroboração e negociação

| # | Decisão | Valor atual | Aprovado |
|---|---|---|---|
| 4.1 | Compatibilidade de observações | distância ≤ 3,0 células, janela de 2,0 s, mínimo de 1 fonte compatível ([runner.py](../src/isia/simulation/runner.py)) | [ ] |
| 4.2 | Ausência de resposta, timeout ou falha de comunicação | `no_data`, nunca ausência informativa | [x] 16-11-2026 (Guilherme) |
| 4.3 | Sensibilidade e taxas de erro das fontes | as de [config/scenarios/](../config/scenarios/), sem calibração empírica | [ ] |
| 5.1 | Prazo de espera por propostas e `STATUS` | 0,5 s reais (local), 2,0 s (XMPP). Prazo dinâmico opcional (`max_receive_timeout`), desligado; proposta: teto de 2,0 s ([que teto escolher](scalability.md#que-teto-escolher)) | [ ] |
| 5.2 | Custo da proposta | ETA + energia + carga, pesos 1,0 cada; autonomia mínima de 10 % | [ ] |
| 5.3 | ~~Desvio ao FIPA na recusa do CFP~~ | Corrigido a 16-11-2026: o recurso envia `refuse` ([protocols.md, secção 9](protocols.md#9-porquê-estes-protocolos-alternativas-prós-e-contras)) | Não se aplica |

## Etapa 7 — reputação e política (fecha [development-plan.md:341](development-plan.md#L341))

Valores de [config/agents.json](../config/agents.json).

| # | Decisão | Valor atual | Aprovado |
|---|---|---|---|
| 7.1 | Prior da reputação | α = β = 2,0 (reputação inicial de 0,5) | [ ] |
| 7.2 | Limiares da política | patrulha 0,25 · guarda 0,65 · grave 0,8 · patrulha em caso grave 0,08 | [ ] |
| 7.3 | Diversidade exigida para chamar o guarda | 2 grupos de correlação e 2 modalidades | [ ] |
| 7.4 | Gravidade por omissão | 0,5 | [ ] |
| 7.5 | Adjudicação de uma missão | distância ≤ 1 célula, atraso ≤ 30 s | [ ] |
| 7.6 | Os limiares são *scores* de engenharia, não probabilidades calibradas | [reputation-policy.md](reputation-policy.md) | [ ] |

## Depois de aprovar

1. Preencher a data, quem aprovou e as caixas desta ata, e fazer commit.
2. No [plano](development-plan.md), assinalar as tarefas citadas acima com a ligação para esta ata.
3. Na [checklist de marcos](development-plan.md#checklist-de-marcos), fechar as Etapas 0–1, 4–5 e 7.
4. Qualquer «não» vira uma issue com o valor proposto. Se o valor mudar, a recolha da Etapa 9 tem de ser repetida.
