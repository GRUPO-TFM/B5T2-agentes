"""Ejecución por lotes y reconciliación, sin API: responder falso y golden temporal."""
import json

import pandas as pd
import pytest

from agente import interfaz, lotes
from tests.test_harness import _responder_falso


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    """Resultados en tmp; un golden 'dificil' de 3 preguntas y uno 'original' de 2."""
    monkeypatch.setattr(interfaz, "dir_resultados", lambda: tmp_path / interfaz.CARPETA_RESULTADOS)
    reales = interfaz.leer_golden("data/golden_set_dificil.jsonl")
    por_id = {g["id"]: g for g in reales}
    dificil = [por_id["gY-006"], por_id["gY-011"], por_id["gY-016"]]
    original = interfaz.leer_golden("data/golden_set.jsonl")[:2]
    rutas = {}
    for nombre, items in (("dificil", dificil), ("original", original)):
        ruta = tmp_path / f"{nombre}.jsonl"
        ruta.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
        rutas[nombre] = ruta
    monkeypatch.setattr(lotes, "GOLDENS", {"original": (str(rutas["original"]), "resultados"),
                                           "dificil": (str(rutas["dificil"]), "resultados_dificil")})
    # `correr` llama a interfaz.ejecutar sin responder: se le inyecta el falso y se cuentan las preguntas
    llamadas = []
    real = interfaz.ejecutar

    def ejecutar_falso(ruta, arq, rep, **kw):
        def resp(pregunta, **k):
            llamadas.append((interfaz.arquitectura(arq).nombre, rep, pregunta[:30]))
            return _responder_falso(pregunta, **k)
        return real(ruta, arq, rep, responder_fn=resp, verbose=False)
    monkeypatch.setattr(interfaz, "ejecutar", ejecutar_falso)
    return tmp_path, rutas, llamadas


def test_plan_no_gasta(entorno, monkeypatch):
    _, _, llamadas = entorno
    p = lotes.correr("dificil", ["baseline", "a4_comparativas"], 1, solo_plan=True)
    assert p is None and llamadas == []
    est = lotes.plan("dificil", ["baseline", "a4_comparativas"], 1)
    assert list(est["por_correr"]) == [3, 3]


def test_correr_no_rehace_lo_hecho(entorno):
    tmp, rutas, llamadas = entorno
    lotes.correr("dificil", ["baseline"], 1, confirmar=False)
    assert len(llamadas) == 3
    lotes.correr("dificil", ["baseline"], 1, confirmar=False)       # segunda vez: nada nuevo
    assert len(llamadas) == 3
    # una pregunta nueva en el golden: solo corre esa
    items = [json.loads(l) for l in rutas["dificil"].read_text(encoding="utf-8").splitlines()]
    extra = interfaz.leer_golden("data/golden_set_dificil.jsonl")[0]
    rutas["dificil"].write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items + [extra]),
                                encoding="utf-8")
    lotes.correr("dificil", ["baseline"], 1, confirmar=False)
    assert len(llamadas) == 4
    assert (tmp / "resultados_dificil" / "comparativa.md").is_file()
    assert not (tmp / "resultados" / "agente").exists()               # no toca el otro golden
    hist = (tmp / "resultados_dificil" / "agente" / "baseline" / "config_historial.jsonl")
    assert len(hist.read_text(encoding="utf-8").splitlines()) == 2    # la pasada vacía no ejecuta


def test_estado_detecta_reparables_obsoletas_y_sobrantes(entorno):
    tmp, rutas, _ = entorno
    lotes.correr("dificil", ["baseline"], 1, confirmar=False)
    crudo = tmp / "resultados_dificil" / "agente" / "baseline" / "rep1" / "crudo"
    # reparable: el JSON perdió la respuesta
    reg = json.loads((crudo / "gY-006.json").read_text(encoding="utf-8"))
    reg.pop("resultado"); reg["error"] = "OpenRouterError: 400"
    (crudo / "gY-006.json").write_text(json.dumps(reg), encoding="utf-8")
    # obsoleta: el enunciado guardado no es el actual
    reg = json.loads((crudo / "gY-011.json").read_text(encoding="utf-8"))
    reg["item"]["pregunta"] = "otra pregunta"
    (crudo / "gY-011.json").write_text(json.dumps(reg), encoding="utf-8")
    # sobrante: id que ya no está en el golden
    (crudo / "gY-999.json").write_text((crudo / "gY-016.json").read_text(encoding="utf-8"), encoding="utf-8")
    e = lotes.estado("dificil", ["baseline"]).iloc[0]
    assert (e.hechas, e.reparables, e.obsoletas, e.sobran, e.por_correr) == (2, 1, 1, 1, 1)
    assert e.ids_reparables == "gY-006" and e.ids_obsoletas == "gY-011"


