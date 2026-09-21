"""Compara recall@5 del retrieval baseline contra el mejorado.

Fija corpus, embedding (`BAAI/bge-small-en-v1.5`), filtros del golden
(`ticker`, `fiscal_year`, `item_esperado`) y k=5. El delta se atribuye a
reescritura + BM25/RRF.

Sin OPENROUTER_API_KEY no hay llamada al LLM: se mide el híbrido con la
query original (identidad). Con clave, la ablación completa es:

    denso + filtros
    híbrido BM25+RRF (query original)
    reescritura + híbrido

Uso:
    uv run python scripts/evaluar_recall.py
    uv run python scripts/evaluar_recall.py --reescribir
    uv run python scripts/evaluar_recall.py --sin-reescritura
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

from agente.agente import MODELO
from agente.corpus import raiz_repo
from agente.interfaz import PRECIOS_OPENROUTER
from agente.reescritura import reescribir, ultimo_uso
from agente.retrieval import buscar

K = 5
_ESPACIOS = re.compile(r"\s+")


def normalizar(texto: str) -> str:
    return _ESPACIOS.sub(" ", texto).strip().lower()


def acierta(item: dict, recuperados: list[dict]) -> bool:
    """True si algún fragmento del mismo ticker/FY contiene el ancla."""
    ancla = item.get("ancla_texto")
    if not ancla:
        return False
    objetivo = normalizar(ancla)
    for fragmento in recuperados:
        mismo_documento = (
            fragmento.get("ticker") == item.get("ticker")
            and int(fragmento.get("fiscal_year", -1))
            == int(item.get("fiscal_year", -2))
        )
        if not mismo_documento:
            continue
        if objetivo in normalizar(fragmento.get("texto", "")):
            return True
    return False


def cargar_golden(ruta: Path) -> list[dict]:
    return [
        json.loads(linea)
        for linea in ruta.read_text(encoding="utf-8").splitlines()
        if linea.strip()
    ]


def ids_de(fragmentos: list[dict]) -> list[str]:
    return [f["chunk_id"] for f in fragmentos]


def recuperar(item: dict, *, mejoras: bool, reescritor) -> list[dict]:
    kwargs = dict(
        query=item["pregunta"],
        ticker=item.get("ticker"),
        fiscal_year=item.get("fiscal_year"),
        item=item.get("item_esperado"),
        k=K,
        mejoras=mejoras,
    )
    if mejoras:
        kwargs["reescritor"] = reescritor
    return buscar(**kwargs)


def hay_clave() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY", "").strip())


def coste_usd(entrada: int, salida: int, modelo: str = MODELO) -> float:
    nombre = modelo.split(":", 1)[-1]
    if nombre not in PRECIOS_OPENROUTER:
        return 0.0
    precio_entrada, precio_salida = PRECIOS_OPENROUTER[nombre]
    return (entrada * precio_entrada + salida * precio_salida) / 1e6


def resumen(filas: list[dict], campo_hit: str, campo_lat: str) -> dict:
    n = len(filas)
    return {
        "n": n,
        "aciertos": sum(f[campo_hit] for f in filas),
        "recall_at_k": sum(f[campo_hit] for f in filas) / n if n else 0.0,
        "latencia_media_s": sum(f[campo_lat] for f in filas) / n if n else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="recall@5 baseline vs híbrido (filtros, embedding y k fijos)."
    )
    parser.add_argument(
        "--golden",
        type=Path,
        default=None,
        help="JSONL del golden set (por defecto data/golden_set.jsonl).",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=None,
        help="JSON de resultados (por defecto data/recall_retrieval.json).",
    )
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument(
        "--reescribir",
        action="store_true",
        help="Fuerza reescritura con el LLM (requiere OPENROUTER_API_KEY).",
    )
    grupo.add_argument(
        "--sin-reescritura",
        action="store_true",
        help="Híbrido con la query original; no llama al LLM.",
    )
    args = parser.parse_args()

    raiz = raiz_repo()
    golden = args.golden or (raiz / "data" / "golden_set.jsonl")
    if not golden.is_file():
        raise SystemExit(f"No encuentro el golden set: {golden}")

    items = [g for g in cargar_golden(golden) if g.get("ancla_texto")]
    if not items:
        raise SystemExit(f"Ningún ítem con ancla_texto en {golden}")

    usar_llm = args.reescribir or (not args.sin_reescritura and hay_clave())
    if args.reescribir and not hay_clave():
        raise SystemExit(
            "OPENROUTER_API_KEY no está definida: no puedo reescribir en vivo."
        )

    salida = args.salida or (raiz / "data" / "recall_retrieval.json")

    print(f"{len(items)} preguntas con ancla · k={K}")
    print("Precargando FAISS, embeddings y BM25…", flush=True)
    from agente.retrieval import _indice, _indice_bm25
    _indice()
    _indice_bm25()
    print()

    filas = []
    tokens_in = tokens_out = 0
    for i, item in enumerate(items, 1):
        t0 = time.perf_counter()
        rec_base = recuperar(item, mejoras=False, reescritor=None)
        tb = time.perf_counter() - t0
        hit_b = acierta(item, rec_base)

        t0 = time.perf_counter()
        rec_hib = recuperar(item, mejoras=True, reescritor=lambda q: q)
        th = time.perf_counter() - t0
        hit_h = acierta(item, rec_hib)

        consulta = item["pregunta"]
        t_rew = 0.0
        uso = {"input_tokens": 0, "output_tokens": 0}
        if usar_llm:
            t1 = time.perf_counter()
            consulta = reescribir(item["pregunta"])
            t_rew = time.perf_counter() - t1
            uso = ultimo_uso()
            tokens_in += uso["input_tokens"]
            tokens_out += uso["output_tokens"]
            t0 = time.perf_counter()
            rec_mej = recuperar(
                item, mejoras=True, reescritor=lambda _q, c=consulta: c
            )
            tm = time.perf_counter() - t0
        else:
            rec_mej = rec_hib
            tm = th
        hit_m = acierta(item, rec_mej)

        fila = {
            "id": item["id"],
            "familia": item.get("familia"),
            "ticker": item.get("ticker"),
            "fiscal_year": item.get("fiscal_year"),
            "item_esperado": item.get("item_esperado"),
            "pregunta": item["pregunta"],
            "consulta_reescrita": consulta if usar_llm else None,
            "ancla_texto": item.get("ancla_texto"),
            "chunk_id_esperado": item.get("chunk_id_esperado"),
            "baseline": int(hit_b),
            "hibrido": int(hit_h),
            "mejorado": int(hit_m),
            "chunk_ids_baseline": ids_de(rec_base),
            "chunk_ids_hibrido": ids_de(rec_hib),
            "chunk_ids_mejorado": ids_de(rec_mej),
            "lat_baseline_s": round(tb, 3),
            "lat_hibrido_s": round(th, 3),
            "lat_mejorado_s": round(tm, 3),
            "lat_reescritura_s": round(t_rew, 3),
            "tokens_entrada": uso["input_tokens"],
            "tokens_salida": uso["output_tokens"],
        }
        filas.append(fila)
        marca = {1: "sí", 0: "no"}
        extra = f"  rew {t_rew:.2f}s" if usar_llm else ""
        print(
            f"  [{i:02d}/{len(items)}] {item['id']}  "
            f"base={marca[hit_b]}  hib={marca[hit_h]}  "
            f"mej={marca[hit_m]}  ({tb:.2f}s / {th:.2f}s / {tm:.2f}s{extra})"
        )
        if usar_llm:
            print(f"           EN: {consulta}")

    n = len(filas)
    cfg_base = resumen(filas, "baseline", "lat_baseline_s")
    cfg_hib = resumen(filas, "hibrido", "lat_hibrido_s")
    cfg_mej = resumen(filas, "mejorado", "lat_mejorado_s")
    lat_rew = sum(f["lat_reescritura_s"] for f in filas) / n
    coste = coste_usd(tokens_in, tokens_out)

    print()
    print(f"{'configuración':42s}  recall@{K}  latencia media")
    print(
        f"{'1 · baseline (denso + filtros)':42s}  "
        f"{cfg_base['recall_at_k']:7.1%}  {cfg_base['latencia_media_s']:8.2f}s"
    )
    print(
        f"{'2 · híbrido BM25+RRF (query original)':42s}  "
        f"{cfg_hib['recall_at_k']:7.1%}  {cfg_hib['latencia_media_s']:8.2f}s"
    )
    if usar_llm:
        print(
            f"{'3 · reescritura + híbrido':42s}  "
            f"{cfg_mej['recall_at_k']:7.1%}  {cfg_mej['latencia_media_s']:8.2f}s"
        )
        print(
            f"{'     reescritura (LLM, extra)':42s}  "
            f"{'':7}  {lat_rew:8.2f}s  · "
            f"{tokens_in}+{tokens_out} tokens · ${coste:.5f}"
        )
        print(
            f"\ndelta 3 vs 1: {cfg_mej['recall_at_k'] - cfg_base['recall_at_k']:+.1%}"
        )
        print(
            f"delta 2 vs 1: {cfg_hib['recall_at_k'] - cfg_base['recall_at_k']:+.1%}"
        )
    else:
        print(
            "\nPENDIENTE: recall@5 con reescritura en vivo "
            "(no hay OPENROUTER_API_KEY). El delta de esta corrida "
            "solo mide BM25+RRF sobre la query original."
        )
        print(
            f"delta 2 vs 1: {cfg_hib['recall_at_k'] - cfg_base['recall_at_k']:+.1%}"
        )

    informe = {
        "k": K,
        "modelo_embeddings": "BAAI/bge-small-en-v1.5",
        "modelo_reescritura": MODELO if usar_llm else None,
        "golden": (
            str(golden.resolve().relative_to(raiz.resolve()))
            if golden.resolve().is_relative_to(raiz.resolve())
            else str(golden)
        ),
        "n_con_ancla": n,
        "con_reescritura": usar_llm,
        "configuraciones": {
            "baseline": cfg_base,
            "hibrido_sin_reescritura": cfg_hib,
            "reescritura_hibrido": cfg_mej if usar_llm else None,
        },
        "reescritura": {
            "latencia_media_s": lat_rew if usar_llm else None,
            "tokens_entrada": tokens_in,
            "tokens_salida": tokens_out,
            "coste_usd": round(coste, 6) if usar_llm else None,
            "llamadas": n if usar_llm else 0,
        },
        "items": filas,
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(
        json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nResultados en {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
