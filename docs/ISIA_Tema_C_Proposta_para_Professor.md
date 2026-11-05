# ISIA — Trabalho 1 | Proposta para discussão com o docente

**Unidade curricular:** Introdução aos Sistemas Inteligentes e Autónomos (2026/2027)  
**Tema C:** *Decentralised Wildlife Monitoring and Anti-Poaching Patrols*  
**Grupo:** 3 estudantes  
**Data:** 5 de novembro de 2026  
**Estado:** proposta de conceção em desenvolvimento; pretendemos validar as principais opções com o docente.

## 1. O que pretendemos construir?

Um **sistema multiagente descentralizado**, implementado em **Python com SPADE**, que simula a monitorização de uma reserva natural e a resposta a possíveis situações de caça furtiva.

O sistema deverá:

- **Detetar** atividades potencialmente suspeitas através de sensores e informadores simulados.
- **Verificar** os alertas, cruzando observações de fontes próximas e considerando falsos positivos.
- **Avaliar a fiabilidade** das fontes através de um mecanismo simples de reputação.
- **Coordenar recursos** (drones, veículos e equipas de *rangers*) de forma descentralizada, considerando disponibilidade, distância e autonomia.
- **Medir os resultados** da simulação em diferentes condições.

Não utilizaremos sensores, drones ou imagens reais: os acontecimentos, as leituras e os movimentos serão **simulados**.

## 2. Estratégia proposta: B1 — coordenação temporária por ocorrência

A nossa escolha inicial é uma arquitetura em que **não existe um gestor central permanente de todas as missões**.

Quando um sensor ou informador identifica uma ocorrência, pode assumir temporariamente o papel de **iniciador/coordenador dessa ocorrência**. Solicita informação a outros agentes, avalia as evidências e, se necessário, pede propostas a recursos móveis. Cada recurso decide autonomamente se pode aceitar a missão.

Podem existir diferentes iniciadores para ocorrências distintas. O **simulador** apenas fornece observações e regista a verdade de referência para avaliação; **não escolhe patrulhas pelos agentes**.

### Exemplo simples

1. Um sensor deteta um possível disparo na posição `(4, 7)`.
2. Pede observações a sensores ou informadores próximos.
3. Cruza as respostas e estima a credibilidade do alerta.
4. Se for necessária verificação, comunica uma proposta de missão a dois recursos disponíveis.
5. Os recursos respondem com tempo estimado e condições de execução (ou recusam).
6. O iniciador seleciona uma proposta válida; o recurso confirma, desloca-se e reporta o resultado.
7. A ocorrência é encerrada ou encaminhada para nova resposta, e o resultado fica registado.

**Questão importante:** teremos de definir como evitar ocorrências duplicadas e o que acontece se o iniciador deixar de responder.

## 3. Que componentes vamos programar?

| Componente | Função prevista |
|---|---|
| **Ambiente 2D** | Mapa da reserva, acontecimentos reais/falsos alarmes, posições, tempo e perceções imperfeitas |
| **SensorAgent / InformantAgent** | Produzir observações e responder a pedidos de verificação |
| **DroneAgent / VehicleAgent / RangerAgent** | Avaliar pedidos, propor/recusar missões e executar deslocações/intervenções simuladas |
| **Comunicação SPADE/XMPP** | Trocar mensagens assíncronas com identificadores de ocorrência e de missão |
| **Corroboração e reputação** | Cruzar informação de fontes distintas e ponderar a sua fiabilidade |
| **Atribuição de tarefas** | Negociação **Contract Net simplificada**, inspirada nas mensagens FIPA-ACL |
| **Avaliação e visualização** | Registar mensagens, decisões, deslocações, falhas e métricas |

**Opções para manter a implementação viável:** agentes com regras simples e estado interno; dados JSON nas mensagens; mapa 2D sem física complexa; pontuação de suspeita **heurística** (não apresentada como probabilidade cientificamente calibrada). A metodologia **Gaia** serve de inspiração para identificar papéis e interações, mas não estamos a afirmar que aplicámos integralmente todos os seus modelos.

## 4. Como vamos avaliar o sistema?

De acordo com o enunciado, planeamos **pelo menos três cenários contrastantes**:

