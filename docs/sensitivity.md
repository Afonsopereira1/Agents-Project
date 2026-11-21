# Sensibilidade dos parâmetros — Bloco G

[Experiências da Etapa 9](experiments.md)

## Em resumo

- Variámos **13 parâmetros, um de cada vez**, com duas alternativas cada: 25 alternativas × 3 cenários = **75 combinações, 3500 execuções**. A 26.ª alternativa (diversidade 1/1) não correu, porque a política exige pelo menos 2 grupos e 2 modalidades.
- **O limiar de patrulha é o parâmetro que mais pesa.** Em B, subir de 0,25 para 0,35 baixa o recall de 0,65 para 0,10 (FPR de 0,25 para 0,025). Descer para 0,15 dá recall 0,75 e FPR 0,575.
- **Gravidade 0,9** ativa o limiar grave (0,08): em B o FPR sobe de 0,25 para 0,75 (falsos alarmes de 10 para 30) e o recall de 0,65 para 0,80.
- **Distância de corroboração 3 → 1** em B: recall de 0,65 para 0,35 e FPR de 0,25 para 0,125.
- **Pesos «só energia»** trocam o veículo pelo drone sem mudar a classificação: em A, verificação aos 4 s em vez de 6 s e 6,8 p.p. de energia em vez de 8,5.
- **46 das 75 combinações são iguais à referência** em todas as métricas, e em 55 a classificação não muda. Em vários casos o cenário não exercita o parâmetro; isso não prova que ele seja irrelevante.

Os resultados são descritivos. Não há significância estatística e nenhum valor passa a produção por ter corrido melhor aqui.

## O que foi medido

- **Referência:** os cenários A, B e C da [Etapa 9](experiments.md), variante `full`, sementes 1000 a 1019. São 40 execuções em A e C e 60 em B, com 20 ameaças por cenário.
- **Um fator de cada vez.** Cada alternativa parte de uma cópia do cenário oficial e muda só o fator declarado ([`apply_experiment`](../scripts/sensitivity.py)).
- **Reputação.** Cada combinação começa com um `ReputationBook` novo, que aprende ao longo das 20 repetições, pela ordem original.
- **Comparação.** Os dados foram recolhidos em 41 lotes. Cada lote repete a referência e a alternativa compara-se com a referência do seu lote. As 41 referências repetidas são iguais entre si em todas as métricas; só o tempo real varia.
- **Extensões desligadas.** Sem fila e sem prazo dinâmico (`PUBLISHED_CONDITIONS`) e sem reenvio: as condições da Etapa 9.

| Fator (nome em `PARAMETERS`) | Referência | Alternativas | O que controla |
|---|---|---|---|
| Distância de corroboração (`corroboration_distance`) | 3,0 células | 1,0; 5,0 | Corte de compatibilidade entre observações e atenuação espacial do score |
| Janela temporal (`corroboration_window`) | 2,0 s simulados | 0,5; 5,0 | Corte e atenuação temporal do score |
| Qualidade das fontes (`sensor_quality`) | FP e FN de cada cenário | `ideal` (FP=FN=0); `noisy` (FP=FN=0,3) | Taxas de erro das duas fontes |
| Prazo-base (`receive_timeout`) | 0,5 s reais | 0,1; 2,0 | Espera por respostas na negociação |
| Pesos ETA/energia/carga (`cost_weights`) | 1/1/1 | 0/1/0; 1/1/5 | Escolha da patrulha |
| Autonomia mínima (`minimum_autonomy`) | 10 % | 5 %; 30 % | Reserva abaixo da qual um recurso recusa |
| Prior α=β (`reputation_prior`) | 2,0 | 0,5; 10,0 | Velocidade de aprendizagem da reputação; o valor inicial é sempre 0,5 |
| Limiar de patrulha (`patrol_threshold`) | 0,25 | 0,15; 0,35 | Score mínimo para mobilizar uma patrulha |
| Limiar do guarda (`ranger_threshold`) | 0,65 | 0,50; 0,80 | Score mínimo para chamar o guarda diretamente |
| Diversidade (`source_diversity`) | 2 grupos / 2 modalidades | 3/3; 1/1 (bloqueada) | Evidência diversa exigida para chamar o guarda diretamente |
| Gravidade (`severity`) | 0,5 | 0,2; 0,9 | A partir de 0,8, a patrulha usa o limiar grave 0,08 |
| Distância de adjudicação (`adjudication_distance`) | 1 célula | 0; 2 | Distância aceite entre a célula inspecionada e a observação para a reputação aprender |
| Prazo de adjudicação (`adjudication_delay`) | 30 s simulados | 5; 120 | Atraso máximo da inspeção para a reputação aprender |

Notas sobre os fatores:

