# -*- coding: utf-8 -*-
"""Reescritura de la consulta al inglés, una sola vez y en caché.

Las preguntas están en español y el corpus en inglés. Ese desajuste pesa
mucho más que el troceado: sin filtros, el ancla del baseline aparece en la
posición 259, 576 o 1020. Si no se controla, tapa el efecto que se quiere
medir.

La reescritura se hace **una vez**, se guarda en `cache_consultas.json`
(versionado) y ninguna variante vuelve a llamar al modelo: las cinco ven
exactamente la misma consulta, que es la única forma de que la comparación
mida el troceado y no la lotería del LLM.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

CACHE = Path(__file__).resolve().parent / "cache_consultas.json"

INSTRUCCION = (
    "You rewrite Spanish questions about SEC 10-K filings into English "
    "search queries for a dense retriever over the filing text. Reply with "
    "the query only: no quotes, no explanation, no preamble. Keep tickers, "
    "fiscal years and figures. Prefer the wording a 10-K would use."
)


def cargar_cache() -> dict[str, str]:
    if CACHE.is_file():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    return {}


def guardar_cache(cache: dict[str, str]) -> None:
    CACHE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def reescribir(golden: list[dict], modelo: str | None = None) -> dict[str, str]:
    """Rellena la caché con lo que falte. No toca lo ya guardado."""
    from agente.agente import MODELO

    cache = cargar_cache()
    pendientes = [g for g in golden if g.get("ancla_texto") and g["id"] not in cache]
    if not pendientes:
        return cache

    if not os.environ.get("OPENROUTER_API_KEY"):
        from dotenv import load_dotenv

        load_dotenv()
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise RuntimeError(
            "Falta OPENROUTER_API_KEY: es lo único que necesita el modo de "
            "consulta reescrita. El modo de consulta original no la usa."
        )

    from langchain.chat_models import init_chat_model

    llm = init_chat_model(modelo or MODELO)
    for g in pendientes:
        respuesta = llm.invoke(
            [("system", INSTRUCCION), ("human", g["pregunta"])]
        )
        cache[g["id"]] = respuesta.content.strip().strip('"')
    guardar_cache(cache)
    return cache


if __name__ == "__main__":
    from experimentos.chunking.evaluar import cargar_golden

    cache = reescribir(cargar_golden())
    for k in sorted(cache):
        print(f"{k}  {cache[k]}")
