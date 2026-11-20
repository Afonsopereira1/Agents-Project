"""Dois gráficos SVG a partir de results/experiments/summary.csv, sem dependências.

Uma linha por cenário e variante, com barra e valor: taxas (precision, recall, FPR)
e custo (energia e mensagens por execução). Só lê o CSV; não corre agentes.
Uso, a partir da raiz: python scripts/charts.py
Grava results/experiments/charts/taxas.svg e custo.svg (modo claro e escuro no próprio SVG).
"""
import csv
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "experiments" / "charts"
# Paleta categórica validada (claro, escuro), em ordem fixa: a cor segue a variante.
VARIANTS = {"full": ("#2a78d6", "#3987e5"), "no_reputation": ("#eb6834", "#d95926"),
            "no_corroboration": ("#1baf7a", "#199e70"), "nearest": ("#eda100", "#c98500")}
STYLE = """<style>
.bg{fill:#fcfcfb}.t1{fill:#0b0b0b}.t2{fill:#52514e}.mu{fill:#898781}.grid{stroke:#e1e0d9}.axis{stroke:#c3c2b7}
%s
text{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;font-size:12px}
.title{font-size:15px;font-weight:600}.num{font-variant-numeric:tabular-nums}
@media (prefers-color-scheme:dark){.bg{fill:#1a1a19}.t1{fill:#f0efec}.t2{fill:#c3c2b7}.grid{stroke:#2c2c2a}.axis{stroke:#383835}
%s}
</style>""" % ("".join(f".s{i}{{fill:{c[0]}}}" for i, c in enumerate(VARIANTS.values())),
               "".join(f".s{i}{{fill:{c[1]}}}" for i, c in enumerate(VARIANTS.values())))
LABEL, PANEL, GAP, ROW, BAR, TOP = 150, 150, 70, 20, 12, 78


def number(text):
    """Converter uma célula do CSV em float; vazio e "N/A" dão ``None``.

    Args:
        text (str): Valor da célula, tal como vem do ``csv.DictReader``.

    Returns:
        float | None: O valor numérico, ou ``None`` se a célula estiver vazia ou for "N/A".
    """
    return None if text in ("", "N/A") else float(text)


def bar(x, y, width, cls, tip):
    """Desenhar uma barra com a base quadrada e a ponta arredondada (4 px).

    O ``<title>`` da barra mostra o valor ao passar o rato.

    Args:
        x (float): Abcissa da base da barra, em px.
        y (float): Ordenada do topo da barra, em px; a altura é ``BAR``.
        width (float): Comprimento da barra, em px.
        cls (str): Classe CSS da cor (``s0``…``s3``, pela variante).
        tip (str): Texto da dica, já sem escapar.

    Returns:
        str: Elemento SVG ``<path>`` com o ``<title>``.
    """
    r = min(4, width)
    path = f"M{x},{y}h{width - r:.1f}a{r},{r} 0 0 1 {r},{r}v{BAR - 2 * r}a{r},{r} 0 0 1 -{r},{r}h-{width - r:.1f}z"
    return f'<path class="{cls}" d="{path}"><title>{escape(tip)}</title></path>'


