"""Reescritura de consultas para un índice de informes 10-K en inglés.

Aislada del retrieval para poder inyectar un reescritor en tests, sin
red ni credenciales. Si el modelo no está, falla la llamada o la
respuesta llega vacía, se devuelve la query original.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

INSTRUCCION = """Reescribe esta pregunta como una consulta de búsqueda breve
para un índice de informes 10-K en INGLÉS. Usa el vocabulario del propio
informe (por ejemplo: revenue increased, net sales, risk factors, export
controls, effective tax rate). Conserva literalmente tickers, años fiscales,
importes, porcentajes, nombres propios y términos regulatorios.
Devuelve SOLO la consulta, sin comillas ni explicación."""

# Solo reescrituras no vacías. Una query fallida no se cachea, para
# poder recuperarse si el modelo vuelve a estar disponible.
_CACHE: dict[str, str] = {}
_ULTIMO_USO: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}


def _texto_de(respuesta: Any) -> str:
    texto = getattr(respuesta, "text", None)
    if texto is None:
        texto = getattr(respuesta, "content", "")
    if isinstance(texto, list):
        partes = []
        for bloque in texto:
            if isinstance(bloque, str):
                partes.append(bloque)
            elif isinstance(bloque, dict):
                partes.append(str(bloque.get("text", "")))
            else:
                partes.append(str(getattr(bloque, "text", "")))
        texto = "".join(partes)
    limpio = str(texto).strip()
    if len(limpio) >= 2 and limpio[0] == limpio[-1] and limpio[0] in {'"', "'"}:
        limpio = limpio[1:-1].strip()
    return limpio


@functools.lru_cache(maxsize=1)
def _llm():
    from langchain.chat_models import init_chat_model

    from agente.agente import MODELO

    return init_chat_model(MODELO, temperature=0)


def _reescribir_con_llm(query: str) -> str:
    if query in _CACHE:
        _ULTIMO_USO["input_tokens"] = 0
        _ULTIMO_USO["output_tokens"] = 0
        return _CACHE[query]
    respuesta = _llm().invoke(
        [
            {"role": "system", "content": INSTRUCCION},
            {"role": "user", "content": query},
        ]
    )
    uso = getattr(respuesta, "usage_metadata", None) or {}
    _ULTIMO_USO["input_tokens"] = int(uso.get("input_tokens") or 0)
    _ULTIMO_USO["output_tokens"] = int(uso.get("output_tokens") or 0)
    salida = _texto_de(respuesta)
    if salida:
        _CACHE[query] = salida
    return salida


def ultimo_uso() -> dict[str, int]:
    """Tokens de la última llamada real al LLM (0 si salió de caché)."""
    return dict(_ULTIMO_USO)


def borrar_cache() -> None:
    """Para tests: no arrastrar reescrituras entre casos."""
    _CACHE.clear()
    _ULTIMO_USO["input_tokens"] = 0
    _ULTIMO_USO["output_tokens"] = 0
    _llm.cache_clear()


def reescribir(
    query: str,
    reescritor: Callable[[str], str] | None = None,
) -> str:
    """Consulta breve en inglés. Si falla, `query` intacta."""
    try:
        if reescritor is not None:
            salida = reescritor(query)
        else:
            salida = _reescribir_con_llm(query)
    except Exception:
        return query
    if not salida or not str(salida).strip():
        return query
    return str(salida).strip()
