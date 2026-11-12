# ISIA — Tema C: Monitorização descentralizada da vida selvagem

**Unidade curricular:** Introdução aos Sistemas Inteligentes e Autónomos (2026/2027) — Assignment 1  
**Tema:** *Decentralised Wildlife Monitoring and Anti-Poaching Patrols*

> **Estado (12-11-2026):** Etapa 6 integrada na `main` pelos PRs #12 e #13. Esta branch inclui essa base e adapta a reputação e a política da Etapa 7 ao ciclo existente. A integração foi testada com transporte local dos comportamentos SPADE. A aprendizagem automática a partir das missões, as Etapas 8–10 e as aprovações formais continuam pendentes. Ver [reputação e limites](docs/reputation-policy.md).

## O projeto

Vamos simular uma reserva onde sensores e informadores detetam atividade suspeita e **corroboram evidências**. Drones, veículos e rangers podem propor e executar missões, sem despachante central. Na **abordagem B1**, cada ocorrência tem um iniciador local temporário; os outros agentes decidem autonomamente se colaboram. Utilizaremos **SPADE (Python/XMPP)**.

O simulador mantém a verdade dos acontecimentos apenas para avaliação; os agentes recebem observações imperfeitas e mensagens.

## Onde encontrar cada coisa?

| Preciso de… | Ficheiro |
|---|---|
| Objetivos e ideias originais do colega | [requirements.md](requirements.md) |
| **Tarefas e ordem de implementação (Etapas 0–10)** | [docs/development-plan.md](docs/development-plan.md) |
| Arquitetura, agentes, algoritmos e decisões pendentes | [docs/architecture.md](docs/architecture.md) |
| Mensagens e protocolos de comunicação | [docs/protocols.md](docs/protocols.md) |
| Testes, métricas e três cenários | [docs/evaluation.md](docs/evaluation.md) |
| Demonstração Contract Net da Etapa 5 | [contract_net_demo.py](contract_net_demo.py) |
| MVP completo da Etapa 6 | [runner.py](src/isia/simulation/runner.py) |
| Política da Etapa 7 e limites da aprendizagem | [docs/reputation-policy.md](docs/reputation-policy.md) |
| Organização flexível dos colegas | [docs/team-tasks.md](docs/team-tasks.md) e [Issues](https://github.com/Afonsopereira1/Agents-Project/issues) |

**MVP implementado:** ocorrência → observação → evidências → avaliação → propostas de recursos → missão → resultado. O MVP não substitui os requisitos da entrega final.

## Requisitos e fontes

**Enunciado oficial** — `ISIA 2026-2027 - Assignment 1 - Theme suggestions [simple].pdf`:
- **Tema C, p. 1:** deteção de ameaças, corroboração e coordenação descentralizada de patrulhas/respostas comunitárias.
- **Instruções gerais, p. 4:** SPADE; decisões justificadas sobre agentes, mensagens, protocolos, confiança e falhas; pelo menos **três cenários contrastantes**; métricas e limitações; código com instruções, documentação, relatório, visualização ou gravação, apresentação. Testes automatizados surgem como opcionais, mas são recomendáveis.

**Materiais oficiais da cadeira** (PDF fornecidos no âmbito da UC; não publicados neste repositório):
- `ISIA_0 (2026-27).pdf` — enquadramento, ferramentas e datas;
- `ISIA_1 - Agent-based Computing.pdf` — conceitos de agentes e MAS;
- `ISIA_2 - Intelligent Agents.pdf` — arquiteturas reativas, deliberativas e híbridas;
- `ISIA_3 - Multi-Agent Systems.pdf` — comunicação FIPA-ACL, coordenação e Contract Net.

**Referências técnicas e teóricas essenciais:** [SPADE](https://spade-mas.readthedocs.io/), [GitHub SPADE](https://github.com/javipalanca/spade), [FIPA](http://www.fipa.org/), [GitHub Docs](https://docs.github.com/en/), Wooldridge (*An Introduction to MultiAgent Systems*, 2009), Russell e Norvig (*Artificial Intelligence: A Modern Approach*, 4.ª ed.), [Gaia (Wooldridge, Jennings e Kinny, 2000)](https://link.springer.com/article/10.1023/A:1010071910869).

**Nota:** as fórmulas, os limiares de confiança, o mapa 2D e o protocolo Contract Net simplificado são **propostas de engenharia**, não exigências literais do enunciado.

## Executar o projeto

### MVP da Etapa 6

Depois de preparar e ativar o ambiente Python indicado abaixo, executar sem
servidor. Pode ser usado outro ambiente existente com Python 3.12 e as
dependências de `requirements.txt`; `python` e `spade` devem pertencer a esse
mesmo ambiente ativo.

```bash
PYTHONPATH=src python -m isia.simulation.runner > /tmp/isia-mvp.json
PYTHONPATH=src python -m unittest discover -s tests/scenarios -v
```

O JSON contém mensagens, linha temporal, missões, resultados e recursos finais.
Esperado: `incident_status: "closed"`, resultados de `drone` e `ranger`, todas
as reservas `null` e todos os recursos `available`. O drone regressa a `(0, 2)`
com 94% de energia; o guarda regressa a `(5, 5)` com 90%. O veículo apresentou
uma proposta, mas não foi escolhido e conserva 100%.

Para injetar perdas, atrasos, duplicações e indisponibilidade (Etapa 8), juntar
`--faults config/faults.json`; ver [falhas](docs/faults.md).

Para executar os mesmos agentes ligados ao XMPP, iniciar num terminal:

```bash
spade run --host localhost --memory
```

Noutro terminal, ativar o mesmo ambiente Python, definir `XMPP_PASSWORD` e executar:

```bash
PYTHONPATH=src python -m isia.simulation.runner --xmpp
```

São criadas cinco contas de demonstração no servidor local: `sensor-mvp`,
`sensor-peer-mvp`, `drone-mvp`, `vehicle-mvp` e `ranger-mvp`, todas em `localhost`.
O processo encerra os agentes quando a ocorrência termina e os recursos regressam.
O SPADE pode otimizar a entrega entre agentes no mesmo processo; este comando
não substitui uma verificação de rede com agentes em processos separados.

O mapa não tem obstáculos: percorre primeiro x e depois y, a uma célula por
segundo simulado. Cada célula gasta um ponto percentual de energia; a inspeção
leva um segundo e não tem consumo adicional. A inspeção local é idealizada e a
intervenção do guarda é uma ação simulada bem-sucedida, sem remover o evento do
ambiente. Falhas sistemáticas e avaliação experimental ficam para as etapas
seguintes. Ver o [protocolo da missão](docs/protocols.md#missões-e-intervenção--etapa-6).

Para ativar a política da Etapa 7 sobre os mesmos agentes:

```bash
PYTHONPATH=src python -m isia.simulation.runner --policy config/agents.json > /tmp/isia-policy.json
```

Com os parâmetros fornecidos, as duas fontes acústicas correlacionadas levam a
`observe`, sem missões, e a janela termina como `expired`. A configuração,
pesos e razões constam do JSON. Ver os [parâmetros e a aprendizagem](docs/reputation-policy.md).

### Requisitos
- Python 3.12
- SPADE 4.1.4
- Git

### 1. Preparar o ambiente Python

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 2. Iniciar o servidor XMPP

No primeiro terminal:

```bash
spade run
```

Manter o servidor em execução.

### 3. Executar o primeiro agente

Abrir um segundo terminal e ativar o ambiente:

```bash
source .venv/bin/activate
python hello_agent.py
```

### Resultado esperado

```text
A iniciar o agente...
Olá! Sou o agente teste_isia@localhost
Agente terminou corretamente.
```

### Terminar

Para parar o servidor XMPP, utilizar Ctrl+C
no terminal em que foi iniciado.

### Mapa 2D e relógio da simulação

**Estado atual:** as Etapas 1–6 estão integradas na `main`. O demonstrador `verification_demo.py` utiliza observações do simulador e mostra classificação, fontes distintas, pontuação descritiva, cobertura e decisão preliminar. As demonstrações de verificação e Contract Net continuam disponíveis separadamente; `isia.simulation.runner` liga automaticamente decisão, negociação e execução no MVP da Etapa 6.

### Demonstração da Etapa 4 — observações reais e decisão preliminar

Na `main` ou numa branch atualizada a partir dela, iniciar o servidor local XMPP num terminal (`spade run`). Noutro, ativar o ambiente Python com SPADE 4.1.4 e definir `SENSOR_JID`, `INFORMANT_JID`, `SENSOR_PASSWORD` e `INFORMANT_PASSWORD` para contas locais válidas; **não colocar credenciais em ficheiros versionados**.

```bash
PYTHONPATH=src python verification_demo.py
```

O demonstrador carrega `config/environment.json`, avança o simulador, dá a cada agente apenas o seu feed de observações e troca `VERIFY_REQUEST`/`VERIFY_RESPONSE` através de SPADE/XMPP. Na execução local de 11-11-2026, a observação inicial `obs-000001` recebeu a evidência compatível `obs-000002` de `sensor_02`: pontuação preliminar `1.0`, cobertura `1.0` e decisão `request_mobile_verification`, com mínimo de uma fonte compatível nesta demonstração. Estes indicadores **não são probabilidades calibradas de caça furtiva**.

A implementação também permite `observe` perante informação insuficiente, `no_data`, timeout ou resposta inválida; classifica `compatible`, `contradictory`, `informative_absence` e o resultado auxiliar `inconclusive` sob as regras explícitas do contrato; elimina mensagens/observações repetidas e mantém histórico de diagnóstico em memória por conversa e pedido. Contradição e ausência informativa são cobertas por testes automatizados, enquanto a demonstração XMPP real valida o fluxo normal de pedido, resposta e corroboração compatível. A aprovação formal do grupo sobre incompatibilidade, cobertura, sensibilidade e falsos negativos permanece pendente.

Para repetir os testes locais:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Referência histórica de 11-11-2026: **249 testes, OK**; a implementação do PR #12 acrescentou os testes do MVP e comunicou **358 testes, OK**. Isto é distinto das demonstrações reais XMPP acima; os cenários de falha continuam validados por testes/mocks.

### Demonstração da comunicação entre agentes

Depois de instalar `requirements.txt` e iniciar um servidor XMPP compatível
com SPADE (por exemplo, `spade run`), crie duas contas locais ou use contas
disponibilizadas pelo servidor. As palavras-passe são sempre fornecidas por
variáveis de ambiente:

```bash
export SENSOR_JID=sensor@localhost
export SENSOR_PASSWORD='password-da-conta-do-servidor'
export INFORMANT_JID=informant@localhost
export INFORMANT_PASSWORD='password-da-conta-do-servidor'
PYTHONPATH=src python3 main.py
```

O programa inicia os dois agentes, envia um pedido de verificação com um
evento de exemplo, aguarda a resposta até ao timeout e encerra ambos os
agentes no bloco `finally`. Não coloque palavras-passe no código ou no Git.

Os testes locais podem ser executados com:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Os testes de construção/parsing SPADE são ignorados quando SPADE não está
instalado; para os executar, instale a versão fixada `spade==4.1.4`.

### Demonstração da Etapa 5 — Contract Net e reserva

Com um servidor XMPP local compatível com SPADE em execução, a demonstração
[contract_net_demo.py](contract_net_demo.py) inicia um agente iniciador e dois
recursos móveis. O cenário normal envia CFP, recolhe `PROPOSAL`/`REJECT`,
seleciona deterministicamente a melhor proposta, envia `ACCEPT`, aguarda o
`STATUS/inform` de reserva e só então altera a missão para `RESERVED`.

Os prazos em `CFP` são instantes absolutos em **segundos simulados**. O tempo
de espera por mensagens XMPP é um timeout de parede independente. O limite do
CFP é inclusivo: `created_at == deadline` é válido; apenas propostas posteriores
são tardias.

As palavras-passe devem ser fornecidas apenas por variáveis de ambiente:

```bash
export CONTRACT_INITIATOR_JID=initiator@localhost
export CONTRACT_INITIATOR_PASSWORD='password-da-conta'
export CONTRACT_RESOURCE_ONE_JID=drone@localhost
export CONTRACT_RESOURCE_ONE_PASSWORD='password-da-conta'
export CONTRACT_RESOURCE_TWO_JID=vehicle@localhost
export CONTRACT_RESOURCE_TWO_PASSWORD='password-da-conta'
export CONTRACT_MAX_ROUNDS=2
export CONTRACT_RECEIVE_TIMEOUT_SECONDS=10
PYTHONPATH=src python3 contract_net_demo.py
```

`CONTRACT_MAX_ROUNDS` aceita `1` ou `2` e impede ciclos infinitos. Uma recusa
explícita de reserva pode iniciar a ronda seguinte com novos IDs de CFP e
conversa, mantendo `mission_id` e `incident_id`. Um timeout depois de `ACCEPT`
produz `confirmation_unknown`; não provoca outro `ACCEPT` nem marca a missão
como reservada. A ausência de propostas produz `no_eligible_proposals`.

Os testes com mocks validam ausência de propostas, recusas, timeouts, mensagens
tardias, limite de rondas e concorrência. A demonstração XMPP real validada no
Ubuntu cobre o cenário normal; os testes unitários não substituem essa
validação de transporte.

Na raiz do repositório, sem precisar de SPADE nem de servidor XMPP:

```bash
PYTHONPATH=src python3 -m isia.simulation config/environment.json --steps 3 --step-seconds 0.5
```

O comando mostra a grelha, os instantes e as observações de cada fonte.
Guarda cada execução num novo `results/simulation/run-*/run.json`, com semente,
parâmetros, avanços, observações e verdade de referência para avaliação.
`--output /tmp/execucao.json` permite escolher um ficheiro que ainda não exista.
Sem `--steps`, amostra apenas o instante inicial e guarda esse registo.

Editar [config/environment.json](config/environment.json) para mudar as
dimensões, posições e cenário. O exemplo tem 12 × 10 células, duas fontes
próximas (acústica e visual), um drone e um veículo. Uma ameaça começa em
`t=1`, dura cinco segundos e desloca-se de `(5, 6)` para `(8, 6)`.
As coordenadas são inteiras: `0 <= x < width` e
`0 <= y < height`. A origem `(0, 0)` fica no canto inferior esquerdo;
`x` cresce para a direita e `y` para cima. Não há escala física definida.
Coordenadas inválidas e identificadores repetidos são rejeitados.
Vários participantes podem partilhar uma célula, assinalada com `*`.

O [World](src/isia/simulation/world.py) usa os modelos `Position` e
`ResourceState` existentes. Cada execução tem um
[SimulationClock](src/isia/simulation/clock.py) próprio, iniciado em zero.
Usar `scenario.advance(segundos)` para avançar o relógio e gerar leituras.
Não há espera real nem avanço automático; `world.clock.now` fornece o instante
simulado. Avançar diretamente `world.clock` num cenário é rejeitado no próximo
avanço ou gravação. Os timeouts XMPP continuam a usar tempo real.

```python
from isia.simulation.scenario import Scenario

scenario = Scenario.from_config("config/environment.json")
source = scenario.source("sensor_01")  # Entregar apenas esta API ao agente.
scenario.advance(1)
observations = source.recent()
```

`recent()` devolve apenas as observações dessa fonte na janela inclusiva
`[agora - corroboration_window, agora]`. Consultas repetidas não sorteiam novas
leituras. A geração ocorre em `t=0` e após cada avanço; eventos que comecem e
terminem entre duas amostras podem passar despercebidos. Mesma configuração,
semente e sequência de avanços reproduzem o resultado.

Cada perfil em `scenario.sources` corresponde a uma posição em `sensors`:

| Parâmetro | Efeito |
|---|---|
| `kind` | `acoustic`, `visual` ou `human`; cada tipo emite um sinal distinto |
| `detection_range` | Distância euclidiana máxima, inclusiva, em células |
| `sensitivity` | Probabilidade base de captar o sinal, entre 0 e 1 |
| `false_negative_rate` | Falha adicional perante uma ameaça |
| `false_positive_rate` | Confusão de um evento benigno com um sinal suspeito |
| `position_error` | Desvio inteiro máximo por eixo, limitado às bordas do mapa |
| `confidence` | Pontuação fixa da fonte; não representa a verdade do evento |

A probabilidade de emitir uma leitura de ameaça é
`sensitivity * (1 - false_negative_rate)`; num evento benigno é
`sensitivity * false_positive_rate`. São sorteios independentes por evento,
fonte e amostra, sempre sujeitos ao alcance e capacidade da fonte.
`threat` produz sinais nos três canais; `thunder` apenas no acústico;
`tourist` nos canais visual e humano. Sem evento não há falso alerta.
Estes parâmetros são um modelo simplificado, sem calibração empírica.

Eventos estão ativos em `[starts_at, starts_at + duration)`. O movimento base
percorre primeiro x e depois y, em células completas, à velocidade `speed`
(células/segundo), sem ultrapassar `destination`. Frações acumulam-se pelo tempo
decorrido desde o início. Fontes e patrulhas mantêm as posições iniciais;
obstáculos e execução de missões pertencem às etapas seguintes.

O avaliador consulta `scenario.ground_truth`: tipo real, posição, estado temporal
e ligação entre cada observação e o evento que a originou. Os agentes recebem
apenas `ObservationFeed`, sem acesso aos eventos através da API pública.
`Observation.event_id` identifica a leitura, não o evento real. A janela de
consulta está pronta; a decisão de corroboração distribuída pertence à Etapa 4.

Para verificar os modelos, contratos e simulação:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
