# Sensibilidade dos parâmetros — Bloco G

[Pendentes](delivery-todo.md#bloco-g--sensibilidade-dos-parâmetros-no-final) · [Experiências da Etapa 9](experiments.md) · [Ata de parâmetros](approvals.md)

**Estado: âmbito executável medido e analisado — 25 alternativas, 75 combinações com cenário. A alternativa 1/1 continua bloqueada.**
A implementação parte de `be0d3f99606c87f0376a7631e8a459b4f04e0b45`, na
branch `feature/bloco-g-sensibilidade`. Os resultados oficiais, os cenários e
as aprovações existentes são preservados. Nenhuma alternativa passa a valor de
produção por ter um resultado melhor numa experiência.

## Metodologia

A unidade de avaliação continua a ser uma execução: o mundo 8×8 numa janela
única. Existe ameaça real quando há um evento `threat`; existe positivo previsto
quando a política mobiliza uma patrulha ou o guarda. Um episódio sem alerta
continua a contar na classificação, mesmo que não tenha score.

Usam-se A, B e C, variante `full`, sementes 1000–1019 e a ordem original:
repetição, seguida dos episódios na ordem do JSON. Em cada combinação de fator,
valor e cenário há um `ReputationBook` novo; dentro dessa combinação, o mesmo
livro aprende sequencialmente entre episódios **e** repetições. Paralelizar as
execuções ou reiniciar o livro em cada episódio mudaria a experiência.

Cada alternativa parte de uma cópia independente do cenário oficial e altera
apenas o fator declarado. Alguns fatores são conjuntos definidos pelo plano:
os três pesos do custo, α e β iguais, as duas exigências de diversidade ou FP/FN
de ambas as fontes. Não são estimativas dos efeitos individuais de cada
componente desse conjunto. A referência usa os valores próprios de cada cenário;
em particular, a qualidade de B continua a ser a de B.

O runner mantém as extensões do Bloco F disponíveis e desligadas nesta recolha:
`extra_initiators=None`, `extra_patrols=None`, `cfp_limit=None`,
`max_receive_timeout=None`, `queue_rounds=0`, `silent_invalid=False` e
`queue_priority=False`. O prazo-base é independente do teto dinâmico do Bloco F.

O plano contém 13 fatores com duas alternativas: 26 configurações ×
(40 execuções de A + 60 de B + 40 de C) = 3640 execuções alternativas previstas.
Foram concluídas **25 alternativas válidas, nas 75 combinações com A/B/C,
num total de 3500 execuções alternativas**. Diversidade `1/1` permanece bloqueada
nos três cenários: 140 execuções previstas não foram realizadas.

## Cobertura e proveniência da recolha final

| Origem | Lotes | Alternativas | Referências dos lotes | Gates iniciais | Simulações dos lotes |
|---|---:|---:|---:|---:|---:|
| Custo já existente, reutilizado | 5 | 280 | 240 | 10 | 530 |
| Recolha efetuada nesta conclusão | 36 | 3220 | 1680 | 72 | 4972 |
| Total da recolha final | 41 | 3500 | 1920 | 82 | 5502 |

O self-check completo de 140 execuções foi feito antes e é contabilizado
separadamente. A consolidação tem **5420 linhas**: 3500 alternativas e 1920
referências, sem os 82 gates. Tem 116 resumos: 75 alternativas e 41 referências
identificadas por lote. Não há alternativas duplicadas. Cada valor tem 40
execuções em A/C ou 60 em B, sempre com as sementes 1000–1019.
As alternativas distribuem-se por 1000 execuções em A, 1500 em B e 1000 em C.

Foram reutilizados os cinco lotes válidos de custo, excluindo o piloto de uma
repetição, as pastas de testes e os ensaios incompletos. Um primeiro lote novo
foi validado antes dos 35 restantes. O controlador manteve o mesmo processo
quando a sessão de trabalho foi retomada: a
[`auditoria de recuperação`](../results/sensitivity/g-final-recovery-audit-20261117/recovery.json)
identificou 1600 alternativas já validadas e as 1900 então em falta. Não houve
repetição dos lotes válidos, reinício do controlador ou tentativas adicionais.

Fontes definitivas:

- [`completion-manifest.json`](../results/sensitivity/completion-manifest.json),
  com a cobertura técnica concluída e a ressalva do plano original de 26 alternativas;
- [`manifesto consolidado`](../results/sensitivity/g-final-consolidated-20261117/manifest.json),
  com `selection_complete=true`, proveniência, fontes e nenhuma combinação
  válida em falta;
- [`runs.csv`](../results/sensitivity/runs.csv) e
  [`summary.csv`](../results/sensitivity/summary.csv), cópias canónicas dos CSV
  consolidados, com referências separadas por `batch_id`;
- [`blocked-configurations.csv`](../results/sensitivity/blocked-configurations.csv),
  com os três casos `1/1`, motivo e zero execuções;
- [`comparisons.csv`](../results/sensitivity/g-final-analysis-20261117/comparisons.csv),
  [`effects.csv`](../results/sensitivity/g-final-analysis-20261117/effects.csv) e
  [`manifesto da análise`](../results/sensitivity/g-final-analysis-20261117/manifest.json);
- registos reais da recolha no
  [`primeiro lote`](../results/sensitivity/g-final-preflight-20261117/collection.json)
  e nos [`35 lotes seguintes`](../results/sensitivity/g-final-remaining-20261117/collection.json).

Os 41 lotes e as 75 alternativas têm proveniência compatível; as referências
foram comparadas com a Etapa 9 sem diferenças reportadas. Código e cenários
foram conservados durante a recolha. A plataforma foi Python 3.12.3 e SPADE
4.1.4, com transporte local. Não houve recolha XMPP, alteração de parâmetros
oficiais nem atualização de aprovações.

## Parâmetros e hipóteses

As previsões nesta tabela são hipóteses, não resultados medidos.

| Fator | Referência | Alternativas | Hipótese / limite a investigar |
|---|---|---|---|
| Distância de corroboração | 3,0 células (euclidiana) | 1,0; 5,0 | Uma distância maior pode tolerar o erro de posição de B, mas associar evidência indevida. Também altera a atenuação espacial do score. |
| Janela temporal | 2,0 s simulados | 0,5; 5,0 | Pode afetar compatibilidade e atenuação temporal. Nesta janela única as observações são geradas em `t=0`, pelo que pode não haver efeito observável. |
| Qualidade das fontes | FP/FN de cada cenário | FP=FN=0; FP=FN=0,3 | Separa o efeito destas taxas do restante pipeline. Sensibilidade, confiança, alcance e erro de posição mantêm-se. |
| Prazo-base | 0,5 s reais locais | 0,1; 2,0 | Esperar mais pode tolerar atrasos, com mais demora quando falta resposta. O teto dinâmico fica desligado. |
| Pesos ETA/energia/carga | 1/1/1 | 0/1/0; 1/1/5 | Pode mudar a patrulha escolhida. A carga não tem penalização física adicional no simulador. |
| Autonomia mínima | 10% | 5%; 30% | Uma reserva maior pode aumentar recusas e ocorrências sem proposta; aplica-se a todos os recursos. |
| Prior α=β | 2,0 | 0,5; 10,0 | O prior inicial continua a ser 0,5, mas a velocidade de aprendizagem muda. |
| Limiar de patrulha | 0,25 | 0,15; 0,35 | Pode trocar recall por menos falsos alarmes. |
| Limiar do guarda | 0,65 | 0,50; 0,80 | Pode mudar pedidos diretos ao guarda. Uma missão independente confirmada pode chamar o guarda por outra regra. |
| Diversidade grupos/modalidades | 2/2 | 1/1 (bloqueada); 3/3 | Só há duas fontes. Com 3/3 a regra de evidência diversa não chama o guarda; a via de confirmação independente continua disponível. |
| Gravidade | 0,5 | 0,2; 0,9 | Com 0,9 ativa-se o limiar de patrulha grave, 0,08. A fila por prioridade continua desligada. |
| Distância de adjudicação | 1 célula (Manhattan) | 0; 2 | Só muda a cobertura aceite para aprender após uma missão; não muda a inspeção nem corrige a posição percebida. |
| Atraso de adjudicação | 30 s simulados | 5; 120 | Pode excluir ou incluir atualizações da reputação; não é um prazo de comunicação. |

A designação «ideal» do plano refere-se apenas a FP/FN nulos. Em `Source`,
`sensitivity` é uma probabilidade adicional de emissão: FP=FN=0 não garante
deteção perfeita. Colocar também `sensitivity=1` alteraria outro componente
que não foi incluído nesta definição do fator.

O rótulo **`sensor_quality=noisy` significa exatamente FP=FN=0,3 em ambas as
fontes**; não significa qualidade inferior à referência de todos os cenários.
Em B, FP desce de 0,6/0,5 para 0,3, enquanto FN sobe de 0,2/0,25 para 0,3.
Pode, portanto, reduzir falsos alarmes e piorar a deteção em simultâneo.
Sensibilidade, confiança, alcance e erro de posição mantêm-se. O nome identifica
um perfil de taxas, não uma ordenação universal de qualidade.

### Experiência bloqueada: diversidade 1/1

`ResponsePolicy.__post_init__()` exige pelo menos dois grupos e duas modalidades.
Aceitar `1/1` modificaria esse contrato e a garantia de independência usada pela
política. A alternativa fica registada como bloqueada e não é executada.

Se a seleção contiver **apenas alternativas bloqueadas**, o script grava
`plan.json` e `manifest.json` com `status="blocked"`, os motivos e todas as
contagens de execução a zero, devolvendo código 1. Não executa o self-check,
referências ou alternativas e não cria uma pasta de self-check. O `--dry-run`
também identifica o bloqueio e devolve 1, sem escrever ficheiros. Seleções
mistas continuam a executar as alternativas válidas, mantendo o bloqueio das
restantes explícito. A validação de `ResponsePolicy` não foi alterada.

Uma proposta a discutir pela equipa é uma política experimental distinta,
explicitamente identificada como ablação da exigência de diversidade, mantendo
o contrato de produção e os mesmos restantes limiares. Essa ablação permitiria
medir o custo de abdicar da independência, sem assumir que uma fonte é evidência
diversa. Exige aprovação e implementação próprias antes de medir; não se
contorna a validação por mutação de objetos nem se troca silenciosamente por 2/2.

## Implementação e rastreabilidade

`run_mvp()` em [`runner.py`](../src/isia/simulation/runner.py) recebe
`corroboration_settings` (`max_distance`, `max_time_difference`),
`receive_timeout` e `minimum_autonomy_percent`. As omissões efetivas continuam
a ser 3,0 / 2,0, prazo local de 0,5 s (XMPP: 2,0 s) e autonomia mínima de 10%.
Os pesos já configuráveis chegam a `select_best_proposal()`.

O coletor mantém o watchdog original de 30 s. Quando o override explícito de
`receive_timeout` excede 0,5 s, passa `max_seconds=None` ao runner para calcular
um orçamento que cubra os prazos operacionais maiores. Evita-se censurar uma
execução ainda válida aos 30 s. Isto é uma consequência do prazo experimental,
não uma ativação do prazo dinâmico nem uma mudança na referência.

`run_scenario()` em [`collector.py`](../src/isia/evaluation/collector.py)
aceita `runner_options` sem acrescentar campos aos JSON dos cenários. O coletor
continua a controlar as sementes, a ordem e o livro de reputação. O script
[`sensitivity.py`](../scripts/sensitivity.py) reutiliza essa função e
`flat_summary()`, que agrega as linhas produzidas por `run_metrics()`.

Cada invocação cria uma pasta exclusiva em `results/sensitivity/`. Uma pasta
anterior nunca é limpa ou reutilizada. Os CSV mantêm as métricas da Etapa 9 e
identificam fator, valor e cenário. Os relatórios, configurações efetivas e
manifesto permitem conferir sementes, ordem, código e dados de referência.
Os detalhes de cada modo e os nomes aceites pelo catálogo podem ser consultados
com `--help` e `--list`.

## Métricas

Mantêm-se TP, FP, TN, FN, precision, recall, FPR, accuracy, confirmações e
ocorrências não resolvidas, além da média, mediana, desvio-padrão e `n` dos
tempos de verificação/resposta, energia, mensagens e missões. Denominadores
nulos ficam `N/A`. Os tempos destas métricas são simulados; o tempo real da
recolha é uma medição separada e depende da máquina.

As linhas individuais permitem estudar a primeira patrulha, o motivo do
desfecho e a reputação final de `sensor-1`. Os relatórios permitem conferir
recusas, atualizações e pedidos do guarda. Não se deve confundir resultado
local de uma missão com resultado recebido pelo coordenador, nem mensagem
enviada com mensagem entregue.

Os campos suplementares do resumo são `expired_runs`, quatro motivos de
encerramento, `autonomy_insufficient`, `ranger_missions_known` (com resultado
recebido), `ranger_cfp_sent` (pedidos tentados) e `reputation_updates` (efetivamente
aceites pelo avaliador). Estas duas contagens do guarda têm semânticas diferentes.

`confirmed_runs` conta apenas verificações móveis confirmadas cujo resultado
foi recebido. Não conta todas as intervenções do guarda. Uma alternativa que
mobilize diretamente o guarda pode reduzir as verificações confirmadas porque
dispensa essa etapa, sem reduzir o número de ameaças mobilizadas. O guarda
devolve sempre `confirmed` neste simulador; isso não constitui uma avaliação
independente da exatidão de cada alerta.

### Comparação emparelhada e incerteza descritiva

Cada alternativa é comparada com a referência do **mesmo lote e cenário**.
As linhas são emparelhadas por repetição, episódio e semente. A/B/C têm,
respetivamente, 40/60/40 execuções por valor, distribuídas por 20 sementes.
As referências repetidas em lotes diferentes não são juntadas para aumentar
artificialmente a dimensão da amostra.

A análise calcula diferenças absolutas e relativas. Uma diferença de recall
de 0,30 corresponde a 30 pontos percentuais; uma diferença relativa de 0,30
corresponde a 30% do valor de referência. A diferença relativa fica `N/A` se
a referência for zero ou se algum valor estiver indisponível. Precision,
recall e FPR continuam a ser razões de contagens, com `N/A` quando não há
denominador; não se calcula a média de razões por episódio.

Para os tempos, distinguem-se as médias marginais publicadas e a diferença
nos pares em que ambos os valores existem. A segunda comparação usa o mesmo
conjunto de execuções, enquanto a primeira pode mudar por haver mais ou menos
resultados recebidos. A análise regista os dois `n`, o número de pares comuns e
a diferença de cobertura. Uma resposta recebida mais depressa não equivale a
uma melhoria de cobertura, nem um tempo ausente é substituído por zero.

O script de análise usa bootstrap emparelhado descritivo: 2000 reamostragens,
semente 917, preservando juntos todos os episódios de cada semente e os seus
pares referência/alternativa. Em cada amostra recalculam-se as contagens e
as razões. Os percentis 2,5 e 97,5% descrevem a variação das diferenças na
trajetória observada. As amostras sem denominador ou sem pares válidos são
excluídas dessa estatística, sendo registado o número de amostras válidas.

**Estes intervalos não são intervalos inferenciais validados:** a reputação
aprende entre episódios e entre sementes consecutivas, pelo que nem os 20
grupos de sementes são independentes. O bootstrap não volta a executar a
aprendizagem na ordem reamostrada. É uma análise de sensibilidade descritiva,
não um teste de significância nem uma garantia de cobertura de 95%. Uma
inferência mais forte exigiria várias trajetórias completas independentes.

## Verificação da referência

O self-check inicial usa a repetição 0 de A, semente 1000, com episódios
`threat` e `empty`, na ordem original. Compara cada indicador com a linha
correspondente de `results/experiments/runs.csv`; não compara duas execuções
com a média de quarenta execuções.

O modo completo executa as 20 repetições originais de cada cenário e compara
**as 140 linhas individuais** da variante `full` com
`results/experiments/runs.csv`, além dos três agregados com as linhas `full`
de `results/experiments/summary.csv`. Com `--scenario`, compara a sequência
completa dos cenários escolhidos. Também verifica a ordem devolvida das
execuções; não a ordena para ocultar diferenças.

O self-check só passa se as duas comparações passarem. Médias e contagens iguais
podem esconder missões, mensagens ou reputações diferentes entre episódios.
Todas as colunas individuais publicadas entram na comparação, incluindo
`first_patrol` e `reputation_sensor_1`, que não constam dos agregados.
`actual-runs.csv` guarda as linhas individuais, `actual.csv` mantém os agregados
e `comparison.json` separa `run_comparison` de `summary_comparison`, com as
respetivas diferenças. Os campos anteriores são preservados: `run_count` é o
número de execuções, e `compared_rows` continua a contar os agregados no modo
`full`; as contagens de cada comparação estão nos dois objetos específicos.

Uma recolha reduzida não serve como self-check completo. O teste inicial é
uma condição necessária para experimentar; não comprova toda a referência.

A referência completa foi entretanto executada em
[`20261117T205436Z-475d73da`](../results/sensitivity/20261117T205436Z-475d73da/manifest.json):
**140 linhas individuais e três agregados comparados, ambas as verificações
aprovadas e zero diferenças**. Este resultado é distinto dos ensaios iniciais
registados abaixo. Os lotes finais voltam a verificar a primeira repetição de A
antes de executar as suas referências e alternativas.

As sementes estabilizam perceções e decisões aleatórias. No cenário C,
a sequência dos envios assíncronos determina a que mensagem corresponde cada
sorteio de perda. A carga da máquina também afeta os prazos reais. Uma diferença
é registada e investigada, nunca apagada por alterar valores ou escolher uma
semente favorável. Não há tolerância científica para classificar divergências
de decisão como simples arredondamento.

## Calibração descritiva do score (7.6)

O `suspicion_score` é uma heurística, não uma probabilidade calibrada. A análise
usa **um score inicial por execução**, de `verification.response_policy`, antes
de incorporar resultados das missões. A verdade real é lida exclusivamente
pelo avaliador, em `ground_truth.events`, com a mesma unidade de `run_metrics()`.

Os intervalos são `[0; 0,25[`, `[0,25; 0,50[`, `[0,50; 0,75[` e `[0,75; 1]`.
Para cada cenário e intervalo, contam-se amostras e ameaças reais; a frequência
é ameaças/amostras. Intervalos vazios ficam `N/A`. Não se atribui score zero a
execuções sem score. Resultados de variantes ou alternativas diferentes não
devem ser misturados numa única curva de calibração.

A auditoria local encontrou os 560 relatórios antigos da Etapa 9, incluindo
os 140 `full`. Estes têm score inicial em 19/40 execuções de A, 46/60 de B e
19/40 de C. Não é necessário regenerá-los neste computador. Estes relatórios
são ignorados pelo Git e podem faltar noutro computador. Nesse caso, o plano
é primeiro medir a cobertura em falta e só depois planear uma regeneração
sequencial de `full`, em `results/sensitivity/`, preservando os dados publicados.
Essa recolha adicional não faz parte desta intervenção.

**Viés de seleção:** a tabela estima a frequência de ameaça condicionada à
existência de score. Execuções sem alerta ou sem avaliação podem ficar de fora,
sobretudo negativos vazios e falhas de deteção. A cobertura por cenário acompanha
a tabela; a frequência não estima a prevalência global, a exatidão do sistema
nem probabilidades aplicáveis a ocorrências futuras. A aprendizagem sequencial
também torna estas amostras dependentes. Calibrar probabilidades exigiria um
protocolo separado de treino/validação, mais dados e avaliação da incerteza.

### Calibração medida na recolha final

A análise utiliza **78 perfis separados**: 75 combinações alternativas e uma
referência canónica por cenário, obtida do self-check completo. São 3640
relatórios, 2126 com score e 1514 sem score, distribuídos por 312 intervalos.
Estes totais descrevem a cobertura do ficheiro; não misturam os perfis numa
única curva de calibração nem tornam as referências repetidas novas amostras.

As tabelas completas estão em
[`calibration.csv`](../results/sensitivity/calibration.csv) e
[`calibration-coverage.csv`](../results/sensitivity/calibration-coverage.csv),
e os registos por execução em
[`calibration-samples.csv`](../results/sensitivity/g-final-analysis-20261117/calibration-samples.csv).
Para a referência original:

| Intervalo | A: n / ameaças / frequência | B: n / ameaças / frequência | C: n / ameaças / frequência |
|---|---:|---:|---:|
| [0; 0,25[ | 2 / 2 / 100% | 23 / 3 / 13,04% | 3 / 3 / 100% |
| [0,25; 0,50[ | 4 / 4 / 100% | 23 / 13 / 56,52% | 7 / 7 / 100% |
| [0,50; 0,75[ | 13 / 13 / 100% | 0 / 0 / N/A | 9 / 9 / 100% |
| [0,75; 1] | 0 / 0 / N/A | 0 / 0 / N/A | 0 / 0 / N/A |

| Cenário | Relatórios | Com score | Sem score | Ameaças sem score |
|---|---:|---:|---:|---:|
| A | 40 | 19 | 21 | 1 |
| B | 60 | 46 | 14 | 4 |
| C | 40 | 19 | 21 | 1 |

Em A/C todos os scores disponíveis são de ameaças: os 20 episódios negativos
vazios não geram score, tal como uma ameaça não detetada. Logo, 100% nos
intervalos preenchidos não significa deteção perfeita ou probabilidades
corretamente calibradas. Em B há positivos e negativos com score, mas poucos
casos por intervalo e dependência da aprendizagem.

O intervalo [0,75; 1] ficou vazio em todos os 78 perfis. A confiança das fontes
é no máximo 0,8, o par mantém reputação 0,5 e só a fonte iniciadora aprende;
com os fatores espaciais/temporais ≤1, o score de duas fontes fica abaixo de
0,6 em A/C e de 0,525 em B. A parte superior da escala não é exercitada pela
matriz. Não há dados para validar interpretações probabilísticas nessa faixa.
A calibração apresentada é descritiva e condicionada à seleção; transformar
estes scores em probabilidades exigiria outro protocolo, com validação
independente e dados que representassem os casos sem score e os negativos.

## Resultados por parâmetro

Fonte comum: [`comparisons.csv`](../results/sensitivity/g-final-analysis-20261117/comparisons.csv) e
[`effects.csv`](../results/sensitivity/g-final-analysis-20261117/effects.csv). Cada linha alternativa
usa a referência do seu próprio lote. São 20 sementes por valor: 40 execuções
em A/C e 60 em B. As configurações dos 75 overrides válidos estão auditadas em
[`application-audit.csv`](../results/sensitivity/g-final-analysis-20261117/application-audit.csv): 69 também têm o
valor efetivo reportado; os seis perfis de qualidade das fontes são verificados
pela configuração do cenário e proveniência do código, pois FP/FN não são
repetidos no relatório operacional. Cada cenário contém 20 ameaças; os negativos
são 20 em A/C e 40 em B.

Nas tabelas, P/R/FPR são proporções; `tv [n] / tg [n]` são as médias de verificação
e resposta do guarda, em segundos simulados, seguidas do número de resultados
disponíveis. Energia é a média de pontos percentuais por execução; Msg./perdidas
são médias de tentativas de envio e perdas por execução. Conf./NR/atualiz. são
contagens de verificações confirmadas, ocorrências não resolvidas e atualizações
de reputação aceites. `N/A [0]` não significa tempo zero. As contagens de TP/FP/TN/FN
são de classificação por mobilização, não de missões concluídas.

### 1. Distância de corroboração (4.1)

| Cen. | Valor | TP/FP/TN/FN | P/R/FPR | tv [n] / tg [n] | Energia | Msg./perdidas | Conf./NR/atualiz. |
|---|---|---:|---|---|---:|---|---|
| A | 3 (ref.) | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| A | 1 | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| A | 5 | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| B | 3 (ref.) | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | 1 | 7/5/35/13 | 0,583/0,35/0,125 | 6 [12] / 12 [1] | 2,167 | 3,217/0 | 1/0/1 |
| B | 5 | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| C | 3 (ref.) | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |
| C | 1 | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |
| C | 5 | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |

Em B, reduzir a distância de 3 para 1 célula baixou o recall de 0,65 para 0,35
(TP 13→7; FN 7→13), mas também o FPR de 0,25 para 0,125 (FP 10→5). A energia
média passou de 4,167 para 2,167 p.p., em parte porque se mobilizaram menos
recursos. Não é um ganho de eficiência que conserve a cobertura.
A distância participa tanto no corte de compatibilidade como na atenuação
espacial do score. Com 5 células, as métricas de saída não mudaram: em B, o
score mudou em 20 dos 46 pares com score, mas nenhuma decisão atravessou um
limiar. A/C têm posições percebidas coincidentes, explicando a invariância.
Δ emparelhado de recall: -0,3 (-46,15% relativamente à referência emparelhada); intervalo central descritivo [-0,5; -0,1], 60 pares; 20 sementes.

### 2. Janela temporal (4.1)

| Cen. | Valor | TP/FP/TN/FN | P/R/FPR | tv [n] / tg [n] | Energia | Msg./perdidas | Conf./NR/atualiz. |
|---|---|---:|---|---|---:|---|---|
| A | 2 (ref.) | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| A | 0,5 | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| A | 5 | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| B | 2 (ref.) | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | 0,5 | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | 5 | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| C | 2 (ref.) | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |
| C | 0,5 | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |
| C | 5 | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |

As duas alternativas não alteraram as métricas por execução nos três cenários.
O valor foi aplicado à compatibilidade e ao score; as leituras usadas na
decisão inicial têm `observed_at=0`, pelo que Δt=0 e o fator temporal é 1.
Atrasos de transporte são reais e não alteram retroativamente esse timestamp.
Este desenho não exercita a sensibilidade temporal: o resultado não demonstra
que a escolha da janela seja irrelevante em observações desencontradas.

### 3. Qualidade das fontes (4.3)

| Cen. | Valor | TP/FP/TN/FN | P/R/FPR | tv [n] / tg [n] | Energia | Msg./perdidas | Conf./NR/atualiz. |
|---|---|---:|---|---|---:|---|---|
| A | original (ref.) | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| A | ideal | 20/0/20/0 | 1/1/0 | 6 [20] / 12 [20] | 10 | 7,5/0 | 20/0/20 |
| A | noisy | 12/0/20/8 | 1/0,6/0 | 6 [12] / 12 [12] | 6 | 4,65/0 | 12/0/12 |
| B | original (ref.) | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | ideal | 17/0/40/3 | 1/0,85/0 | 5,824 [17] / 12 [2] | 3,067 | 3,067/0 | 2/0/2 |
| B | noisy | 12/0/40/8 | 1/0,6/0 | 6,083 [12] / 12 [2] | 2,367 | 2,467/0 | 2/0/2 |
| C | original (ref.) | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |
| C | ideal | 18/0/20/2 | 1/0,9/0 | 6 [11] / 17 [7] | 5,25 | 4,75/0,45 | 11/11/11 |
| C | noisy | 7/0/20/13 | 1/0,35/0 | 6 [4] / 17 [2] | 1,75 | 2,075/0,225 | 4/5/4 |

O perfil `ideal` elevou o recall de A de 0,85 para 1,00 e o de B de 0,65 para
0,85, removendo os 10 falsos positivos de B nesta amostra. Em C, o recall passou
de 0,80 para 0,90, mantendo perdas de comunicação e escassez.
`noisy` reduziu o recall de A para 0,60 e o de C para 0,35. Em B, porém, reduziu
FP de 10 para 0 e manteve 12 dos 20 positivos mobilizados (recall 0,60).
O rótulo significa FP=FN=0,3: em B melhora as taxas FP da referência, mas piora FN.
O custo menor de `noisy` em A/C acompanha ameaças não atendidas e não deve ser
interpretado como melhoria geral. A precisão perfeita de alguns perfis é
amostral; sensibilidade e erro de posição não foram tornados ideais.
Δ emparelhado de recall: -0,45 (-56,25% relativamente à referência emparelhada); intervalo central descritivo [-0,65; -0,25], 40 pares; 20 sementes.

### 4. Prazo-base de espera (5.1)

| Cen. | Valor | TP/FP/TN/FN | P/R/FPR | tv [n] / tg [n] | Energia | Msg./perdidas | Conf./NR/atualiz. |
|---|---|---:|---|---|---:|---|---|
| A | 0,5 (ref.) | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| A | 0,1 | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| A | 2 | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| B | 0,5 (ref.) | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | 0,1 | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | 2 | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| C | 0,5 (ref.) | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |
| C | 0,1 | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |
| C | 2 | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |

As alternativas não alteraram classificação, desfechos, mensagens ou tempos
simulados. Os atrasos injetados em C são 0,05 s, inferiores aos três prazos;
esperar mais não recupera mensagens perdidas, pois não há retransmissão.
O efeito aparece no relógio real: em C, as 40 execuções demoraram 44,384 s na referência, 35,095 s com 0,1 s e 78,823 s com 2 s. As diferenças relativas foram -20,93% e +77,59%.
São medições de uma máquina e de um lote por valor, sem intervalo por execução.
O prazo também multiplica por dez a espera pelo resultado da missão; o teto
dinâmico do Bloco F continua desligado.

### 5. Pesos de ETA, energia e carga (5.2)

| Cen. | Valor | TP/FP/TN/FN | P/R/FPR | tv [n] / tg [n] | Energia | Msg./perdidas | Conf./NR/atualiz. |
|---|---|---:|---|---|---:|---|---|
| A | 1/1/1 (ref.) | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| A | 0/1/0 | 17/0/20/3 | 1/0,85/0 | 4 [17] / 10 [17] | 6,8 | 6,475/0 | 17/0/17 |
| A | 1/1/5 | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| B | 1/1/1 (ref.) | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | 0/1/0 | 13/10/30/7 | 0,565/0,65/0,25 | 4,174 [23] / 10 [2] | 2,767 | 4,767/0 | 2/0/2 |
| B | 1/1/5 | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| C | 1/1/1 (ref.) | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |
| C | 0/1/0 | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |
| C | 1/1/5 | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |

Só energia trocou veículo por drone nas 17 verificações de A e nas 23 de B,
sem alterar TP/FP/FN/TN. Em A, tv passou de 6 para 4 s, tg de 12 para 10 s e
energia média de 8,5 para 6,8 p.p. (−20%). Em B, tv passou de 6 para 4,174 s
e energia de 4,167 para 2,767 p.p. (−33,6%). A classificação constante torna
este compromisso diferente de poupar energia deixando de mobilizar.
Carga 5 não mudou os resultados: reforçou o veículo já escolhido. Em C, o
drone com 15% e reserva mínima de 10% era inelegível; os pesos não mudaram o
único candidato elegível. A carga não tem penalização física adicional no simulador.
Δ emparelhado de tv (s): -2 (-33,33% relativamente à referência emparelhada); intervalo central descritivo [-2; -2], 17 pares; 20 sementes.

### 6. Autonomia mínima (5.2)

| Cen. | Valor | TP/FP/TN/FN | P/R/FPR | tv [n] / tg [n] | Energia | Msg./perdidas | Conf./NR/atualiz. |
|---|---|---:|---|---|---:|---|---|
| A | 10 (ref.) | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| A | 5 | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| A | 30 | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| B | 10 (ref.) | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | 5 | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | 30 | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| C | 10 (ref.) | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |
| C | 5 | 16/0/20/4 | 1/0,8/0 | 4,429 [14] / 14 [8] | 5,05 | 5,125/0,5 | 14/8/14 |
| C | 30 | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |

A/B mantiveram os resultados nas duas alternativas porque os recursos começam
com 100% de autonomia e os percursos não atingem as reservas comparadas.
Em C, o mínimo de 5% tornou o drone elegível: 15% iniciais menos 6 p.p. de
ida e volta deixam 9%, suficientes para 5%, mas não para 10%/30%. As verificações
confirmadas subiram de 10 para 14 e NR desceu de 10 para 8, com recall constante
0,80. A energia média subiu de 4,5 para 5,05 p.p., porque se completaram mais missões.
A verificação marginal passou de 6 para 4,429 s; é necessário considerar os
pares comuns porque a cobertura aumentou. Reduzir a reserva troca margem
configurada por disponibilidade; não valida uma margem de segurança de campo.
Δ emparelhado de tv (s): -1,333 (-22,22% relativamente à referência emparelhada); intervalo central descritivo [-2; -0,667], 9 pares; 20 sementes.

### 7. Prior da reputação (7.1)

| Cen. | Valor | TP/FP/TN/FN | P/R/FPR | tv [n] / tg [n] | Energia | Msg./perdidas | Conf./NR/atualiz. |
|---|---|---:|---|---|---:|---|---|
| A | 2 (ref.) | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| A | 0,5 | 18/0/20/2 | 1/0,9/0 | 6 [18] / 12 [18] | 9 | 6,8/0 | 18/0/18 |
| A | 10 | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| B | 2 (ref.) | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | 0,5 | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | 10 | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| C | 2 (ref.) | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |
| C | 0,5 | 18/0/20/2 | 1/0,9/0 | 6 [12] / 17 [8] | 5,5 | 4,825/0,425 | 12/10/12 |
| C | 10 | 15/0/20/5 | 1/0,75/0 | 6 [9] / 17 [5] | 4 | 3,925/0,425 | 9/10/9 |

α=β=0,5 acelerou a aprendizagem: A passou de 17 para 18 TP e C de 16 para 18.
Com α=β=10, A manteve 17 TP e C desceu para 15. Em B, a classificação ficou
igual, embora a reputação final de sensor-1 passasse de 0,667 para 0,833 ou 0,545.
A reputação inicial continua a ser 0,5. Só verificações confirmadas geram
atualizações aceites; `not_confirmed` é inconclusivo, pelo que a reputação
não é penalizada pelos falsos alarmes de B nesta implementação. Com uma fonte
isolada em A/C, o score é 0,3×reputação: cruzar 0,25 exige reputação ≥5/6.
Diferenças de uma ou duas ameaças devem ser lidas como efeitos desta trajetória,
não como evidência geral de superioridade de um prior.
Δ emparelhado de recall: +0,1 (+12,5% relativamente à referência emparelhada); intervalo central descritivo [0; +0,25], 40 pares; 20 sementes.

### 8. Limiar de patrulha (7.2)

| Cen. | Valor | TP/FP/TN/FN | P/R/FPR | tv [n] / tg [n] | Energia | Msg./perdidas | Conf./NR/atualiz. |
|---|---|---:|---|---|---:|---|---|
| A | 0,25 (ref.) | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| A | 0,15 | 19/0/20/1 | 1/0,95/0 | 6 [19] / 12 [19] | 9,5 | 7,125/0 | 19/0/19 |
| A | 0,35 | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| B | 0,25 (ref.) | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | 0,15 | 15/23/17/5 | 0,395/0,75/0,575 | 5,763 [38] / 12 [2] | 6,367 | 6,767/0 | 2/0/2 |
| B | 0,35 | 2/1/39/18 | 0,667/0,1/0,025 | 6 [3] / N/A [0] | 0,5 | 1,933/0 | 0/0/0 |
| C | 0,25 (ref.) | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |
| C | 0,15 | 19/0/20/1 | 1/0,95/0 | 6 [13] / 17 [8] | 6 | 5,125/0,475 | 13/11/13 |
| C | 0,35 | 15/0/20/5 | 1/0,75/0 | 6 [9] / 17 [5] | 4 | 3,925/0,425 | 9/10/9 |

Em B, subir 0,25→0,35 reduziu FP 10→1, mas TP 13→2: recall 0,65→0,10 e FPR
0,25→0,025. A precisão de 0,667 assenta em apenas três mobilizações. A energia
média 4,167→0,5 p.p. acompanha 18 ameaças não mobilizadas e zero verificações
confirmadas; não constitui uma melhoria global.
Baixar para 0,15 elevou o recall de B para 0,75, com FP 23 e FPR 0,575. Em A/C,
atingiu recall 0,95, mas A/C só têm negativos vazios. O limiar controla um
compromisso real entre cobertura e alarmes, sem um valor ótimo demonstrado.
Δ emparelhado de recall: -0,55 (-84,62% relativamente à referência emparelhada); intervalo central descritivo [-0,75; -0,35], 60 pares; 20 sementes.

### 9. Limiar do guarda (7.2)

| Cen. | Valor | TP/FP/TN/FN | P/R/FPR | tv [n] / tg [n] | Energia | Msg./perdidas | Conf./NR/atualiz. |
|---|---|---:|---|---|---:|---|---|
| A | 0,65 (ref.) | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| A | 0,5 | 17/0/20/3 | 1/0,85/0 | 6 [4] / 7,412 [17] | 5,25 | 3,875/0 | 4/0/4 |
| A | 0,8 | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| B | 0,65 (ref.) | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | 0,5 | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | 0,8 | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| C | 0,65 (ref.) | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |
| C | 0,5 | 15/0/20/5 | 1/0,75/0 | 6 [4] / 10,4 [5] | 2,75 | 2,9/0,375 | 4/10/4 |
| C | 0,8 | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |

Em A, 0,5 manteve a classificação e as 17 missões conhecidas do guarda, mas
reduziu verificações confirmadas e atualizações de 17 para 4: o guarda passou
a ser chamado diretamente em parte dos casos. O tempo médio de resposta passou
de 12 para 7,412 s e energia de 8,5 para 5,25 p.p. Menos confirmações móveis
não significa, neste caso, menos intervenções do guarda.
Em C, 0,5 baixou o recall de 0,80 para 0,75 e as atualizações de 10 para 4;
interromper a aprendizagem móvel impediu uma mobilização isolada tardia.
B não mudou, e 0,8 não mudou nenhum cenário. O par sensor-2 mantém reputação
0,5; com duas fontes e confiança ≤0,8, o score não chega a 0,65/0,8.
A chamada do guarda após verificação confirmada segue outra via operacional.
Δ emparelhado de tg (s): -4,588 (-38,24% relativamente à referência emparelhada); intervalo central descritivo [-5,648; -3,2], 17 pares; 20 sementes.

### 10. Diversidade das fontes (7.3)

| Cen. | Valor | TP/FP/TN/FN | P/R/FPR | tv [n] / tg [n] | Energia | Msg./perdidas | Conf./NR/atualiz. |
|---|---|---:|---|---|---:|---|---|
| A | 2/2 (ref.) | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| A | 3/3 | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| A | 1/1 (bloqueada) | N/A | N/A | N/A | N/A | N/A | N/A |
| B | 2/2 (ref.) | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | 3/3 | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | 1/1 (bloqueada) | N/A | N/A | N/A | N/A | N/A | N/A |
| C | 2/2 (ref.) | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |
| C | 3/3 | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |
| C | 1/1 (bloqueada) | N/A | N/A | N/A | N/A | N/A | N/A |

3/3 não alterou as métricas dos três cenários. Só existem duas fontes, mas a
chamada direta com o limiar de 0,65 já não era atingida nesta configuração.
O guarda continua a ser mobilizado após uma verificação móvel confirmada;
a exigência 3/3 não bloqueia essa via. Os valores efetivos da política foram
auditados. Não há evidência de que três fontes sejam dispensáveis num sistema
que efetivamente as possua e atinja a chamada direta.
1/1 não foi executado: permanece bloqueado pelo contrato de ResponsePolicy.

### 11. Gravidade (7.4)

| Cen. | Valor | TP/FP/TN/FN | P/R/FPR | tv [n] / tg [n] | Energia | Msg./perdidas | Conf./NR/atualiz. |
|---|---|---:|---|---|---:|---|---|
| A | 0,5 (ref.) | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| A | 0,2 | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| A | 0,9 | 19/0/20/1 | 1/0,95/0 | 6 [19] / 12 [19] | 9,5 | 7,125/0 | 19/0/19 |
| B | 0,5 (ref.) | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | 0,2 | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | 0,9 | 16/30/10/4 | 0,348/0,8/0,75 | 5,804 [46] / 12 [2] | 7,7 | 7,833/0 | 2/0/2 |
| C | 0,5 (ref.) | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |
| C | 0,2 | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |
| C | 0,9 | 19/0/20/1 | 1/0,95/0 | 6 [13] / 17 [8] | 6 | 5,125/0,475 | 13/11/13 |

Em B, 0,9 elevou TP 13→16 e o recall 0,65→0,80, mas FP 10→30 e FPR
0,25→0,75. A energia média passou de 4,167 para 7,7 p.p. (+84,8%), sem aumentar
as duas verificações confirmadas de B. Em A/C, o recall atingiu 0,95.
0,2 não mudou as métricas, porque 0,2 e 0,5 ficam abaixo do limiar grave 0,8.
Com 0,9, a patrulha usa o limiar grave 0,08 e aceita evidência local fraca.
A prioridade do CFP também muda, mas não intervém na seleção nem numa fila
ordenada, que continua desligada. O efeito observado é o da política de
mobilização por gravidade; não demonstra benefício da fila do Bloco F.
Δ emparelhado de FPR: +0,5 (+200% relativamente à referência emparelhada); intervalo central descritivo [+0,35; +0,65], 60 pares; 20 sementes.

### 12. Distância de adjudicação (7.5)

| Cen. | Valor | TP/FP/TN/FN | P/R/FPR | tv [n] / tg [n] | Energia | Msg./perdidas | Conf./NR/atualiz. |
|---|---|---:|---|---|---:|---|---|
| A | 1 (ref.) | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| A | 0 | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| A | 2 | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| B | 1 (ref.) | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | 0 | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | 2 | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| C | 1 (ref.) | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |
| C | 0 | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |
| C | 2 | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |

0 e 2 células não alteraram as métricas nem as atualizações de reputação.
Os valores chegam a result_from_mission, mas a distância medida é entre a
célula inspecionada e a posição percebida da observação, que é o destino da
missão. Nestes percursos essa distância é zero. Em B, uma inspeção da célula
errada devolve `not_confirmed` e não aprende; alargar a distância de adjudicação
não corrige o erro de posição nem transforma esse resultado em confirmação.

### 13. Prazo de adjudicação (7.5)

| Cen. | Valor | TP/FP/TN/FN | P/R/FPR | tv [n] / tg [n] | Energia | Msg./perdidas | Conf./NR/atualiz. |
|---|---|---:|---|---|---:|---|---|
| A | 30 (ref.) | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| A | 5 | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/0 |
| A | 120 | 17/0/20/3 | 1/0,85/0 | 6 [17] / 12 [17] | 8,5 | 6,475/0 | 17/0/17 |
| B | 30 (ref.) | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| B | 5 | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/0 |
| B | 120 | 13/10/30/7 | 0,565/0,65/0,25 | 6 [23] / 12 [2] | 4,167 | 4,767/0 | 2/0/2 |
| C | 30 (ref.) | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |
| C | 5 | 15/0/20/5 | 1/0,75/0 | 6 [9] / 17 [5] | 4 | 3,925/0,425 | 9/10/0 |
| C | 120 | 16/0/20/4 | 1/0,8/0 | 6 [10] / 17 [6] | 4,5 | 4,225/0,425 | 10/10/10 |

O limite de 5 s excluiu a aprendizagem das verificações confirmadas padrão,
que terminam aos 6 s simulados. 120 s manteve os resultados de 30 s. O efeito
é posterior à decisão do episódio: só pode alterar decisões seguintes pela
reputação. A tabela distingue essas atualizações de mobilizações ou missões.
O código usa completed_at−observed_at, não o instante real de entrega da
mensagem. Por isso, a ausência de efeito de 120 s não mede tolerância a
120 segundos de atraso de rede.


## Síntese dos efeitos e ausência de diferenças

O critério do diapositivo de sensibilidade é o maior valor absoluto de Δprecision,
Δrecall ou ΔFPR observado por parâmetro; são comparadas proporções na mesma
escala, sem combinar segundos e energia num índice arbitrário. Os dois maiores
casos foram ambos em B:

| Fator | Alteração principal | Diferença absoluta | Diferença relativa | Intervalo central descritivo da diferença |
|---|---|---:|---:|---|
| Patrulha 0,25→0,35 | Recall 0,65→0,10 | −0,55 (−55 p.p.) | −84,62% | [−0,75; −0,35] |
| Gravidade 0,5→0,9 | FPR 0,25→0,75 | +0,50 (+50 p.p.) | +200% | [+0,35; +0,65] |

Há 20 sementes e 60 execuções em cada braço de B; recall tem denominador de
20 ameaças e FPR de 40 negativos. Os intervalos usam 2000 reamostragens e a
semente 917. São descritivos: estes números não demonstram significância
estatística nem superioridade de uma política.

**55 das 75 combinações não alteraram a classificação por mobilização.** Destas,
46 também não alteraram nenhuma métrica individual comparada, incluindo
patrulha, reputação e desfecho. A lista exata está em
[`findings.json`](../results/sensitivity/g-final-analysis-20261117/findings.json):

| Configuração | Cenários sem diferenças nas métricas individuais comparadas |
|---|---|
| Custo 1/1/5 | A, B, C |
| Custo 0/1/0 | C |
| Distância de corroboração 1 | A, C |
| Distância de corroboração 5 | A, B, C |
| Janela temporal 0,5 e 5 | A, B, C |
| Prazo-base 0,1 e 2 | A, B, C — com diferenças no tempo real de C |
| Autonomia mínima 5 | A, B |
| Autonomia mínima 30 | A, B, C |
| Limiar de patrulha 0,35 | A |
| Limiar do guarda 0,5 | B |
| Limiar do guarda 0,8 | A, B, C |
| Diversidade 3/3 | A, B, C |
| Gravidade 0,2 | A, B, C |
| Distância de adjudicação 0 e 2 | A, B, C |
| Prazo de adjudicação 120 | A, B, C |

Esta invariância não significa relatórios idênticos: os valores efetivos dos
parâmetros mudam, os identificadores de conversação são locais e o tempo real
varia. Em particular, o prazo-base tem efeito físico mesmo sem alterar as
métricas por execução; a distância 5 em B altera scores sem mudar decisões.
Os mecanismos foram conferidos na configuração, no código e, quando
reportados, nos valores efetivos dos relatórios.

A melhoria depende do objetivo. Só energia melhora rapidez/consumo em A/B sem
reduzir a classificação. Qualidade `ideal` melhora deteção e falsos alarmes em
B neste conjunto; autonomia 5 melhora confirmações/NR em C, com menor margem
configurada e mais energia total consumida. Um limiar alto poupa alarmes e
energia, mas pode deixar ameaças por mobilizar. Gravidade alta aumenta
cobertura e também falsos alarmes. Não foi encontrado nem procurado um valor
universalmente ótimo; os valores oficiais permanecem intactos.

## Validação final

A análise verificou a coerência entre relatórios, CSV e configurações. O
consolidado cobre as 75 combinações válidas, mantém as 41 referências separadas
por lote e não contém alternativas duplicadas. Os pilotos e a configuração
bloqueada não são tratados como resultados medidos.

A suite completa passou **572 testes em 63,598 s**, sem falhas, erros ou testes
ignorados (64,420 s incluindo arranque). O comando e o resultado reais estão em
[`unittest-full.json`](../results/sensitivity/g-final-validation-20261117/unittest-full.json)
e o log em
[`unittest-full.log`](../results/sensitivity/g-final-validation-20261117/unittest-full.log).
Inclui regressões de defaults, propagação dos overrides, aprendizagem
sequencial, referências individuais/agregadas, consolidação, análise,
calibração e compatibilidade do Bloco F.

Uma verificação independente conferiu as 114 linhas numéricas das 13 tabelas
contra os CSV e identificou as três linhas bloqueadas, sem divergências além
do arredondamento de apresentação:
[`documentation-check.json`](../results/sensitivity/g-final-validation-20261117/documentation-check.json).

## Historial e validação da infraestrutura

Os ensaios de preparação estão preservados, mas não entram na recolha final:

- A referência inicial comparou duas linhas de A com zero diferenças:
  [`comparison.json`](../results/sensitivity/g-reference-initial-20261117/self-check/comparison.json).
- O piloto de custo só por energia usou uma repetição de A e demonstrou a troca
  veículo → drone. Os seus
  [`runs.csv`](../results/sensitivity/g-energy-smoke-20261117/runs.csv) e
  [`summary.csv`](../results/sensitivity/g-energy-smoke-20261117/summary.csv)
  permanecem separados das 20 repetições finais. Os comandos dessa primeira
  intervenção constam de
  [`commands.json`](../results/sensitivity/g-validation-20261117/commands.json).
- A primeira análise dos 140 relatórios `full` da Etapa 9 está em
  [`calibration.csv`](../results/sensitivity/g-calibration-20261117/calibration.csv)
  e [`calibration-coverage.csv`](../results/sensitivity/g-calibration-20261117/calibration-coverage.csv).
  Não exigiu regenerar relatórios nem alterar dados oficiais.
- A suite da primeira implementação passou 531 testes em 63,090 s:
  [`log`](../results/sensitivity/g-validation-20261117/unittest-full.log) e
  [`comando`](../results/sensitivity/g-validation-20261117/unittest-full.json).
  A auditoria de 587 ficheiros preexistentes não encontrou alterações nos
  dados protegidos:
  [`integrity.json`](../results/sensitivity/g-validation-20261117/integrity.json).
- A revisão seguinte passou 51 testes relevantes em 4,812 s, incluindo 20
  regressões novas e os testes de compatibilidade F:
  [`tests.log`](../results/sensitivity/g-review-validation-20261117/tests.log) e
  [`review.json`](../results/sensitivity/g-review-validation-20261117/review.json).
  Estes testes já detetam agregados iguais com execuções individuais diferentes.
- A chamada exclusivamente bloqueada `source_diversity=1` devolveu código 1,
  estado `blocked` e zero simulações, guardando apenas
  [`plan.json`](../results/sensitivity/g-review-blocked-20261117/plan.json) e
  [`manifest.json`](../results/sensitivity/g-review-blocked-20261117/manifest.json).
  A validação da política foi preservada.

A referência completa posterior passou as comparações das 140 execuções e dos
três agregados, como descrito na secção de verificação. Os resultados da recolha
final são apresentados separadamente; pilotos, testes e lotes incompletos não
são tratados como repetições adicionais.

## Recolha por lotes e consolidação

A estratégia escolhida usa os filtros existentes `--parameter`, `--value` e
`--scenario`. Cada lote mantém **as 20 repetições completas de cada combinação
de parâmetro, valor e cenário**, com os episódios na ordem original. Não há
retoma por episódio nem gravação/restauro intermédio do `ReputationBook`.
Se um lote falhar, repete-se esse lote inteiro numa pasta nova.

Não se juntam dois ensaios com `--repetitions 10` como se fossem 20 repetições:
ambos começam na semente 1000 e no prior inicial. Também não se divide uma
trajetória em faixas de sementes com livros de reputação reiniciados. Os ensaios
reduzidos continuam a servir para diagnóstico, separados da recolha final.

Depois de o self-check completo passar, estes exemplos recolhem dois lotes
independentes. **Não foram executados nesta revisão:**

```bash
PYTHONPATH=src python scripts/sensitivity.py --parameter corroboration_distance --scenario A --run-id lote-distancia-A
PYTHONPATH=src python scripts/sensitivity.py --parameter minimum_autonomy --scenario A --run-id lote-autonomia-A

# Só depois de ambos terminarem: unir os CSV numa terceira pasta exclusiva.
PYTHONPATH=src python scripts/consolidate_sensitivity.py results/sensitivity/lote-distancia-A results/sensitivity/lote-autonomia-A --run-id consolidado-A
```

[`consolidate_sensitivity.py`](../scripts/consolidate_sensitivity.py) valida os
lotes antes de criar a saída. Exige recolhas concluídas com a verificação da
referência aprovada, configurações oficiais, 20 repetições, grupos completos,
sementes e ordem originais, além de código, referências e ambiente compatíveis
(hashes, commit, Python, SPADE e plataforma). Confere os agregados a partir das
linhas individuais. Recusa pilotos, lotes falhados, alternativas sobrepostas e
pastas já consolidadas. As entradas são pastas distintas diretamente em
`results/sensitivity/`; não são aceites árvores de resultados arbitrárias.

A união acrescenta `batch_id` a `runs.csv` e `summary.csv`. **As referências de
cada lote mantêm-se separadas**: não se calculam médias das médias nem se tratam
referências repetidas como novas amostras independentes. Isto preserva também
possíveis diferenças assíncronas entre referências de C. Comparar cada
alternativa com a referência do seu próprio `batch_id`.

O manifesto da consolidação guarda os caminhos e hashes dos manifestos/CSV
de entrada e a localização dos relatórios originais. Não copia nem altera esses
relatórios, nem consolida as tabelas de calibração. É necessário preservar as
pastas originais. O estado `complete` indica que a união terminou; só
`selection_complete=true` indica cobertura das 75 combinações válidas de
cenário e alternativa previstas. `missing_groups` enumera o que falta; uma
união de dois lotes não equivale à recolha completa do Bloco G.

Esta solução repete o gate inicial e a referência em cada lote, aumentando o
número total de simulações face à invocação única. Em contrapartida, reduz o
trabalho a repetir após uma falha e mantém cada trajetória intacta. Não admite
juntar lotes de código/ambiente diferentes ou repetir uma alternativa para
aumentar artificialmente `n`. Se essas condições forem necessárias no futuro,
exigem um protocolo experimental próprio.

## Reproduzir a análise e consultar a proveniência

Os dados finais já estão recolhidos. Para repetir apenas a análise, depois de
ativar um ambiente com as dependências de `requirements.txt`:

```bash
PYTHONPATH=src python scripts/analyze_sensitivity.py results/sensitivity/g-final-consolidated-20261117 --reference-reports results/sensitivity/20261117T205436Z-475d73da/self-check/runs --bootstrap-samples 2000 --bootstrap-seed 917
```

Sem `--run-id`, é criada outra pasta exclusiva. Este comando não executa agentes
nem simulações. Os argumentos e hashes da análise efetivamente realizada estão
no seu manifesto. Os manifestos dos lotes preservam as configurações e a ordem
de execução; os logs dos controladores permitem conferir cada comando real.
Não é necessário voltar a executar os lotes válidos para consultar os resultados.

## Limitações e interpretação científica

O mundo tem uma janela, um iniciador, um par fixo e eventos parados. As sementes
são comuns, mas a reputação dentro de cada combinação cria dependência entre
observações. Mesmo 20 repetições não justificam interpretar diferenças de um ou
dois casos como um efeito robusto sem estudar incerteza e mecanismo.

Os negativos de A/C são episódios sem eventos; a taxa FP das fontes só gera
sinais quando existe um evento benigno. Por isso FPR=0 nesses cenários é
imposto pelo desenho dos negativos, não prova resistência geral a ruído.
C combina perdas, atraso e escassez; o sorteio de perdas depende da ordem de
envios, que pode mudar quando a política muda. Sementes comuns não garantem
uma máscara idêntica de mensagens perdidas em braços diferentes.

A energia é uma soma de pontos percentuais de autonomia, não joules nem uma
medida de baterias fisicamente equivalentes. A carga tem peso no custo, mas
não uma penalização física na execução. A patrulha pode inspecionar a célula
errada em B; a intervenção do guarda é idealizada. Menos consumo pode refletir
menos ameaças mobilizadas, e os tempos médios podem refletir seleção de
resultados recebidos. Estes mecanismos acompanham cada interpretação.

Intervalos descritivos iguais a [0; 0] quando nenhum caso observado muda não
provam que o efeito populacional seja zero. A mesma ressalva aplica-se a zero
falsos positivos numa amostra finita. O bootstrap não observa os casos que
faltam nem resolve a dependência da reputação entre sementes.

Um efeito nulo pode resultar de um fator não ser exercitado: as observações em
`t=0` limitam a análise temporal; só dois sensores limitam a diversidade; missões
confirmadas dominam a via de chamada ao guarda; a carga não acrescenta custo
físico. Não se alteram os cenários oficiais para obter uma diferença. Cenários
adicionais, se necessários, devem ser identificados como experiências distintas.

## Conclusões e trabalho que permanece condicionado

O âmbito executável do Bloco G está concluído: infraestrutura testada, 25
alternativas/75 combinações medidas, consolidação completa, calibração
descritiva e análise dos 13 fatores com apresentação atualizada. O critério
literal original de medir as 26 alternativas permanece parcialmente pendente:
`source_diversity=1/1` exige uma decisão explícita sobre uma política experimental
separada. O bloqueio está registado e não foi contornado.

Os resultados sustentam compromissos dentro destes três cenários e desta
trajetória de aprendizagem. Não justificam calibrar probabilidades, alterar
silenciosamente a produção ou afirmar significância estatística. As aprovações
da equipa continuam pendentes. Mais trajetórias completas independentes,
cenários com observações temporalmente separadas e validação de sensores e
energia em campo seriam necessários para conclusões mais gerais.
