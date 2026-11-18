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
| 0.3 | Instalação testada: `PYTHONPATH=src python -m unittest discover -s tests` dá 579 testes OK (18-11-2026) | num computador | [ ] |

## Etapa 1 — contratos (fecha [development-plan.md:91](development-plan.md#L91))

| # | Decisão | Valor atual | Aprovado |
|---|---|---|---|
| 1.1 | Formato das mensagens e exemplos válidos e inválidos revistos por quem implementa agentes e simulação | [message-contract.md](message-contract.md), [protocols.md](protocols.md) | [x] 16-11-2026 (Guilherme) |
| 1.2 | Retenção para deduplicação por `message_id` | 600 s simulados (a constante e `MessageDeduplicator` foram removidos em 18-11-2026 por nunca terem sido usados; ver o [registo](#registo-de-alterações-ao-código)) | [x] 16-11-2026 (Guilherme) |

## Etapas 4–5 — corroboração e negociação

| # | Decisão | Valor atual | Aprovado |
|---|---|---|---|
| 4.1 | Compatibilidade de observações | distância ≤ 3,0 células, janela de 2,0 s, mínimo de 1 fonte compatível ([runner.py](../src/isia/simulation/runner.py)) | [ ] |
| 4.2 | Ausência de resposta, timeout ou falha de comunicação | `no_data`, nunca ausência informativa | [x] 16-11-2026 (Guilherme) |
| 4.3 | Sensibilidade e taxas de erro das fontes | as de [config/scenarios/](../config/scenarios/), sem calibração empírica | [ ] |
| 5.1 | Prazo de espera por propostas e `STATUS` | Prazo-base de 0,5 s reais (local) e 2,0 s (XMPP). Desde 18-11-2026, `run_mvp` liga por omissão o prazo dinâmico com teto de 2,0 s ([que teto escolher](scalability.md#que-teto-escolher)), a fila (`queue_rounds=60`) e o silêncio perante `ACCEPT` incoerente. O coletor e os scripts de medição continuam no prazo fixo, sem fila (`PUBLISHED_CONDITIONS`), por isso os resultados publicados não mudam: a Etapa 9 repetida deu ficheiros iguais, byte a byte | [ ] |
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

## Registo de alterações ao código

- **18-11-2026 — três opções ligadas por omissão** (pendente C do [Bloco F](delivery-todo.md#pendentes-deixados-pelo-bloco-f)): `max_receive_timeout=2.0`, `queue_rounds=60` e `silent_invalid=True` em `run_mvp`. Afeta o MVP na linha de comandos e o modo `--xmpp`; não afeta as recolhas (Etapa 9, P3, Blocos F1 e G), que passam `PUBLISHED_CONDITIONS`. Seis testes que verificavam o comportamento antigo foram ajustados. O silêncio muda o contrato de mensagens: um `ACCEPT` incoerente deixa de ter resposta. Falta a aprovação do item 5.1 por um elemento; para desfazer, basta repor os três valores na assinatura de `run_mvp`.
- **18-11-2026 — correções da auditoria ao código** (branch `fix/auditoria-correcoes`). (1) Aviso entre iniciadores: a espera pelos vizinhos gasta tempo real e o relógio simulado anda com as missões dos outros; o iniciador lia o feed outra vez, obtinha outra observação e o informador respondia `no_data`, por isso ameaças reais fechavam `expired`. Agora lê depois da espera, usa essa leitura e o mesmo incidente, e os pedidos de verificação levam a hora simulada atual. Sem leitura depois da espera fecha `expired/threat_expired`, em vez de pedir verificação de um evento de exemplo. (2) Segunda volta de `ALERT`: só se cede a um vizinho que fica com a ameaça. (3) Removidos `contract_net_demo.py` e o código que só os testes usavam (decisão `close`, `result_from_ground_truth`, `MessageDeduplicator`, `serialize_model`). (4) A espera por `VERIFY_RESPONSE` usa o prazo do iniciador; `requirements.txt` fixa `pyjabber` e `SQLAlchemy`. Afeta só as execuções com `alert_distance`: o cenário E e `alerta.csv` foram recolhidos de novo; A, B, C e D foram repetidos e não mudaram.

## Depois de aprovar

1. Preencher a data, quem aprovou e as caixas desta ata, e fazer commit.
2. No [plano](development-plan.md), assinalar as tarefas citadas acima com a ligação para esta ata.
3. Na [checklist de marcos](development-plan.md#checklist-de-marcos), fechar as Etapas 0–1, 4–5 e 7.
4. Qualquer «não» vira uma issue com o valor proposto. Se o valor mudar, a recolha da Etapa 9 tem de ser repetida.
