"""Un solo agente, con interruptor de mejoras.

`construir_agente(mejoras=False)` es el del día 10. `mejoras=True` le
añadirá middleware y retrieval mejorado; hoy el interruptor existe y no
cambia el comportamiento, para que baseline y final sean el mismo código.
"""

from __future__ import annotations

import functools

from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from agente.esquema import RespuestaFinanciera
from agente.herramientas import construir_herramientas
from agente.middleware import middlewares_mejoras

MODELO = "openrouter:google/gemini-3.8-flash"

SYSTEM = """Eres un analista financiero que responde preguntas sobre informes
10-K usando ÚNICAMENTE las herramientas disponibles.

Reglas:
- Para cualquier CIFRA, usa get_xbrl_fact. Nunca leas un número de la prosa.
- Para riesgos, estrategia o comentarios de la dirección, usa search_filings.
- Si no sabes si una compañía o un ejercicio están en el corpus, empieza por
  list_available.
- El corpus está en inglés: escribe las consultas de búsqueda en inglés.
- Cita el chunk_id del fragmento en el que te apoyes.
- Si el dato no está en el corpus, dilo. No lo estimes.
"""


@functools.lru_cache(maxsize=4)
def construir_agente(modelo: str = MODELO, mejoras: bool = False):
    """El agente del día 10 (`mejoras=False`) o el sistema final."""
    kwargs: dict = {
        "model": modelo,
        "tools": construir_herramientas(),
        "system_prompt": SYSTEM,
        "response_format": RespuestaFinanciera,
        "checkpointer": InMemorySaver(),
    }
    if mejoras:
        kwargs["middleware"] = middlewares_mejoras()
    return create_agent(**kwargs)
