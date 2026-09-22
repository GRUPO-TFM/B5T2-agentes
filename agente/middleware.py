"""Middleware del agente: los ganchos dentro del bucle.

El bucle que se escribió a mano el día 10 era: modelo → ¿pide herramientas? →
ejecutarlas → volver. El middleware son funciones que se enganchan en los
huecos de ese bucle. Aquí hay cuatro:

- `limites(arq)`            techo de llamadas a herramienta y de vueltas del modelo
- `verificar_cifras_contra_xbrl`   after_model: la cifra afirmada existe en XBRL
- `verificar_cita`          after_model: el chunk citado existe y contiene la cita
- `forzar_filtros`          wrap_tool_call: search_filings lleva ticker/año si la
                            pregunta los menciona y el modelo los olvidó

Regla de oro, del propio profesor: añadir un mensaje NO hace que el agente
vuelva a pensar. Para que haya otra vuelta hay que devolver `jump_to="model"`.
Y una corrección como máximo por invocación: sin ese freno, un modelo que
insiste da vueltas entre él y el verificador sin gastar herramientas, y el
límite de herramientas no lo corta.
"""

from __future__ import annotations

import re

from langchain.agents.middleware import (
    AgentState,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
    after_model,
    wrap_tool_call,
)
from langgraph.runtime import Runtime

from agente.config import Arquitectura
from agente.herramientas import formatear_valor
from agente.metricas import cuadra, normalizar
from agente.resultado import NO_SON_HERRAMIENTAS

MARCA_CIFRA = "VERIFICACIÓN AUTOMÁTICA DE CIFRA"
MARCA_CITA = "VERIFICACIÓN AUTOMÁTICA DE CITA"


# ---------------------------------------------------------------------------
# 1. Límites — control de coste, no inteligencia. Es lo primero que se pone.
# ---------------------------------------------------------------------------
class LimiteDeHerramientas(ToolCallLimitMiddleware):
    """Límite global que NO cuenta la llamada de salida estructurada.

    `create_agent(response_format=…)` implementa la respuesta como un tool call
    más (`RespuestaFinanciera`), y `ToolCallLimitMiddleware` sin `tool_name` lo
    cuenta contra el presupuesto: con 8 configuradas, la respuesta y su
    corrección se comen dos, y cuando el presupuesto está agotado la propia
    respuesta recibe un «Tool call limit exceeded» (visto en gX-019 de A1; la
    respuesta estructurada se capturó igual, pero de casualidad). La respuesta
    no es una herramienta: no cuenta.
    """

    def _matches_tool_filter(self, tool_call) -> bool:     # noqa: ANN001  (langchain 1.3.x)
        if tool_call["name"] in NO_SON_HERRAMIENTAS:
            return False
        return super()._matches_tool_filter(tool_call)


def limites(arq: Arquitectura) -> list:
    """Los techos. `exit_behavior="continue"` bloquea la herramienta y deja que
    el modelo cierre: recibe un ToolMessage diciendo que la llamada fue
    bloqueada y tiene que responder con lo que tenga (el prompt le dice cómo:
    fuente='ninguna'). Con "end" no habría respuesta estructurada."""
    return [
        LimiteDeHerramientas(run_limit=arq.max_llamadas,
                             exit_behavior="continue"),
        ToolCallLimitMiddleware(tool_name="read_section",
                                run_limit=arq.max_read_section,
                                exit_behavior="continue"),
        # Acota también el bucle modelo→verificador→modelo, que no gasta
        # herramientas y por tanto el de arriba no lo ve.
        ModelCallLimitMiddleware(run_limit=arq.max_vueltas_modelo,
                                exit_behavior="end"),
    ]


# ---------------------------------------------------------------------------
# 2. Verificador de cifras — el middleware que pide el §4.2 del enunciado
# ---------------------------------------------------------------------------
def _ya_corregido(state: AgentState, marca: str) -> bool:
    for m in state.get("messages", []):
        contenido = getattr(m, "content", None)
        if isinstance(contenido, str) and marca in contenido:
            return True
    return False


def _es_porcentaje(unidad: str | None) -> bool:
    return bool(unidad) and bool(re.search(r"%|porcent|percent|pp\b|puntos",
                                           unidad, re.IGNORECASE))


