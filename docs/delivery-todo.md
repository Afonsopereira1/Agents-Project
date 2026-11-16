# Pendentes para a entrega — complemento ao plano (Blocos A a E)

> **Lista de acompanhamento (criada em 2026-11-16).** `- [ ]` indica trabalho pendente; `- [x]` exige evidência verificada. As linhas citadas referem-se à `main` em `81a09e8`.

[README](../README.md) · [Plano](development-plan.md) · [Arquitetura](architecture.md) · [Protocolos](protocols.md) · [Experiências](experiments.md)

## Para que serve este documento

- **O que é:** a lista do que falta para entregar o projeto completo.
- **Relação com o plano:** complementa o [plano de desenvolvimento](development-plan.md), não o substitui. Só inclui trabalho que **não está** no plano ou que lá está mal definido; estas últimas tarefas aparecem como «Ajuste à Etapa X».
- **Organização:** os Blocos A, B e C respondem às três questões de análise abaixo; o Bloco D cobre os entregáveis do enunciado (demonstração, apresentação, README); o Bloco E fecha as caixas pendentes do plano. O Bloco F, no fim, reúne testes de stress opcionais.
- **Porquê agora:** parte da análise destas questões existe apenas em notas locais, fora do Git. A lista indica o que passar para a documentação versionada.
- **Como usar:** cada elemento escolhe uma tarefa `- [ ]`, executa-a e assinala-a com a evidência. O trabalho opcional só começa depois de fechados os obrigatórios.
- **Quando termina:** quando a [checklist de marcos](#checklist-de-marcos) estiver completa. Nessa altura o documento passa a registo histórico.

## Questões de análise

- **P1.** Como são construídos os agentes?
- **P2.** Que protocolos são usados? Porquê esta arquitetura e não outras? Prós e contras?
- **P3.** Escalabilidade computacional (limites C1–C8 da [Etapa 9A](development-plan.md#etapa-9a--escalabilidade-computacional-e-situacional)) e situacional (distribuição de recursos e caçadores).

## Regras de progressão

- Trabalho **obrigatório** estimado: cerca de **17 h** no total. O trabalho **opcional** só começa depois de os obrigatórios estarem fechados.
- Cada tarefa tem o porquê numa frase. Sem porquê, não entra.
- Não inventar resultados: o que não foi medido fica escrito como «não medido».
- A análise das três questões está hoje em `temp/perguntas-defesa.md`, um ficheiro local que o Git ignora. Tudo o que for necessário à entrega tem de passar para um caminho versionado.

## Verificação de partida (16-11-2026)

- Na `main` (`81a09e8`), a suite completa passou **489 testes, OK**, em cerca de 58 s. Só passa dentro de um repositório Git.
- Os scripts locais `temp/scale.py` e `temp/dist.py` correram sem alterações e reproduziram as contagens de P3: 15 mensagens por execução completa (média 12,4), 8/10, 8/20 e 8/30 caçadores atendidos, 0/10 alertas em (7,0) e 13/20 contra 9/20 com 10 % de perda.
- Com o drone silencioso, dez execuções passaram de 1,5 s para 5,5 s reais. O fator depende da máquina; reportar os dois tempos.
- O modo `--xmpp` foi executado só na base anterior ao PR #18: terminou `closed`, com `messages` vazio, porque a transcrição só existe no transporte local.
- A recolha das 560 execuções da Etapa 9 não foi repetida nesta verificação.

## Dependências gerais

```mermaid
flowchart LR
  C[C Escalabilidade P3] --> D[D Entregáveis]
  A[A Agentes P1] --> D
  B[B Protocolos P2] --> D
  E[E Fecho do plano] --> D
```

Os Blocos A, B, C e E podem decorrer em paralelo. O Bloco D depende deles para os diapositivos.

---

## Bloco A — P1: construção dos agentes

**Objetivo:** tornar visível na entrega como os agentes são construídos, com a descrição igual ao código.

**Pré-requisitos:** `main` atualizada; acesso a `temp/perguntas-defesa.md` (secções P1.2 a P1.5).

**Ficheiros envolvidos:** `docs/architecture.md`, `temp/perguntas-defesa.md`, `docs/presentation/`.

**Tarefas concretas:**

- [x] **Ajuste à Etapa 10: reescrever a secção 3 de `architecture.md` com o conteúdo de P1.2–P1.5** (obrigatório, ~1,5 h) — a secção atual descreve uma proposta que o código não tem (drone que «anuncia disponibilidade», sensor com «lista de vizinhos»). Ver [architecture.md:60](architecture.md#L60). **Feito:** [secção 3](architecture.md#3-como-os-agentes-são-construídos) com as três camadas, a tabela agente/comportamentos/código, as sete decisões e a autonomia; cada `ficheiro:linha` conferido em `89c08a7`. O título deixou de dizer «proposta».
- [x] **Corrigir as linhas e os números da Parte 0** (obrigatório, ~0,5 h) — as ligações a `incident.py`, `runner.py` e `reputation.py` deslocaram-se com o PR #18, e «421 testes em 12 s» passou a 489 em cerca de 58 s. **Feito** em `temp/perguntas-defesa.md` (local): 29 ligações conferidas; suite reexecutada a 16-11-2026: 489 testes, OK, 57,9 s.
- [x] **Fazer um diapositivo de P1** (obrigatório, ~1 h) — a construção dos agentes deve poder ser explicada em 30 segundos. **Feito:** conteúdo em [presentation/p1-agentes.md](presentation/p1-agentes.md), com as três ligações de autonomia; formato final no Bloco D.
- [x] **Declarar que `InformantAgent` corre como `sensor-2` visual** (obrigatório, ~0,25 h) — o enunciado pede informadores e nenhum cenário medido tem fonte `human`. Ver [architecture.md:70](architecture.md#L70). **Feito:** nota e tabela de instâncias na [secção 3.2](architecture.md#instâncias-usadas-nas-execuções-medidas).

**Evidência disponível:** comportamentos em [sensor.py:129](../src/isia/agents/sensor.py#L129), [informant.py:66](../src/isia/agents/informant.py#L66) e [mobile.py:137](../src/isia/agents/mobile.py#L137), [:195](../src/isia/agents/mobile.py#L195), [:285](../src/isia/agents/mobile.py#L285). Autonomia do recurso em [mobile.py:103](../src/isia/agents/mobile.py#L103) (decide localmente), [mobile.py:115](../src/isia/agents/mobile.py#L115) (energia de ida e volta) e [incident.py:190](../src/isia/agents/incident.py#L190) (pode recusar a reserva depois do `ACCEPT`).

**Dependências:** nenhuma. Alimenta o Bloco D.

**Testes a realizar:** abrir cada ligação `ficheiro:linha` e confirmar que aponta para o código descrito; correr a suite e conferir o número de testes citado.

**Critérios de conclusão:** `architecture.md` contém as três camadas, a tabela agente/comportamentos/código e as sete decisões, sem a palavra «proposta»; o diapositivo mostra as três ligações de autonomia.

**Resultado esperado:** quem lê a entrega encontra a resposta a P1 na documentação versionada e nos diapositivos.

**Erros prováveis/diagnóstico:** copiar linhas da base antiga; descrever o informador como fonte humana quando os cenários A, B e C só têm fontes acústica e visual.

---

## Bloco B — P2: protocolos e arquitetura

**Objetivo:** tornar visível porquê esta arquitetura e estes protocolos, com alternativas, prós e contras.

**Pré-requisitos:** `main` atualizada; acesso a `temp/perguntas-defesa.md` (secções P2.2, P2.3 e P2.5).

**Ficheiros envolvidos:** `docs/protocols.md`, `docs/architecture.md`, `docs/evaluation.md`, `docs/presentation/`.

**Tarefas concretas:**

- [x] **Ajuste à Etapa 10: copiar as tabelas de alternativas (P2.2, P2.3, P2.5) para os documentos versionados** (obrigatório, ~1,5 h) — «porquê não outras» só tem resposta num ficheiro que o Git ignora. A versão atual tem quatro linhas em [architecture.md:196](architecture.md#L196). **Feito:** P2.2 e P2.3 em [protocols.md, secção 9](protocols.md#9-porquê-estes-protocolos-alternativas-prós-e-contras); P2.5 em [architecture.md](architecture.md#porquê-b1-e-não-outras-arquiteturas-do-sistema).
- [x] **Corrigir `protocols.md`: `refuse` contra `reject-proposal`, e `ALERT`/`INCIDENT_CLOSED` não enviados** (obrigatório, ~0,5 h) — o diagrama diz `refuse` ([protocols.md:245](protocols.md#L245)), mas o código envia `reject-proposal` ([mobile.py:256](../src/isia/agents/mobile.py#L256)). É um desvio do FIPA fácil de detetar. A tabela de tipos atribui destinatários a mensagens que só ficam no registo local ([protocols.md:160](protocols.md#L160)). **Feito:** tabela da secção 3 com a performativa enviada e a linha do código; diagramas das secções 4 e 5 sem `refuse`; desvios ao FIPA na secção 9.
- [x] **Reescrever «várias ocorrências em paralelo» como «o desenho permite; não medido»** (obrigatório, ~0,25 h) — é a principal vantagem alegada da abordagem B1 e nenhuma execução tem mais de um iniciador. Ver [evaluation.md:126](evaluation.md#L126). **Feito** aí e na tabela B1 de `architecture.md`.
- [x] **Fazer um diapositivo de P2 com dois contras medidos** (obrigatório, ~1 h) — prós e contras com números convencem mais do que a tabela teórica. **Feito:** conteúdo em [presentation/p2-protocolos.md](presentation/p2-protocolos.md) (espera 1,5 → 5,5 s; recall 0,80 → 0,65); formato final no Bloco D.

**Evidência disponível:** em [experiments.md:98](experiments.md#L98), a reputação mudou uma decisão em 560 execuções; no cenário B, a comparação `full`/`no_corroboration` dá FPR de 0,25 contra 0,75 e recall de 0,65 contra 0,80.

**Dependências:** nenhuma. Alimenta o Bloco D.

**Testes a realizar:** comparar cada performativa do diagrama com a que os agentes enviam; confirmar que nenhum texto afirma paralelismo medido.

**Critérios de conclusão:** os documentos têm as três tabelas com prós, contras e escolha; o diagrama coincide com o código e o desvio do FIPA está escrito como decisão; `protocols.md` deixa de se intitular «proposta».

**Resultado esperado:** resposta a P2 apoiada em código, medições e alternativas descartadas.

**Erros prováveis/diagnóstico:** alterar a performativa no código em vez de documentar o desvio (obriga a mexer em templates e testes); apresentar vantagens do desenho como resultados.

---

## Bloco C — P3: escalabilidade

**Objetivo:** tornar as medições de P3 reproduzíveis por quem recebe a entrega e fechar a Etapa 9A com limites explícitos.

**Pré-requisitos:** Etapa 9; scripts locais `temp/scale.py` e `temp/dist.py`.

**Ficheiros envolvidos:** `scripts/` (novo), `results/scalability/` (novo), `docs/scalability.md` (novo), `docs/development-plan.md`, `temp/perguntas-defesa.md`, `docs/presentation/`.

**Tarefas concretas:**

- [x] **Ajuste à Etapa 9A (tarefa 1): mover os scripts para `scripts/`, gravar CSV e criar `docs/scalability.md`** (obrigatório, ~2 h) — a tarefa do plano não diz para onde nem em que formato. Ver [development-plan.md:545](development-plan.md#L545). **Evidência:** [scripts/](../scripts/), [results/scalability/](../results/scalability/), [scalability.md](scalability.md); corridos num clone limpo a 16-11-2026.
- [x] **Ajuste à Etapa 9A: fechar a etapa com uma tabela C1–C8 «medido / proposto / adiado»** (obrigatório, ~0,5 h) — as oito tarefas atuais pedem C6, C7 e fila por gravidade; com esse âmbito a etapa não fecha. A métrica por caçador conta como feita pela função `attended()` do script de distribuição. **Evidência:** [scalability.md#estado-de-c1c8](scalability.md#estado-de-c1c8); Etapa 9A assinalada no plano.
- [x] **Corrigir três afirmações de P3** (obrigatório, ~0,5 h) — C1 diz que o iniciador conhece a posição base, mas `candidates` só tem `{jid: resource_id}` ([runner.py:165](../src/isia/simulation/runner.py#L165)); o fator «3,4×» varia com a máquina; «menos recursos só prejudica com falhas» é forte demais para 20 repetições. **Evidência:** secção «Correções a afirmações anteriores» de [scalability.md](scalability.md), plano e `temp/perguntas-defesa.md`.
- [x] **Fazer um diapositivo de P3** (obrigatório, ~1 h) — é a questão com mais medições e estas têm de aparecer. **Evidência:** [presentation/p3-escalabilidade.md](presentation/p3-escalabilidade.md) (conteúdo; o formato final dos diapositivos é decidido no Bloco D).

**Estado proposto para C1–C8:**

| Ref. | Estado | Justificação |
|---|---|---|
| C2, C7 | Medido | Espera de 1,5 s para 5,5 s; 8/10, 8/20 e 8/30 atendidos |
| C1, C4 | Proposto | C1 sozinho não muda nada: com duas patrulhas e K ≥ 2, o «antes» é igual ao «depois». Só com C4 |
| C5 | Proposto | O feed é lido uma vez por execução; o ganho não é mensurável no sistema |
| C6 | Proposto | Um único par fixo de corroboração ([runner.py:135](../src/isia/simulation/runner.py#L135)) |
| C8 (reputação) | Proposto | Pelo menos quatro testes usam `book.history`; o crescimento de memória não foi medido |
| C3, C8 (processos) | Adiado | Mudanças grandes; trabalho futuro |

**Dependências:** Etapa 9. Fecha a Etapa 9A e alimenta o Bloco D.

**Testes a realizar:** correr os scripts a partir de um clone limpo; comparar o CSV gerado com a verificação de 16-11-2026.

**Critérios de conclusão:** `PYTHONPATH=src python scripts/dist.py` corre num clone limpo e grava `results/scalability/dist.csv`; a Etapa 9A fica assinalada com adiamentos justificados; o diapositivo mostra a tabela C1–C8, o mapa com o ponto cego (7,0) e a série 8/10, 8/20, 8/30.

**Resultado esperado:** resposta a P3 com referência reproduzível e limites assumidos, medidos e com proposta.

**Erros prováveis/diagnóstico:** caminhos relativos a `temp/` nos scripts; apresentar o fator de lentidão como constante; implementar C1 sem C4 e não obter diferença.

---

## Bloco D — Entregáveis oficiais

**Objetivo:** cobrir os entregáveis do enunciado que faltam: visualização ou demonstração gravada, apresentação e instruções de execução.

**Pré-requisitos:** Blocos A, B e C para o conteúdo dos diapositivos; relatório JSON do `run_mvp`.

**Ficheiros envolvidos:** `scripts/replay.py` (novo), `docs/presentation/` (novo), `README.md`, `src/isia/evaluation/collector.py`, `results/experiments/summary.csv`.

**Estado dos entregáveis (16-11-2026):**

| Entregável | Estado | Falta |
|---|---|---|
| Código SPADE com instruções | Parcial | Estado antigo em [README.md:6](../README.md#L6); sem comando dos cenários nem de P3 |
| Documentação | Parcial | Justificação com alternativas; agentes descritos como estão no código |
| Relatório de desempenho | Pronto | Gráficos (opcional) |
| Visualização/demonstração e diapositivos | Em falta | Tudo |
| Testes e scripts (opcional) | Pronto | Scripts de P3 versionados |

**Tarefas concretas:**

- [x] **Ajuste à Etapa 10: fazer a visualização como repetição do relatório JSON, em `scripts/replay.py`** (obrigatório, ~3 h) — é a opção mais barata que mostra interações e métricas; o plano previa um módulo ao vivo ([development-plan.md:572](development-plan.md#L572)). Ler a `timeline` e não `messages`, que vem vazio em XMPP. **Feito:** [scripts/replay.py](../scripts/replay.py) lê só a `timeline` (aceita também `results/experiments/runs/*.json`); gravação em [results/demo/](../results/demo/) (`script`/`scriptreplay`, sem dependências novas).
- [x] **Ajuste à Etapa 10: fixar o roteiro da apresentação** (obrigatório, ~2 h) — o plano só diz «inserir dados na apresentação» ([development-plan.md:578](development-plan.md#L578)); sem roteiro, as três questões de análise ficam dispersas entre os resultados. **Feito:** [presentation/roteiro.md](presentation/roteiro.md), 12 diapositivos com a fonte de cada número.
- [x] **Ajuste à Etapa 10: pôr no topo do README os comandos por ordem** (obrigatório, ~1 h) — o estado é de 12-11-2026 e as contagens de testes são antigas ([README.md:172](../README.md#L172)). **Feito:** secção [Comandos por ordem](../README.md#comandos-por-ordem), com estado de 16-11-2026.
- [x] **Testar a entrega sem a pasta `.git`** (obrigatório, ~0,5 h) — numa cópia sem Git, o coletor recusa correr e sete testes falham. **Feito:** o coletor continua a exigir Git (proveniência); os 4 testes que dependem dele (as 7 falhas contavam subtestes) passam a `skipped` com a razão, e o README manda entregar com `.git` ou `git bundle`. Verificado a 16-11-2026: com `.git`, 489 testes OK; cópia sem `.git`, 489 OK (`skipped=4`).
- [ ] **Gerar dois gráficos a partir de `summary.csv`** (opcional, ~2 h) — precision, recall e FPR por cenário leem-se melhor em gráfico do que numa tabela de doze linhas.

**Opções de visualização comparadas:**

| Opção | Esforço | Mostra |
|---|---|---|
| **A. Repetição no terminal a partir do JSON, gravada (recomendada)** | ~3 h, sem dependências | Grelha, mensagens por segundo, métricas finais |
| B. Gráficos e grelha animada em matplotlib | ~5–6 h, dependência nova | O mesmo, com melhor aspeto |
| C. Interface gráfica ou painel ao vivo | 10 h ou mais | Interativo; risco de bloquear o SPADE |

**Dependências:** Blocos A, B e C. Substitui a forma de cumprir as tarefas de visualização da Etapa 10.

**Testes a realizar:** um colega instala, testa, corre o MVP, os cenários, P3 e a repetição seguindo apenas o README; extrair a entrega para uma pasta sem Git e repetir.

**Critérios de conclusão:** existe uma gravação da repetição; a apresentação segue P1, P2, P3, resultados A/B/C, demonstração e limites, em cerca de doze diapositivos; o README indica se é preciso entregar o clone com `.git`.

**Resultado esperado:** entregáveis do enunciado cobertos com o mínimo de código novo.

**Erros prováveis/diagnóstico:** visualizador que toma decisões pelos agentes (a repetição evita-o, porque só lê o relatório); entrega em ZIP sem Git; gráficos com dados que não vêm de `results/`.

---

## Bloco E — Fecho do plano

**Objetivo:** fechar as caixas do plano que só dependem de aprovação e alinhar a proveniência dos resultados.

**Pré-requisitos:** os três elementos disponíveis durante 15 minutos.

**Ficheiros envolvidos:** `docs/development-plan.md`, `results/experiments/manifest.json`.

**Tarefas concretas:**

- [ ] **Ajuste às Etapas 0, 1 e 7: aprovar parâmetros e contratos numa reunião de 15 minutos** (obrigatório, ~0,25 h) — as caixas das Etapas 0–1, 4–5 e 7 só dependem dessa aprovação. Ver [development-plan.md:49](development-plan.md#L49), [:91](development-plan.md#L91) e [:341](development-plan.md#L341).
- [ ] **Ajuste à Etapa 9: corrigir a caixa «tabelas/gráficos»** (obrigatório, ~0,1 h) — está assinalada como feita ([development-plan.md:455](development-plan.md#L455)), mas não há gráficos ([:464](development-plan.md#L464)).
- [ ] **Repetir a recolha das 560 execuções na `main`** (opcional, ~0,5 h) — o `manifest.json` cita o commit `667cba2`, anterior ao PR #18.

**Dependências:** nenhuma.

**Testes a realizar:** conferir a checklist de marcos do plano; se a recolha for repetida, comparar `summary.csv` com o publicado.

**Critérios de conclusão:** na checklist de marcos só ficam por fechar a Etapa 9A e a Etapa 10.

**Resultado esperado:** plano coerente com o estado real do trabalho.

**Erros prováveis/diagnóstico:** assinalar aprovações sem as registar; substituir resultados publicados sem guardar o commit e o estado `dirty`.

---

## O que não fazer antes da entrega

- **C5 (pesquisa binária no feed)** — sem efeito mensurável; fica como proposta de duas linhas.
- **C8, histórico da reputação em JSONL** — parte testes e não resolve nada que tenha sido medido.
- **C2, C3, C6, C7, processos separados, qualquer sensor a iniciar, fila por gravidade** — mudanças grandes; ficam como limite medido, com proposta. Medir duas ocorrências em paralelo é diferente: está como opcional no [Bloco F](#bloco-f--testes-de-stress-opcional).
- **Trocar `reject-proposal` por `refuse` no código** — mexe em templates e testes; basta documentar.
- **Interface gráfica ou painel interativo** — 10 h ou mais, e o enunciado aceita demonstração gravada.
- **Mais repetições, intervalos de confiança, reescrever `message-contract.md`, PyDoc em HTML** — ninguém pediu; basta declarar o limite.

## Checklist de marcos

- [x] Bloco A: P1 respondida na documentação versionada e num diapositivo.
- [x] Bloco B: P2 respondida com alternativas, prós e contras, e diagrama igual ao código.
- [x] Bloco C: P3 reproduzível a partir de `scripts/` e Etapa 9A fechada com adiamentos justificados.
- [ ] Bloco D: repetição gravada, apresentação e README finais. Feito: repetição, roteiro, README e teste sem `.git`. Falta: os diapositivos em si e o teste de um colega a seguir só o README.
- [ ] Bloco E: aprovações registadas e plano coerente.

---

## Bloco F — Testes de stress (opcional)

**Objetivo:** levar o sistema aos limites em várias dimensões e trocar «o desenho permite» por números.

**Pré-requisitos:** Blocos A a E fechados; Bloco C com os scripts em `scripts/`, que servem de modelo.

**Ficheiros envolvidos:** `scripts/stress_*.py` (novos), `results/stress/` (novo), `docs/scalability.md`, `src/isia/simulation/runner.py` (só no grupo F2).

**Regra:** cada teste grava um CSV em `results/stress/` e uma linha em `docs/scalability.md` com o ponto onde o sistema deixa de atender. Sem CSV, o teste não conta como feito.

### F1 — Sem código novo (só parâmetros de `faults` e `scenario`)

Os parâmetros já existem e estão validados em [runner.py:36](../src/isia/simulation/runner.py#L36) e [faults.md](faults.md). Cada teste é um ciclo sobre `run_mvp`.

- [ ] **Curva de perda** (opcional, ~1 h) — `loss` em 0; 0,1; 0,2; 0,3; 0,5, com 20 repetições cada. Medir atendidas, `unresolved` e mensagens perdidas. Hoje só existe o ponto de 10 % (13/20 contra 9/20).
- [ ] **Curva de latência** (opcional, ~1 h) — `delay` de 0,1 s a 1,0 s em `PROPOSAL` e depois em `STATUS`, à volta do `receive_timeout` de 0,5 s ([runner.py:166](../src/isia/simulation/runner.py#L166)). Medir onde passa a `no_eligible_proposals` ou `confirmation_unknown`. Mostra se o prazo fixo é frágil.
- [ ] **Recursos a cair em cascata** (opcional, ~0,5 h) — `unavailable_agents` com `drone`, depois `drone`+`vehicle`, depois `ranger`. Medir estados finais e tempo real. Mostra como o sistema degrada com menos recursos, e não só quanto demora.
- [ ] **Escassez de autonomia** (opcional, ~1 h) — `autonomy_percent` do drone e do veículo de 100 a 10. Medir recusas (`REJECT`), quem ganha e ocorrências sem proposta. Confirma que a decisão local de recusar funciona sob pressão.
- [ ] **Falhas combinadas** (opcional, ~1 h) — `loss` 0,2 com `duplicate` em `MISSION_RESULT` e `occupied_after_proposal` no drone, tudo na mesma execução. Medir se alguma vez há duas missões no mesmo recurso ou um incidente fechado duas vezes. Hoje cada falha só foi testada sozinha.

### F2 — Com código novo no runner

- [ ] **Duas ocorrências em paralelo** (opcional, ~5 h) — um segundo `IncidentSensorAgent` (hoje só existe um, em [runner.py:132](../src/isia/simulation/runner.py#L132)) e duas ameaças simultâneas em zonas diferentes, a disputar os mesmos recursos. Medir:
  - duplas reservas: tem de dar zero;
  - renegociações causadas pelo `STATUS`;
  - tempo de resolução com duas ocorrências contra uma.

  Mede a principal vantagem alegada da B1 e a condição de corrida que justifica o `STATUS`.
- [ ] **Rajada de ocorrências** (opcional, ~2 h, depois da anterior) — 2, 4 e 8 ameaças no mesmo instante. Medir quantas são atendidas e quantas ficam `no_eligible_proposals`. Encontra o ponto de saturação dos três recursos.
- [ ] **Mensagens inválidas em massa** (opcional, ~1,5 h) — enviar ao iniciador e aos recursos uma rajada de JSON malformado, IDs trocados e respostas fora de prazo, a meio de uma negociação. Medir se o resultado da negociação legítima se mantém e se algum agente termina com exceção. A validação já existe; falta prová-la sob carga.
- [ ] **Execução longa** (opcional, ~1 h) — 1000 execuções seguidas com a mesma reputação. Medir a memória do processo e o tamanho de `book.history`. Dá o número que falta ao C8 (reputação), hoje «não medido».
- [ ] **Implementar C4 mínimo e C1 e medir mensagens em função de N** (opcional, ~5 h) — é a única correção com «antes e depois» visível. Ver [runner.py:80](../src/isia/simulation/runner.py#L80), [:148](../src/isia/simulation/runner.py#L148), [:165](../src/isia/simulation/runner.py#L165) e [incident.py:128](../src/isia/agents/incident.py#L128).

**Dependências:** F1 depende só do Bloco C. F2 depende de F1 para reutilizar os scripts.

**Testes a realizar:** cada script corre num clone limpo e grava o CSV; repetir uma vez com a mesma semente e conferir que o CSV é igual (a perda depende da ordem do `asyncio`, por isso registar a diferença, se houver).

**Critérios de conclusão:** pelo menos as cinco curvas de F1 em `results/stress/` e resumidas em `docs/scalability.md`; F2 só se houver tempo.

**Resultado esperado:** um mapa de limites («até X % de perda atende Y de 20; a partir de Z s de atraso, deixa de negociar») para a defesa.

**Erros prováveis/diagnóstico:** varrer valores sem repetições e ler ruído como efeito; aumentar o `receive_timeout` para «passar» o teste em vez de reportar o limite; em F2, ter um despachante escondido no runner a escolher qual iniciador trata cada ameaça.

---

## Pendentes deixados pelo Bloco D

O que ficou por fazer ou por verificar depois das quatro tarefas obrigatórias do Bloco D (16-11-2026).

- [ ] **Fazer os diapositivos a partir do [roteiro](presentation/roteiro.md)** (obrigatório, ~3 h) — só existe o roteiro e o conteúdo de P1–P3; o marco do Bloco D não fecha sem a apresentação.
- [ ] **Um colega segue só o README, numa máquina limpa** (obrigatório, ~0,5 h) — é o teste de aceitação do Bloco D: instalar, testar, correr o MVP, a repetição, os cenários e P3 sem ajuda.
- [ ] **Gravar vídeo da demonstração** (opcional, ~0,25 h) — a gravação versionada é de terminal (`scriptreplay`); se a apresentação precisar de vídeo, correr o `scriptreplay` com um gravador de ecrã.
- [ ] **Gerar dois gráficos a partir de `summary.csv`** (opcional, ~2 h) — a mesma tarefa do [Bloco D](#bloco-d--entregáveis-oficiais); só depois do Bloco E.
- [ ] **Correr `scripts/replay.py` sobre um relatório `--xmpp`** (opcional, ~0,25 h) — o visualizador foi feito para não depender de `messages`, mas só foi testado com o transporte local.
- [ ] **Ler o mapa e os sensores do relatório em `scripts/replay.py`** (opcional, ~0,5 h) — hoje estão fixos (8×8, sensores em (2,2) e (4,2)), como no runner; só é preciso se o runner os passar a variar.
