"""Un solo agente, con la arquitectura como parámetro.

`construir_agente("baseline")` es el agente del día 10. `construir_agente("a1_guardrails")`
es el mismo código con los guardrails enchufados, y así hasta `"final"`. Ver
`agente/config.py` para lo que enciende cada nivel.

Todo lo que cambia entre niveles pasa por aquí: prompt, esquema, middleware y
las opciones del retrieval. Nada más. Así baseline y final son el mismo código
y la comparación del informe no arrastra diferencias accidentales.
"""

from __future__ import annotations

import functools

from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from agente.config import MODELO, Arquitectura, arquitectura
from agente.esquema import RespuestaFinanciera, RespuestaFinancieraEstricta
from agente.herramientas import construir_herramientas
from agente.middleware import middlewares_para
from agente.prompts import PROMPTS

SYSTEM = PROMPTS["base"]        # compatibilidad con el nombre anterior


def _herramientas(arq: Arquitectura) -> list:
    """Las cuatro herramientas. Cuando el retrieval mejorado (híbrido,
    reescritura) entre en `agente/retrieval.py`, se le pasan aquí las opciones
    de la arquitectura; hoy `construir_herramientas()` no acepta argumentos y
    los niveles a2/a3 usan el retrieval denso con filtros del día 10."""
    try:
        return construir_herramientas(reescritura=arq.reescritura,
                                      hibrido=arq.hibrido, k=arq.k)
    except TypeError:               # firma antigua, sin opciones
        return construir_herramientas()


@functools.lru_cache(maxsize=8)
def _construir(modelo: str, nombre: str):
    arq = arquitectura(nombre)
    esquema = RespuestaFinancieraEstricta if arq.esquema_estricto else RespuestaFinanciera
    kwargs: dict = {
        "model": modelo,
        "tools": _herramientas(arq),
        "system_prompt": PROMPTS[arq.prompt],
        "response_format": esquema,
        "checkpointer": InMemorySaver(),
    }
    middleware = middlewares_para(arq)
    if middleware:
        kwargs["middleware"] = middleware
    return create_agent(**kwargs)


def construir_agente(modelo: str = MODELO,
                     mejoras: bool | None = None,
                     arquitectura: str | Arquitectura = "baseline"):
    """El agente de una arquitectura. `mejoras=True` es un alias de "final"
    que se mantiene por compatibilidad con el código anterior."""
    if mejoras is True:
        arquitectura = "final"
    nombre = arquitectura if isinstance(arquitectura, str) else arquitectura.nombre
    return _construir(modelo, nombre)