@after_model(can_jump_to=["model"])
def verificar_cifras_contra_xbrl(state: AgentState,
                                 runtime: Runtime) -> dict | None:
    """Si la respuesta afirma una cifra, tiene que existir tal cual (±1 %) entre
    los hechos XBRL de ese ticker y ejercicio. Si no, se le devuelve al modelo
    QUÉ afirmó y QUÉ hay reportado, y se le obliga a otra vuelta."""
    r = state.get("structured_response")
    if r is None or getattr(r, "cifra", None) is None:
        return None
    if not r.ticker or not r.ejercicio:
        return None
    if _es_porcentaje(r.unidad):
        return None                     # los porcentajes no son hechos XBRL
    if _ya_corregido(state, MARCA_CIFRA):
        return None                     # una corrección por invocación

    from agente.corpus import cargar_xbrl   # perezoso: no cargar si no hace falta
    xbrl = cargar_xbrl()
    hechos = xbrl[(xbrl.ticker == r.ticker.upper())
                  & (xbrl.fiscal_year == int(r.ejercicio))]
    if hechos.empty:
        return None                     # no hay contra qué comparar

    if any(cuadra(float(r.cifra), float(v)) for v in hechos["value"]):
        return None                     # cuadra con algún hecho: todo bien

    lista = "\n".join(f"  - {h.concept} = {formatear_valor(h.value, h.unit)} {h.unit}"
                      for h in hechos.itertuples())
    aviso = (
        f"[{MARCA_CIFRA}] Has afirmado cifra={r.cifra:,.2f} "
        f"({r.unidad or 'sin unidad'}) para {r.ticker} FY{r.ejercicio}, pero "
        f"NINGÚN hecho XBRL de esa compañía y ejercicio coincide (tolerancia "
        f"1 %). Los hechos reportados son:\n{lista}\n\n"
        f"Corrige la respuesta: usa exactamente uno de esos valores obtenido "
        f"con get_xbrl_fact (la cifra del ejercicio preguntado; si la pregunta "
        f"es una variación, pon en `cifra` el valor del ejercicio más reciente "
        f"y explica la variación en `respuesta`). Si el dato que te piden no "
        f"está en esa lista, responde fuente='ninguna' con cifra=null. No "
        f"estimes ni redondees a otra magnitud."
    )
    return {"messages": [{"role": "user", "content": aviso}],
            "jump_to": "model"}


# ---------------------------------------------------------------------------
# 3. Verificador de cita — simétrico al anterior, para el texto
# ---------------------------------------------------------------------------
_LONGITUD_CITA = 120


@after_model(can_jump_to=["model"])
def verificar_cita(state: AgentState, runtime: Runtime) -> dict | None:
    """Si cita un chunk_id, tiene que existir y contener la cita (primeros
    ~120 caracteres, normalizados). Cierra las citas inventadas ANTES de que
    las cace el evaluador."""
    r = state.get("structured_response")
    if r is None or not getattr(r, "chunk_id", None):
        return None
    if _ya_corregido(state, MARCA_CITA):
        return None

    from agente.corpus import cargar_chunks
    por_id = {c["chunk_id"]: c for c in cargar_chunks()}
    fragmento = por_id.get(r.chunk_id)

    if fragmento is None:
        aviso = (
            f"[{MARCA_CITA}] El chunk_id {r.chunk_id!r} NO existe en el corpus. "
            f"Solo puedes citar identificadores que hayan aparecido entre "
            f"corchetes en un resultado de search_filings (formato "
            f"TICKER-AÑO-ITEM-NNNN). Vuelve a buscar y cita uno real, o "
            f"responde fuente='ninguna' con chunk_id=null."
        )
        return {"messages": [{"role": "user", "content": aviso}],
                "jump_to": "model"}

    if r.cita:
        objetivo = normalizar(r.cita)[:_LONGITUD_CITA]
        if objetivo and objetivo not in normalizar(fragmento["texto"]):
            muestra = fragmento["texto"][:400].replace("\n", " ")
            aviso = (
                f"[{MARCA_CITA}] La cita que das no aparece en el fragmento "
                f"{r.chunk_id}. La cita debe ser TEXTO LITERAL del fragmento, "
                f"copiado sin cambios (en inglés, tal y como está en el "
                f"informe). El fragmento empieza así:\n«{muestra}…»\n\n"
                f"Corrige `cita` copiando una frase literal de ese fragmento, o "
                f"cambia `chunk_id` al fragmento del que de verdad la sacaste."
            )
            return {"messages": [{"role": "user", "content": aviso}],
                    "jump_to": "model"}
    return None


# ---------------------------------------------------------------------------
# 4. Filtros forzados — el modelo suele olvidar ticker y fiscal_year
# ---------------------------------------------------------------------------
_NOMBRES = {
    "NVDA": r"\bnvidia\b|\bnvda\b",
    "MSFT": r"\bmicrosoft\b|\bmsft\b",
    "AAPL": r"\bapple\b|\baapl\b",
    "GOOGL": r"\balphabet\b|\bgoogle\b|\bgoogl\b",
    "META": r"\bmeta\b|\bfacebook\b",
    "AMZN": r"\bamazon\b|\bamzn\b",
}
_ANIO = re.compile(r"\b(?:fy\s?)?(20(?:24|25))\b", re.IGNORECASE)

