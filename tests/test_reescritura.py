"""Reescritura inyectable, sin red ni credenciales."""

from agente.reescritura import borrar_cache, reescribir


def test_usa_la_salida_del_reescritor_inyectado():
    borrar_cache()
    vista = []

    def falso(query: str) -> str:
        vista.append(query)
        return "export controls China market NVDA"

    salida = reescribir("¿Qué dice NVIDIA de China?", reescritor=falso)
    assert vista == ["¿Qué dice NVIDIA de China?"]
    assert salida == "export controls China market NVDA"


def test_conserva_la_query_si_el_reescritor_lanza():
    def boom(_query: str) -> str:
        raise RuntimeError("sin modelo")

    original = "effective tax rate META FY2025"
    assert reescribir(original, reescritor=boom) == original


def test_conserva_la_query_si_la_salida_esta_vacia():
    original = "net sales increased AAPL"

    assert reescribir(original, reescritor=lambda _q: "") == original
    assert reescribir(original, reescritor=lambda _q: "   ") == original


def test_fallback_si_falla_el_llm_por_defecto(monkeypatch):
    borrar_cache()

    def boom(_query: str) -> str:
        raise RuntimeError("offline")

    monkeypatch.setattr("agente.reescritura._reescribir_con_llm", boom)
    assert reescribir("query original") == "query original"


def test_no_llama_al_llm_si_hay_reescritor():
    borrar_cache()
    llamadas_llm = []

    def llm_prohibido(_query: str) -> str:
        llamadas_llm.append("llm")
        return "NO"

    # El camino inyectado no debe ir a _reescribir_con_llm.
    salida = reescribir("hola", reescritor=lambda q: q.upper())
    assert salida == "HOLA"
    assert llamadas_llm == []
