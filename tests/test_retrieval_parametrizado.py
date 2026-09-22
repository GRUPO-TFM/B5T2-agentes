"""construir_herramientas(reescritura=, hibrido=, k=) y el recall sobre trazas.

Sin API y sin codificador: la búsqueda densa se sustituye por una falsa que
devuelve fragmentos reales del corpus (filtrados) — lo que se prueba aquí es
el CABLEADO: qué retriever se llama, con qué consulta, y qué ve el modelo.
La integración con el FAISS real corre solo si el codificador está en caché.
"""
import json

import pytest

from agente import herramientas as mod_herramientas
from agente import recall
from agente.corpus import cargar_chunks
from agente.herramientas import construir_herramientas, formatear_valor


def _tool(hs, nombre):
    return next(t for t in hs if t.name == nombre)


def _busqueda_falsa(registro: list):
    """Filtra los chunks reales por metadatos y devuelve los k primeros; si la
    consulta contiene un trozo del texto de un chunk, ese va el primero.
    Apunta cada llamada en `registro`."""
    chunks = cargar_chunks()

    def fn(consulta, ticker=None, fiscal_year=None, item=None, k=None, **_):
        registro.append({"consulta": consulta, "ticker": ticker, "fiscal_year": fiscal_year,
                         "item": item, "k": k})
        cand = [c for c in chunks
                if (not ticker or c["ticker"] == ticker)
                and (not fiscal_year or int(c["fiscal_year"]) == int(fiscal_year))
                and (not item or c["item"] == item)]
        cand.sort(key=lambda c: 0 if consulta[:40] and consulta[:40] in c["texto"] else 1)
        out = [{**{kk: c.get(kk) for kk in ("chunk_id", "ticker", "fiscal_year", "item", "texto",
                                            "inicio_car", "fin_car")}, "puntuacion": 0.5}
               for c in cand]
        return out if k is None else out[:k]
    return fn


@pytest.fixture
def busqueda(monkeypatch):
    llamadas: list = []
    fn = _busqueda_falsa(llamadas)
    monkeypatch.setattr(mod_herramientas, "buscar", fn)      # camino denso de la herramienta
    monkeypatch.setattr(recall, "con_filtros", fn)           # camino denso del recall
    monkeypatch.setattr(recall, "hibrido", fn)               # camino híbrido (mismo falso, se
    return llamadas                                          #   distingue por quién lo llama)


def test_por_defecto_es_el_agente_del_dia_10(busqueda):
    hs = construir_herramientas()
    assert [t.name for t in hs] == ["list_available", "get_xbrl_fact", "search_filings", "read_section"]
    salida = _tool(hs, "search_filings").invoke({"query": "export controls", "ticker": "NVDA",
                                                 "fiscal_year": 2025, "item": "1A"})
    assert salida.startswith("[NVDA-2025-1A-")
    assert "(consulta reescrita" not in salida
    assert busqueda[-1]["consulta"] == "export controls" and busqueda[-1]["k"] == 5


def test_get_xbrl_fact_no_redondea_el_eps():
    hs = construir_herramientas()
    salida = _tool(hs, "get_xbrl_fact").invoke({"ticker": "NVDA", "fiscal_year": 2025,
                                                "concept": "EarningsPerShareDiluted"})
    assert "= 2.94 " in salida                            # antes: «= 3 USD/shares»
    salida = _tool(hs, "get_xbrl_fact").invoke({"ticker": "NVDA", "fiscal_year": 2025,
                                                "concept": "Revenues"})
    assert "= 130,497,000,000 " in salida                 # los dólares siguen sin decimales


def test_la_reescritura_se_ve_en_el_toolmessage(busqueda, monkeypatch):
    monkeypatch.setattr(recall, "reescribir_consulta",
                        lambda q, modelo=None: "export controls Item 1A risk factors")
    hs = construir_herramientas(reescritura=True)
    salida = _tool(hs, "search_filings").invoke({"query": "controles de exportación",
                                                 "ticker": "NVDA", "fiscal_year": 2025, "item": "1A"})
    assert salida.startswith("(consulta reescrita: 'export controls Item 1A risk factors')")
    assert "[NVDA-2025-1A-" in salida
    assert busqueda[-1]["consulta"] == "export controls Item 1A risk factors"   # busca la reescrita

    # si la reescritura no cambia nada, no se ensucia el mensaje
    monkeypatch.setattr(recall, "reescribir_consulta", lambda q, modelo=None: q)
    hs = construir_herramientas(reescritura=True)
    salida = _tool(hs, "search_filings").invoke({"query": "export controls", "ticker": "NVDA",
                                                 "fiscal_year": 2025, "item": "1A"})
    assert not salida.startswith("(consulta reescrita")


