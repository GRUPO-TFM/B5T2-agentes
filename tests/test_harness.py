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
    assert ARQUITECTURAS["final"].nombre == "a6_cifras_texto"


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


# ---------------------------------------------------------------------------
# Errores del proveedor: se reintentan, se guardan enteros y se reparan solos
# ---------------------------------------------------------------------------
class _ErrorProveedor(Exception):
    """Imita `openrouter.errors.OpenRouterError`: trae status_code y body."""
    def __init__(self, status_code, body):
        super().__init__("Provider returned error")
        self.status_code = status_code
        self.body = body


def _responder_que_falla(veces, codigo=400):
    """Falla `veces` veces y luego responde. Apunta los thread_id que recibió."""
    estado = {"llamadas": 0, "hilos": []}

    def fn(pregunta, thread_id=None, arquitectura="baseline", modelo="test"):
        estado["llamadas"] += 1
        estado["hilos"].append(thread_id)
        if estado["llamadas"] <= veces:
            raise _ErrorProveedor(codigo, '{"error":{"message":"Provider returned error",'
                                          '"metadata":{"raw":"upstream says no"}}}')
        return _responder_falso(pregunta, thread_id, arquitectura, modelo)
    fn.estado = estado
    return fn


def test_un_400_del_proveedor_se_reintenta_en_un_hilo_nuevo(tmp_path, monkeypatch):
    monkeypatch.setattr(interfaz, "dir_resultados", lambda: tmp_path / "resultados")
    monkeypatch.setattr(interfaz.time, "sleep", lambda s: None)
    ruta = interfaz.raiz_repo() / "data" / "golden_set.jsonl"
    fn = _responder_que_falla(veces=1)

    carpeta = interfaz.ejecutar(ruta, "baseline", 1, responder_fn=fn, solo_ids=["gX-001"], verbose=False)
    reg = json.loads((carpeta / "gX-001.json").read_text(encoding="utf-8"))

    assert fn.estado["llamadas"] == 2
    # el reintento NO reutiliza el hilo: reanudar un checkpoint a medias
    # metería la pregunta dos veces en la misma conversación
    assert fn.estado["hilos"] == ["baseline-rep1-gX-001", "baseline-rep1-gX-001-intento2"]
    assert "resultado" in reg and "error" not in reg
    assert reg["thread_id"] == "baseline-rep1-gX-001-intento2"
    # el error se guarda ENTERO: el body es lo único que dice qué pasó de verdad
    assert len(reg["intentos_fallidos"]) == 1
    assert reg["intentos_fallidos"][0]["status_code"] == 400
    assert "upstream says no" in reg["intentos_fallidos"][0]["body"]

    tabla = interfaz.puntuar("baseline", 1, con_recall=False).set_index("id")
    assert tabla.loc["gX-001", "reintentos_proveedor"] == 1
    assert tabla.loc["gX-001", "acierto"] == True                      # noqa: E712


def test_un_401_no_se_reintenta(tmp_path, monkeypatch):
    monkeypatch.setattr(interfaz, "dir_resultados", lambda: tmp_path / "resultados")
    ruta = interfaz.raiz_repo() / "data" / "golden_set.jsonl"
    fn = _responder_que_falla(veces=5, codigo=401)        # clave mala: repetir no arregla nada

    carpeta = interfaz.ejecutar(ruta, "baseline", 1, responder_fn=fn, solo_ids=["gX-001"], verbose=False)
    reg = json.loads((carpeta / "gX-001.json").read_text(encoding="utf-8"))
    assert fn.estado["llamadas"] == 1
    assert "error" in reg and "resultado" not in reg
    assert reg["intentos_fallidos"][0]["status_code"] == 401


