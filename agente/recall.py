"""recall@k del retrieval, medido contra el ancla y SIN agente.

Es la tabla del §4.4 del enunciado: la búsqueda densa de partida y, encima,
cada arreglo medido por separado. No gasta API salvo la reescritura de la
consulta (una llamada barata por pregunta, cacheada en disco).

    medir_recall()                         # las cinco configuraciones del profesor
    medir_recall({"mi config": fn, ...})   # las que quieras: fn(item) -> fragmentos ordenados

Cada configuración es una función `item_del_golden -> lista de fragmentos
ORDENADOS` (todos, no solo k): así se saca recall@k para cualquier k y la
posición del ancla, que es lo que dice qué arreglar.

Las funciones de búsqueda que hay aquí (`denso_plano`, `hibrido`, `reescribir`)
son las de referencia para medir. Si `agente/retrieval.py` trae versiones
mejores, se enchufan aquí y se miden igual.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Callable

import pandas as pd

from agente.config import K, MODELO, Arquitectura, arquitectura
from agente.corpus import cargar_chunks, raiz_repo
from agente.metricas import acierta, posicion_del_ancla, tokenizar
from agente.retrieval import _indice, buscar

Config = Callable[[dict], list[dict]]

# ---------------------------------------------------------------------------
# Búsquedas de referencia
# ---------------------------------------------------------------------------
def _fragmento(fila, puntuacion: float) -> dict:
    return {
        "chunk_id": fila["chunk_id"], "ticker": fila["ticker"],
        "fiscal_year": int(fila["fiscal_year"]), "item": fila["item"],
        "texto": fila["texto"], "puntuacion": round(float(puntuacion), 4),
        "inicio_car": int(fila["inicio_car"]) if "inicio_car" in fila else None,
        "fin_car": int(fila["fin_car"]) if "fin_car" in fila else None,
    }


def denso_plano(consulta: str, k: int | None = None) -> list[dict]:
    """Lo que hacía search_filings el día 10: los k más parecidos de TODO el
    corpus, sin mirar de qué compañía ni ejercicio son."""
    indice, meta, codificador = _indice()
    from agente.retrieval import PREFIJO_CONSULTA_BGE
    v = codificador.encode([PREFIJO_CONSULTA_BGE + consulta], normalize_embeddings=True,
                           convert_to_numpy=True).astype("float32")
    n = indice.ntotal if k is None else min(k, indice.ntotal)
    puntuaciones, posiciones = indice.search(v, n)
    return [_fragmento(meta.iloc[int(i)], s) for s, i in zip(puntuaciones[0], posiciones[0])]


def con_filtros(consulta: str, ticker=None, fiscal_year=None, item=None,
                k: int | None = None) -> list[dict]:
    """Denso + filtros por metadatos (post-filtrado). Es `retrieval.buscar`."""
    indice, _, _ = _indice()
    return buscar(consulta, ticker=ticker, fiscal_year=fiscal_year, item=item,
                  k=indice.ntotal if k is None else k)


@functools.lru_cache(maxsize=1)
def _bm25():
    from rank_bm25 import BM25Okapi
    chunks = cargar_chunks()
    return BM25Okapi([tokenizar(c["texto"]) for c in chunks]), chunks


def hibrido(consulta: str, ticker=None, fiscal_year=None, item=None,
            k: int | None = None, kk: int = 60) -> list[dict]:
    """Fusión por Reciprocal Rank Fusion del orden denso y el orden BM25.

    No se suman puntuaciones (un coseno y un BM25 no viven en la misma escala):
    se combinan POSICIONES: RRF(d) = Σ 1/(kk + posición_de_d) en cada lista.
    """
    densos = con_filtros(consulta, ticker, fiscal_year, item, k=None)
    pos_denso = {f["chunk_id"]: i for i, f in enumerate(densos, 1)}

    bm25, chunks = _bm25()
    puntuaciones = bm25.get_scores(tokenizar(consulta))
    orden_bm = sorted(range(len(chunks)), key=lambda i: -puntuaciones[i])
    pos_bm25, por_id = {}, {}
    p = 0
    for i in orden_bm:
        c = chunks[i]
        if ticker and c["ticker"] != ticker:
            continue
        if fiscal_year and int(c["fiscal_year"]) != int(fiscal_year):
            continue
        if item and c["item"] != item:
            continue
        p += 1
        pos_bm25[c["chunk_id"]] = p
        por_id[c["chunk_id"]] = c
    for f in densos:
        por_id.setdefault(f["chunk_id"], f)

    def rrf(cid):
        return (1 / (kk + pos_denso.get(cid, 10**6))) + (1 / (kk + pos_bm25.get(cid, 10**6)))

    ordenados = sorted(por_id, key=lambda cid: -rrf(cid))
    salida = []
    for cid in ordenados[: (len(ordenados) if k is None else k)]:
        c = por_id[cid]
        salida.append({**{key: c.get(key) for key in ("chunk_id", "ticker", "fiscal_year", "item",
                                                       "texto", "inicio_car", "fin_car")},
                       "puntuacion": round(rrf(cid), 5)})
    return salida


# ---------------------------------------------------------------------------
# Reescritura de la consulta, con caché en disco
# ---------------------------------------------------------------------------
INSTRUCCION_REESCRITURA = """Reescribe esta pregunta como una consulta de búsqueda para un
índice de informes 10-K en INGLÉS. Usa el vocabulario del propio informe
(«ingresos» -> «revenue» o «net sales», «cuánto creció» -> «increased»).
Devuelve SOLO la consulta, sin comillas ni explicación."""


def _ruta_cache() -> Path:
    return raiz_repo() / "resultados" / "retrieval" / "reescrituras.json"


def reescribir(pregunta: str, clave: str | None = None, modelo: str = MODELO) -> str:
    """La pregunta convertida en consulta en inglés. Cacheada por `clave` (el id
    del golden) o por la pregunta literal, para no pagar dos veces."""
    ruta = _ruta_cache()
    cache = json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else {}
    k = clave or pregunta
    if k in cache and cache[k].get("pregunta") == pregunta:
        return cache[k]["consulta"]
    from langchain.chat_models import init_chat_model
    modelo_llm = init_chat_model(modelo, temperature=0)
    consulta = modelo_llm.invoke([{"role": "system", "content": INSTRUCCION_REESCRITURA},
                                  {"role": "user", "content": pregunta}]).text.strip().strip('"')
    cache[k] = {"pregunta": pregunta, "consulta": consulta, "modelo": modelo}
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return consulta


INSTRUCCION_REESCRITURA_CONSULTA = """Reescribe esta consulta de búsqueda para un índice de
informes 10-K de la SEC en INGLÉS. Mantén el sentido; usa el vocabulario literal que
usan los propios informes (Item 1A risk factors, MD&A, "net sales", "operating cash
flow", "stock split", "geographic region"). Si ya está bien, devuélvela tal cual.
Devuelve SOLO la consulta, sin comillas ni explicación."""


def reescribir_consulta(consulta: str, modelo: str = MODELO) -> str:
    """Reescritura de la CONSULTA que manda el modelo (no de la pregunta del
    golden): es lo que usa `search_filings` en a2_retrieval. Misma caché en
    disco, con prefijo `agente:` para no mezclarse con las del recall."""
    ruta = _ruta_cache()
    cache = json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else {}
    clave = f"agente:{consulta}"
    if clave in cache:
        return cache[clave]["consulta"]
    from langchain.chat_models import init_chat_model
    modelo_llm = init_chat_model(modelo, temperature=0)
    nueva = modelo_llm.invoke([{"role": "system", "content": INSTRUCCION_REESCRITURA_CONSULTA},
                               {"role": "user", "content": consulta}]).text.strip().strip('"')
    cache[clave] = {"pregunta": consulta, "consulta": nueva or consulta, "modelo": modelo}
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return nueva or consulta


# ---------------------------------------------------------------------------
# Configuraciones: item del golden -> fragmentos ordenados
# ---------------------------------------------------------------------------
def _filtros(item: dict) -> dict:
    return {"ticker": item.get("ticker"), "fiscal_year": item.get("fiscal_year"),
            "item": item.get("item_esperado")}


def _q(item: dict, reescrita: bool) -> str:
    return reescribir(item["pregunta"], item.get("id")) if reescrita else item["pregunta"]


CONFIGS: dict[str, Config] = {
    "1 · denso plano":                lambda it: denso_plano(_q(it, False)),
    "2 · + filtro de metadatos":      lambda it: con_filtros(_q(it, False), **_filtros(it)),
    "3 · + híbrido BM25":             lambda it: hibrido(_q(it, False), **_filtros(it)),
    "4 · + reescritura de consulta":  lambda it: con_filtros(_q(it, True), **_filtros(it)),
    "5 · reescritura + híbrido":      lambda it: hibrido(_q(it, True), **_filtros(it)),
}

COSTES = {
    "1 · denso plano": "0 llamadas al LLM",
    "2 · + filtro de metadatos": "0 llamadas al LLM",
    "3 · + híbrido BM25": "0 llamadas, +1 índice en memoria",
    "4 · + reescritura de consulta": "1 llamada al LLM por búsqueda",
    "5 · reescritura + híbrido": "1 llamada + índice léxico",
}


def recuperar_para(item: dict, arq: str | Arquitectura, k: int | None = None) -> list[dict]:
    """Los fragmentos que devolvería el retrieval de esa arquitectura para este
    ítem del golden set (con sus filtros). Es lo que alimenta la columna
    recall@5 de la tabla del agente."""
    a = arquitectura(arq)
    consulta = _q(item, a.reescritura)
    if a.hibrido:
        return hibrido(consulta, **_filtros(item), k=k)
    return con_filtros(consulta, **_filtros(item), k=k)


def medir_recall(configs: dict[str, Config] | None = None, *,
                 ruta_jsonl: str | Path = "data/golden_set.jsonl", k: int = K,
                 escribir: bool = True, verbose: bool = True) -> pd.DataFrame:
    """recall@k y posición del ancla para cada configuración. Escribe
    `resultados/retrieval/recall_por_config.csv` y `posiciones.csv`."""
    from agente.interfaz import leer_golden
    golden = [g for g in leer_golden(ruta_jsonl) if g.get("ancla_texto")]
    configs = configs or CONFIGS
    filas, posiciones = [], []
    for nombre, fn in configs.items():
        aciertos = 0
        for it in golden:
            ordenados = fn(it)
            ok = acierta(it, ordenados[:k])
            aciertos += ok
            posiciones.append({"config": nombre, "id": it["id"], "familia": it["familia"],
                               f"recall@{k}": ok, "pos_ancla": posicion_del_ancla(it, ordenados)})
        filas.append({"configuración": nombre, f"recall@{k}": aciertos / len(golden),
                      "aciertos": f"{aciertos}/{len(golden)}", "coste": COSTES.get(nombre, "")})
        if verbose:
            print(f"  {nombre:<32} {aciertos}/{len(golden)}  ({aciertos/len(golden):.1%})", flush=True)
    tabla = pd.DataFrame(filas)
    if escribir:
        carpeta = raiz_repo() / "resultados" / "retrieval"
        carpeta.mkdir(parents=True, exist_ok=True)
        tabla.to_csv(carpeta / "recall_por_config.csv", index=False)
        pd.DataFrame(posiciones).to_csv(carpeta / "posiciones.csv", index=False)
    return tabla


# ---------------------------------------------------------------------------
# Recall sobre las consultas REALES del agente (leídas de las trazas)
# ---------------------------------------------------------------------------
# La tabla del §4.4 mide el retriever con la pregunta del golden en español.
# Pero el agente NO manda esa pregunta: manda su propia consulta, casi siempre
# ya en inglés y con filtros. Lo que importa para el agente es: con las
# consultas que de verdad hizo, ¿habría visto el ancla con otro retriever?
# Esto lo mide sin gastar API (salvo la reescritura, cacheada).

def consultas_del_agente(arq: str | Arquitectura) -> dict[str, list[dict]]:
    """id del golden -> lista de {query, ticker, fiscal_year, item, rep} con
    todas las llamadas a search_filings que hizo esa arquitectura."""
    from agente.interfaz import dir_arquitectura
    a = arquitectura(arq)
    salida: dict[str, list[dict]] = {}
    for carpeta in sorted(dir_arquitectura(a).glob("rep*/crudo")):
        for f in sorted(carpeta.glob("*.json")):
            reg = json.loads(f.read_text(encoding="utf-8"))
            r = reg.get("resultado") or {}
            for c in r.get("llamadas", []):
                if c.get("name") != "search_filings":
                    continue
                args = c.get("args") or {}
                salida.setdefault(reg["item"]["id"], []).append({
                    "query": args.get("query", ""), "ticker": args.get("ticker"),
                    "fiscal_year": args.get("fiscal_year"), "item": args.get("item"),
                    "rep": reg.get("rep"),
                })
    return salida


def _buscador(reescrita: bool, hibrida: bool):
    def fn(consulta: str, **filtros) -> list[dict]:
        q = reescribir_consulta(consulta) if reescrita else consulta
        return hibrido(q, **filtros) if hibrida else con_filtros(q, **filtros)
    return fn


CONFIGS_AGENTE = {
    "denso + filtros del agente":      _buscador(False, False),
    "+ híbrido BM25":                  _buscador(False, True),
    "+ reescritura":                   _buscador(True, False),
    "reescritura + híbrido":           _buscador(True, True),
}


def recall_de_trazas(arq_origen: str | Arquitectura = "a1_guardrails", *,
                     configs: dict | None = None, ruta_jsonl: str | Path = "data/golden_set.jsonl",
                     k: int = K, escribir: bool = True, verbose: bool = True) -> pd.DataFrame:
    """Para cada pregunta con ancla en la que el agente buscó: ¿alguna de SUS
    búsquedas (con SUS filtros) habría puesto el ancla en el top-k con cada
    retriever? Una fila por configuración; `posiciones_trazas.csv` con la
    mejor posición del ancla por pregunta y configuración."""
    from agente.interfaz import leer_golden
    golden = {g["id"]: g for g in leer_golden(ruta_jsonl) if g.get("ancla_texto")}
    consultas = consultas_del_agente(arq_origen)
    ids = [i for i in golden if i in consultas]
    configs = configs or CONFIGS_AGENTE
    filas, posiciones = [], []
    for nombre, fn in configs.items():
        aciertos = 0
        for id_ in ids:
            it = golden[id_]
            mejor = None
            for c in consultas[id_]:
                if not c["query"]:
                    continue
                ordenados = fn(c["query"], ticker=c["ticker"], fiscal_year=c["fiscal_year"],
                               item=c["item"])
                pos = posicion_del_ancla(it, ordenados)
                if pos is not None and (mejor is None or pos < mejor):
                    mejor = pos
            ok = mejor is not None and mejor <= k
            aciertos += ok
            posiciones.append({"config": nombre, "id": id_, "familia": it["familia"],
                               "n_busquedas": len(consultas[id_]), f"recall@{k}": ok,
                               "mejor_pos_ancla": mejor})
        filas.append({"configuración": nombre, f"recall@{k}": aciertos / max(len(ids), 1),
                      "aciertos": f"{aciertos}/{len(ids)}"})
        if verbose:
            print(f"  {nombre:<32} {aciertos}/{len(ids)}", flush=True)
    tabla = pd.DataFrame(filas)
    if escribir:
        carpeta = raiz_repo() / "resultados" / "retrieval"
        carpeta.mkdir(parents=True, exist_ok=True)
        tabla.to_csv(carpeta / f"recall_trazas_{arquitectura(arq_origen).nombre}.csv", index=False)
        pd.DataFrame(posiciones).to_csv(
            carpeta / f"posiciones_trazas_{arquitectura(arq_origen).nombre}.csv", index=False)
    return tabla