| Cenário | Condições | Objetivo |
|---|---|---|
| **A — Funcionamento normal** | Rede estável e recursos disponíveis | Demonstrar o funcionamento de referência |
| **B — Alertas pouco fiáveis** | Mais falsos positivos e fontes com reputações diferentes | Verificar o efeito da corroboração e confiança |
| **C — Falhas e escassez** | Mensagens perdidas/atrasadas e patrulhas ocupadas ou com pouca autonomia | Analisar robustez e capacidade de resposta |

**Métricas previstas:** alertas corretos e falsos, *precision/recall* quando bem definidos, tempo até à resposta, missões concluídas, mensagens trocadas e custos de deslocação/energia. Os resultados serão obtidos por execução da simulação; **ainda não temos resultados experimentais**.

## 5. Estado real do trabalho — 5/11/2026

**Já fizemos e testámos localmente:**

- Configuração do projeto no VS Code/Git, Python **3.12.3** e SPADE **4.1.4**.
- Arranque do servidor XMPP local (`spade run`).
- Primeiro agente SPADE (`hello_agent.py`): iniciou, executou um `OneShotBehaviour` e terminou corretamente.
- Estrutura inicial de pastas, `.gitignore`, `requirements.txt` e instruções no README.
- Primeiro modelo de dados, `Position(x, y)`, com validações e **4 testes unitários aprovados**.

**Ainda por implementar:** ambiente simulado, agentes específicos da reserva, comunicação entre agentes, corroboração, reputação, negociação, execução de missões, cenários e métricas. A configuração ainda não foi validada num segundo computador.

## 6. Plano de desenvolvimento

Vamos seguir o plano incremental já documentado no repositório, **Etapas 0–10**, sem criar funcionalidades complexas antes de termos um sistema mínimo a funcionar:

**Modelos de dados → ambiente e primeiros agentes → comunicação e corroboração → negociação → execução de uma missão (MVP) → reputação e falhas → três experiências → visualização e apresentação.**

O grupo não terá uma divisão rígida em três módulos: cada colega escolhe tarefas pequenas e prioritárias, com coordenação, testes e revisão cruzada.

**Previsão de entrega/apresentação nos materiais da UC:** **19–20 de novembro de 2026**.

## 7. Questões que gostaríamos de colocar ao professor

1. **A coordenação temporária por ocorrência (B1) é adequada** para demonstrar descentralização, mesmo existindo um iniciador local em cada ocorrência?
2. **Contract Net simplificado**, corroboração por regras e reputação baseada em histórico são mecanismos suficientes para a complexidade esperada do trabalho?
3. A simulação com **mapa 2D, observações sintéticas e deslocações simplificadas** é adequada, desde que os agentes não tenham acesso à verdade do simulador?
4. Para o primeiro MVP, podemos começar com **dois sensores e dois recursos**, introduzindo depois informadores, outros tipos de patrulha, reputação e falhas?
5. Existem **critérios de avaliação ou funcionalidades adicionais** que devamos priorizar, tendo em conta o prazo?

---

### Apresentação oral sugerida (cerca de 1 minuto)

> O nosso grupo escolheu o Tema C, sobre monitorização descentralizada de uma reserva natural. Vamos criar uma simulação em Python com SPADE, em que sensores e informadores detetam situações suspeitas, comunicam entre si para confirmar alertas e coordenam patrulhas móveis.
>
> A estratégia que propomos é a B1: o agente que deteta uma ocorrência pode coordená-la temporariamente, mas não existe um gestor global. Quando é necessária uma missão, os recursos apresentam propostas e um é selecionado segundo a sua disponibilidade e custo.
>
> Queremos começar por um sistema mínimo que execute uma ocorrência completa e depois testar reputação, falsos positivos, falhas de comunicação e recursos limitados, em três cenários. Já validámos SPADE, o servidor XMPP, um agente de teste e o primeiro modelo de dados. Gostávamos de saber se considera esta arquitetura e este nível de simplificação adequados ao trabalho.

**Fontes:** enunciado oficial *Assignment 1 — Theme Suggestions*, Tema C (p. 1) e instruções gerais/entregáveis (p. 4); `ISIA_01_PL (2026-27).pdf` (instalação e primeiros agentes SPADE); materiais `ISIA_2` e `ISIA_3` (agentes, comunicação e coordenação); documentação de planeamento do grupo no repositório [Agents-Project](https://github.com/Afonsopereira1/Agents-Project).
