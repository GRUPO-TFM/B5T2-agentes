"""ejecutar → puntuar → comparar con un responder falso. Sin API."""
import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agente import interfaz
from agente.esquema import RespuestaFinanciera


def _responder_falso(pregunta, thread_id=None, arquitectura="baseline", modelo="test"):
    """Imita la estructura real: mensajes LangChain + structured_response Pydantic,
    con la llamada de salida estructurada como tool call (como hace create_agent)."""
    mensajes = [
        HumanMessage(content=pregunta),
        AIMessage(content="", tool_calls=[{"name": "get_xbrl_fact", "id": "1",
                                          "args": {"ticker": "NVDA", "fiscal_year": 2025, "concept": "Revenues"}}],
                  usage_metadata={"input_tokens": 1000, "output_tokens": 50, "total_tokens": 1050}),
        ToolMessage(content="NVDA FY2025 · Revenues = 130,497,000,000 USD", tool_call_id="1", name="get_xbrl_fact"),
        AIMessage(content="", tool_calls=[{"name": "RespuestaFinanciera", "id": "2", "args": {}}],
                  usage_metadata={"input_tokens": 1200, "output_tokens": 80, "total_tokens": 1280}),
        ToolMessage(content="Returning structured response", tool_call_id="2", name="RespuestaFinanciera"),
    ]
    sr = RespuestaFinanciera(respuesta="130.497 M", cifra=130497000000.0, unidad="USD", ticker="NVDA",
                             ejercicio=2025, fuente="xbrl")
    return {"messages": mensajes, "structured_response": sr, "coste_usd": 0.0012, "latencia_s": 2.5}


def test_flujo_completo(tmp_path, monkeypatch):
    monkeypatch.setattr(interfaz, "dir_resultados", lambda: tmp_path / "resultados")
    ruta = interfaz.raiz_repo() / "data" / "golden_set.jsonl"

    carpeta = interfaz.ejecutar(ruta, "baseline", 1, responder_fn=_responder_falso,
                                solo_ids=["gX-001", "gX-002", "gX-007"], verbose=False)
    assert len(list(carpeta.glob("*.json"))) == 3
    reg = json.loads((carpeta / "gX-001.json").read_text(encoding="utf-8"))
    assert reg["resultado"]["herramientas"] == ["get_xbrl_fact"]        # sin RespuestaFinanciera
    assert reg["resultado"]["n_llamadas"] == 1
    assert reg["resultado"]["tokens_in"] == 2200
    assert reg["thread_id"] == "baseline-rep1-gX-001"

    # idempotente: segunda pasada no reescribe
    antes = (carpeta / "gX-001.json").stat().st_mtime_ns
    interfaz.ejecutar(ruta, "baseline", 1, responder_fn=_responder_falso, solo_ids=["gX-001"], verbose=False)
    assert (carpeta / "gX-001.json").stat().st_mtime_ns == antes

    tabla = interfaz.puntuar("baseline", 1, con_recall=False)
    assert set(tabla["id"]) == {"gX-001", "gX-002", "gX-007"}
    fila = tabla.set_index("id")
    assert fila.loc["gX-001", "cifra"] == True and fila.loc["gX-001", "trayectoria"] == True   # noqa: E712
    assert fila.loc["gX-001", "acierto"] == True                                                 # noqa: E712
    assert fila.loc["gX-002", "cifra"] == False        # AAPL: la cifra falsa es la de NVDA        # noqa: E712
    assert fila.loc["gX-007", "cita"] == False         # extractiva sin chunk                       # noqa: E712

    interfaz.ejecutar(ruta, "baseline", 2, responder_fn=_responder_falso, solo_ids=["gX-001"], verbose=False)
    interfaz.puntuar("baseline", 2, con_recall=False)
    comp = interfaz.comparar(["baseline"])
    assert comp.iloc[0]["reps"] == 2
    assert (tmp_path / "resultados" / "comparativa.md").is_file()
    md = (tmp_path / "resultados" / "comparativa.md").read_text(encoding="utf-8")
    assert "baseline" in md and "recall@5" in md
