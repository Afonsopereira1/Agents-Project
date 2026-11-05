# ISIA — Tema C: Monitorização descentralizada da vida selvagem

**Unidade curricular:** Introdução aos Sistemas Inteligentes e Autónomos (2026/2027) — Assignment 1  
**Tema:** *Decentralised Wildlife Monitoring and Anti-Poaching Patrols*

> **Estado:** documentação de planeamento; arquitetura B1 proposta, ainda a validar em grupo. Não há implementação Python verificada nesta branch.

## O projeto

Vamos simular uma reserva onde sensores e informadores detetam atividade suspeita e **corroboram evidências**. Drones, veículos e rangers podem propor e executar missões, sem despachante central. Na **abordagem B1**, cada ocorrência tem um iniciador local temporário; os outros agentes decidem autonomamente se colaboram. Utilizaremos **SPADE (Python/XMPP)**.

O simulador mantém a verdade dos acontecimentos apenas para avaliação; os agentes recebem observações imperfeitas e mensagens.

## Onde encontrar cada coisa?

| Preciso de… | Ficheiro |
|---|---|
| Objetivos e ideias originais do colega | [requirements.md](requirements.md) |
| **Tarefas e ordem de implementação (Etapas 0–10)** | [docs/development-plan.md](docs/development-plan.md) |
| Arquitetura, agentes, algoritmos e decisões pendentes | [docs/architecture.md](docs/architecture.md) |
| Mensagens e protocolos de comunicação | [docs/protocols.md](docs/protocols.md) |
| Testes, métricas e três cenários | [docs/evaluation.md](docs/evaluation.md) |
| Organização flexível dos colegas | [docs/team-tasks.md](docs/team-tasks.md) e [Issues](https://github.com/Afonsopereira1/Agents-Project/issues) |

**MVP previsto:** ocorrência → observação → evidências → avaliação → propostas de recursos → missão → resultado. O MVP não substitui os requisitos da entrega final.

## Requisitos e fontes

**Enunciado oficial** — `ISIA 2026-2027 - Assignment 1 - Theme suggestions [simple].pdf`:
- **Tema C, p. 1:** deteção de ameaças, corroboração e coordenação descentralizada de patrulhas/respostas comunitárias.
- **Instruções gerais, p. 4:** SPADE; decisões justificadas sobre agentes, mensagens, protocolos, confiança e falhas; pelo menos **três cenários contrastantes**; métricas e limitações; código com instruções, documentação, relatório, visualização ou gravação, apresentação. Testes automatizados surgem como opcionais, mas são recomendáveis.

**Materiais oficiais da cadeira** (PDF fornecidos no âmbito da UC; não publicados neste repositório):
- `ISIA_0 (2026-27).pdf` — enquadramento, ferramentas e datas;
- `ISIA_1 - Agent-based Computing.pdf` — conceitos de agentes e MAS;
- `ISIA_2 - Intelligent Agents.pdf` — arquiteturas reativas, deliberativas e híbridas;
- `ISIA_3 - Multi-Agent Systems.pdf` — comunicação FIPA-ACL, coordenação e Contract Net.

**Referências técnicas e teóricas essenciais:** [SPADE](https://spade-mas.readthedocs.io/), [GitHub SPADE](https://github.com/javipalanca/spade), [FIPA](http://www.fipa.org/), [GitHub Docs](https://docs.github.com/en/), Wooldridge (*An Introduction to MultiAgent Systems*, 2009), Russell e Norvig (*Artificial Intelligence: A Modern Approach*, 4.ª ed.), [Gaia (Wooldridge, Jennings e Kinny, 2000)](https://link.springer.com/article/10.1023/A:1010071910869).

**Nota:** as fórmulas, os limiares de confiança, o mapa 2D e o protocolo Contract Net simplificado são **propostas de engenharia**, não exigências literais do enunciado.

## Executar o projeto

Ainda não existe aplicação Python executável nesta branch. Quando a Etapa 0 e a comunicação SPADE estiverem efetivamente testadas, colocar aqui os comandos de instalação, execução e testes validados.
