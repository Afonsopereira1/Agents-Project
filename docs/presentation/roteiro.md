# Roteiro da apresentação

> Ordem fixa e conteúdo de cada diapositivo. Os números vêm de `results/` (Etapa 9: 560 execuções; P3: `results/scalability/`). Nada aqui é novo: cada diapositivo aponta para a fonte.

**Duração alvo:** cerca de 12 minutos, 12 diapositivos, cerca de 1 minuto cada. A demonstração gravada ocupa o diapositivo 10.

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
| 11 | Limites | Uma ocorrência por janela; 20 repetições sem intervalos de confiança; parâmetros não calibrados; a reputação mudou 1 decisão em 560; falhas só no transporte local | [experiments.md](../experiments.md#limitações-e-incerteza), [scalability.md](../scalability.md) |
| 12 | Conclusão e trabalho futuro | O que funciona (ciclo completo, recusa autónoma, corroboração corta FP); próximos passos: C4 + C1, várias ocorrências em paralelo, retransmissões | [delivery-todo.md](../delivery-todo.md#bloco-f--testes-de-stress-opcional) |

## Notas para os diapositivos 7, 8 e 11

- **7:** em A, os 3 FN vêm de 1 ameaça sem alerta e 2 `expired` por falta de corroboração. Em C, o drone recusa sempre (`autonomy_insufficient`) e o veículo fica sozinho.
- **8:** é a diferença conjunta de corroboração e limiar; não isola a causa. Dizer isto em voz alta.
- **11:** reportar o fator de lentidão como dois tempos (1,5 s e 5,5 s), não como um múltiplo fixo.

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
