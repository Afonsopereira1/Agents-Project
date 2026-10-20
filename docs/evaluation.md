# Plano de testes, cenários e avaliação experimental

> **Estado:** testes e experiências **planeados**. Este documento não contém resultados empíricos. O enunciado exige **pelo menos três cenários contrastantes** e discussão de métricas, trade-offs e limitações.

[README](../README.md) · [Plano](development-plan.md) · [Estratégia](implementation-strategy.md) · [Referências](references.md)

## 1. Questões de investigação

1. A corroboração reduz os falsos alertas sem diminuir excessivamente a deteção de incidentes verdadeiros?
2. A reputação baseada em histórico melhora decisões face a fontes heterogéneas?
3. A negociação de recursos oferece vantagens sobre escolher apenas a patrulha disponível mais próxima?
4. Como se degradam a resposta e a disponibilidade com atrasos, perdas e recursos limitados?
5. Que compromisso emerge entre rapidez, precisão, energia e mensagens trocadas?

Estas são **hipóteses de análise**, não efeitos já demonstrados.

## 2. Cenários contrastantes

| Cenário | Configuração a comparar | Pergunta principal |
|---|---|---|
| **A — Operação normal** | Conectividade elevada, níveis moderados de ruído e recursos suficientes | Linha de base de deteção e resposta |
| **B — Sensores ruidosos** | Mais falsos positivos, fontes com fiabilidade distinta e evidência contraditória | Robustez da corroboração e reputação |
| **C — Perturbação/escassez** | Atrasos/perda de mensagens, recursos ocupados e pouca autonomia | Degradação, coordenação e recuperação |

**Parâmetros ainda não fixados:** dimensão do mapa, nº de agentes por papel, incidentes por execução, distribuição espacial, probabilidades de erro, atrasos/perdas, velocidade, bateria e políticas de resposta. Defini-los **antes** da recolha final de resultados, na configuração versionada. Não usar números arbitrários como se fossem medidos no mundo real.

## 3. Baselines e ablações

Comparar quando possível a solução completa com:

- **Sem corroboração:** uma observação isolada desencadeia a política de referência.
- **Sem reputação:** todas as fontes recebem o mesmo peso inicial.
- **Seleção nearest-available:** escolhe-se o recurso elegível mais próximo, sem negociação por custo composto.
- **Sem injeção de falhas:** isolamos a influência das perturbações de comunicação.

Comparar sempre sob as **mesmas sequências de incidentes e configurações**, quando tecnicamente possível. O uso de sementes comuns reduz a variabilidade devida ao ambiente, mas não garante determinismo completo de escalonamento assíncrono.

## 4. Definição de métricas

Antes de medir, escolher a **unidade de classificação** (sugestão: incidente no horizonte experimental). Para calcular verdadeiros negativos, definir também o conjunto de oportunidades negativas: por exemplo, zonas-intervalos sem incidente. Se não existir tal definição, **não calcular FPR** nem TN fictícios.

| Métrica | Definição operacional proposta | Interpretação |
|---|---|---|
| `TP` | Incidentes verdadeiros detetados e classificados como ameaça | Acertos positivos |
| `FP` | Casos negativos classificados como ameaça | Alarmes falsos |
| `FN` | Incidentes verdadeiros não detetados no prazo definido | Falhas de deteção |
| `TN` | Casos negativos corretamente não sinalizados (requer conjunto negativo definido) | Acertos negativos |
| Precision | `TP / (TP + FP)` | Qualidade dos alertas positivos |
| Recall | `TP / (TP + FN)` | Cobertura de incidentes reais |
| FPR | `FP / (FP + TN)` | Alarmes falsos relativos a negativos |
| Tempo de deteção | `t_primeiro_alerta - t_início_incidente` | Rapidez da deteção |
| Tempo de resposta | `t_chegada_recurso - t_início_incidente` | Rapidez de intervenção |
| Sucesso das missões | Missões concluídas / missões iniciadas | Fiabilidade operacional |
| Energia consumida | Energia total gasta por papel/cenário | Custo operacional |
| Mensagens por incidente | Nº de mensagens emitidas ou entregues / nº incidentes | Custo de comunicação |
| Conflitos de missão | Tentativas incompatíveis / nº missões | Qualidade de coordenação |
| Não resolvidos | Incidentes terminados sem decisão/resposta confirmada | Casos pendentes |

**Se o denominador de uma métrica for zero:** marcar `N/A` e explicar, em vez de devolver 0 ou 1 silenciosamente. Os tempos devem indicar unidade e relógio. Registar atrasos e perdas na aplicação separadamente de falhas do XMPP.

## 5. Protocolo experimental

