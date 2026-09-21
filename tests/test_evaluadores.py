"""Los tres evaluadores, con resultados sintéticos. Sin API."""
from agente.evaluadores import (acierto, cifra_coincide_xbrl, cita_correcta, honestidad,
                                uso_la_tool_correcta)
from tests.conftest import resultado_falso

NUMERICA = {"id": "t-num", "familia": "numerica", "ticker": "NVDA", "fiscal_year": 2025,
            "cifra_esperada": 130497000000.0, "herramienta_esperada": ["get_xbrl_fact"]}
EXTRACTIVA = {"id": "t-ext", "familia": "extractiva", "ticker": "NVDA", "fiscal_year": 2025,
              "item_esperado": "1A", "ancla_texto": "The market in China, where our offerings are limited",
              "chunk_id_esperado": "NVDA-2025-1A-0013", "herramienta_esperada": ["search_filings"]}


# --- cifra -----------------------------------------------------------------
def test_cifra_redondeada_cuenta_como_acierto():
    r = resultado_falso(cifra=130_500_000_000, fuente="xbrl", herramientas=["get_xbrl_fact"])
    assert cifra_coincide_xbrl(NUMERICA, r) is True


def test_cifra_muy_desviada_es_fallo():
    r = resultado_falso(cifra=100_000_000_000, fuente="xbrl")
    assert cifra_coincide_xbrl(NUMERICA, r) is False


def test_sin_cifra_es_fallo_si_se_esperaba():
    assert cifra_coincide_xbrl(NUMERICA, resultado_falso(fuente="ninguna")) is False


def test_cifra_no_aplica_a_extractivas():
    assert cifra_coincide_xbrl(EXTRACTIVA, resultado_falso()) is None


# --- cita ------------------------------------------------------------------
def test_cita_literal_del_chunk_correcto(chunks_por_id):
    texto = chunks_por_id["NVDA-2025-1A-0013"]["texto"]
    frase = texto[texto.lower().find("the market in china"):][:150]
    r = resultado_falso(fuente="texto", cita=frase, chunk_id="NVDA-2025-1A-0013")
    assert cita_correcta(EXTRACTIVA, r) is True


def test_chunk_inventado_es_fallo():
    r = resultado_falso(fuente="texto", cita="anything", chunk_id="NVDA-2025-1A-9999")
    assert cita_correcta(EXTRACTIVA, r) is False


def test_cita_parafraseada_es_fallo():
    r = resultado_falso(fuente="texto", cita="China is a very competitive market for us",
                        chunk_id="NVDA-2025-1A-0013")
    assert cita_correcta(EXTRACTIVA, r) is False


def test_chunk_del_otro_ejercicio_es_fallo(chunks_por_id):
    otro = next(c for c in chunks_por_id if c.startswith("NVDA-2024-1A-"))
    r = resultado_falso(fuente="texto", cita=chunks_por_id[otro]["texto"][:100], chunk_id=otro)
    assert cita_correcta(EXTRACTIVA, r) is False


def test_cita_no_aplica_a_numericas():
    assert cita_correcta(NUMERICA, resultado_falso()) is None


# --- trayectoria -----------------------------------------------------------
def test_acertar_sin_xbrl_suspende_trayectoria():
    r = resultado_falso(cifra=130_497_000_000, fuente="texto", herramientas=["search_filings"])
    assert cifra_coincide_xbrl(NUMERICA, r) is True
    assert uso_la_tool_correcta(NUMERICA, r) is False
    assert acierto({"cifra": True, "trayectoria": False, "cita": None}) is False


def test_trayectoria_con_todas_las_esperadas():
    item = {**NUMERICA, "herramienta_esperada": ["get_xbrl_fact", "search_filings"]}
    r = resultado_falso(herramientas=["list_available", "get_xbrl_fact", "get_xbrl_fact", "search_filings"])
    assert uso_la_tool_correcta(item, r) is True


# --- honestidad y acierto --------------------------------------------------
def test_honestidad_solo_si_el_item_lo_pide():
    item = {**NUMERICA, "fuente_esperada": "ninguna", "cifra_esperada": None}
    assert honestidad(item, resultado_falso(fuente="ninguna")) is True
    assert honestidad(item, resultado_falso(fuente="xbrl", cifra=1.0)) is False
    assert honestidad(NUMERICA, resultado_falso()) is None


def test_acierto_ignora_los_que_no_aplican():
    assert acierto({"cita": None, "cifra": True, "trayectoria": True, "honestidad": None}) is True
    assert acierto({"cita": None, "cifra": None, "trayectoria": None, "honestidad": None}) is None
