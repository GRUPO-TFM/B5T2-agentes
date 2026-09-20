# -*- coding: utf-8 -*-
"""Sonda de anclas en tabla. **No es el golden set.**

Ninguna de las 14 anclas de `data/golden_set.jsonl` cae dentro de una
tabla, así que el recall@5 del golden set no puede ver nada de lo que C y D
vienen a arreglar. Esta sonda tapa ese hueco: cinco preguntas cuyo ancla es
una fila de tabla.

Se reporta **aparte**, como diagnóstico. No entra en la tabla principal ni
en el informe como golden set: son preguntas escritas para este experimento
y validarlas con el mismo rigor que el golden set está fuera de alcance.

Las anclas no se escriben a mano: se localizan por su texto dentro de la
sección y los offsets salen de ahí, así que o cuadran o el script falla.
"""

from __future__ import annotations

import json
from pathlib import Path

from agente.corpus import cargar_secciones

SALIDA = Path(__file__).resolve().parent / "sonda_tablas.jsonl"

# (id, pregunta, ticker, fy, item, trozo literal de la fila de la tabla)
PREGUNTAS = [
    (
        "tab-001",
        "¿Cuál fue el margen bruto de Microsoft en el ejercicio 2025?",
        "MSFT", 2025, "7",
        "Gross margin",
        "193,893",
    ),
    (
        "tab-002",
        "¿Cuántos ingresos por intereses y dividendos registró Microsoft "
        "en el ejercicio 2025?",
        "MSFT", 2025, "7",
        "Interest and dividends income",
        "2,647",
    ),
    (
        "tab-003",
        "¿A cuánto ascendían los compromisos de compra de Microsoft a 30 de "
        "junio de 2025?",
        "MSFT", 2025, "7",
        "Purchase commitments",
        "103,940",
    ),
    (
        "tab-004",
        "¿Qué porcentaje de los ingresos representó el gasto en investigación "
        "y desarrollo de NVIDIA en el ejercicio 2025?",
        "NVDA", 2025, "7",
        "Research and development",
        "9.9",
    ),
    (
        "tab-005",
        "¿Qué porcentaje de los ingresos fue el beneficio bruto de NVIDIA en "
        "el ejercicio 2025?",
        "NVDA", 2025, "7",
        "Gross profit",
        "75.0",
    ),
]


def generar() -> list[dict]:
    secciones = cargar_secciones()
    texto_de = {
        (r.ticker, int(r.fiscal_year), r.item): r.texto
        for r in secciones.itertuples()
    }

    filas = []
    for ident, pregunta, ticker, fy, item, etiqueta, cifra in PREGUNTAS:
        texto = texto_de[(ticker, fy, item)]
        # La fila es la línea que lleva la etiqueta y la cifra a la vez.
        ancla = inicio = None
        cursor = 0
        while True:
            i = texto.find(etiqueta, cursor)
            if i < 0:
                break
            ini = texto.rfind("\n", 0, i) + 1
            fin = texto.find("\n", i)
            fin = len(texto) if fin < 0 else fin
            linea = texto[ini:fin]
            if cifra in linea and "\t" in linea:
                ancla, inicio = linea, ini
                break
            cursor = i + 1
        if ancla is None:
            raise RuntimeError(f"{ident}: no encuentro la fila de {etiqueta!r}")

        assert texto[inicio : inicio + len(ancla)] == ancla
        filas.append(
            {
                "id": ident,
                "pregunta": pregunta,
                "familia": "tabular",
                "ticker": ticker,
                "fiscal_year": fy,
                "respuesta_esperada": None,
                "cifra_esperada": None,
                "unidad": None,
                "concept_xbrl": None,
                "item_esperado": item,
                "ancla_texto": ancla,
                "ancla_inicio": inicio,
                "ancla_fin": inicio + len(ancla),
                "chunk_id_esperado": None,
                "herramienta_esperada": ["search_filings"],
                "autor": "sonda-chunking",
            }
        )
    return filas


if __name__ == "__main__":
    filas = generar()
    with SALIDA.open("w", encoding="utf-8", newline="\n") as fh:
        for fila in filas:
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
    for f in filas:
        print(f"{f['id']}  [{f['ancla_inicio']}:{f['ancla_fin']}]  "
              f"{f['ancla_texto'][:70].replace(chr(9), ' | ')}")