1. Definir `scenario_id`, versão de código/commit, versão do contrato, parâmetros e semente.
2. Fixar horizonte temporal e critério de terminação.
3. Executar cada cenário e cada baseline, idealmente com várias sementes independentes.
4. Guardar ficheiro de configuração, log estruturado, métricas por execução e eventuais falhas.
5. Validar contagens internas e detetar missões/incident states incompletos.
6. Calcular medidas-resumo apropriadas (média, mediana, dispersão e nº execuções).
7. Comparar cenários e políticas; indicar variabilidade e mecanismos plausíveis.
8. Registar limitações do simulador e hipóteses não confirmadas.

**Formato de resultados sugerido** (estrutura, não medições):

```text
results/
  scenario-A/
    run-001-config.json
    run-001-events.jsonl
    run-001-metrics.json
  scenario-B/
  scenario-C/
  summary.csv
```

Não inserir métricas fictícias na apresentação. Um gráfico só é resultado experimental depois de executar e validar as respetivas simulações.

## 6. Testes unitários e de integração

| ID | Caso | Tipo | Condição esperada |
|---|---|---|---|
| UT01 | Posição inválida | Unitário | Modelo rejeita fora dos limites |
| UT02 | JSON sem campo obrigatório | Unitário | Mensagem inválida é rejeitada |
| UT03 | Mesmo `event_id` retransmitido | Unitário | Uma única evidência contabilizada |
| UT04 | Divergência temporal/espacial | Unitário | Observações não agrupadas indevidamente |
| UT05 | Reputação com poucos dados | Unitário | Prior impede extremos injustificados |
| UT06 | Denominador zero em métrica | Unitário | `N/A` explícito |
| UT07 | Recurso sem bateria | Unitário | Não apresenta proposta elegível |
| IT01 | Troca request/response | Integração | Mensagem SPADE recebe resposta correlacionada |
| IT02 | Contratação com dois recursos | Integração | Um recurso reserva missão, outros rejeitados |
| IT03 | Duas missões simultâneas | Integração | Sem dupla reserva incompatível |
| IT04 | Proposta atrasada | Integração | Não altera missão já fechada |
| IT05 | Perda de mensagem | Integração | Timeout e estado recuperável |
| E2E01 | Incidente completo | End-to-end | Observação → verificação → missão → fecho |
| E2E02 | Falso positivo | End-to-end | Decisão coerente, sem alegar evento real |
| E2E03 | Iniciador indisponível | End-to-end | Recuperação prevista ou falha explícita |

**O enunciado considera testes automáticos opcionais**, mas esta estratégia recomenda executá-los para tornar o resultado verificável.

## 7. Matriz requisito → evidência

| Fonte/requisito | Método de verificação | Artefacto esperado |
|---|---|---|
| Tema C — descentralização | Testar mais de uma ocorrência/iniciador e ausência de despacho global | Diagrama + logs de conversação |
| Tema C — deteção | Injetar eventos conhecidos e conferir observações | TP/FP/FN e timeline |
| Tema C — corroboração | Sensores com evidência diferente | Registo de pedidos e agregação |
| `requirements` RF3 — reputação | Fontes com históricos distintos | Histórico e decisões justificadas |
| Tema C — coordenação de patrulhas | Propostas, aceitação, recusa e execução | Sequência Contract Net |
| Tema C — falsos positivos | Cenário B | Precision/Recall ou métricas justificadas |
| Tema C — conectividade intermitente | Cenário C | Timeouts e comparação de latências |
| Tema C — recursos limitados | Cenário C | Energia/ocupação/recusas |
| Enunciado — 3 cenários | A, B e C | Configurações e resultados distintos |
| Enunciado — documentação/demonstração | Instalação limpa + visualização | README + slides + gravação ou interface |

## 8. Como interpretar os resultados

- Confirmar que eventuais ganhos em Precision não escondem perda excessiva de Recall.
- Diferenciar custo de mensagens **enviadas** e **entregues** em cenários de perda.
- Não confundir quantidade de propostas com qualidade da alocação.
- Documentar limites de validade: sensores simulados, topologia simplificada, probabilidades escolhidas pelo grupo, sem calibração de campo e dependência de XMPP.
- Evitar inferência causal a partir de uma única execução; repetir e comparar condições equivalentes.

## 9. Checklist

- [ ] Definições de TP/FP/FN/TN e unidade de análise aprovadas.
- [ ] Configurações A, B e C versionadas.
- [ ] Baselines e ablações definidos.
- [ ] Logs com IDs, tempos, decisões e resultado de referência.
- [ ] Métricas unitariamente verificadas.
- [ ] Cenários executados e resultados armazenados.
- [ ] Comparações e limitações redigidas.
- [ ] Material de apresentação fiel às execuções realizadas.
