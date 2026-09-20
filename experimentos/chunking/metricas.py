# -*- coding: utf-8 -*-
"""Métricas estructurales: no usan embeddings ni el golden set.

Son las que de verdad distinguen las variantes, porque miden lo que cada
estrategia viene a arreglar: frases partidas, tablas partidas y fragmentos
tabulares sin cabecera. El recall@5 depende además del ranking y del idioma
de la consulta; esto no.

La cobertura se calcula sobre **toda la prosa del corpus** (más de 15.000
oraciones), no solo sobre las 14 anclas del golden set, que el baseline ya
cubre al 100 % y por tanto no discriminan nada.
"""

from __future__ import annotations

import statistics
from collections import defaultdict

from agente.corpus import cargar_secciones

from experimentos.chunking.bloques import bloques_tabla
from experimentos.chunking.tokenizacion import contar_bge
from experimentos.chunking.trocear import (
    encabezado_de_columnas,
    oraciones,
)

LIMITE_UTIL = 510   # 512 menos [CLS] y [SEP]
MIN_ORACION = 40    # caracteres; por debajo son fragmentos de tabla o rótulos


def _por_documento(meta):
    porDoc = defaultdict(list)
    for fila in meta.to_dict("records"):
        clave = (fila["ticker"], int(fila["fiscal_year"]), fila["item"])
        porDoc[clave].append(fila)
    for lista in porDoc.values():
        lista.sort(key=lambda f: int(f["inicio_car"]))
    return porDoc


def medir(meta) -> dict:
    """Todas las métricas estructurales de una variante."""
    secciones = cargar_secciones()
    porDoc = _por_documento(meta)

    oraciones_totales = oraciones_cubiertas = 0
    tablas_totales = tablas_enteras = 0
    tabulares = sin_cabecera = 0

    for r in secciones.itertuples():
        clave = (r.ticker, int(r.fiscal_year), r.item)
        trozos = porDoc.get(clave, [])
        tramos = [(int(f["inicio_car"]), int(f["fin_car"])) for f in trozos]
        texto = r.texto

        # 1. Cobertura de oraciones de prosa (líneas sin tabulador).
        tablas = bloques_tabla(texto)
        for a, b in oraciones(texto, 0, len(texto)):
            if b - a < MIN_ORACION:
                continue
            if any(not (b <= ti or a >= tf) for ti, tf in tablas):
                continue        # es texto de tabla, no prosa
            oraciones_totales += 1
            if any(i <= a and f >= b for i, f in tramos):
                oraciones_cubiertas += 1

        # 2. Tablas enteras dentro de algún fragmento.
        for ti, tf in tablas:
            tablas_totales += 1
            if any(i <= ti and f >= tf for i, f in tramos):
                tablas_enteras += 1

        # 3. Fragmentos tabulares que empiezan sin su cabecera.
        for fila in trozos:
            if "\t" not in fila["texto"]:
                continue
            tabulares += 1
            if fila.get("encabezado_repetido"):
                continue        # la lleva repetida: cuenta como que la tiene
            inicio = int(fila["inicio_car"])
            for ti, tf in tablas:
                if not (int(fila["fin_car"]) <= ti or inicio >= tf):
                    _, hf = encabezado_de_columnas(texto, ti, tf)
                    if inicio > ti and inicio >= hf:
                        sin_cabecera += 1
                    break

    n_tokens = [contar_bge(f) for f in meta["texto"]]
    return {
        "n_chunks": len(meta),
        "tokens_medios": statistics.mean(n_tokens),
        "tokens_max": max(n_tokens),
        "pct_sobre_tope": 100 * sum(1 for x in n_tokens if x > LIMITE_UTIL) / len(n_tokens),
        "oraciones_evaluadas": oraciones_totales,
        "cobertura_oraciones": 100 * oraciones_cubiertas / max(1, oraciones_totales),
        "tablas": tablas_totales,
        "pct_tablas_partidas": 100 * (tablas_totales - tablas_enteras) / max(1, tablas_totales),
        "fragmentos_tabulares": tabulares,
        "pct_tabulares_sin_cabecera": 100 * sin_cabecera / max(1, tabulares),
    }
