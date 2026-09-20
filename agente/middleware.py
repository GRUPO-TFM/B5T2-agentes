"""Middleware del agente.

Vacío hasta el paso 5: verificador de cifras contra XBRL y límites de
llamadas. `construir_agente(mejoras=True)` engancha lo que devuelva
`middlewares_mejoras()`.
"""

from __future__ import annotations


def middlewares_mejoras() -> list:
    """Los middleware que se activan con `construir_agente(mejoras=True)`."""
    return []
