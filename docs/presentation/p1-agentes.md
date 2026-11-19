# P1 — Como os agentes são construídos

Folha de estudo para a primeira pergunta do professor. É o diapositivo 5 do [roteiro](roteiro.md). A explicação completa, com diagramas, está em [architecture.md](../architecture.md).

## Em resumo

- Cada agente é uma subclasse de `spade.agent.Agent` com **comportamentos** filtrados por **Templates**.
- Os comportamentos coordenam comunicação, estado e execução. Delegam regras de avaliação em funções puras, mas nem todas as decisões são puras.
- Drone, veículo e guarda são subclasses distintas que partilham a implementação de `MobileResourceAgent`; as capacidades e o estado são configurados.
- A **autonomia** está no recurso: é ele que decide se propõe.

## Resposta de 30 segundos

«Cada agente é uma subclasse de `Agent` do SPADE. No `setup()` regista comportamentos com Templates; o iniciador filtra pela ontologia e valida cada protocolo ao receber. Os comportamentos coordenam comunicação, estado e execução, delegando regras de avaliação em funções puras. Drone, veículo e guarda partilham a implementação móvel. O recurso decide se propõe, conta a energia de ida e volta e pode negar a reserva depois da proposta. As decisões são descentralizadas; a simulação partilha processo, ambiente e relógio.»

## Três camadas

| Camada | O que tem | Onde |
|---|---|---|
| 1. SPADE: comunicação, estado e execução | `setup()`, comportamentos e Templates | `src/isia/agents/` |
| 2. Raciocínio: avaliação e estado local | Funções de corroboração, política, `evaluate_cfp` e seleção; reputação e reserva mantêm estado | `src/isia/reasoning/` |
| 3. Domínio: dados imutáveis e validados | `Observation`, `Mission`, `Bid`, `Message` | `src/isia/domain/`, `src/isia/communication/` |

## Os agentes

| Agente | Comportamentos | O que faz |
|---|---|---|
| `IncidentSensorAgent` | 1 `OneShotBehaviour` | Conduz uma ocorrência, do alerta ao fecho |
| `InformantAgent` | 1 `CyclicBehaviour` | Responde só com as suas observações |
| `MobileResourceAgent` | 3 `CyclicBehaviour` | Responde a CFP; trata aceites e rejeições; executa a missão |
| `DroneAgent`, `VehicleAgent`, `RangerAgent` | herdados | Classes vazias: a mesma lógica com capacidades diferentes |

## Onde está a autonomia

1. **Decide se propõe:** `MobileResourceAgent.evaluate_request` chama `evaluate_cfp` com o estado do próprio recurso ([mobile.py](../../src/isia/agents/mobile.py), [allocation.py](../../src/isia/reasoning/allocation.py)).
2. **Energia de ida e volta:** recusa (`autonomy_insufficient`) se não consegue ir, regressar e ficar com 10 % de reserva.
3. **Pode negar a reserva depois do `ACCEPT`:** responde `STATUS` diferente de `reserved`; o iniciador não o obriga e renegoceia uma vez (`IncidentBehaviour.allocate` em [incident.py](../../src/isia/agents/incident.py)).

## Limites a admitir

- É um híbrido de reativo e utilidade, não um interpretador BDI.
- Cada iniciador trata uma ocorrência por execução.
- Todos os recursos se movem da mesma maneira na grelha (primeiro em x, depois em y).
- Os agentes nunca veem o `ground_truth`; só o avaliador, no fim.
