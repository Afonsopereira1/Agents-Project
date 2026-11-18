# Notas para a apresentação — testes de stress e mecanismos

> Notas de apoio para quem fala, não são diapositivos. Os números estão em [p3-escalabilidade.md](p3-escalabilidade.md); a explicação e as tabelas completas em [scalability.md](../scalability.md#testes-de-stress-bloco-f).

## Em resumo

- Antes dizíamos «o sistema foi desenhado para aguentar falhas». Agora dizemos «aguenta até aqui e deixa de funcionar aqui», com números.
- Cada fraqueza medida deu origem a um mecanismo, e cada mecanismo tem um «antes e depois» no mesmo teste.
- Duas garantias mantiveram-se em todos os testes: zero reservas duplas e zero agentes parados por exceção.
- Tudo foi medido no transporte local, com 5 a 20 execuções por ponto.

## O que está ligado

- **Por omissão em `run_mvp`:** prazo dinâmico (teto de 2,0 s), fila (60 tentativas) e silêncio perante `ACCEPT` incoerente.
- **Nos cenários A, B e C e nas medições base:** nada. O coletor e os scripts passam `PUBLISHED_CONDITIONS`, para os resultados publicados continuarem reproduzíveis.
- **No cenário D:** as três de cima, mais a fila por gravidade, o prazo de validade, o `busy_until` e as missões encadeadas.
- **No cenário E:** tudo o que o D liga, mais o reenvio e o aviso entre iniciadores.
- **Em nenhum cenário:** o CFP só aos K mais próximos.

## As três opções ligadas por omissão

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

## O que dizer de cada mecanismo

| Mecanismo | Uma frase | O preço |
|---|---|---|
| CFP aos K mais próximos | «Chamando só as duas patrulhas mais próximas, o custo fica em 15 mensagens, haja 2 ou 16 patrulhas.» | Usa a posição base; só foi medido com uma ocorrência |
| Prazo dinâmico | «Com uma proposta na mão avança ao fim de 0,5 s; sem nenhuma, espera até 2 s. Um atraso de 1,5 s deixa de ser uma falha.» | Quando ninguém responde, falhar demora 2,0 s em vez de 0,5 s |
| Vários iniciadores | «Cada sensor que ouve uma ameaça abre a sua ocorrência; não há despachante a distribuir.» | Sem fila, só fecha uma por execução, porque há um guarda |
| Fila | «Um recurso ocupado deixa de ser uma ocorrência perdida: com 8 ao mesmo tempo fecham as 8, em vez de 1.» | Quase o triplo das mensagens (352 contra 123); a última fecha aos 80 s em vez de 12 s |
| Fila por gravidade | «As graves fecham três vezes mais cedo, com as mesmas mensagens; quem paga são as leves.» | Leves: 27 s → 76 s. Não interrompe missões |
| Prazo de validade | «Antes de voltar a pedir, o iniciador relê o sensor; se a ameaça já lá não está, não manda ninguém.» | Não salva nenhuma ocorrência, só evita a viagem |
| Recurso diz quando fica livre | «A recusa leva a hora a que o recurso prevê ficar livre, e o iniciador espera até lá.» | Ganho pequeno: menos 8 % de mensagens |
| Encadear missões | «O recurso aceita a missão seguinte no regresso, sem voltar à base: o último fecho passa de 81 s para 54 s.» | Mais tempo fora da base, sem recarga |
| Silêncio | «Um `ACCEPT` que não bate com a proposta fica sem resposta: menos 80 % de respostas a lixo.» | Um iniciador com um erro vê silêncio em vez de «reserva falhada» |
| Reenvio | «O iniciador reenvia a mesma mensagem, com o mesmo identificador: com 10 % de perda fecham 17 de 20, como sem perda.» | Com 30 % de perda ainda ficam 7 por resolver |
| Aviso entre iniciadores | «Os sensores vizinhos avisam-se e só o que ouviu primeiro trata a ameaça: 40 idas de patrulha passam a 10.» | Um aviso perdido volta a duplicar |
| Informadores humanos | «Um relato humano fiável corrobora como uma câmara; o que conta é a fiabilidade, não o tipo de fonte.» | Respondem no mesmo instante; não medimos falsos relatos |

## A história da fila em quatro passos

1. **O que encontrámos.** Com 8 ocorrências ao mesmo tempo, só 1 fechava. As outras encontravam o guarda ocupado e ninguém o voltava a chamar.
2. **O que fizemos.** Uma fila: o iniciador espera e volta a pedir. Passaram a fechar as 8, sem reservas duplas.
3. **O que a fila revelou.** Atender todas não é atender a tempo: com ameaças de 30 s, só 20 de 80 têm o guarda no local antes de a ameaça terminar, e 40 patrulhas chegam em vão.
4. **O que fizemos a seguir.** Ordem por gravidade, prazo de validade, mais guardas, o recurso a dizer quando fica livre e missões encadeadas, cada uma medida no mesmo teste.

**Frase para dizer:** «A fila troca "não atendida" por "atendida mais tarde". As mitigações aproximam-na de "atendida a tempo".»

**Como se resolve a disputa quando o guarda fica livre.** Os iniciadores em espera voltam a enviar o CFP. Sem ordem por gravidade, o guarda faz proposta a todos e reserva para o primeiro `ACCEPT` que lê; os outros recebem `STATUS` com `reservation_failed` e voltam à fila. Com ordem por gravidade, o guarda só faz proposta ao primeiro da sua lista. Nos dois casos, é o `STATUS` que impede a reserva dupla.

## Perguntas prováveis

| Pergunta | Resposta curta |
|---|---|
| Porque não aumentaram simplesmente o prazo? | Um prazo fixo maior atrasa todas as rondas em que um candidato se cala. O dinâmico só espera mais quando não tem nenhuma proposta; quando tudo corre bem, o tempo é igual. |
| 2 s não é lento? | Só quando ninguém responde, e uma ocorrência demora pelo menos 12 s simulados a fechar. |
| Porque é que o teto é 2 s? | É uma troca medida: o teto é o maior atraso tolerado e também o tempo perdido quando ninguém responde ([tabela](../scalability.md#que-teto-escolher)). 2 s é o prazo que já usamos na rede XMPP. |
| Como garantem que dois iniciadores não reservam o mesmo guarda? | Pelo `STATUS`: o recurso só confirma uma reserva de cada vez. Zero reservas duplas em todos os testes. |
| O sistema aguenta ataques? | Até 300 mensagens inválidas por cada mensagem real, nenhuma decisão muda e nenhum agente termina com exceção. Não há autenticação: um atacante com credenciais válidas não é detetado. |
| Quantos agentes aguenta? | Medimos até 16 patrulhas e, no cenário E, 16 iniciadores, 4 informadores e 6 recursos. O que cresce é o custo da fila: 78 mensagens por ocorrência em E, contra 15 com uma só. |
| Onde está o gargalo? | Nos recursos. Com um guarda, é o guarda; com dois, passam a faltar patrulhas; no cenário E, é a autonomia dos guardas que acaba. |
| Porque não está tudo ligado em A, B e C? | Cada execução tem uma só ocorrência e nenhuma mensagem inválida: a fila e o silêncio não atuariam. Mantê-los desligados deixa os resultados publicados reproduzíveis. |
| Os resultados repetem-se? | Sem fila, sim: `scale.csv` e `dist.csv` foram gerados de novo com o código atual e saíram iguais. Com fila, a ordem dos pedidos depende do relógio real: em E fecharam 132 numa recolha e 136 noutra. |
| Isto foi testado na rede XMPP? | Não. As falhas são injetadas no transporte local, e o SPADE entrega em memória as mensagens entre agentes do mesmo processo. |
| E se todas as ameaças forem graves? | A ordem deixa de distinguir e vale o tempo de espera. Com graves a chegar sem parar, as leves nunca seriam atendidas: é um limite assumido. |
| Porque ainda se chama «MVP»? | É o nome da Etapa 6. A função `run_mvp` ficou; mudar o nome mexe em dezenas de testes e não muda nenhum comportamento. |

## O que não afirmar

- **«Mesma decisão» com o CFP limitado.** O resultado é o mesmo (10 de 10 fechadas aos 12 s). Com 16 patrulhas, a patrulha escolhida não é a mesma: tem o mesmo custo.
- **«O ponto (6,6) está fora do alcance dos dois sensores.»** Está fora do alcance do `sensor-1`; o `sensor-2` alcança-o, como ao ponto (7,0).
- **«O prazo dinâmico aguenta até 2,0 s de atraso.»** O que medimos: 1,5 s passa e 2,5 s falha. 2,0 s é o teto configurado.
- **«Com reenvio é mais rápido.»** Os tempos reais dos testes de perda são anteriores a uma alteração do código e não foram medidos de novo.
- **«67 % em D e 83 % em E» sem dizer de quê.** São ameaças fechadas como confirmadas: 40 de 60 e 132 de 160. Por ocorrência com alerta são 45 de 52 e 132 de 152 fechadas.
- **Significância estatística.** São 5 a 20 execuções por ponto, sem intervalos de confiança.

## Trabalho futuro

1. Interromper uma missão leve quando chega uma ocorrência grave, e não deixar as leves à espera para sempre.
2. Patrulhas e guardas a variar em conjunto, com autonomia e carga próprias.
3. Atrasos reais na rede XMPP: pedem agentes em processos separados.
4. Prazo que se ajusta sozinho aos tempos de resposta observados.
5. Ameaças espaçadas no tempo e relatos atrasados dos informadores.