def test_un_fichero_con_error_se_repara_al_volver_a_pasar(tmp_path, monkeypatch):
    monkeypatch.setattr(interfaz, "dir_resultados", lambda: tmp_path / "resultados")
    monkeypatch.setattr(interfaz.time, "sleep", lambda s: None)
    ruta = interfaz.raiz_repo() / "data" / "golden_set.jsonl"

    # Pasada 1: falla dos veces seguidas → se agota el reintento y queda el error
    fn = _responder_que_falla(veces=2)
    carpeta = interfaz.ejecutar(ruta, "baseline", 1, responder_fn=fn, solo_ids=["gX-001"], verbose=False)
    reg = json.loads((carpeta / "gX-001.json").read_text(encoding="utf-8"))
    assert "error" in reg and len(reg["intentos_fallidos"]) == 2
    assert interfaz.puntuar("baseline", 1, con_recall=False).set_index("id").loc["gX-001", "acierto"] == False  # noqa: E712

    # Pasada 2 (volver a ejecutar el bloque 3): el fichero con error se repite
    # solo, en un hilo que no se haya usado, y conserva el historial de errores
    fn2 = _responder_que_falla(veces=0)
    interfaz.ejecutar(ruta, "baseline", 1, responder_fn=fn2, solo_ids=["gX-001"], verbose=False)
    reg = json.loads((carpeta / "gX-001.json").read_text(encoding="utf-8"))
    assert fn2.estado["hilos"] == ["baseline-rep1-gX-001-intento3"]
    assert "resultado" in reg and "error" not in reg
    assert len(reg["intentos_fallidos"]) == 2
    tabla = interfaz.puntuar("baseline", 1, con_recall=False).set_index("id")
    assert tabla.loc["gX-001", "reintentos_proveedor"] == 2
    assert tabla.loc["gX-001", "acierto"] == True                      # noqa: E712

    # Con reintentar_errores=False se respeta el fichero tal cual
    fn3 = _responder_que_falla(veces=0)
    interfaz.ejecutar(ruta, "baseline", 1, responder_fn=fn3, solo_ids=["gX-001"],
                      reintentar_errores=False, verbose=False)
    assert fn3.estado["llamadas"] == 0


# ---------------------------------------------------------------------------
# Turno vacío: el modelo cierra sin structured_response (2 de 60 en A4)
# ---------------------------------------------------------------------------
def _responder_vacio(veces):
    """Devuelve `structured_response=None` las primeras `veces` invocaciones."""
    estado = {"llamadas": 0, "hilos": []}

    def fn(pregunta, thread_id=None, arquitectura="baseline", modelo="test"):
        estado["llamadas"] += 1
        estado["hilos"].append(thread_id)
        r = _responder_falso(pregunta, thread_id, arquitectura, modelo)
        if estado["llamadas"] <= veces:
            r = {**r, "structured_response": None}
        return r
    fn.estado = estado
    return fn


def test_un_turno_vacio_se_reintenta_en_un_hilo_nuevo(tmp_path, monkeypatch):
    monkeypatch.setattr(interfaz, "dir_resultados", lambda: tmp_path / "resultados")
    monkeypatch.setattr(interfaz.time, "sleep", lambda s: None)
    ruta = interfaz.raiz_repo() / "data" / "golden_set.jsonl"
    fn = _responder_vacio(veces=1)

    carpeta = interfaz.ejecutar(ruta, "baseline", 1, responder_fn=fn, solo_ids=["gX-001"], verbose=False)
    reg = json.loads((carpeta / "gX-001.json").read_text(encoding="utf-8"))

    assert fn.estado["llamadas"] == 2
    assert fn.estado["hilos"] == ["baseline-rep1-gX-001", "baseline-rep1-gX-001-intento2"]
    assert reg["resultado"]["structured_response"] is not None
    assert [x["tipo"] for x in reg["intentos_fallidos"]] == [interfaz.MARCA_SIN_RESPUESTA]

    tabla = interfaz.puntuar("baseline", 1, con_recall=False).set_index("id")
    assert tabla.loc["gX-001", "reintentos_vacios"] == 1
    assert tabla.loc["gX-001", "reintentos_proveedor"] == 0      # no fue culpa de la red
    assert tabla.loc["gX-001", "acierto"] == True                                  # noqa: E712


