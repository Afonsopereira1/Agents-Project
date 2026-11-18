# Requisitos iniciais

> **Estado:** documento histórico, de 2-11-2026, escrito antes da implementação. Regista os objetivos e as ideias de partida do grupo. A coluna «Como ficou» foi acrescentada a 18-11-2026 e diz onde cada ponto está hoje. Para a versão atual, ver o [README](README.md) e a [arquitetura](docs/architecture.md). A lista de pacotes Python é outro ficheiro: [requirements.txt](requirements.txt).

## Objetivos

Detetar ameaças de caça furtiva, verificar a veracidade dos eventos detetados e coordenar respostas sem autoridade central.

| Objetivo | Descrição |
|---|---|
| Deteção | Monitorizar a reserva e reportar eventos suspeitos |
| Verificação | Confirmar se a informação é verdadeira ou um falso positivo |
| Gestão de reputação | Avaliar a fiabilidade de quem reporta os alertas (sensores e informadores) |
| Distribuição de tarefas | Enviar patrulhas para o local da ameaça, equilibrando rapidez e precisão |

## Atores

| Ator | Descrição | Como ficou |
|---|---|---|
| Sensores estáticos | Áudio e visual | `SensorAgent` e `IncidentSensorAgent`, com fontes `acoustic` e `visual` |
| Informadores | Comunidade local que reporta eventos | `InformantAgent`; as fontes `human` só entram nos testes de stress e no cenário E |
| Patrulhas móveis | Drones e veículos | `DroneAgent` e `VehicleAgent` |
| *Rangers* | Humanos que atuam e intercetam | `RangerAgent` (guarda) |

## Requisitos funcionais

| # | Requisito | Como ficou |
|---|---|---|
| RF1 | Sensores ou informadores detetam e enviam alertas (local, tipo de acontecimento…) | Observações com posição, tipo e instante, geradas pelo simulador |
| RF2 | Os sensores próximos comunicam e cruzam dados para verificar a veracidade | `VERIFY_REQUEST` / `VERIFY_RESPONSE` ([protocolos](docs/protocols.md)) |
| RF3 | Pontuação de confiança em sensores e informadores | Reputação com prior Beta ([reputação e política](docs/reputation-policy.md)) |
| RF4 | Comunicação entre sensores, informadores, patrulhas e *rangers* | Contract Net entre o iniciador da ocorrência e os recursos ([protocolos](docs/protocols.md)) |

## Requisitos não funcionais

| # | Requisito | Como ficou |
|---|---|---|
| RNF1 | Descentralização | Sem despachante central: um iniciador temporário por ocorrência (abordagem B1) |
| RNF2 | Falsos positivos | Cenário B e taxas de erro por fonte ([experiências](docs/experiments.md)) |
| RNF3 | Atraso ou não receção de mensagens (problemas de conectividade) | Falhas injetadas no transporte local ([falhas](docs/faults.md)); a rede XMPP real não foi medida |
| RNF4 | Recursos limitados (patrulhas e *rangers*): combinar rapidez e precisão | Cenário C e testes de stress ([escalabilidade](docs/scalability.md)) |
| RNF5 | Distâncias que patrulhas e *rangers* têm de percorrer (tempo de A a B) | Movimento na grelha, uma célula por segundo simulado; o tempo de chegada entra no custo da proposta |
| RNF6 | Bateria ou gasóleo dos recursos | Autonomia em percentagem; o recurso recusa a missão se não lhe chegar para ir e voltar |

## Ideias principais

1. Sensores ou informadores captam dados suspeitos e recolhem a informação de sensores próximos que possam ajudar a confirmá-la.
2. Depois de comunicarem entre si, transmitem essa informação às patrulhas e aos *rangers*.
3. Consoante o nível de confiança da informação:
   - **Caso 1:** se não for de confiança (só um sensor captou, ou reportou um informador que costuma estar errado), pode decidir-se não enviar ninguém.
   - **Caso 2:** se a confiança for intermédia (por exemplo, entre 30 % e 75 %), envia-se um drone ou um veículo, se disponíveis, para verificar; depois comunica-se com os *rangers* para combater a ameaça.
   - **Caso 3:** se a confiança for elevada, envia-se uma equipa de *rangers*.

**Como ficou:** os três casos existem na política de resposta, com limiares de 0,25 (patrulha) e 0,65 (guarda) em [config/agents.json](config/agents.json). São pontuações de engenharia, não probabilidades: os 30 % e 75 % acima eram só um exemplo.
