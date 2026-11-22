ISIA 2026/2027 - Assignment 1 - Tema C
Monitorização Descentralizada da Vida Selvagem

Equipa: Afonso Pereira, Guilherme Gomes e Guilherme Kotchergenko

Sistema multiagente em SPADE que deteta atividade suspeita numa reserva,
corrobora observações e coordena drones, veículos e guardas por Contract Net,
sem despachante central.

ONDE ESTÁ O QUÊ (abrir no navegador)

  index.html                   documentação do código (docstrings de
                               todos os módulos, classes e funções)
  extra/cenarios.html          interface dos cenários A a E, com replay
  Presentation.pdf             apresentação
  mvp.mp4                      vídeo de uma ocorrência, do alerta ao fecho


1. ARQUITETURA

Agentes e mensagens:

               P1: VERIFY_REQUEST / VERIFY_RESPONSE
  InformantAgent <------------------------------> IncidentSensorAgent
  (fonte que corrobora)                           (sensor iniciador)
                                                        |
                         P2: Contract Net               |
          +-------------------+-------------------------+
          |                   |                         |
     DroneAgent          VehicleAgent              RangerAgent
     (patrulha)          (patrulha)                (guarda)
     verify_incident     verify_incident           respond_incident

  IncidentSensorAgent  deteta, pede corroboração (P1), decide e conduz
                       o Contract Net (P2) até fechar a ocorrência
  InformantAgent       responde só com as observações do seu feed
  Drone, Veículo       propõem ou recusam a verificação e inspecionam a célula
  RangerAgent          intervém; o seu resultado fecha a ocorrência

Os recursos móveis partilham a classe MobileResourceAgent. O servidor XMPP
só entrega mensagens: não existe despachante central.

P1, verificação distribuída (inspirado em FIPA Request):

  Iniciador                         Fonte
     | --- request / VERIFY_REQUEST --> |
     | <-- inform / VERIFY_RESPONSE --- |   observations_available,
     |                                  |   no_data ou informative_absence
  decide: observe, request_mobile_verification ou request_rangers
  (sem resposta no prazo, o pedido expira; nunca conta como ausência)

P2, atribuição de missões (Contract Net simplificado):

  Iniciador                              Recursos candidatos
     | --- cfp / CFP ----------------------> |
     | <-- propose / PROPOSAL ou refuse ---- |
     |   (fim do prazo: escolhe o menor custo)
     | --- accept-proposal / ACCEPT -------> |  vencedor
     | --- reject-proposal / REJECT -------> |  restantes
     | <-- inform / STATUS (reserved) ------ |
     | <-- inform / MISSION_RESULT --------- |

Primeiro com as patrulhas (verify_incident). Se a ameaça for confirmada,
repete-se com os guardas (respond_incident).

Formato das mensagens (exemplo real de um CFP, identificadores encurtados):

  Metadados SPADE:
    performative:     cfp
    ontology:         isia
    protocol:         contract-net
    conversation-id:  conversation-9a06

  Corpo JSON:
    {
      "schema_version": 1,
      "message_id": "message-45dc",
      "message_type": "CFP",
      "created_at": 0.0,
      "conversation_id": "conversation-9a06",
      "incident_id": "incident-obs-000001",
      "mission_id": "mission-incident-obs-000001-mobile-verification",
      "payload": {
        "task": "verify_incident",
        "target": {"x": 3, "y": 2},
        "required_capability": "mobile_verification",
        "priority": 1,
        "deadline": 100.0,
        "round_number": 1
      }
    }

Especificação completa em docs/protocols.md e docs/message-contract.md.


2. INSTALAÇÃO

Pré-requisitos: Linux com Bash, Python 3.12 e Git (com a pasta .git do
repositório presente). Não é preciso servidor XMPP.

Todos os comandos são executados a partir da raiz do projeto.

  python3.12 -m venv .venv
  source .venv/bin/activate
  python -m pip install -r requirements.txt
  python -m pip check
  export PYTHONPATH=src

Para confirmar as versões instaladas:

  python -c 'import importlib.metadata as m; print({n: m.version(n) for n in ("spade", "pyjabber", "SQLAlchemy")})'

Em cada novo terminal, repetir:

  source .venv/bin/activate
  export PYTHONPATH=src


3. EXECUÇÃO DE EXEMPLO