def test_si_el_turno_vacio_persiste_se_guarda_como_fallo(tmp_path, monkeypatch):
    """Agotado el reintento, la fila se guarda VACÍA: es un fallo real y la
    tabla tiene que verlo, no esconderlo."""
    monkeypatch.setattr(interfaz, "dir_resultados", lambda: tmp_path / "resultados")
    monkeypatch.setattr(interfaz.time, "sleep", lambda s: None)
    ruta = interfaz.raiz_repo() / "data" / "golden_set.jsonl"
    fn = _responder_vacio(veces=99)

    carpeta = interfaz.ejecutar(ruta, "baseline", 1, responder_fn=fn, solo_ids=["gX-001"],
                                reintentar_errores=False, verbose=False)
    reg = json.loads((carpeta / "gX-001.json").read_text(encoding="utf-8"))
    assert fn.estado["llamadas"] == 2                     # 1 + 1 reintento, no más
    assert reg["resultado"]["structured_response"] is None
    assert "error" not in reg                             # no hubo excepción

    tabla = interfaz.puntuar("baseline", 1, con_recall=False).set_index("id")
    assert tabla.loc["gX-001", "sin_respuesta"] == True                            # noqa: E712
    assert tabla.loc["gX-001", "acierto"] == False                                 # noqa: E712
    assert tabla.loc["gX-001", "reintentos_vacios"] == 2


def test_una_fila_sin_respuesta_se_repara_al_volver_a_pasar(tmp_path, monkeypatch):
    """Es lo que permite reparar las 2 filas de A4 sin repetir las otras 58."""
    monkeypatch.setattr(interfaz, "dir_resultados", lambda: tmp_path / "resultados")
    monkeypatch.setattr(interfaz.time, "sleep", lambda s: None)
    ruta = interfaz.raiz_repo() / "data" / "golden_set.jsonl"

    fn = _responder_vacio(veces=99)
    carpeta = interfaz.ejecutar(ruta, "baseline", 1, responder_fn=fn, solo_ids=["gX-001"],
                                reintentar_errores=False, verbose=False)
    assert json.loads((carpeta / "gX-001.json").read_text(encoding="utf-8"))[
        "resultado"]["structured_response"] is None

    fn2 = _responder_vacio(veces=0)
    interfaz.ejecutar(ruta, "baseline", 1, responder_fn=fn2, solo_ids=["gX-001"], verbose=False)
    reg = json.loads((carpeta / "gX-001.json").read_text(encoding="utf-8"))
    assert fn2.estado["hilos"] == ["baseline-rep1-gX-001-intento3"]   # hilo nunca usado
    assert reg["resultado"]["structured_response"] is not None
    assert len(reg["intentos_fallidos"]) == 2                          # historial conservado

    tabla = interfaz.puntuar("baseline", 1, con_recall=False).set_index("id")
    assert tabla.loc["gX-001", "acierto"] == True                                  # noqa: E712


def test_una_respuesta_equivocada_no_se_repite(tmp_path, monkeypatch):
    """Sólo se repara lo que no dejó respuesta. Una respuesta MALA es una
    medición: repetirla sería re-tirar el dado hasta que salga bien."""
    monkeypatch.setattr(interfaz, "dir_resultados", lambda: tmp_path / "resultados")
    ruta = interfaz.raiz_repo() / "data" / "golden_set.jsonl"
    # gX-002 es AAPL; el responder falso siempre contesta la cifra de NVDA -> falla
    carpeta = interfaz.ejecutar(ruta, "baseline", 1, responder_fn=_responder_falso,
                                solo_ids=["gX-002"], verbose=False)
    assert interfaz.puntuar("baseline", 1, con_recall=False).set_index("id").loc[
        "gX-002", "cifra"] == False                                                # noqa: E712
    antes = (carpeta / "gX-002.json").stat().st_mtime_ns
    interfaz.ejecutar(ruta, "baseline", 1, responder_fn=_responder_falso,
                      solo_ids=["gX-002"], verbose=False)
    assert (carpeta / "gX-002.json").stat().st_mtime_ns == antes       # no se tocó
