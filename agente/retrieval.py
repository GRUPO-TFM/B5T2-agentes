"""Búsqueda densa sobre el índice FAISS. Hoy es el retrieval del día 10.

Los filtros se aplican **después** de la búsqueda, como en `miax_s1.buscar`.
El híbrido BM25 y la reescritura de consulta entran después, detrás del
interruptor `construir_agente(mejoras=True)`.
"""

from __future__ import annotations

import functools

from agente.corpus import dir_corpus

MODELO_EMBEDDINGS = "BAAI/bge-small-en-v1.5"
PREFIJO_CONSULTA_BGE = (
    "Represent this sentence for searching relevant passages: "
)


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


def buscar(
    query: str,
    ticker: str | None = None,
    fiscal_year: int | None = None,
    item: str | None = None,
    k: int = 5,
) -> list[dict]:
    """Los `k` fragmentos más parecidos a `query`, con sus metadatos."""
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
        if ticker and fila["ticker"] != ticker:
            continue
        if fiscal_year and int(fila["fiscal_year"]) != int(fiscal_year):
            continue
        if item and fila["item"] != item:
            continue
        resultados.append(
            {
                "chunk_id": fila["chunk_id"],
                "ticker": fila["ticker"],
                "fiscal_year": int(fila["fiscal_year"]),
                "item": fila["item"],
                "texto": fila["texto"],
                "n_tokens": int(fila["n_tokens"]),
                "contiene_tabla": bool(fila["contiene_tabla"]),
                "puntuacion": round(float(puntuacion), 4),
            }
        )
        if len(resultados) >= k:
            break
    return resultados


def formatear_fragmentos(fragmentos: list[dict]) -> str:
    """Los fragmentos, en el texto que ve el modelo."""
    if not fragmentos:
        return ("Sin resultados para esa consulta con esos filtros. "
                "Prueba a quitar algún filtro o a reformular la búsqueda.")
    partes = []
    for f in fragmentos:
        partes.append(
            f"[{f['chunk_id']}] {f['ticker']} FY{f['fiscal_year']} "
            f"Item {f['item']} (similitud {f['puntuacion']:.3f})\n{f['texto']}"
        )
    return "\n\n---\n\n".join(partes)
