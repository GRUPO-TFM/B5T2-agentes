"""Fixtures compartidas. Ningún test de esta carpeta llama a la API."""
from __future__ import annotations

import json

import pytest

from agente.corpus import cargar_chunks, cargar_xbrl, raiz_repo


@pytest.fixture(scope="session")
def golden() -> list[dict]:
    ruta = raiz_repo() / "data" / "golden_set.jsonl"
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


@pytest.fixture(scope="session")
def chunks_por_id() -> dict:
    return {c["chunk_id"]: c for c in cargar_chunks()}


@pytest.fixture(scope="session")
def xbrl():
    return cargar_xbrl()


def resultado_falso(*, cifra=None, unidad="USD", ticker=None, ejercicio=None, fuente="ninguna",
                    cita=None, chunk_id=None, herramientas=(), respuesta="…") -> dict:
    """Un resultado ya normalizado, como el que se guarda en disco."""
    return {
        "_normalizado": True,
        "structured_response": {"respuesta": respuesta, "cifra": cifra, "unidad": unidad,
                                "ticker": ticker, "ejercicio": ejercicio, "fuente": fuente,
                                "cita": cita, "chunk_id": chunk_id},
        "herramientas": list(herramientas), "llamadas": [{"name": h, "args": {}} for h in herramientas],
        "n_llamadas": len(herramientas), "tokens_in": 100, "tokens_out": 50,
        "coste_usd": 0.001, "latencia_s": 1.0, "limite_alcanzado": False, "correcciones": [],
        "messages": [], "modelo": "test", "arquitectura": "test",
    }
