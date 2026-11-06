# Organização do grupo — tarefas flexíveis

Somos três elementos. **Não há uma divisão fixa por sensores, patrulhas ou simulação.** Cada elemento escolhe tarefas conforme a sua disponibilidade, respeitando as prioridades e dependências do [plano de desenvolvimento](development-plan.md).

## 1. Como escolher uma tarefa

1. Consultar as **GitHub Issues** e escolher uma tarefa aberta e prioritária cujos pré-requisitos estejam resolvidos.
2. Atribuir a Issue a si próprio e avisar o grupo antes de começar. Se já tiver responsável, combinar colaboração em vez de duplicar trabalho.
3. Criar uma branch curta a partir da branch de integração acordada: `feature/nome-da-tarefa` ou `fix/nome-do-erro`.
4. Implementar apenas o objetivo da Issue e testar a alteração.
5. Abrir um **Pull Request (PR)** com descrição do que mudou, como foi testado e ligação à Issue.
6. Pedir revisão a um colega; integrar após revisão e fechar a Issue quando estiver concluída.

Se a tarefa ficar incompleta, comentar na Issue: **feito / falta / impedimentos**.

## 2. O que deve conter cada Issue

- **Objetivo:** o que vamos construir e porquê.
- **Ficheiros previstos:** onde se espera trabalhar.
- **Dependências:** o que precisa de estar definido ou implementado.
- **Como testar:** execução ou verificações esperadas.
- **Critério de conclusão:** resultado observável para dar a tarefa como pronta.

**Estados simples, sem quadro obrigatório:** Issue aberta e sem responsável = por fazer; atribuída = em desenvolvimento; PR aberto = em revisão; Issue fechada após integração = concluída.

## 3. Regras para não perder tempo

- Dar prioridade às tarefas que desbloqueiam o **MVP** e aos requisitos obrigatórios. Se uma tarefa crítica ficar sem responsável, os três decidem como a assumir ou dividir.
- As interfaces partilhadas (mensagens, IDs, modelos, tempo de simulação) são decisões **conjuntas**. Não alterar contratos sem avisar e rever os módulos afetados.
- Fazer PRs pequenos e integrar frequentemente. Evitar branches divergentes durante muitos dias.
- Nunca publicar passwords, tokens ou credenciais XMPP.
- Todos devem compreender o funcionamento geral e participar na revisão, testes finais, experiências e apresentação.

## 4. Quando uma tarefa está concluída?

- [ ] Cumpre o objetivo e os critérios definidos na Issue.
- [ ] Tem testes executados ou evidência de funcionamento; se não for testável, explica porquê.
- [ ] Não quebra os contratos nem o fluxo funcional existente.
- [ ] As instruções ou documentação afetadas foram atualizadas.
- [ ] Foi revista por outro elemento e integrada na branch acordada.

**Plano técnico e ordem de implementação:** consultar [development-plan.md](development-plan.md). Este documento trata apenas da colaboração e **não altera as Etapas 0–10**.
