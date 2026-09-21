"""BM25, RRF, filtros y aislamiento del baseline. Sin FAISS ni red."""

from __future__ import annotations

from agente.retrieval import (
    RRF_K,
    _pasa_filtro,
    buscar,
    buscar_lexico,
    formatear_fragmentos,
    fusionar_rrf,
    montar_bm25,
    tokenizar,
)


def _chunk(
    chunk_id: str,
    texto: str,
    *,
    ticker: str = "NVDA",
    fiscal_year: int = 2025,
    item: str = "1A",
    n_tokens: int = 10,
) -> dict:
    return {
        "chunk_id": chunk_id,
        "ticker": ticker,
        "fiscal_year": fiscal_year,
        "item": item,
        "texto": texto,
        "n_tokens": n_tokens,
        "contiene_tabla": False,
    }


def _frag(chunk_id: str, puntuacion: float, **kwargs) -> dict:
    base = _chunk(chunk_id, f"texto {chunk_id}", **kwargs)
    base["puntuacion"] = puntuacion
    return base


_RELLENO = [
    _chunk(f"AAPL-2024-8-{i:04d}", f"Unrelated filler document number {i} about inventories.",
           ticker="AAPL", fiscal_year=2024, item="8")
    for i in range(8)
]
CORPUS_SINTETICO = [
    _chunk(
        "NVDA-2025-1A-0001",
        "The market in China is limited by export controls and remains competitive.",
        ticker="NVDA", fiscal_year=2025, item="1A",
    ),
    _chunk(
        "NVDA-2025-7-0001",
        "Data Center revenue increased 142% to $115.2 billion in fiscal year 2025.",
        ticker="NVDA", fiscal_year=2025, item="7",
    ),
    _chunk(
        "MSFT-2025-1A-0001",
        "The market in China is limited by export controls and remains competitive.",
        ticker="MSFT", fiscal_year=2025, item="1A",
    ),
    _chunk(
        "NVDA-2024-1A-0001",
        "The market in China is limited by export controls and remains competitive.",
        ticker="NVDA", fiscal_year=2024, item="1A",
    ),
] + _RELLENO


def test_tokenizar_conserva_cifras_dolares_y_porcentajes():
    tokens = tokenizar("Revenue increased 23% to $115.2 billion in FY2025")
    assert "23%" in tokens
    assert "$115.2" in tokens
    assert "fy2025" in tokens
    assert "revenue" in tokens


def test_bm25_ranking_determinista_sobre_corpus_sintetico():
    query = "export controls China"
    primera = buscar_lexico(query, chunks=CORPUS_SINTETICO)
    segunda = buscar_lexico(query, chunks=CORPUS_SINTETICO)
    assert [f["chunk_id"] for f in primera] == [f["chunk_id"] for f in segunda]
    ids = [f["chunk_id"] for f in primera]
    relevantes = {
        "MSFT-2025-1A-0001",
        "NVDA-2024-1A-0001",
        "NVDA-2025-1A-0001",
    }
    assert set(ids[:3]) == relevantes
    assert ids[:3] == sorted(relevantes)
    assert ids.index("NVDA-2025-1A-0001") < ids.index("NVDA-2025-7-0001")

    bm25_a, _ = montar_bm25(CORPUS_SINTETICO)
    bm25_b, _ = montar_bm25(CORPUS_SINTETICO)
    tokens = tokenizar(query)
    assert list(bm25_a.get_scores(tokens)) == list(bm25_b.get_scores(tokens))


def test_rrf_combina_rangos_no_scores_brutos():
    # A es #1 en ambas listas, con scores pequeños.
    # B es #2 denso (coseno enorme) y #2 BM25 (score enorme).
    denso = [_frag("A", 0.01), _frag("B", 0.99)]
    lexico = [_frag("A", 0.5), _frag("B", 999.0)]
    fusion = fusionar_rrf(denso, lexico, k=2, rrf_k=60)
    assert [f["chunk_id"] for f in fusion] == ["A", "B"]
    esperado_a = round(1 / (60 + 1) + 1 / (60 + 1), 4)
    esperado_b = round(1 / (60 + 2) + 1 / (60 + 2), 4)
    assert fusion[0]["puntuacion"] == esperado_a
    assert fusion[1]["puntuacion"] == esperado_b
    assert fusion[0]["tipo_puntuacion"] == "rrf"


def test_rrf_sin_contribucion_si_el_chunk_no_esta_en_una_rama():
    denso = [_frag("A", 0.9), _frag("B", 0.8)]
    lexico = [_frag("A", 10.0)]
    fusion = fusionar_rrf(denso, lexico, k=2, rrf_k=RRF_K)
    por_id = {f["chunk_id"]: f["puntuacion"] for f in fusion}
    assert por_id["A"] == round(1 / 61 + 1 / 61, 4)
    assert por_id["B"] == round(1 / 62, 4)


