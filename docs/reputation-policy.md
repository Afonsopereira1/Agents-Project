# Reputação e política — Etapa 7

`reputation.py` mantém a fiabilidade dos alertas de ameaça; `corroboration.py`
pondera evidência; `policy.py` escolhe a resposta. `IncidentSensorAgent` e
`MissionExecution`, da Etapa 6, continuam a executar o ciclo de missões.

## Reputação

`ReputationBook` calcula `(acertos + alpha) / (acertos + erros + alpha + beta)`.
Com `alpha=beta=2`, uma fonte nova vale `0.5`; um acerto dá `0.6`, um erro `0.4`.
Mede utilidade como alerta de ameaça: detetar corretamente um trovão pode gerar
um alerta incorreto.

Só aprende com `EvaluationResult` final, confirmado ou refutado, associado à
observação e incidente, posterior à observação, com referências independentes e
cobertura suficiente. Cada observação e par fonte/incidente contam uma vez.
Concordância, timeout, falha e falta de deteção não são referência suficiente.
O avaliador verifica a proveniência; os campos do resultado apenas a registam.

`result_from_ground_truth()` serve apenas o avaliador: exige ligação explícita a
um evento terminado. O sensor recebe pesos históricos através de
`book.snapshot(source_ids)`, nunca `ground_truth`. Contagens e `book.history`
vivem no processo; IDs devem ser únicos nesse âmbito.

## Score e decisão

O score é heurístico, **não uma probabilidade calibrada**:

```text
peso = reputação × confiança declarada / (1 + Δtempo/janela) / (1 + distância/limite)
diversidade = 0.5 + 0.25 × min(2, modalidades dos grupos com apoio líquido positivo)
score = clamp((apoio - oposição) / 2, 0, 1) × diversidade
```

Fora da janela ou distância, a observação não contribui; limite zero exige
coincidência exata. A âncora inicial tem fatores espacial/temporal iguais a 1.
Cada grupo de correlação contribui com o maior peso positivo e negativo.
Contradição e ausência informativa válida reduzem apoio; `no_data` não reduz.
Metadados desconhecidos partilham o grupo `unknown`, sem modalidade conhecida.
Os grupos são configurados localmente e não provam independência estatística.

[config/agents.json](../config/agents.json) define os valores experimentais:
`patrol_threshold=0.25`, `ranger_threshold=0.65`, diversidade mínima de dois grupos
e duas modalidades, `severe_threshold=0.8` e `severe_patrol_threshold=0.08`.
A gravidade padrão é `0.5`, distinta da intensidade do sinal. Estes parâmetros
estão testados, mas **não aprovados formalmente nem calibrados cientificamente**.

A política pede rangers com apoio suficiente, diversidade e ausência de conflito;
pede patrulha ao atingir o limiar adequado à gravidade; caso contrário, observa.
Missão independente fundamentada: `confirmed` pede rangers; `refuted` encerra.
Score baixo ou falta de confirmação nunca encerram. A política rejeita verdade
de referência como entrada operacional.

`SensorAgent.set_response_policy()` ativa esta regra; sem ela mantém-se a decisão
preliminar da Etapa 4. `MINIMUM_COMPATIBLE_SOURCES` só afeta a regra preliminar.
O histórico regista fatores, limiares, razões e atualizações aceites/recusadas.
Os testes verificam extremos, correlação e sensibilidade: score `0.5` pede patrulha
com limiar `0.5`, mas observa com `0.51`. Isso não valida os valores para dados reais.

## Executar sobre o MVP

```bash
PYTHONPATH=src python -m isia.simulation.runner --policy config/agents.json > /tmp/isia-policy.json
PYTHONPATH=src python -m unittest discover -s tests/scenarios -p test_mvp_policy.py -v
```

Sem `--policy`, o runner mantém a decisão preliminar da Etapa 6. Com a configuração
fornecida, os dois sensores acústicos pertencem ao mesmo grupo: a decisão é
`observe`, sem missões, e a janela única termina como `expired`. Alterar `severity`
para `0.8` pede verificação móvel e usa o ciclo existente até à resposta do guarda.
O JSON regista configuração, pesos, decisão, evidências e linha temporal.

`run_mvp(response_settings=settings, reputation=book)` aceita histórico já
avaliado. Sem `book`, começa com o prior da configuração. Não persiste nem treina
reputações automaticamente entre execuções. As fontes da configuração usam os
IDs `sensor-1` e `sensor-2` deste MVP; a demonstração isolada da Etapa 4 mantém-se.

`request_rangers` cria `respond_incident` com a capacidade existente
`incident_response`. A negociação, movimento, consumo, tentativas e regresso
usam a implementação da Etapa 6 e o seu contrato `MISSION_RESULT`.

**Limite da aprendizagem:** o resultado atual da missão contém `outcome`, motivo
e instante, mas não comprova cobertura temporal/espacial nem referências
independentes. Por isso não é convertido automaticamente em `EvaluationResult`.
`not_confirmed` encerra operacionalmente o incidente, como na Etapa 6, sem
significar `refuted` nem penalizar fontes. O avaliador pode atualizar `book` com
verdade de referência de eventos terminados ou uma adjudicação independente
fundamentada. Automatizar esta adjudicação continua pendente.
