# Roteiro da apresentação

> Ordem fixa, tempo e fala de cada diapositivo. Os números vêm de `results/`: Etapa 9 (560 execuções), P3 (`results/scalability/`), testes de stress (`results/stress/`), cenários D e E e Bloco G (3500 execuções). As recolhas têm âmbitos distintos; cada diapositivo aponta para a fonte.

**Diapositivos (18-11-2026):** <https://claude.ai/artifact/8unfFKR29LmPhbGwdKwggj>. São 15, com notas do orador, na paleta areia, verde-floresta e âmbar. A ligação é privada até ser partilhada no menu Share; para a entrega, exportar para PDF ou PowerPoint (Share › Export) e guardar em `docs/presentation/`. As versões anteriores, a cinzento e azul, continuam em <https://claude.ai/artifact/HiSFxr2GXmDaTUH3NHpohF> e <https://claude.ai/artifact/T1wJXEX4xufTvvUWFwV2UL> (intermédia); a mais antiga, com outro desenho, em <https://claude.ai/artifact/C5kRVniNyws5ZcU1z3SaXs>.

**Grupo, por ordem alfabética:** Afonso Pereira, Guilherme Gomes e Guilherme Kotchergenko.

**Duração alvo:** 12 minutos; os tempos abaixo somam 12:30. Sugestão de divisão em três blocos, um por elemento: diapositivos 1 a 5 (o sistema), 6 a 10 (demonstração, SPADE, método, variantes e resultados) e 11 a 15 (comparação, sensibilidade, escala e conclusões).

## Ordem e tempos