def test_puntuar_con_el_golden_actual(entorno):
    """El crudo guarda el ítem viejo; con `golden` se puntúa con el nuevo."""
    tmp, rutas, _ = entorno
    lotes.correr("dificil", ["baseline"], 1, confirmar=False)
    crudo = tmp / "resultados_dificil" / "agente" / "baseline" / "rep1" / "crudo"
    reg = json.loads((crudo / "gY-011.json").read_text(encoding="utf-8"))
    reg["item"].pop("cifras_aceptables")              # así era el golden v1
    (crudo / "gY-011.json").write_text(json.dumps(reg), encoding="utf-8")
    with lotes.carpeta_de("dificil"):
        viejo = interfaz.puntuar("baseline", 1, con_recall=False).set_index("id")
        nuevo = interfaz.puntuar("baseline", 1, con_recall=False, golden=rutas["dificil"]).set_index("id")
    # el responder falso da 130.497 M (ingresos NVDA FY2025): vale en v2, no en v1
    assert viejo.loc["gY-011", "cifra"] == False and nuevo.loc["gY-011", "cifra"] == True   # noqa: E712
    assert not nuevo["obsoleta"].any()


def test_reconciliar_sin_api(entorno):
    tmp, _, llamadas = entorno
    lotes.correr("dificil", ["baseline", "a1_guardrails"], 1, confirmar=False)
    lotes.correr("original", ["baseline"], 1, confirmar=False, con_recall=False)
    n = len(llamadas)
    lado = lotes.reconciliar(con_recall_original=False, con_recall_dificil=False)
    assert len(llamadas) == n                                          # no llama al agente
    assert list(lado.index) == ["baseline", "a1_guardrails"]
    assert "original · acierto" in lado.columns and "dificil · acierto" in lado.columns
    assert lado["original · acierto"].isna()["a1_guardrails"]          # no corrida en el original
    informe = (tmp / "resultados" / "reconciliacion" / "reconciliacion.md").read_text(encoding="utf-8")
    assert "lado a lado" in informe and "no ejecutada" in informe


def test_tabla_baseline_final_tiene_las_columnas_y_remarca_el_mejor():
    comp = pd.DataFrame([
        {"arquitectura": "baseline", "reps": 3, "acierto": .6,
         "acierto numerica": 1., "acierto extractiva": 1., "acierto comparativa": .1,
         "recall@5": .5, "coste medio (¢)": 1.4,
         "latencia media (s)": 20., "llamadas/pregunta": 4.},
        {"arquitectura": "a4_comparativas", "reps": 3, "acierto": .9,
         "acierto numerica": 1., "acierto extractiva": 1., "acierto comparativa": .75,
         "recall@5": .85, "coste medio (¢)": 1.6,
         "latencia media (s)": 48., "llamadas/pregunta": 3.6},
        {"arquitectura": "a6_cifras_texto", "reps": 1, "acierto": 1.,
         "acierto numerica": 1., "acierto extractiva": 1., "acierto comparativa": 1.,
         "recall@5": .85, "coste medio (¢)": 1.8,
         "latencia media (s)": 39., "llamadas/pregunta": 3.2},
    ])
    tabla = lotes.tabla_baseline_final(comp, "original")
    assert list(tabla["arquitectura"]) == ["baseline", "a6_cifras_texto"]
    assert list(tabla.columns) == ["arquitectura", "reps", "acierto", "acierto numerica",
                                   "acierto extractiva", "acierto comparativa", "recall@5",
                                   "coste medio (¢)", "latencia media (s)", "llamadas/pregunta"]
    md = lotes._markdown_baseline_final(tabla, "original")
    assert "| coste medio (¢) | latencia media (s) | llamadas/pregunta |" in md
    assert "| baseline | 3 | 60.0% | **100.0%**" in md
    assert "| final | 1 | **100.0%** | **100.0%**" in md
    assert "**1.40** | **20.00** | 4.00" in md
    assert "1.80 | 39.00 | **3.20**" in md
