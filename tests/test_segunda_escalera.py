"""A5 y A6: la segunda escalera, sin API.

A5 límite por herramienta · A6 contrato y verificador para cifras que solo
están en el texto. La reescritura con razonamiento mínimo se midió y se
descartó (no baja la latencia); su código se conserva y se sigue probando.
"""
import json
import sys
import types

import pytest

from agente import recall
from agente.config import ARQUITECTURAS
from agente.middleware import (cifras_de_la_cita, limites, middlewares_para,
                               verificar_cifras_con_texto, verificar_cifras_contra_xbrl)
from agente.prompts import PROMPTS


class _SR:
    def __init__(self, **kw):
        self.__dict__.update({"cifra": None, "unidad": "USD", "ticker": None, "ejercicio": None,
                              "fuente": "ninguna", "cita": None, "chunk_id": None, **kw})


def _estado(sr, mensajes=()):
    return {"structured_response": sr, "messages": list(mensajes)}


CITA_GOOGL = ("A hypothetical adverse price change of 10% on our December 31, 2025 balance would "
              "decrease the fair value of marketable equity securities by $631 million.")


# --- la escalera ------------------------------------------------------------
def test_la_segunda_escalera_es_acumulativa_y_final_no_cambia():
    orden = ["a4_comparativas", "a5_limites", "a6_cifras_texto"]
    booleanos = ["limites", "verificador_cifras", "verificador_cita", "esquema_estricto",
                 "filtros_forzados", "reescritura", "hibrido", "limites_por_herramienta",
                 "reescritura_rapida", "cifras_de_texto"]
    previo = ARQUITECTURAS[orden[0]].como_dict()
    for nombre in orden[1:]:
        actual = ARQUITECTURAS[nombre].como_dict()
        for b in booleanos:
            assert actual[b] >= previo[b], f"{nombre} apaga {b}"
        # un cambio por peldaño: exactamente un booleano nuevo encendido
        nuevos = [b for b in booleanos if actual[b] and not previo[b]]
        assert len(nuevos) == 1, (nombre, nuevos)
        previo = actual
    # lo que corre evaluar() mañana no cambia hasta medir
    assert ARQUITECTURAS["final"].nombre == "a4_comparativas"
    # el experimento descartado no está en la escalera
    assert "x_reescritura_rapida" not in ARQUITECTURAS
    from agente.config import X_REESCRITURA_RAPIDA
    assert X_REESCRITURA_RAPIDA.reescritura_rapida and not ARQUITECTURAS["a6_cifras_texto"].reescritura_rapida


# --- A5 ---------------------------------------------------------------------
def test_a5_pone_un_techo_por_herramienta():
    nombres = lambda arq: sorted(m.name for m in limites(arq))
    a4 = nombres(ARQUITECTURAS["a4_comparativas"])
    a5 = nombres(ARQUITECTURAS["a5_limites"])
    assert not any("get_xbrl_fact" in n or "search_filings" in n for n in a4)
    assert any("[get_xbrl_fact]" in n for n in a5) and any("[search_filings]" in n for n in a5)
    assert any("[read_section]" in n for n in a5)
    assert len(set(a5)) == len(a5)                       # nombres únicos: LangChain lo exige
    arq = ARQUITECTURAS["a5_limites"]
    # la pregunta de las seis compañías (13 llamadas XBRL + list_available) cabe
    assert arq.max_xbrl >= 13 and arq.max_llamadas >= 14
    # lo medido en A4 sobre el original (hasta 6 búsquedas) sigue cabiendo
    assert arq.max_busquedas >= 6


def test_a5_el_limite_de_xbrl_bloquea_solo_xbrl():
    arq = ARQUITECTURAS["a5_limites"]
    mw = next(m for m in limites(arq) if m.name.endswith("[get_xbrl_fact]"))
    assert mw._matches_tool_filter({"name": "get_xbrl_fact", "args": {}, "id": "1"})
    assert not mw._matches_tool_filter({"name": "search_filings", "args": {}, "id": "2"})


# --- A6 ---------------------------------------------------------------------
def _modelo_falso(registro, texto="rewritten query", fallar=()):
    class _Resp:
        def __init__(self, t): self.text = t

    def init_chat_model(modelo, **kw):
        registro.append(kw)
        esfuerzo = (kw.get("reasoning") or {}).get("effort")
        if esfuerzo in fallar:
            raise ValueError(f"effort {esfuerzo} no soportado")

        class _M:
            def invoke(self, _): return _Resp(texto)
        return _M()
    mod = types.ModuleType("langchain.chat_models")
    mod.init_chat_model = init_chat_model
    return mod


def test_rapida_pide_razonamiento_minimo_y_usa_otra_cache(tmp_path, monkeypatch):
    cache = tmp_path / "c.json"
    cache.write_text(json.dumps({"agente:net sales": {"consulta": "VIEJA", "pregunta": "net sales"}}),
                     encoding="utf-8")
    monkeypatch.setattr(recall, "_ruta_cache", lambda: cache)
    llamadas = []
    monkeypatch.setitem(sys.modules, "langchain.chat_models", _modelo_falso(llamadas))
    # la normal reutiliza la caché de siempre; la rápida NO (si no, mediría la caché)
    assert recall.reescribir_consulta("net sales") == "VIEJA" and llamadas == []
    assert recall.reescribir_consulta("net sales", rapida=True) == "rewritten query"
    assert llamadas == [{"temperature": 0, "reasoning": {"effort": "minimal"}}]
    guardado = json.loads(cache.read_text(encoding="utf-8"))["agente-rapida:net sales"]
    assert guardado["razonamiento"] == "minimal" and "latencia_s" in guardado
    assert json.loads(cache.read_text(encoding="utf-8"))["agente:net sales"]["consulta"] == "VIEJA"