| # | Diapositivo | Tempo | Responde a | Fonte |
|---|---|---|---|---|
| 1 | Capa | 0:20 | — | — |
| 2 | Problema | 0:50 | — | [README](../../README.md#o-projeto) |
| 3 | Arquitetura | 1:00 | P1, P2 | [architecture.md](../architecture.md) |
| 4 | Decisão dos Agentes | 1:15 | P1 | [reputation-policy.md](../reputation-policy.md), [allocation.py](../../src/isia/reasoning/allocation.py) |
| 5 | Comunicação | 1:00 | P2 | [protocols.md](../protocols.md#3-tipos-de-mensagens-e-intenção), [mvp.json](../../results/demo/mvp.json) |
| 6 | Demonstração | 1:00 | — | [results/demo/](../../results/demo/) |
| 7 | SPADE e Falhas | 1:00 | P1 | [mobile.py](../../src/isia/agents/mobile.py), [faults.md](../faults.md) |
| 8 | Método de Avaliação | 0:45 | — | [experiments.md](../experiments.md#unidade-de-avaliação-e-métricas) |
| 9 | As Quatro Variantes | 0:40 | — | [experiments.md](../experiments.md#variantes-comparadas-collectorvariants) |
| 10 | Resultados por Cenário | 1:00 | — | [experiments.md](../experiments.md#resultados), [scalability.md](../scalability.md#cenário-d--dia-movimentado) |
| 11 | Comparação entre Variantes | 0:50 | P2 | [experiments.md](../experiments.md#discussão) |
| 12 | Sensibilidade dos Parâmetros | 0:40 | — | [sensitivity.md](../sensitivity.md#síntese-dos-efeitos-e-ausência-de-diferenças) |
| 13 | Escalabilidade | 0:50 | P3 | [p3-escalabilidade.md](p3-escalabilidade.md), [scalability.md](../scalability.md) |
| 14 | Testes de Stress | 0:40 | P3 | [scalability.md](../scalability.md#mapa-de-limites) |
| 15 | Conclusões e Limitações | 0:40 | — | [scalability.md](../scalability.md#cenário-e--reserva-alargada) |

P1 é «como são construídos os agentes», P2 é «que protocolos e porquê esta arquitetura» e P3 é «escalabilidade computacional e situacional».

## O que dizer em cada diapositivo

As falas são guias, não texto para ler. O essencial de cada uma está na primeira frase.

### 1 · Capa (0:20)

«O nosso tema é a monitorização de uma reserva contra a caça furtiva. O mapa mostra as três camadas do sistema: o terreno é o ambiente simulado, à volta da ameaça estão as fontes de informação, e a rota tracejada é um recurso móvel. Não há despachante central: quem deteta coordena. O ciclo é detetar, corroborar e intervir.»

### 2 · Problema (0:50)

«O mapa é o mundo base: uma grelha de oito por oito, dois sensores, uma ameaça, um drone, um veículo e um guarda. O problema tem três restrições e a cada uma corresponde uma peça do sistema. Os sensores erram, por isso uma leitura sozinha não mobiliza ninguém: outra fonte corrobora e uma patrulha verifica no local. As mensagens perdem-se, por isso o iniciador pode reenviar o pedido. Os recursos são poucos e gastam energia, por isso cada um propõe ou recusa, e ganha o de menor custo.»

Apontar os números no mapa, de 1 a 5: observação, corroboração, Contract Net, missão, resultado.

### 3 · Arquitetura (1:00)

«Lê-se da esquerda para a direita. O ambiente gera os eventos e envia-os às fontes. O sensor acústico ouve o som de tiro e é ele que inicia e coordena a ocorrência. A câmara e o informador humano só corroboram. O sensor pede propostas aos recursos: drone, veículo e guarda são a mesma classe e só muda a capacidade. Drone e veículo verificam; o guarda intervém. O círculo riscado lembra que não há agente central de atribuição: cada recurso decide sozinho se propõe ou recusa. Os agentes nunca veem a verdade; só o avaliador, em baixo, a usa, no fim.»

### 4 · Decisão dos Agentes (1:15)

«São três decisões, todas em funções puras. Primeira, cruzar observações: o peso de cada fonte é reputação vezes confiança vezes proximidade. Neste exemplo real, os dois sensores valem 0,40 cada e são de modalidades diferentes; na régua, o score é 0,40 e passa o limiar de 0,25. Sozinho, o sensor-1 ficava em 0,15, à esquerda do limiar, e o sistema só observava. Segunda, escolher um recurso: o custo junta tempo de chegada, energia e carga. Aqui o drone está mais perto, mas leva carga, e por isso ganha o veículo, a coluna escura. Terceira, a reputação: começa em 0,5 e sobe para 0,6 com uma missão confirmada.»

Dizer em voz alta: o score é uma heurística, não uma probabilidade.

### 5 · Comunicação (1:00)

«Esta é a ocorrência que vamos ver a seguir na demonstração: 15 mensagens e dois protocolos FIPA, contadas por fase. Na primeira coluna, o FIPA Request: o sensor-1 pede corroboração e o sensor-2 informa; são 2. Na segunda, o Contract Net: o pedido vai às duas patrulhas, as duas propõem, o drone é aceite e o veículo rejeitado. O drone confirma a reserva com STATUS e depois envia o resultado; são 8. Com a ameaça confirmada, a mesma ronda repete-se só para o guarda; são 5.»

Dizer em voz alta: o STATUS é uma extensão nossa ao FIPA, para um recurso não aceitar duas missões.

### 6 · Demonstração (1:00)

Clicar no vídeo. Dura 25 segundos; narrar por cima:

1. **t = 0 s:** alerta, corroboração pelo sensor-2, pedido de propostas e aceite ao drone.
2. **t = 1 a 3 s:** o drone (D) vai até à ameaça (X) e a energia desce um ponto por célula.
3. **t = 4 s:** resultado confirmado; segunda ronda só para o guarda.
4. **t = 10 s:** o guarda confirma e o sensor fecha a ocorrência.
5. **Métricas no fim:** 15 mensagens; energia gasta: drone 6, guarda 10, veículo 0.

«O visualizador só lê o relatório da execução: não corre agentes nem decide nada.»

### 7 · SPADE e Falhas (1:00)

«Cada agente é uma subclasse de Agent do SPADE. O sensor iniciador tem um comportamento OneShot, que conduz uma ocorrência do alerta ao fecho. Os recursos têm comportamentos cíclicos, sempre à escuta. No setup, cada comportamento é registado com um Template, as linhas a âmbar, que filtra as mensagens pela performativa, pela ontologia e pelo protocolo. Os comportamentos só comunicam; as decisões estão em funções puras, por isso os 581 testes correm sem servidor. À direita, o que acontece depois de uma atribuição: o iniciador envia o accept-proposal e fica à espera. Se o recurso confirma, executa. Se há silêncio, reenvia o mesmo pedido e volta a esperar. Se o recurso recusa, abre-se uma nova ronda, até duas tentativas. Já sem tentativas, a ocorrência fica por resolver, mas visível no relatório.»

Se perguntarem: nos cenários A, B e C não há reenvio (`retransmit` é 0), por isso o silêncio leva logo a «por resolver». Os testes de stress usaram 1 e 2 reenvios.

### 8 · Método de Avaliação (0:45)

«Cada experiência segue cinco passos: o cenário e a semente fixam as entradas, os agentes correm só com o seu estado local, a execução produz um relatório, e só depois o avaliador o cruza com a verdade, a linha tracejada. Fizemos três recolhas: 560 execuções nos três cenários, 3500 de sensibilidade, e os testes de stress. As métricas saem da matriz: a linha de cima são as ameaças reais, a de baixo os episódios sem ameaça. O recall é a fração das ameaças reais que foram mobilizadas; a FPR é a fração dos episódios sem ameaça que mesmo assim mobilizaram.»

### 9 · As Quatro Variantes (0:40)

«Cada cenário correu em quatro variantes, com as mesmas sementes. A completa é a referência; cada uma das outras muda uma peça. Sem reputação: a reputação volta a 0,5 em cada execução, e só uma decisão mudou em 560. Sem corroboração: ignora o segundo sensor e baixa o limiar, por isso qualquer alerta mobiliza; em B os falsos alarmes triplicam, de 10 para 30. Só o mais próximo: escolhe pelo tempo de chegada e verifica aos 4 segundos em vez de 6, com a mesma deteção.»

Dizer em voz alta: a variante sem corroboração muda duas coisas, a corroboração e o limiar, por isso não isola a causa.

### 10 · Resultados por Cenário (1:00)

«Cada barra mostra até onde chegou cada ameaça real: verde, chegou ao guarda; âmbar, foi confirmada mas o guarda não respondeu; verde claro, saiu patrulha mas não confirmou; tracejado, nem saiu patrulha. Em A, a operação normal, saem 17 patrulhas e as 17 chegam ao guarda, sem nenhum falso alarme. Em B, com ruído e erro de posição, saem 13 patrulhas mas só 2 confirmam: em 11, a patrulha vai à célula ao lado. Os falsos alarmes contam-se nos episódios sem ameaça: em B há 40, e 10 mobilizaram por engano. Em C, com 10 % de mensagens perdidas, saem 16 patrulhas, 10 confirmam e só 6 chegam ao guarda: basta perder uma mensagem. D e E são os cenários de escala, com seis e dezasseis ameaças ao mesmo tempo: fecham 40 de 60 e 129 de 160.»

Se perguntarem por D: das 20 que faltam, 15 nem tiveram patrulha (8 sem alerta, 4 sem corroboração, 3 expiradas) e em 5 a ameaça curta já tinha acabado quando a patrulha chegou.

### 11 · Comparação entre Variantes (0:50)

«Este é o compromisso central, nos três cenários. Cada linha vai de sem corroboração, à esquerda, a com corroboração, à direita: verde melhora, âmbar piora, cinzento não muda. Em todos, corroborar custa recall: 0,95 para 0,85 em A, 0,80 para 0,65 em B, 0,95 para 0,80 em C. Só em B, onde há trovões e turistas, isso compra alguma coisa: os falsos alarmes descem de 0,75 para 0,25 e a precision sobe de 0,35 para 0,57. Em A e C os episódios sem ameaça são vazios e nunca dão alerta, por isso a FPR é 0 com ou sem corroboração.»

Dizer em voz alta: a variante sem corroboração também desce o limiar, por isso é a diferença conjunta dos dois; não isola a causa.

`no_reputation` e `nearest` estão no diapositivo 9, e o reenvio com 10 % de perda (7 → 17) no 14; já não estão neste.

### 12 · Sensibilidade dos Parâmetros (0:40)

«Variámos 13 parâmetros, um de cada vez. Estes são os dois maiores efeitos. Um limiar mais exigente evita nove falsos alarmes, mas deixa onze ameaças por mobilizar. Uma gravidade alta mobiliza mais três ameaças, mas gera mais vinte falsos alarmes. Não há um valor melhor em todos os objetivos.»

Não afirmar significância estatística: os intervalos são descritivos.

### 13 · Escalabilidade (0:50)

«Dois limites e a resposta a cada um. Computacional: cada missão custa até 3N mais 2 mensagens. Com 16 patrulhas eram 57 mensagens por ocorrência; chamando só as duas mais próximas são 15. Situacional: com um só sensor a iniciar, atendemos sempre oito ameaças, haja uma, duas ou três ao mesmo tempo. A resposta foi deixar vários sensores iniciar, com um aviso entre eles e uma fila por gravidade.»

### 14 · Testes de Stress (0:40)

Não ler a tabela. Escolher três linhas:

«Com um guarda para oito ocorrências, fechava-se uma; com fila fecham as oito. Com a fila por gravidade, as graves fecham aos 23 segundos em vez de 74. Com reenvio e 10 % de perda, fecham 17 de 20 em vez de 7. Em todos os testes houve zero reservas duplas.»

### 15 · Conclusões e Limitações (0:40)

«A cascata é o cenário maior, de 160 ameaças: 8 não geram alerta, 23 não são corroboradas, e as 129 confirmadas têm todas intervenção. O que se perde é na deteção e na corroboração, não na coordenação. Três conclusões, cada uma com o seu limite: corroborar corta falsos alarmes e custa deteções; a coordenação dispensa o despachante, sem garantir a melhor atribuição global; e uma mensagem perdida trava a ocorrência, o que o reenvio resolve.»

## Sensibilidade — Bloco G (diapositivo 12)

| Comparação em B | TP | FP | Recall | FPR | Energia média (p.p./execução) |
|---|---:|---:|---:|---:|---:|
| Referência | 13 | 10 | 0,65 | 0,25 | 4,167 |
| Patrulha 0,25→0,35 | 2 | 1 | 0,10 | 0,025 | 0,5 |
| Gravidade 0,5→0,9 | 16 | 30 | 0,80 | 0,75 | 7,7 |

São 20 sementes e 60 execuções por valor: 20 ameaças e 40 negativos. Os intervalos centrais descritivos das diferenças foram [−0,75; −0,35] para o recall e [+0,35; +0,65] para a FPR, com 2000 reamostragens emparelhadas por semente. Não são intervalos inferenciais nem testes de significância.

Fonte: [comparisons.csv](../../results/sensitivity/g-final-analysis-20261117/comparisons.csv), [effects.csv](../../results/sensitivity/g-final-analysis-20261117/effects.csv) e [manifesto](../../results/sensitivity/g-final-consolidated-20261117/manifest.json).

## Demonstração (diapositivo 6)

O vídeo do diapositivo é `results/demo/mvp.mp4` (relatório do `run_mvp`, semente 6). Se não tocar, reproduzir no terminal, sem Python nem SPADE:

```bash
scriptreplay --log-timing results/demo/replay.tim --log-out results/demo/replay.log
```

**Segunda gravação, para perguntas sobre várias ocorrências:** o [cenário D](../scalability.md#cenário-d--dia-movimentado), com seis ameaças ao mesmo tempo num mapa 12×8.

```bash
scriptreplay --log-timing results/demo/replay-d.tim --log-out results/demo/replay-d.log
```

---

## Para o grupo — não dizer na apresentação

Esta parte explica o trabalho a quem o vai apresentar. Nada daqui é para ser lido em voz alta.

### O trabalho numa frase

Simulámos uma reserva onde sensores com ruído detetam possíveis caçadores e, sem ninguém a mandar em todos, pedem a um drone ou a um veículo que vá confirmar e a um guarda que vá intervir.

### Como corre uma ocorrência, em linguagem simples

1. O ambiente cria um evento numa célula do mapa (uma ameaça, um trovão, um turista ou nada).
2. O `sensor-1` ouve algo e gera um alerta. Pode falhar (não ouvir) ou enganar-se (ouvir um trovão).
3. O `sensor-1` pergunta ao `sensor-2`: «também viste?». É o FIPA Request.
4. Com as respostas, calcula um score. Se passar o limiar, decide mobilizar.
5. Pede propostas ao drone e ao veículo (Contract Net). Cada um responde com o seu tempo, energia e carga, ou recusa. Ganha o de menor custo.
6. O vencedor vai à célula e diz se viu a ameaça.
7. Se viu, o `sensor-1` repete a negociação só para o guarda, que vai intervir.
8. A ocorrência fecha. Depois de tudo acabar, o avaliador compara o que aconteceu com a verdade.

### Onde está cada coisa no código

| O quê | Onde |
|---|---|
| Sensor que inicia e coordena | `src/isia/agents/incident.py` |
| Sensor que corrobora | `src/isia/agents/informant.py` |
| Drone, veículo e guarda (a mesma classe) | `src/isia/agents/mobile.py` |
| Score e corroboração | `src/isia/reasoning/corroboration.py` |
| Decidir observar, patrulhar ou chamar o guarda | `src/isia/reasoning/policy.py` |
| Custo das propostas e reservas | `src/isia/reasoning/allocation.py` |
| Reputação | `src/isia/reasoning/reputation.py` |
| Montar e correr uma execução | `src/isia/simulation/runner.py` |
| Correr cenários e calcular métricas | `src/isia/evaluation/collector.py`, `metrics.py` |

### Vocabulário que vai aparecer nas perguntas

- **Ocorrência (incident):** um alerta e tudo o que se segue até fechar.
- **Corroboração:** uma segunda fonte, de outro tipo, confirmar a primeira.
- **Contract Net:** leilão de uma ronda. Quem precisa pede propostas (`cfp`), os outros propõem ou recusam, e um é aceite.
- **B1:** o nome que demos à arquitetura na proposta. Quer dizer só «quem deteta coordena a sua ocorrência».
- **Recall:** das ameaças reais, quantas mobilizámos. Alto é bom.
- **FPR:** dos episódios sem ameaça, em quantos mobilizámos por engano. Baixo é bom.
- **Precision:** das vezes que mobilizámos, em quantas havia ameaça.
- **Unresolved:** ocorrência que ficou a meio, em geral por uma mensagem perdida.
- **Variante:** o mesmo cenário com uma peça desligada, para ver o que ela faz.
- **Coordenadas (x, y):** coluna primeiro, linha depois, a contar do canto de baixo à esquerda. A ameaça da demonstração está em (3,2): coluna 3 da linha 2. Lida como (linha, coluna) parece (2,3); não é.

### O que os números querem mesmo dizer

- **«17 de 20» em A:** das 3 que faltam, 1 foi o sensor que não ouviu e 2 foi o `sensor-2` que não confirmou. Não é falha de coordenação.
- **«2 de 20» em B:** parece muito mau, mas mobilizámos 13. Em 11, o erro de posição de uma célula mandou a patrulha para a célula ao lado, e ela não viu nada. O sistema decidiu bem e foi ao sítio errado.
- **«6 de 20» em C:** o drone tem 15 % de energia e recusa sempre, por isso só o veículo pode ir. Com um só candidato, qualquer mensagem perdida deixa a ocorrência por resolver.
- **FPR 0,75 → 0,25:** em 40 episódios sem ameaça, passámos de 30 para 10 mobilizações erradas. As 10 que sobram são todas do episódio com trovão e turista juntos: dois enganos de fontes diferentes parecem confirmar-se.
- **«129 de 160» em E:** as 31 que faltam são 8 sem alerta e 23 sem corroboração. Tudo o que foi mobilizado fechou.

### Os pontos fracos, para não sermos apanhados de surpresa

- **A reputação quase não faz nada.** Mudou 1 decisão em 560. Existe, está testada, mas com estes limiares só pesa quando chega a 0,84. Admitir isto se perguntarem.
- **A comparação com e sem corroboração não é limpa.** A variante sem corroboração também tem o limiar mais baixo (0,01), senão nunca mobilizava. Medimos dois sistemas diferentes, não o efeito de uma só peça.
- **Os scores não são probabilidades.** 0,40 não quer dizer 40 % de hipótese de ameaça.
- **As falhas são simuladas em memória.** Não testámos perda de mensagens num servidor XMPP real.
- **Todos os agentes correm no mesmo processo.** Não medimos nada em máquinas separadas.
- **Poucas repetições.** 20 sementes nos cenários A, B e C, e 10 nos testes de stress e em D e E. Diferenças de 1 ou 2 execuções não significam nada.
- **D e E são um pico.** As ameaças começam todas no mesmo instante; não é um dia de operação.
- **A recolha do cenário D foi feita com código por commitar** (`dirty: true` no manifesto). Se perguntarem pela reprodutibilidade, dizer que as 40 confirmadas se repetiram em três recolhas.
- **Os diapositivos 4 e 5 mostram vencedores diferentes.** No 4 (cenário A) o drone leva carga 0,5 e ganha o veículo. No 5 e no vídeo (demonstração) ninguém leva carga e ganha o drone, que está mais perto. Não é contradição; é a função de custo a funcionar.

### Perguntas prováveis e resposta curta

- **«O sensor-1 não é um despachante disfarçado?»** Não. Coordena só a sua ocorrência, não conhece o estado dos recursos e não os pode obrigar: eles recusam.
- **«Porquê Contract Net e não um leilão de várias rondas?»** Uma ronda custa cerca de 3N mensagens e chega. Várias rondas seriam mais lentas, e não temos pagamentos para um Vickrey.
- **«Porquê Request e não Subscribe?»** Uma pergunta e uma resposta, com um prazo simples. O Subscribe traria evidência posterior, com mais mensagens.
- **«Isto é BDI?»** Não. É reativo, com uma função de custo. As decisões são funções puras.
- **«Onde está a autonomia?»** No recurso: decide se propõe, conta a energia de ida e volta e pode recusar a reserva mesmo depois de aceite.
- **«E se o sensor que coordena falhar?»** O recurso acaba a missão e liberta-se sozinho. A ocorrência fica por resolver e visível no relatório; ninguém a assume.
- **«Os informadores humanos estão implementados?»** Sim, nos testes de stress e no cenário E, não nos cenários A, B e C. Onde corrobora um humano fecham 59 de 80, contra 70 com câmara.

### Antes de apresentar

- Partilhar a ligação dos diapositivos e exportar o PDF para `docs/presentation/`.
- Abrir o diapositivo 6 e confirmar que o vídeo toca no computador da apresentação.
- Deixar um terminal aberto na pasta do projeto, com o comando do `scriptreplay` pronto.
- Ensaiar uma vez com cronómetro: o diapositivo 4 é o que mais derrapa.
