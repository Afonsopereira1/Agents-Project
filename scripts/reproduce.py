"""Listar os resultados publicados e o comando que reproduz cada um.

Uso, a partir da raiz:  python scripts/reproduce.py

Os comandos correm da raiz, com o ambiente ativo e ``PYTHONPATH=src``. Os tempos
dependem da máquina. A maioria reescreve ficheiros versionados em ``results/``;
para o coletor, ``--output "$(mktemp -d)"`` evita tocar-lhes.
"""

RESULTS = [
    ("Ocorrência de exemplo com a política de reputação", "python -m isia.simulation.runner --policy config/agents.json", "1 s", "stdout"),
    ("Ocorrência de exemplo com falhas injetadas", "python -m isia.simulation.runner --faults config/faults.json", "2 s", "stdout"),
    ("Cenários A, B e C (560 execuções)", "python -m isia.evaluation.collector config/scenarios/*.json --output results/experiments", "3,5 min", "results/experiments/"),
    ("Gráficos dos cenários A, B e C", "python scripts/charts.py", "< 1 s", "results/experiments/charts/"),
    ("P3: custo e espera", "python scripts/scale.py", "18 s", "results/scalability/scale.csv"),
    ("P3: cobertura e distribuição", "python scripts/dist.py", "47 s", "results/scalability/dist.csv"),
    ("Stress F1 (perda, latência, cascata, autonomia…)", "python scripts/stress_f1.py [grupo]", "9 min", "results/stress/<grupo>.csv"),
    ("Stress F2 (paralelo, fila, prioridade, guardas…)", "python scripts/stress_f2.py [grupo]", "> 15 min", "results/stress/<grupo>.csv"),
    ("Stress: 1000 execuções com a mesma reputação", "python scripts/stress_long.py", "3 min", "results/stress/longa.csv"),
    ("Ponto ótimo de guardas, reenvios e distância", "python scripts/sugestoes.py", "10 min", "results/stress/sugestoes.csv"),
    ("Cenário D, «dia movimentado»", "python -m isia.evaluation.collector config/scenarios/demo/D.json --variants full --output results/scenario-d", "5 s", "results/scenario-d/"),
    ("Cenário E, «reserva alargada»", "python -m isia.evaluation.collector config/scenarios/demo/E.json --variants full --output results/scenario-e", "16 s", "results/scenario-e/"),
    ("Cenário E: câmaras contra informadores (depois do anterior)", "python scripts/scenario_e.py", "< 1 s", "results/scenario-e/informants.csv"),
    ("Sensibilidade dos parâmetros (ver docs/sensitivity.md)", "python scripts/sensitivity.py --list", "—", "results/sensitivity/"),
    # isia.agents e isia.reasoning definem __all__, por isso os seus submódulos têm de ser passados à mão.
    ("Documentação do código (requer pip install pdoc==16.0.0)", "rm -rf deliverables/documentacao-api && pdoc -t docs/pdoc --no-show-source -o deliverables/documentacao-api src/isia src/isia/agents/[!_]*.py src/isia/reasoning/[!_]*.py scripts/*.py", "3 s", "deliverables/documentacao-api/"),
]


def main():
    """Imprimir cada resultado numerado, com o comando, o tempo e onde grava."""
    for number, (what, command, duration, output) in enumerate(RESULTS, 1):
        print(f"{number:2}. {what}  [{duration}]\n      {command}\n      → {output}\n")


if __name__ == "__main__":
    main()
