# P3 — Escalabilidade

<!-- Diapositivo único. Fonte dos números: results/scalability/*.csv (16-11-2026, cenário A, full). -->

**Situacional: o iniciador e as ocorrências limitam mais do que os recursos**

```
   7 . . . . . . . .
   6 . . . . . . P .   P (6,6): fora de alcance → 0/10 alertas
   5 . p . . . R . .
   2 D . S X S . . .   S sensor-1 (único iniciador) · S sensor-2
   0 V . . . . . . Q   Q (7,0): sensor-2 vê, sensor-1 não → 0/10 alertas
     0 1 2 3 4 5 6 7
```

| Caçadores | 1 | 2 | 3 |
|---|---|---|---|
| Atendidos | 8/10 | 8/20 | 8/30 |

Uma ocorrência por janela (C7). Com 10 % de perda: 2 patrulhas atendem 13/20, 1 atende 9/20.

**Computacional: C1–C8**

| Estado | Limites |
|---|---|
| Medido | C2 candidato calado: 1,5 s → 5,5 s reais (esta máquina) · C7 uma ocorrência por janela |
| Proposto | C1 CFP aos K mais próximos (precisa de C4) · C4 recursos no cenário · C5 `bisect` no feed · C6 k vizinhos · C8 reputação em contagens |
| Adiado | C3 prazos no relógio simulado · C8 um processo por agente |

Mensagens por missão: até 3N + 2 · ocorrência completa: 15.

<!-- Notas do orador (30 s):
1. O ponto cego (7,0) mostra que a cobertura é a do iniciador, não a soma dos sensores.
2. 8/10 → 8/20 → 8/30: a métrica por execução daria sempre 8 TP; a métrica por caçador mostra o limite.
3. Redundância: 13/20 contra 9/20 com perdas — 20 repetições, sem intervalo de confiança.
4. Reproduzir: PYTHONPATH=src python scripts/dist.py e scripts/scale.py. -->
