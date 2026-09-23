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


def _acepta_ninguna(item: dict) -> bool:
    fe = item.get("fuente_esperada")
    return isinstance(fe, list) and "ninguna" in fe


def cifra_coincide_xbrl(item: dict, resultado) -> bool | None:
    """Aplica a los ítems con `cifra_esperada`. Tolerancia relativa del 1 %.

    Extensión del golden adversario (v2), inerte en el original:
    - `cifras_aceptables`: lista de cifras válidas. En una pregunta
      multi-entidad hay dos convenciones defendibles —la magnitud derivada
      (el diferencial) o el valor XBRL de la ganadora, que es lo que manda el
      prompt del agente— y se aceptan las dos.
    - `fuente_esperada` como lista con "ninguna": si el agente respondió
      "ninguna" (honestidad parcial), la cifra no aplica.
    """
    esperadas = item.get("cifras_aceptables") or (
        [item["cifra_esperada"]] if item.get("cifra_esperada") is not None else [])
    if not esperadas:
        return None
    sr = _sr(resultado)
    if sr and sr.get("fuente") == "ninguna" and _acepta_ninguna(item):
        return None
    if not sr or sr.get("cifra") is None:
        return False                                   # no dio cifra, o dijo "ninguna"
    try:
        return any(cuadra(float(sr["cifra"]), float(e), TOLERANCIA) for e in esperadas)
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
    (por ejemplo "ninguna" en una pregunta cuyo dato no está en el corpus).
    Puede ser una lista de fuentes válidas (honestidad parcial, gY-010)."""
    esperada = item.get("fuente_esperada")
    if not esperada:
        return None
    sr = _sr(resultado)
    validas = esperada if isinstance(esperada, list) else [esperada]
    return bool(sr) and sr.get("fuente") in validas


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
