# Fontes, bibliografia e rastreabilidade

> Este inventário separa **material oficial fornecido**, **bibliografia indicada** e **propostas de engenharia**. Links públicos não implicam leitura integral de obras protegidas.

[Voltar ao README](../README.md) · [Estratégia](implementation-strategy.md) · [Decisões](decisions.md)

## Documentos oficiais

Os PDF foram fornecidos ao grupo na unidade curricular e analisados durante o planeamento. **Não estão incluídos neste pacote nem publicados no repositório**, para não reproduzir materiais docentes sem autorização. Os números indicados são páginas dos PDF/slides.

| Documento | Secções/páginas relevantes | Aplicação |
|---|---|---|
| `ISIA 2026-2027 - Assignment 1 - Theme suggestions [simple].pdf` | p. 1, Tema C; p. 4, instruções gerais e entregáveis | Base normativa dos requisitos e do mínimo de três cenários |
| `ISIA_0 (2026-27).pdf` | slides 6–11; slide 10: datas | Contexto, bibliografia oficial, ferramenta SPADE e calendário |
| `ISIA_1 - Agent-based Computing.pdf` | slides 12, 14 e 16 | Definição de agente/MAS; descentralização; problema micro/macro |
| `ISIA_2 - Intelligent Agents.pdf` | slides 3–18; 30–38; 45–52 | Racionalidade, observabilidade, reatividade, BDI e arquiteturas híbridas |
| `ISIA_3 - Multi-Agent Systems.pdf` | slides 4–16, 22–31, 36–43 | Cooperação, ACL, ontologias, Contract Net, FIPA Request e simulação |

### Requisitos explícitos do Tema C (enunciado, p. 1)

> Construir um sistema descentralizado de monitorização e resposta que detete ameaças de caça furtiva, verifique eventos por corroboração e coordene patrulhas e respostas comunitárias sem autoridade central.

O exemplo usa sensores acústicos, *camera traps*, comunicações de rangers, informadores, drones e veículos. Propõe incorporar falsos positivos, comunicação intermitente e recursos limitados, deixando a seleção exata dos métodos ao grupo.

### Instruções transversais (enunciado, p. 4)

- Implementar em SPADE.
- Selecionar e justificar normas do sistema, granularidade dos agentes, esquemas de mensagens, protocolos, negociação, mecanismos de confiança e gestão de falhas.
- Documentar agentes, mensagens, falhas, métricas e escolhas de conceção.
- Avaliar pelo menos **três cenários contrastantes**, discutir resultados, compromissos e limitações.
- Entregar código com instruções de execução, documentação, relatório de desempenho, visualização/demonstração e apresentação.
- Testes unitários/scripts automáticos surgem como **opcionais no enunciado**, mas são recomendados pela estratégia.

## Contributo inicial do grupo

- [`../requirements`](../requirements): documento Markdown **sem extensão**, escrito por um colega, com RF1–RF4, RNF1–RNF6, atores e política indicativa de três níveis de resposta.
- Este documento é **fonte de planeamento do grupo**, não um novo requisito oficial nem um ficheiro `requirements.txt` de bibliotecas.
- A sugestão de limiares «30%–75%» é indicativa, sem calibração probabilística demonstrada.

## Bibliografia principal e complementar dos slides

