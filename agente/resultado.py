"""Un resultado del agente, en formato plano y serializable.

`responder()` devuelve objetos de LangChain (AIMessage, ToolMessage, la
RespuestaFinanciera de Pydantic). Para guardar el crudo en disco y para que los
evaluadores funcionen igual sobre un resultado vivo que sobre uno guardado
hace tres días, todo pasa por `normalizar_resultado()` primero.

Formato plano:
    {
      "structured_response": {...} | None,   # RespuestaFinanciera.model_dump()
      "herramientas": [...],                 # nombres, en orden, SOLO herramientas
      "llamadas": [{"name", "args"}, ...],   # las mismas, con argumentos
      "n_llamadas": int,
      "tokens_in": int, "tokens_out": int,
      "coste_usd": float, "latencia_s": float,
      "limite_alcanzado": bool,              # ¿alguna herramienta fue bloqueada?
      "correcciones": [...],                 # marcas de los verificadores que saltaron
      "messages": [...],                     # messages_to_dict, para pretty_trace
      "modelo": str, "arquitectura": str,
    }
"""

from __future__ import annotations

from typing import Any

# Nombres que aparecen como tool_call en la trayectoria pero NO son
# herramientas: son el mecanismo de salida estructurada de create_agent.
NO_SON_HERRAMIENTAS = {"RespuestaFinanciera", "RespuestaFinancieraEstricta"}
HERRAMIENTAS_CONTRATO = ("list_available", "get_xbrl_fact", "search_filings",
                         "read_section")


def _mensajes(resultado) -> list:
    if isinstance(resultado, dict):
        return resultado.get("messages", []) or []
    return list(resultado)


def llamadas_de(resultado) -> list[dict]:
    """`[{"name", "args"}]` de todas las tool calls reales, en orden."""
    salida = []
    for m in _mensajes(resultado):
        if isinstance(m, dict):                       # ya normalizado
            for tc in m.get("tool_calls") or []:
                if tc["name"] not in NO_SON_HERRAMIENTAS:
                    salida.append({"name": tc["name"], "args": tc.get("args", {})})
            continue
        for tc in getattr(m, "tool_calls", None) or []:
            if tc["name"] not in NO_SON_HERRAMIENTAS:
                salida.append({"name": tc["name"], "args": tc.get("args", {})})
    return salida


def herramientas_usadas(resultado) -> list[str]:
    """Nombres de las herramientas de la trayectoria, en orden, sin contar la
    llamada de salida estructurada (que `create_agent` implementa como tool call)."""
    if isinstance(resultado, dict) and "herramientas" in resultado \
            and "structured_response" in resultado \
            and not hasattr(resultado.get("structured_response"), "model_dump"):
        return list(resultado["herramientas"])       # ya normalizado
    return [c["name"] for c in llamadas_de(resultado)]


def tokens_de(resultado) -> tuple[int, int]:
    entrada = salida = 0
    for m in _mensajes(resultado):
        uso = (m.get("usage_metadata") if isinstance(m, dict)
               else getattr(m, "usage_metadata", None)) or {}
        entrada += uso.get("input_tokens", 0) or 0
        salida += uso.get("output_tokens", 0) or 0
    return entrada, salida


def _limite_alcanzado(mensajes) -> bool:
    for m in mensajes:
        tipo = m.get("type") if isinstance(m, dict) else type(m).__name__
        contenido = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
        if tipo in ("tool", "ToolMessage") and isinstance(contenido, str) \
                and ("limit" in contenido.lower() and "exceed" in contenido.lower()
                     or "bloquead" in contenido.lower()):
            return True
    return False


def _correcciones(mensajes) -> list[str]:
    marcas = []
    for m in mensajes:
        contenido = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
        if isinstance(contenido, str) and contenido.startswith("[VERIFICACIÓN AUTOMÁTICA"):
            marcas.append(contenido.split("]", 1)[0].strip("["))
    return marcas


def normalizar_resultado(resultado, *, modelo: str = "", arquitectura: str = "",
                         coste_usd: float | None = None,
                         latencia_s: float | None = None) -> dict[str, Any]:
    """De objetos LangChain a un dict plano y serializable. Idempotente."""
    if isinstance(resultado, dict) and resultado.get("_normalizado"):
        return resultado

    from langchain_core.messages import messages_to_dict

    mensajes = _mensajes(resultado)
    sr = resultado.get("structured_response") if isinstance(resultado, dict) else None
    if sr is not None and hasattr(sr, "model_dump"):
        sr = sr.model_dump()

    llamadas = llamadas_de(resultado)
    entrada, salida = tokens_de(resultado)
    mensajes_dict = messages_to_dict(mensajes) if mensajes and not isinstance(mensajes[0], dict) else mensajes
    # `messages_to_dict` anida el contenido en ["data"]; aplanamos lo que usamos.
    planos = []
    for m in mensajes_dict:
        d = m.get("data", m)
        planos.append({
            "type": m.get("type", d.get("type")),
            "content": d.get("content"),
            "tool_calls": d.get("tool_calls"),
            "name": d.get("name"),
            "tool_call_id": d.get("tool_call_id"),
            "usage_metadata": d.get("usage_metadata"),
        })

    return {
        "_normalizado": True,
        "structured_response": sr,
        "herramientas": [c["name"] for c in llamadas],
        "llamadas": llamadas,
        "n_llamadas": len(llamadas),
        "tokens_in": entrada,
        "tokens_out": salida,
        "coste_usd": (coste_usd if coste_usd is not None
                      else (resultado.get("coste_usd", 0.0) if isinstance(resultado, dict) else 0.0)),
        "latencia_s": (latencia_s if latencia_s is not None
                       else (resultado.get("latencia_s") if isinstance(resultado, dict) else None)),
        "limite_alcanzado": _limite_alcanzado(mensajes),
        "correcciones": _correcciones(mensajes),
        "messages": planos,
        "modelo": modelo or (resultado.get("modelo", "") if isinstance(resultado, dict) else ""),
        "arquitectura": arquitectura or (resultado.get("arquitectura", "") if isinstance(resultado, dict) else ""),
    }


def pretty_trace(resultado, max_chars: int = 220) -> str:
    """La trayectoria legible. Funciona sobre el resultado vivo o el guardado."""
    r = normalizar_resultado(resultado)
    lineas, paso = [], 0
    for m in r["messages"]:
        for tc in m.get("tool_calls") or []:
            if tc["name"] in NO_SON_HERRAMIENTAS:
                continue
            paso += 1
            args = ", ".join(f"{k}={v!r}" for k, v in (tc.get("args") or {}).items())
            lineas.append(f"  {paso}. {tc['name']}({args})")
        if m.get("type") == "tool":
            contenido = str(m.get("content", "")).replace("\n", " ")
            lineas.append(f"       -> {contenido[:max_chars]}"
                          f"{'…' if len(contenido) > max_chars else ''}")
    sr = r["structured_response"]
    if sr:
        lineas.append(f"\n  respuesta: {sr.get('respuesta')}")
        lineas.append(f"  cifra: {sr.get('cifra')} {sr.get('unidad') or ''} · "
                      f"fuente: {sr.get('fuente')} · chunk: {sr.get('chunk_id')}")
    else:
        lineas.append("\n  (sin respuesta estructurada)")
    return "\n".join(lineas)
