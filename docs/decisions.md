# Decisões técnicas — proposta e registo de deliberações

> **Estado em 20-10-2026:** todas as escolhas de conceção abaixo são **propostas para discussão**. Não há aprovação coletiva documentada. Atualizar este ficheiro após a reunião dos três elementos.

[Voltar ao README](../README.md) · [Estratégia](implementation-strategy.md) · [Equipa](team-tasks.md) · [Protocolos](protocols.md)

## Convenção de estatutos

- **OFICIAL:** exigência explícita do enunciado, não negociável pelo grupo sem orientação do docente.
- **BASE DO COLEGA:** proposta ou requisito descrito no ficheiro [`requirements`](../requirements), ainda não necessariamente aprovado.
- **PROPOSTA:** decisão técnica sugerida nesta estratégia, por validar com a equipa.
- **PENDENTE:** precisa de informação, comparação ou consenso antes de ser fixada.
- **APROVADO:** só utilizar depois de documentar data, participantes e decisão.
- **REJEITADO/ALTERADO:** manter rasto e justificação; não apagar a decisão anterior.

## O que é efetivamente obrigatório

| Item | Estatuto | Fonte |
|---|---|---|
| Tema C: monitorização descentralizada de ameaças, corroboração e coordenação de resposta | OFICIAL | Enunciado, p. 1 |
| Utilização de SPADE | OFICIAL | Enunciado, p. 4 |
| Escolher normas, granularidade, mensagens, negociação, confiança e tratamento de falhas | OFICIAL (decisões a justificar, não algoritmos pré-escolhidos) | Enunciado, p. 4 |
| Descrever agentes, mensagens, modos de falha e métricas | OFICIAL | Enunciado, p. 4 |
| Avaliar pelo menos três cenários contrastantes, discutir resultados e limitações | OFICIAL | Enunciado, p. 4 |
| Código executável, documentação, apresentação e visualização ou gravação | OFICIAL | Enunciado, p. 4 |
| RF1–RF4 e RNF1–RNF6 do ficheiro `requirements` | BASE DO COLEGA | Ficheiro original do repositório |

**Precisão:** o Tema C inclui exemplos de sensores acústicos, câmaras, drones, veículos e rangers e sugere falsos positivos, conectividade intermitente e escassez de recursos. Esses exemplos orientam o desenho, mas o enunciado não fixa quantidades, fórmulas ou modelos de sensores.

## Decisões submetidas ao grupo

| ID | Decisão proposta | Estado | Razão e critérios para aprovação |
|---|---|---|---|
| D01 | Python + SPADE + XMPP; preservar `requirements` e criar `requirements.txt` apenas na implementação | PROPOSTA, salvo SPADE que é OFICIAL | Compatibilidade com o enunciado, bibliotecas mínimas e instalação reprodutível |
| D02 | Cinco papéis: `SensorAgent`, `InformantAgent`, `DroneAgent`, `VehicleAgent`, `RangerAgent` | PROPOSTA | Papel claro, granularidade e carga de execução realistas |
| D03 | Arquitetura híbrida simplificada: sensores reativos; recursos com estados/objetivos | PROPOSTA | Boa relação entre reatividade e explicabilidade; evitar BDI integral desnecessário |
| D04 | Grelha 2D e relógio de simulação controlado | PROPOSTA | Reprodutibilidade, visualização e implementação incremental |
| D05 | Estado verdadeiro do ambiente separado do estado interno dos agentes | PROPOSTA, princípio metodológico essencial | Evitar conhecimento indevido e medir deteção corretamente |
| D06 | Mensagens JSON versionadas com metadados FIPA-ACL | PROPOSTA | Schema estável, rastreabilidade e validação automática |
| D07 | Corroboração espacial e temporal, com deduplicação e distinção de fontes | PROPOSTA | Redução de falsos alarmes sem fabricar independência de evidência |
| D08 | Pontuação ponderada de evidência, sem a chamar probabilidade calibrada | PROPOSTA | Simplicidade e transparência; comparar com baseline |
| D09 | Reputação por histórico confirmado, com prior Beta simples | PROPOSTA | Evitar estimativas extremas com poucas observações |
| D10 | Política de resposta por níveis, com limiares parametrizáveis | PROPOSTA | Conciliar rapidez e precisão; 30%/75% do colega são apenas exemplos |
| D11 | Contract Net simplificado com iniciador **local por ocorrência** | PROPOSTA | Permitir propostas autónomas e evitar despachante global |
| D12 | Reserva atómica de recursos, timeout, deduplicação e recuperação de falhas | PROPOSTA | Consistência em presença de concorrência e rede imperfeita |
| D13 | Critérios de seleção elegibilidade + custo normalizado (ETA, energia, carga) | PROPOSTA | Justificabilidade; pesos a avaliar |
| D14 | Três cenários: normal, sensores ruidosos, falhas/escassez | PROPOSTA quanto aos cenários; mínimo de três é OFICIAL | Cobrir objetivos e fragilidades principais |
| D15 | Divisão funcional em A/B/C e revisões cruzadas | PROPOSTA | Equilibrar implementação, integração e testes |
| D16 | Estrutura modular em `src/isia/`, `tests/`, `config/`, `docs/` | PROPOSTA | Evitar dependências circulares e tornar testes independentes |
| D17 | Versão de Python, SPADE e biblioteca de testes | PENDENTE | Validar no ambiente dos três elementos antes de fixar versões |
| D18 | Estratégia de descoberta de vizinhos e eventual substituição do iniciador local | PENDENTE | Definir abordagem de recuperação sem centro decisor permanente |
| D19 | Modelos de erro, velocidades, energia, limiares e custo de missões | PENDENTE | Parâmetros configuráveis e experimentação documentada |
| D20 | Modalidade de visualização e formato final de dados | PENDENTE | Escolher solução que não comprometa o tempo de implementação |

## Perguntas a deliberar antes da Etapa 0

- [ ] Concordamos com o objetivo e âmbito do MVP?
- [ ] A granularidade dos cinco papéis é adequada ou devemos simplificar a primeira versão?
- [ ] Como cada ocorrência será identificada e quem inicia a negociação local?
- [ ] Que mensagens e campos são estritamente necessários para a primeira integração?
- [ ] A estrutura de diretórios e os modelos partilhados podem ser considerados contratos estáveis?
- [ ] Qual a política de revisão, branching e integração na `main`?
- [ ] Quem assume A, B e C, e como serão partilhados os testes e a documentação?
- [ ] Qual a versão de Python e SPADE verificada nos computadores dos três elementos?
- [ ] Que simplificações são aceitáveis no primeiro MVP?

## Modelo de registo de deliberação

Ao aprovar ou alterar uma decisão, acrescentar uma entrada nesta secção:

```text
Data: AAAA-MM-DD
ID: Dxx
Decisão: [descrição aprovada]
Participantes: Elementos A, B e C (ou indicação dos presentes)
Justificação: [requisitos e argumentos técnicos]
Alternativas analisadas: [...]
Consequências: [ficheiros e etapas afetados]
Ligação ao PR/Issue: #...
```

**Não existem ainda entradas aprovadas.** As escolhas preliminares deverão ser confirmadas em revisão coletiva antes de alterar o estatuto para `APROVADO`.
