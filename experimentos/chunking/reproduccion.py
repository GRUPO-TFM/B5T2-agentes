# -*- coding: utf-8 -*-
"""Puerta de reproducción del baseline.

Conclusión, para no hacerla buscar: **no se puede reproducir exactamente
partiendo solo de `secciones.jsonl`**. Lo que sí queda establecido:

1. El baseline cuenta tokens con `tiktoken cl100k_base` (coincide con
   `n_tokens` en el 100 % de una muestra de 60 y explica 1.063 de 1.077
   decisiones de partición a 500).
2. El troceado es: partir en bloques por encabezado y **ventanear cada
   bloque por separado** a 500 tokens con solape de 80, recortando el
   espacio en blanco de los bordes. No hay empaquetado: 1.077 bloques +
   672 ventanas de continuación = 1.749 fragmentos.
3. Las fronteras de bloque **no salen del texto plano**: el 84,4 % de ellas
   no las explica el tamaño (el párrafo siguiente cabía de sobra), y el
   88,6 % coincide con un `<span>` en negrita del HTML original, frente al
   69 % de los párrafos parecidos que no son frontera. El corpus se
   construyó desde `fuentes_10k_html.zip`, donde los encabezados están
   marcados; `secciones.jsonl` ya no lleva esa marca.

Por eso el mismo texto («Risks Related to Our Industry and Markets») es
frontera cuando es un encabezado real y no lo es cuando aparece repetido
dentro del «Risk Factors Summary».

Este módulo mide las tres cosas para que el dato sea auditable.
"""

from __future__ import annotations

from collections import defaultdict

from agente.corpus import cargar_chunks, cargar_secciones

from experimentos.chunking.bloques import empaquetar, recortar, unidades
from experimentos.chunking.tokenizacion import (
    contar_cl100k,
    trocear_por_tokens_cl100k,
)

VENTANA = 500
SOLAPE = 80


def _por_documento():
    secciones = cargar_secciones()
    texto_de = {
        (r.ticker, int(r.fiscal_year), r.item): r.texto
        for r in secciones.itertuples()
    }
    chunks = defaultdict(list)
    for c in cargar_chunks():
        chunks[(c["ticker"], int(c["fiscal_year"]), c["item"])].append(c)
    for lista in chunks.values():
        lista.sort(key=lambda c: c["posicion"])
    return texto_de, chunks


def bloques_reales(lista: list[dict]) -> list[tuple[int, int]]:
    """Bloques del baseline, deducidos de los huecos entre fragmentos.

    Solo se usa para *medir* la puerta, nunca para construir una variante:
    sale de `chunks.jsonl`, que §3 prohíbe como punto de partida.
    """
    salida = []
    inicio = 0
    for a, b in zip(lista, lista[1:]):
        if b["inicio_car"] > a["fin_car"]:
            salida.append((inicio, a["fin_car"]))
            inicio = b["inicio_car"]
    salida.append((inicio, lista[-1]["fin_car"]))
    return salida


def ventanear(texto: str, bloques: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """El troceado del baseline: cada bloque, por separado, a 500/80."""
    salida = []
    for a, b in bloques:
        for ta, tb in trocear_por_tokens_cl100k(texto[a:b], VENTANA, SOLAPE):
            salida.append(recortar(texto, a + ta, min(a + tb, b)))
    return salida


def informe() -> dict:
    texto_de, chunks = _por_documento()

    identicos = total_con_bloques = n_bloques = 0
    total_desde_cero = identicos_desde_cero = 0
    cabia = no_cabia = 0

    for clave, lista in chunks.items():
        texto = texto_de[clave]
        suyos = {(c["inicio_car"], c["fin_car"]) for c in lista}

        bloques = bloques_reales(lista)
        n_bloques += len(bloques)
        mios = ventanear(texto, bloques)
        total_con_bloques += len(mios)
        identicos += len(set(mios) & suyos)

        desde_cero = ventanear(
            texto,
            empaquetar(texto, unidades(texto), contar_cl100k, VENTANA),
        )
        total_desde_cero += len(desde_cero)
        identicos_desde_cero += len(set(desde_cero) & suyos)

        # ¿Cierra el bloque porque no cabía lo siguiente, o porque sí o sí?
        for (a1, b1), (a2, b2) in zip(bloques, bloques[1:]):
            if contar_cl100k(texto[a1:b1]) > VENTANA:
                continue
            siguiente = texto[a2:b2].split("\n\n")[0]
            if contar_cl100k(texto[a1:b1]) + contar_cl100k(siguiente) <= VENTANA:
                cabia += 1
            else:
                no_cabia += 1

    entregados = sum(len(v) for v in chunks.values())
    item_1a = sum(len(v) for k, v in chunks.items() if k[2] == "1A")
    return {
        "chunks_entregados": entregados,
        "chunks_item_1A": item_1a,
        "bloques_del_baseline": n_bloques,
        "con_bloques_reales": total_con_bloques,
        "identicos_con_bloques_reales": identicos,
        "desde_secciones": total_desde_cero,
        "identicos_desde_secciones": identicos_desde_cero,
        "fronteras_que_no_explica_el_tamano": cabia,
        "fronteras_que_explica_el_tamano": no_cabia,
    }


if __name__ == "__main__":
    datos = informe()
    ancho = max(len(k) for k in datos)
    for k, v in datos.items():
        print(f"{k:<{ancho}} : {v}")
