"""Retrieval denso (día 10) e híbrido FAISS + BM25 con RRF.

`buscar(..., mejoras=False)` es el baseline: FAISS, prefijo BGE, filtros
después de rankear. `mejoras=True` reescribe la consulta y fusiona las
ramas densa y léxica por Reciprocal Rank Fusion. Los rangos empiezan en 1
y un chunk ausente de una lista no recibe contribución de esa rama.
"""

from __future__ import annotations

import functools
import re
from collections.abc import Callable, Mapping
from typing import Any

from agente.corpus import cargar_chunks, dir_corpus
from agente.reescritura import reescribir

MODELO_EMBEDDINGS = "BAAI/bge-small-en-v1.5"
PREFIJO_CONSULTA_BGE = (
    "Represent this sentence for searching relevant passages: "
)
RRF_K = 60
_PALABRAS = re.compile(r"[a-z0-9$%.]+")


@functools.lru_cache(maxsize=1)
def _indice():
    """Índice, metadatos y codificador. Se cargan una sola vez."""
    import faiss
    import pandas as pd
    from sentence_transformers import SentenceTransformer

    base = dir_corpus() / "indice"
    indice = faiss.read_index(str(base / "corpus.faiss"))
    meta = pd.read_parquet(base / "chunks_meta.parquet")

    if indice.ntotal != len(meta):
        raise RuntimeError(
            f"El índice tiene {indice.ntotal} vectores y los metadatos "
            f"{len(meta)} filas. Están desalineados: vuelve a extraer "
            "los dos ZIP en la misma carpeta."
        )

    codificador = SentenceTransformer(MODELO_EMBEDDINGS)
    return indice, meta, codificador


def tokenizar(texto: str) -> list[str]:
    """Minúsculas; conserva letras, números, `$`, `%` y puntos decimales."""
    return _PALABRAS.findall(texto.lower())


def _pasa_filtro(
    fila: Mapping[str, Any],
    ticker: str | None,
    fiscal_year: int | None,
    item: str | None,
) -> bool:
    if ticker and fila["ticker"] != ticker:
        return False
    if fiscal_year and int(fila["fiscal_year"]) != int(fiscal_year):
        return False
    if item and fila["item"] != item:
        return False
    return True


def _fragmento(fila: Mapping[str, Any], puntuacion: float) -> dict:
    return {
        "chunk_id": fila["chunk_id"],
        "ticker": fila["ticker"],
        "fiscal_year": int(fila["fiscal_year"]),
        "item": fila["item"],
        "texto": fila["texto"],
        "n_tokens": int(fila["n_tokens"]),
        "contiene_tabla": bool(fila["contiene_tabla"]),
        "puntuacion": round(float(puntuacion), 4),
    }


def montar_bm25(chunks: list[dict] | None = None):
    """`(bm25, chunks)` tokenizados con `tokenizar`. Sin caché: para tests."""
    from rank_bm25 import BM25Okapi

    if chunks is None:
        chunks = cargar_chunks()
    return BM25Okapi([tokenizar(c["texto"]) for c in chunks]), chunks


@functools.lru_cache(maxsize=1)
def _indice_bm25():
    """Índice léxico del corpus, una sola vez."""
    return montar_bm25()


