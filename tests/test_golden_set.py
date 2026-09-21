"""El golden set cumple el enunciado y cuadra con el corpus."""
import collections

from agente.metricas import cuadra


def test_veinte_preguntas_y_seis_comparativas(golden):
    assert len(golden) == 20
    familias = collections.Counter(g["familia"] for g in golden)
    assert familias["comparativa"] >= 6
    assert set(familias) == {"numerica", "extractiva", "comparativa"}


def test_cifras_esperadas_cuadran_con_xbrl(golden, xbrl):
    for g in golden:
        if not g.get("concept_xbrl"):
            continue
        f = xbrl[(xbrl.ticker == g["ticker"]) & (xbrl.fiscal_year == int(g["fiscal_year"]))
                 & (xbrl.concept == g["concept_xbrl"])]
        assert not f.empty, f"{g['id']}: {g['concept_xbrl']} no está en XBRL"
        assert cuadra(float(f.iloc[0]["value"]), g["cifra_esperada"], 1e-6), g["id"]


def test_comparativas_tienen_el_concepto_en_ambos_ejercicios(golden, xbrl):
    for g in golden:
        if g["familia"] != "comparativa":
            continue
        for fy in (2024, 2025):
            f = xbrl[(xbrl.ticker == g["ticker"]) & (xbrl.fiscal_year == fy)
                     & (xbrl.concept == g["concept_xbrl"])]
            assert not f.empty, f"{g['id']}: {g['concept_xbrl']} falta en FY{fy}"


def test_anclas_estan_en_su_chunk(golden, chunks_por_id):
    from agente.metricas import normalizar
    for g in golden:
        if not g.get("ancla_texto"):
            continue
        c = chunks_por_id.get(g["chunk_id_esperado"])
        assert c is not None, f"{g['id']}: chunk {g['chunk_id_esperado']} no existe"
        assert normalizar(g["ancla_texto"]) in normalizar(c["texto"]), g["id"]
        assert c["ticker"] == g["ticker"] and int(c["fiscal_year"]) == int(g["fiscal_year"])
        assert c["item"] == g["item_esperado"]
