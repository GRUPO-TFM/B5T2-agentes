"""Evaluadores de cita, cifra y trayectoria.

Vacío hasta el paso 3. Las firmas ya son las que usará `evaluar()`: cada
función recibe el ítem del golden set y el resultado de `responder()`, y
devuelve True/False o None si el criterio no aplica.
"""

from __future__ import annotations


def cita_correcta(item: dict, resultado: dict) -> bool | None:
    return None


def cifra_coincide_xbrl(item: dict, resultado: dict) -> bool | None:
    return None


def uso_la_tool_correcta(item: dict, resultado: dict) -> bool | None:
    return None


EVALUADORES = {
    "cita": cita_correcta,
    "cifra": cifra_coincide_xbrl,
    "trayectoria": uso_la_tool_correcta,
}
