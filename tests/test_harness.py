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


def test_calentar_no_revienta_si_no_hay_codificador(capsys):
    """Si el codificador no se puede cargar, avisa y devuelve False: el agente
    sigue funcionando y pagará la carga en su primera búsqueda."""
    assert interfaz.calentar(offline_si_cacheado=False, verbose=True) in (True, False)


def test_ejecutar_no_calienta_con_responder_falso(tmp_path, monkeypatch):
    """Con un responder inyectado (tests) no hay agente que precalentar."""
    llamadas = []
    monkeypatch.setattr(interfaz, "calentar", lambda **kw: llamadas.append(kw))
    monkeypatch.setattr(interfaz, "dir_resultados", lambda: tmp_path / "r")
    interfaz.ejecutar(interfaz.raiz_repo() / "data" / "golden_set.jsonl", "baseline", 9,
                      responder_fn=_responder_falso, solo_ids=["gX-001"], verbose=False)
    assert llamadas == []


def test_la_cifra_del_agente_no_la_pisa_el_veredicto(tmp_path, monkeypatch):
    """Regresión: `cifra` y `cita` son a la vez campos de la respuesta y nombres
    de evaluador. Si comparten nombre de columna, el booleano pisa el dato y la
    tabla miente (pasó de verdad en el baseline del 21-sep)."""
    monkeypatch.setattr(interfaz, "dir_resultados", lambda: tmp_path / "r")
    ruta = interfaz.raiz_repo() / "data" / "golden_set.jsonl"
    interfaz.ejecutar(ruta, "baseline", 7, responder_fn=_responder_falso,
                      solo_ids=["gX-001"], verbose=False)
    fila = interfaz.puntuar("baseline", 7, con_recall=False).set_index("id").loc["gX-001"]

    assert fila["cifra_dada"] == 130497000000.0      # lo que respondió el agente
    assert fila["cifra"] == True                      # el veredicto del evaluador  # noqa: E712
    assert fila["cifra_esperada"] == 130497000000.0
    assert abs(fila["ratio_cifra"] - 1.0) < 1e-9


def test_columnas_de_instrumentacion(tmp_path, monkeypatch):
    """Sin ablación no se puede atribuir dentro de un peldaño; con estas
    columnas sí, porque dicen qué guardrail actuó y cuántas veces."""
    monkeypatch.setattr(interfaz, "dir_resultados", lambda: tmp_path / "r")
    ruta = interfaz.raiz_repo() / "data" / "golden_set.jsonl"
    interfaz.ejecutar(ruta, "baseline", 8, responder_fn=_responder_falso,
                      solo_ids=["gX-001"], verbose=False)
    t = interfaz.puntuar("baseline", 8, con_recall=False)
    for col in ("corrigio_cifra", "corrigio_cita", "reintentos_esquema",
                "limite_alcanzado", "n_busquedas", "busquedas_con_ticker",
                "busquedas_con_item", "uso_read_section"):
        assert col in t, col
    fila = t.set_index("id").loc["gX-001"]
    assert fila["corrigio_cifra"] == False and fila["corrigio_cita"] == False   # noqa: E712
    assert fila["reintentos_esquema"] == 0        # el responder falso valida a la primera
    assert fila["n_busquedas"] == 0               # solo llamó a get_xbrl_fact

    resumen = interfaz.resumir(t, "baseline")
    for clave in ("% corrigió cifra", "% corrigió cita", "reintentos esquema",
                  "% límite alcanzado"):
        assert clave in resumen, clave


def test_solo_familia_filtra(tmp_path, monkeypatch):
    monkeypatch.setattr(interfaz, "dir_resultados", lambda: tmp_path / "r")
    ruta = interfaz.raiz_repo() / "data" / "golden_set.jsonl"
    carpeta = interfaz.ejecutar(ruta, "baseline", 10, responder_fn=_responder_falso,
                                solo_familia="numerica", verbose=False)
    assert len(list(carpeta.glob("*.json"))) == 6      # 6 numéricas en el golden set


def test_la_escalera_es_acumulativa():
    """Cada peldaño añade y no quita: si algo se apaga al subir, la comparación
    deja de atribuirse a una sola cosa."""
    from agente.config import ARQUITECTURAS
    orden = ["baseline", "a1_guardrails", "a2_retrieval", "a3_hibrido", "a4_comparativas"]
    booleanos = ["limites", "verificador_cifras", "verificador_cita", "esquema_estricto",
                 "filtros_forzados", "reescritura", "hibrido"]
    previo = ARQUITECTURAS[orden[0]].como_dict()
    for nombre in orden[1:]:
        actual = ARQUITECTURAS[nombre].como_dict()
        for b in booleanos:
            assert actual[b] >= previo[b], f"{nombre} apaga {b}"
        previo = actual
    assert ARQUITECTURAS["final"].nombre == "a4_comparativas"


def test_la_instrumentacion_se_recalcula_al_puntuar(tmp_path, monkeypatch):
    """Lo derivado se deriva al puntuar, no se lee del crudo. Así un detector
    corregido se aplica a lo ya guardado sin repetir llamadas — que es la
    promesa de guardar el crudo."""
    import json as _json
    monkeypatch.setattr(interfaz, "dir_resultados", lambda: tmp_path / "r")
    ruta = interfaz.raiz_repo() / "data" / "golden_set.jsonl"
    carpeta = interfaz.ejecutar(ruta, "baseline", 11, responder_fn=_responder_falso,
                                solo_ids=["gX-001"], verbose=False)

    # Ensuciamos el valor GUARDADO: si puntuar lo leyera, saldría True.
    f = carpeta / "gX-001.json"
    reg = _json.loads(f.read_text(encoding="utf-8"))
    reg["resultado"]["limite_alcanzado"] = True
    reg["resultado"]["reintentos_esquema"] = 99
    f.write_text(_json.dumps(reg, ensure_ascii=False), encoding="utf-8")

    fila = interfaz.puntuar("baseline", 11, con_recall=False).set_index("id").loc["gX-001"]
    assert fila["limite_alcanzado"] == False      # recalculado de los mensajes  # noqa: E712
    assert fila["reintentos_esquema"] == 0
