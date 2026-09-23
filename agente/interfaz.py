"""Punto de entrada del §6 — `responder(pregunta)` y `evaluar(ruta_jsonl)` — y el
harness de evaluación que hay detrás.

Principio: una invocación del agente se ejecuta UNA vez y se guarda entera.
Todo lo demás se deriva de lo guardado sin volver a llamar a la API:

    ejecutar(ruta_jsonl, arquitectura, rep)   # API. Escribe crudo/<id>.json. Idempotente.
    puntuar(arquitectura, rep)                # Sin API. Lee crudo/, aplica evaluadores → tabla.csv
    comparar()                                # Sin API. Todas las tabla.csv → comparativa.csv/.md

`evaluar(ruta_jsonl)` es la fachada: ejecutar + puntuar sobre la arquitectura
final. Es lo que corre el día 24 sobre `holdout.jsonl`.

Carpetas:
    resultados/agente/<arquitectura>/config.json
    resultados/agente/<arquitectura>/rep<n>/crudo/<id>.json
    resultados/agente/<arquitectura>/rep<n>/tabla.csv
    resultados/agente/<arquitectura>/resumen.csv
    resultados/comparativa.csv · comparativa_por_familia.csv · comparativa.md
"""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from agente.agente import construir_agente
from agente.config import ARQUITECTURAS, MODELO, REPETICIONES, Arquitectura, arquitectura
from agente.corpus import raiz_repo
from agente.evaluadores import EVALUADORES, acierto
from agente.resultado import (_correcciones, _limite_alcanzado, _reintentos_esquema,
                              herramientas_usadas, normalizar_resultado, tokens_de)

# USD por millón de tokens (entrada, salida). Los del profesor, consultados el
# 2/09/2026 en https://openrouter.ai/api/v1/models. REVISAR LA VÍSPERA.
PRECIOS_OPENROUTER = {
    "google/gemini-3.5-flash-lite": (0.30, 2.50),
    "google/gemini-3.8-flash": (0.75, 3.75),
    "anthropic/claude-opus-5": (5.00, 25.00),
    "anthropic/claude-fable-5.1": (10.00, 50.00),
}

FAMILIAS = ("numerica", "extractiva", "comparativa")


def coste_de(resultado, modelo: str = MODELO) -> float:
    nombre = modelo.split(":", 1)[-1]
    if nombre not in PRECIOS_OPENROUTER:
        return 0.0
    p_in, p_out = PRECIOS_OPENROUTER[nombre]
    entrada, salida = tokens_de(resultado)
    return (entrada * p_in + salida * p_out) / 1e6


# ---------------------------------------------------------------------------
# calentar — que el arranque no se cuele dentro de una pregunta medida
# ---------------------------------------------------------------------------
# La primera llamada a `search_filings` de un proceso carga el índice FAISS y el
# modelo de embeddings desde disco: ~15-20 s que, sin esto, se suman a la
# latencia de la pregunta que tuvo la mala suerte de ser la primera en buscar.
# Peor aún: como el proceso sobrevive entre repeticiones, solo la rep 1 los
# paga, y eso aparece como varianza entre repeticiones que no es del modelo.
_MODELO_EMBEDDINGS_CACHE = "models--BAAI--bge-small-en-v1.5"


def _embeddings_en_cache() -> bool:
    """¿Está el modelo ya descargado en la caché de Hugging Face?"""
    import os
    base = Path(os.environ.get("HF_HOME") or (Path.home() / ".cache" / "huggingface"))
    return any((base / "hub").glob(f"{_MODELO_EMBEDDINGS_CACHE}*"))