Executar uma ocorrência completa (cerca de 1 s) e guardar o relatório:

  python -m isia.simulation.runner > /tmp/exemplo.json

Resultado esperado no relatório:
  incident_status: closed
  reason: confirmed
  15 mensagens e duas missões
  o drone verifica aos 4 s simulados e o guarda intervém aos 10 s
  todos os recursos terminam com estado available

Repetir a ocorrência visualmente no terminal:

  python scripts/replay.py /tmp/exemplo.json --delay 0.5

O replay apenas lê o relatório; não executa agentes.


4. EXECUÇÃO COM POLÍTICA DE REPUTAÇÃO

  python -m isia.simulation.runner --policy config/agents.json > /tmp/exemplo-politica.json

Resultado esperado:
  decision: observe
  suspicion_score: aproximadamente 0,15
  incident_status: expired
  reason: insufficient_corroboration

Este resultado é o esperado: as duas fontes acústicas pertencem ao mesmo
grupo de correlação e a pontuação fica abaixo do limiar de patrulha (0,25).

Para injetar falhas no transporte local:

  python -m isia.simulation.runner --faults config/faults.json > /tmp/exemplo-falhas.json


5. CENÁRIOS A A E

  A  config/scenarios/A.json       operação normal, sem falhas
  B  config/scenarios/B.json       ruído e falsos positivos
  C  config/scenarios/C.json       falhas de mensagens e escassez de recursos
  D  config/scenarios/demo/D.json  dia movimentado: seis ameaças simultâneas
  E  config/scenarios/demo/E.json  reserva alargada: 16 ameaças e 20 fontes

Correr todos os cenários (uma repetição cada, cerca de 4 s) sem alterar
os resultados publicados:

  OUT="$(mktemp -d)"
  python -m isia.evaluation.collector config/scenarios/*.json config/scenarios/demo/*.json --variants full --repetitions 1 --output "$OUT"
  cat "$OUT/summary.csv"


6. TESTES

  python -m unittest discover -s tests

A suite tem 572 testes (unitários, de integração e de cenários) e demora
cerca de 47 s. Não precisa de servidor XMPP.

Os testes de sensibilidade e o coletor de resultados requerem Git e a
pasta .git do repositório. Numa cópia sem histórico (por exemplo, um ZIP),
a suite termina com 4 erros; usar um clone do repositório ou um git bundle.


7. MODO XMPP (OPCIONAL)

Abrir dois terminais com o ambiente virtual ativo.

Terminal 1:
  spade run --host localhost --memory

Terminal 2:
  export PYTHONPATH=src
  XMPP_PASSWORD=local-demo python -m isia.simulation.runner --xmpp > /tmp/exemplo-xmpp.json

Resultado esperado:
  transport: xmpp
  incident_status: closed
  reason: confirmed
  duas missões, com MISSION_RESULT aos 4 s e aos 10 s simulados

A lista messages fica vazia neste modo: só o transporte local regista o
transcrito das mensagens. A timeline continua completa.

As contas são criadas no arranque, pelo que qualquer palavra-passe serve.
Os agentes correm no mesmo processo: este modo demonstra a ligação ao
servidor XMPP, não o transporte das mensagens pela rede.


8. REPRODUÇÃO DOS RESULTADOS

  python scripts/reproduce.py

Lista cada resultado publicado com o comando que o gera, o tempo estimado
e o destino. ATENÇÃO: esses comandos reescrevem ficheiros em results/.
Para o coletor, usar --output "$(mktemp -d)" para não os alterar.


9. ESTRUTURA E DOCUMENTAÇÃO

src/isia/          código dos agentes, domínio, raciocínio e simulação
config/            mapa, política, falhas e cenários A a E
scripts/           replay, gráficos, stress, sensibilidade e reprodução
tests/             testes unitários, de integração e de cenários
results/           resultados publicados (CSV, gráficos, relatórios)
docs/              documentação técnica e relatório de desempenho
deliverables/      este ficheiro, documentação do código
                   (documentacao-api/ e index.html), interface de
                   exemplo (extra/cenarios.html), Presentation.pdf e mvp.mp4

Documentos principais:
  docs/architecture.md     arquitetura e agentes
  docs/protocols.md        protocolos P1 e P2
  docs/experiments.md      cenários e resultados
  docs/scalability.md      escalabilidade (P3)
  deliverables/documentacao-api/index.html  documentação do código (docstrings)

Mais detalhes em README.md.
