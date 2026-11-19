# P2 — Protocolos e arquitetura

Folha de estudo para a segunda pergunta do professor. São os diapositivos 3 (arquitetura) e 6 (protocolos) do [roteiro](roteiro.md). A explicação completa está em [protocols.md](../protocols.md) e [architecture.md](../architecture.md).

## Em resumo

- Protocolos **inspirados em FIPA Request e Contract Net**, com conteúdo JSON e extensões próprias, para corroborar e escolher recursos.
- **Extensão nossa:** depois do `accept-proposal`, o recurso confirma a reserva com `STATUS`.
- **Arquitetura:** quem deteta coordena a sua ocorrência. Não há despachante.
- **Preço assumido:** escolha gulosa por ocorrência, sem ótimo global.

## Resposta de 30 segundos

«Usamos protocolos inspirados em FIPA Request e Contract Net. Quem deteta coordena a ocorrência e cada recurso decide se propõe. Uma ronda normal com N candidatos custa até 3N + 2 mensagens, incluindo confirmação e resultado, sem novas tentativas ou reenvios. O `STATUS` comunica a reserva; a exclusividade é garantida pela reserva atómica local do recurso. As decisões são descentralizadas, mas a infraestrutura de simulação é partilhada. A escolha é gulosa, sem ótimo global.»

## As mensagens

| Protocolo | Sequência (performativas) |
|---|---|
| Verificação (FIPA Request) | `request` → `inform` |
| Atribuição (FIPA Contract Net) | `cfp` → `propose` ou `refuse` → `accept-proposal` ao vencedor e `reject-proposal` aos outros → `inform` (`STATUS`) → `inform` (`MISSION_RESULT`) |

No MVP normal, sem falhas ou reenvios, são **15 mensagens**: 2 de verificação, 8 para a patrulha (2 candidatos) e 5 para o guarda (1 candidato).

Dois pormenores que caem em perguntas:

- Quem recusa um CFP é o **recurso**, com `refuse`. `reject-proposal` é do **iniciador**, para as propostas que não escolheu.
- `ALERT` só é enviado entre iniciadores vizinhos, no cenário E. `INCIDENT_CLOSED` nunca é enviado: é um registo na linha temporal.

## Prós e contras, com números

| Escolha | Ganho | Preço medido |
|---|---|---|
| Contract Net | Uma ronda; o recurso decide | Um candidato calado faz a ronda esperar o prazo: 1,5 s → 5,5 s reais em 10 execuções |
| Reserva atómica local + `STATUS` | Exclusividade no recurso e confirmação ao iniciador; nenhuma reserva dupla nos casos testados | Mais 1 mensagem por missão |
| Corroboração | Cenário B: FPR 0,75 → 0,25 | Cenário B: recall 0,80 → 0,65 |
| Quem deteta coordena | Sem centro; 6 e 16 ocorrências em paralelo em D e E | Sem ótimo global |

## Alternativas descartadas

| Alternativa | Porque não |
|---|---|
| Despachante central | Ponto único de falha; o enunciado pede «without a central authority» |
| Votação ou consenso entre todos | O(n²) mensagens; fontes correlacionadas enganam a maioria |
| Atribuição direta («drone, vai») | O iniciador teria de saber o estado de todos: um despachante disfarçado |
| Leilões de várias rondas | Mais mensagens e mais tempo |
| Vickrey / VCG | Só garantem verdade com pagamentos; os nossos agentes são cooperativos |

## Limites a admitir

- São protocolos inspirados em FIPA, com JSON e extensões próprias, sem alegação de conformidade integral.
- `ALERT` agrupa observações compatíveis; ameaças distintas próximas podem ser confundidas com duplicados.
- O mecanismo não é *strategy-proof*.
- As falhas foram injetadas só no transporte local, não num servidor XMPP.