def calentar(*, offline_si_cacheado: bool = True, hibrido: bool = False,
             verbose: bool = True) -> bool:
    """Carga el índice y el codificador ANTES de empezar a cronometrar.

    Idempotente y barata a partir de la segunda vez (`_indice` tiene lru_cache).
    Nunca lanza: si el codificador no se puede cargar, avisa y devuelve False —
    el agente seguirá funcionando y pagará la carga en su primera búsqueda.

    `offline_si_cacheado` pone HF_HUB_OFFLINE=1 cuando el modelo ya está en la
    caché local: quita el aviso de peticiones anónimas, ahorra un viaje de red
    por arranque y, sobre todo, hace que la ejecución no dependa de que Hugging
    Face esté disponible. En un clon recién hecho (sin caché) NO se activa, para
    que la primera descarga funcione con normalidad.
    """
    import os
    if offline_si_cacheado and "HF_HUB_OFFLINE" not in os.environ and _embeddings_en_cache():
        os.environ["HF_HUB_OFFLINE"] = "1"
    comienzo = time.perf_counter()
    try:
        from agente.retrieval import _indice
        indice, meta, _ = _indice()
    except Exception as e:                                  # noqa: BLE001
        if verbose:
            print(f"  aviso: no se pudo precargar el retrieval ({type(e).__name__}: "
                  f"{e}). La primera búsqueda pagará la carga.", flush=True)
        return False
    if hibrido:
        # El índice BM25 se construye en la primera búsqueda híbrida: también
        # fuera del cronómetro, por la misma razón que el FAISS.
        try:
            from agente.recall import _bm25
            _bm25()
        except Exception as e:                              # noqa: BLE001
            if verbose:
                print(f"  aviso: no se pudo precargar BM25 ({type(e).__name__}: {e}).",
                      flush=True)
    if verbose:
        print(f"  retrieval precargado: {indice.ntotal} vectores, "
              f"{len(meta)} fragmentos{' + BM25' if hibrido else ''} "
              f"({time.perf_counter() - comienzo:.1f} s)", flush=True)
    return True


# ---------------------------------------------------------------------------
# responder — la firma del §6
# ---------------------------------------------------------------------------
def responder(pregunta: str, thread_id: str | None = None, *,
              arquitectura: str | Arquitectura = "final",
              modelo: str = MODELO, mejoras: bool | None = None) -> dict:
    """Pregunta in, dict con `structured_response`, `coste_usd` y `latencia_s` out.

    `mejoras` se acepta por compatibilidad: True equivale a arquitectura="final",
    False a "baseline".
    """
    if mejoras is True:
        arquitectura = "final"
    elif mejoras is False:
        arquitectura = "baseline"
    agente = construir_agente(modelo, arquitectura=arquitectura)
    comienzo = time.perf_counter()
    resultado = agente.invoke(
        {"messages": [{"role": "user", "content": pregunta}]},
        config={"configurable": {"thread_id": thread_id or "default"}},
    )
    segundos = time.perf_counter() - comienzo
    return {**resultado, "coste_usd": coste_de(resultado, modelo), "latencia_s": segundos}


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
# Un golden set distinto va a una carpeta distinta: así las tablas de A4 sobre
# las 20 preguntas del golden original no se mezclan con las de A4 sobre las 15
# adversarias. El notebook lo cambia antes de ejecutar; el valor por defecto
# es el de siempre y `evaluar()` no lo toca.
CARPETA_RESULTADOS = "resultados"


def dir_resultados() -> Path:
    return raiz_repo() / CARPETA_RESULTADOS


def dir_arquitectura(arq: str | Arquitectura) -> Path:
    return dir_resultados() / "agente" / arquitectura(arq).nombre


def dir_rep(arq: str | Arquitectura, rep: int) -> Path:
    return dir_arquitectura(arq) / f"rep{rep}"


def leer_golden(ruta_jsonl: str | Path) -> list[dict]:
    ruta = Path(ruta_jsonl)
    if not ruta.is_absolute() and not ruta.is_file():
        ruta = raiz_repo() / ruta
    if not ruta.is_file():
        raise FileNotFoundError(f"No encuentro el golden set: {ruta}")
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def _commit_actual() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=raiz_repo(), text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# ejecutar — la única función que gasta API
# ---------------------------------------------------------------------------
# Un 400/429/5xx del proveedor NO es el agente fallando: es la red. Si se cuenta
# como fallo, la tabla mezcla dos cosas que no tienen nada que ver. Por eso se
# reintenta UNA vez (en un hilo nuevo, para no reanudar un checkpoint a medias)
# y se apunta el reintento como instrumentación (`reintentos_proveedor`).
# 401/402/403 (clave, crédito) no se reintentan: repetir no arregla nada.
REINTENTOS_PROVEEDOR = 1
_CODIGOS_REINTENTABLES = {400, 408, 409, 425, 429, 500, 502, 503, 504, 529}

