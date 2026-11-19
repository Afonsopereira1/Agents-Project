# Roteiro da apresentação

## Em resumo

- **Diapositivos:** <https://claude.ai/artifact/1Sn3z364MWc1cbjCLoVQUU>. São 15, para **10 minutos**, com notas do orador em cada um.
- **A história:** um alerta na reserva → a ideia (quem deteta coordena) → ver a funcionar → como é feito → como o explorámos (cenários, resultados, valor de cada peça, sensibilidade, stress, escala) → o que aprendemos.
- **As 3 perguntas do professor** têm diapositivo próprio: P1 no 5, P2 no 3 e no 6, P3 no 13 e no 14.
- **Números:** todos conferidos com os CSV de `results/` a 18-11-2026.

A ligação é privada até ser partilhada no menu Share. Para a entrega, exportar para PDF ou PowerPoint (Share › Export) e guardar em `docs/presentation/`. A versão anterior, com 18 diapositivos e 14 minutos, continua em <https://claude.ai/artifact/8unfFKR29LmPhbGwdKwggj>.

**Grupo, por ordem alfabética:** Afonso Pereira, Guilherme Gomes e Guilherme Kotchergenko.

## Ordem e tempos

Os tempos somam 9:50. Sugestão de divisão: diapositivos 1 a 6 (o sistema), 7 a 11 (a exploração e o valor) e 12 a 15 (stress, escala e fecho), um bloco por elemento. Os diapositivos 8, 11 e 12 são para passar depressa: diz-se a conclusão, não se lê o conteúdo.