1. Michael Wooldridge. *An Introduction to MultiAgent Systems*, 2.ª ed., 2009. [Página da obra](https://www.cs.ox.ac.uk/people/michael.wooldridge/pubs/imas/IMAS2e.html). Agentes, MAS, cooperação e interação.
2. Yoav Shoham e Kevin Leyton-Brown. *Multiagent Systems: Algorithmic, Game-Theoretic, and Logical Foundations*, 2008. [Página da obra](https://www.masfoundations.org/). Coordenação, negociação e mecanismos.
3. Stuart Russell e Peter Norvig. *Artificial Intelligence: A Modern Approach*, 4.ª ed., 2022. [Página da obra](https://aima.cs.berkeley.edu/). Agentes racionais, estado, decisão e incerteza.
4. Richard S. Sutton e Andrew G. Barto. *Reinforcement Learning: An Introduction*, 2.ª ed., 2018. [Obra](http://incompleteideas.net/book/the-book-2nd.html). Referência adicional; RL **não é requisito do MVP**.

## Artigos científicos partilhados

| Identificador e ligação | Temática | Relação com a proposta |
|---|---|---|
| [Rao (1996), *AgentSpeak(L): BDI Agents Speak Out in a Logical Computable Language*](https://link.springer.com/chapter/10.1007/BFb0031845) | Linguagem AgentSpeak(L) e agentes BDI | Inspiração para crenças, intenções e planos, sem necessidade de implementar AgentSpeak |
| [Rao & Georgeff, BDI Agents: From Theory to Practice](https://aaai.org/papers/icmas95-042-bdi-agents-from-theory-to-practice/) | Arquitetura BDI | Fundamentar decisões orientadas a objetivos e compromisso |
| [Poslad (2007), *FIPA: Specifying Protocols for Multi-Agent Systems Interaction*](https://dl.acm.org/doi/10.1145/1293731.1293735) | Especificações e protocolos FIPA | Estrutura, performatives e protocolos de comunicação |
| [Bauer, Müller & Odell, *Agent UML: A Formalism for Specifying Multiagent Software Systems*](https://link.springer.com/chapter/10.1007/3-540-44564-1_6) | Modelação de interações entre agentes/Agent UML | Diagramas e semântica de interações |
| [Bresciani et al. (2004), *Tropos: An Agent-Oriented Software Development Methodology*](https://link.springer.com/article/10.1023/B:AGNT.0000018806.20944.ef) | Tropos e requisitos orientados a agentes | Objetivos e dependências |
| [Wooldridge, Jennings & Kinny (2000), *The Gaia Methodology for Agent-Oriented Analysis and Design*](https://link.springer.com/article/10.1023/A:1010071910869) | Gaia e engenharia de MAS | Papéis e organização |
| [Zambonelli, Jennings & Wooldridge (2003), *Developing Multiagent Systems: The Gaia Methodology*](https://dl.acm.org/doi/10.1145/958961.958963) | Desenvolvimento da metodologia Gaia | Papéis, serviços e protocolos |

**Nota sobre acesso e rigor:** durante o levantamento anterior alguns editores disponibilizaram apenas resumos ou reproduções alternativas. Não se afirma uma revisão integral de todos os artigos. A escolha concreta de algoritmos de reputação, pesos, limiares e estrutura de código é **proposta nossa**, não uma prescrição desses artigos. Para citações académicas no relatório final, confirmar metadados bibliográficos e consultar os textos integrais quando disponíveis.

## Documentação técnica útil

- [SPADE — documentação](https://spade-mas.readthedocs.io/)
- [SPADE — repositório oficial](https://github.com/javipalanca/spade)
- [FIPA — normas](http://www.fipa.org/)
- [GitHub — documentação Markdown](https://docs.github.com/en/get-started/writing-on-github)
- [GitHub — Pull Requests](https://docs.github.com/en/pull-requests)

## Mapa de fundamentação

| Decisão discutida | Fundamentação disponível | Grau de certeza |
|---|---|---|
| Usar SPADE | Enunciado, p. 4 | Obrigatório |
| Manter decisão distribuída | Tema C + ISIA_1, slide 14 | Obrigatório como objetivo; mecanismo por escolher |
| Agentes reativos/híbridos | ISIA_2, slides 6–18 e 45–52 | Opção técnica fundamentada |
| Usar BDI simplificado | ISIA_2, slides 30–38; Rao/Georgeff | Opção técnica, não obrigação |
| ACL e Contract Net | ISIA_3, slides 9–13 e 24–26; FIPA/Poslad | Protocolos ensinados; adaptação a escolher |
| Modelação de papéis | ISIA_1, slide 16; Gaia/Tropos | Opção metodológica |
| Pontuação ponderada/Beta | Heurística/estatística geral, proposta do grupo | **Não** é fórmula prescrita nos slides |
| Grelha 2D, três cenários específicos | Escolhas de engenharia para viabilizar a simulação | Exemplos propostos, parâmetros por validar |

Se aparecerem outros slides, um enunciado atualizado ou restrições dos docentes, rever a [matriz de decisões](decisions.md) e o [plano](development-plan.md) antes de implementar.
