# Roteiro da apresentação

## Em resumo

- **Slides:** <https://claude.ai/artifact/1Sn3z364MWc1cbjCLoVQUU>. São 16: **10 para apresentar** (cerca de 7 minutos, com folga até aos 10), um separador e **5 de apêndice** só para perguntas. Cada um tem notas do orador.
- **A história:** um alerta na reserva → a ideia (quem deteta coordena) → ver a funcionar → como é feito → o que deu (resultados, valor de cada peça, escala) → o que aprendemos.
- **As 3 perguntas do professor:** P1 no 5, P2 no 3 e no 6, P3 no 9. O apoio de P3 está no apêndice: o 15 (stress) e o 16 (escala computacional).
- **Números:** todos conferidos com os CSV de `results/` a 18-11-2026.

A ligação é privada até ser partilhada no menu Share. Para a entrega, exportar para PDF ou PowerPoint (Share › Export) e guardar em `docs/presentation/`. A versão anterior, com 18 slides e 14 minutos, continua em <https://claude.ai/artifact/8unfFKR29LmPhbGwdKwggj>.

**Grupo, por ordem alfabética:** Afonso Pereira, Guilherme Gomes e Guilherme Kotchergenko.

## Ordem e tempos

A apresentação acaba no slide 10. Os tempos somam 7:05. Sugestão de divisão, um bloco por elemento: 1 a 4 (o problema e a ideia, 2:35), 5 a 7 (como é feito e o que deu, 2:15) e 8 a 10 (o valor, a escala e o fecho, 2:15).

