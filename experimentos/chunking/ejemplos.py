# -*- coding: utf-8 -*-
"""Ejemplos cualitativos: qué corta mal el baseline y cómo queda después.

Busca por sí solo los casos, no van a mano:

- **tabla**: la tabla con más filas que A parte por una frontera de ventana
  y C mantiene entera o parte por filas repitiendo la cabecera;
- **prosa**: la oración más larga que A deja partida entre dos fragmentos
  y B mantiene entera.

Escribe `resultados/ejemplos.md` con el fragmento de cada variante recortado,
para poder pegarlo en el informe sin reescribir nada.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from agente.corpus import cargar_secciones

from experimentos.chunking.bloques import bloques_tabla
from experimentos.chunking.evaluar import cargar_indice
from experimentos.chunking.trocear import oraciones

SALIDA = Path(__file__).resolve().parent / "resultados"
RECORTE = 700


def _tramos(meta):
    porDoc = defaultdict(list)
    for f in meta.to_dict("records"):
        clave = (f["ticker"], int(f["fiscal_year"]), f["item"])
        porDoc[clave].append(f)
    for lista in porDoc.values():
        lista.sort(key=lambda f: int(f["inicio_car"]))
    return porDoc


def _entero(tramos, a, b):
    return [f for f in tramos if int(f["inicio_car"]) <= a and int(f["fin_car"]) >= b]


def _recortar(texto, n=RECORTE):
    texto = texto.replace("\t", " | ")
    return texto if len(texto) <= n else texto[:n] + " […]"


def buscar_tabla(docs_a, docs_c, secciones):
    """La tabla más grande que A parte y C mantiene entera.

    Exigir que C la mantenga entera importa: la tabla más grande del corpus
    es el índice de exhibits, que no cabe en ningún tope y que **todas** las
    variantes tienen que partir. Ahí C solo se distingue en que repite la
    cabecera, y como ejemplo se entiende mal. El caso que ilustra la
    estrategia es la tabla que A corta por una frontera de ventana y que C,
    al tratarla como bloque atómico, deja de una pieza.
    """
    mejor = None
    for r in secciones.itertuples():
        clave = (r.ticker, int(r.fiscal_year), r.item)
        ta, tc = docs_a.get(clave, []), docs_c.get(clave, [])
        for ti, tf in bloques_tabla(r.texto):
            if _entero(ta, ti, tf):
                continue                       # A no la parte: no ilustra nada
            if not _entero(tc, ti, tf):
                continue                       # C tampoco la salva
            filas = r.texto[ti:tf].count("\n") + 1
            if mejor is None or filas > mejor[0]:
                mejor = (filas, clave, ti, tf, r.texto, ta, tc)
    return mejor


def buscar_oracion(docs_a, docs_b, secciones):
    """La oración más larga que A parte y B no."""
    mejor = None
    for r in secciones.itertuples():
        clave = (r.ticker, int(r.fiscal_year), r.item)
        ta, tb = docs_a.get(clave, []), docs_b.get(clave, [])
        tablas = bloques_tabla(r.texto)
        for a, b in oraciones(r.texto, 0, len(r.texto)):
            if b - a < 60 or any(not (b <= ti or a >= tf) for ti, tf in tablas):
                continue
            if _entero(ta, a, b):
                continue
            if not _entero(tb, a, b):
                continue                       # B tampoco la salva
            if mejor is None or (b - a) > mejor[0]:
                mejor = (b - a, clave, a, b, r.texto, ta, tb)
    return mejor


def _bloque(titulo, fragmentos, texto, a, b):
    lineas = [f"**{titulo}**", ""]
    tocan = [
        f
        for f in fragmentos
        if not (int(f["fin_car"]) <= a or int(f["inicio_car"]) >= b)
    ]
    if not tocan:
        lineas += ["_sin fragmento que lo cubra_", ""]
    for f in tocan:
        entero = int(f["inicio_car"]) <= a and int(f["fin_car"]) >= b
        lineas += [
            f"`{f['chunk_id']}` · {f['n_tokens']} tok · "
            f"{'contiene el tramo entero' if entero else '**lo corta**'}",
            "",
            "```",
            _recortar(f["texto"]),
            "```",
            "",
        ]
    return lineas


def main() -> None:
    secciones = cargar_secciones()
    metas = {}
    for v in ("A", "B", "C"):
        _, meta = cargar_indice(v)
        metas[v] = _tramos(meta)

    lineas = ["# Ejemplos cualitativos", ""]

    tabla = buscar_tabla(metas["A"], metas["C"], secciones)
    if tabla:
        filas, clave, ti, tf, texto, ta, tc = tabla
        lineas += [
            "## Una tabla que A corta por la mitad",
            "",
            f"{clave[0]} FY{clave[1]} Item {clave[2]}, caracteres {ti}–{tf}, "
            f"{filas} filas.",
            "",
            "Original:",
            "",
            "```",
            _recortar(texto[ti:tf]),
            "```",
            "",
        ]
        lineas += _bloque("A (baseline)", ta, texto, ti, tf)
        lineas += _bloque("C (table-aware)", tc, texto, ti, tf)

    oracion = buscar_oracion(metas["A"], metas["B"], secciones)
    if oracion:
        largo, clave, a, b, texto, ta, tb = oracion
        lineas += [
            "## Una oración que A parte en dos",
            "",
            f"{clave[0]} FY{clave[1]} Item {clave[2]}, caracteres {a}–{b}, "
            f"{largo} caracteres.",
            "",
            "Original:",
            "",
            "```",
            _recortar(texto[a:b]),
            "```",
            "",
        ]
        lineas += _bloque("A (baseline)", ta, texto, a, b)
        lineas += _bloque("B (sentence-window)", tb, texto, a, b)
    else:
        lineas += [
            "## Prosa",
            "",
            "No hay ninguna oración que A parta y B salve: el solape de 80 "
            "tokens ya cubre el 99,9 % de la prosa del corpus.",
            "",
        ]

    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "ejemplos.md").write_text("\n".join(lineas), encoding="utf-8")
    print(f"escrito en {SALIDA / 'ejemplos.md'}")


if __name__ == "__main__":
    main()
