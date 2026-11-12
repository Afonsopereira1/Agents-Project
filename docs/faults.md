# Falhas, atrasos e escassez — Etapa 8

A injeção de falhas existe **apenas no transporte local** do runner
(`run_mvp(faults=...)` ou `--faults config/faults.json`). Os agentes, os contratos
e os timeouts são os mesmos do MVP; não se altera nem se valida o servidor XMPP.
Com `--xmpp`, `--faults` é recusado.

## Parâmetros

| Chave | Efeito |
|-------|--------|
| `seed` | Semente do gerador da perda aleatória |
| `loss` | Probabilidade de perder cada mensagem, em `[0, 1]` |
| `delay` | Atraso real em segundos por tipo, ex. `{"PROPOSAL": 0.05}` |
| `drop` | Tipos sempre perdidos, ex. `["CFP"]` |
| `duplicate` | Tipos entregues duas vezes, ex. `["MISSION_RESULT"]` |
| `unavailable_agents` | Agentes (parte local do JID) sem envio nem receção durante a execução |
| `occupied_after_proposal` | Recursos reservados por outra missão logo após a sua `PROPOSAL` |

O relatório JSON regista `faults` (já validado e completo), `scenario_seed` e
`fault_log`, com cada mensagem perdida, atrasada, duplicada ou recurso ocupado.
Os seletores são exatos e sensíveis a maiúsculas: os tipos seguem `MessageType`,
os agentes usam a parte local do JID (por exemplo `drone-mvp`) e a ocupação usa
o ID do recurso (`drone`). Nomes desconhecidos ou vazios são recusados. Cada
configuração normalizada tem coleções próprias, incluindo as fornecidas pelo
chamador, e não altera os defaults das execuções seguintes.

## Estados resultantes

| Falha | Estado | `reason` |
|-------|--------|----------|
| `CFP` perdido, nenhuma patrulha disponível ou propostas tardias | `unresolved` | `no_eligible_proposals` |
| `ACCEPT` perdido | `unresolved` | `confirmation_unknown` |
| `MISSION_RESULT` perdido | `unresolved` | `mission_result_unknown` |
| Sensor par indisponível | `expired` | decisão `timeout` |
| Recurso ocupado após proposta | renegociação, `closed` com outro recurso | — |
| `MISSION_RESULT`/`ACCEPT` duplicado | `closed`, um efeito por missão | — |

**Retransmissões:** os agentes não retransmitem mensagens; uma perda leva ao
timeout e a um estado explícito. As rondas de negociação estão limitadas por
`max_attempts` (2 no MVP).

O limite global por omissão inclui os prazos reais da verificação e das
tentativas de negociação e resultado das duas fases de missão, com margem
para terminar. Não compete com o timeout de verificação. `max_seconds` explícito
continua a impor o watchdog do chamador. O movimento usa tempo simulado;
atrasos de entrega e esperas usam tempo real. Um resultado antecipado válido
fica retido apenas para o ACCEPT ativo e só é aplicado depois de STATUS válido;
timeout, rejeição ou cancelamento limpam essa retenção.

**Recuperação quando falha o iniciador:** não há despachante nem tomada de
controlo por outro sensor. Depois de um `ACCEPT` confirmado, o recurso executa,
regressa e liberta a reserva sem depender do iniciador. O incidente fica
`unresolved` e visível no relatório. Só se simula a perda da ligação com o
iniciador, não a queda do processo.

**Escassez:** a energia insuficiente e o esgotamento já são tratados pela
Etapa 6 (`tests/scenarios/test_mvp.py`); aqui acrescenta-se o recurso ocupado.

```bash
PYTHONPATH=src python -m isia.simulation.runner --faults config/faults.json > /tmp/isia-faults.json
PYTHONPATH=src python -m unittest tests.integration.test_faults -v
```

**Limites:** a indisponibilidade dura toda a execução do MVP, que tem uma única
janela. A perda aleatória é reprodutível com a mesma semente e a mesma ordem de
envios, mas a ordem depende do escalonamento `asyncio`.
