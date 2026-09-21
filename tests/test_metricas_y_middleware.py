"""Primitivas de medición y la lógica de los middleware, con estado falso."""
from types import SimpleNamespace

from agente.metricas import acierta, cuadra, extraer_cifras, posicion_del_ancla
from agente.middleware import inferir_filtros, verificar_cifras_contra_xbrl, verificar_cita
from agente.esquema import RespuestaFinanciera


def test_cuadra_tolera_redondeo_y_rechaza_desvios():
    assert cuadra(100.0, 100.4, 0.01)
    assert not cuadra(100.0, 150.0, 0.01)


def test_extraer_cifras_en_espanol_e_ingles():
    assert extraer_cifras("281.724 millones de dólares") == [281_724_000_000.0]
    assert extraer_cifras("$130.5 billion") == [130_500_000_000.0]


def test_acierta_exige_mismo_ejercicio(chunks_por_id, golden):
    g = next(x for x in golden if x["id"] == "gX-007")
    bueno = chunks_por_id[g["chunk_id_esperado"]]
    assert acierta(g, [bueno])
    otro_anio = {**bueno, "fiscal_year": 2024}
    assert not acierta(g, [otro_anio])
    assert posicion_del_ancla(g, [otro_anio, bueno]) == 2


def test_inferir_filtros_solo_si_es_unico():
    assert inferir_filtros("¿Cuáles fueron los ingresos de NVIDIA en el ejercicio fiscal 2025?") \
        == {"ticker": "NVDA", "fiscal_year": 2025}
    assert inferir_filtros("¿Cuánto crecieron los ingresos de Microsoft entre FY2024 y FY2025?") \
        == {"ticker": "MSFT", "item": "7"}
    assert inferir_filtros("¿Qué dice Apple sobre sus riesgos y sobre el tipo de cambio?") \
        == {"ticker": "AAPL"}          # dos secciones posibles: no se fuerza ninguna
    assert inferir_filtros("Compara Apple con Meta") == {}


def _estado(sr, mensajes=()):
    return {"structured_response": sr, "messages": list(mensajes)}


def test_verificador_de_cifras_deja_pasar_lo_que_cuadra():
    sr = RespuestaFinanciera(respuesta="x", fuente="xbrl", cifra=130_497_000_000, unidad="USD",
                             ticker="NVDA", ejercicio=2025)
    assert verificar_cifras_contra_xbrl.after_model(_estado(sr), None) is None


def test_verificador_de_cifras_rebota_una_vez():
    sr = RespuestaFinanciera(respuesta="x", fuente="xbrl", cifra=99_000_000_000, unidad="USD",
                             ticker="NVDA", ejercicio=2025)
    salto = verificar_cifras_contra_xbrl.after_model(_estado(sr), None)
    assert salto is not None and salto["jump_to"] == "model"
    assert "NINGÚN hecho XBRL" in salto["messages"][0]["content"]
    # segunda vez, con la marca ya en el estado: no vuelve a rebotar
    ya = SimpleNamespace(content=salto["messages"][0]["content"])
    assert verificar_cifras_contra_xbrl.after_model(_estado(sr, [ya]), None) is None


def test_verificador_de_cifras_ignora_porcentajes_y_sin_cifra():
    pct = RespuestaFinanciera(respuesta="x", fuente="xbrl", cifra=14.9, unidad="%", ticker="MSFT", ejercicio=2025)
    assert verificar_cifras_contra_xbrl.after_model(_estado(pct), None) is None
    assert verificar_cifras_contra_xbrl.after_model(_estado(None), None) is None


def test_verificador_de_cita_rebota_chunk_inventado_y_parafrasis(chunks_por_id):
    sr = RespuestaFinanciera(respuesta="x", fuente="texto", cita="hola", chunk_id="NVDA-2025-1A-9999")
    assert "NO existe" in verificar_cita.after_model(_estado(sr), None)["messages"][0]["content"]
    sr2 = RespuestaFinanciera(respuesta="x", fuente="texto", cita="frase inventada que no está",
                              chunk_id="NVDA-2025-1A-0013")
    assert "no aparece" in verificar_cita.after_model(_estado(sr2), None)["messages"][0]["content"]
    literal = chunks_por_id["NVDA-2025-1A-0013"]["texto"][50:200]
    sr3 = RespuestaFinanciera(respuesta="x", fuente="texto", cita=literal, chunk_id="NVDA-2025-1A-0013")
    assert verificar_cita.after_model(_estado(sr3), None) is None


def test_el_texto_del_10k_no_dispara_el_detector_de_limite():
    """Regresión: buscar «limit» y «exceed» sueltos daba falso positivo en el
    baseline, que no lleva límites. Los 10-K hablan de export licensing limits
    y de thresholds exceeding — gX-007 (NVIDIA, controles de exportación)."""
    from agente.resultado import _limite_alcanzado
    texto_10k = ("The licensing requirements also apply to the export of products "
                 "exceeding certain performance thresholds... would limit access "
                 "to the market for IT services.")
    assert _limite_alcanzado([{"type": "tool", "content": texto_10k}]) is False
    assert _limite_alcanzado([{"type": "tool",
                               "content": "Tool call limit exceeded. Do not call "
                                          "'search_filings' again."}]) is True