def chart(rows, title, subtitle, columns):
    """Desenhar um gráfico de painéis, um por entrada de ``columns``, cada um com o seu eixo.

    Valores acima do máximo do eixo ficam cortados no fim do painel; "N/A" (ou um valor com
    menos de 1 px) não desenha barra.

    Args:
        rows (list[dict[str, str]]): Linhas de ``summary.csv``, com ``scenario``, ``variant`` e as
            colunas pedidas, já contíguas por cenário (o cabeçalho muda quando o cenário muda).
        title (str): Título do gráfico.
        subtitle (str): Linha de contexto por baixo do título (fonte, nº de execuções).
        columns (list[tuple[str, str, float, str]]): Um painel por entrada: (cabeçalho, coluna do
            CSV, máximo do eixo, formato de ``format``).

    Returns:
        str: Documento SVG completo, terminado em mudança de linha.
    """
    scenarios = list(dict.fromkeys(row["scenario"] for row in rows))
    height = TOP + len(rows) * ROW + len(scenarios) * 14 + 28
    width = LABEL + len(columns) * (PANEL + GAP)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
           f'height="{height}" role="img" aria-label="{escape(title)}">', STYLE,
           f'<rect class="bg" width="{width}" height="{height}"/>',
           f'<text class="title t1" x="12" y="22">{escape(title)}</text>',
           f'<text class="t2" x="12" y="40">{escape(subtitle)}</text>']
    for i, name in enumerate(VARIANTS):  # legenda: a cor nunca é o único identificador (as linhas têm nome)
        out.append(f'<rect class="s{i}" x="{12 + i * 150}" y="50" width="10" height="10" rx="2"/>'
                   f'<text class="t2" x="{27 + i * 150}" y="59">{name}</text>')
    for j, (header, _, top, _) in enumerate(columns):
        x0 = LABEL + j * (PANEL + GAP)
        out.append(f'<text class="t1" x="{x0}" y="{TOP - 4}" font-weight="600">{escape(header)}</text>')
        for fraction in (0.5, 1):
            x = x0 + PANEL * fraction
            out.append(f'<line class="grid" x1="{x}" x2="{x}" y1="{TOP + 4}" y2="{height - 22}"/>'
                       f'<text class="mu num" x="{x}" y="{height - 8}" text-anchor="middle">{format(top * fraction, "g").replace(".", ",")}</text>')
        out.append(f'<line class="axis" x1="{x0}" x2="{x0}" y1="{TOP + 4}" y2="{height - 22}"/>'
                   f'<text class="mu num" x="{x0}" y="{height - 8}" text-anchor="middle">0</text>')
    y, previous = TOP + 4, None
    for row in rows:
        if row["scenario"] != previous:
            previous, y = row["scenario"], y + 14
            out.append(f'<text class="t1" x="12" y="{y - 3}" font-weight="600">Cenário {previous}</text>')
        index = list(VARIANTS).index(row["variant"])
        out.append(f'<text class="t2" x="24" y="{y + 14}">{row["variant"]}</text>')
        for j, (header, key, top, fmt) in enumerate(columns):
            x0, value = LABEL + j * (PANEL + GAP), number(row[key])
            shown = "N/A" if value is None else format(value, fmt).replace(".", ",")
            length = 0 if value is None else PANEL * min(value, top) / top
            if length >= 1:
                out.append(bar(x0, y + 4, length, f"s{index}", f"{row['scenario']} {row['variant']} — {header}: {shown}"))
            out.append(f'<text class="t1 num" x="{x0 + length + 6:.1f}" y="{y + 14}">{shown}</text>')
        y += ROW
    return "\n".join(out + ["</svg>"]) + "\n"


# Self-check: metade do máximo dá meia largura de painel; N/A não desenha barra.
_svg = chart([{"scenario": "A", "variant": "full", "v": "0.5", "w": "N/A"}], "t", "s",
             [("v", "v", 1, ".2f"), ("w", "w", 1, ".2f")])
assert f"h{PANEL / 2 - 4:.1f}a4,4" in _svg and _svg.count("<path") == 1 and ">N/A<" in _svg

if __name__ == "__main__":
    with open(ROOT / "results" / "experiments" / "summary.csv", encoding="utf-8") as stream:
        data = list(csv.DictReader(stream))
    OUT.mkdir(parents=True, exist_ok=True)
    runs = "Etapa 9: 560 execuções, 20 sementes por episódio. Fonte: results/experiments/summary.csv"
    charts = {
        "taxas.svg": ("Taxas de classificação por cenário e variante", runs,
                      [("Precision", "precision", 1, ".2f"), ("Recall", "recall", 1, ".2f"), ("FPR", "fpr", 1, ".2f")]),
        "custo.svg": ("Custo por execução, por cenário e variante", runs,
                      [("Energia gasta (p.p., média)", "energy_used_mean", 10, ".1f"),
                       ("Mensagens (média)", "messages_sent_mean", 8, ".1f"),
                       ("Execuções não resolvidas", "unresolved_runs", 12, ".0f")]),
    }
    for name, (title, subtitle, columns) in charts.items():
        (OUT / name).write_text(chart(data, title, subtitle, columns), encoding="utf-8")
        print("gravado:", (OUT / name).relative_to(ROOT))
