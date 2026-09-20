"""Punto de entrada del §6: `responder(pregunta)` y `evaluar(ruta_jsonl)`."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd

from agente.agente import MODELO, construir_agente
from agente.evaluadores import EVALUADORES

PRECIOS_OPENROUTER = {
    "google/gemini-3.5-flash-lite": (0.30, 2.50),
    "google/gemini-3.8-flash": (0.75, 3.75),
    "anthropic/claude-opus-5": (5.00, 25.00),
    "anthropic/claude-fable-5.1": (10.00, 50.00),
}


def herramientas_usadas(resultado) -> list[str]:
    """Nombres de las herramientas que aparecen en la trayectoria."""
    mensajes = resultado["messages"] if isinstance(resultado, dict) else resultado
    return [
        llamada["name"]
        for mensaje in mensajes
        for llamada in (getattr(mensaje, "tool_calls", None) or [])
    ]


def tokens_de(resultado) -> tuple[int, int]:
    """`(entrada, salida)` sumando el uso reportado por todos los mensajes."""
    mensajes = resultado["messages"] if isinstance(resultado, dict) else resultado
    entrada = salida = 0
    for mensaje in mensajes:
        uso = getattr(mensaje, "usage_metadata", None) or {}
        entrada += uso.get("input_tokens", 0) or 0
        salida += uso.get("output_tokens", 0) or 0
    return entrada, salida


def coste_de(resultado, modelo: str = MODELO) -> float:
    """Coste en USD de una invocación, según `PRECIOS_OPENROUTER`."""
    nombre = modelo.split(":", 1)[-1]
    if nombre not in PRECIOS_OPENROUTER:
        return 0.0
    precio_entrada, precio_salida = PRECIOS_OPENROUTER[nombre]
    entrada, salida = tokens_de(resultado)
    return (entrada * precio_entrada + salida * precio_salida) / 1e6


def responder(
    pregunta: str,
    thread_id: str | None = None,
    *,
    mejoras: bool = False,
    modelo: str = MODELO,
) -> dict:
    """Firma del §6: pregunta in, dict con `structured_response` out."""
    agente = construir_agente(modelo, mejoras)
    comienzo = time.perf_counter()
    resultado = agente.invoke(
        {"messages": [{"role": "user", "content": pregunta}]},
        config={"configurable": {"thread_id": thread_id or "default"}},
    )
    segundos = time.perf_counter() - comienzo
    return {
        **resultado,
        "coste_usd": coste_de(resultado, modelo),
        "latencia_s": segundos,
    }


def evaluar(
    ruta_jsonl: str | Path,
    responder=None,
    etiqueta: str = "",
    salida: str | Path | None = None,
) -> pd.DataFrame:
    """Ejecuta el agente sobre un JSONL. La ruta va primero; el resto es opcional.

    Los evaluadores están vacíos (paso 3): las columnas `cita`, `cifra` y
    `trayectoria` quedan en None. La trayectoria, el coste y la latencia sí
    se guardan, que es lo que hace falta para congelar el baseline.
    """
    ruta = Path(ruta_jsonl)
    if not ruta.is_file():
        raise FileNotFoundError(f"No encuentro el golden set: {ruta}")

    preguntas = [
        json.loads(linea)
        for linea in ruta.read_text(encoding="utf-8").splitlines()
        if linea.strip()
    ]
    funcion = responder if responder is not None else globals()["responder"]

    filas = []
    for i, item in enumerate(preguntas, 1):
        print(f"  [{i}/{len(preguntas)}] {item.get('id', i)}", flush=True)
        fila = {
            "id": item.get("id"),
            "familia": item.get("familia"),
            "ticker": item.get("ticker"),
        }
        try:
            r = funcion(
                item["pregunta"],
                thread_id=f"{etiqueta or 'eval'}-{item.get('id', i)}",
            )
            estructurada = r.get("structured_response")
            fila["latencia_s"] = r.get("latencia_s")
            fila["coste_usd"] = r.get("coste_usd", 0.0)
            fila["llamadas"] = len(herramientas_usadas(r))
            fila["herramientas"] = herramientas_usadas(r)
            fila["respuesta"] = getattr(estructurada, "respuesta", None)
            fila["cifra"] = getattr(estructurada, "cifra", None)
            fila["fuente"] = getattr(estructurada, "fuente", None)
            fila["chunk_id"] = getattr(estructurada, "chunk_id", None)
            for nombre, evaluador in EVALUADORES.items():
                fila[nombre] = evaluador(item, r)
        except Exception as e:
            fila["error"] = f"{type(e).__name__}: {e}"
        filas.append(fila)

    tabla = pd.DataFrame(filas)
    if salida:
        Path(salida).parent.mkdir(parents=True, exist_ok=True)
        tabla.to_csv(salida, index=False)
    return tabla
