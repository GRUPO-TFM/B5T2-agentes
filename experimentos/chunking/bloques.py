# -*- coding: utf-8 -*-
"""Segmentación de una sección en bloques y detección de tablas.

Todo parte de `secciones.jsonl`. Dos primitivas que usan las cuatro variantes:

- `unidades()`: parte el texto por encabezados. Un encabezado es un párrafo
  cuya primera línea es corta y no termina en punto. Es la mejor regla que se
  puede escribir sobre el texto plano; **no** reproduce la del baseline, que
  venía del marcado HTML (ver `reproduccion.py`).
- `bloques_tabla()`: las tablas. El LEEME garantiza que el tabulador solo
  aparece dentro de una tabla, así que la detección es exacta y no una
  heurística: un bloque de tabla es una racha maximal de líneas con `\t`.
"""

from __future__ import annotations

# Viñetas que usan estos 10-K. Una línea que empieza por viñeta es un ítem de
# lista, no un encabezado, aunque sea corta y no acabe en punto.
VINETAS = "•·–—-●▪*"

LARGO_MAX_ENCABEZADO = 87


def es_encabezado(parrafo: str) -> bool:
    """¿Este párrafo abre una sección?

    Corto, sin punto final, sin dos puntos (eso es un pie de lista: «Our
    success depends on our ability to:») y sin viñeta inicial.
    """
    primera = parrafo.split("\n")[0].strip()
    if not primera or len(primera) > LARGO_MAX_ENCABEZADO:
        return False
    if primera.endswith((".", ":", ";", ",")):
        return False
    return primera[:1] not in VINETAS


def unidades(texto: str) -> list[tuple[int, int]]:
    """(inicio, fin) de cada unidad encabezado→siguiente encabezado."""
    partes = texto.split("\n\n")
    desplazamientos = []
    cursor = 0
    for parte in partes:
        desplazamientos.append(cursor)
        cursor += len(parte) + 2

    cortes = [0]
    for i in range(1, len(partes)):
        if es_encabezado(partes[i]):
            cortes.append(desplazamientos[i])
    cortes.append(len(texto) + 2)
    return [(cortes[i], cortes[i + 1] - 2) for i in range(len(cortes) - 1)]


def bloques_tabla(texto: str) -> list[tuple[int, int]]:
    """(inicio, fin) de cada tabla: racha maximal de líneas con tabulador."""
    salida = []
    cursor = inicio = fin = None
    cursor = 0
    for linea in texto.split("\n"):
        a, b = cursor, cursor + len(linea)
        cursor = b + 1
        if "\t" in linea:
            if inicio is None:
                inicio = a
            fin = b
        elif inicio is not None:
            salida.append((inicio, fin))
            inicio = None
    if inicio is not None:
        salida.append((inicio, fin))
    return salida


def recortar(texto: str, inicio: int, fin: int) -> tuple[int, int]:
    """Quita el espacio en blanco de los bordes sin perder los offsets."""
    while inicio < fin and texto[inicio].isspace():
        inicio += 1
    while fin > inicio and texto[fin - 1].isspace():
        fin -= 1
    return inicio, fin


def empaquetar(
    texto: str,
    uds: list[tuple[int, int]],
    contar,
    tope: int,
) -> list[tuple[int, int]]:
    """Agrupa unidades consecutivas mientras quepan en `tope` tokens.

    Hace falta porque la regla de encabezado sobre texto plano parte mucho
    más fino que la del baseline (3.311 unidades frente a 1.077 bloques):
    sin agrupar saldrían miles de fragmentos diminutos. Una unidad que ya no
    cabe ella sola se devuelve entera y la ventanea quien llame.
    """
    salida: list[tuple[int, int]] = []
    grupo: list[tuple[int, int]] = []
    acumulado = 0

    def cerrar():
        nonlocal grupo, acumulado
        if grupo:
            salida.append((grupo[0][0], grupo[-1][1]))
            grupo, acumulado = [], 0

    for a, b in uds:
        n = contar(texto[a:b])
        if n > tope:
            cerrar()
            salida.append((a, b))
            continue
        if grupo and acumulado + n > tope:
            cerrar()
        grupo.append((a, b))
        acumulado += n
    cerrar()
    return salida
