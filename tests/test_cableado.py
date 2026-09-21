"""El flag `mejoras` llega a las herramientas y a `buscar`."""

from agente.agente import construir_agente
from agente.herramientas import construir_herramientas


def test_construir_agente_pasa_mejoras_a_las_herramientas(monkeypatch):
    visto = {}

    def fake_herramientas(*, mejoras=False, reescritor=None):
        visto["mejoras"] = mejoras
        return []

    monkeypatch.setattr("agente.agente.construir_herramientas", fake_herramientas)
    monkeypatch.setattr("agente.agente.create_agent", lambda **kwargs: kwargs)

    construir_agente.cache_clear()
    resultado = construir_agente(mejoras=True)
    assert visto["mejoras"] is True
    assert "middleware" in resultado

    construir_agente.cache_clear()
    construir_agente(mejoras=False)
    assert visto["mejoras"] is False
    construir_agente.cache_clear()


def test_search_filings_propaga_mejoras_sin_cambiar_su_firma(monkeypatch):
    visto = {}

    def fake_buscar(query, ticker=None, fiscal_year=None, item=None, k=5,
                    *, mejoras=False, reescritor=None, rrf_k=60):
        visto.update({
            "query": query,
            "mejoras": mejoras,
            "reescritor": reescritor,
            "k": k,
        })
        return []

    monkeypatch.setattr("agente.herramientas.buscar", fake_buscar)
    monkeypatch.setattr("agente.herramientas.cargar_secciones", lambda: None)
    monkeypatch.setattr("agente.herramientas.cargar_xbrl", lambda: None)

    def reescritor(q: str) -> str:
        return "rewritten " + q

    tools = construir_herramientas(mejoras=True, reescritor=reescritor)
    search = next(t for t in tools if t.name == "search_filings")
    search.invoke({"query": "riesgo cambiario"})
    assert visto["query"] == "riesgo cambiario"
    assert visto["mejoras"] is True
    assert visto["reescritor"] is reescritor

    tools_base = construir_herramientas(mejoras=False)
    search_base = next(t for t in tools_base if t.name == "search_filings")
    search_base.invoke({"query": "riesgo cambiario"})
    assert visto["mejoras"] is False
    assert visto["reescritor"] is None
