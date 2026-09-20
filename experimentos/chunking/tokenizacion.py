# -*- coding: utf-8 -*-
"""Contadores de tokens.

Dos tokenizadores, y conviene no confundirlos:

- `cl100k_base` (tiktoken) es **el que usó el troceado entregado**. Se
  descubrió por reconstrucción: coincide 60/60 con el campo `n_tokens` de
  `chunks.jsonl`. Solo se usa para pasar la puerta de reproducción.
- El tokenizador de `BAAI/bge-small-en-v1.5` es **el que de verdad importa**,
  porque es el que ve el modelo de embeddings. Su límite de entrada es 512 y
  trunca sin avisar: 308 de los 1.749 fragmentos entregados (17,6 %) se
  embeben cortados.

Por eso las variantes nuevas se trocean contando con BGE y con un tope duro
por debajo de 512.
"""

from __future__ import annotations

import functools

MODELO_EMBEDDINGS = "BAAI/bge-small-en-v1.5"

# 512 es el límite del modelo, pero [CLS] y [SEP] ocupan dos posiciones, así
# que el texto útil son 510. El tope duro deja un margen adicional para que
# ninguna variante roce el truncado.
LIMITE_MODELO = 512
TOPE_DURO = 480


@functools.lru_cache(maxsize=1)
def _cl100k():
    import tiktoken

    return tiktoken.get_encoding("cl100k_base")


@functools.lru_cache(maxsize=1)
def _bge():
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(MODELO_EMBEDDINGS)


def contar_cl100k(texto: str) -> int:
    return len(_cl100k().encode(texto))


def contar_bge(texto: str) -> int:
    """Tokens del texto **sin** los especiales. Suma 2 para el límite real."""
    return len(_bge().encode(texto, add_special_tokens=False))


def trocear_por_tokens_cl100k(texto: str, ventana: int, solape: int):
    """Ventanas sobre los tokens de cl100k, devueltas como (ini_car, fin_car).

    Los offsets se recuperan decodificando el prefijo, que es exacto porque
    la decodificación de cl100k es reversible byte a byte.
    """
    enc = _cl100k()
    ids = enc.encode(texto)
    if len(ids) <= ventana:
        return [(0, len(texto))]
    paso = ventana - solape
    tramos = []
    for i in range(0, len(ids), paso):
        trozo = ids[i : i + ventana]
        if not trozo:
            break
        ini = len(enc.decode(ids[:i]))
        fin = ini + len(enc.decode(trozo))
        tramos.append((ini, fin))
        if i + ventana >= len(ids):
            break
    return tramos


def trocear_por_tokens_bge(texto: str, ventana: int, solape: int):
    """Lo mismo con el tokenizador de BGE, usando `offset_mapping`.

    BGE es WordPiece: decodificar no reconstruye el texto original (se come
    espacios y marca subpalabras con `##`), así que los offsets salen del
    mapeo que da el propio tokenizador, no de la decodificación.
    """
    tk = _bge()
    cod = tk(texto, add_special_tokens=False, return_offsets_mapping=True)
    offsets = cod["offset_mapping"]
    if len(offsets) <= ventana:
        return [(0, len(texto))]
    paso = ventana - solape
    tramos = []
    for i in range(0, len(offsets), paso):
        trozo = offsets[i : i + ventana]
        if not trozo:
            break
        tramos.append((trozo[0][0], trozo[-1][1]))
        if i + ventana >= len(offsets):
            break
    return tramos