def test_el_hibrido_usa_el_retriever_hibrido_y_el_k_de_la_arquitectura(busqueda, monkeypatch):
    marcador = []
    fn = _busqueda_falsa(busqueda)
    monkeypatch.setattr(recall, "hibrido", lambda *a, **kw: (marcador.append("hibrido"), fn(*a, **kw))[1])
    hs = construir_herramientas(hibrido=True, k=3)
    # SIN pasar k: es el caso real (el modelo casi nunca lo manda). Antes la
    # firma decía `k: int = 5` y el k de la arquitectura nunca se aplicaba.
    salida = _tool(hs, "search_filings").invoke({"query": "export controls", "ticker": "NVDA",
                                                 "fiscal_year": 2025, "item": "1A"})
    assert marcador == ["hibrido"]
    ids = [l.split("]")[0][1:] for l in salida.split("\n") if l.startswith("[NVDA-2025-1A-")]
    assert len(ids) == 3
    assert _tool(hs, "search_filings").args["k"]["default"] == 3     # y el esquema que ve el modelo lo dice
    # el modelo puede pedir otro k, y k=0 cae al de la arquitectura
    salida = _tool(hs, "search_filings").invoke({"query": "export controls", "ticker": "NVDA",
                                                 "fiscal_year": 2025, "item": "1A", "k": 2})
    assert len([l for l in salida.split("\n") if l.startswith("[NVDA-2025-1A-")]) == 2
    salida = _tool(hs, "search_filings").invoke({"query": "export controls", "ticker": "NVDA",
                                                 "fiscal_year": 2025, "item": "1A", "k": 0})
    assert len([l for l in salida.split("\n") if l.startswith("[NVDA-2025-1A-")]) == 3


def test_formatear_valor():
    assert formatear_valor(2.94, "USD/shares") == "2.94"
    assert formatear_valor(130_497_000_000, "USD") == "130,497,000,000"


def test_contador_de_busquedas_reescritas():
    from agente.interfaz import _busquedas_reescritas
    msgs = [{"type": "tool", "name": "search_filings", "content": "(consulta reescrita: 'x')\n\n[A]"},
            {"type": "tool", "name": "search_filings", "content": "[B] ..."},
            {"type": "tool", "name": "get_xbrl_fact", "content": "(consulta reescrita: no cuenta"}]
    assert _busquedas_reescritas(msgs) == 1


def test_recall_de_trazas_usa_las_consultas_del_agente(tmp_path, monkeypatch, busqueda):
    """Dos trazas falsas de gX-007: una búsqueda que no encuentra el ancla y
    otra que sí. «Cualquiera de sus búsquedas» -> recall 1/1. Y una pregunta
    en la que el agente no buscó no entra en el denominador."""
    from agente import interfaz
    monkeypatch.setattr(interfaz, "dir_resultados", lambda: tmp_path / "resultados")
    golden = {g["id"]: g for g in interfaz.leer_golden("data/golden_set.jsonl")}
    it = golden["gX-007"]
    for rep, query in ((1, "zzzz qqqq nothing relevant"), (2, it["ancla_texto"])):
        carpeta = tmp_path / "resultados" / "agente" / "a1_guardrails" / f"rep{rep}" / "crudo"
        carpeta.mkdir(parents=True)
        (carpeta / "gX-007.json").write_text(json.dumps({
            "item": it, "rep": rep, "thread_id": "t",
            "resultado": {"llamadas": [{"name": "search_filings",
                                        "args": {"query": query, "ticker": it["ticker"],
                                                 "fiscal_year": it["fiscal_year"], "item": "1A"}}]},
        }), encoding="utf-8")
    (tmp_path / "resultados" / "agente" / "a1_guardrails" / "rep1" / "crudo" / "gX-013.json").write_text(
        json.dumps({"item": golden["gX-013"], "rep": 1, "thread_id": "t",
                    "resultado": {"llamadas": [{"name": "get_xbrl_fact", "args": {}}]}}), encoding="utf-8")

    consultas = recall.consultas_del_agente("a1_guardrails")
    assert len(consultas["gX-007"]) == 2 and "gX-013" not in consultas

    tabla = recall.recall_de_trazas("a1_guardrails", escribir=False, verbose=False,
                                    configs={"denso + filtros del agente": recall._buscador(False, False),
                                             "+ híbrido BM25": recall._buscador(False, True)})
    assert list(tabla["aciertos"]) == ["1/1", "1/1"]


def _hay_codificador() -> bool:
    try:
        import os
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        from agente.retrieval import _indice
        _indice()
        return True
    except Exception:                                       # noqa: BLE001
        return False


@pytest.mark.skipif(not _hay_codificador(), reason="codificador de embeddings no disponible en caché")
def test_integracion_hibrido_real_respeta_filtros():
    hs = construir_herramientas(hibrido=True, k=3)
    salida = _tool(hs, "search_filings").invoke({"query": "export controls licensing",
                                                 "ticker": "NVDA", "fiscal_year": 2025, "item": "1A"})
    ids = [l.split("]")[0][1:] for l in salida.split("\n") if l.startswith("[")]
    assert len(ids) == 3 and all(i.startswith("NVDA-2025-1A-") for i in ids)
