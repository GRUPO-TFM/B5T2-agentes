"""La escalera de arquitecturas en una figura: acierto, recall, coste y latencia.

    uv run --with matplotlib python -m agente.graficos

Sin API: lee las `tabla.csv` que deja `puntuar()` (ejecuta antes
`python -m agente.lotes reconciliar` para que estén al día) y escribe
`docs/figuras/escalera_arquitecturas.png` y su tabla `.csv` al lado.

Decisiones de la figura:
- Cuatro paneles, UNA magnitud por panel y un solo eje en cada uno. Coste y
  latencia no comparten eje: tienen escalas distintas y un doble eje fabrica
  correlaciones visuales que no existen.
- Dos series, una por golden set. No se promedian: el original es la
  regresión (3 repeticiones, con la banda mín-máx) y el difícil mide
  capacidad (1 repetición, sin banda: no hay varianza que enseñar).
- Recall@5 solo en el golden original: es una propiedad del RETRIEVER sobre
  las 14 anclas con los filtros del golden, no del agente. Si una arquitectura
  no se ejecutó con el agente (A3 en el original), se calcula igual desde el
  retriever, porque no depende de que el agente haya corrido.
- matplotlib no es dependencia del paquete (no hace falta el día 24): se trae
  con `--with matplotlib` solo para dibujar.
"""
from __future__ import annotations

import sys

import pandas as pd

from agente import interfaz, lotes

ETIQUETAS = {
    "baseline": "baseline",
    "a1_guardrails": "A1\nguardrails",
    "a2_retrieval": "A2\nretrieval",
    "a3_hibrido": "A3\nhíbrido",
    "a4_comparativas": "A4\ncomparativas",
}
METRICAS = [  # (columna de resumir(), título del panel, formato, escala)
    ("acierto", "Acierto", "{:.0%}", 1.0),
    ("recall@5", "Recall@5 del retriever · golden original (14 anclas)", "{:.0%}", 1.0),
    ("coste medio (¢)", "Coste por pregunta (¢)", "{:.2f}", 1.0),
    ("latencia media (s)", "Latencia por pregunta (s)", "{:.0f}", 1.0),
]
# Paleta categórica validada (skill dataviz, modo claro): slot 1 azul, slot 2 naranja.
COLOR = {"original": "#2a78d6", "dificil": "#eb6834"}
NOMBRE = {"original": "Golden original (20 preg. × 3 reps)",
          "dificil": "Golden difícil v2 (18 preg. × 1 rep)"}
SUPERFICIE, TINTA, TINTA_2, REJILLA = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"


def _recall_retriever(nombre: str) -> float | None:
    """Recall@5 del retriever de una arquitectura sobre las anclas del golden
    original, sin agente. Necesita el codificador (en el PC, no en la nube)."""
    try:
        from agente.metricas import acierta
        from agente.recall import recuperar_para
        arq = interfaz.arquitectura(nombre)
        items = [g for g in interfaz.leer_golden(lotes.GOLDENS["original"][0]) if g.get("ancla_texto")]
        return sum(acierta(g, recuperar_para(g, arq, k=None)[:arq.k]) for g in items) / len(items)
    except Exception as e:                                          # noqa: BLE001
        print(f"  (recall de {nombre} sin agente no calculable aquí: {type(e).__name__})")
        return None


def datos() -> pd.DataFrame:
    """Una fila por golden × arquitectura × métrica: media, mínimo y máximo entre reps."""
    filas = []
    for golden in lotes.GOLDENS:
        with lotes.carpeta_de(golden):
            for nombre in lotes.ORDEN:
                tablas = interfaz._tablas_de(interfaz.arquitectura(nombre))
                res = pd.DataFrame([interfaz.resumir(t, f"{nombre} rep{r}") for r, t in tablas.items()])
                for col, *_ in METRICAS:
                    v = res[col].dropna() if col in res else pd.Series(dtype=float)
                    fuente = "agente"
                    if v.empty and col == "recall@5" and golden == "original":
                        r = _recall_retriever(nombre)
                        v, fuente = (pd.Series([r]) if r is not None else v), "retriever"
                    if col == "recall@5" and golden != "original":
                        continue
                    filas.append({"golden": golden, "arquitectura": nombre, "metrica": col,
                                  "media": v.mean() if len(v) else None,
                                  "min": v.min() if len(v) else None,
                                  "max": v.max() if len(v) else None,
                                  "reps": len(tablas), "fuente": fuente if len(v) else ""})
    return pd.DataFrame(filas)


