"""Los tres evaluadores del §4.5, más el acierto agregado.

Firma común: `(item_del_golden_set, resultado)` → `True`, `False` o `None`
(no aplica). `resultado` puede ser lo que devuelve `responder()` o el dict
plano guardado en disco: los dos pasan por `normalizar_resultado`.

| Evaluador               | Qué comprueba                                              | Qué error caza                       |
|-------------------------|------------------------------------------------------------|--------------------------------------|
| cita_correcta           | el chunk_id existe, es del documento correcto y contiene la cita | citas inventadas o de otro año  |
| cifra_coincide_xbrl     | la cifra coincide con la esperada dentro de la tolerancia  | cifras leídas de la prosa o estimadas|
| uso_la_tool_correcta    | la trayectoria pasó por TODAS las herramientas esperadas   | acertar por el camino equivocado     |

El tercero es el que enseña la lección del curso: una numérica que acierta el
número sin pasar por get_xbrl_fact suspende. Ese acierto no generaliza.
"""

from __future__ import annotations

import functools

from agente.metricas import TOLERANCIA, cuadra, normalizar
from agente.resultado import normalizar_resultado

_LONGITUD_CITA = 120


@functools.lru_cache(maxsize=1)
def _chunks_por_id() -> dict:
    from agente.corpus import cargar_chunks
    return {c["chunk_id"]: c for c in cargar_chunks()}


def _sr(resultado) -> dict | None:
    return normalizar_resultado(resultado).get("structured_response")


# ---------------------------------------------------------------------------
def cita_correcta(item: dict, resultado) -> bool | None:
    """Aplica a los ítems con `ancla_texto` (extractivas y comparativas).

    False si: no hay respuesta estructurada, no hay chunk_id, el chunk_id no
    existe, es de otro ticker/ejercicio, no hay cita, o la cita (primeros 120
    caracteres normalizados) no aparece en el texto del fragmento.
    """
    if not item.get("ancla_texto"):
        return None
    sr = _sr(resultado)
    if not sr or not sr.get("chunk_id"):
        return False
    fragmento = _chunks_por_id().get(sr["chunk_id"])
    if fragmento is None:
        return False                                   # se lo inventó
    if item.get("ticker") and fragmento.get("ticker") != item["ticker"]:
        return False                                   # otra compañía
    if item.get("fiscal_year") is not None \
            and int(fragmento.get("fiscal_year", -1)) != int(item["fiscal_year"]):
        return False                                   # otro ejercicio
    cita = sr.get("cita")
    if not cita:
        return False
    objetivo = normalizar(cita)[:_LONGITUD_CITA]
    return bool(objetivo) and objetivo in normalizar(fragmento["texto"])


def cifra_coincide_xbrl(item: dict, resultado) -> bool | None:
    """Aplica a los ítems con `cifra_esperada`. Tolerancia relativa del 1 %."""
    esperada = item.get("cifra_esperada")
    if esperada is None:
        return None
    sr = _sr(resultado)
    if not sr or sr.get("cifra") is None:
        return False                                   # no dio cifra, o dijo "ninguna"
    try:
        return cuadra(float(sr["cifra"]), float(esperada), TOLERANCIA)
    except (TypeError, ValueError):
        return False


def uso_la_tool_correcta(item: dict, resultado) -> bool | None:
    """La trayectoria pasó por TODAS las herramientas esperadas."""
    esperadas = item.get("herramienta_esperada") or []
    if not esperadas:
        return None
    usadas = set(normalizar_resultado(resultado).get("herramientas", []))
    return set(esperadas).issubset(usadas)


def honestidad(item: dict, resultado) -> bool | None:
    """Extensión propia. Solo aplica si el ítem declara `fuente_esperada`
    (por ejemplo "ninguna" en una pregunta cuyo dato no está en el corpus)."""
    esperada = item.get("fuente_esperada")
    if not esperada:
        return None
    sr = _sr(resultado)
    return bool(sr) and sr.get("fuente") == esperada


EVALUADORES = {
    "cita": cita_correcta,
    "cifra": cifra_coincide_xbrl,
    "trayectoria": uso_la_tool_correcta,
    "honestidad": honestidad,
}


def acierto(veredictos: dict) -> bool | None:
    """Acierto global: todos los evaluadores APLICABLES en True. None si ninguno aplica."""
    aplicables = [v for k, v in veredictos.items() if k in EVALUADORES and v is not None]
    if not aplicables:
        return None
    return all(aplicables)
