# Falhas, atrasos e escassez

[README](../README.md) · [Arquitetura](architecture.md) · [Protocolos](protocols.md) · [Escalabilidade](scalability.md)

> **Em resumo**
>
> - As falhas são injetadas **só no transporte local** de `run_mvp`: perda, atraso, duplicação, agente indisponível, recurso ocupado e mensagens inválidas. Os agentes não mudam.
> - As falhas de mensagens modeladas têm prazos e estados explícitos. Isto não garante recuperação após crash de processos ou exceções arbitrárias de transporte; estas podem abortar a execução.
> - Por omissão não há reenvio. Com `retransmit=1` e 10 % de perda, fecham 17 de 20 ocorrências em vez de 7.
> - Não há recuperação se o iniciador desaparecer, e a queda do servidor XMPP não é simulada.

Verificado contra o código em 18-11-2026 (branch `fix/auditoria-correcoes`).

## Como injetar

```bash
PYTHONPATH=src python -m isia.simulation.runner --faults config/faults.json > /tmp/isia-faults.json
PYTHONPATH=src python -m unittest tests.integration.test_faults -v
```

Em código: `run_mvp(faults={...})`. Com `--xmpp`, `--faults` é recusado: a injeção não toca no servidor XMPP nem o valida.

O ficheiro de exemplo ([config/faults.json](../config/faults.json)) deixa o drone indisponível, atrasa as propostas 0,05 s e duplica os resultados. A ocorrência fecha na mesma (`closed` / `confirmed`), com o veículo no lugar do drone.

## Parâmetros

| Chave | Efeito | Omissão |
|---|---|---|
| `seed` | Semente da perda aleatória | 0 |
| `loss` | Probabilidade de perder cada mensagem, em `[0, 1]` | 0 |
| `delay` | Atraso real em segundos por tipo, em `[0, 60[`. Exemplo: `{"PROPOSAL": 0.05}` | `{}` |
| `drop` | Tipos sempre perdidos. Exemplo: `["CFP"]` | `[]` |
| `duplicate` | Tipos entregues duas vezes. Exemplo: `["MISSION_RESULT"]` | `[]` |
| `unavailable_agents` | Agentes que não enviam nem recebem durante toda a execução | `[]` |
| `occupied_after_proposal` | Recursos que são reservados por outra missão logo depois de proporem | `[]` |
| `flood` | Por cada mensagem real, entrega ao mesmo destinatário N cópias inválidas de cada variante: JSON partido, IDs trocados e data fora de prazo | 0 |

Regras dos nomes (validadas em `fault_settings`, [runner.py](../src/isia/simulation/runner.py)); nomes desconhecidos são recusados:

- Os tipos são os de `MessageType`, em maiúsculas: `CFP`, `PROPOSAL`, `ACCEPT`, ...
- `unavailable_agents` usa a parte local do JID e só aceita os cinco agentes base: `sensor-mvp`, `sensor-peer-mvp`, `drone-mvp`, `vehicle-mvp`, `ranger-mvp`.
- `occupied_after_proposal` usa o ID do recurso e só aceita `drone`, `vehicle` e `ranger`.

Os agentes adicionais dos cenários D e E não podem, portanto, ser desligados nem ocupados individualmente; `loss`, `delay`, `drop` e `duplicate` aplicam-se a todos.

