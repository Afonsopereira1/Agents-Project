# Diapositivo P2 — Protocolos e arquitetura

> Conteúdo do diapositivo. O formato final e a ordem na apresentação ficam para o roteiro do Bloco D.

## Título

**Porquê B1 + FIPA Request + Contract Net?**

## Corpo (esquerda): o que usamos

1. **Verificação — FIPA Request:** `sensor-1` → `request` → `sensor-2` → `inform`.
2. **Atribuição — Contract Net:** `cfp` → `propose` / `refuse` → `accept-proposal` (ou `reject-proposal` aos perdedores) → `STATUS` → `MISSION_RESULT`. Corre duas vezes numa ameaça confirmada (patrulha, depois guarda).
3. **Arquitetura B1:** o sensor que deteta coordena só a sua ocorrência; não há despachante.

## Corpo (direita): prós e contras

| | Pró | Contra **medido** |
|---|---|---|
| Contract Net | Recursos decidem sozinhos; uma ronda | Drone silencioso: **1,5 s → 5,5 s** em 10 execuções (espera pelo prazo) |
| Corroboração | Cenário B: FPR **0,75 → 0,25** | Cenário B: recall **0,80 → 0,65** |

## Rodapé

Descartadas: despachante central (contraria o tema), votação/consenso (O(n²), fontes correlacionadas), leilões de várias rondas. Paralelismo de ocorrências: **o desenho permite; não medido**.

## Notas do orador (30 s)

«Usamos dois protocolos FIPA: Request para pedir corroboração e Contract Net para escolher o recurso. Não há despachante: quem deteta coordena. O preço está medido: o Contract Net espera pelo prazo quando um recurso não responde, e a corroboração corta falsos positivos de 0,75 para 0,25 mas perde recall. Desvio assumido: o recurso confirma a reserva com `STATUS` depois do `accept-proposal`, para evitar duas missões no mesmo recurso.»

Fontes: [architecture.md](../architecture.md#porquê-b1-e-não-outras-arquiteturas-do-sistema), [protocols.md](../protocols.md#9-porquê-estes-protocolos-alternativas-prós-e-contras), [experiments.md](../experiments.md).