def buscar_denso(
    query: str,
    ticker: str | None = None,
    fiscal_year: int | None = None,
    item: str | None = None,
    k: int | None = 5,
) -> list[dict]:
    """Ranking FAISS, filtros después. `k=None` devuelve todos los que pasan."""
    indice, meta, codificador = _indice()

    vector = codificador.encode(
        [PREFIJO_CONSULTA_BGE + query],
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype("float32")

    puntuaciones, posiciones = indice.search(vector, indice.ntotal)

    resultados: list[dict] = []
    for puntuacion, posicion in zip(puntuaciones[0], posiciones[0]):
        fila = meta.iloc[int(posicion)]
        if not _pasa_filtro(fila, ticker, fiscal_year, item):
            continue
        resultados.append(_fragmento(fila, float(puntuacion)))
        if k is not None and len(resultados) >= k:
            break
    return resultados


def buscar_lexico(
    query: str,
    ticker: str | None = None,
    fiscal_year: int | None = None,
    item: str | None = None,
    k: int | None = None,
    *,
    chunks: list[dict] | None = None,
) -> list[dict]:
    """Ranking BM25 sobre los chunks que pasan el filtro, orden estable."""
    if chunks is None:
        bm25, chunks = _indice_bm25()
    else:
        bm25, chunks = montar_bm25(chunks)

    tokens = tokenizar(query)
    if tokens:
        scores = bm25.get_scores(tokens)
    else:
        scores = [0.0] * len(chunks)

    ranqueados: list[tuple[float, dict]] = []
    for chunk, score in zip(chunks, scores):
        if not _pasa_filtro(chunk, ticker, fiscal_year, item):
            continue
        crudo = float(score)
        ranqueados.append((crudo, _fragmento(chunk, crudo)))
    ranqueados.sort(key=lambda par: (-par[0], par[1]["chunk_id"]))
    resultados = [frag for _score, frag in ranqueados]
    if k is not None:
        return resultados[:k]
    return resultados


def fusionar_rrf(
    ranking_denso: list[dict],
    ranking_bm25: list[dict],
    k: int = 5,
    rrf_k: int = RRF_K,
) -> list[dict]:
    """Combina rangos (desde 1), no scores brutos. Ausente ⇒ sin término."""
    scores: dict[str, float] = {}
    payload: dict[str, dict] = {}
    for rango, frag in enumerate(ranking_denso, 1):
        cid = frag["chunk_id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + rango)
        payload[cid] = frag
    for rango, frag in enumerate(ranking_bm25, 1):
        cid = frag["chunk_id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + rango)
        payload.setdefault(cid, frag)

    orden = sorted(scores, key=lambda cid: (-scores[cid], cid))
    salida: list[dict] = []
    for cid in orden[:k]:
        item = dict(payload[cid])
        item["puntuacion"] = round(scores[cid], 4)
        item["tipo_puntuacion"] = "rrf"
        salida.append(item)
    return salida


def buscar(
    query: str,
    ticker: str | None = None,
    fiscal_year: int | None = None,
    item: str | None = None,
    k: int = 5,
    *,
    mejoras: bool = False,
    reescritor: Callable[[str], str] | None = None,
    rrf_k: int = RRF_K,
) -> list[dict]:
    """Los `k` fragmentos más relevantes. Baseline si `mejoras=False`."""
    if not mejoras:
        return buscar_denso(query, ticker, fiscal_year, item, k=k)

    consulta = reescribir(query, reescritor=reescritor)
    denso = buscar_denso(consulta, ticker, fiscal_year, item, k=None)
    lexico = buscar_lexico(consulta, ticker, fiscal_year, item, k=None)
    return fusionar_rrf(denso, lexico, k=k, rrf_k=rrf_k)


def formatear_fragmentos(fragmentos: list[dict]) -> str:
    """Los fragmentos, en el texto que ve el modelo."""
    if not fragmentos:
        return ("Sin resultados para esa consulta con esos filtros. "
                "Prueba a quitar algún filtro o a reformular la búsqueda.")
    partes = []
    for f in fragmentos:
        if f.get("tipo_puntuacion") == "rrf":
            etiqueta = f"RRF {f['puntuacion']:.3f}"
        else:
            etiqueta = f"similitud {f['puntuacion']:.3f}"
        partes.append(
            f"[{f['chunk_id']}] {f['ticker']} FY{f['fiscal_year']} "
            f"Item {f['item']} ({etiqueta})\n{f['texto']}"
        )
    return "\n\n---\n\n".join(partes)