# El modelo puede cerrar la invocación con un turno VACÍO —sin texto y sin tool
# call— y entonces `create_agent` termina sin `structured_response`: la pregunta
# se pierde entera, sin excepción que lo avise. Medido en A4: 2 de 60 (3,3 %).
# No es red ni límite ni retrieval; es el modelo gastando el turno en razonar.
# Se trata igual que un 400: un reintento en un hilo nuevo.
MARCA_SIN_RESPUESTA = "SinRespuestaEstructurada"
_AVISO_SIN_RESPUESTA = ("el modelo cerró la invocación sin salida estructurada "
                        "(turno vacío, sin texto ni llamada a herramienta)")


def _describir_error(e: Exception) -> dict:
    """Todo lo que la excepción sepa. El `body` de OpenRouter lleva dentro el
    error real del proveedor (Google), que es lo que hay que leer para
    diagnosticar: `str(e)` se queda en «Provider returned error»."""
    d = {"tipo": type(e).__name__, "texto": f"{type(e).__name__}: {e}"}
    codigo = getattr(e, "status_code", None)
    if codigo is not None:
        d["status_code"] = codigo
    cuerpo = getattr(e, "body", None)
    if cuerpo:
        d["body"] = str(cuerpo)[:3000]
    return d


def _es_reintentable(e: Exception) -> bool:
    return getattr(e, "status_code", None) in _CODIGOS_REINTENTABLES


def _reparable(destino: Path) -> dict | None:
    """El registro guardado si hay que repetirlo; None si es bueno.

    Se repite lo que no dejó respuesta: una excepción (no hay `resultado`) o un
    turno vacío (hay `resultado` pero sin `structured_response`). Una respuesta
    equivocada NO es reparable: eso es una medición, y se respeta."""
    try:
        reg = json.loads(destino.read_text(encoding="utf-8"))
    except Exception:                                       # noqa: BLE001
        return {"error": "fichero ilegible"}
    if "resultado" not in reg:
        return reg
    if not (reg["resultado"] or {}).get("structured_response"):
        return reg
    return None


