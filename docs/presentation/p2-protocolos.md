# P2 — Protocolos e arquitetura

Folha de estudo para a segunda pergunta do professor. São os diapositivos 3 (arquitetura) e 6 (protocolos) do [roteiro](roteiro.md). A explicação completa está em [protocols.md](../protocols.md) e [architecture.md](../architecture.md).

## Em resumo

- **FIPA Request** para pedir corroboração; **FIPA Contract Net** para escolher o recurso, duas vezes numa ameaça confirmada (patrulha, depois guarda).
- **Extensão nossa:** depois do `accept-proposal`, o recurso confirma a reserva com `STATUS`.
- **Arquitetura:** quem deteta coordena a sua ocorrência. Não há despachante.
- **Preço assumido:** escolha gulosa por ocorrência, sem ótimo global.

## Resposta de 30 segundos

«Usamos dois protocolos FIPA: Request para pedir corroboração e Contract Net para escolher o recurso. Não há despachante: quem deteta coordena, e cada recurso decide se propõe. Uma missão custa no máximo 3N + 2 mensagens. Acrescentámos uma confirmação de reserva, o `STATUS`, para evitar duas missões no mesmo recurso. O preço é a escolha gulosa: não garantimos a melhor atribuição global.»

## As mensagens

| Protocolo | Sequência (performativas) |
|---|---|
| Verificação (FIPA Request) | `request` → `inform` |
| Atribuição (FIPA Contract Net) | `cfp` → `propose` ou `refuse` → `accept-proposal` ao vencedor e `reject-proposal` aos outros → `inform` (`STATUS`) → `inform` (`MISSION_RESULT`) |

Numa ocorrência completa são **15 mensagens**: 2 de verificação, 8 para a patrulha (2 candidatos) e 5 para o guarda (1 candidato).

Dois pormenores que caem em perguntas:

- Quem recusa um CFP é o **recurso**, com `refuse`. `reject-proposal` é do **iniciador**, para as propostas que não escolheu.
- `ALERT` só é enviado entre iniciadores vizinhos, no cenário E. `INCIDENT_CLOSED` nunca é enviado: é um registo na linha temporal.

## Prós e contras, com números

| Escolha | Ganho | Preço medido |
|---|---|---|
| Contract Net | Uma ronda; o recurso decide | Um candidato calado faz a ronda esperar o prazo: 1,5 s → 5,5 s reais em 10 execuções |
| `STATUS` | 0 reservas duplas em todos os testes, com até 16 ameaças juntas | Mais 1 mensagem por missão |
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

- É FIPA nas performativas e nos protocolos; o conteúdo é JSON nosso, não FIPA-SL.
- O mecanismo não é *strategy-proof*.
- As falhas foram injetadas só no transporte local, não num servidor XMPP.