| # | Slide | Tempo | Responde a | Fonte dos números |
|---|---|---|---|---|
| 1 | Capa | 0:20 | — | — |
| 2 | O Problema | 0:40 | — | enunciado |
| 3 | A Ideia: Quem Deteta Coordena | 0:50 | **P2** (arquitetura) | [architecture.md](../architecture.md) |
| 4 | Uma Ocorrência do Alerta ao Fecho | 0:45 | — | `results/demo/mvp.json` |
| 5 | Construção dos Agentes | 0:50 | **P1** | [architecture.md](../architecture.md), [p1-agentes.md](p1-agentes.md) |
| 6 | Protocolos | 0:45 | **P2** (protocolos) | [protocols.md](../protocols.md), [p2-protocolos.md](p2-protocolos.md) |
| 7 | Resultados por Cenário | 0:40 | — | [experiments.md](../experiments.md#resultados), [scalability.md](../scalability.md#cenário-d--dia-movimentado) |
| 8 | Valor de Cada Peça | 0:50 | — | [experiments.md](../experiments.md#discussão) |
| 9 | Escalabilidade Situacional | 0:40 | **P3** | [scalability.md](../scalability.md#escalabilidade-situacional-distcsv) |
| 10 | Conclusões e Limites | 0:45 | — | os anteriores |

## O que dizer em cada slide

As falas são guias, não texto para ler. O texto completo está nas notas do orador de cada slide. Aqui fica só a ideia e a frase que não pode faltar.

| # | A ideia | A frase que não pode faltar |
|---|---|---|
| 1 | Três coisas em dez minutos | «O que construímos, como o explorámos e o que cada peça vale.» |
| 2 | Um tiro, três restrições | «Alguém tem de ir ver, e o enunciado diz que ninguém pode mandar.» |
| 3 | Três arquiteturas, uma escolha | «Quem deteta coordena a sua ocorrência; o preço é não haver ótimo global.» |
| 4 | Ver antes de explicar | «15 mensagens, verificação aos 4 s, fecho aos 10 s.» |
| 5 | Três camadas | «Os comportamentos só comunicam; as decisões são funções puras, por isso 560 testes correm sem servidor.» |
| 6 | Dois protocolos e uma extensão | «Uma ronda, até 3N + 2 mensagens, e é o recurso que decide.» |
| 7 | Três histórias, não cinco barras | «Em C, basta uma mensagem perdida para travar a ocorrência.» |
| 8 | Como funciona cada peça, antes e depois | «Três peças provaram valor; duas ainda não, e dizemo-lo.» |
| 9 | Antes, depois e sugestão testada | «Antes a parte cheia não crescia; agora acompanha: 13 de 16 em E. E com 3 guardas, nenhuma das 139 mobilizadas ficou por resolver nesse ensaio.» |
| 10 | As três restrições, com a sugestão testada para cada uma | «Trocámos alguma deteção e rapidez por fiabilidade e por não ter um centro, e medimos quanto custou.» |

### O que os slides que saíram deixam por dizer

Os slides 12 e 13 (método e cenários) passaram para o apêndice. Três coisas que eles explicavam têm de ser ditas em voz alta:

1. **Antes do 7, numa frase:** «Corremos cinco cenários: A é o caso normal, B tem ruído, C tem falhas, D e E têm várias ameaças ao mesmo tempo. As mesmas sementes em todas as variantes.» Os nomes dos cenários já estão nas barras.
2. **No 7, ao falar de falsos alarmes:** «Recall é a fração das ameaças reais que mobilizaram; FPR é a fração dos episódios sem ameaça que mobilizaram por engano.» O 8 usa os dois.
3. **No 6 ou no 9, para P3 computacional:** «Pedindo propostas só às 2 patrulhas mais próximas, uma ocorrência custa 15 mensagens com qualquer número de patrulhas.» O detalhe está no 16.

### Avisos para quem fala

1. **Slide 8:** dizer em voz alta que a variante sem corroboração também desce o limiar para 0,01. A diferença junta as duas mudanças.
2. **Slides 7 e 9:** os números de D e E são de uma recolha. Ao repetir, E fechou entre 132 e 139 de 160; as 40 confirmadas de D repetiram-se sempre. A ordem na fila depende do relógio real.
3. **Os slides 4 e 8 mostram vencedores diferentes.** Na demonstração ninguém leva carga e ganha o drone, que está mais perto. No cenário A o drone leva carga 0,5 e ganha o veículo. Não é contradição: é a função de custo.
4. **P3:** os limites de `flood` e a redução de respostas 5 → 1 são históricos, anteriores à validação temporal atual. A reserva local atómica garante exclusividade; `STATUS` comunica-a.
5. **Sugestões:** 139 foi o melhor total observado, não um máximo geral. Quatro guardas mantiveram esse total, reduziram o último fecho médio (102,6 → 94,1 s) e aumentaram o tráfego (1148,9 → 1163,5 mensagens). A coluna temporal de `sugestoes.csv` tem unidades estatísticas diferentes entre grupos; ver [folha P3](p3-escalabilidade.md#sugestões-testadas).
6. **Proveniência de D:** o manifesto tem `dirty: true`; o commit registado não recupera integralmente o estado da recolha. Esta limitação não prova invalidade dos resultados.
7. **Sensibilidade (apêndice, 14):** o limiar do guarda 0,5 mantém a classificação em A e reduz tempo e energia, mas deixa só 4 verificações confirmadas e atualizações de reputação; em C reduz o recall. Não generalizar o benefício de A a falsos alarmes.

## Apêndice (slides 11 a 16)

O 11 é o separador: lista os cinco seguintes com o número de cada um. Na apresentação, parar no 10. Numa pergunta, saltar diretamente para o número.

| # | Slide | Saltar para aqui quando perguntarem | Fonte dos números |
|---|---|---|---|
| 11 | Apêndice (separador) | — | — |
| 12 | Percurso da Exploração | «Como avaliaram?», «O que é recall e FPR?» | [evaluation.md](../evaluation.md) |
| 13 | Os Cinco Cenários | «O que muda entre os cenários?» | `config/scenarios/` |
| 14 | Sensibilidade dos Parâmetros | «Os resultados dependem dos limiares que escolheram?» | [sensitivity.md](../sensitivity.md#resultados-por-parâmetro) |
| 15 | Testes de Stress | «Onde é que o sistema parte?», «Como trataram as mensagens perdidas?» | [scalability.md](../scalability.md#mapa-de-limites) |
| 16 | Escalabilidade Computacional | «E com muitas patrulhas?», «Quantas mensagens custa?» | [p3-escalabilidade.md](p3-escalabilidade.md), [scalability.md](../scalability.md#custo-computacional-scalecsv) |

As notas do 12 dizem «os slides seguintes seguem esta ordem». Isso era da ordem antiga: ignorar.

## Demonstração (slide 4)

O vídeo é `results/demo/mvp.mp4` (25 s, relatório do `run_mvp`, semente 6). Se não tocar, reproduzir no terminal, sem Python nem SPADE:

```bash
scriptreplay --log-timing results/demo/replay.tim --log-out results/demo/replay.log
```

Para perguntas sobre várias ocorrências há uma segunda gravação, com o [cenário D](../scalability.md#cenário-d--dia-movimentado):

```bash
scriptreplay --log-timing results/demo/replay-d.tim --log-out results/demo/replay-d.log
```

## O que mudou em relação à versão de 15 slides

Nenhum slide foi apagado nem reescrito: mudou a ordem e entrou o separador.

| Antes | Agora |
|---|---|
| 1 a 6 (capa ao Protocolos) | 1 a 6, iguais |
| 7 Percurso da Exploração, 8 Os Cinco Cenários | Apêndice, 12 e 13 |
| 9 Resultados, 10 Valor | 7 e 8 |
| 11 Sensibilidade, 12 Stress, 13 Escala Computacional | Apêndice, 14, 15 e 16 |
| 14 Escala Situacional, 15 Conclusões | 9 e 10 |
| — | 11, separador do apêndice |

---

## Para o grupo — não dizer na apresentação

### O trabalho numa frase

Simulámos uma reserva onde sensores com ruído detetam possíveis caçadores e, sem ninguém a mandar em todos, pedem a um drone ou a um veículo que vá confirmar e a um guarda que vá intervir.

### Como corre uma ocorrência, em linguagem simples

1. O ambiente cria um evento numa célula do mapa (uma ameaça, um trovão, um turista ou nada).
2. O `sensor-1` ouve algo e gera um alerta. Pode falhar (não ouvir) ou enganar-se (ouvir um trovão).
3. O `sensor-1` pergunta ao `sensor-2`: «também viste?». É o FIPA Request.
4. Com a resposta, calcula um score. Se passar o limiar, decide mobilizar.
5. Pede propostas ao drone e ao veículo (Contract Net). Cada um responde com o seu tempo, energia e carga, ou recusa. Ganha o de menor custo.
6. O vencedor confirma a reserva (`STATUS`), vai à célula e diz se viu a ameaça.
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
- **Contract Net:** leilão de uma ronda. Quem precisa pede propostas (`cfp`), os outros propõem (`propose`) ou recusam (`refuse`), e um é aceite.
- **B1:** o nome que demos à arquitetura na proposta. Quer dizer só «quem deteta coordena a sua ocorrência».
- **Recall:** das ameaças reais, quantas mobilizámos. Alto é bom.
- **FPR:** dos episódios sem ameaça, em quantos mobilizámos por engano. Baixo é bom.
- **Unresolved (por resolver):** ocorrência que ficou a meio, em geral por uma mensagem perdida.
- **Variante:** o mesmo cenário com uma peça desligada, para ver o que ela faz.
- **Coordenadas (x, y):** coluna primeiro, linha depois, a contar do canto de baixo à esquerda. A ameaça da demonstração está em (3,2).

### O que os números querem mesmo dizer

- **«17 de 20» em A:** das 3 que faltam, 1 foi o sensor que não ouviu e 2 foi o `sensor-2` que não confirmou. Não é falha de coordenação.
- **«2 de 20» em B:** mobilizámos 13. Em 11, o erro de posição de uma célula mandou a patrulha para a célula ao lado, e ela não viu nada. O sistema decidiu bem e foi ao sítio errado.
- **«6 de 20» em C:** o drone tem 15 % de energia e recusa, por isso só o veículo pode ir. Com um só candidato, qualquer mensagem perdida deixa a ocorrência por resolver (10 de 20).
- **FPR 0,75 → 0,25 em B:** em 40 episódios sem ameaça, passámos de 30 para 10 mobilizações erradas. As 10 que sobram são todas do episódio com trovão e turista juntos: dois enganos de fontes diferentes parecem confirmar-se.
- **«40 de 60» em D:** faltam 8 sem alerta, 4 sem corroboração, 3 em que a ameaça curta expirou antes de a patrulha sair e 5 em que acabou antes de ela chegar.
- **«132 de 160» em E:** faltam 8 sem alerta, 13 sem corroboração e 7 que a patrulha confirmou mas a que nenhum guarda pôde ir, por falta de autonomia.
- **Informador humano em E:** onde corrobora uma câmara fecham 72 de 80; onde corrobora um humano, 60 de 80 (`results/scenario-e/informants.csv`).

### Os pontos fracos, para não sermos apanhados de surpresa

- **A reputação quase não faz nada.** Com e sem ela, mudou 1 decisão em 140 execuções. Só pesa a partir de 0,83 e só aprende com confirmações.
- **O custo composto não se consegue justificar com dados.** O simulador não penaliza a carga, e o mais próximo verifica antes (4 s contra 6 s).
- **A comparação com e sem corroboração não é limpa.** A variante sem corroboração também tem o limiar mais baixo (0,01).
- **Os scores não são probabilidades.** 0,40 não quer dizer 40 % de hipótese de ameaça.
- **As falhas são simuladas em memória,** e todos os agentes correm no mesmo processo.
- **Poucas repetições:** 20 sementes em A, B e C; 10 em D, E e na maioria dos testes de stress. Sem intervalos de confiança.
- **D e E são um pico:** as ameaças começam todas no mesmo instante. E os números variam um pouco entre recolhas.
- **Em A, B e C só o `sensor-1` inicia:** uma ameaça que só o `sensor-2` alcança não gera alerta.
- **Um candidato calado custa tempo:** cada ronda espera o prazo inteiro (1,5 → 5,5 s reais em 10 execuções).

### Perguntas prováveis e resposta curta

As respostas longas, com alternativas e limites, estão em `temp/perguntas-defesa.md` (Parte 0). Entre parênteses, o slide para onde saltar.

- **«O sensor-1 não é um despachante disfarçado?»** (3) Não. Coordena só a sua ocorrência, não conhece o estado dos recursos e não os pode obrigar: eles recusam. Em E há 16 coordenadores ao mesmo tempo.
- **«Porquê Contract Net e não um leilão de várias rondas?»** (6) Uma ronda custa até 3N + 2 mensagens e chega. Várias rondas seriam mais lentas, e não temos pagamentos para um Vickrey.
- **«Porquê Request e não Subscribe?»** (6) Uma pergunta e uma resposta, com um prazo simples. O Subscribe traria evidência posterior, com mais mensagens.
- **«Isto é BDI?»** (5) Não. É híbrido: reativo nos sensores, com estado e uma função de custo nos recursos.
- **«Onde está a autonomia?»** (5) No recurso: decide se propõe, conta a energia de ida e volta e pode negar a reserva mesmo depois de aceite.
- **«E se o sensor que coordena falhar?»** O recurso acaba a missão e liberta-se sozinho. A ocorrência fica por resolver; ninguém a assume.
- **«Reenviam mensagens perdidas?»** (15) Sim, como opção: o mesmo pedido, com o mesmo identificador. Está ligado em E e nos testes de stress, não em A, B e C.
- **«E com muitas patrulhas?»** (16) Pedindo só às 2 mais próximas, 15 mensagens por ocorrência com qualquer N; antes eram 57 com 16 patrulhas.

### Antes de apresentar

- Partilhar a ligação dos slides e exportar o PDF para `docs/presentation/`.
- Abrir o slide 4 e confirmar que o vídeo toca no computador da apresentação.
- Deixar um terminal aberto na pasta do projeto, com o comando do `scriptreplay` pronto.
- Ensaiar uma vez com cronómetro, parando no 10: o 5 e o 8 são os que mais derrapam.
- Ensaiar uma vez o salto para o apêndice (ir do 10 ao 16 e voltar).
