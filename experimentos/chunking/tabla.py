# -*- coding: utf-8 -*-
"""Genera las tablas de resultados. Nada se pega a mano.

Salida en `resultados/`:

- `comparativa.md`   tabla A/A′/B/C/D con las métricas de §4, en los dos
                     modos de consulta
- `por_pregunta.csv` la posición del ancla de cada pregunta en cada
                     variante y modo, que es lo que permite ver si una
                     diferencia la sostiene una sola pregunta
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from pathlib import Path

from experimentos.chunking.consultas import cargar_cache
from experimentos.chunking.evaluar import (
    cargar_golden,
    cargar_indice,
    cobertura_anclas,
    con_ancla,
    evaluar_variante,
)
from experimentos.chunking.metricas import medir

RAIZ = Path(__file__).resolve().parent
SALIDA = RAIZ / "resultados"
VARIANTES = ["Entregado", "A", "Ap", "B", "C", "D"]
NOMBRES = {
    "Entregado": "Entregado",
    "A": "A (baseline reimpl.)",
    "Ap": "A′ (BGE + tope)",
    "B": "B (sentence-window)",
    "C": "C (table-aware)",
    "D": "D (combinada)",
}


def _sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def recopilar() -> dict:
    golden = cargar_golden()
    anclas = con_ancla(golden)
    reescritas = cargar_cache()
    modos = {"original": {}, "reescrita": reescritas}

    datos = {}
    for variante in VARIANTES:
        _, meta = cargar_indice(variante)
        if "encabezado_repetido" not in meta.columns:
            meta = meta.assign(encabezado_repetido="")
        cubiertas, fallan = cobertura_anclas(meta, golden)
        entrada = {
            "estructura": medir(meta),
            "cobertura_anclas": (cubiertas, len(anclas), fallan),
            "evaluacion": {},
        }
        for modo, consultas in modos.items():
            if modo == "reescrita" and not consultas:
                continue
            for con_filtro in (True, False):
                clave = f"{modo}/{'filtro' if con_filtro else 'sin_filtro'}"
                entrada["evaluacion"][clave] = evaluar_variante(
                    variante, golden, consultas, con_filtro=con_filtro
                )
        datos[variante] = entrada
    return {"golden": golden, "variantes": datos}


def _fila(variante, datos, clave):
    est = datos["estructura"]
    ev = datos["evaluacion"].get(clave)
    cub, tot, _ = datos["cobertura_anclas"]
    if ev is None:
        return None
    return (
        f"| {NOMBRES[variante]} | {est['n_chunks']} | {est['tokens_medios']:.0f} | "
        f"{est['pct_sobre_tope']:.1f} % | {cub}/{tot} | "
        f"{est['cobertura_oraciones']:.2f} % | {est['pct_tablas_partidas']:.1f} % | "
        f"{est['pct_tabulares_sin_cabecera']:.1f} % | "
        f"{ev['aciertos']}/{ev['n_preguntas']} ({ev['recall_5']:.0%}) | "
        f"{ev['mrr']:.3f} | {ev['tokens_top5_medio']:.0f} |"
    )


def _cambios(datos, referencia, variante, clave):
    """Preguntas que cambian de acierto a fallo y viceversa."""
    a = datos[referencia]["evaluacion"][clave]["por_pregunta"]
    b = datos[variante]["evaluacion"][clave]["por_pregunta"]
    ganadas = [i for i in a if not a[i]["acierto"] and b[i]["acierto"]]
    perdidas = [i for i in a if a[i]["acierto"] and not b[i]["acierto"]]
    return ganadas, perdidas


def escribir(recopilado: dict) -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    datos = recopilado["variantes"]
    golden = recopilado["golden"]
    claves = [
        k for k in datos["A"]["evaluacion"] if k.startswith("original")
    ] + [k for k in datos["A"]["evaluacion"] if k.startswith("reescrita")]

    cabecera = (
        "| Variante | Chunks | Tok. medios | > 510 tok | Cobertura anclas | "
        "Cobertura oraciones | Tablas partidas | Tabulares sin cabecera | "
        "recall@5 | MRR | Tokens top-5 |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    )

    lineas = [
        "# Comparativa de estrategias de troceado",
        "",
        f"Generado por `experimentos.chunking.tabla` el {date.today().isoformat()}.",
        "",
        f"Golden set: `data/golden_set.jsonl`, SHA-256 "
        f"`{_sha256(Path('data/golden_set.jsonl'))}`, "
        f"{len(golden)} preguntas, {len(con_ancla(golden))} con ancla.",
        "",
    ]

    for clave in claves:
        modo, filtro = clave.split("/")
        lineas += [
            f"## Consulta {modo}, {'con filtro' if filtro == 'filtro' else 'sin filtro'}",
            "",
            cabecera,
        ]
        for variante in VARIANTES:
            fila = _fila(variante, datos[variante], clave)
            if fila:
                lineas.append(fila)
        lineas.append("")
        if filtro == "filtro":
            lineas += ["Preguntas que cambian respecto a A′:", ""]
            for variante in ("B", "C", "D"):
                ganadas, perdidas = _cambios(datos, "Ap", variante, clave)
                lineas.append(
                    f"- **{variante}**: gana {ganadas or '—'}, pierde {perdidas or '—'}"
                )
            ganadas, perdidas = _cambios(datos, "Entregado", "A", clave)
            lineas.append(
                f"- **A frente al entregado**: gana {ganadas or '—'}, "
                f"pierde {perdidas or '—'}"
            )
            lineas.append("")

    (SALIDA / "comparativa.md").write_text("\n".join(lineas), encoding="utf-8")

    with (SALIDA / "por_pregunta.csv").open(
        "w", encoding="utf-8", newline=""
    ) as fh:
        escritor = csv.writer(fh)
        escritor.writerow(["pregunta", "modo", "filtro", "variante", "posicion", "acierto"])
        for variante in VARIANTES:
            for clave, ev in datos[variante]["evaluacion"].items():
                modo, filtro = clave.split("/")
                for pid, v in ev["por_pregunta"].items():
                    escritor.writerow(
                        [pid, modo, filtro, variante, v["posicion"], int(v["acierto"])]
                    )

    (SALIDA / "crudo.json").write_text(
        json.dumps(
            {v: datos[v] for v in VARIANTES}, ensure_ascii=False, indent=2, default=str
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    escribir(recopilar())
    print(f"escrito en {SALIDA}")
