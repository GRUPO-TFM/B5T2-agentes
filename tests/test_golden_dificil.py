"""El golden set adversario (`data/golden_set_dificil.jsonl`) cuadra con el corpus."""
import collections
import json

import pytest

from agente.corpus import raiz_repo
from agente.metricas import cuadra, normalizar


@pytest.fixture(scope="session")
def dificil() -> list[dict]:
    ruta = raiz_repo() / "data" / "golden_set_dificil.jsonl"
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_dieciocho_preguntas_en_tres_familias_nuevas(dificil, golden):
    assert len(dificil) == 18
    fams = collections.Counter(g["familia"] for g in dificil)
    assert fams == {"honestidad": 5, "multi": 6, "multi_temporal": 7}
    # ids distintos de los del golden original: se pueden puntuar juntos sin pisarse
    assert not ({g["id"] for g in dificil} & {g["id"] for g in golden})
    assert len({g["id"] for g in dificil}) == 18


def test_las_de_honestidad_no_tienen_respuesta_en_el_corpus(dificil, xbrl):
    for g in (g for g in dificil if g["familia"] == "honestidad"):
        assert g["fuente_esperada"] == "ninguna", g["id"]
        assert g["cifra_esperada"] is None and g["ancla_texto"] is None, g["id"]
    # AMZN de verdad no reporta GrossProfit; NVDA de verdad no tiene FY2023; TSLA no está
    assert xbrl[(xbrl.ticker == "AMZN") & (xbrl.concept == "GrossProfit")].empty
    assert xbrl[(xbrl.ticker == "NVDA") & (xbrl.fiscal_year == 2023)].empty
    assert xbrl[xbrl.ticker == "TSLA"].empty


def test_las_cifras_con_concepto_cuadran_con_xbrl(dificil, xbrl):
    for g in dificil:
        if not g.get("concept_xbrl"):
            continue
        f = xbrl[(xbrl.ticker == g["ticker"]) & (xbrl.fiscal_year == int(g["fiscal_year"]))
                 & (xbrl.concept == g["concept_xbrl"])]
        assert not f.empty, g["id"]
        assert cuadra(float(f.iloc[0]["value"]), g["cifra_esperada"], 1e-6), g["id"]


def test_las_derivadas_se_recalculan_desde_xbrl(dificil, xbrl):
    """Las cifras que no son un hecho XBRL (diferencias, ratios, crecimientos)
    se vuelven a calcular aquí desde el parquet: si alguien cambia el corpus,
    el golden se queja."""
    def v(t, fy, c):
        f = xbrl[(xbrl.ticker == t) & (xbrl.fiscal_year == fy) & (xbrl.concept == c)]
        assert len(f) == 1, (t, fy, c)
        return float(f.iloc[0]["value"])
    por_id = {g["id"]: g for g in dificil}
    R = "RevenueFromContractWithCustomerExcludingAssessedTax"
    assert cuadra(por_id["gY-008"]["cifra_esperada"],
                  v("GOOGL", 2025, "ResearchAndDevelopmentExpense") - v("META", 2025, "ResearchAndDevelopmentExpense"), 1e-6)
    assert cuadra(por_id["gY-009"]["cifra_esperada"],
                  v("NVDA", 2025, "OperatingIncomeLoss") / v("NVDA", 2025, "Revenues") * 100, 1e-3)
    g_nvda = (v("NVDA", 2025, "Revenues") / v("NVDA", 2024, "Revenues") - 1) * 100
    g_msft = (v("MSFT", 2025, R) / v("MSFT", 2024, R) - 1) * 100
    assert cuadra(por_id["gY-011"]["cifra_esperada"], g_nvda - g_msft, 1e-3)
    ratio = lambda t, fy: v(t, fy, "Liabilities") / v(t, fy, "Assets") * 100
    assert cuadra(por_id["gY-012"]["cifra_esperada"], ratio("AAPL", 2024) - ratio("AAPL", 2025), 1e-3)
    assert cuadra(por_id["gY-013"]["cifra_esperada"],
                  (v("NVDA", 2025, "EarningsPerShareDiluted") / (v("NVDA", 2024, "EarningsPerShareDiluted") / 10) - 1) * 100, 1e-3)
    ocf = "NetCashProvidedByUsedInOperatingActivities"
    assert cuadra(por_id["gY-014"]["cifra_esperada"], (v("NVDA", 2025, ocf) / v("NVDA", 2024, ocf) - 1) * 100, 1e-3)
    assert cuadra(por_id["gY-015"]["cifra_esperada"],
                  (v("NVDA", 2025, "NetIncomeLoss") / v("NVDA", 2024, "NetIncomeLoss") - 1) * 100, 1e-3)


def test_anclas_estan_en_su_chunk(dificil, chunks_por_id):
    for g in dificil:
        if not g.get("ancla_texto"):
            continue
        c = chunks_por_id.get(g["chunk_id_esperado"])
        assert c is not None, g["id"]
        assert normalizar(g["ancla_texto"]) in normalizar(c["texto"]), g["id"]
        assert c["ticker"] == g["ticker"] and int(c["fiscal_year"]) == int(g["fiscal_year"])
        assert c["item"] == g["item_esperado"]