# Palabras de la pregunta que delatan la sección. Medido sobre el golden set:
# restringir la búsqueda al item correcto es el filtro que más mueve el recall
# (BM25 en español: 21 % → 57 % solo con este filtro), porque nadie escribe
# «7A» en su pregunta y sin él 37 fragmentos compiten con 1.749.
_ITEMS = {
    "1A": r"riesgo|risk|competen|competitiv|antimonopol|antitrust|demanda|litig|"
          r"regula|\bdma\b|desastre|catástrof|amenaza|ciberseg|sanci|control(es)? de export",
    "7A": r"divisa|tipo de cambio|cambiario|tipos? de inter|sensibilidad|riesgo de mercado|"
          r"cartera de (inversion|valores)|exposición a",
    "7":  r"crec|aument|dismin|baj[óo]|vari|evoluc|explica|md&a|discusi|inversi[oó]n en capital|"
          r"capex|gastos? de capital|anticipa|prev[eé]|guía|guidance|margen|resultados?",
    "8":  r"split|desdoblamiento|estados financieros|dividendo|acciones en circulaci|"
          r"balance|notas? a los estados",
}


def inferir_filtros(pregunta: str) -> dict:
    """ticker, fiscal_year e item que la pregunta delata, SOLO si son únicos.

    Si la pregunta menciona dos compañías o dos ejercicios (una comparativa),
    no se fuerza ese campo: el modelo tiene que buscar por separado. El item
    solo se infiere cuando una única sección encaja con las palabras.
    """
    texto = pregunta.lower()
    tickers = [t for t, patron in _NOMBRES.items() if re.search(patron, texto)]
    anios = sorted({int(a) for a in _ANIO.findall(pregunta)})
    items = [it for it, patron in _ITEMS.items() if re.search(patron, texto)]
    filtros: dict = {}
    if len(tickers) == 1:
        filtros["ticker"] = tickers[0]
    if len(anios) == 1:
        filtros["fiscal_year"] = anios[0]
    if len(items) == 1:
        filtros["item"] = items[0]
    return filtros


def _pregunta_del_usuario(state) -> str:
    mensajes = state.get("messages", []) if isinstance(state, dict) else []
    for m in mensajes:
        if type(m).__name__ == "HumanMessage" and isinstance(m.content, str):
            return m.content
    return ""


def _busquedas_previas(state) -> int:
    """Cuántas search_filings lleva ya esta invocación."""
    n = 0
    mensajes = state.get("messages", []) if isinstance(state, dict) else []
    for m in mensajes:
        for tc in getattr(m, "tool_calls", None) or []:
            if tc.get("name") == "search_filings":
                n += 1
    return max(n - 1, 0)          # la llamada actual ya está en el último AIMessage


@wrap_tool_call
def forzar_filtros(request, handler):
    """Si search_filings llega sin ticker o sin fiscal_year y la pregunta los
    menciona sin ambigüedad, se rellenan. El item solo se fuerza en la PRIMERA
    búsqueda de la invocación: si la inferencia falla y no sale nada, el modelo
    conserva el control en las siguientes. No se sobreescribe lo que el modelo
    ya puso."""
    if request.tool_call["name"] != "search_filings":
        return handler(request)
    args = dict(request.tool_call["args"])
    inferidos = inferir_filtros(_pregunta_del_usuario(request.state))
    if _busquedas_previas(request.state) > 0:
        inferidos.pop("item", None)
    cambiado = False
    for clave, valor in inferidos.items():
        if args.get(clave) in (None, "", 0):
            args[clave] = valor
            cambiado = True
    if not cambiado:
        return handler(request)
    return handler(request.override(tool_call={**request.tool_call, "args": args}))


# ---------------------------------------------------------------------------
# Montaje según la arquitectura
# ---------------------------------------------------------------------------
def middlewares_para(arq: Arquitectura) -> list:
    """La lista, EN ORDEN: primero los límites, luego los verificadores."""
    lista: list = []
    if arq.limites:
        lista += limites(arq)
    if arq.filtros_forzados:
        lista.append(forzar_filtros)
    if arq.verificador_cifras:
        lista.append(verificar_cifras_contra_xbrl)
    if arq.verificador_cita:
        lista.append(verificar_cita)
    return lista


# Compatibilidad con el nombre que usaba `agente.py` antes.
def middlewares_mejoras() -> list:
    from agente.config import ARQUITECTURAS
    return middlewares_para(ARQUITECTURAS["final"])
