"""Rutas y carga del corpus 10-K.

Una sola copia: `corpus/` en la raíz del repo, extraída de los ZIP de
`dataset/`. Los notebooks de `clase/` no tienen corpus propio.
"""

from __future__ import annotations

import functools
import hashlib
import json
import zipfile
from pathlib import Path

import pandas as pd

PAQUETES = [
    (
        "corpus_miax_2026.zip",
        "4233c37fc9e9d12091af7a146063ad70903a3fe51404a485854f4021c63daee4",
    ),
    (
        "indice_faiss.zip",
        "6b5610ad8ac6ea50364445d39bb464d993cbd87048fb07c4fe16657d7ac11655",
    ),
]


class CorpusNoEncontrado(RuntimeError):
    """El corpus no está montado. Se lanza con instrucciones, no a secas."""


def raiz_repo() -> Path:
    """Directorio que contiene `pyproject.toml`."""
    for candidato in Path(__file__).resolve().parents:
        if (candidato / "pyproject.toml").is_file():
            return candidato
    return Path.cwd().resolve()


def _sha256(ruta: Path) -> str:
    digest = hashlib.sha256()
    with ruta.open("rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            digest.update(bloque)
    return digest.hexdigest()


def _es_corpus(carpeta: Path) -> bool:
    return (
        (carpeta / "chunks.jsonl").is_file()
        and (carpeta / "secciones.jsonl").is_file()
        and (carpeta / "xbrl_facts.parquet").is_file()
        and (carpeta / "indice" / "corpus.faiss").is_file()
        and (carpeta / "indice" / "chunks_meta.parquet").is_file()
    )


def _extraer(destino: Path) -> Path:
    dataset = raiz_repo() / "dataset"
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, esperado in PAQUETES:
        origen = dataset / nombre
        if not origen.is_file():
            raise CorpusNoEncontrado(
                f"No encuentro {nombre} en {dataset}."
            )
        obtenido = _sha256(origen)
        if obtenido != esperado:
            raise RuntimeError(
                f"{nombre} no coincide con el hash esperado: el fichero "
                f"está corrupto o es de otra versión.\n"
                f"  esperado: {esperado}\n  obtenido: {obtenido}"
            )
        with zipfile.ZipFile(origen) as zf:
            zf.extractall(destino)

    huella = _sha256(destino / "chunks.jsonl")
    for manifiesto in ("MANIFEST.md", "indice/MANIFEST.md"):
        ruta = destino / manifiesto
        if ruta.is_file() and huella not in ruta.read_text(encoding="utf-8"):
            raise RuntimeError(
                f"chunks.jsonl no cuadra con {manifiesto}: el índice se "
                "construyó sobre otros fragmentos."
            )
    if not _es_corpus(destino):
        raise CorpusNoEncontrado(
            f"La extracción en {destino} no dejó el corpus completo."
        )
    return destino


def dir_corpus() -> Path:
    """`corpus/` en la raíz del repo, extrayendo los ZIP si hace falta."""
    destino = raiz_repo() / "corpus"
    if _es_corpus(destino):
        return destino
    return _extraer(destino)


def _leer_jsonl(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8") as fh:
        return [json.loads(linea) for linea in fh if linea.strip()]


@functools.lru_cache(maxsize=1)
def cargar_secciones() -> pd.DataFrame:
    return pd.DataFrame(_leer_jsonl(dir_corpus() / "secciones.jsonl"))


@functools.lru_cache(maxsize=1)
def cargar_xbrl() -> pd.DataFrame:
    return pd.read_parquet(dir_corpus() / "xbrl_facts.parquet")


@functools.lru_cache(maxsize=1)
def cargar_chunks() -> list[dict]:
    return _leer_jsonl(dir_corpus() / "chunks.jsonl")
