"""ISIA: deteção e resposta descentralizada à caça furtiva numa reserva (SPADE).

Quem deteta uma ameaça coordena a sua própria ocorrência: corrobora com outras
fontes, negocia uma patrulha por Contract Net e chama um guarda. Não há
despachante central.

## Onde encontrar cada coisa

| Procura | Onde |
|---|---|
| **P1 — como os agentes são construídos** | `isia.agents` (comportamentos SPADE); as decisões estão em `isia.reasoning` |
| Iniciador de uma ocorrência, do alerta ao fecho | `isia.agents.incident.IncidentSensorAgent` |
| Recurso móvel (drone, veículo, guarda): propor, reservar, executar | `isia.agents.mobile.MobileResourceAgent` |
| Autonomia: o recurso decide se propõe | `isia.reasoning.allocation.evaluate_cfp` |
| **P2 — protocolos** | `isia.communication.messages.MessageType` (tipos) e `isia.communication.transport` (performativas FIPA) |
| Verificação (FIPA Request) | `isia.agents.sensor`, `isia.agents.informant`, `isia.reasoning.corroboration` |
| Atribuição (Contract Net + confirmação `STATUS`) | `isia.reasoning.allocation`, `isia.agents.incident.IncidentSensorAgent.IncidentBehaviour.allocate` |
| Política de resposta (observar, verificar, mobilizar) | `isia.reasoning.policy` |
| Reputação das fontes | `isia.reasoning.reputation` |
| **P3 — escalabilidade e experiências** | `isia.simulation.runner.run_mvp`, `isia.evaluation` e os scripts de stress |
| Métricas (matriz de confusão, tempos, energia) | `isia.evaluation.metrics` |
| Dados do domínio (observação, missão, proposta) | `isia.domain.models` |

## Camadas

1. `isia.agents`: comportamentos SPADE. Só comunicam, guardam estado e executam.
2. `isia.reasoning`: regras de decisão, quase todas funções puras e testáveis sem servidor.
3. `isia.domain` e `isia.communication`: dados imutáveis e validados, e o formato JSON das mensagens.

`isia.simulation` dá o mundo, o relógio e o transporte; `isia.evaluation` só lê
os relatórios no fim. Os agentes nunca veem o `ground_truth`.
"""
