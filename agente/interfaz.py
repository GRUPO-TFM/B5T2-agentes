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
from agente.resultado import herramientas_usadas, normalizar_resultado, tokens_de

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
def dir_resultados() -> Path:
    return raiz_repo() / "resultados"


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
def ejecutar(ruta_jsonl: str | Path, arq: str | Arquitectura = "final", rep: int = 1, *,
             modelo: str = MODELO, solo_ids: list[str] | None = None,
             forzar: bool = False, responder_fn=None, verbose: bool = True) -> Path:
    """Corre el agente sobre el JSONL y guarda UN JSON crudo por pregunta.

    Idempotente: si `crudo/<id>.json` ya existe y no se pide `forzar`, se salta.
    Así una ejecución cortada se relanza y sigue donde estaba, y las que dieron
    excepción se pueden repetir solas con `solo_ids`.

    `responder_fn` permite inyectar un responder falso (tests) o el de otro.
    """
    a = arquitectura(arq)
    carpeta = dir_rep(a, rep) / "crudo"
    carpeta.mkdir(parents=True, exist_ok=True)

    config = {**a.como_dict(), "modelo": modelo, "commit": _commit_actual(),
              "golden_set": str(ruta_jsonl), "fecha": datetime.now().isoformat(timespec="seconds")}
    (dir_arquitectura(a) / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    preguntas = leer_golden(ruta_jsonl)
    if solo_ids:
        preguntas = [p for p in preguntas if p.get("id") in set(solo_ids)]
    fn = responder_fn or responder

    for i, item in enumerate(preguntas, 1):
        destino = carpeta / f"{item['id']}.json"
        if destino.is_file() and not forzar:
            if verbose:
                print(f"  [{i}/{len(preguntas)}] {item['id']} · ya existe, salto", flush=True)
            continue
        if verbose:
            print(f"  [{i}/{len(preguntas)}] {item['id']} …", end=" ", flush=True)
        thread_id = f"{a.nombre}-rep{rep}-{item['id']}"     # la rep DENTRO del hilo
        registro: dict = {"item": item, "rep": rep, "thread_id": thread_id}
        try:
            r = fn(item["pregunta"], thread_id=thread_id, arquitectura=a.nombre, modelo=modelo)
            registro["resultado"] = normalizar_resultado(
                r, modelo=modelo, arquitectura=a.nombre,
                coste_usd=r.get("coste_usd"), latencia_s=r.get("latencia_s"))
            if verbose:
                sr = registro["resultado"]["structured_response"] or {}
                print(f"{registro['resultado']['latencia_s']:.1f}s · "
                      f"{registro['resultado']['coste_usd']*100:.2f}¢ · "
                      f"{registro['resultado']['n_llamadas']} llamadas · fuente={sr.get('fuente')}",
                      flush=True)
        except Exception as e:                      # noqa: BLE001 — se registra, no se pierde la fila
            registro["error"] = f"{type(e).__name__}: {e}"
            if verbose:
                print(f"ERROR {registro['error'][:80]}", flush=True)
        destino.write_text(json.dumps(registro, ensure_ascii=False, indent=1, default=str),
                           encoding="utf-8")
    return carpeta


# ---------------------------------------------------------------------------
# puntuar — sin API
# ---------------------------------------------------------------------------
def _fila(registro: dict, arq: Arquitectura, con_recall: bool) -> dict:
    item = registro["item"]
    fila = {"id": item.get("id"), "familia": item.get("familia"), "ticker": item.get("ticker"),
            "arquitectura": arq.nombre, "rep": registro.get("rep")}
    if "error" in registro:
        fila["error"] = registro["error"]
        for nombre in EVALUADORES:
            fila[nombre] = False if nombre != "honestidad" else None
        fila["acierto"] = False
        return fila

    r = registro["resultado"]
    sr = r.get("structured_response") or {}
    fila.update({
        "respuesta": sr.get("respuesta"), "cifra": sr.get("cifra"), "unidad": sr.get("unidad"),
        "ejercicio": sr.get("ejercicio"), "fuente": sr.get("fuente"),
        "cita": sr.get("cita"), "chunk_id": sr.get("chunk_id"),
        "herramientas": " → ".join(r.get("herramientas", [])),
        "n_llamadas": r.get("n_llamadas"),
        "tokens_in": r.get("tokens_in"), "tokens_out": r.get("tokens_out"),
        "coste_usd": r.get("coste_usd"), "latencia_s": r.get("latencia_s"),
        "limite_alcanzado": r.get("limite_alcanzado"),
        "correcciones": len(r.get("correcciones", [])),
        "sin_respuesta": sr == {},
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


def puntuar(arq: str | Arquitectura = "final", rep: int = 1, *,
            con_recall: bool = True) -> pd.DataFrame:
    """Lee `crudo/`, aplica los evaluadores y escribe `tabla.csv`."""
    a = arquitectura(arq)
    carpeta = dir_rep(a, rep) / "crudo"
    ficheros = sorted(carpeta.glob("*.json"))
    if not ficheros:
        raise FileNotFoundError(f"No hay crudo en {carpeta}. Ejecuta primero.")
    filas = [_fila(json.loads(f.read_text(encoding="utf-8")), a, con_recall) for f in ficheros]
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
    }
    for fam in FAMILIAS:
        sub = tabla[tabla["familia"] == fam] if "familia" in tabla else tabla.iloc[0:0]
        fila[f"acierto {fam}"] = _tasa(sub, "acierto")
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
        for fam in FAMILIAS:
            por_familia.append({"arquitectura": a.nombre, "familia": fam,
                                "acierto": float(media[f"acierto {fam}"])})
    comp = pd.DataFrame(filas)
    if escribir and not comp.empty:
        dir_resultados().mkdir(parents=True, exist_ok=True)
        comp.to_csv(dir_resultados() / "comparativa.csv", index=False)
        pd.DataFrame(por_familia).to_csv(dir_resultados() / "comparativa_por_familia.csv", index=False)
        (dir_resultados() / "comparativa.md").write_text(_markdown(comp), encoding="utf-8")
    return comp


_MAYOR_MEJOR = {"acierto", "cita", "cifra", "trayectoria", "recall@5",
                "acierto numerica", "acierto extractiva", "acierto comparativa"}
_MENOR_MEJOR = {"coste medio (¢)", "latencia media (s)", "llamadas/pregunta", "errores"}


def _markdown(comp: pd.DataFrame) -> str:
    """La tabla del informe con el mejor valor de cada columna en negrita."""
    columnas = ["arquitectura", "reps", "acierto", "acierto numerica", "acierto extractiva",
                "acierto comparativa", "cita", "cifra", "trayectoria", "recall@5",
                "coste medio (¢)", "latencia media (s)", "llamadas/pregunta", "% fuente=ninguna"]
    columnas = [c for c in columnas if c in comp]
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
