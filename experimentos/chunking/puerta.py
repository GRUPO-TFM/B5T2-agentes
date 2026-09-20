# -*- coding: utf-8 -*-
"""Criterios débiles que sustituyen a la puerta de reproducción exacta.

Se fijaron **antes** de medir, al saber que la identidad bit a bit era
inalcanzable desde `secciones.jsonl` (ver `reproduccion.py`):

1. cobertura de anclas del 100 % en A;
2. recall@5 de A a menos de una pregunta del índice entregado;
3. nº de fragmentos de A dentro del ±2 % de 1.749.
"""

from __future__ import annotations

from experimentos.chunking.evaluar import (
    cargar_golden,
    cargar_indice,
    cobertura_anclas,
    con_ancla,
    evaluar_variante,
)

OBJETIVO_CHUNKS = 1749
TOLERANCIA = 0.02


def comprobar() -> dict:
    golden = cargar_golden()
    sin_reescribir = {}

    _, meta_a = cargar_indice("A")
    cubiertas, fallan = cobertura_anclas(meta_a, golden)
    n_anclas = len(con_ancla(golden))

    ent = evaluar_variante("Entregado", golden, sin_reescribir, con_filtro=True)
    a = evaluar_variante("A", golden, sin_reescribir, con_filtro=True)

    difieren = [
        (
            i,
            ent["por_pregunta"][i]["acierto"],
            a["por_pregunta"][i]["acierto"],
            ent["por_pregunta"][i]["posicion"],
            a["por_pregunta"][i]["posicion"],
        )
        for i in ent["por_pregunta"]
        if ent["por_pregunta"][i]["acierto"] != a["por_pregunta"][i]["acierto"]
    ]

    desvio = abs(len(meta_a) - OBJETIVO_CHUNKS) / OBJETIVO_CHUNKS
    return {
        "cobertura": (cubiertas, n_anclas, fallan),
        "cobertura_ok": cubiertas == n_anclas,
        "recall_entregado": ent["recall_5"],
        "recall_A": a["recall_5"],
        "aciertos_entregado": ent["aciertos"],
        "aciertos_A": a["aciertos"],
        "recall_ok": abs(ent["aciertos"] - a["aciertos"]) <= 1,
        "preguntas_que_difieren": difieren,
        "n_chunks_A": len(meta_a),
        "desvio_chunks": desvio,
        "chunks_ok": desvio <= TOLERANCIA,
    }


if __name__ == "__main__":
    r = comprobar()
    c, n, fallan = r["cobertura"]
    print(f"1. cobertura de anclas en A: {c}/{n}  -> {'OK' if r['cobertura_ok'] else 'FALLA ' + str(fallan)}")
    print(f"2. recall@5  entregado {r['aciertos_entregado']}/{n} ({r['recall_entregado']:.1%})"
          f"   A {r['aciertos_A']}/{n} ({r['recall_A']:.1%})  -> {'OK' if r['recall_ok'] else 'FALLA'}")
    for i, e, a, pe, pa in r["preguntas_que_difieren"]:
        print(f"     {i}: entregado {'acierta' if e else 'falla'} (pos {pe}) | A {'acierta' if a else 'falla'} (pos {pa})")
    print(f"3. fragmentos de A: {r['n_chunks_A']} vs 1749 ({r['desvio_chunks']:+.2%})"
          f"  -> {'OK' if r['chunks_ok'] else 'FALLA'}")
