# Organização dos três elementos — proposta de responsabilidades

> **Estado:** distribuição inicial **não atribuída a pessoas reais** e ainda não aprovada. O trabalho é partilhado: a divisão de módulos não elimina revisão cruzada, integração nem responsabilidade conjunta pelo resultado.

[README](../README.md) · [Plano detalhado](development-plan.md) · [Decisões](decisions.md) · [Avaliação](evaluation.md)

## 1. Distribuição preliminar

| Elemento | Área principal | Trabalho concreto | Interfaces com outros |
|---|---|---|---|
| **A** | Deteção e inteligência das fontes | `SensorAgent`, `InformantAgent`, associação e corroboração, reputação, política de evidência, testes unitários | B: requisitos de missão; C: geração de observações, verdade de referência e resultados |
| **B** | Coordenação e resposta | `DroneAgent`, `VehicleAgent`, `RangerAgent`, Contract Net, reserva, ETA/energia e execução de missões | A: severidade/decisão; C: movimento, relógio e disponibilidade |
| **C** | Ambiente, observabilidade e integração | `World`, cenários, relógio, registo de eventos, métricas, visualização, runner e testes integrados | A: observações; B: movimentos, estados e relatórios |

**Avaliação de equilíbrio:** A concentra lógica de avaliação e qualidade da evidência; B concentra protocolos assíncronos e movimento; C concentra infraestrutura e integração. O risco é sobrecarregar C com todas as integrações e A com todo o raciocínio. Para equilibrar: **cada elemento testa o seu módulo e participa em revisão cruzada**; visualização deve ficar simples até o MVP funcionar.

## 2. Trabalho conjunto antes de tarefas paralelas

As seguintes decisões devem ser feitas pelos **três**:

- [ ] Objetivos, fronteiras do MVP e limitações admitidas.
- [ ] Estrutura de ficheiros e interfaces partilhadas.
- [ ] Modelos `Observation`, `Incident`, `Mission`, `Bid` e `ResourceState`.
- [ ] Metadados de mensagens, IDs, correlação e timeouts.
- [ ] Versão Python/SPADE, servidor XMPP e fluxo GitHub.
- [ ] Critérios de teste, cenários e definição das métricas.

**Regra:** alterar um contrato comum exige revisão dos módulos afetados, não apenas autorização do autor do ficheiro.

## 3. Paralelismo por fase

| Fase | A | B | C | Integração conjunta |
|---|---|---|---|---|
| Etapas 0–1 | Acordar modelos de observações | Acordar modelos de missões | Propor configuração e tempo | Testar importação/serialização dos contratos |
| Etapas 2–3 | Preparar sensores e exemplos de observações | Preparar recursos/esqueletos SPADE | Implementar mundo, cenários e execução | **A/C** testam fluxo de sensor; **B** revê contrato |
| Etapas 4–5 | Corroboração distribuída | Contract Net | Ambiente e scripts de teste | A/B/C executam negociação a partir de ocorrência |
| Etapa 6 | Avaliação de evidências para MVP | Execução e estados de recursos | Movimento/runner/logs | **Todos** validam uma ocorrência completa |
| Etapas 7–8 | Reputação/política | Falhas da negociação e recuperação | Injeção de falhas/limites no simulador | Todos revêm testes de concorrência |
| Etapas 9–10 | Métricas da qualidade da deteção | Métricas de missões/energia | Experimentos, visualização e síntese | Todos interpretam resultados e apresentam |

**Dependências críticas:** A e B não devem alterar os esquemas da Etapa 1 sem coordenação; C não deve expor a verdade do cenário diretamente ao código de decisão; B precisa de modelos de missão estáveis antes da negociação real.

## 4. Definição de pronto (*Definition of Done*)

Uma tarefa só pode ser marcada como concluída se:

1. Cumpre a descrição e condições de aceitação da Issue.
2. Tem testes apropriados executados ou uma explicação fundamentada quando não aplicáveis.
3. Mantém os contratos partilhados ou documenta uma mudança aprovada.
4. Não introduz credenciais em código nem ficheiros de ambiente no GitHub.
5. Atualiza a documentação relacionada quando o comportamento mudou.
6. Foi revista por pelo menos outro elemento, quando o fluxo do grupo o permitir.
7. Foi integrada sem quebrar o MVP ou os testes relevantes.

## 5. Estratégia GitHub simples

### Branches

- `main`: versão aceite, executável e revista.
- `docs/implementation-proposal`: proposta de documentação para um PR inicial.
- `feature/<assunto>`: uma funcionalidade por branch, a partir da `main` atualizada.
- `fix/<assunto>`: correção isolada.

### Issues

Criar uma Issue por etapa **ou**, se for demasiado grande, por entrega testável. Por exemplo:

- `Etapa 0 — validar Python/SPADE e auditar repositório`
- `Etapa 1 — contratos Observation/Incident/Mission`
- `Etapa 3 — troca SPADE request/response`
- `Etapa 5 — primeira negociação Contract Net`
- `Etapa 6 — MVP integrado`

Incluir na descrição o objetivo, ficheiros, dependências, testes e critérios de conclusão retirados de [development-plan.md](development-plan.md). Não copiar indiscriminadamente todas as páginas do roteiro para dezenas de Issues.

### Pull Requests

Cada PR deve descrever: o que mudou, porquê, quais os requisitos afetados, testes realizados, riscos e referências à Issue. Pedir revisão aos outros elementos e resolver comentários antes do merge.

### Projects (opcional)

Se o grupo considerar útil, criar um quadro `Todo` → `In progress` → `Review` → `Done`, associado a Issues e PRs. Não criar um processo administrativo que atrase uma equipa de três pessoas.

## 6. Ritmo de integração

- Integrar contratos primeiro e escrever exemplos mínimos utilizáveis por todos.
- Fazer *merge* de funcionalidades pequenas; não manter branches divergentes durante semanas.
- Demonstrar semanalmente o estado **realmente executável**.
- Guardar logs e uma checklist dos erros por resolver.
- Realizar ensaio da demo antes do dia de apresentação, evitando deixar o primeiro teste de ponta a ponta para o fim.

## 7. Compromissos de revisão para a reunião do grupo

- [ ] Distribuição A/B/C equilibrada e aprovada.
- [ ] Responsável inicial por contratos e revisão cruzada definido.
- [ ] Estratégia de conflitos de PR e de alteração de schemas aprovada.
- [ ] Datas internas e prioridades do MVP acordadas.
- [ ] Responsabilidade conjunta por apresentação e análise experimental explícita.

As aprovações devem ser registadas em [decisions.md](decisions.md), com data e ligação ao PR/Issue correspondente.
