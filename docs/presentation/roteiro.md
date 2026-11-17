# Roteiro da apresentação

> Ordem fixa e conteúdo de cada diapositivo. Os números vêm de `results/`: Etapa 9 (560 execuções), P3 (`results/scalability/`) e Bloco G (3500 execuções alternativas válidas). Cada diapositivo aponta para a fonte; as recolhas têm âmbitos distintos.

**Duração alvo:** cerca de 12 minutos, 13 diapositivos, cerca de 55 segundos cada. A demonstração gravada ocupa o diapositivo 10.

| # | Diapositivo | Conteúdo | Fonte |
|---|---|---|---|
| 1 | Título | Tema C — monitorização descentralizada e patrulhas anti-caça furtiva; SPADE; nomes do grupo | — |
| 2 | Problema e abordagem | Sensores com ruído, recursos limitados, sem despachante. Abordagem B1: quem deteta coordena a sua ocorrência. Ciclo: observação → corroboração → Contract Net → missão → resultado | [README](../../README.md#o-projeto) |
| 3 | Mapa e agentes | Grelha 8×8: `sensor-1` (2,2), `sensor-2` (4,2), drone (0,2), veículo (0,0), guarda (5,5). O ambiente guarda a verdade só para o avaliador | [runner.py](../../src/isia/simulation/runner.py) |
| 4 | **P1** — construção dos agentes | Três camadas e as três ligações de autonomia | [p1-agentes.md](p1-agentes.md) |
| 5 | **P2** — protocolos e arquitetura | FIPA Request + Contract Net; dois contras medidos | [p2-protocolos.md](p2-protocolos.md) |
| 6 | Cenários e variantes | A normal, B ruído, C falhas/escassez; variantes `full`, `no_reputation`, `no_corroboration`, `nearest`; 20 repetições por episódio | [experiments.md](../experiments.md#cenários-configscenariosjson) |
| 7 | Resultados A e C | A/full: precision 1,00, recall 0,85. C/full: recall 0,80, mas 10/20 ameaças `unresolved` (uma mensagem perdida no único recurso elegível) | [experiments.md](../experiments.md#resultados) |
| 8 | Resultado B — o compromisso da corroboração | FPR 0,75 → 0,25 e precision 0,35 → 0,57, ao custo de recall 0,80 → 0,65. Os 10 FP restantes vêm de `thunder+tourist` | [experiments.md](../experiments.md#discussão) |
| 9 | **P3** — escalabilidade | Ponto cego (7,0), série 8/10 → 8/20 → 8/30, tabela C1–C8 | [p3-escalabilidade.md](p3-escalabilidade.md) |
| 10 | Demonstração | Repetição gravada de uma execução do MVP (ver abaixo) | [results/demo/](../../results/demo/) |
| 11 | **Bloco G — sensibilidade** | Em B, patrulha 0,35 reduz recall 0,65→0,10 e FPR 0,25→0,025; gravidade 0,9 eleva recall a 0,80 e FPR a 0,75. São os dois maiores efeitos absolutos observados nas taxas de classificação | [sensitivity.md](../sensitivity.md#síntese-dos-efeitos-e-ausência-de-diferenças), tabela abaixo |
| 12 | Limites | Uma ocorrência por janela; 20 sementes com aprendizagem dependente; intervalos G descritivos; scores não calibrados; 1/1 bloqueado; falhas só no transporte local. A reputação mudou 1 decisão em 560 na Etapa 9 | [experiments.md](../experiments.md#limitações-e-incerteza), [sensitivity.md](../sensitivity.md#limitações-e-interpretação-científica), [scalability.md](../scalability.md) |
| 13 | Conclusão e trabalho futuro | Ciclo completo, recusa autónoma e compromissos medidos entre deteção, alarmes e custo. Próximos passos: trajetórias independentes, observações temporalmente separadas, agrupamento de ocorrências, retransmissões e decisão sobre 1/1 | [sensitivity.md](../sensitivity.md#conclusões-e-trabalho-que-permanece-condicionado), [delivery-todo.md](../delivery-todo.md#bloco-g--sensibilidade-dos-parâmetros-no-final) |

## Notas para os diapositivos 7, 8, 11 e 12

- **7:** em A, os 3 FN vêm de 1 ameaça sem alerta e 2 `expired` por falta de corroboração. Em C, o drone recusa sempre (`autonomy_insufficient`) e o veículo fica sozinho.
- **8:** é a diferença conjunta de corroboração e limiar; não isola a causa. Dizer isto em voz alta.
- **11:** cada comparação G altera um fator e conserva a referência do mesmo lote. O critério de seleção dos dois exemplos é o maior valor absoluto de Δprecision, Δrecall ou ΔFPR por parâmetro; não é um ranking universal de qualidade.
- **12:** os intervalos G são percentis de reamostragem descritiva; a reputação partilhada torna as sementes dependentes. Não afirmar significância estatística. Ao falar do stress, reportar a lentidão como dois tempos (1,5 s e 5,5 s), não como um múltiplo fixo.

## Sensibilidade — Bloco G (diapositivo 11)

**Pergunta a mostrar:** quanto custa reduzir alarmes ou mobilizar mais ameaças?

| Comparação em B | TP | FP | Recall | FPR | Energia média (p.p./execução) |
|---|---:|---:|---:|---:|---:|
| Referência | 13 | 10 | 0,65 | 0,25 | 4,167 |
| Patrulha 0,25→0,35 | 2 | 1 | 0,10 | 0,025 | 0,5 |
| Gravidade 0,5→0,9 | 16 | 30 | 0,80 | 0,75 | 7,7 |

São 20 sementes e 60 execuções por valor: 20 ameaças e 40 negativos. O efeito
máximo do limiar de patrulha foi Δrecall=−0,55 (−55 pontos percentuais;
−84,62% relativamente à referência). O da gravidade foi ΔFPR=+0,50
(+50 pontos percentuais; +200%). Os intervalos centrais descritivos das
diferenças foram, respetivamente, [−0,75; −0,35] e [+0,35; +0,65], com
2000 reamostragens emparelhadas por semente, semente do bootstrap 917.
Não são intervalos inferenciais validados nem testes de significância.

**Frase de apresentação:** «O limiar mais exigente evita nove falsos alarmes,
mas deixa onze ameaças adicionais por mobilizar. A gravidade alta mobiliza
mais três ameaças, mas gera mais vinte falsos alarmes. Menos energia pode
significar menos resposta; não há um valor melhor em todos os objetivos.»

Fonte: [comparisons.csv](../../results/sensitivity/g-final-analysis-20261117/comparisons.csv),
[effects.csv](../../results/sensitivity/g-final-analysis-20261117/effects.csv) e
[manifesto completo](../../results/sensitivity/g-final-consolidated-20261117/manifest.json).
O Bloco G mediu 25 alternativas em 75 combinações; diversidade 1/1 continua
bloqueada, sem alterar a política de produção.

## Demonstração (diapositivo 10)

Gravação versionada em `results/demo/`: `mvp.json` (relatório do `run_mvp`, semente 6), `replay.log` e `replay.tim`. Reproduzir sem Python nem SPADE:

```bash
scriptreplay --log-timing results/demo/replay.tim --log-out results/demo/replay.log
```

Para gravar vídeo, correr o comando acima com um gravador de ecrã aberto. O que mostrar, por ordem:

1. **t = 0 s:** `ALERT`, corroboração por `sensor-2`, `CFP` ao drone e ao veículo, `ACCEPT` ao drone e `REJECT` ao veículo.
2. **t = 1–3 s:** o drone desloca-se para (3,2) e a energia desce 1 p.p. por célula.
3. **t = 4 s:** `MISSION_RESULT confirmed`; segunda ronda de Contract Net só para o guarda.
4. **t = 10 s:** o guarda confirma e o sensor fecha a ocorrência (`closed`).
5. **Métricas:** energia gasta (drone 6, guarda 10, veículo 0) e 15 mensagens no transcrito.

O visualizador só lê o relatório: não corre agentes nem decide nada.
