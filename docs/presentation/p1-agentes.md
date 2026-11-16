# Diapositivo P1 — Como os agentes são construídos

> Conteúdo do diapositivo. O formato final e a ordem na apresentação ficam para o roteiro do Bloco D.

## Título

**Agentes SPADE finos, decisões em funções puras**

## Corpo (esquerda): três camadas

1. **SPADE — comunicação e tempo:** `setup()` regista comportamentos; cada um filtra mensagens por performativa, ontologia e protocolo.
2. **Raciocínio — funções puras:** corroboração, política, `evaluate_cfp`, escolha da proposta, reputação. Testadas sem servidor (489 testes).
3. **Domínio — dados imutáveis e validados:** `Observation`, `Mission`, `Bid`, `Message`.

| Agente | Comportamentos |
|---|---|
| `IncidentSensorAgent` (`sensor-1`) | 1 OneShot: verifica, negoceia, fecha |
| `InformantAgent` (`sensor-2`, visual) | 1 Cyclic: responde a pedidos |
| Drone / veículo / guarda | **Mesma classe**, 3 Cyclic: CFP, ACCEPT, execução |

## Corpo (direita): onde está a autonomia

1. **Decide se propõe:** o recurso avalia o CFP com o seu próprio estado — [mobile.py:104](../../src/isia/agents/mobile.py#L104).
2. **Energia de ida e volta:** recusa se não consegue regressar — [mobile.py:116](../../src/isia/agents/mobile.py#L116).
3. **Pode recusar depois do `ACCEPT`:** `STATUS` ≠ `reserved` e o iniciador não o obriga — [incident.py:190](../../src/isia/agents/incident.py#L190).

## Rodapé

Híbrido reativo + utilidade, não BDI completo. Os agentes nunca veem o `ground_truth`. Informador humano: o tipo existe, mas **nenhum cenário medido o usa**.

## Notas do orador (30 s)

«Cada agente é uma subclasse de `Agent` do SPADE com comportamentos filtrados por templates FIPA. Os comportamentos só comunicam; as decisões estão em funções puras, por isso testamos tudo sem servidor. Drone, veículo e guarda são a mesma classe e só mudam a capacidade. A autonomia está no recurso: decide se propõe, conta a energia de ida e volta e pode recusar a reserva mesmo depois de aceite.»

Fontes: [architecture.md, secção 3](../architecture.md#3-como-os-agentes-são-construídos).