- Quatro fatores são conjuntos: os três pesos do custo, α e β iguais, grupos e modalidades, FP e FN das duas fontes. Não medem o efeito de cada componente.
- `ideal` e `noisy` só mudam FP e FN. A `sensitivity`, a confiança, o alcance e o erro de posição ficam como no cenário. Por isso `ideal` não garante deteção perfeita.
- `noisy` não é «pior do que a referência» em todos os cenários. Em B baixa o FP de 0,6 e 0,5 para 0,3 e sobe o FN de 0,2 e 0,25 para 0,3.
- **Diversidade 1/1 está bloqueada.** `ResponsePolicy.__post_init__` exige pelo menos 2 grupos e 2 modalidades. O script regista a alternativa como `blocked` e não a executa. Medi-la exige uma política experimental separada, aprovada pela equipa.

## Como ler as tabelas

| Coluna | Significado |
|---|---|
| TP/FP/TN/FN | Classificação por mobilização, como na [Etapa 9](experiments.md#unidade-de-avaliação-e-métricas) |
| tv [n], tg [n] | Tempo médio até ao resultado da verificação e até ao resultado do guarda, em segundos simulados; `n` é o número de execuções com esse resultado. `N/A [0]` não é tempo zero. |
| Energia, Msg. | Médias por execução: pontos percentuais de autonomia e tentativas de envio |
| Conf. | Execuções com verificação móvel confirmada e resultado recebido |
| NR | Execuções que terminam `unresolved` |
| Atualiz. | Atualizações de reputação aceites |
| Rep. final | Reputação do `sensor-1` depois da última execução |

`Conf.` conta verificações móveis, não intervenções do guarda. Uma alternativa que chame o guarda diretamente tem menos `Conf.` sem ter menos ameaças atendidas.

## Resultados por parâmetro

Fonte: [`summary.csv`](../results/sensitivity/summary.csv), uma linha por combinação e por referência de lote. As tabelas de cada parâmetro mostram só as combinações que diferem da referência; as restantes são iguais em todas as colunas do resumo.

**Referência (igual nos 41 lotes):**

| Cen. | Valor | TP/FP/TN/FN | Precision | Recall | FPR | tv [n] | tg [n] | Energia | Msg. | Conf. | NR | Atualiz. | Rep. final |
|---|---|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| A | referência | 17/0/20/3 | 1,00 | 0,85 | 0 | 6 [17] | 12 [17] | 8,5 | 6,475 | 17 | 0 | 17 | 0,905 |
| B | referência | 13/10/30/7 | 0,57 | 0,65 | 0,25 | 6 [23] | 12 [2] | 4,167 | 4,767 | 2 | 0 | 2 | 0,667 |
| C | referência | 16/0/20/4 | 1,00 | 0,80 | 0 | 6 [10] | 17 [6] | 4,5 | 4,225 | 10 | 10 | 10 | 0,857 |

**Visão geral:**

| # | Fator | Maior efeito observado | Combinações iguais à referência |
|---:|---|---|---:|
| 1 | Distância de corroboração | B com 1 célula: recall 0,65 → 0,35; FPR 0,25 → 0,125 | 5 de 6 |
| 2 | Janela temporal | Nenhum | 6 de 6 |
| 3 | Qualidade das fontes | B `ideal`: FP 10 → 0, recall 0,85. C `noisy`: recall 0,80 → 0,35 | 0 de 6 |
| 4 | Prazo-base | Nenhum nas métricas; só o tempo real de C | 6 de 6 |
| 5 | Pesos do custo | A com 0/1/0: tv 6 → 4 s, energia 8,5 → 6,8 p.p., mesma classificação | 4 de 6 |
| 6 | Autonomia mínima | C com 5 %: verificações confirmadas 10 → 14, não resolvidas 10 → 8 | 5 de 6 |
| 7 | Prior da reputação | C: TP 16 → 18 (prior 0,5) e 16 → 15 (prior 10) | 0 de 6 |
| 8 | Limiar de patrulha | B com 0,35: recall 0,65 → 0,10; com 0,15: FPR 0,25 → 0,575 | 1 de 6 |
| 9 | Limiar do guarda | A com 0,5: tg 12 → 7,4 s, verificações confirmadas 17 → 4 | 4 de 6 |
| 10 | Diversidade | Nenhum (3/3); 1/1 bloqueada | 3 de 3 |
| 11 | Gravidade | B com 0,9: FPR 0,25 → 0,75, recall 0,65 → 0,80 | 3 de 6 |
| 12 | Distância de adjudicação | Nenhum | 6 de 6 |
| 13 | Prazo de adjudicação | Com 5 s a reputação deixa de aprender; C: TP 16 → 15 | 3 de 6 |

### 1. Distância de corroboração

| Cen. | Valor | TP/FP/TN/FN | Precision | Recall | FPR | tv [n] | tg [n] | Energia | Msg. | Conf. | NR | Atualiz. | Rep. final |
|---|---|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| B | 1 | 7/5/35/13 | 0,58 | 0,35 | 0,125 | 6 [12] | 12 [1] | 2,167 | 3,217 | 1 | 0 | 1 | 0,6 |

- Iguais à referência: A e C com 1 e com 5; B com 5.
- Em B, com 1 célula, perdem-se 6 ameaças (TP 13 → 7) e 5 falsos alarmes (FP 10 → 5). A energia desce porque se mobiliza menos, não por eficiência.
- Com 5 células, em B o score muda em 20 das 46 execuções com score, mas nenhuma decisão atravessa um limiar.
- A e C não têm erro de posição: os dois sensores percebem a mesma célula e a distância não entra.
- Δ recall em B (1 célula) = −0,30; intervalo descritivo [−0,50; −0,10].

### 2. Janela temporal

- As 6 combinações são iguais à referência.
- Nesta janela única, todas as observações têm `observed_at = 0`. A diferença de tempo é zero e o fator temporal vale 1.
- O desenho não exercita este parâmetro. O resultado não diz nada sobre observações desencontradas no tempo.

### 3. Qualidade das fontes

| Cen. | Valor | TP/FP/TN/FN | Precision | Recall | FPR | tv [n] | tg [n] | Energia | Msg. | Conf. | NR | Atualiz. | Rep. final |
|---|---|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| A | ideal | 20/0/20/0 | 1,00 | 1,00 | 0 | 6 [20] | 12 [20] | 10 | 7,5 | 20 | 0 | 20 | 0,917 |
| A | noisy | 12/0/20/8 | 1,00 | 0,60 | 0 | 6 [12] | 12 [12] | 6 | 4,65 | 12 | 0 | 12 | 0,875 |
| B | ideal | 17/0/40/3 | 1,00 | 0,85 | 0 | 5,824 [17] | 12 [2] | 3,067 | 3,067 | 2 | 0 | 2 | 0,667 |
| B | noisy | 12/0/40/8 | 1,00 | 0,60 | 0 | 6,083 [12] | 12 [2] | 2,367 | 2,467 | 2 | 0 | 2 | 0,667 |
| C | ideal | 18/0/20/2 | 1,00 | 0,90 | 0 | 6 [11] | 17 [7] | 5,25 | 4,75 | 11 | 11 | 11 | 0,867 |
| C | noisy | 7/0/20/13 | 1,00 | 0,35 | 0 | 6 [4] | 17 [2] | 1,75 | 2,075 | 4 | 5 | 4 | 0,75 |

- `ideal` sobe o recall: 0,85 → 1,00 em A, 0,65 → 0,85 em B, 0,80 → 0,90 em C. Em B elimina os 10 falsos alarmes.
- `noisy` baixa o recall para 0,60 em A e 0,35 em C. Em B também elimina os falsos alarmes (FP 10 → 0), porque aí o FP desce para 0,3, e o recall fica em 0,60.
- O custo menor de `noisy` em A e C vem de ameaças não atendidas. Não é uma melhoria.
- Em B, mesmo com `ideal`, só 2 verificações confirmam: o erro de posição mantém-se.
- Precision 1,00 com poucos casos é um resultado desta amostra, não uma garantia.
- Δ recall em C (`noisy`) = −0,45; intervalo descritivo [−0,65; −0,25].

### 4. Prazo-base de espera

- As 6 combinações são iguais à referência nas métricas.
- Os atrasos injetados em C são de 0,05 s, abaixo dos três prazos. Esperar mais não recupera mensagens perdidas, porque não há reenvio.
- O efeito aparece no tempo real da recolha de C (40 execuções): 44,4 s na referência, 35,1 s com 0,1 s (−21 %) e 78,8 s com 2 s (+78 %). São medições de uma máquina, num lote por valor.
- A espera pelo resultado da missão é dez vezes o prazo-base, por isso também muda.

### 5. Pesos de ETA, energia e carga

| Cen. | Valor | TP/FP/TN/FN | Precision | Recall | FPR | tv [n] | tg [n] | Energia | Msg. | Conf. | NR | Atualiz. | Rep. final |
|---|---|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| A | 0/1/0 | 17/0/20/3 | 1,00 | 0,85 | 0 | 4 [17] | 10 [17] | 6,8 | 6,475 | 17 | 0 | 17 | 0,905 |
| B | 0/1/0 | 13/10/30/7 | 0,57 | 0,65 | 0,25 | 4,174 [23] | 10 [2] | 2,767 | 4,767 | 2 | 0 | 2 | 0,667 |

- Iguais à referência: 1/1/5 nos três cenários; 0/1/0 em C.
- Só energia (0/1/0) troca o veículo pelo drone nas 17 verificações de A e nas 23 de B. A classificação não muda.
- Em A, a verificação passa de 6 para 4 s, o guarda de 12 para 10 s e a energia de 8,5 para 6,8 p.p. (−20 %). Em B, a energia desce de 4,167 para 2,767 p.p. (−34 %).
- São os mesmos agregados da variante `nearest` da Etapa 9.
- Carga 5 reforça a escolha do veículo, que já ganhava. Em C o drone não é elegível e os pesos não mudam o único candidato.
- A carga pesa na escolha, mas não tem custo físico na execução. O simulador não mostra o benefício de poupar o drone carregado.
- Δ tv em A (0/1/0) = −2 s nos 17 pares; intervalo descritivo [−2; −2].

### 6. Autonomia mínima

| Cen. | Valor | TP/FP/TN/FN | Precision | Recall | FPR | tv [n] | tg [n] | Energia | Msg. | Conf. | NR | Atualiz. | Rep. final |
|---|---|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| C | 5 % | 16/0/20/4 | 1,00 | 0,80 | 0 | 4,429 [14] | 14 [8] | 5,05 | 5,125 | 14 | 8 | 14 | 0,889 |

- Iguais à referência: A e B com 5 % e com 30 %; C com 30 %.
- Em A e B os recursos começam com 100 % e os percursos nunca chegam às reservas comparadas.
- Em C, com 5 %, o drone passa a ser elegível: 15 % menos 6 p.p. de ida e volta deixam 9 %, que chega para 5 % mas não para 10 %. As recusas por autonomia passam de 12 para 0.
- Com dois candidatos, as negociações sem proposta descem de 6 para 2. As verificações confirmadas sobem de 10 para 14 e as não resolvidas descem de 10 para 8. O recall mantém-se em 0,80.
- A energia sobe de 4,5 para 5,05 p.p. porque se completam mais missões.
- Troca-se margem de segurança por disponibilidade. Isto não valida uma margem para uso real.
- Δ tv em C (5 %) = −1,33 s nos 9 pares com valor nos dois braços; intervalo descritivo [−2; −0,67].

### 7. Prior da reputação

| Cen. | Valor | TP/FP/TN/FN | Precision | Recall | FPR | tv [n] | tg [n] | Energia | Msg. | Conf. | NR | Atualiz. | Rep. final |
|---|---|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| A | 0,5 | 18/0/20/2 | 1,00 | 0,90 | 0 | 6 [18] | 12 [18] | 9 | 6,8 | 18 | 0 | 18 | 0,974 |
| A | 10 | 17/0/20/3 | 1,00 | 0,85 | 0 | 6 [17] | 12 [17] | 8,5 | 6,475 | 17 | 0 | 17 | 0,73 |
| B | 0,5 | 13/10/30/7 | 0,57 | 0,65 | 0,25 | 6 [23] | 12 [2] | 4,167 | 4,767 | 2 | 0 | 2 | 0,833 |
| B | 10 | 13/10/30/7 | 0,57 | 0,65 | 0,25 | 6 [23] | 12 [2] | 4,167 | 4,767 | 2 | 0 | 2 | 0,545 |
| C | 0,5 | 18/0/20/2 | 1,00 | 0,90 | 0 | 6 [12] | 17 [8] | 5,5 | 4,825 | 12 | 10 | 12 | 0,962 |
| C | 10 | 15/0/20/5 | 1,00 | 0,75 | 0 | 6 [9] | 17 [5] | 4 | 3,925 | 9 | 10 | 9 | 0,655 |

- Um prior fraco (0,5) aprende mais depressa: mais uma ameaça mobilizada em A (17 → 18) e duas em C (16 → 18). Um prior forte (10) aprende devagar: C perde uma (16 → 15).
- O mecanismo é o do alerta isolado: o score é 0,3 × reputação e só passa 0,25 com reputação ≥ 5/6.
- Em B a classificação não muda. A reputação final muda (0,833 ou 0,545 em vez de 0,667), sem consequência.
- Só verificações confirmadas atualizam a reputação. Os falsos alarmes de B dão `not_confirmed`, que é inconclusivo e não a baixa.
- São diferenças de uma ou duas ameaças numa única trajetória. Não mostram que um prior seja melhor.
- Δ recall em C (prior 0,5) = +0,10; intervalo descritivo [0; +0,25].

### 8. Limiar de patrulha

| Cen. | Valor | TP/FP/TN/FN | Precision | Recall | FPR | tv [n] | tg [n] | Energia | Msg. | Conf. | NR | Atualiz. | Rep. final |
|---|---|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| A | 0,15 | 19/0/20/1 | 1,00 | 0,95 | 0 | 6 [19] | 12 [19] | 9,5 | 7,125 | 19 | 0 | 19 | 0,913 |
| B | 0,15 | 15/23/17/5 | 0,39 | 0,75 | 0,575 | 5,763 [38] | 12 [2] | 6,367 | 6,767 | 2 | 0 | 2 | 0,667 |
| B | 0,35 | 2/1/39/18 | 0,67 | 0,10 | 0,025 | 6 [3] | N/A [0] | 0,5 | 1,933 | 0 | 0 | 0 | 0,5 |
| C | 0,15 | 19/0/20/1 | 1,00 | 0,95 | 0 | 6 [13] | 17 [8] | 6 | 5,125 | 13 | 11 | 13 | 0,882 |
| C | 0,35 | 15/0/20/5 | 1,00 | 0,75 | 0 | 6 [9] | 17 [5] | 4 | 3,925 | 9 | 10 | 9 | 0,846 |

- Igual à referência: A com 0,35.
- **B com 0,35:** os falsos alarmes quase desaparecem (FP 10 → 1), mas as ameaças também (TP 13 → 2). Recall 0,10, zero verificações confirmadas. A precision 0,67 assenta em 3 mobilizações.
- **B com 0,15:** recall 0,75 (TP 15), com 23 falsos alarmes (FPR 0,575).
- Em A e C, 0,15 deixa passar o alerta isolado (score 0,15 com reputação 0,5) e o recall chega a 0,95. Estes cenários só têm negativos vazios, por isso não mostram o custo em falsos alarmes.
- O limiar controla um compromisso real entre cobertura e alarmes. Não há um valor ótimo demonstrado.
- Δ recall em B (0,35) = −0,55; intervalo descritivo [−0,75; −0,35].

### 9. Limiar do guarda

| Cen. | Valor | TP/FP/TN/FN | Precision | Recall | FPR | tv [n] | tg [n] | Energia | Msg. | Conf. | NR | Atualiz. | Rep. final |
|---|---|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| A | 0,5 | 17/0/20/3 | 1,00 | 0,85 | 0 | 6 [4] | 7,412 [17] | 5,25 | 3,875 | 4 | 0 | 4 | 0,75 |
| C | 0,5 | 15/0/20/5 | 1,00 | 0,75 | 0 | 6 [4] | 10,4 [5] | 2,75 | 2,9 | 4 | 10 | 4 | 0,75 |

- Iguais à referência: 0,8 nos três cenários; 0,5 em B.
- **Na referência, o guarda nunca é chamado diretamente.** Com dois sensores, confiança 0,8 e o par com reputação 0,5, o score máximo é 0,60, abaixo de 0,65. O guarda só vai depois de uma verificação móvel confirmada.
- Com 0,5, o score de duas fontes passa o limiar quando a reputação do `sensor-1` chega a 0,75, ao fim de 4 confirmações. A partir daí o guarda é chamado diretamente e a verificação móvel deixa de acontecer.
- Em A isso dá o mesmo número de intervenções do guarda (17), mais cedo (7,4 s em vez de 12 s) e com menos energia (5,25 em vez de 8,5 p.p.). A reputação pára de aprender: 4 atualizações em vez de 17.
- Em C o recall desce de 0,80 para 0,75: sem aprendizagem, um alerta isolado tardio deixa de mobilizar.
- Em B o score nunca chega a 0,5 (máximo observado: 0,385).
- O guarda devolve sempre `confirmed` quando a ameaça está na célula. Chamar o guarda sem verificar não foi avaliado contra falsos alarmes, porque A e C só têm negativos vazios.
- Δ tg em A (0,5) = −4,59 s nos 17 pares; intervalo descritivo [−5,65; −3,20].

### 10. Diversidade das fontes

- 3/3 é igual à referência nos três cenários. 1/1 não foi executada.
- A regra de evidência diversa só conta para a chamada direta do guarda, que na referência nunca é atingida (ver ponto 9). Exigir 3/3 não muda nada.
- O guarda continua a ser chamado depois de uma verificação confirmada; essa via não depende da diversidade.
- Só existem duas fontes. O resultado não diz se três fontes seriam úteis num sistema que as tivesse.

### 11. Gravidade

| Cen. | Valor | TP/FP/TN/FN | Precision | Recall | FPR | tv [n] | tg [n] | Energia | Msg. | Conf. | NR | Atualiz. | Rep. final |
|---|---|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| A | 0,9 | 19/0/20/1 | 1,00 | 0,95 | 0 | 6 [19] | 12 [19] | 9,5 | 7,125 | 19 | 0 | 19 | 0,913 |
| B | 0,9 | 16/30/10/4 | 0,35 | 0,80 | 0,75 | 5,804 [46] | 12 [2] | 7,7 | 7,833 | 2 | 0 | 2 | 0,667 |
| C | 0,9 | 19/0/20/1 | 1,00 | 0,95 | 0 | 6 [13] | 17 [8] | 6 | 5,125 | 13 | 11 | 13 | 0,882 |

- Igual à referência: 0,2 nos três cenários. Tanto 0,2 como 0,5 ficam abaixo do limiar de gravidade (0,8).
- Com 0,9, a patrulha usa o limiar grave 0,08 e qualquer alerta mobiliza.
- Em B: recall 0,65 → 0,80 (TP 13 → 16) e FPR 0,25 → 0,75 (FP 10 → 30). A energia sobe de 4,167 para 7,7 p.p. (+85 %) e as verificações confirmadas continuam a ser 2.
- São os mesmos agregados da variante `no_corroboration` da Etapa 9: com o limiar grave, a corroboração deixa de filtrar.
- A fila por prioridade está desligada. O efeito medido é o do limiar, não o da prioridade.
- Δ FPR em B (0,9) = +0,50; intervalo descritivo [+0,35; +0,65].

### 12. Distância de adjudicação

- As 6 combinações são iguais à referência, incluindo as atualizações de reputação.
- A distância mede-se entre a célula inspecionada e a posição percebida da observação. A patrulha vai sempre à posição percebida, logo a distância é zero.
- Em B, inspecionar a célula errada dá `not_confirmed` e não há aprendizagem. Alargar esta distância não corrige o erro de posição.

### 13. Prazo de adjudicação

| Cen. | Valor | TP/FP/TN/FN | Precision | Recall | FPR | tv [n] | tg [n] | Energia | Msg. | Conf. | NR | Atualiz. | Rep. final |
|---|---|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| A | 5 | 17/0/20/3 | 1,00 | 0,85 | 0 | 6 [17] | 12 [17] | 8,5 | 6,475 | 17 | 0 | 0 | 0,5 |
| B | 5 | 13/10/30/7 | 0,57 | 0,65 | 0,25 | 6 [23] | 12 [2] | 4,167 | 4,767 | 2 | 0 | 0 | 0,5 |
| C | 5 | 15/0/20/5 | 1,00 | 0,75 | 0 | 6 [9] | 17 [5] | 4 | 3,925 | 9 | 10 | 0 | 0,5 |

- Igual à referência: 120 s nos três cenários.
- Com 5 s a reputação nunca aprende: as verificações confirmadas terminam aos 6 s simulados, fora do prazo. Zero atualizações e reputação final 0,5.
- O efeito só aparece em decisões seguintes. Em C perde-se uma mobilização (TP 16 → 15). Os agregados são os da variante `no_reputation` da Etapa 9, em que a execução perdida é o alerta isolado da repetição 19.
- O código compara `completed_at − observed_at`, em tempo simulado. Os 120 s não medem tolerância a atrasos de rede.

## Síntese

**Os dois maiores efeitos na classificação** (maior |Δ| de precision, recall ou FPR), ambos em B:

| Alteração | Efeito | Diferença | Intervalo descritivo |
|---|---|---:|---|
| Limiar de patrulha 0,25 → 0,35 | Recall 0,65 → 0,10 | −0,55 (−85 %) | [−0,75; −0,35] |
| Gravidade 0,5 → 0,9 | FPR 0,25 → 0,75 | +0,50 (+200 %) | [+0,35; +0,65] |

Em B há 20 ameaças (denominador do recall) e 40 negativos (denominador do FPR).

**O que os resultados dizem, em linguagem simples:**

- A decisão de mobilizar depende sobretudo dos limiares (patrulha, gravidade) e do que conta como corroboração (distância). São estes os parâmetros a discutir primeiro.
- Em B não há ganho sem custo: o que reduz falsos alarmes reduz também o recall, e vice-versa. A exceção é melhorar as fontes (`ideal`).
- Pesos só de energia e autonomia mínima 5 % melhoram custo ou disponibilidade sem mexer na classificação, com menos margem configurada no segundo caso. O limiar do guarda 0,5 também mantém a classificação em A (17 intervenções): reduz o tempo médio de resposta de 12 para 7,412 s e a energia de 8,5 para 5,25 p.p.; as verificações confirmadas e atualizações de reputação descem de 17 para 4. Em C reduz o recall de 0,80 para 0,75 e em B não muda os resultados. O benefício observado em A não valida a chamada direta contra falsos alarmes: os negativos são vazios.
- A reputação pesa pouco: priors e prazo de adjudicação mudam no máximo duas ameaças em 20.
- Não foi procurado nem encontrado um valor ótimo. Os valores oficiais mantêm-se.

**Porque é que 46 combinações não mudam nada:**

| Motivo | Fatores | Combinações |
|---|---|---:|
| O cenário não exercita o parâmetro | Janela temporal (tudo em `t=0`); distância de adjudicação (distância sempre 0); distância de corroboração em A e C (mesma célula percebida); diversidade 3/3 e limiar do guarda 0,8 (chamada direta nunca atingida); limiar do guarda 0,5 em B (score máximo 0,385) | 23 |
| Os valores ficam do mesmo lado do limiar | Pesos 1/1/5 (o veículo já ganhava); limiar de patrulha 0,35 em A (alertas corroborados têm score ≥ 0,40); gravidade 0,2 (abaixo de 0,8); prazo de adjudicação 120 s (verificações aos 6 s) | 10 |
| O recurso afetado não entra | Autonomia mínima em A e B (recursos a 100 %); autonomia 30 % e pesos 0/1/0 em C (drone já inelegível) | 6 |
| Só muda fora das métricas | Prazo-base (tempo real); distância de corroboração 5 em B (scores mudam, decisões não) | 7 |

Um efeito nulo aqui não prova que o parâmetro seja irrelevante noutras condições.

## Calibração descritiva do score

O `suspicion_score` é uma heurística, não uma probabilidade. A tabela conta, por intervalo de score inicial, quantas execuções da referência tinham ameaça real ([`calibration.py`](../src/isia/evaluation/calibration.py)).

| Intervalo | A: n / ameaças | B: n / ameaças | C: n / ameaças |
|---|---:|---:|---:|
| [0; 0,25[ | 2 / 2 | 23 / 3 (13 %) | 3 / 3 |
| [0,25; 0,50[ | 4 / 4 | 23 / 13 (57 %) | 7 / 7 |
| [0,50; 0,75[ | 13 / 13 | 0 / 0 | 9 / 9 |
| [0,75; 1] | 0 / 0 | 0 / 0 | 0 / 0 |

| Cenário | Execuções | Com score | Sem score | Ameaças sem score |
|---|---:|---:|---:|---:|
| A | 40 | 19 | 21 | 1 |
| B | 60 | 46 | 14 | 4 |
| C | 40 | 19 | 21 | 1 |

- Só há score quando há alerta. Em A e C os negativos são vazios e nunca têm score, por isso 100 % de ameaças nos intervalos preenchidos não significa nada sobre calibração.
- Em B o score separa alguma coisa: 13 % de ameaças abaixo de 0,25 contra 57 % acima. São 23 casos por intervalo, dependentes entre si.
- O intervalo [0,75; 1] está vazio. Com duas fontes, o score máximo possível é 0,60 em A e C e 0,525 em B. Os máximos observados são 0,56 em A, 0,53 em C e 0,385 em B.
- Segundo o manifesto, a análise completa cobriu 78 perfis (75 combinações e 3 referências) e 3640 relatórios, 2126 com score. O intervalo superior ficou vazio em todos.
- Transformar o score em probabilidade exigia outro protocolo, com treino e validação separados e dados que incluíssem os casos sem score.

## Limites e incerteza

- **Sem significância estatística.** Os intervalos são percentis 2,5 e 97,5 de um bootstrap emparelhado (2000 reamostragens das 20 sementes, semente 917). A reputação aprende de uma semente para a seguinte, logo as sementes não são independentes. Os intervalos descrevem esta trajetória; não são intervalos de confiança.
- **Amostra pequena.** 20 ameaças por cenário. Diferenças de uma ou duas execuções não são efeitos robustos.
- **Um intervalo [0; 0] não prova efeito nulo**, tal como zero falsos alarmes numa amostra finita não prova FPR 0.
- **FPR 0 em A e C é do desenho.** Os negativos são episódios vazios, que nunca geram sinal. Só B testa falsos alarmes.
- **C mistura perdas, atrasos e escassez.** O sorteio das perdas depende da ordem dos envios, que pode mudar quando a política muda. As mesmas sementes não garantem as mesmas mensagens perdidas nos dois braços.
- **Menos energia pode ser menos serviço.** Ler sempre a energia ao lado do recall e das não resolvidas.
- **Tempos médios dependem de quem respondeu.** A média só inclui execuções com resultado recebido; por isso as diferenças de tempo citadas usam os pares com valor nos dois braços.
- **Mundo simplificado.** Uma janela, um iniciador, dois sensores, eventos parados, guarda idealizado, carga sem custo físico.

## Evidências locais e proposta de entrega complementar — 19-11-2026

Consulta apenas de leitura ao GitHub: na `main` e no commit de origem `c86e9ad4`, `results/sensitivity/` contém apenas `summary.csv` e `completion-manifest.json`. Os CSV detalhados, relatórios e auditorias abaixo existem localmente, mas não nessa árvore publicada. Isto não verifica outras branches, anexos ou entregas externas.

**Proposta, sem criar nem publicar qualquer pacote:**

| Seleção mínima para revisão dos resultados | O que permite conferir |
|---|---|
| `completion-manifest.json`; os quatro ficheiros de `g-final-consolidated-20261117/` (`manifest.json`, `runs.csv`, `summary.csv`, `blocked-configurations.csv`) | 3500 alternativas, 75 combinações válidas, referências separadas por lote, contagens agregadas e diversidade 1/1 bloqueada |
| Os oito ficheiros de `g-final-analysis-20261117/`: `manifest.json`, `comparisons.csv`, `effects.csv`, `findings.json`, `application-audit.csv`, `calibration.csv`, `calibration-coverage.csv`, `calibration-samples.csv` | Comparações emparelhadas, intervalos descritivos, aplicação dos fatores e calibração |
| `manifest.json`, `plan.json`, `self-check/comparison.json` e `self-check/actual.csv` de cada uma das 41 fontes indicadas em `g-final-consolidated-20261117/manifest.json` (quando presentes) | Configurações, sementes, hashes históricos e verificações de referência de cada lote |
| Os quatro ficheiros de `g-final-validation-20261117/` e `g-final-recovery-audit-20261117/recovery.json` | Auditorias e registos históricos de validação; não são uma nova execução dos testes |

Esta seleção tem **182 ficheiros, 5,82 MB sem compressão**; estimativa de compressão de conteúdo de **0,68 MB**, à qual acrescem nomes e metadados do arquivo. Permite rever as tabelas e os cálculos sobre métricas, mas não reconstituir integralmente observações e mensagens. A versão do código deve ser identificada pelos hashes históricos, pois a recolha antecede correções posteriores.

Para auditar também os relatórios de origem, acrescentar os JSON dos 41 lotes canónicos e os 3640 caminhos de `calibration_inputs` do manifesto de análise, incluindo a referência de calibração do lote inicial. A união, sem repetir caminhos, tem **6070 ficheiros, 101,77 MB sem compressão**; estimativa de conteúdo comprimido de **14,24 MB**, acrescida de metadados. Os caminhos referidos existem localmente. Não é necessário incluir todos os ensaios preliminares, de fumo, recuperação intermédia e logs de recolha: a árvore local completa tem 118,09 MB. Existem também os arquivos locais anteriores `auditoria_final_bloco_g.tar.gz` e `bloco_g_revisao.tar.gz`, fora dessa árvore; foram preservados e não são a proposta de pacote desta revisão.

**Duplicações:** os cinco CSV da raiz (`summary`, `runs`, `calibration`, `calibration-coverage`, `blocked-configurations`) são cópias byte a byte dos correspondentes no consolidado/análise; entregar apenas uma cópia de cada. O resumo e o manifesto de conclusão já publicados podem ser incluídos para tornar o complemento autónomo. Os manifestos e planos dos lotes mantêm a ligação à recolha; os agregados não substituem os relatórios para uma auditoria ao detalhe.

**Revisão antes de partilhar:** há caminhos absolutos em cinco ficheiros da seleção: o manifesto de conclusão, os manifestos do consolidado e da análise, `recovery.json` e `unittest-full.json`. Expõem o nome de utilizador, a estrutura de pastas e o caminho do interpretador; há também metadados da máquina nos manifestos. Os caminhos absolutos precisam de um mapeamento para caminhos relativos para uso noutra máquina. Decidir com a equipa o formato e canal de entrega e o eventual tratamento desses dados, preservando os originais e a correspondência dos hashes. Nenhum pacote foi criado e nenhum ficheiro experimental foi movido, copiado, apagado ou adicionado ao índice nesta revisão.

## Como reproduzir

Os scripts escrevem sempre numa pasta nova dentro de `results/sensitivity/` e nunca alteram as anteriores.

```bash
# Catálogo de fatores e plano de uma experiência, sem simular nem gravar:
PYTHONPATH=src python scripts/sensitivity.py --list
PYTHONPATH=src python scripts/sensitivity.py --parameter patrol_threshold --value 0.35 --scenario B --dry-run

# Conferir que o código atual reproduz a referência da Etapa 9 (140 execuções):
PYTHONPATH=src python scripts/sensitivity.py --self-check full --run-id conferir-referencia

# Um lote: referência + alternativas de um fator num cenário (B demora segundos; C, cerca de 45 s por combinação):
PYTHONPATH=src python scripts/sensitivity.py --parameter patrol_threshold --scenario B --run-id lote-patrulha-B

# Juntar lotes e analisar (comparações emparelhadas, bootstrap, calibração), sem simular:
PYTHONPATH=src python scripts/consolidate_sensitivity.py results/sensitivity/lote-1 results/sensitivity/lote-2 --run-id consolidado
PYTHONPATH=src python scripts/analyze_sensitivity.py results/sensitivity/consolidado --run-id analise
```

- Cada lote corre as 20 repetições completas. Não se juntam meias recolhas: partir a trajetória reiniciava a reputação.
- A análise precisa dos relatórios `full` da Etapa 9 em `results/experiments/runs/`, que não são versionados. Geram-se com o coletor ([como reproduzir a Etapa 9](experiments.md#como-reproduzir)).
- [`collect_sensitivity_batches.py`](../scripts/collect_sensitivity_batches.py) recolhe os lotes em falta a partir de lotes existentes.
- A recolha completa soma cerca de 33 minutos de simulação, quase tudo no cenário C.

## Proveniência

- **Versionado:** [`summary.csv`](../results/sensitivity/summary.csv) (116 linhas: 75 combinações e 41 referências) e [`completion-manifest.json`](../results/sensitivity/completion-manifest.json).
- **Não versionado:** as linhas por execução (`runs.csv`, 5420 linhas), os relatórios, as tabelas de calibração e as saídas da análise ficaram na máquina de recolha. O manifesto guarda os SHA-256 dos ficheiros principais.
- **Recolha:** 17-11-2026, commit `be0d3f9`, Python 3.12.3, SPADE 4.1.4, transporte local. 41 lotes, 3500 execuções alternativas e 1920 de referência. A suite de testes passou nessa altura (`tests.returncode = 0` no manifesto).
- **Conferido a 18-11-2026 no código atual:** todas as tabelas desta página batem com `summary.csv`. As referências de A, B e C e 15 das 75 combinações (10 de A e B, 5 de C) foram repetidas e deram os mesmos agregados em todas as colunas. Os oito intervalos citados e a contagem «20 de 46» do ponto 1 foram recalculados a partir dessas repetições e coincidem. A tabela de calibração da referência foi recalculada a partir dos 140 relatórios locais da Etapa 9.
- **Não conferido:** as outras 60 combinações não foram repetidas; os totais da calibração completa (78 perfis, 3640 relatórios) dependem de ficheiros não versionados.