| # | Diapositivo | Tempo | Responde a | Fonte dos números |
|---|---|---|---|---|
| 1 | Capa | 0:20 | — | — |
| 2 | O Problema | 0:40 | — | enunciado |
| 3 | A Ideia: Quem Deteta Coordena | 0:50 | **P2** (arquitetura) | [architecture.md](../architecture.md) |
| 4 | Uma Ocorrência do Alerta ao Fecho | 0:45 | — | `results/demo/mvp.json` |
| 5 | Construção dos Agentes | 0:50 | **P1** | [architecture.md](../architecture.md), [p1-agentes.md](p1-agentes.md) |
| 6 | Protocolos | 0:45 | **P2** (protocolos) | [protocols.md](../protocols.md), [p2-protocolos.md](p2-protocolos.md) |
| 7 | Percurso da Exploração | 0:30 | — | [evaluation.md](../evaluation.md) |
| 8 | Os Cinco Cenários | 0:30 | — | `config/scenarios/` |
| 9 | Resultados por Cenário | 0:40 | — | [experiments.md](../experiments.md#resultados), [scalability.md](../scalability.md#cenário-d--dia-movimentado) |
| 10 | Valor de Cada Peça | 0:50 | — | [experiments.md](../experiments.md#discussão) |
| 11 | Sensibilidade dos Parâmetros | 0:30 | — | [sensitivity.md](../sensitivity.md#resultados-por-parâmetro) |
| 12 | Testes de Stress | 0:35 | **P3** (apoio) | [scalability.md](../scalability.md#mapa-de-limites) |
| 13 | Escalabilidade Computacional | 0:40 | **P3** | [p3-escalabilidade.md](p3-escalabilidade.md), [scalability.md](../scalability.md#custo-computacional-scalecsv) |
| 14 | Escalabilidade Situacional | 0:40 | **P3** | [scalability.md](../scalability.md#escalabilidade-situacional-distcsv) |
| 15 | Conclusões e Limites | 0:45 | — | os anteriores |

## O que dizer em cada diapositivo

As falas são guias, não texto para ler. O texto completo está nas notas do orador de cada diapositivo. Aqui fica só a ideia e a frase que não pode faltar.

| # | A ideia | A frase que não pode faltar |
|---|---|---|
| 1 | Três coisas em dez minutos | «O que construímos, como o explorámos e o que cada peça vale.» |
| 2 | Um tiro, três restrições | «Alguém tem de ir ver, e o enunciado diz que ninguém pode mandar.» |
| 3 | Três arquiteturas, uma escolha | «Quem deteta coordena a sua ocorrência; o preço é não haver ótimo global.» |
| 4 | Ver antes de explicar | «15 mensagens, verificação aos 4 s, fecho aos 10 s.» |
| 5 | Três camadas | «Os comportamentos só comunicam; as decisões são funções puras, por isso 560 testes correm sem servidor.» |
| 6 | Dois protocolos e uma extensão | «Uma ronda, até 3N + 2 mensagens, e é o recurso que decide.» |
| 7 | A viragem da história | «Funcionava num caso. Fomos à procura de onde deixava de funcionar.» |
| 8 | O mapa para ler os resultados | «Cada cenário testa uma coisa: o caso base, o ruído, as falhas e a escala.» |
| 9 | Três histórias, não cinco barras | «Em C, basta uma mensagem perdida para travar a ocorrência.» |
| 10 | Como funciona cada peça, antes e depois | «Três peças provaram valor; duas ainda não, e dizemo-lo.» |
| 11 | Depende dos valores escolhidos? | «Quase não: 55 de 75 combinações não mudaram nenhuma mobilização.» |
| 12 | Onde partia e o que mudámos | «Contar só os três cartões com contorno: fila, gravidade e reenvio.» |
| 13 | O custo deixa de crescer | «Das 57 mensagens, 50 eram para negociar com 16 patrulhas; pedindo só a 2, ficam 8.» |
| 14 | Antes, depois e sugestão testada | «Antes a parte cheia não crescia; agora acompanha: 13 de 16 em E. E com 3 guardas, nenhuma das 139 mobilizadas ficou por resolver nesse ensaio.» |
| 15 | As três restrições, com a sugestão testada para cada uma | «Trocámos alguma deteção e rapidez por fiabilidade e por não ter um centro, e medimos quanto custou.» |

### Avisos para quem fala

1. **Diapositivo 10:** dizer em voz alta que a variante sem corroboração também desce o limiar para 0,01. A diferença junta as duas mudanças.
2. **Diapositivos 9 e 14:** os números de D e E são de uma recolha. Ao repetir, E fechou entre 132 e 139 de 160; as 40 confirmadas de D repetiram-se sempre. A ordem na fila depende do relógio real.
3. **Diapositivos 4 e 10 mostram vencedores diferentes.** Na demonstração ninguém leva carga e ganha o drone, que está mais perto. No cenário A o drone leva carga 0,5 e ganha o veículo. Não é contradição: é a função de custo.
4. **P3:** os limites de `flood` e a redução de respostas 5 → 1 são históricos, anteriores à validação temporal atual. A reserva local atómica garante exclusividade; `STATUS` comunica-a.
5. **Sugestões:** 139 foi o melhor total observado, não um máximo geral. Quatro guardas mantiveram esse total, reduziram o último fecho médio (102,6 → 94,1 s) e aumentaram o tráfego (1148,9 → 1163,5 mensagens). A coluna temporal de `sugestoes.csv` tem unidades estatísticas diferentes entre grupos; ver [folha P3](p3-escalabilidade.md#sugestões-testadas).
6. **Proveniência de D:** o manifesto tem `dirty: true`; o commit registado não recupera integralmente o estado da recolha. Esta limitação não prova invalidade dos resultados.
7. **Sensibilidade:** o limiar do guarda 0,5 mantém a classificação em A e reduz tempo e energia, mas deixa só 4 verificações confirmadas e atualizações de reputação; em C reduz o recall. Não generalizar o benefício de A a falsos alarmes.

## Demonstração (diapositivo 4)

O vídeo é `results/demo/mvp.mp4` (25 s, relatório do `run_mvp`, semente 6). Se não tocar, reproduzir no terminal, sem Python nem SPADE:

```bash
scriptreplay --log-timing results/demo/replay.tim --log-out results/demo/replay.log
```

Para perguntas sobre várias ocorrências há uma segunda gravação, com o [cenário D](../scalability.md#cenário-d--dia-movimentado):

```bash
scriptreplay --log-timing results/demo/replay-d.tim --log-out results/demo/replay-d.log
```

## O que mudou em relação à versão de 18 diapositivos

Três diapositivos vieram da versão anterior quase iguais: Os Cinco Cenários (8), Sensibilidade dos Parâmetros (11) e Testes de Stress (12). O resto foi reorganizado; nada se perdeu.

| Antes | Agora |
|---|---|
| Arquitetura (diagrama de componentes) | Diapositivo 3, como comparação de três arquiteturas |
| Decisão dos Agentes (score, custo, reputação) | Notas do 5 e do 10; detalhe em [reputation-policy.md](../reputation-policy.md) |
| SPADE e Falhas | Diapositivo 5 (SPADE) e cartão do reenvio no 12 |
| Método, As Quatro Variantes | Diapositivo 7; detalhe em [experiments.md](../experiments.md) |
| Comparação entre Variantes, Ponderações | Diapositivo 10, em «antes · sem a peça» e «depois · com a peça» |
| Conclusões | Diapositivo 15, agora ligado às três restrições do diapositivo 2 |

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

As respostas longas, com alternativas e limites, estão em `temp/perguntas-defesa.md` (Parte 0).

- **«O sensor-1 não é um despachante disfarçado?»** Não. Coordena só a sua ocorrência, não conhece o estado dos recursos e não os pode obrigar: eles recusam. Em E há 16 coordenadores ao mesmo tempo.
- **«Porquê Contract Net e não um leilão de várias rondas?»** Uma ronda custa até 3N + 2 mensagens e chega. Várias rondas seriam mais lentas, e não temos pagamentos para um Vickrey.
- **«Porquê Request e não Subscribe?»** Uma pergunta e uma resposta, com um prazo simples. O Subscribe traria evidência posterior, com mais mensagens.
- **«Isto é BDI?»** Não. É híbrido: reativo nos sensores, com estado e uma função de custo nos recursos.
- **«Onde está a autonomia?»** No recurso: decide se propõe, conta a energia de ida e volta e pode negar a reserva mesmo depois de aceite.
- **«E se o sensor que coordena falhar?»** O recurso acaba a missão e liberta-se sozinho. A ocorrência fica por resolver; ninguém a assume.
- **«Reenviam mensagens perdidas?»** Sim, como opção: o mesmo pedido, com o mesmo identificador. Está ligado em E e nos testes de stress, não em A, B e C.

### Antes de apresentar

- Partilhar a ligação dos diapositivos e exportar o PDF para `docs/presentation/`.
- Abrir o diapositivo 4 e confirmar que o vídeo toca no computador da apresentação.
- Deixar um terminal aberto na pasta do projeto, com o comando do `scriptreplay` pronto.
- Ensaiar uma vez com cronómetro: os diapositivos 5 e 10 são os que mais derrapam; o 8, o 11 e o 12 passam-se depressa.