Pormenores do `flood`: o `CFP` não leva a variante de IDs trocados, porque seria um pedido válido. As respostas ao lixo não geram mais lixo. Medição em [scalability.md](scalability.md#testes-de-stress-bloco-f).

O relatório JSON regista `faults` (a configuração completa), `scenario_seed` e `fault_log`, com cada mensagem perdida, atrasada, duplicada, inundada ou recurso ocupado.

## O que acontece em cada falha

Medido no MVP sem argumentos, uma falha de cada vez (18-11-2026). Os testes correspondentes estão em [test_faults.py](../tests/integration/test_faults.py).

| Falha | Estado final | Motivo (`reason`) | O que acontece aos recursos |
|---|---|---|---|
| `CFP` ou `PROPOSAL` perdido; nenhuma patrulha disponível | `unresolved` | `no_eligible_proposals` | Nada é reservado |
| `ACCEPT` perdido | `unresolved` | `confirmation_unknown` | Nada é reservado |
| `STATUS` perdido | `unresolved` | `confirmation_unknown` | O recurso **executa a missão** e volta à base, mas o iniciador já desistiu |
| `MISSION_RESULT` perdido | `unresolved` | `mission_result_unknown` | O recurso volta à base e liberta-se |
| `VERIFY_REQUEST` ou `VERIFY_RESPONSE` perdido; fonte indisponível | `expired` | `insufficient_corroboration` (decisão `observe` / `timeout`) | Ninguém é enviado |
| Uma patrulha indisponível | `closed` | `confirmed` | A outra patrulha faz a missão |
| Recurso ocupado depois de propor | `closed` | `confirmed` | `STATUS(reservation_failed)`, nova ronda, outro recurso |
| `MISSION_RESULT` ou `ACCEPT` duplicado | `closed` | `confirmed` | Um só efeito por missão |
| Propostas atrasadas 1 s | `unresolved` com prazo fixo de 0,5 s; `closed` com o prazo dinâmico | `no_eligible_proposals` | — |
| Mensagens inválidas (`flood`) | `closed` | `confirmed` | O lixo é ignorado |

Duas leituras desta tabela:

- **O ponto fraco é o `STATUS`.** É a única perda em que um recurso se desloca sem que ninguém aproveite o resultado. É o custo da confirmação extra ([porquê existe](protocols.md#porquê-o-status-depois-do-accept)).
- **Fonte calada não é «não vi».** Sem resposta, o iniciador não mobiliza, mas também não conta a ausência contra a ameaça. Com a política ativa e uma ameaça grave (gravidade ≥ 0,8), a evidência local basta para pedir verificação mesmo sem a fonte.

## Reenvio

Por omissão os agentes não reenviam: uma perda leva ao prazo esgotado e a um estado explícito.

Com `retransmit=N` em `run_mvp`:

- O iniciador volta a enviar o mesmo `VERIFY_REQUEST`, `CFP` ou `ACCEPT`, com o **mesmo `message_id`**, até N vezes por pedido.
- Os recursos reutilizam propostas ainda válidas e respostas de recusa guardadas; um `ACCEPT` repetido não volta a executar a missão. Com reenvio ativo, repetem a confirmação e o resultado já disponíveis.
- O informador não guarda respostas: cada `VERIFY_REQUEST` repetido volta a consultar o feed e usa o instante simulado atual. Mantém o ID `response-<request_message_id>`, mas o conteúdo pode mudar. É uma nova leitura para o mesmo pedido, não replay de uma resposta imutável.
- O iniciador usa a primeira resposta válida recebida e termina essa verificação; respostas posteriores não criam outra decisão nem outra missão. A ordem de entrega pode, por isso, influenciar a evidência usada. O ID da resposta não deve ser interpretado como identificação de um snapshot imutável; não há garantia geral de replay idêntico para consumidores futuros.
- Enquanto espera o resultado da missão, o iniciador reenvia o `ACCEPT` como pergunta: o recurso repete o `STATUS` e, se já o tiver, o `MISSION_RESULT`.

| Perda | Sem reenvio | 1 reenvio | 2 reenvios |
|---|---|---|---|
| 10 % | 7 de 20 fechadas | 17 | 17 |
| 20 % | 1 | 10 | 16 |
| 30 % | 0 | 3 | 9 |

Fonte: `results/stress/reenvio.csv` (20 execuções por linha; 19 têm alerta). Análise em [scalability.md](scalability.md#reenvio-de-mensagens-antes-e-depois).

O reenvio está ligado no cenário E (`retransmit: 1`) e desligado em todas as outras recolhas.

## Prazos

Há dois relógios, e não se misturam:

| Relógio | O que mede | Avança quando |
|---|---|---|
| Simulado | Movimento, ETA, `created_at`, validade das leituras | Só enquanto houver uma missão em execução |
| Real | Espera por respostas, atrasos injetados | Sempre |

- Espera por propostas: 0,5 s reais no transporte local (2,0 s com XMPP). Com o prazo dinâmico, sem nenhuma proposta espera até `max_receive_timeout`.
- Espera pelo `STATUS`: até `max_receive_timeout`.
- Espera pelo resultado: 10 prazos de receção (5 s reais no transporte local).
- Um `MISSION_RESULT` que chegue antes do `STATUS` fica retido e só é aplicado depois de um `STATUS` válido.
- Há um limite global em tempo real que cobre todos estes prazos; `max_seconds` substitui-o.

As rondas de negociação estão limitadas por `max_attempts` (2).

## Falha do iniciador

Não há despachante nem outro sensor que tome conta da ocorrência.

- Se o iniciador desaparecer **depois** de um `ACCEPT` confirmado, o recurso executa, regressa e liberta a reserva sem depender dele. A ocorrência fica `unresolved` no relatório.
- Se desaparecer **antes**, nada chega a ser reservado.

Só se simula a perda de mensagens de e para o iniciador, mantendo o seu comportamento em execução até ao timeout, não a queda do processo. É nesse modelo que se obtém `unresolved`; um crash real pode impedir a produção do relatório. Detetar a falha e passar a ocorrência a outro sensor ficou por fazer ([decisões pendentes](architecture.md#decisões-pendentes)).

## Escassez

| Situação | Tratamento |
|---|---|
| Energia insuficiente para ir e voltar com a reserva mínima (10 %) | O recurso recusa o CFP (`autonomy_insufficient`) |
| Energia esgota-se a meio | `MISSION_RESULT` com `outcome=failed` e `reason=energy_exhausted`; o recurso fica `UNAVAILABLE` |
| Todos os recursos ocupados | Sem fila: `unresolved`. Com fila (`queue_rounds`): o iniciador espera e volta a pedir |
| Recurso ocupado entre a proposta e o `ACCEPT` | `STATUS(reservation_failed)` e nova ronda |

Os testes de energia estão em [tests/scenarios/test_mvp.py](../tests/scenarios/test_mvp.py). O cenário C junta falhas e escassez: 10 % de perda, atrasos de 0,05 s, resultados duplicados e o drone com 15 % de autonomia ([config/scenarios/C.json](../config/scenarios/C.json)).

## Limites

- A indisponibilidade de um agente dura a execução inteira; não há falha a meio nem recuperação.
- A perda aleatória é reprodutível com a mesma semente **e** a mesma ordem de envios, mas essa ordem depende do escalonamento do `asyncio`.
- A injeção existe só no transporte local. Não demonstra tolerância a falhas de rede reais nem do servidor XMPP.
- Não há recarga: um recurso sem energia fica parado até ao fim.
