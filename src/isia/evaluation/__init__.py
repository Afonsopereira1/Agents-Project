"""Avaliação das experiências: lança as execuções e, depois de cada uma terminar, é a única camada que lê ``ground_truth``.

- `isia.evaluation.collector`: corre cenários × variantes × sementes e grava relatórios e CSV.
- `isia.evaluation.metrics`: matriz de confusão, taxas, tempos, mensagens e energia por execução.
- `isia.evaluation.calibration`: frequência de ameaças por intervalo de score (não é calibração probabilística).
"""
