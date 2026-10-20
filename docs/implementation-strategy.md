# Estratégia de implementação e fundamentação — proposta para debate

> **Estado:** documento orientador **não aprovado coletivamente**. Não apresenta resultados de implementação. A prioridade é satisfazer o [enunciado do Tema C](references.md#documentos-oficiais), preservando o [contributo inicial](../requirements) do grupo.

[README](../README.md) · [Arquitetura](architecture.md) · [Plano](development-plan.md) · [Avaliação](evaluation.md) · [Decisões](decisions.md)

## 1. Problema e objetivo

Pretende-se estudar o modo como **agentes autónomos com informação incompleta** podem cooperar na monitorização de uma reserva natural e na reação a potenciais ameaças de caça furtiva. O enunciado exige deteção, verificação por corroboração e coordenação da resposta **sem autoridade central**, utilizando SPADE e avaliando resultados em três ou mais cenários.

A solução não deve reduzir-se a uma sequência centralizada de funções que lê toda a verdade do simulador e manda os restantes componentes executar. Para demonstrar comportamento multiagente, cada recurso deve conservar estado, capacidade de decisão e protocolos explícitos de interação.

### Objetivos funcionais

- Detetar e reportar observações suspeitas de fontes heterogéneas.
- Corroborar informação espacial e temporalmente relevante; lidar com falsos positivos.
- Manter uma estimativa transparente da fiabilidade das fontes.
- Solicitar e negociar verificação/resposta conforme necessidade e capacidades.
- Executar deslocações e intervenções **simuladas**, considerando recursos limitados.
- Registar explicações das decisões e métricas de desempenho.

### Objetivos não funcionais

Descentralização, autonomia, tolerância a falhas modeladas, escalabilidade limitada mas mensurável, testabilidade, reprodutibilidade, baixo custo de implementação e documentação suficiente para os três elementos compreenderem o sistema.

## 2. Separação entre enunciado, contributo do colega e escolhas da proposta

| Questão | Estatuto correto |
|---|---|
| Sistema descentralizado de deteção/corroboração/resposta com SPADE | Exigência oficial |
| Três cenários contrastantes e análise de métricas/falhas/limitações | Exigência oficial |
| Sensores, informadores, patrulhas móveis e rangers | Atores propostos no exemplo do Tema C; também presentes no ficheiro `requirements` |
| RF1–RF4/RNF1–RNF6 e política de três níveis | Contributo inicial do colega, a validar |
| Grelha 2D, cinco classes de agentes, BDI simplificado, JSON, Contract Net, Beta | Propostas de conceção, não exigências literais |
| Thresholds de suspeita, pesos de decisão, versões de biblioteca, velocidades, energia | Parâmetros ainda pendentes de definição/validação |

Consultar [decisions.md](decisions.md) antes de classificar qualquer proposta como «aprovada».

## 3. Análise das alternativas

### 3.1 Arquiteturas dos agentes

| Abordagem | Forças | Fragilidades | Juízo para a proposta |
|---|---|---|---|
| Reativa pura | Simples, resposta rápida | Pouca memória e planeamento; difícil coordenar missões longas | Adequada para comportamento básico de sensores |
| BDI completo | Crenças, objetivos e intenções explícitos; planos elaborados | Tempo de implementação e complexidade | Excesso para MVP, salvo evidência contrária |
| Híbrida simplificada | Comportamentos reativos + estado/objetivos | Exige disciplina em estados e mensagens | **Recomendação técnica a discutir** |
| Aprendizagem por reforço | Potencial adaptação de políticas | Treino, desenho de recompensa, validação | Não necessária nem recomendada no MVP |

**Justificação:** `ISIA_2` ensina agentes reativos, orientados a objetivos, BDI e híbridos (slides 6–18, 30–38 e 45–52). O relatório poderá explicar como estas ideias são adaptadas ao código SPADE sem alegar que existe um motor BDI formal.

### 3.2 Atribuição de tarefas

| Alternativa | Vantagem | Limitação |
|---|---|---|
| Patrulha disponível mais próxima | Baseline fácil e barato | Ignora autonomia, energia, capacidades e custo composto |
| **Contract Net simplificado** | Recursos fazem propostas; iniciador compara custos; demonstra interação FIPA | Requer IDs, reservas, timeout e gestão de concorrência |
| Otimização global | Pode melhorar objetivos agregados em certos modelos | Mais complexo; risco de precisar de conhecimento/globalidade centralizada |

**Proposta:** Contract Net local por ocorrência, com critério de elegibilidade e custo comparável. O *initiator* é um **papel temporário**, não um coordenador único de toda a reserva. Consultar [protocols.md](protocols.md).

### 3.3 Avaliação de observações

| Alternativa | Considerações |
|---|---|
| Contagem simples de alertas | Fácil, mas ignora qualidade e correlação |
| **Pontuação ponderada + reputação** | Explicável e implementável; precisa de calibração empírica dos limiares |
| Modelo probabilístico completo | Interpretabilidade estatística potencial; exige hipóteses e parâmetros sustentados |

Preferir no MVP uma função determinística de avaliação com pesos explícitos; usar benchmarks para verificar se melhora decisões. Não a designar como `P(poaching|observations)` sem calibração e hipóteses justificadas.

### 3.4 Ambiente

Começar por grelha 2D com alcance, deslocação e relógio controlado permite demonstrar agentes e protocolos sem construir um simulador físico. A introdução de obstáculos/caminhos, velocidades diferenciadas, fontes ruidosas e falhas deve ser incremental. Ao comparar opções, considerar simultaneamente tempo de implementação e qualidade da evidência experimental.

## 4. Algoritmos propostos

### 4.1 Associação de observações

Dadas observações `o_i`, avaliar se partilham tipo de evento, distância espacial admissível e diferença temporal dentro de uma janela. Manter `event_id` por observação e `incident_id` por ocorrência. Em caso de associação ambígua, conservar incerteza; não forçar a fusão de todos os alertas próximos.

### 4.2 Agregação ponderada de suspeita

$$
S = \frac{\sum_{i=1}^{n}w_i c_i}{\sum_{i=1}^{n}w_i}, \qquad w_i \ge 0,\quad \sum_i w_i > 0.
$$

- `c_i`: pontuação/força da evidência fornecida pela fonte `i`, dentro de `[0,1]`.
- `w_i`: ponderação da evidência, calculada a partir de fiabilidade, atualidade e outros fatores aprovados.
- `S`: índice **heurístico** agregado, não probabilidade posterior calibrada.

Quando não houver pesos positivos, a decisão deve ser «evidência insuficiente», não dividir por zero. Mensagens da mesma observação não acrescentam evidência; erros correlacionados entre sensores exigem cautela.

### 4.3 Reputação da fonte

Uma opção inicial é a média suavizada de uma proporção binária:

$$
R_i = \frac{\alpha_0+a_i}{\alpha_0+\beta_0+a_i+b_i}
$$

Em que `a_i` são observações posteriormente confirmadas, `b_i` são incorretas e `α₀`, `β₀` são pseudocontagens/prior positivo. Com `α₀=β₀=1`, a estimativa inicial é `0,5` (valor ilustrativo). **Não atualizar `a_i`/`b_i` apenas porque outros agentes concordam**. É preciso resultado verificado ou verdade da simulação utilizada na camada apropriada.

Limitação: esta taxa de acertos condicionada aos alertas verificados **não mede automaticamente capacidade de deteção de incidentes não reportados**.

### 4.4 Decisão sobre resposta

Propor política por estados: `WATCH`, `VERIFY`, `RESPOND`, `CLOSE/EXPIRE`. Os limiares e gravidade poderão determinar ações distintas. O ficheiro inicial do colega sugere 30%/75%, mas são exemplos a validar e **não probabilidades científicas confirmadas**. Registar decisão, evidência usada, objetivo, recursos disponíveis e risco de falso alarme.

### 4.5 Custos e elegibilidade de recursos

Antes de comparar propostas, cada recurso tem de cumprir: capacidade, disponibilidade, autonomia suficiente e nenhuma reserva incompatível. Entre recursos elegíveis:

$$
J_j=\lambda_t\widehat{T}_j+\lambda_e\widehat{E}_j+\lambda_l\widehat{L}_j
$$

onde os termos representam ETA, gasto energético e carga de trabalho **normalizados**; os pesos são parâmetros a definir. Selecionar a proposta válida de menor custo, com regra de desempate determinística documentada. Comparar experimentalmente com baseline de patrulha mais próxima.

## 5. Estratégia de MVP

O MVP tem de evidenciar as propriedades do problema sem depender de algoritmos sofisticados:

1. Ambiente pequeno configurável, um incidente e observações imperfeitas.
2. Dois sensores com comunicação SPADE e pelo menos uma troca de verificação.
3. Iniciador local avalia a evidência e anuncia tarefa.
4. Duas patrulhas recebem CFP e produzem propostas autónomas.
5. Recurso selecionado reserva missão, desloca-se, verifica e comunica o resultado.
6. Incidente termina num estado explícito e produz log legível.

Não considerar o MVP «concluído» apenas porque o código compila: deve existir teste de integração executado. Reputação dinâmica avançada, falhas e múltiplos cenários são incrementos posteriores.

## 6. Robustez e riscos prioritários

| Risco | Mitigação proposta | Teste principal |
|---|---|---|
| Algoritmo conhece verdade do simulador | Separação de interfaces estado real/perceção | Garantir ausência de acesso na decisão |
| Conflito de missões | Reserva atómica no recurso + identificador único | Atribuições concorrentes |
| Duplicação de mensagens | IDs e operação idempotente | Reenvio do mesmo `event_id` |
| Fonte enviesada | Reputação com prior e confirmação externa | Sensores repetidamente incorretos |
| Iniciador local falha | Política explícita de substituição, ainda por definir | Timeout de iniciador |
| Mensagens perdidas | Deadline e reenvios limitados | Falha de conexão simulada |
| Limites energéticos | Elegibilidade e margem de regresso | Proposta com bateria insuficiente |
| Prazos apertados | Entregar MVP antes de investir em visualização | Marco Etapa 6 |

## 7. Justificação metodológica

- **Visão micro (agente):** estado, objetivos, decisão e reação. Ver `ISIA_1`, slide 16, e `ISIA_2`.
- **Visão macro (sociedade):** contratos de interação, negociação, gestão de dependências e autonomia. Ver `ISIA_3`.
- **BDI simplificado:** crenças (informação recebida), objetivos (verificar/proteger), intenções (missão aceite); não implica semântica formal de um interpretador BDI. Referências Rao/Georgeff e slides 30–38.
- **Protocolos:** FIPA-ACL, Contract Net, request/inform, diagramas Mermaid inspirados nas sequências ensinadas em `ISIA_3`, slides 24–28.
- **Modelação:** Gaia/Tropos ajudam a explicitar papéis, objetivos e responsabilidades; não representam imposição de framework.
- **Experimentação:** cenários contrastantes e análise de métricas decorrem diretamente do enunciado, p. 4.

Para ligações e limites de acesso às fontes, consultar [references.md](references.md).

## 8. Dependências e distribuição da implementação

A ordem técnica completa encontra-se em [development-plan.md](development-plan.md). Com contratos estáveis, a equipa pode desenvolver em paralelo **ambiente** e **comunicação SPADE**; posteriormente **reputação** e **falhas**. A integração de cada parte requer PR revisto e testes reproduzíveis.

Proposta de responsabilidades: A deteta/corrobora/reputação; B negoceia e executa missões; C simula/integra/mede. Ver [team-tasks.md](team-tasks.md). Nenhuma atribuição é definitiva.

## 9. Restrições, simplificações e exclusões do MVP

- Os dados acústicos/visuais serão inicialmente **simulados**; não é obrigatório processar áudio ou imagens reais.
- Não será introduzido RL apenas por ser parte do programa da UC.
- Não será criado, como ponto de partida, um único agente central responsável por todos os alertas e tarefas.
- Modelos de velocidade, energia, perceção, reputação e conectividade são aproximações com parâmetros a declarar.
- O facto de o XMPP ter infraestrutura não elimina a descentralização **da decisão**; não afirmar tolerância a falhas do servidor se não for testada.
- Não serão atribuídos valores de desempenho nem eficácia de deteção sem experiências reais.

## 10. Condições para aprovação coletiva

- [ ] Objetivos e fronteiras de simulação/MVP aceites.
- [ ] Agentes e papéis validados.
- [ ] Contratos de dados e mensagens revistos pelos três.
- [ ] Critérios de decisão (reputação, limiares, custos) identificados como propostas parametrizadas.
- [ ] Política de descentralização e recuperação do iniciador definida.
- [ ] Estrutura de ficheiros e responsabilidades aceites.
- [ ] Plano de teste e três cenários aprovados.

**Próximo passo apenas após aprovação:** [Etapa 0](development-plan.md#etapa-0--auditoria-e-preparação).
