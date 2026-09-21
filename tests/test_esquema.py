"""El esquema estricto rechaza respuestas incoherentes; el del contrato no cambia."""
import pytest
from pydantic import ValidationError

from agente.esquema import RespuestaFinanciera, RespuestaFinancieraEstricta


def test_el_contrato_no_cambia():
    campos = set(RespuestaFinanciera.model_fields)
    assert campos == {"respuesta", "cifra", "unidad", "ticker", "ejercicio", "fuente", "cita", "chunk_id"}
    assert set(RespuestaFinancieraEstricta.model_fields) == campos


def test_ninguna_con_cifra_falla():
    with pytest.raises(ValidationError, match="fuente='ninguna'"):
        RespuestaFinancieraEstricta(respuesta="x", fuente="ninguna", cifra=5.0)


def test_xbrl_sin_cifra_falla():
    with pytest.raises(ValidationError, match="implica una cifra"):
        RespuestaFinancieraEstricta(respuesta="x", fuente="xbrl")


def test_texto_sin_chunk_falla():
    with pytest.raises(ValidationError, match="fragmento de texto"):
        RespuestaFinancieraEstricta(respuesta="x", fuente="texto", cita="hola")


def test_ticker_desconocido_falla_y_se_normaliza():
    with pytest.raises(ValidationError, match="no está en el corpus"):
        RespuestaFinancieraEstricta(respuesta="x", fuente="ninguna", ticker="TSLA")
    r = RespuestaFinancieraEstricta(respuesta="x", fuente="ninguna", ticker="nvda")
    assert r.ticker == "NVDA"


def test_respuesta_coherente_pasa():
    r = RespuestaFinancieraEstricta(respuesta="x", fuente="ambas", cifra=1.0, unidad="USD",
                                    ticker="META", ejercicio=2025, cita="c", chunk_id="META-2025-7-0003")
    assert r.fuente == "ambas"


def test_el_contrato_base_sigue_siendo_permisivo():
    # El baseline usa la clase del enunciado: no debe rechazar nada de esto.
    RespuestaFinanciera(respuesta="x", fuente="ninguna", cifra=5.0)