def test_rapida_si_el_proveedor_rechaza_minimal_prueba_low_y_lo_apunta(tmp_path, monkeypatch):
    cache = tmp_path / "c.json"
    monkeypatch.setattr(recall, "_ruta_cache", lambda: cache)
    llamadas = []
    monkeypatch.setitem(sys.modules, "langchain.chat_models",
                        _modelo_falso(llamadas, fallar=("minimal",)))
    recall.reescribir_consulta("capex", rapida=True)
    assert json.loads(cache.read_text(encoding="utf-8"))["agente-rapida:capex"]["razonamiento"] == "low"


def test_rapida_la_herramienta_pasa_rapida_a_la_reescritura(monkeypatch):
    from agente import herramientas as H
    vistos = []
    monkeypatch.setattr(recall, "reescribir_consulta",
                        lambda q, modelo=None, **kw: vistos.append(kw) or q)
    monkeypatch.setattr(H, "buscar", lambda *a, **k: [])
    hs = H.construir_herramientas(reescritura=True, reescritura_rapida=True)
    next(t for t in hs if t.name == "search_filings").invoke({"query": "x", "ticker": "NVDA"})
    assert vistos == [{"rapida": True}]


# --- A7 ---------------------------------------------------------------------
def test_cifras_de_la_cita_respeta_la_escala():
    assert 631_000_000 in cifras_de_la_cita(CITA_GOOGL)
    assert 631 not in cifras_de_la_cita(CITA_GOOGL)            # el error del baseline no pasa
    assert 5_990_000_000 in cifras_de_la_cita("represent $5.99 billion and $1.23 billion")
    fila = "Investment portfolio  100 basis points  Decline in fair value  $ 2,416  $ 2,755"
    assert 2_416_000_000 in cifras_de_la_cita(fila)             # tabla «in millions»


def test_a6_cifras_valida_la_cifra_de_texto_contra_la_cita_y_no_contra_xbrl():
    bien = _SR(cifra=631_000_000.0, ticker="GOOGL", ejercicio=2025, fuente="texto",
               cita=CITA_GOOGL, chunk_id="GOOGL-2025-7A-0003")
    # el verificador viejo la rechazaría: 631 M no es un hecho XBRL de GOOGL
    assert verificar_cifras_contra_xbrl.after_model(_estado(bien), None) is not None
    # el de A7 la acepta
    assert verificar_cifras_con_texto.after_model(_estado(bien), None) is None


def test_a6_cifras_rebota_la_escala_equivocada_una_sola_vez():
    mal = _SR(cifra=631.0, ticker="GOOGL", ejercicio=2025, fuente="texto",
              cita=CITA_GOOGL, chunk_id="GOOGL-2025-7A-0003")
    salto = verificar_cifras_con_texto.after_model(_estado(mal), None)
    assert salto["jump_to"] == "model" and "unidades completas" in salto["messages"][0]["content"]
    ya = type("H", (), {"content": salto["messages"][0]["content"]})()
    assert verificar_cifras_con_texto.after_model(_estado(mal, [ya]), None) is None


def test_a6_cifras_sigue_verificando_xbrl_cuando_la_fuente_no_es_texto():
    inventada = _SR(cifra=1.0e11, ticker="NVDA", ejercicio=2025, fuente="xbrl")
    assert verificar_cifras_con_texto.after_model(_estado(inventada), None) is not None
    real = _SR(cifra=130_497_000_000.0, ticker="NVDA", ejercicio=2025, fuente="xbrl")
    assert verificar_cifras_con_texto.after_model(_estado(real), None) is None


def test_a6_cifras_monta_el_verificador_nuevo_y_el_prompt_mantiene_la_honestidad():
    nombres = lambda n: [m.name for m in middlewares_para(ARQUITECTURAS[n])]
    assert "verificar_cifras_con_texto" in nombres("a6_cifras_texto")
    assert "verificar_cifras_contra_xbrl" not in nombres("a6_cifras_texto")
    assert "verificar_cifras_contra_xbrl" in nombres("a5_limites")
    p = PROMPTS["cifras_texto"]
    assert p.startswith(PROMPTS["comparativas"])               # añade, no quita
    assert "UNIDADES COMPLETAS" in p and "fuente='ninguna'" in p.split("Lo que NO cambia")[1]


def test_la_cache_de_reescrituras_no_pierde_entradas_ni_se_corrompe(tmp_path):
    """Dos procesos (los dos golden a la vez) escriben la misma caché."""
    ruta = tmp_path / "r.json"
    recall._guardar_en_cache(ruta, "a", {"consulta": "1"})
    recall._guardar_en_cache(ruta, "b", {"consulta": "2"})
    assert set(json.loads(ruta.read_text(encoding="utf-8"))) == {"a", "b"}
    assert not list(tmp_path.glob("*.tmp"))
