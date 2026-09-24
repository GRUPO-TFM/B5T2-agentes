"""Ejecución por lotes y reconciliación de resultados.

Dos órdenes, pensadas para lanzarse desde PowerShell en la raíz del repo:

    uv run python -m agente.lotes correr --plan           # qué falta, sin gastar
    uv run python -m agente.lotes correr                  # todas las arquitecturas, golden difícil, 1 rep
    uv run python -m agente.lotes correr --golden original --arqs a3_hibrido --reps 3
    uv run python -m agente.lotes reconciliar             # estado + tablas, incluido baseline vs final

`correr` nunca repite lo hecho: `ejecutar()` salta cada pregunta que ya tiene
respuesta guardada y solo repite las que no dejaron respuesta (error del
proveedor o turno vacío). Se puede cortar con Ctrl+C y volver a lanzar: sigue
donde se quedó.

`reconciliar` no llama al agente. Recorre las dos carpetas de resultados, dice
qué está completo, qué falta, qué se hizo con una configuración o un golden
distintos a los actuales, vuelve a puntuar TODO con el golden y los
evaluadores actuales («crudo primero»: la medición no se repite, la
puntuación sí) y escribe las tablas comparativas, una por golden y otra con los
dos lado a lado y baseline frente al alias `final`, en `resultados/reconciliacion/`.
El recall del golden difícil se mide también al repuntuar. Las consultas
reescritas se leen de la caché; si falta alguna, calcularla puede llamar al
modelo.
"""
from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from datetime import datetime

import pandas as pd

from agente import interfaz
from agente.config import ARQUITECTURAS, arquitectura

GOLDENS = {
    # clave: (ruta del golden, carpeta de resultados)
    "original": ("data/golden_set.jsonl", "resultados"),
    "dificil": ("data/golden_set_dificil.jsonl", "resultados_dificil"),
}
ORDEN = [n for n in ARQUITECTURAS if n != "final"]          # la escalera, en orden
_CAMPOS_NO_CONFIG = {"modelo", "commit", "golden_set", "fecha", "rep"}

# Si una arquitectura aún no tiene tabla, se estima con esto (medias de A4).
_LATENCIA_POR_DEFECTO_S = 45.0
_COSTE_POR_DEFECTO_USD = 0.016


@contextmanager
def carpeta_de(golden: str):
    """Apunta el harness a la carpeta de resultados de ese golden y la restaura."""
    anterior = interfaz.CARPETA_RESULTADOS
    interfaz.CARPETA_RESULTADOS = GOLDENS[golden][1]
    try:
        yield
    finally:
        interfaz.CARPETA_RESULTADOS = anterior


def _reps_en_disco(nombre: str) -> list[int]:
    d = interfaz.dir_arquitectura(nombre)
    return sorted(int(p.name[3:]) for p in d.glob("rep*") if p.name[3:].isdigit())


def _configs_usadas(nombre: str) -> list[dict]:
    """Todas las configuraciones con las que se ejecutó (historial, o el
    config.json de la última pasada si el historial aún no existía)."""
    d = interfaz.dir_arquitectura(nombre)
    hist = d / "config_historial.jsonl"
    if hist.is_file():
        return [json.loads(l) for l in hist.read_text(encoding="utf-8").splitlines() if l.strip()]
    unico = d / "config.json"
    return [json.loads(unico.read_text(encoding="utf-8"))] if unico.is_file() else []


def _config_cambiada(nombre: str) -> str:
    """Parámetros de la arquitectura que difieren entre lo ejecutado y lo actual."""
    actual = arquitectura(nombre).como_dict()
    distintos = set()
    for c in _configs_usadas(nombre):
        for k, v in c.items():
            if k not in _CAMPOS_NO_CONFIG and k in actual and actual[k] != v:
                distintos.add(f"{k}: {v!r}→{actual[k]!r}")
    return "; ".join(sorted(distintos))


