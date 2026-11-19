ISIA 2026/2027 — Assignment 1 — Tema C
Monitorização descentralizada da vida selvagem

Equipa: Afonso Pereira, Guilherme Gomes e Guilherme Kotchergenko.

1. OBJETIVO E CONTEÚDO

Sistema multiagente em SPADE para detetar atividade suspeita, corroborar
observações e coordenar patrulhas e guardas sem despachante central.
Cada ocorrência tem um iniciador local; cada recurso pode propor ou recusar.
Os protocolos são inspirados em FIPA Request e Contract Net.

src/isia/          código dos agentes, domínio, raciocínio e simulação
config/            configurações e cenários A/B/C/D/E
scripts/           demonstração, gráficos e ferramentas experimentais
tests/             testes unitários, de integração e de cenários
results/           resultados históricos e demonstração gravada
docs/              documentação técnica e científica
requirements.txt   versões fixadas das dependências principais

2. AMBIENTE E DEPENDÊNCIAS

Usar Python 3.12; a validação foi realizada com Python 3.12.3 em Linux.
O código usa asyncio.timeout(), disponível desde Python 3.11, mas outras
versões do Python não foram validadas nesta fase.
Os comandos abaixo pressupõem Bash e execução a partir da raiz do projeto.

Versões fixadas em requirements.txt:
  spade==4.1.4
  pyjabber==0.4.5
  SQLAlchemy[asyncio]==2.1.8

Validação isolada em 19-11-2026, com as versões exatas acima:
- Ambiente virtual novo, sem pacotes globais nem pacotes do utilizador.
- Instalação de requirements.txt concluída e pip check sem incompatibilidades.
- MVP normal e MVP com política com os resultados esperados nas secções 4 e 5.
- Suite completa: 581 testes em 46,670 s, OK, sem falhas, erros ou ignorados.

A suite foi executada numa cópia fiel dos ficheiros auditados, com metadados
Git, usando diretórios temporários para as saídas. O código, os resultados
históricos e o ambiente virtual anterior foram preservados. A validação
não repetiu recolhas experimentais extensas nem o modo XMPP.

O ambiente anterior, também com 581 testes aprovados, usava SQLAlchemy
2.1.0. Essa validação é distinta da validação isolada descrita acima.
As dependências transitivas são resolvidas pelo pip; requirements.txt
não fixa integralmente todas as versões transitivas.

3. INSTALAÇÃO NUM AMBIENTE NOVO

Criar um ambiente virtual separado, sem reutilizar o de outra instalação:

  ISIA_AMBIENTE_DIR="$(mktemp -d)"
  python3.12 -m venv "$ISIA_AMBIENTE_DIR/venv"
  source "$ISIA_AMBIENTE_DIR/venv/bin/activate"
  python -m pip install -r requirements.txt
  python -m pip check
  export PYTHONPATH=src
  export PYTHONDONTWRITEBYTECODE=1

Confirmar as versões efetivas:

  python -c 'import sys, importlib.metadata as m; print(sys.version); print({n: m.version(n) for n in ("spade", "pyjabber", "SQLAlchemy")})'

A instalação inicial precisa de acesso às dependências. O MVP local não
precisa de servidor XMPP, serviços externos ou acesso ao GitHub.
Não substituir automaticamente versões se a instalação falhar.

4. MVP NORMAL — TRANSPORTE LOCAL

Guardar saídas fora dos resultados históricos:

  ISIA_SAIDAS_DIR="$(mktemp -d)"
  python -m isia.simulation.runner > "$ISIA_SAIDAS_DIR/mvp.json"

Resultado esperado:
  incident_status: closed
  reason: confirmed
  15 mensagens; duas missões
  drone verifica aos 4 s simulados; guarda intervém aos 10 s
  reservas: null em todos os recursos
  estado final: available em todos os recursos
  autonomia final: drone 94%, veículo 100%, guarda 90%

O veículo propõe, mas não é escolhido nesta demonstração.

Repetir visualmente o relatório no terminal:

  python scripts/replay.py "$ISIA_SAIDAS_DIR/mvp.json" --delay 0.5

O replay apenas lê o relatório; não executa agentes nem toma decisões.
O vídeo gravado está em results/demo/mvp.mp4, com cerca de 25 segundos.

5. MVP COM POLÍTICA

  python -m isia.simulation.runner --policy config/agents.json > "$ISIA_SAIDAS_DIR/mvp-politica.json"

Resultado esperado:
  decision: observe
  suspicion_score: aproximadamente 0,15
  incident_status: expired
  reason: insufficient_corroboration
  duas mensagens; nenhuma missão
  reservas: null; todos os recursos disponíveis e com 100% de autonomia