def test_pasa_filtro_ticker_ejercicio_item():
    fila = CORPUS_SINTETICO[0]
    assert _pasa_filtro(fila, "NVDA", 2025, "1A")
    assert not _pasa_filtro(fila, "MSFT", 2025, "1A")
    assert not _pasa_filtro(fila, "NVDA", 2024, "1A")
    assert not _pasa_filtro(fila, "NVDA", 2025, "7")
    assert _pasa_filtro(fila, None, None, None)


def test_filtros_iguales_en_la_rama_lexica():
    query = "export controls China"
    solo_nvda_2025_1a = buscar_lexico(
        query,
        ticker="NVDA",
        fiscal_year=2025,
        item="1A",
        chunks=CORPUS_SINTETICO,
    )
    ids = {f["chunk_id"] for f in solo_nvda_2025_1a}
    assert ids == {"NVDA-2025-1A-0001"}
    for f in solo_nvda_2025_1a:
        assert f["ticker"] == "NVDA"
        assert f["fiscal_year"] == 2025
        assert f["item"] == "1A"


def test_filtros_en_ambas_ramas_antes_de_fusionar(monkeypatch):
    """Un chunk de otra empresa no entra aunque sea #1 en las listas crudas."""
    otro = _frag("MSFT-2025-1A-0001", 0.99, ticker="MSFT")
    propio = _frag("NVDA-2025-1A-0001", 0.10, ticker="NVDA")

    def denso(query, ticker=None, fiscal_year=None, item=None, k=None):
        crudo = [otro, propio]
        return [
            f for f in crudo
            if (not ticker or f["ticker"] == ticker)
            and (not fiscal_year or f["fiscal_year"] == fiscal_year)
            and (not item or f["item"] == item)
        ]

    def lexico(query, ticker=None, fiscal_year=None, item=None, k=None, **_):
        return denso(query, ticker, fiscal_year, item, k)

    monkeypatch.setattr("agente.retrieval.buscar_denso", denso)
    monkeypatch.setattr("agente.retrieval.buscar_lexico", lexico)

    resultados = buscar(
        "export controls",
        ticker="NVDA",
        fiscal_year=2025,
        item="1A",
        k=5,
        mejoras=True,
        reescritor=lambda q: q,
    )
    assert [f["chunk_id"] for f in resultados] == ["NVDA-2025-1A-0001"]
    assert all(f["ticker"] == "NVDA" for f in resultados)


def test_baseline_no_invoca_reescritura_ni_bm25(monkeypatch):
    llamadas = []

    def denso(query, ticker=None, fiscal_year=None, item=None, k=5):
        llamadas.append(("denso", query, k))
        return [_frag("NVDA-2025-1A-0001", 0.5)]

    def lexico(*_args, **_kwargs):
        llamadas.append(("lexico",))
        return []

    def rew(query, reescritor=None):
        llamadas.append(("reescribir", query))
        return "SHOULD_NOT_RUN"

    monkeypatch.setattr("agente.retrieval.buscar_denso", denso)
    monkeypatch.setattr("agente.retrieval.buscar_lexico", lexico)
    monkeypatch.setattr("agente.retrieval.reescribir", rew)

    out = buscar("¿controles de exportación en China?", k=5, mejoras=False)
    assert [f["chunk_id"] for f in out] == ["NVDA-2025-1A-0001"]
    assert llamadas == [("denso", "¿controles de exportación en China?", 5)]


def test_mejoras_manda_la_query_reescrita_a_las_dos_ramas(monkeypatch):
    visto = {"denso": [], "lexico": []}

    def denso(query, ticker=None, fiscal_year=None, item=None, k=None):
        visto["denso"].append((query, k))
        return [_frag("NVDA-2025-1A-0001", 0.4)]

    def lexico(query, ticker=None, fiscal_year=None, item=None, k=None, **_):
        visto["lexico"].append((query, k))
        return [_frag("NVDA-2025-1A-0001", 1.2)]

    monkeypatch.setattr("agente.retrieval.buscar_denso", denso)
    monkeypatch.setattr("agente.retrieval.buscar_lexico", lexico)

    reescrita = "China market limited by export controls"
    out = buscar(
        "¿Cómo describe NVIDIA el mercado chino?",
        ticker="NVDA",
        k=5,
        mejoras=True,
        reescritor=lambda _q: reescrita,
    )
    assert visto["denso"] == [(reescrita, None)]
    assert visto["lexico"] == [(reescrita, None)]
    assert out[0]["tipo_puntuacion"] == "rrf"
    assert out[0]["chunk_id"] == "NVDA-2025-1A-0001"


def test_formatear_no_etiqueta_rrf_como_similitud():
    rrf = _frag("NVDA-2025-1A-0001", 0.0328)
    rrf["tipo_puntuacion"] = "rrf"
    texto_hibrido = formatear_fragmentos([rrf])
    assert "RRF 0.033" in texto_hibrido
    assert "similitud" not in texto_hibrido

    denso = _frag("NVDA-2025-1A-0001", 0.8123)
    texto_denso = formatear_fragmentos([denso])
    assert "similitud 0.812" in texto_denso
    assert "RRF" not in texto_denso
