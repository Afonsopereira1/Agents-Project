# ISIA — Tema C: Monitorização descentralizada da vida selvagem

**Unidade curricular:** Introdução aos Sistemas Inteligentes e Autónomos (2026/2027) — Assignment 1  
**Tema:** *Decentralised Wildlife Monitoring and Anti-Poaching Patrols*

> **Estado:** as Etapas 1 e 2 têm modelos, contratos JSON e ambiente 2D com observações imperfeitas implementados e testados. A arquitetura B1 e os contratos continuam sujeitos a revisão do grupo; comunicação entre agentes, corroboração distribuída e negociação estão pendentes.

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
| Organização flexível dos colegas | [docs/team-tasks.md](docs/team-tasks.md) e [Issues](https://github.com/Afonsopereira1/Agents-Project/issues) |

**MVP previsto:** ocorrência → observação → evidências → avaliação → propostas de recursos → missão → resultado. O MVP não substitui os requisitos da entrega final.

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

**Estado atual:** as Etapas 1 e 2 estão concluídas, com modelos, contratos JSON,
simulação 2D, sensores e cenários implementados e testados. A Etapa 3 está
implementada nesta branch: `SensorAgent` e `InformantAgent` trocam
`VERIFY_REQUEST`/`VERIFY_RESPONSE` através de SPADE, com dados de exemplo e
correlação por `conversation-id`.

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