def dibujar(df: pd.DataFrame, salida) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9.5,
                         "axes.edgecolor": REJILLA, "axes.labelcolor": TINTA_2,
                         "xtick.color": TINTA_2, "ytick.color": TINTA_2,
                         "text.color": TINTA})
    fig, ejes = plt.subplots(2, 2, figsize=(11.5, 7.6), facecolor=SUPERFICIE)
    x = {n: i for i, n in enumerate(lotes.ORDEN)}

    for ax, (col, titulo, fmt, _) in zip(ejes.flat, METRICAS):
        ax.set_facecolor(SUPERFICIE)
        ax.set_title(titulo, loc="left", fontsize=10.5, color=TINTA, pad=10, fontweight="bold")
        for golden in lotes.GOLDENS:
            d = df[(df.golden == golden) & (df.metrica == col)].set_index("arquitectura")
            if d.empty:
                continue
            xs = [x[n] for n in d.index if pd.notna(d.loc[n, "media"])]
            ys = [d.loc[n, "media"] for n in d.index if pd.notna(d.loc[n, "media"])]
            c = COLOR[golden]
            # línea continua entre peldaños medidos; si falta uno, el hueco se ve
            tramo_x, tramo_y = [], []
            for n in lotes.ORDEN:
                m = d.loc[n, "media"] if n in d.index else None
                if m is None or pd.isna(m):
                    if tramo_x:
                        ax.plot(tramo_x, tramo_y, color=c, lw=2, solid_capstyle="round", zorder=2)
                    tramo_x, tramo_y = [], []
                    continue
                tramo_x.append(x[n]); tramo_y.append(m)
            if tramo_x:
                ax.plot(tramo_x, tramo_y, color=c, lw=2, solid_capstyle="round", zorder=2)
            # banda mín-máx entre repeticiones (solo si hay más de una)
            for n in d.index:
                r = d.loc[n]
                if r["reps"] > 1 and pd.notna(r["min"]) and r["max"] > r["min"]:
                    ax.vlines(x[n], r["min"], r["max"], color=c, lw=1, alpha=.45, zorder=1)
            # marcadores: rellenos si los midió el agente, huecos si solo el retriever
            for n in d.index:
                r = d.loc[n]
                if pd.isna(r["media"]):
                    continue
                hueco = r["fuente"] == "retriever"
                ax.scatter(x[n], r["media"], s=58, zorder=3, linewidths=2,
                           facecolor=SUPERFICIE if hueco else c, edgecolor=c if hueco else SUPERFICIE)
            # un tramo punteado y tenue salva el peldaño no medido: se lee la
            # evolución sin fingir que hay un dato donde no lo hay
            for a, b in zip(xs, xs[1:]):
                if b - a > 1:
                    ax.plot([a, b], [ys[xs.index(a)], ys[xs.index(b)]], color=c, lw=1,
                            ls=(0, (1, 3)), alpha=.6, zorder=1)
            # etiquetas selectivas: el primer y el último peldaño medidos. Encima
            # si esta serie es la de arriba en ese peldaño, debajo si es la de abajo.
            otra = df[(df.golden != golden) & (df.metrica == col)].set_index("arquitectura")["media"]
            for i in (0, -1) if len(xs) > 1 else (0,):
                n = lotes.ORDEN[xs[i]]
                v_otra = otra.get(n)
                abajo = v_otra is not None and pd.notna(v_otra) and v_otra > ys[i]
                ax.annotate(fmt.format(ys[i]), (xs[i], ys[i]), textcoords="offset points",
                            xytext=(0, -15 if abajo else 9), ha="center", fontsize=8.5, color=TINTA_2)
        ax.set_xticks(range(len(lotes.ORDEN)), [ETIQUETAS[n] for n in lotes.ORDEN], fontsize=8.5)
        ax.set_xlim(-.4, len(lotes.ORDEN) - .6)
        ax.grid(axis="y", color=REJILLA, lw=1)
        ax.set_axisbelow(True)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.tick_params(length=0)
        if fmt.endswith("%}"):
            ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
            lo = df[df.metrica == col]["min"].min()
            ax.set_ylim(max(0, (lo or 0) - .12), 1.04)
        else:
            ax.set_ylim(0, df[df.metrica == col]["max"].max() * 1.22)

    # notas de lectura en los paneles que lo necesitan
    ro = df[(df.golden == "original") & (df.metrica == "acierto")].set_index("arquitectura")
    if "a3_hibrido" in ro.index and pd.isna(ro.loc["a3_hibrido", "media"]):
        ejes.flat[0].annotate("A3 no ejecutada\nen el original", (x["a3_hibrido"], ejes.flat[0].get_ylim()[0]),
                              textcoords="offset points", xytext=(0, 8), ha="center",
                              fontsize=7.5, color=TINTA_2)
    rr = df[(df.metrica == "recall@5") & (df.fuente == "retriever")]
    if not rr.empty:
        ejes.flat[1].text(0.99, 0.04, "○ medido solo con el retriever (sin ejecutar el agente)",
                          transform=ejes.flat[1].transAxes, ha="right", fontsize=7.5, color=TINTA_2)

    from matplotlib.lines import Line2D
    fig.legend(handles=[Line2D([], [], color=COLOR[g], lw=2, marker="o", markersize=7,
                               markeredgecolor=SUPERFICIE, label=NOMBRE[g]) for g in lotes.GOLDENS],
               loc="upper left", bbox_to_anchor=(0.055, 0.935), ncol=2, frameon=False, fontsize=9)
    fig.suptitle("La escalera de arquitecturas: qué cuesta cada mejora",
                 x=0.055, y=0.985, ha="left", fontsize=13.5, fontweight="bold")
    fig.text(0.055, 0.015, "Media de las repeticiones; la barra vertical es el rango mín-máx entre "
             "repeticiones; el punteado salva un peldaño no medido. Sin llamadas a la API: "
             "todo sale de las tablas guardadas.",
             fontsize=7.5, color=TINTA_2)
    fig.tight_layout(rect=(0.04, 0.03, 1, 0.9), h_pad=2.2, w_pad=2.5)
    fig.savefig(salida, dpi=200, facecolor=SUPERFICIE)
    plt.close(fig)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                               # noqa: BLE001
        pass
    carpeta = interfaz.raiz_repo() / "docs" / "figuras"
    carpeta.mkdir(parents=True, exist_ok=True)
    df = datos()
    df.to_csv(carpeta / "escalera_arquitecturas.csv", index=False)
    dibujar(df, carpeta / "escalera_arquitecturas.png")
    ancho = df.pivot_table(index="arquitectura", columns=["golden", "metrica"], values="media").reindex(lotes.ORDEN)
    print(ancho.round(3).to_string())
    print(f"\n→ {carpeta / 'escalera_arquitecturas.png'}")


if __name__ == "__main__":
    main()
