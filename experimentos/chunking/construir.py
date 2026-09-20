# -*- coding: utf-8 -*-
"""Construye los artefactos de una variante: fragmentos, vectores e índice.

Constantes en todas las variantes, para que lo único que cambie sea el
troceado: el modelo de embeddings, la normalización, `IndexFlatIP`, el
prefijo BGE **solo en la consulta** y el orden de las filas.

Cada variante deja en `experimentos/chunking/<variante>/`:

- `chunks.jsonl`          (ignorado por git; regenerable)
- `embeddings.npy`        (ignorado)
- `chunks_meta.parquet`   (ignorado)
- `corpus.faiss`          (ignorado)
- `manifiesto.json`       (**versionado**)

El manifiesto ata el índice a sus fragmentos por SHA-256. Si alguien
regenera `chunks.jsonl` sin regenerar el índice, `cargar()` lo detecta y
falla en vez de devolver texto equivocado en silencio.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from agente.corpus import cargar_secciones

from experimentos.chunking.tokenizacion import (
    LIMITE_MODELO,
    MODELO_EMBEDDINGS,
    contar_bge,
    contar_cl100k,
)
from experimentos.chunking.trocear import VARIANTES, trocear

RAIZ = Path(__file__).resolve().parent
CAMPOS = [
    "chunk_id",
    "ticker",
    "fiscal_year",
    "item",
    "posicion",
    "inicio_car",
    "fin_car",
    "n_tokens",
    "contiene_tabla",
    "texto",
    "encabezado_repetido",
]


def _sha256(ruta: Path) -> str:
    digest = hashlib.sha256()
    with ruta.open("rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            digest.update(bloque)
    return digest.hexdigest()


def generar_chunks(variante: str) -> list[dict]:
    """Los fragmentos de una variante, a partir de `secciones.jsonl`."""
    parametros = VARIANTES[variante]
    contar = contar_cl100k if not parametros.get("bge", True) else contar_bge

    filas: list[dict] = []
    secciones = cargar_secciones()
    for r in secciones.sort_values(["ticker", "fiscal_year", "item"]).itertuples():
        fiscal_year = int(r.fiscal_year)
        for posicion, f in enumerate(trocear(r.texto, **parametros)):
            texto = f.texto(r.texto)
            filas.append(
                {
                    "chunk_id": f"{r.ticker}-{fiscal_year}-{r.item}-{posicion:04d}",
                    "ticker": r.ticker,
                    "fiscal_year": fiscal_year,
                    "item": r.item,
                    "posicion": posicion,
                    "inicio_car": f.inicio_car,
                    "fin_car": f.fin_car,
                    "n_tokens": contar(texto),
                    "contiene_tabla": "\t" in texto,
                    "texto": texto,
                    "encabezado_repetido": f.encabezado_repetido,
                }
            )
    return filas


def construir(variante: str, rehacer: bool = False) -> Path:
    """Genera fragmentos, vectores, metadatos, índice y manifiesto."""
    import faiss
    import numpy as np
    import pandas as pd
    from sentence_transformers import SentenceTransformer

    destino = RAIZ / variante
    destino.mkdir(parents=True, exist_ok=True)
    manifiesto = destino / "manifiesto.json"
    if manifiesto.is_file() and not rehacer:
        return destino

    filas = generar_chunks(variante)
    ruta_chunks = destino / "chunks.jsonl"
    with ruta_chunks.open("w", encoding="utf-8", newline="\n") as fh:
        for fila in filas:
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")

    codificador = SentenceTransformer(MODELO_EMBEDDINGS)
    vectores = codificador.encode(
        [f["texto"] for f in filas],      # los documentos NO llevan prefijo
        normalize_embeddings=True,
        convert_to_numpy=True,
        batch_size=64,
        show_progress_bar=False,
    ).astype("float32")

    meta = pd.DataFrame(filas, columns=CAMPOS)
    meta.to_parquet(destino / "chunks_meta.parquet", index=False)
    np.save(destino / "embeddings.npy", vectores)

    indice = faiss.IndexFlatIP(vectores.shape[1])
    indice.add(vectores)
    faiss.write_index(indice, str(destino / "corpus.faiss"))

    # La fila i describe el vector i. Si esto no se cumple, todo lo demás
    # miente sin dar error.
    assert indice.ntotal == len(meta) == len(filas), "índice y metadatos desalineados"
    assert list(meta["chunk_id"]) == [f["chunk_id"] for f in filas]

    huella = _sha256(ruta_chunks)
    n_bge = [contar_bge(f["texto"]) for f in filas]
    manifiesto.write_text(
        json.dumps(
            {
                "variante": variante,
                "parametros": VARIANTES[variante],
                "modelo_embeddings": MODELO_EMBEDDINGS,
                "normalizacion": "L2, IndexFlatIP (coseno)",
                "prefijo_bge": "solo en la consulta",
                "tokenizador_recuento": (
                    "tiktoken cl100k_base"
                    if not VARIANTES[variante].get("bge", True)
                    else f"{MODELO_EMBEDDINGS} (WordPiece)"
                ),
                "limite_modelo": LIMITE_MODELO,
                "n_chunks": len(filas),
                "dimension": int(vectores.shape[1]),
                "sha256_chunks_jsonl": huella,
                "tokens_bge_max": max(n_bge),
                "chunks_por_encima_de_510": sum(1 for x in n_bge if x > 510),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return destino


def cargar(variante: str):
    """(índice, metadatos) de una variante, comprobando la alineación."""
    import faiss
    import pandas as pd

    destino = RAIZ / variante
    datos = json.loads((destino / "manifiesto.json").read_text(encoding="utf-8"))
    if _sha256(destino / "chunks.jsonl") != datos["sha256_chunks_jsonl"]:
        raise RuntimeError(
            f"{variante}: chunks.jsonl no cuadra con el manifiesto. El índice "
            "se construyó sobre otros fragmentos: reconstruye la variante."
        )
    indice = faiss.read_index(str(destino / "corpus.faiss"))
    meta = pd.read_parquet(destino / "chunks_meta.parquet")
    if indice.ntotal != len(meta):
        raise RuntimeError(
            f"{variante}: {indice.ntotal} vectores y {len(meta)} filas."
        )
    return indice, meta


if __name__ == "__main__":
    import sys

    pedidas = [a for a in sys.argv[1:] if not a.startswith("--")]
    for variante in pedidas or list(VARIANTES):
        destino = construir(variante, rehacer="--rehacer" in sys.argv)
        datos = json.loads(
            (destino / "manifiesto.json").read_text(encoding="utf-8")
        )
        print(
            f"{variante:3s} {datos['n_chunks']:5d} fragmentos  "
            f"máx {datos['tokens_bge_max']:4d} tok BGE  "
            f">510: {datos['chunks_por_encima_de_510']:4d}  "
            f"{datos['sha256_chunks_jsonl'][:12]}"
        )