def test_los_evaluadores_aplican_como_se_espera(dificil):
    """Sin API: comprueba qué evaluador se activa en cada familia con una
    respuesta perfecta y con una deshonesta."""
    from agente.evaluadores import EVALUADORES, acierto
    from tests.conftest import resultado_falso
    por_id = {g["id"]: g for g in dificil}
    # honestidad: fuente='ninguna' acierta; inventarse una cifra suspende
    it = por_id["gY-001"]
    bien = resultado_falso(fuente="ninguna", herramientas=["get_xbrl_fact"])
    mal = resultado_falso(cifra=1.2e11, fuente="xbrl", ticker="AMZN", ejercicio=2025, herramientas=["get_xbrl_fact"])
    vb = {k: f(it, bien) for k, f in EVALUADORES.items()}
    vm = {k: f(it, mal) for k, f in EVALUADORES.items()}
    assert vb["honestidad"] is True and vb["cifra"] is None and vb["cita"] is None and acierto(vb) is True
    assert vm["honestidad"] is False and acierto(vm) is False
    # multi_temporal con ancla: cifra + trayectoria + cita
    it = por_id["gY-014"]
    r = resultado_falso(cifra=128.16, unidad="%", ticker="NVDA", ejercicio=2025, fuente="ambas",
                        cita=it["ancla_texto"], chunk_id=it["chunk_id_esperado"],
                        herramientas=["get_xbrl_fact", "search_filings"])
    v = {k: f(it, r) for k, f in EVALUADORES.items()}
    assert v == {"cita": True, "cifra": True, "trayectoria": True, "honestidad": None}


def test_v2_cifras_aceptables(dificil, xbrl):
    """v2: en las multi-entidad se acepta la magnitud derivada Y el valor XBRL
    que manda poner el prompt del agente. La primera siempre es `cifra_esperada`
    (la v1, que se registró) y la segunda es un hecho XBRL real."""
    def v(t, fy, c):
        return float(xbrl[(xbrl.ticker == t) & (xbrl.fiscal_year == fy) & (xbrl.concept == c)].iloc[0]["value"])
    contrato = {"gY-008": ("GOOGL", "ResearchAndDevelopmentExpense"), "gY-009": ("NVDA", "OperatingIncomeLoss"),
                "gY-011": ("NVDA", "Revenues"), "gY-012": ("AAPL", "Liabilities"),
                "gY-013": ("NVDA", "EarningsPerShareDiluted"),
                "gY-014": ("NVDA", "NetCashProvidedByUsedInOperatingActivities"),
                "gY-015": ("NVDA", "NetIncomeLoss")}
    por_id = {g["id"]: g for g in dificil}
    for iid, (t, c) in contrato.items():
        acc = por_id[iid]["cifras_aceptables"]
        assert acc[0] == por_id[iid]["cifra_esperada"], iid
        assert cuadra(acc[1], v(t, 2025, c), 1e-6), iid
    assert por_id["gY-010"]["fuente_esperada"] == ["xbrl", "ninguna"]


def test_las_de_texto_no_son_hechos_xbrl(dificil, xbrl, chunks_por_id):
    """gY-016..018: la cifra SOLO está en el texto del Item 7A, y está literal
    en el ancla (en millones). Si coincidiera con un hecho XBRL, el ítem no
    probaría nada sobre el verificador."""
    for iid in ("gY-016", "gY-017", "gY-018"):
        g = next(x for x in dificil if x["id"] == iid)
        assert g["item_esperado"] == "7A" and g["concept_xbrl"] is None
        hechos = xbrl[(xbrl.ticker == g["ticker"]) & (xbrl.fiscal_year == 2025)]["value"]
        assert not any(cuadra(g["cifra_esperada"], float(h), 0.01) for h in hechos), iid
        assert f"${g['cifra_esperada'] / 1e6:,.0f} million" in g["ancla_texto"], iid
    # los otros tres valores de gY-017 también están donde dice la nota
    for cid, cifra in (("META-2024-7A-0002", "$123 million"), ("GOOGL-2024-7A-0003", "$508 million"),
                       ("GOOGL-2025-7A-0003", "$631 million")):
        assert cifra in chunks_por_id[cid]["texto"], cid


def test_evaluadores_v2(dificil):
    from agente.evaluadores import EVALUADORES, acierto
    from tests.conftest import resultado_falso
    por_id = {g["id"]: g for g in dificil}
    ver = lambda it, r: {k: f(it, r) for k, f in EVALUADORES.items()}
    # gY-011: vale el diferencial (99,27 pp) y vale el valor XBRL de NVDA; no vale el de MSFT
    it = por_id["gY-011"]
    for cifra, ok in ((99.27, True), (130_497_000_000.0, True), (281_724_000_000.0, False)):
        r = resultado_falso(cifra=cifra, fuente="xbrl", herramientas=["get_xbrl_fact"])
        assert ver(it, r)["cifra"] is ok, cifra
    # gY-010: honestidad parcial. 'ninguna' sin cifra acierta; 'xbrl' con el I+D de Meta, también
    it = por_id["gY-010"]
    v = ver(it, resultado_falso(fuente="ninguna", herramientas=["get_xbrl_fact"]))
    assert v["cifra"] is None and v["honestidad"] is True and acierto(v) is True
    v = ver(it, resultado_falso(cifra=57_372_000_000.0, fuente="xbrl", ticker="META", ejercicio=2025,
                                herramientas=["get_xbrl_fact"]))
    assert v["cifra"] is True and v["honestidad"] is True and acierto(v) is True
    # gY-018: no exige herramienta (read_section o search_filings valen); cita + cifra
    it = por_id["gY-018"]
    v = ver(it, resultado_falso(cifra=590_000_000.0, fuente="texto", ticker="AAPL", ejercicio=2025,
                                cita=it["ancla_texto"], chunk_id=it["chunk_id_esperado"],
                                herramientas=["read_section"]))
    assert v == {"cita": True, "cifra": True, "trayectoria": None, "honestidad": None}
    # las de honestidad pura siguen igual: 'ninguna' como texto, no como lista
    assert por_id["gY-001"]["fuente_esperada"] == "ninguna"


def test_el_golden_original_no_usa_extensiones_v2(golden):
    for g in golden:
        assert "cifras_aceptables" not in g and not isinstance(g.get("fuente_esperada"), list)
