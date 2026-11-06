# Comunicação: começar com dois agentes

**Primeiro objetivo:** um agente faz uma pergunta e outro responde por SPADE/XMPP. Só depois acrescentamos o ciclo de incidente e a negociação de recursos.

Já existem validadores de mensagens e estados. A comunicação real ainda precisa de ser implementada e verificada. O [contrato completo](message-contract.md) fica como referência técnica; não é uma lista de funcionalidades a implementar antes do primeiro teste.

## 1. A primeira troca

Usar apenas dois tipos de mensagem:

| Mensagem | Quem envia | Para quê |
|---|---|---|
| `VERIFY_REQUEST` | Agente A → agente B | Pedir observações de um local e período. |
| `VERIFY_RESPONSE` | Agente B → agente A | Devolver as observações disponíveis ou indicar que não tem dados. |

Começar com observações preparadas para o teste. Esta troca não precisa de patrulhas, missões, reputação ou de um simulador completo.

1. A envia o pedido e guarda o seu ID, a conversa e o prazo.
2. B lê o pedido e responde na mesma conversa, com ID próprio.
3. A verifica se a resposta corresponde ao pedido e chegou dentro do prazo.
4. Os dois agentes registam o resultado e terminam.

Se B não responder, A termina a espera e regista o timeout. Falta de resposta não significa ausência de ameaça.

## 2. O que reutilizar

Cada mensagem já tem um formato definido:

- **Corpo JSON:** tipo, ID, instante, incidente e dados do pedido ou resposta.
- **Metadados:** intenção, protocolo, conversa e ligação ao pedido.

Nesta troca, usar `protocol=verification` e `ontology=wildlife-monitoring`. O pedido usa `performative=request` e `reply-with` igual ao seu ID. A resposta usa `performative=inform` e `in-reply-to` igual ao ID do pedido. Ambos mantêm `conversation-id` e `incident_id`; não precisam de `mission_id`.

Reutilizar `to_json`/`from_json` e `validate_reply` de [messages.py](../src/isia/communication/messages.py). Passar à validação o instante de receção. Consultar na [referência](message-contract.md#exemplos-dos-restantes-tipos) os exemplos `msg-002` e `msg-003`; `msg-023` mostra uma resposta sem dados. Não inventar outro formato só para o primeiro teste.

## 3. Quando este passo está pronto

- Dois agentes com identidades distintas trocam o pedido e a resposta reais.
- Uma resposta de outra conversa ou fora do prazo não é aceite.
- Uma mensagem inválida não interrompe o agente.
- Sem resposta, a espera termina no prazo.
- Os agentes encerram e o comando para repetir o teste fica documentado.

Os testes atuais dos validadores ajudam, mas não comprovam entrega por XMPP.

## 4. O que acrescentar depois

| Entrega | Próximo aumento de âmbito |
|---|---|
| **1 — Integrar e comunicar** | Verificar a troca acima e as conversões com os modelos reais disponíveis. |
| **2 — Completar um incidente** | Ligar alerta, corroboração, propostas, reserva, deslocação e resultado. Dois sensores e dois recursos chegam para começar. |
| **3 — Cobrir os restantes requisitos** | Acrescentar reputação simples, capacidades distintas, ruído, escassez e falhas controladas. Testar disputa pelo mesmo recurso. |
| **4 — Avaliar e entregar** | Executar três cenários, comparar uma alternativa simples e preparar resultados e demonstração. |

Na Entrega 2, implementar prazos, prevenção de efeitos repetidos e reserva sem conflitos junto de cada fluxo. Aceitar uma proposta não confirma uma reserva; terminar uma missão não encerra automaticamente o incidente. Esses cuidados entram quando a funcionalidade passa a existir.

O [contrato v1](message-contract.md) preserva os outros tipos e regras já estudados. Consultá-lo à medida que forem necessários, sem implementar todos os fluxos de uma vez.