Este resultado é esperado, não é uma falha: as fontes acústicas desta
configuração pertencem ao mesmo grupo de correlação e o score fica abaixo
do limiar de patrulha de 0,25. Não confundir esta configuração com o cenário A.

6. TESTES E PROVENIÊNCIA GIT

Na raiz do repositório, com o ambiente ativo e PYTHONPATH=src:

  python -m unittest discover -s tests -v

A suite contém 581 testes, incluindo pequenas execuções automatizadas.
Para preservar uma cópia de evidências, executar os testes numa cópia de
trabalho, mantendo configurações, scripts, CSV e manifestos de referência.
Os testes podem usar ficheiros temporários; não precisam de servidor XMPP.

IMPORTANTE: o MVP e o replay funcionam numa cópia sem .git, mas o coletor
e parte dos testes de sensibilidade exigem Git instalado e um repositório
com HEAD válido. Um ZIP apenas de código não basta para essas operações.
Não criar um histórico artificial para simular a proveniência original.

Se a entrega incluir um bundle Git aprovado, restaurar o repositório numa
nova diretoria com git clone, usando o caminho e a referência indicados
nas instruções que acompanhem esse bundle. Caso contrário, usar o clone
do repositório fornecido pela equipa. Nenhum bundle é criado por estes
comandos de instalação; não se pressupõe que já exista no pacote.

7. XMPP — OPCIONAL

A execução local acima é suficiente para demonstrar o MVP.
Para exercitar ligação e registo num servidor XMPP local, abrir dois
terminais, ambos com o ambiente virtual ativo.

Terminal 1:
  spade run --host localhost --memory

Terminal 2, a partir da raiz:
  export PYTHONPATH=src
  ISIA_SAIDAS_DIR="$(mktemp -d)"
  XMPP_PASSWORD=local-demo python -m isia.simulation.runner --xmpp > "$ISIA_SAIDAS_DIR/mvp-xmpp.json"

local-demo é apenas uma palavra-passe de demonstração para o servidor
local de teste. Os agentes do MVP continuam no mesmo processo: este modo
não demonstra escalabilidade multiprocesso nem transporte de todas as
mensagens pela rede. As falhas injetadas aplicam-se ao transporte local.
O arranque XMPP não foi repetido na validação isolada desta fase.

8. RESULTADOS, DOCUMENTAÇÃO E APRESENTAÇÃO

results/experiments/    A/B/C: 560 execuções históricas, não 560 testes
results/scenario-d/     cenário D, vários iniciadores
results/scenario-e/     cenário E, vários iniciadores e fontes humanas
results/scalability/    distribuição e custo
results/stress/         filas, prioridades, reenvios e outros ensaios
results/sensitivity/    Bloco G: 3500 execuções alternativas válidas

Referências principais:
  docs/architecture.md
  docs/protocols.md
  docs/evaluation.md
  docs/experiments.md
  docs/faults.md
  docs/reputation-policy.md
  docs/scalability.md
  docs/sensitivity.md

A apresentação PDF final será disponibilizada pela equipa na entrega.
Esta fase não inclui nem aprova uma versão final da apresentação.

9. LIMITAÇÕES E PRESERVAÇÃO DAS EVIDÊNCIAS

- Todas as medições experimentais usam o transporte local.
- Os scores são heurísticos, não probabilidades calibradas demonstradas.
- Não foi demonstrado ótimo global nem significância estatística.
- D/E podem variar devido à ordem dos pedidos e ao relógio real.
- O manifesto histórico de D conserva dirty: true; o commit não recupera
  integralmente o estado do código da recolha.
- As oito métricas de classificação de D/E são N/A porque verdade global
  e decisão apenas de sensor-1 não têm a mesma unidade de avaliação.
- closed não significa genericamente intervenção confirmada: é necessário
  ler também reason. A falta de confirmação recebida não prova que um
  guarda não tenha executado a missão.
- Os 139 do grupo de guardas em results/stress/sugestoes.csv provêm de
  incidents_closed; não são uma contagem independente de resultados
  confirmed do guarda.
- Os limites publicados de flood são históricos e não foram revalidados
  após a alteração da validação temporal.
- Os relatórios completos históricos de D/E não estão disponíveis nesta
  cópia. A seleção de agregados G não permite reconstituir integralmente
  todas as observações e mensagens da recolha original.

Não executar os comandos de recolha A/B/C/D/E, stress ou sensibilidade
sobre a cópia de evidências entregue. O coletor pode substituir a pasta
de resultados indicada, e vários scripts têm destinos fixos em results/.
Para novas experiências, usar uma cópia de trabalho e saídas próprias.
A instalação, os dois MVP e os testes não exigem repetir essas recolhas.
