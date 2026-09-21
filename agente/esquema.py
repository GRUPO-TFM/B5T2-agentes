"""Contrato de salida estructurada (§7 del enunciado).

Dos clases:

- `RespuestaFinanciera`: el contrato del enunciado, sin tocar. Es lo que usa
  el baseline.
- `RespuestaFinancieraEstricta`: la misma, con validadores de coherencia. Es
  un guardrail: si el modelo dice `fuente="ninguna"` y a la vez da una cifra,
  Pydantic falla, LangChain le devuelve el error como ToolMessage y el modelo
  tiene que corregirse. No cuesta una llamada extra salvo cuando hace falta.

Los campos del enunciado no se quitan ni se renombran. Se pueden añadir.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

TICKERS = {"NVDA", "MSFT", "AAPL", "GOOGL", "META", "AMZN"}
EJERCICIOS = {2024, 2025}


class RespuestaFinanciera(BaseModel):
    """Respuesta trazable a una pregunta sobre informes 10-K."""

    respuesta: str = Field(
        description="Respuesta en prosa, breve y directa")
    cifra: float | None = Field(
        default=None, description="Valor numérico, si la pregunta pide uno")
    unidad: str | None = Field(
        default=None, description="USD, shares, porcentaje…")
    ticker: str | None = None
    ejercicio: int | None = None
    fuente: Literal["xbrl", "texto", "ambas", "ninguna"] = Field(
        description="De dónde sale el dato. 'ninguna' si no está en el corpus")
    cita: str | None = Field(
        default=None,
        description="Texto literal del informe que respalda la respuesta")
    chunk_id: str | None = Field(
        default=None,
        description="Identificador del fragmento citado, para verificar")


class RespuestaFinancieraEstricta(RespuestaFinanciera):
    """El mismo contrato, con las reglas de coherencia que un analista exigiría.

    Los mensajes de error están escritos PARA EL MODELO: son lo que le llega
    de vuelta cuando la validación falla, así que le dicen qué corregir.
    """

    @model_validator(mode="after")
    def _coherencia(self) -> "RespuestaFinancieraEstricta":
        if self.ticker is not None:
            self.ticker = self.ticker.upper().strip()
            if self.ticker not in TICKERS:
                raise ValueError(
                    f"ticker={self.ticker!r} no está en el corpus. "
                    f"Válidos: {sorted(TICKERS)}. Si la compañía no está, "
                    f"usa fuente='ninguna' y ticker=null."
                )
        if self.ejercicio is not None and self.ejercicio not in EJERCICIOS:
            raise ValueError(
                f"ejercicio={self.ejercicio} no está en el corpus (solo "
                f"{sorted(EJERCICIOS)}). Si el ejercicio no está, usa "
                f"fuente='ninguna' y ejercicio=null."
            )
        if self.fuente == "ninguna":
            if self.cifra is not None or self.chunk_id is not None:
                raise ValueError(
                    "fuente='ninguna' significa que el dato NO está en el "
                    "corpus: entonces cifra y chunk_id deben ser null. Si sí "
                    "encontraste el dato, cambia fuente a 'xbrl', 'texto' o "
                    "'ambas'."
                )
        if self.fuente in ("xbrl", "ambas") and self.cifra is None:
            raise ValueError(
                f"fuente={self.fuente!r} implica una cifra sacada de "
                f"get_xbrl_fact: rellena `cifra` con ese valor exacto, o usa "
                f"fuente='texto' si la respuesta no es numérica."
            )
        if self.fuente in ("texto", "ambas") and not (self.cita and self.chunk_id):
            raise ValueError(
                f"fuente={self.fuente!r} implica un fragmento de texto: "
                f"rellena `cita` con la frase literal y `chunk_id` con el "
                f"identificador que devolvió search_filings (formato "
                f"TICKER-AÑO-ITEM-NNNN)."
            )
        return self