def estado(golden: str, arqs: list[str] | None = None, reps: int | None = None) -> pd.DataFrame:
    """Una fila por arquitectura × repetición: qué hay en disco frente al golden actual."""
    ruta, _ = GOLDENS[golden]
    items = {g["id"]: g for g in interfaz.leer_golden(ruta)}
    filas = []
    with carpeta_de(golden):
        for nombre in arqs or ORDEN:
            reps_ = range(1, reps + 1) if reps else (_reps_en_disco(nombre) or [1])
            for rep in reps_:
                crudo = interfaz.dir_rep(nombre, rep) / "crudo"
                hechas, reparables, obsoletas, sobran, fechas, commits = [], [], [], [], [], set()
                for f in sorted(crudo.glob("*.json")) if crudo.is_dir() else []:
                    iid = f.stem
                    if iid not in items:
                        sobran.append(iid)
                        continue
                    if interfaz._reparable(f) is not None:
                        reparables.append(iid)
                        continue
                    reg = json.loads(f.read_text(encoding="utf-8"))
                    if reg["item"].get("pregunta") != items[iid].get("pregunta"):
                        obsoletas.append(iid)
                    hechas.append(iid)
                    fechas.append(reg.get("fecha")
                                  or datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds"))
                    if reg.get("commit"):
                        commits.add(reg["commit"])
                faltan = [i for i in items if i not in hechas and i not in reparables]
                filas.append({
                    "golden": golden, "arquitectura": nombre, "rep": rep,
                    "preguntas": len(items), "hechas": len(hechas),
                    "faltan": len(faltan), "reparables": len(reparables),
                    "obsoletas": len(obsoletas), "sobran": len(sobran),
                    "por_correr": len(faltan) + len(reparables),
                    "desde": min(fechas)[:16] if fechas else "",
                    "hasta": max(fechas)[:16] if fechas else "",
                    "commits": ",".join(sorted(commits)),
                    "config_cambiada": _config_cambiada(nombre),
                    "ids_faltan": " ".join(faltan), "ids_reparables": " ".join(reparables),
                    "ids_obsoletas": " ".join(obsoletas),
                })
    return pd.DataFrame(filas)


def _medias(golden: str, nombre: str) -> tuple[float, float]:
    """Latencia (s) y coste (USD) medios por pregunta de lo ya medido."""
    with carpeta_de(golden):
        tablas = [pd.read_csv(p) for p in interfaz.dir_arquitectura(nombre).glob("rep*/tabla.csv")]
    if not tablas:
        with carpeta_de("original"):       # misma arquitectura en el otro golden
            tablas = [pd.read_csv(p) for p in interfaz.dir_arquitectura(nombre).glob("rep*/tabla.csv")]
    if not tablas:
        return _LATENCIA_POR_DEFECTO_S, _COSTE_POR_DEFECTO_USD
    t = pd.concat(tablas)
    return float(t["latencia_s"].mean()), float(t["coste_usd"].mean())


def plan(golden: str, arqs: list[str], reps: int) -> pd.DataFrame:
    est = estado(golden, arqs, reps)
    lat, cos = zip(*(_medias(golden, n) for n in est["arquitectura"]))
    est["min_estimados"] = (est["por_correr"] * pd.Series(lat)).div(60).round(1)
    est["usd_estimados"] = (est["por_correr"] * pd.Series(cos)).round(2)
    return est


def _imprimir_plan(p: pd.DataFrame) -> None:
    cols = ["arquitectura", "rep", "preguntas", "hechas", "por_correr", "obsoletas",
            "min_estimados", "usd_estimados", "config_cambiada"]
    print(p[cols].to_string(index=False))
    print(f"\nTOTAL por correr: {int(p['por_correr'].sum())} preguntas · "
          f"~{p['min_estimados'].sum():.0f} min · ~{p['usd_estimados'].sum():.2f} $ "
          f"(estimación con las medias ya medidas)")
    if p["obsoletas"].sum():
        print("AVISO: hay respuestas a preguntas que han cambiado de enunciado "
              "(columna obsoletas). No se repiten solas: ver ids_obsoletas en "
              "`reconciliar` y repetirlas con forzar=True si procede.")


def correr(golden: str = "dificil", arqs: list[str] | None = None, reps: int = 1, *,
           solo_plan: bool = False, confirmar: bool = True, con_recall: bool | None = None) -> pd.DataFrame | None:
    arqs = arqs or ORDEN
    ruta, carpeta = GOLDENS[golden]
    con_recall = (golden == "original") if con_recall is None else con_recall
    p = plan(golden, arqs, reps)
    print(f"Golden: {ruta}  →  {carpeta}/\n")
    _imprimir_plan(p)
    if solo_plan:
        return None
    if int(p["por_correr"].sum()) == 0:
        print("\nNada que correr. Se vuelve a puntuar y a comparar.")
    elif confirmar and input("\n¿Lanzar? [s/N] ").strip().lower() not in ("s", "si", "sí", "y"):
        print("Cancelado.")
        return None

    with carpeta_de(golden):
        try:
            for nombre in arqs:
                for rep in range(1, reps + 1):
                    fila = p[(p.arquitectura == nombre) & (p.rep == rep)].iloc[0]
                    if fila["por_correr"]:
                        print(f"\n== {nombre} · rep {rep} · {fila['por_correr']} preguntas ==")
                        interfaz.ejecutar(ruta, nombre, rep)
                    interfaz.puntuar(nombre, rep, con_recall=con_recall, golden=ruta)
        except KeyboardInterrupt:
            print("\nInterrumpido. Lo guardado se conserva: vuelve a lanzar la misma "
                  "orden y seguirá donde se quedó.")
            return None
        comp = interfaz.comparar(arqs)
        md = interfaz.dir_resultados() / "comparativa.md"
        if md.is_file():
            print("\n" + md.read_text(encoding="utf-8"))
    return comp


# ---------------------------------------------------------------------------
# reconciliar — sin API
# ---------------------------------------------------------------------------
_COLS_LADO_A_LADO = ["reps", "acierto", "cita", "cifra", "trayectoria", "honestidad",
                     "recall@5", "coste medio (¢)", "latencia media (s)",
                     "llamadas/pregunta", "% límite alcanzado"]
_COLS_BASELINE_FINAL = ["recall@5", "coste medio (¢)", "latencia media (s)",
                        "llamadas/pregunta"]


def _repuntuar(golden: str, con_recall: bool) -> pd.DataFrame:
    ruta, _ = GOLDENS[golden]
    with carpeta_de(golden):
        nombres = []
        for nombre in ORDEN:
            reps = _reps_en_disco(nombre)
            for rep in reps:
                if any((interfaz.dir_rep(nombre, rep) / "crudo").glob("*.json")):
                    interfaz.puntuar(nombre, rep, con_recall=con_recall, golden=ruta)
            if reps:
                nombres.append(nombre)
        return interfaz.comparar(nombres) if nombres else pd.DataFrame()


def _fmt(v, col: str) -> str:
    if pd.isna(v):
        return "—"
    if col in ("reps",):
        return str(int(v))
    if col in ("coste medio (¢)", "latencia media (s)", "llamadas/pregunta"):
        return f"{v:.1f}" if col == "latencia media (s)" else f"{v:.2f}"
    return f"{v:.1%}"


def tabla_baseline_final(comp: pd.DataFrame, golden: str) -> pd.DataFrame:
    """Tabla breve del enunciado, usando el preset al que apunta `final`."""
    nombre_final = arquitectura("final").nombre
    nombres = ["baseline", nombre_final]
    if comp.empty or not set(nombres).issubset(set(comp["arquitectura"])):
        return pd.DataFrame()
    familias = list(dict.fromkeys(g["familia"] for g in interfaz.leer_golden(GOLDENS[golden][0])))
    columnas = ["arquitectura", "reps", "acierto"]
    columnas += [f"acierto {familia}" for familia in familias]
    columnas += _COLS_BASELINE_FINAL
    faltan = [c for c in columnas if c not in comp]
    if faltan:
        raise ValueError(f"Faltan métricas para {golden}: {faltan}")
    tabla = comp.set_index("arquitectura").loc[nombres, columnas[1:]].reset_index()
    return tabla


def _markdown_baseline_final(tabla: pd.DataFrame, golden: str) -> str:
    """Marca máximos de acierto/recall y mínimos de coste/latencia/llamadas."""
    nombre_final = arquitectura("final").nombre
    menores = {"coste medio (¢)", "latencia media (s)", "llamadas/pregunta"}
    porcentajes = {"acierto", "recall@5"} | {c for c in tabla if c.startswith("acierto ")}
    mejores = {c: tabla[c].min() if c in menores else tabla[c].max()
               for c in tabla if c not in ("arquitectura", "reps")}

    def celda(col, valor):
        if col == "arquitectura":
            return "final" if valor == nombre_final else str(valor)
        if col == "reps":
            return str(int(valor))
        if pd.isna(valor):
            return "—"
        forma = f"{valor:.1%}" if col in porcentajes else f"{valor:.2f}"
        return f"**{forma}**" if valor == mejores[col] else forma

    columnas = list(tabla.columns)
    lineas = [f"## Golden {golden}: baseline frente a final ({nombre_final})", "",
              "| " + " | ".join(columnas) + " |",
              "|" + "|".join("---" for _ in columnas) + "|"]
    lineas += ["| " + " | ".join(celda(c, r[c]) for c in columnas) + " |"
              for _, r in tabla.iterrows()]
    lineas += ["", "Media de las repeticiones. Aciertos por familia en porcentaje. "
               "Recall@5 sobre las preguntas con ancla del golden; "
               "coste, latencia y llamadas por pregunta. Mejor valor de cada columna "
               "en negrita (los empates se remarcan en ambas filas)."]
    if tabla["recall@5"].isna().any():
        lineas += ["Recall@5 sin medir: vuelve a ejecutar `python -m agente.lotes reconciliar` "
                   "sin `--sin-recall` para completar esta columna."]
    return "\n".join(lineas) + "\n"


def reconciliar(con_recall_original: bool = True, con_recall_dificil: bool = True) -> pd.DataFrame:
    with carpeta_de("original"):
        salida = interfaz.dir_resultados() / "reconciliacion"
    salida.mkdir(parents=True, exist_ok=True)

    est = pd.concat([estado(g) for g in GOLDENS], ignore_index=True)
    est.to_csv(salida / "estado.csv", index=False)

    comps = {"original": _repuntuar("original", con_recall_original),
             "dificil": _repuntuar("dificil", con_recall_dificil)}

    # lado a lado: una fila por arquitectura, las métricas de cada golden
    partes = []
    for g, comp in comps.items():
        if comp.empty:
            continue
        cols = [c for c in _COLS_LADO_A_LADO if c in comp]
        partes.append(comp.set_index("arquitectura")[cols].add_prefix(f"{g} · "))
    lado = pd.concat(partes, axis=1).reindex([n for n in ORDEN if any(
        n in p.index for p in partes)]) if partes else pd.DataFrame()
    lado.to_csv(salida / "comparativa_dos_golden.csv")

    # Tabla entregable por golden. Se deriva de las mismas comparativas de toda
    # la escalera, así `final` sigue la configuración efectiva de evaluar().
    tablas_bf = {}
    for golden, comp in comps.items():
        tabla = tabla_baseline_final(comp, golden)
        if tabla.empty:
            continue
        tablas_bf[golden] = tabla
        base = salida / f"baseline_vs_final_{golden}"
        tabla.to_csv(base.with_suffix(".csv"), index=False)
        base.with_suffix(".md").write_text(_markdown_baseline_final(tabla, golden), encoding="utf-8")

    # informe
    lineas = [f"# Reconciliación de resultados · {datetime.now():%Y-%m-%d %H:%M}", "",
              "Todo re-puntuado con el golden y los evaluadores ACTUALES, sin repetir "
              "las preguntas del agente. El recall puede usar el modelo si falta una "
              "consulta reescrita en la caché.", ""]
    lineas += ["## Estado por golden, arquitectura y repetición", "",
               "| golden | arquitectura | rep | hechas | faltan | reparables | obsoletas | desde | hasta | config cambiada |",
               "|---|---|---|---|---|---|---|---|---|---|"]
    for r in est.itertuples():
        lineas.append(f"| {r.golden} | {r.arquitectura} | {r.rep} | {r.hechas}/{r.preguntas} | "
                      f"{r.faltan} | {r.reparables} | {r.obsoletas} | {r.desde} | {r.hasta} | "
                      f"{r.config_cambiada or '—'} |")
    pend = est[(est.faltan > 0) | (est.reparables > 0) | (est.obsoletas > 0)]
    lineas += ["", "## Pendiente", ""]
    if pend.empty:
        lineas.append("Nada: todas las arquitecturas ejecutadas están completas.")
    for r in pend.itertuples():
        partes_p = []
        if r.faltan and r.hechas:            # a medias (si no hay nada, no es "pendiente", es "no corrida")
            partes_p.append(f"faltan {r.ids_faltan}")
        if r.reparables:
            partes_p.append(f"sin respuesta (se repiten solas al volver a correr) {r.ids_reparables}")
        if r.obsoletas:
            partes_p.append(f"OBSOLETAS, repetir con forzar=True: {r.ids_obsoletas}")
        if not r.hechas:
            partes_p.append("no ejecutada")
        lineas.append(f"- **{r.golden} · {r.arquitectura} · rep{r.rep}**: " + "; ".join(partes_p))
    if not lado.empty:
        cols = list(lado.columns)
        lineas += ["", "## Las dos tablas, lado a lado", "",
                   "| arquitectura | " + " | ".join(cols) + " |",
                   "|---|" + "---|" * len(cols)]
        for nombre, fila in lado.iterrows():
            celdas = [_fmt(fila[c], c.split(" · ", 1)[1]) for c in cols]
            lineas.append(f"| {nombre} | " + " | ".join(celdas) + " |")
        lineas += ["", "Cada golden se lee por separado: no se promedian. El original es "
                   "la regresión (una mejora no puede empeorarlo); el difícil mide capacidad. "
                   "Con 18 preguntas y 1 repetición, cada pregunta vale 5,6 pp."]
    for golden, tabla in tablas_bf.items():
        lineas += ["", _markdown_baseline_final(tabla, golden).rstrip()]
    (salida / "reconciliacion.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))
    return lado


def main(argv: list[str] | None = None) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # consola de Windows
    except Exception:                                                 # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(prog="python -m agente.lotes")
    sub = ap.add_subparsers(dest="orden", required=True)
    c = sub.add_parser("correr", help="ejecuta lo que falte, puntúa y compara")
    c.add_argument("--golden", choices=list(GOLDENS), default="dificil")
    c.add_argument("--arqs", nargs="+", choices=ORDEN, default=None,
                   help="por defecto, toda la escalera")
    c.add_argument("--reps", type=int, default=1)
    c.add_argument("--plan", action="store_true", help="solo muestra qué falta, coste y tiempo")
    c.add_argument("--si", action="store_true", help="no pide confirmación")
    c.add_argument("--recall", action="store_true", help="calcula recall@5 al puntuar")
    r = sub.add_parser("reconciliar", help="repuntúa y regenera las tablas finales")
    r.add_argument("--sin-recall", action="store_true",
                   help="no recalcula recall@5 en ninguno de los dos golden (más rápido)")
    a = ap.parse_args(argv)
    if a.orden == "correr":
        correr(a.golden, a.arqs, a.reps, solo_plan=a.plan, confirmar=not a.si,
               con_recall=True if a.recall else None)
    else:
        reconciliar(con_recall_original=not a.sin_recall,
                   con_recall_dificil=not a.sin_recall)


if __name__ == "__main__":
    main()
