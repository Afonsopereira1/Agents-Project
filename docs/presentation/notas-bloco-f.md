# Notas para a apresentação — Bloco F e as três melhorias

> Notas de apoio, não são diapositivos. Os números e as tabelas completas estão em [scalability.md](../scalability.md#testes-de-stress-bloco-f).

## Numa frase

Antes dizíamos «o sistema foi desenhado para aguentar falhas». Depois do Bloco F dizemos «aguenta até aqui, e deixa de funcionar aqui», com números.

## Para que serviu o Bloco F

1. **Respostas medidas para a banca:** perda, atraso, falta de recursos, várias ocorrências e mensagens falsas, cada uma com o ponto onde o sistema deixa de atender.
2. **Três fraquezas que não se viam:** o prazo fixo de 0,5 s (passa de «funciona sempre» a «nunca funciona»), o guarda único (só fecha uma ocorrência por janela) e as respostas a mensagens inválidas.
3. **Duas garantias provadas:** zero reservas duplas e zero agentes parados por exceção, mesmo com falhas combinadas e milhares de mensagens inválidas.
4. **Escalabilidade com «antes e depois»:** com 16 patrulhas, 57 mensagens sem limite contra 15 com `cfp_limit=2` (C1).
5. **Repete-se:** mesmas sementes e clone limpo dão os mesmos resultados.

## As três melhorias

Desde 18-11-2026 as três estão ligadas por omissão em `run_mvp` (`max_receive_timeout=2.0`, `queue_rounds=60`, `silent_invalid=True`). As recolhas publicadas continuam nas condições antigas (`PUBLISHED_CONDITIONS`), por isso os resultados não mudaram.

```
 CFP ──► proposta em 0,5 s? ──sim──────────────────► ACCEPT ──► STATUS até 2,0 s?
            │ não                                         │           │      │      │
            ▼                                             │      reservado falhou  nada
         proposta até 2,0 s? ──sim────────────────────────┘           │      │      │
            │ não                          (1) PRAZO DINÂMICO          ▼      │      ▼
            ▼                                                     MISSÃO     │   NÃO RESOLVIDA
         recurso ocupado? ──não──► NÃO RESOLVIDA                             │
            │ sim                                                            │
            ▼                                                                │
         espera 5 s simulados e volta ao CFP ◄───────────────────────────────┘
                                   (2) FILA

 (3) SILÊNCIO: o recurso não responde a um ACCEPT que não bate com a proposta que fez.
```

### (1) Prazo dinâmico

- **Como funciona:** com uma proposta na mão ao fim de 0,5 s, avança como antes. Sem nenhuma, espera até 2,0 s. O `STATUS` espera sempre até 2,0 s, porque depois do `ACCEPT` não há outro recurso para tentar.
- **Ganho:** aguenta atrasos até 2,0 s (antes 0,5 s) e 5000 mensagens inválidas por mensagem real (antes 1000).
- **Custo:** quando ninguém responde, a ocorrência só é dada como não resolvida ao fim de 2,0 s, em vez de 0,5 s. Quando há resposta, o tempo é igual.
- **Porque 2 s não pesam:** uma ocorrência demora pelo menos 12 s simulados a fechar e, num caso real, deslocar um veículo demora minutos.
- **O teto é uma troca, não um ótimo:** é o maior atraso que se tolera e também o tempo perdido quando ninguém responde. Proposta: 2,0 s, o prazo que o projeto já usa na rede XMPP.

### (2) Fila para recursos ocupados

- **Como funciona:** «recurso ocupado» deixa de ser falha. O iniciador espera 5 s simulados e volta a enviar o `CFP`, até `queue_rounds` vezes.
- **Ganho:** com 8 ocorrências ao mesmo tempo, fecha as 8 em vez de 1, sem duplas reservas.
- **Custo:** quase o triplo das mensagens (352 contra 123), e a última ocorrência fecha aos 80 s simulados em vez de 12 s.

**Como se resolve a disputa quando o guarda fica livre.** Todos os iniciadores em espera voltam a enviar o `CFP` mais ou menos ao mesmo tempo. O guarda, livre, faz proposta a todos; cada iniciador envia o seu `ACCEPT`. O guarda reserva para o primeiro `ACCEPT` que lê e responde `STATUS(reservation_failed)` aos outros, que voltam à fila. Não há sorteio nem ordem de chegada: ganha quem chega primeiro naquele instante. O `STATUS` é o que impede a reserva dupla.

**Problemas de ficar muito tempo na fila** (medições e soluções na secção [A fila: o que aconteceu e o que propomos](#a-fila-o-que-aconteceu-e-o-que-propomos)):

- **A ameaça pode já não estar lá.** O iniciador não volta a confirmar a ameaça quando chega a sua vez; o guarda pode ir a uma célula vazia.
- **Uma ocorrência pode perder sempre.** Sem ordem de chegada, nada impede que perca todas as disputas até esgotar as tentativas e terminar como não resolvida, muito mais tarde.
- **Sem prioridade:** uma ocorrência grave pode esperar atrás de uma ligeira.
- **Tráfego:** cada ocorrência em espera envia um `CFP` a cada candidato de 5 em 5 s, e cada candidato ocupado responde com uma recusa.
- **Não resolve a causa:** o gargalo continua a ser o guarda único; a fila troca «não atendida» por «atendida mais tarde».

### (3) Silêncio perante `ACCEPT` incoerente

- **Como funciona:** se o `ACCEPT` não bate com a proposta que o recurso fez (IDs trocados, data no futuro), o recurso regista um aviso e não responde. Um iniciador legítimo nunca envia um `ACCEPT` assim.
- **Ganho:** menos 80 % de respostas a mensagens inválidas, com o mesmo resultado.
- **Custo:** um iniciador com um erro de programação deixa de receber «reserva falhada» e passa a ver silêncio, o que é mais difícil de diagnosticar.

## A fila: o que aconteceu e o que propomos

### A história em quatro passos (cabe num diapositivo)

1. **O que encontrámos.** Com 8 ocorrências ao mesmo tempo, só 1 fechava. As outras 7 terminavam como não resolvidas, porque encontravam o guarda ocupado e ninguém o voltava a chamar.
2. **O que fizemos.** Uma fila: recurso ocupado deixa de ser falha; o iniciador espera e volta a pedir. Passaram a fechar as 8, sem reservas duplas.
3. **O que a fila revelou.** Atender todas não é o mesmo que atender a tempo. Medimos com ameaças que duram pouco ([espera.csv](../../results/stress/espera.csv)).
4. **O que fizemos a seguir.** Cinco mitigações, cada uma para um problema medido (tabela abaixo), todas feitas e medidas até 18-11-2026.

**Frase para dizer:** «A fila troca "não atendida" por "atendida mais tarde". O passo seguinte é garantir "atendida a tempo".»

### O que medimos (8 ocorrências com fila, 80 ocorrências por linha)

| Duração da ameaça | Confirmadas | Patrulhas em vão | Guarda chega depois do fim |
|---|---|---|---|
| 1000 s | 80 | 0 | 0 |
| 60 s | 54 | 10 | 16 |
| 30 s | 20 | 40 | 20 |

Com ameaças de 30 s, só 20 das 80 ocorrências têm o guarda no local a tempo. (Medição repetida a 18-11-2026: o guarda que chega tarde já não conta como confirmada.)

### Problema, evidência e solução

| Problema | O que medimos | Solução | Resultado medido (18-11-2026) |
|---|---|---|---|
| A ameaça já lá não está quando chega a vez | Com ameaças de 30 s, 41 de 80 patrulhas chegam em vão | **Prazo de validade:** antes de voltar a pedir, o iniciador relê o seu sensor; se já não vê a ameaça, desiste | Patrulhas em vão: 40 → 12; guarda em vão: 20 → 8 |
| O guarda único é o gargalo | O último fecho passa de 12 s para 80 s com 8 ocorrências | **Mais guardas:** medir 1, 2 e 4 guardas | Com 2 guardas, 1 pedido por ocorrência (antes 3,3); o último fecho só desce de 81 s para 68 s, porque passam a faltar patrulhas |
| Tráfego de quem espera | 352 mensagens contra 123; pede-se o guarda de 5 em 5 s | **O recurso diz quando fica livre:** a recusa leva a hora prevista e o iniciador espera até lá | Mensagens: 367 → 336; pedidos ao guarda: 3,2 → 2,6 |
| Sem ordem nem prioridade | Uma ocorrência chega a pedir o guarda 15 vezes (média 2,9); a gravidade não conta | **Ordem na fila:** primeiro a mais grave; em caso de empate, a que espera há mais tempo | **Feito** (ver abaixo) |
| O guarda volta à base entre missões | Cerca de 10 s simulados a mais por cada ocorrência à frente | **Encadear missões:** aceitar a seguinte durante o regresso | Último fecho: 81 s → 54 s |

### Feito: fila ordenada por gravidade

- **Três níveis:** grave (gravidade a partir de 0,8), média (a partir de 0,4) e leve.
- **Como funciona:** cada recurso guarda a lista de quem espera e só faz proposta ao primeiro: o mais grave e, em caso de empate, o que espera há mais tempo. Os outros recebem uma recusa, mesmo com o recurso livre. Não há mensagens novas.
- **Resultado** (2 graves, 3 médias e 3 leves ao mesmo tempo, [prioridade.csv](../../results/stress/prioridade.csv)):

| Gravidade | Fecho médio antes | Fecho médio depois |
|---|---|---|
| Grave | 73,5 s | **22,8 s** |
| Média | 46,7 s | 46,7 s |
| Leve | 27,3 s | 75,9 s |

- **O que dizer:** «as graves fecham três vezes mais cedo, com as mesmas mensagens; quem paga são as leves».
- **O que não faz:** não interrompe uma missão em curso, e, com graves a chegar sem parar, as leves ficam à espera para sempre.

**Um limite do simulador, já corrigido:** a intervenção do guarda dava sempre «confirmada», mesmo que a ameaça já tivesse terminado. Desde 18-11-2026 o guarda que chega tarde devolve «não confirmada»; a Etapa 9 não mudou.

**Se perguntarem «e ligadas todas ao mesmo tempo?»:** é o [cenário D](../scalability.md#cenário-d--dia-movimentado): seis ameaças num mapa 12×8, seis iniciadores, quatro patrulhas e dois guardas. Em 10 execuções, nenhuma ocorrência ficou por resolver e não houve duplas reservas; as graves fecham em média aos 10 s e as leves aos 31 s. As mitigações estão desligadas por omissão; tabelas completas em [scalability.md](../scalability.md#mitigações-da-espera-na-fila-antes-e-depois).

## Porque estiveram desligadas por omissão até 18-11-2026

- **Não mudam os resultados oficiais.** Repetimos a recolha da Etapa 9 (560 execuções, cerca de 4,5 min) com as três ligadas: `summary.csv` e `runs.csv` saíram iguais, byte a byte.
- **Porque não mudam:** cada execução da Etapa 9 tem uma só ocorrência (o guarda nunca está ocupado, a fila nunca atua) e não tem mensagens inválidas (o silêncio nunca atua). As perdas do cenário C são perdas, não atrasos: uma mensagem perdida nunca chega, por isso esperar mais não ajuda.
- **O que mudaria:** 4 testes que verificam o comportamento antigo, as curvas do F1 (que passam a ser o «antes») e o contrato de mensagens, porque o silêncio troca uma resposta `reservation_failed` por nenhuma.
- **Porque não se ligou logo:** pela regra da [ata](../approvals.md), um valor aprovado não muda no código sem decisão do grupo; o prazo (item 5.1) estava em exploração no Bloco G.
- **Como se ligou:** os seis testes do comportamento antigo foram ajustados, e o coletor e os scripts de medição passam `PUBLISHED_CONDITIONS` (prazo fixo, sem fila, com resposta a `ACCEPT` incoerente). A alteração está registada na [ata](../approvals.md#registo-de-alterações-ao-código); a aprovação do item 5.1 continua por assinar.

## Porque ainda se chama «MVP»

- **É um nome histórico.** MVP (produto mínimo viável) foi o objetivo da Etapa 6: um alerta, corroboração, negociação, missão e fecho, sem despachante. Foi atingido a 12-11-2026.
- **Depois disso, tudo cresceu sobre o mesmo código:** reputação e política (Etapa 7), falhas (Etapa 8), cenários e avaliação (Etapa 9), stress (Bloco F). A função `run_mvp` e os nomes `sensor-mvp`, `drone-mvp` ficaram.
- **O que ainda é mínimo:** nos cenários A, B e C, mapa de 8×8, dois sensores, um guarda e uma ocorrência por janela (C7); todos os agentes no mesmo processo e transporte local por omissão. O [cenário D](../scalability.md#cenário-d--dia-movimentado) já lê o mapa, os sensores e os recursos do ficheiro de cenário.
- **Mudar o nome não vale a pena agora:** mexe em dezenas de testes e documentos e não muda nenhum comportamento.

## Perguntas prováveis da banca

| Pergunta | Resposta curta |
|---|---|
| Porque não aumentaram simplesmente o prazo? | Aumentar o prazo fixo atrasa todas as decisões. O dinâmico só espera mais quando não tem nenhuma resposta, e o tempo é igual quando tudo corre bem. |
| 2 s não é lento? | Só quando ninguém responde, e uma ocorrência demora pelo menos 12 s a fechar. Perder 2 s não muda o resultado. |
| Como garantem que dois iniciadores não reservam o mesmo guarda? | Pelo `STATUS`: o recurso só confirma uma reserva de cada vez. Medido: zero reservas duplas em todos os testes. |
| O sistema aguenta ataques? | Milhares de mensagens inválidas não mudam nenhuma decisão nem param nenhum agente. Não há autenticação: um atacante com credenciais válidas não é detetado. |
| Quantos agentes aguenta? | Medimos até 16 patrulhas e 8 sensores iniciadores. Com o limite de `CFP` (K = 2), as mensagens por missão não crescem com o número de patrulhas. O gargalo é o guarda único. |
| Porque é que o teto é 2 s? | É uma troca medida (tabela «Que teto escolher» em [scalability.md](../scalability.md#que-teto-escolher)), e é o prazo que já usamos na rede XMPP. |

## Trabalho futuro (para o último diapositivo)

1. Interromper uma missão leve quando chega uma ocorrência grave, e não deixar as leves à espera para sempre.
2. Patrulhas e guardas a variar em conjunto: com 2 guardas, o gargalo passa para as 2 patrulhas.
3. Atrasos reais na rede XMPP: pedem agentes em processos separados, porque o SPADE entrega em memória dentro do mesmo processo.
4. Prazo que se ajusta sozinho aos tempos de resposta observados.