def ejecutar(ruta_jsonl: str | Path, arq: str | Arquitectura = "final", rep: int = 1, *,
             modelo: str = MODELO, solo_ids: list[str] | None = None,
             solo_familia: str | None = None,
             forzar: bool = False, reintentar_errores: bool = True,
             responder_fn=None, verbose: bool = True) -> Path:
    """Corre el agente sobre el JSONL y guarda UN JSON crudo por pregunta.

    Idempotente: si `crudo/<id>.json` ya existe y no se pide `forzar`, se salta.
    Excepción: un JSON que no dejó respuesta —porque hubo excepción o porque el
    modelo cerró con un turno vacío— se REPITE al volver a pasar, salvo
    `reintentar_errores=False`; los fallos anteriores se conservan en
    `intentos_fallidos` para que nada se pierda. Una respuesta EQUIVOCADA no se
    repite nunca: eso es una medición.

    `responder_fn` permite inyectar un responder falso (tests) o el de otro.
    """
    a = arquitectura(arq)
    carpeta = dir_rep(a, rep) / "crudo"
    carpeta.mkdir(parents=True, exist_ok=True)

    config = {**a.como_dict(), "modelo": modelo, "commit": _commit_actual(),
              "golden_set": str(ruta_jsonl), "fecha": datetime.now().isoformat(timespec="seconds")}
    (dir_arquitectura(a) / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    # `config.json` solo guarda la ÚLTIMA pasada. El historial guarda todas:
    # es lo que permite reconciliar resultados hechos en días y commits distintos.
    with open(dir_arquitectura(a) / "config_historial.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({**config, "rep": rep}, ensure_ascii=False) + "\n")

    preguntas = leer_golden(ruta_jsonl)
    if solo_ids:
        preguntas = [p for p in preguntas if p.get("id") in set(solo_ids)]
    if solo_familia:
        # Para ablaciones dirigidas: aislar el verificador de cifras solo
        # necesita las preguntas que llevan cifra. Ahorra un tercio de llamadas.
        preguntas = [p for p in preguntas if p.get("familia") == solo_familia]
    fn = responder_fn or responder

    # Fuera del bucle a propósito: la carga del codificador no debe caer dentro
    # de la latencia de ninguna pregunta. Ver `calentar()`.
    if responder_fn is None:
        calentar(hibrido=a.hibrido, verbose=verbose)

    for i, item in enumerate(preguntas, 1):
        destino = carpeta / f"{item['id']}.json"
        intentos: list[dict] = []                    # errores previos + de esta pasada
        if destino.is_file() and not forzar:
            previo = _reparable(destino) if reintentar_errores else None
            if previo is None:
                if verbose:
                    print(f"  [{i}/{len(preguntas)}] {item['id']} · ya existe, salto", flush=True)
                continue
            intentos = list(previo.get("intentos_fallidos") or [])
            if previo.get("error") and not any(x.get("texto") == previo["error"] for x in intentos):
                intentos.append({"texto": previo["error"]})
            if verbose:
                print(f"  [{i}/{len(preguntas)}] {item['id']} · tenía error, se repite …",
                      end=" ", flush=True)
        elif verbose:
            print(f"  [{i}/{len(preguntas)}] {item['id']} …", end=" ", flush=True)

        base_hilo = f"{a.nombre}-rep{rep}-{item['id']}"     # la rep DENTRO del hilo
        registro: dict = {"item": item, "rep": rep, "thread_id": base_hilo,
                          "commit": config["commit"],
                          "fecha": datetime.now().isoformat(timespec="seconds")}
        # Los intentos ya gastados (de pasadas anteriores) cuentan para el hilo:
        # así el hilo del reintento nunca coincide con uno que ya se usó.
        gastados = len(intentos)
        for intento in range(1, REINTENTOS_PROVEEDOR + 2):
            n_hilo = gastados + intento
            thread_id = base_hilo if n_hilo == 1 else f"{base_hilo}-intento{n_hilo}"
            registro["thread_id"] = thread_id
            try:
                r = fn(item["pregunta"], thread_id=thread_id, arquitectura=a.nombre, modelo=modelo)
                registro["resultado"] = normalizar_resultado(
                    r, modelo=modelo, arquitectura=a.nombre,
                    coste_usd=r.get("coste_usd"), latencia_s=r.get("latencia_s"))
                registro.pop("error", None)
                if not registro["resultado"].get("structured_response"):
                    # Turno vacío: no hay nada que puntuar. Se reintenta.
                    intentos.append({"tipo": MARCA_SIN_RESPUESTA,
                                     "texto": f"{MARCA_SIN_RESPUESTA}: {_AVISO_SIN_RESPUESTA}"})
                    if intento <= REINTENTOS_PROVEEDOR:
                        if verbose:
                            print("sin respuesta estructurada, reintento …",
                                  end=" ", flush=True)
                        registro.pop("resultado", None)
                        time.sleep(1.0)
                        continue
                    # Agotado: se GUARDA el resultado vacío tal cual. Es un fallo
                    # real y la tabla tiene que verlo, no esconderlo.
                    if verbose:
                        print(f"SIN RESPUESTA tras {intento} intentos", flush=True)
                    break
                if verbose:
                    sr = registro["resultado"]["structured_response"] or {}
                    print(f"{registro['resultado']['latencia_s']:.1f}s · "
                          f"{registro['resultado']['coste_usd']*100:.2f}¢ · "
                          f"{registro['resultado']['n_llamadas']} llamadas · "
                          f"fuente={sr.get('fuente')}", flush=True)
                break
            except Exception as e:                  # noqa: BLE001 — se registra, no se pierde la fila
                detalle = _describir_error(e)
                intentos.append(detalle)
                if intento <= REINTENTOS_PROVEEDOR and _es_reintentable(e):
                    if verbose:
                        print(f"error del proveedor ({detalle.get('status_code')}), "
                              f"reintento …", end=" ", flush=True)
                    time.sleep(2.0 * intento)
                    continue
                registro["error"] = detalle["texto"]
                if verbose:
                    print(f"ERROR {registro['error'][:80]}", flush=True)
                break
        if intentos:
            registro["intentos_fallidos"] = intentos
        destino.write_text(json.dumps(registro, ensure_ascii=False, indent=1, default=str),
                           encoding="utf-8")
    return carpeta


# ---------------------------------------------------------------------------
# puntuar — sin API
# ---------------------------------------------------------------------------
_PREFIJO_REESCRITA = "(consulta reescrita:"


def _busquedas_reescritas(mensajes) -> int:
    n = 0
    for m in mensajes:
        tipo = m.get("type") if isinstance(m, dict) else type(m).__name__
        nombre = m.get("name") if isinstance(m, dict) else getattr(m, "name", None)
        contenido = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
        if tipo in ("tool", "ToolMessage") and nombre == "search_filings" \
                and isinstance(contenido, str) and contenido.startswith(_PREFIJO_REESCRITA):
            n += 1
    return n


def _fila(registro: dict, arq: Arquitectura, con_recall: bool) -> dict:
    item = registro["item"]
    fila = {"id": item.get("id"), "familia": item.get("familia"), "ticker": item.get("ticker"),
            "arquitectura": arq.nombre, "rep": registro.get("rep")}
    # Reintentos por error del proveedor (400/429/5xx): instrumentación, no
    # veredicto. Una arquitectura que provoca más 400 que otra es un hallazgo.
    _fallidos = registro.get("intentos_fallidos") or []
    fila["reintentos_vacios"] = sum(1 for x in _fallidos
                                    if x.get("tipo") == MARCA_SIN_RESPUESTA)
    fila["reintentos_proveedor"] = len(_fallidos) - fila["reintentos_vacios"]
    if "error" in registro:
        fila["error"] = registro["error"]
        for nombre in EVALUADORES:
            fila[nombre] = False if nombre != "honestidad" else None
        fila["acierto"] = False
        return fila

    r = registro["resultado"]
    sr = r.get("structured_response") or {}
    llamadas = r.get("llamadas", [])
    busquedas = [c for c in llamadas if c["name"] == "search_filings"]
    mensajes = r.get("messages", [])
    marcas = _correcciones(mensajes)
    esperada = item.get("cifra_esperada")
    dada = sr.get("cifra")

    # OJO con los nombres: `cifra` y `cita` son a la vez campos de la respuesta
    # y nombres de evaluador. Si se llaman igual, el veredicto booleano pisa el
    # dato y la tabla miente. Por eso la respuesta va con sufijo `_dada`.
    fila.update({
        "respuesta": sr.get("respuesta"),
        "cifra_dada": dada, "cifra_esperada": esperada,
        "ratio_cifra": (dada / esperada) if (dada is not None and esperada) else None,
        "unidad": sr.get("unidad"), "ejercicio": sr.get("ejercicio"),
        "fuente": sr.get("fuente"),
        "cita_dada": sr.get("cita"), "chunk_id": sr.get("chunk_id"),
        "herramientas": " → ".join(r.get("herramientas", [])),
        "n_llamadas": r.get("n_llamadas"),
        "tokens_in": r.get("tokens_in"), "tokens_out": r.get("tokens_out"),
        "coste_usd": r.get("coste_usd"), "latencia_s": r.get("latencia_s"),
        "sin_respuesta": sr == {},
        # --- instrumentación: qué guardrail actuó, para atribuir sin ablación ---
        # Se RECALCULA desde los mensajes en vez de leer el valor que se guardó
        # al ejecutar. Es la promesa de «crudo primero»: lo derivado se deriva al
        # puntuar, así un detector corregido se aplica a lo ya guardado sin
        # repetir una sola llamada. (Pasó: el detector de límite daba falso
        # positivo con el texto de los 10-K.)
        "corrigio_cifra": any("CIFRA" in m for m in marcas),
        "corrigio_cita": any("CITA" in m for m in marcas),
        "reintentos_esquema": _reintentos_esquema(mensajes),
        "limite_alcanzado": _limite_alcanzado(mensajes),
        # --- instrumentación del retrieval: mide el efecto de forzar_filtros ---
        "n_busquedas": len(busquedas),
        "busquedas_con_ticker": sum(1 for c in busquedas if c["args"].get("ticker")),
        "busquedas_con_item": sum(1 for c in busquedas if c["args"].get("item")),
        "uso_read_section": any(c["name"] == "read_section" for c in llamadas),
        # a2: cuántas búsquedas cambió de verdad la reescritura (lo deja escrito
        # el propio ToolMessage de search_filings)
        "busquedas_reescritas": _busquedas_reescritas(mensajes),
    })
    veredictos = {nombre: ev(item, r) for nombre, ev in EVALUADORES.items()}
    fila.update(veredictos)
    fila["acierto"] = acierto(veredictos)

    if con_recall and item.get("ancla_texto"):
        try:
            from agente.recall import recuperar_para
            from agente.metricas import acierta, posicion_del_ancla
            ordenados = recuperar_para(item, arq, k=None)      # todo el orden
            fila["recall5"] = acierta(item, ordenados[:arq.k])
            fila["pos_ancla"] = posicion_del_ancla(item, ordenados)
        except Exception as e:                                  # noqa: BLE001
            fila["recall5"] = None
            fila["pos_ancla"] = None
            fila["recall_error"] = f"{type(e).__name__}: {e}"[:80]
    return fila


def _items_actuales(golden: str | Path | None) -> dict[str, dict] | None:
    return {g["id"]: g for g in leer_golden(golden)} if golden else None


def puntuar(arq: str | Arquitectura = "final", rep: int = 1, *,
            con_recall: bool = True, golden: str | Path | None = None) -> pd.DataFrame:
    """Lee `crudo/`, aplica los evaluadores y escribe `tabla.csv`.

    Cada JSON crudo guarda el ítem del golden TAL COMO ERA al ejecutar. Si el
    golden ha cambiado después (p. ej. el v2 del adversario añadió
    `cifras_aceptables`), sin `golden` se puntúa con la versión vieja. Con
    `golden`, se puntúa con la actual: los criterios de evaluación se
    actualizan, pero si cambió la PREGUNTA la respuesta ya no le corresponde y
    la fila sale marcada `obsoleta` (hay que repetirla con `forzar=True`).
    Los ids que ya no están en el golden no se puntúan."""
    a = arquitectura(arq)
    carpeta = dir_rep(a, rep) / "crudo"
    ficheros = sorted(carpeta.glob("*.json"))
    if not ficheros:
        raise FileNotFoundError(f"No hay crudo en {carpeta}. Ejecuta primero.")
    actuales = _items_actuales(golden)
    filas = []
    for f in ficheros:
        registro = json.loads(f.read_text(encoding="utf-8"))
        obsoleta = False
        if actuales is not None:
            nuevo = actuales.get(registro["item"].get("id"))
            if nuevo is None:
                continue
            obsoleta = nuevo.get("pregunta") != registro["item"].get("pregunta")
            if not obsoleta:
                registro["item"] = nuevo
        fila = _fila(registro, a, con_recall)
        fila["obsoleta"] = obsoleta
        filas.append(fila)
    tabla = pd.DataFrame(filas)
    tabla.to_csv(dir_rep(a, rep) / "tabla.csv", index=False)
    return tabla


# ---------------------------------------------------------------------------
# comparar — la tabla del informe
# ---------------------------------------------------------------------------
def _tasa(tabla: pd.DataFrame, columna: str) -> float:
    if columna not in tabla:
        return float("nan")
    v = tabla[columna].dropna()
    return float(v.astype(float).mean()) if len(v) else float("nan")


def resumir(tabla: pd.DataFrame, etiqueta: str) -> dict:
    """La fila de la tabla del informe (formato del profesor + por familia)."""
    fila = {
        "versión": etiqueta,
        "acierto": _tasa(tabla, "acierto"),
        "cita": _tasa(tabla, "cita"),
        "cifra": _tasa(tabla, "cifra"),
        "trayectoria": _tasa(tabla, "trayectoria"),
        "recall@5": _tasa(tabla, "recall5"),
        "coste medio (¢)": _tasa(tabla, "coste_usd") * 100,
        "latencia media (s)": _tasa(tabla, "latencia_s"),
        "llamadas/pregunta": _tasa(tabla, "n_llamadas"),
        "% fuente=ninguna": (float((tabla.get("fuente") == "ninguna").mean())
                             if "fuente" in tabla else float("nan")),
        "errores": int(tabla["error"].notna().sum()) if "error" in tabla else 0,
        "reintentos proveedor": int(tabla["reintentos_proveedor"].sum())
                                if "reintentos_proveedor" in tabla else 0,
        "reintentos por respuesta vacía": int(tabla["reintentos_vacios"].sum())
                                          if "reintentos_vacios" in tabla else 0,
        "% sin respuesta": _tasa(tabla, "sin_respuesta"),
        # Cuántas veces actuó cada guardrail. Uno que nunca salta no aportó nada
        # y se dice con el dato, sin gastar una ablación.
        "% corrigió cifra": _tasa(tabla, "corrigio_cifra"),
        "% corrigió cita": _tasa(tabla, "corrigio_cita"),
        "reintentos esquema": _tasa(tabla, "reintentos_esquema"),
        "% límite alcanzado": _tasa(tabla, "limite_alcanzado"),
        "% búsquedas reescritas": (tabla["busquedas_reescritas"].sum() / max(tabla["n_busquedas"].sum(), 1))
                                  if "busquedas_reescritas" in tabla else 0.0,
        "% búsquedas con ticker": (
            float(tabla["busquedas_con_ticker"].sum() / tabla["n_busquedas"].sum())
            if "n_busquedas" in tabla and tabla["n_busquedas"].sum() else float("nan")),
    }
    # Las tres familias del enunciado siempre (aunque den NaN), y detrás las que
    # traiga la tabla (honestidad, multi, multi_temporal…) en orden de aparición.
    familias = list(FAMILIAS)
    if "familia" in tabla:
        familias += [f for f in tabla["familia"].dropna().unique() if f not in familias]
    for fam in familias:
        sub = tabla[tabla["familia"] == fam] if "familia" in tabla else tabla.iloc[0:0]
        fila[f"acierto {fam}"] = _tasa(sub, "acierto")
    fila["honestidad"] = _tasa(tabla, "honestidad")
    return fila


def _tablas_de(a: Arquitectura) -> dict[int, pd.DataFrame]:
    salida = {}
    for carpeta in sorted(dir_arquitectura(a).glob("rep*")):
        f = carpeta / "tabla.csv"
        if f.is_file():
            salida[int(carpeta.name[3:])] = pd.read_csv(f)
    return salida


def comparar(arquitecturas: list[str] | None = None, *, escribir: bool = True) -> pd.DataFrame:
    """Una fila por arquitectura: media de las repeticiones, con el rango."""
    nombres = arquitecturas or [n for n in ARQUITECTURAS if n != "final"]
    filas, por_familia = [], []
    for nombre in nombres:
        a = arquitectura(nombre)
        tablas = _tablas_de(a)
        if not tablas:
            continue
        resumenes = pd.DataFrame([resumir(t, f"{a.nombre} rep{r}") for r, t in tablas.items()])
        if escribir:
            resumenes.to_csv(dir_arquitectura(a) / "resumen.csv", index=False)
        numericas = resumenes.drop(columns=["versión"])
        media = numericas.mean()
        fila = {"arquitectura": a.nombre, "reps": len(tablas), **media.to_dict()}
        if len(tablas) > 1:
            for col in ("acierto", "recall@5", "coste medio (¢)"):
                fila[f"{col} min"] = float(numericas[col].min())
                fila[f"{col} max"] = float(numericas[col].max())
        filas.append(fila)
        for col in media.index:
            if col.startswith("acierto ") and col not in ("acierto min", "acierto max"):
                por_familia.append({"arquitectura": a.nombre, "familia": col[len("acierto "):],
                                    "acierto": float(media[col])})
    comp = pd.DataFrame(filas)
    if escribir and not comp.empty:
        dir_resultados().mkdir(parents=True, exist_ok=True)
        comp.to_csv(dir_resultados() / "comparativa.csv", index=False)
        pd.DataFrame(por_familia).to_csv(dir_resultados() / "comparativa_por_familia.csv", index=False)
        (dir_resultados() / "comparativa.md").write_text(_markdown(comp), encoding="utf-8")
    return comp


_MAYOR_MEJOR = {"acierto", "cita", "cifra", "trayectoria", "honestidad", "recall@5",
                "acierto numerica", "acierto extractiva", "acierto comparativa",
                "acierto honestidad", "acierto multi", "acierto multi_temporal"}
_MENOR_MEJOR = {"coste medio (¢)", "latencia media (s)", "llamadas/pregunta", "errores"}


def _markdown(comp: pd.DataFrame) -> str:
    """La tabla del informe con el mejor valor de cada columna en negrita."""
    columnas = ["arquitectura", "reps", "acierto", "acierto numerica", "acierto extractiva",
                "acierto comparativa"]
    columnas += [c for c in comp.columns if c.startswith("acierto ") and c not in columnas
                 and not c.endswith((" min", " max"))]
    columnas += ["cita", "cifra", "trayectoria", "honestidad", "recall@5",
                 "coste medio (¢)", "latencia media (s)", "llamadas/pregunta", "% fuente=ninguna"]
    columnas = [c for c in columnas if c in comp and not comp[c].isna().all()]
    mejores = {}
    for c in columnas:
        if c in _MAYOR_MEJOR:
            mejores[c] = comp[c].max()
        elif c in _MENOR_MEJOR:
            mejores[c] = comp[c].min()

    def fmt(c, v):
        if pd.isna(v):
            return "—"
        if c in ("arquitectura",):
            return str(v)
        if c == "reps":
            return str(int(v))
        s = f"{v:.1%}" if c in _MAYOR_MEJOR or c == "% fuente=ninguna" else f"{v:.2f}"
        return f"**{s}**" if c in mejores and v == mejores[c] else s

    cab = "| " + " | ".join(columnas) + " |"
    sep = "|" + "|".join("---" for _ in columnas) + "|"
    filas = ["| " + " | ".join(fmt(c, r[c]) for c in columnas) + " |" for _, r in comp.iterrows()]
    nota = ("\n\nMedia de las repeticiones. Mejor valor de cada columna en negrita. "
            "recall@5 sobre las preguntas con ancla, con los filtros del golden set. "
            "Coste y latencia por pregunta.")
    return "\n".join([cab, sep, *filas]) + nota


# ---------------------------------------------------------------------------
# evaluar — la fachada del §6
# ---------------------------------------------------------------------------
def evaluar(ruta_jsonl: str | Path, responder=None, etiqueta: str = "",
            salida: str | Path | None = None, *,
            arquitectura: str | Arquitectura = "final", rep: int = 1,
            con_recall: bool = True) -> pd.DataFrame:
    """`evaluar("holdout.jsonl")`: ejecuta la arquitectura final sobre el JSONL,
    aplica los tres evaluadores y devuelve la tabla por pregunta.

    Los resultados quedan en `resultados/agente/<arquitectura>/rep<rep>/`. Con
    `etiqueta` se usa una arquitectura con ese nombre de carpeta (por ejemplo
    "holdout") sin cambiar la configuración de la final.
    """
    arq = arquitectura if isinstance(arquitectura, Arquitectura) else ARQUITECTURAS[arquitectura]
    if etiqueta:
        from dataclasses import replace
        arq = replace(arq, nombre=etiqueta)
        ARQUITECTURAS.setdefault(etiqueta, arq)
    ejecutar(ruta_jsonl, arq, rep, responder_fn=responder)
    tabla = puntuar(arq, rep, con_recall=con_recall)
    if salida:
        Path(salida).parent.mkdir(parents=True, exist_ok=True)
        tabla.to_csv(salida, index=False)
    return tabla


def ejecutar_todo(ruta_jsonl: str | Path, arq: str | Arquitectura, *,
                  reps: int = REPETICIONES, modelo: str = MODELO, con_recall: bool = True) -> pd.DataFrame:
    """`reps` repeticiones de una arquitectura, puntuadas, y la comparativa actualizada."""
    for rep in range(1, reps + 1):
        print(f"\n== {arquitectura(arq).nombre} · repetición {rep}/{reps} ==")
        ejecutar(ruta_jsonl, arq, rep, modelo=modelo)
        puntuar(arq, rep, con_recall=con_recall)
    return comparar()
