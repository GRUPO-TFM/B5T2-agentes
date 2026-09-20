# -*- coding: utf-8 -*-
"""Métricas de §4, iguales para todas las variantes.

Configuración principal: **con filtro** ticker/ejercicio/ítem. Secundaria:
sin filtro. `fiscal_year` se compara como entero siempre.

Un fragmento acierta si es del mismo documento (ticker, ejercicio, ítem) y
contiene el ancla: por tramo cuando hay offsets, y por texto normalizado si
no. Un fragmento del ejercicio equivocado no cuenta, aunque repita el texto
palabra por palabra — los 10-K copian factores de riesgo de un año a otro.

La cabecera repetida de una tabla partida no está en `[inicio_car, fin_car]`,
así que el criterio por tramo sigue midiendo el cuerpo y no se descuadra.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ESPACIOS = re.compile(r"\s+")
K = 5

PREFIJO_CONSULTA_BGE = "Represent this sentence for searching relevant passages: "


def normalizar(texto: str) -> str:
    return ESPACIOS.sub(" ", texto).strip().lower()


def cargar_golden(ruta: str = "data/golden_set.jsonl") -> list[dict]:
    with open(ruta, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def con_ancla(golden: list[dict]) -> list[dict]:
    return [g for g in golden if g.get("ancla_texto")]


# ---------------------------------------------------------------------------
# Índices
# ---------------------------------------------------------------------------
def cargar_indice(variante: str):
    """(índice, metadatos). `Entregado` es el índice congelado del corpus."""
    if variante == "Entregado":
        import faiss
        import pandas as pd

        from agente.corpus import dir_corpus

        base = dir_corpus() / "indice"
        indice = faiss.read_index(str(base / "corpus.faiss"))
        meta = pd.read_parquet(base / "chunks_meta.parquet")
        if indice.ntotal != len(meta):
            raise RuntimeError("índice entregado desalineado")
        return indice, meta

    from experimentos.chunking.construir import cargar

    return cargar(variante)


def _codificador():
    from functools import lru_cache

    @lru_cache(maxsize=1)
    def _cargar():
        from sentence_transformers import SentenceTransformer

        from experimentos.chunking.tokenizacion import MODELO_EMBEDDINGS

        return SentenceTransformer(MODELO_EMBEDDINGS)

    return _cargar()


def rankear(indice, meta, consulta: str, item: dict, con_filtro: bool) -> list[dict]:
    """Ranking completo (no solo k), para poder dar la posición del ancla."""
    import numpy as np

    vector = (
        _codificador()
        .encode(
            [PREFIJO_CONSULTA_BGE + consulta],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        .astype("float32")
    )
    _, posiciones = indice.search(vector, indice.ntotal)

    columnas = meta.columns
    salida = []
    for p in posiciones[0]:
        fila = meta.iloc[int(p)]
        if con_filtro:
            if fila["ticker"] != item["ticker"]:
                continue
            if int(fila["fiscal_year"]) != int(item["fiscal_year"]):
                continue
            if item.get("item_esperado") and fila["item"] != item["item_esperado"]:
                continue
        salida.append(
            {
                "chunk_id": fila["chunk_id"],
                "ticker": fila["ticker"],
                "fiscal_year": int(fila["fiscal_year"]),
                "item": fila["item"],
                "texto": fila["texto"],
                "inicio_car": int(fila["inicio_car"]),
                "fin_car": int(fila["fin_car"]),
                "n_tokens": int(fila["n_tokens"]),
                "contiene_tabla": bool(fila["contiene_tabla"]),
            }
        )
    return salida


# ---------------------------------------------------------------------------
# Acierto
# ---------------------------------------------------------------------------
def acierta(item: dict, fragmento: dict) -> bool:
    if fragmento["ticker"] != item["ticker"]:
        return False
    if int(fragmento["fiscal_year"]) != int(item["fiscal_year"]):
        return False

    inicio, fin = item.get("ancla_inicio"), item.get("ancla_fin")
    if (
        inicio is not None
        and fragmento["item"] == item.get("item_esperado")
        and fragmento["inicio_car"] <= inicio
        and fragmento["fin_car"] >= fin
    ):
        return True
    return normalizar(item["ancla_texto"]) in normalizar(fragmento["texto"])


def cobertura_anclas(meta, golden: list[dict]) -> tuple[int, list[str]]:
    """¿Está cada ancla entera en algún fragmento de su documento?"""
    cubiertas, fallan = 0, []
    filas = meta.to_dict("records")
    for g in con_ancla(golden):
        candidatos = [
            f
            for f in filas
            if f["ticker"] == g["ticker"]
            and int(f["fiscal_year"]) == int(g["fiscal_year"])
        ]
        if any(
            acierta(
                g,
                {
                    **f,
                    "fiscal_year": int(f["fiscal_year"]),
                    "inicio_car": int(f["inicio_car"]),
                    "fin_car": int(f["fin_car"]),
                },
            )
            for f in candidatos
        ):
            cubiertas += 1
        else:
            fallan.append(g["id"])
    return cubiertas, fallan


def evaluar_variante(
    variante: str,
    golden: list[dict],
    consultas: dict[str, str],
    con_filtro: bool = True,
) -> dict:
    """recall@5, MRR y posiciones para una variante y un modo de consulta."""
    indice, meta = cargar_indice(variante)
    items = con_ancla(golden)

    por_pregunta = {}
    for g in items:
        consulta = consultas.get(g["id"], g["pregunta"])
        ranking = rankear(indice, meta, consulta, g, con_filtro)
        posicion = next(
            (i + 1 for i, f in enumerate(ranking) if acierta(g, f)), None
        )
        tokens_top5 = sum(f["n_tokens"] for f in ranking[:K])
        por_pregunta[g["id"]] = {
            "posicion": posicion,
            "acierto": bool(posicion and posicion <= K),
            "tokens_top5": tokens_top5,
        }

    aciertos = sum(v["acierto"] for v in por_pregunta.values())
    mrr = sum(
        1 / v["posicion"] for v in por_pregunta.values() if v["posicion"]
    ) / len(items)
    return {
        "variante": variante,
        "con_filtro": con_filtro,
        "n_preguntas": len(items),
        "aciertos": aciertos,
        "recall_5": aciertos / len(items),
        "mrr": mrr,
        "tokens_top5_medio": sum(
            v["tokens_top5"] for v in por_pregunta.values()
        )
        / len(items),
        "por_pregunta": por_pregunta,
    }
