# ISIA — Tema C: Monitorização descentralizada da vida selvagem

**Unidade curricular:** Introdução aos Sistemas Inteligentes e Autónomos (2026/2027) — Assignment 1  
**Tema:** *Decentralised Wildlife Monitoring and Anti-Poaching Patrols*

> **Estado (18-11-2026, commit `d99ede4`):** código, testes, resultados e demonstração gravada estão no repositório. Os comandos e os tempos deste README foram executados nesta data, salvo os assinalados com \*. O que falta para a entrega está em [Limites conhecidos](#limites-conhecidos).

## O projeto

Simulamos uma reserva onde sensores e informadores detetam atividade suspeita e **corroboram** as observações uns dos outros. Drones, veículos e guardas (*rangers*) negoceiam cada missão por Contract Net, **sem despachante central**: cada ocorrência tem um iniciador local temporário (abordagem B1) e cada recurso decide sozinho se propõe ou recusa. Os agentes são SPADE (Python/XMPP); o simulador guarda a verdade dos acontecimentos só para a avaliação.

## Começar em 2 minutos

A partir da raiz. Nenhum destes passos precisa de servidor XMPP.

```bash
# 1. Ambiente: Python 3.12, versão recomendada e validada no projeto
python3.12 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
export PYTHONPATH=src

# 2. Testes: 581, OK, cerca de 47 s (19-11-2026; ambiente descrito abaixo)
python -m unittest discover -s tests

# 3. MVP: uma ocorrência completa, cerca de 1 s; o relatório JSON sai no stdout
python -m isia.simulation.runner > /tmp/isia-mvp.json

# 4. Demonstração: repetição do relatório no terminal (só lê o JSON)
python scripts/replay.py /tmp/isia-mvp.json --delay 0.5
```

**Resultado esperado do MVP:** `incident_status: "closed"`, 15 mensagens. O segundo sensor corrobora a observação do primeiro, o drone verifica aos 4 s simulados e o guarda intervém aos 10 s. No fim, todas as reservas estão a `null` e os recursos `available`: drone com 94 % de energia, veículo com 100 % (propôs, não foi escolhido) e guarda com 90 %.

**Compatibilidade Python:** o código exige pelo menos Python 3.11 devido a
`asyncio.timeout()`. A versão recomendada e efetivamente validada no projeto é
Python 3.12. O SPADE 4.1.4 declara `Requires-Python: >=3.10,<=3.14`, que aceita
3.14.0, mas exclui 3.14.4. Essa declaração não equivale à compatibilidade do nosso
código: Python 3.10 não é suficiente, e não validámos o projeto em 3.11 ou 3.14.

**Validação dos testes (19-11-2026):** 581 testes aprovados em 46,814 s, sem
falhas, erros ou testes ignorados, incluindo os oito testes das métricas com vários
iniciadores e os treze novos testes de validação de protocolos. A execução usou
Python 3.12.3, SPADE 4.1.4, pyjabber 0.4.5
e SQLAlchemy 2.1.0 num ambiente existente. O projeto fixa SQLAlchemy 2.1.8 em
`requirements.txt`; esta execução não valida essa versão. Não foram instaladas
nem atualizadas dependências.

**Demonstração sem instalar nada:**

```bash
scriptreplay --log-timing results/demo/replay.tim --log-out results/demo/replay.log       # MVP
scriptreplay --log-timing results/demo/replay-d.tim --log-out results/demo/replay-d.log   # cenário D
```

Ou o vídeo [results/demo/mvp.mp4](results/demo/mvp.mp4) (25 s).

## Comandos por ordem

Todos correm da raiz, com o ambiente ativo e `PYTHONPATH=src`.

| O que reproduz | Comando | Tempo | Onde grava |
|---|---|---|---|
| Testes | `python -m unittest discover -s tests` | 47 s | nada versionado |
| MVP | `python -m isia.simulation.runner` | 1 s | stdout |
| MVP com a política de reputação | `python -m isia.simulation.runner --policy config/agents.json` | 1 s | stdout |
| MVP com falhas injetadas | `python -m isia.simulation.runner --faults config/faults.json` | 2 s | stdout |
| Cenários A, B e C (560 execuções) | `python -m isia.evaluation.collector config/scenarios/*.json --output results/experiments` | 3,5 min\* | `results/experiments/` |
| Gráficos dos cenários | `python scripts/charts.py` | < 1 s | `results/experiments/charts/` |
| P3: custo e espera | `python scripts/scale.py` | 18 s | `results/scalability/scale.csv` |
| P3: cobertura e distribuição | `python scripts/dist.py` | 47 s | `results/scalability/dist.csv` |
| Stress F1 (perda, latência, cascata, autonomia, falhas combinadas) | `python scripts/stress_f1.py` | 9 min\* | `results/stress/<grupo>.csv` |
| Stress F1, reenvio de mensagens | `python scripts/stress_f1.py reenvio` | 10 min\* | `results/stress/reenvio.csv` |
| Stress F2 (16 grupos: paralelo, fila, prioridade, guardas, informadores…) | `python scripts/stress_f2.py` | mais de 15 min\* | `results/stress/<grupo>.csv` |
| Stress: 1000 execuções com a mesma reputação | `python scripts/stress_long.py` | 3 min\* | `results/stress/longa.csv` |
| Sugestões: o ponto ótimo de guardas, reenvios, distância e cobertura | `python scripts/sugestoes.py` | 10 min | `results/stress/sugestoes.csv` |
| Cenário D, «dia movimentado» (6 ameaças) | `python -m isia.evaluation.collector config/scenarios/demo/D.json --variants full --output results/scenario-d` | 5 s | `results/scenario-d/` |
| Cenário E, «reserva alargada» (16 ameaças, 20 fontes) | `python -m isia.evaluation.collector config/scenarios/demo/E.json --variants full --output results/scenario-e` | 16 s | `results/scenario-e/` |
| Cenário E: câmaras contra informadores humanos | `python scripts/scenario_e.py` (depois da linha anterior) | < 1 s\* | `results/scenario-e/informants.csv` |
| Sensibilidade dos parâmetros (Bloco G) | `python scripts/sensitivity.py --list`; ver [sensitivity.md](docs/sensitivity.md) | não medido\* | pasta nova em `results/sensitivity/` |

**Resultado esperado do MVP com política:** o comando
`python -m isia.simulation.runner --policy config/agents.json` decide `observe`,
com score de suspeita aproximadamente 0,15, e termina com
`incident_status: "expired"` e `reason: "insufficient_corroboration"`. Envia duas
mensagens e não cria missões. As reservas ficam a `null` e todos os recursos
ficam disponíveis, com 100 % de autonomia, sem consumo. Este resultado é esperado,
não é um bug: as duas fontes acústicas pertencem ao mesmo grupo de correlação e
o score fica abaixo do limiar de patrulha de 0,25. Ver
[reputação e política](docs/reputation-policy.md).

\* Não repetido a 18-11-2026. Os tempos vêm da coluna `tempo_real_s` dos CSV publicados e do [plano](docs/development-plan.md); dependem da máquina. De `scenario_e.py` e da recolha da sensibilidade só se confirmou que os scripts e as opções existem (`--list` e `--dry-run` correm).

**Antes de correr:**

- **Os comandos da tabela reescrevem ficheiros versionados em `results/`.** Para experimentar o coletor sem lhes tocar, usar `--output "$(mktemp -d)"`. Os scripts de `scripts/` gravam sempre no mesmo sítio.
- **`stress_f1.py` e `stress_f2.py` aceitam nomes de grupos**, por exemplo `python scripts/stress_f1.py cascata` (20 s) ou `python scripts/stress_f2.py paralelo` (9 s). A lista está no cabeçalho de cada script.
- **O que se repete igual:** `charts.py` e `dist.py` deram ficheiros iguais aos publicados, byte a byte; `scale.py`, `cascata` e `paralelo` também, exceto a coluna do tempo real. A recolha de A, B e C deu ficheiros iguais nas repetições registadas no [plano](docs/development-plan.md).
- **O que não se repete igual:** os cenários D e E, porque a ordem na fila depende do relógio real. Em três repetições do D fecharam 44, 46 e 47 de 52 ocorrências (publicado: 45). Numa repetição do E fecharam 139 de 152, com 0 por resolver (publicado: 132 e 7).
- **O coletor precisa do `.git`**: grava o commit em `manifest.json` e recusa correr sem repositório. Ver [Limites conhecidos](#limites-conhecidos).
- **MVP e recolhas correm em condições diferentes.** Desde 18-11-2026, o MVP liga por omissão o prazo dinâmico, a fila e o silêncio perante `ACCEPT` incoerente. O coletor e os scripts de P3 e de stress passam `PUBLISHED_CONDITIONS`, para reproduzir os resultados publicados; cada cenário ou teste liga só as opções que mede. Ver a [ata](docs/approvals.md).

## Mapa do repositório

```text
src/isia/agents/          agentes SPADE: sensor, informador, iniciador da ocorrência, drone, veículo, guarda
src/isia/communication/   mensagens JSON e transporte
src/isia/reasoning/       corroboração, reputação, política de resposta, alocação (Contract Net)
src/isia/simulation/      mapa 2D, relógio, cenário, movimento e runner do MVP
src/isia/evaluation/      métricas, coletor de cenários, calibração
src/isia/domain/          modelos, estados do incidente, validação
config/                   política (agents.json), falhas (faults.json), cenários A, B, C e demo/D, E
scripts/                  repetição, gráficos, P3, stress, cenário E e sensibilidade
tests/                    581 testes: unit/, integration/, scenarios/ e raiz
results/                  resultados publicados: CSV, manifestos, gráficos e gravações
docs/                     documentação (tabela abaixo)
hello_agent.py, main.py, verification_demo.py    demonstrações com servidor XMPP
```

| Pergunta | Documento |
|---|---|
| **P1.** Como são construídos os agentes? | [architecture.md](docs/architecture.md) |
| **P2.** Que protocolos, porquê esta arquitetura, prós e contras? | [protocols.md](docs/protocols.md) e [architecture.md](docs/architecture.md) |
| **P3.** Escalabilidade computacional e situacional; testes de stress; cenários D e E | [scalability.md](docs/scalability.md) |
| Resultados dos cenários A, B e C | [experiments.md](docs/experiments.md) |
| Métricas e definição dos cenários | [evaluation.md](docs/evaluation.md) |
| Falhas injetadas (perda, atraso, duplicação, indisponibilidade) | [faults.md](docs/faults.md) |
| Reputação e política de resposta | [reputation-policy.md](docs/reputation-policy.md) |
| Efeito de cada parâmetro | [sensitivity.md](docs/sensitivity.md) |
| Formato das mensagens | [protocols.md](docs/protocols.md); o contrato anterior está em [message-contract.md](docs/message-contract.md) |
| Apresentação: ordem, tempos e fala de cada diapositivo | [presentation/roteiro.md](docs/presentation/roteiro.md) |
| Valores dos parâmetros e quem os aprovou | [approvals.md](docs/approvals.md) |

**Registos do processo** (históricos; não são precisos para correr nem para avaliar): [plano por etapas](docs/development-plan.md), [pendentes para a entrega](docs/delivery-todo.md), [organização do grupo](docs/team-tasks.md), [proposta inicial ao professor](docs/ISIA_Tema_C_Proposta_para_Professor.md) e [requisitos iniciais](requirements.md).

## Demonstrações com servidor XMPP (opcional)

Os mesmos agentes correm ligados a um servidor XMPP local, que vem com o SPADE.

```bash
# Terminal 1: servidor em memória (Ctrl+C para parar)
spade run --host localhost --memory

# Terminal 2: mesmo ambiente, com PYTHONPATH=src
XMPP_PASSWORD=local-demo python -m isia.simulation.runner --xmpp    # MVP completo: closed, cerca de 1 s
python hello_agent.py                                               # um agente arranca, cumprimenta e termina
SENSOR_PASSWORD=a INFORMANT_PASSWORD=b python main.py                # VERIFY_REQUEST → VERIFY_RESPONSE
SENSOR_PASSWORD=a INFORMANT_PASSWORD=b python verification_demo.py   # corroboração com observações do simulador
```

- As contas são criadas no arranque (`auto_register`); qualquer palavra-passe serve num servidor acabado de iniciar. Não guardar palavras-passe em ficheiros versionados.
- `spade run` sem opções também funciona; cria `server.db` na pasta atual, que o Git ignora.
- `verification_demo.py` termina com a decisão `request_mobile_verification`: a observação `obs-000001` é corroborada por `obs-000002`, de `sensor_02`.
- Com `--xmpp`, o relatório traz `messages` vazio: a transcrição só existe no transporte local. A repetição (`scripts/replay.py`) funciona na mesma, porque lê a `timeline`.
- Os cinco agentes do MVP correm no mesmo processo e o SPADE entrega as mensagens diretamente entre eles. Este modo mostra a ligação e o registo no servidor; **não prova o transporte pela rede**. As falhas (`--faults`) só se injetam no transporte local.

## Mapa 2D e relógio da simulação

O simulador corre sozinho, sem SPADE nem servidor:

```bash
python -m isia.simulation config/environment.json --steps 3 --step-seconds 0.5 --output /tmp/execucao.json
```

Mostra a grelha, os instantes e as observações de cada fonte. O ficheiro de `--output` não pode existir. Sem `--output`, grava em `results/simulation/run-*/run.json`, que o Git ignora.

- **Mapa:** grelha de células inteiras, origem `(0, 0)` no canto inferior esquerdo, sem obstáculos nem escala física. O MVP usa 8 × 8; [config/environment.json](config/environment.json) usa 12 × 10.
- **Relógio:** tempo simulado em segundos, que só avança por ordem explícita. Os prazos de espera por mensagens usam tempo real.
- **Movimento:** primeiro em x, depois em y, uma célula por segundo simulado; cada célula gasta um ponto percentual de energia.
- **Eventos:** `threat` emite nos três canais, `thunder` só no acústico e `tourist` no visual e no humano. Sem evento não há falso alerta.
- **Verdade de referência:** os agentes recebem apenas as observações da sua fonte; só a avaliação consulta os eventos reais.
- **Reprodução:** a mesma configuração, semente e sequência de avanços dão as mesmas observações.

Parâmetros de cada fonte, em `sources` do ficheiro de cenário:

| Parâmetro | Efeito |
|---|---|
| `kind` | `acoustic`, `visual` ou `human` |
| `detection_range` | Distância euclidiana máxima, inclusiva, em células |
| `sensitivity` | Probabilidade base de captar o sinal, entre 0 e 1 |
| `false_negative_rate` | Falha adicional perante uma ameaça: deteta com `sensitivity × (1 − false_negative_rate)` |
| `false_positive_rate` | Confusão de um evento benigno com um sinal suspeito: `sensitivity × false_positive_rate` |
| `position_error` | Desvio inteiro máximo por eixo, limitado às bordas do mapa |
| `confidence` | Pontuação fixa declarada pela fonte; não é a verdade do evento |

Estes valores são um modelo simplificado, sem calibração empírica.

## Limites conhecidos

- **Transporte:** todas as medições usam o transporte local. O XMPP só foi exercitado com os agentes no mesmo processo; os atrasos reais na rede não foram medidos.
- **Amostras pequenas:** 10 a 20 repetições por caso, sem intervalos de confiança.
- **Pontuações:** os limiares (0,25 para a patrulha, 0,65 para o guarda) são pontuações de engenharia, não probabilidades calibradas.
- **Mundo dos cenários A, B e C:** dois sensores e uma ocorrência por janela. Várias ameaças, fila, prioridade e informadores humanos existem como opções, medidas nos testes de stress e nos cenários D e E. As ameaças começam todas em `t = 0`.
- **Cenários D e E:** variam de execução para execução (ver acima).
- **Cópia sem `.git`** (por exemplo, um ZIP do GitHub): o MVP, a repetição e os scripts de `scripts/` funcionam; o coletor recusa correr; a suite corre 551 testes e termina com 4 erros e 4 `skipped`. Os erros são dos testes da sensibilidade, que chamam o Git. **Entregar com o histórico:** `git bundle create isia.bundle --all` ou um ZIP do clone com a pasta `.git`.
- **Sensibilidade:** só `summary.csv` e `completion-manifest.json` estão versionados em `results/sensitivity/`; os relatórios por execução ficaram fora do repositório.

**Por fazer antes da entrega** ([delivery-todo.md](docs/delivery-todo.md)): um colega seguir este README numa máquina limpa; exportar os diapositivos para PDF em `docs/presentation/`; preencher a [ata](docs/approvals.md) (13 de 16 linhas por aprovar); preparar o pacote com `.git`.

## Requisitos e fontes

**Enunciado:** Tema C e instruções gerais de `ISIA 2026-2027 - Assignment 1 - Theme suggestions [simple].pdf` (não publicado neste repositório).

| Entregável pedido | Onde está |
|---|---|
| Código SPADE com instruções para correr | `src/`, este README |
| Documentação: justificação, agentes, mensagens, protocolos | [architecture.md](docs/architecture.md), [protocols.md](docs/protocols.md) |
| Relatório de desempenho com pelo menos três cenários | [experiments.md](docs/experiments.md) (A, B e C), [scalability.md](docs/scalability.md), [sensitivity.md](docs/sensitivity.md) |
| Visualização ou demonstração; apresentação | `scripts/replay.py`, [results/demo/](results/demo/), [roteiro](docs/presentation/roteiro.md) |
| Testes e scripts para reproduzir (opcional) | `tests/`, `scripts/` |

**Dependências:** Python 3.12, SPADE 4.1.4, pyjabber 0.4.5 e SQLAlchemy 2.1.8 ([requirements.txt](requirements.txt)); Git para o coletor.

**Referências:** [SPADE](https://spade-mas.readthedocs.io/), [FIPA](http://www.fipa.org/), Wooldridge (*An Introduction to MultiAgent Systems*, 2009), Russell e Norvig (*Artificial Intelligence: A Modern Approach*, 4.ª ed.), [Gaia (Wooldridge, Jennings e Kinny, 2000)](https://link.springer.com/article/10.1023/A:1010071910869) e os diapositivos da UC (`ISIA_0` a `ISIA_3`, não publicados aqui).

As fórmulas, os limiares, o mapa 2D e o Contract Net simplificado são **propostas de engenharia** do grupo, não exigências literais do enunciado.
