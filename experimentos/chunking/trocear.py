# -*- coding: utf-8 -*-
"""Las cinco variantes de troceado, sobre una misma segmentación.

Diseño 2×2 más la reimplementación del baseline. Lo único que cambia entre
variantes es **cómo se trata la prosa y cómo se tratan las tablas**:

| Variante | Segmentación | Prosa            | Tablas                      | Tokens |
| -------- | ------------ | ---------------- | --------------------------- | ------ |
| A        | encabezados  | ventana 500/80   | como la prosa               | cl100k |
| A′       | encabezados  | ventana 480/80   | como la prosa               | BGE    |
| B        | encabezados  | por oraciones    | como la prosa               | BGE    |
| C        | encabezados  | ventana 480/80   | atómicas, cabecera repetida | BGE    |
| D        | encabezados  | por oraciones    | atómicas, cabecera repetida | BGE    |

La segmentación por encabezados es **idéntica en las cinco**
(`bloques.unidades`) y no se toca entre variantes: es la constante que
permite atribuir cualquier diferencia a la estrategia y no al troceado
previo.

Tres reglas que §3 pide fijar explícitamente, con el criterio elegido:

**(a) Qué es el encabezado de columnas.** Las filas iniciales de la tabla
que no contienen ninguna *celda numérica*, entendiendo por tal una celda que
sea solo una cifra (con `$`, `%`, paréntesis de negativo, comas y
decimales). «Jan 28, 2024» lleva dígitos pero no es una celda numérica, así
que una fila de fechas cuenta como cabecera, que es lo que se quiere.

**(b) Cuándo el texto previo es contexto de la tabla.** El párrafo
inmediatamente anterior, si es una línea corta sin punto final — la misma
forma que un encabezado. Es el «(In millions, except par value)» o el «Year
Ended» que da sentido a las cifras. Se arrastra con la tabla y se repite en
cada fragmento si la tabla se parte.

**(c) Tamaño mínimo de fragmento.** Al partir una tabla por filas no se
corta «hasta llenar y lo que sobre aparte», sino que las filas se reparten
entre `ceil(total/tope)` fragmentos lo más igualados posible. Así una tabla
de 1,1 topes no deja un fragmento de 10 tokens. Además, una tabla que cabe
entera nunca se emite sola: se empaqueta con la prosa vecina como cualquier
otra pieza.

**Offsets.** `inicio_car` y `fin_car` siempre se refieren al cuerpo del
fragmento dentro del texto de la sección. La cabecera repetida en una tabla
partida **no** está en ese tramo: va en `encabezado_repetido` y se antepone
al `texto` que se embebe. Así el matching por tramo y el evaluador de citas
siguen cuadrando.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from experimentos.chunking.bloques import bloques_tabla, recortar, unidades
from experimentos.chunking.tokenizacion import (
    TOPE_DURO,
    contar_bge,
    contar_cl100k,
    trocear_por_tokens_bge,
    trocear_por_tokens_cl100k,
)

SOLAPE = 80

# Una celda que es solo una cifra: $ , . % paréntesis de negativo, guion de
# celda vacía. Si una fila tiene una de estas, ya son datos y no cabecera.
CELDA_NUMERICA = re.compile(r"^\(?\$?\s*-?[\d,]+(?:\.\d+)?\s*\)?%?$")

# Fin de oración: puntuación de cierre seguida de espacio y algo que puede
# abrir oración. Los guardas evitan cortar en abreviaturas y en «U.S.».
_ABREV = (
    r"(?<!\bMr)(?<!\bMrs)(?<!\bMs)(?<!\bDr)(?<!\bInc)(?<!\bCorp)(?<!\bLtd)"
    r"(?<!\bCo)(?<!\bNo)(?<!\bvs)(?<!\bU\.S)(?<!\bi\.e)(?<!\be\.g)(?<!\bSt)"
)
FIN_ORACION = re.compile(_ABREV + r"(?<=[.!?])[\"')\]]?\s+(?=[A-Z(\"$•])")


@dataclass
class Fragmento:
    """Un fragmento antes de convertirse en fila de `chunks.jsonl`."""

    inicio_car: int
    fin_car: int
    encabezado_repetido: str = ""

    def texto(self, seccion: str) -> str:
        cuerpo = seccion[self.inicio_car : self.fin_car]
        if self.encabezado_repetido:
            return f"{self.encabezado_repetido}\n{cuerpo}"
        return cuerpo


@dataclass
class Pieza:
    """Trozo de una unidad, con su naturaleza."""

    inicio: int
    fin: int
    tabla: bool = False
    atomica: bool = False


# ---------------------------------------------------------------------------
# Oraciones
# ---------------------------------------------------------------------------
def _lineas(texto: str, inicio: int, fin: int) -> list[tuple[int, int]]:
    salida = []
    cursor = inicio
    for linea in texto[inicio:fin].split("\n"):
        salida.append((cursor, cursor + len(linea)))
        cursor += len(linea) + 1
    return salida


def oraciones(texto: str, inicio: int, fin: int) -> list[tuple[int, int]]:
    """(ini, fin) de cada oración del tramo, sin cortar ninguna.

    Se respetan los saltos de línea: una línea es una frontera dura, porque
    en estos informes cada viñeta y cada párrafo van en su propia línea y
    unirlos crearía oraciones que no existen.
    """
    salida = []
    for a, b in _lineas(texto, inicio, fin):
        crudo = texto[a:b]
        if not crudo.strip():
            continue
        ult = 0
        for m in FIN_ORACION.finditer(crudo):
            corte = m.start() + 1
            if crudo[ult:corte].strip():
                salida.append((a + ult, a + corte))
            ult = m.end()
        if crudo[ult:].strip():
            salida.append((a + ult, b))
    return salida


# ---------------------------------------------------------------------------
# Tablas
# ---------------------------------------------------------------------------
def _es_fila_de_datos(linea: str) -> bool:
    return any(
        CELDA_NUMERICA.match(c.strip()) for c in linea.split("\t") if c.strip()
    )


def encabezado_de_columnas(texto: str, inicio: int, fin: int) -> tuple[int, int]:
    """Regla (a): filas iniciales sin ninguna celda numérica."""
    corte = inicio
    for a, b in _lineas(texto, inicio, fin):
        if _es_fila_de_datos(texto[a:b]):
            break
        corte = b
    return inicio, corte


def contexto_de_tabla(texto: str, inicio_tabla: int, limite: int) -> str:
    """Regla (b): el párrafo anterior, si es línea corta sin punto final."""
    for linea in reversed(texto[limite:inicio_tabla].split("\n")):
        if not linea.strip():
            continue
        limpio = linea.strip()
        if len(limpio) <= 120 and not limpio.endswith("."):
            return limpio
        return ""
    return ""


# ---------------------------------------------------------------------------
# Troceado
# ---------------------------------------------------------------------------
def _piezas(
    seccion: str, a: int, b: int, tablas_atomicas: bool, separar: bool
) -> list[Pieza]:
    """Divide una unidad en prosa y tablas.

    `separar=False` devuelve la unidad de una pieza: es lo que hace el
    baseline, que no distingue tabla de prosa. A lo reproduce así. A′, B, C
    y D sí separan, para que cada naturaleza reciba su tratamiento y para
    que A′ sea una referencia comparable con B, C y D.
    """
    tablas = [(a + i, a + f) for i, f in bloques_tabla(seccion[a:b])]
    if not tablas or not separar:
        return [Pieza(a, b)]

    salida: list[Pieza] = []
    cursor = a
    for ti, tf in tablas:
        # La tabla se lleva su línea de contexto: deja de ser prosa.
        ctx = contexto_de_tabla(seccion, ti, cursor) if tablas_atomicas else ""
        fin_prosa = ti
        if ctx:
            encontrado = seccion.rfind(ctx, cursor, ti)
            if encontrado > cursor:
                fin_prosa = encontrado
        if fin_prosa > cursor and seccion[cursor:fin_prosa].strip():
            salida.append(Pieza(*recortar(seccion, cursor, fin_prosa)))
        salida.append(
            Pieza(
                *recortar(seccion, fin_prosa, tf),
                tabla=True,
                atomica=tablas_atomicas,
            )
        )
        cursor = tf
    if cursor < b and seccion[cursor:b].strip():
        salida.append(Pieza(*recortar(seccion, cursor, b)))
    return salida


def _partir_tabla(seccion: str, pieza: Pieza, contar, tope: int) -> list[Fragmento]:
    """Parte una tabla por filas repitiendo la cabecera. Reglas (a) y (c)."""
    hi, hf = encabezado_de_columnas(seccion, pieza.inicio, pieza.fin)
    cabecera = seccion[hi:hf].strip("\n")
    filas = [
        (a, b)
        for a, b in _lineas(seccion, hf if cabecera else pieza.inicio, pieza.fin)
        if seccion[a:b].strip()
    ]
    if not filas:
        return [Fragmento(pieza.inicio, pieza.fin)]

    coste_cabecera = contar(cabecera) + 1 if cabecera else 0
    total = contar(seccion[filas[0][0] : filas[-1][1]])
    # Regla (c): repartir las filas entre n fragmentos igualados, no llenar
    # y dejar una cola diminuta.
    n = max(1, math.ceil(total / max(1, tope - coste_cabecera)))
    por_fragmento = math.ceil(len(filas) / n)

    salida = []
    for i in range(0, len(filas), por_fragmento):
        grupo = filas[i : i + por_fragmento]
        ini, fin = recortar(seccion, grupo[0][0], grupo[-1][1])
        salida.append(Fragmento(ini, fin, encabezado_repetido=cabecera))
    # El primer fragmento arranca en la propia cabecera: no hay que repetirla.
    if salida and cabecera:
        salida[0] = Fragmento(*recortar(seccion, pieza.inicio, salida[0].fin_car))
    return salida


def _ventanear(seccion, ini, fin, tope, solape, bge) -> list[Fragmento]:
    partir = trocear_por_tokens_bge if bge else trocear_por_tokens_cl100k
    return [
        Fragmento(*recortar(seccion, ini + ta, min(ini + tb, fin)))
        for ta, tb in partir(seccion[ini:fin], tope, solape)
    ]


def _agrupar_oraciones(seccion, ini, fin, contar, tope, solape) -> list[Fragmento]:
    """Agrupa oraciones hasta el tope sin cortar ninguna, con solape."""
    ors = oraciones(seccion, ini, fin)
    if not ors:
        return []
    costes = [contar(seccion[a:b]) for a, b in ors]
    salida: list[Fragmento] = []
    i = 0
    while i < len(ors):
        j, total = i, 0
        while j < len(ors) and (total + costes[j] <= tope or j == i):
            total += costes[j]
            j += 1
        salida.append(Fragmento(*recortar(seccion, ors[i][0], ors[j - 1][1])))
        if j >= len(ors):
            break
        # Solape: retroceder oraciones enteras hasta ~`solape` tokens.
        atras, acumulado = j, 0
        while atras > i + 1 and acumulado + costes[atras - 1] <= solape:
            atras -= 1
            acumulado += costes[atras]
        i = atras if atras > i else j
    return salida


def trocear(
    seccion: str,
    *,
    por_oraciones: bool = False,
    tablas_atomicas: bool = False,
    bge: bool = True,
    tope: int = TOPE_DURO,
    solape: int = SOLAPE,
    separar_tablas: bool = True,
) -> list[Fragmento]:
    """Trocea una sección entera con la configuración de una variante."""
    contar = contar_bge if bge else contar_cl100k

    # 1. Segmentación común: encabezados.
    piezas: list[Pieza] = []
    for a, b in unidades(seccion):
        if not seccion[a:b].strip():
            continue
        piezas.extend(_piezas(seccion, a, b, tablas_atomicas, separar_tablas))

    # 2. Empaquetar piezas consecutivas mientras quepan; las que no quepan
    #    se desbordan con la regla que le toque a cada una.
    salida: list[Fragmento] = []
    grupo: list[Pieza] = []
    acumulado = 0

    def cerrar():
        nonlocal grupo, acumulado
        if grupo:
            salida.append(
                Fragmento(*recortar(seccion, grupo[0].inicio, grupo[-1].fin))
            )
            grupo, acumulado = [], 0

    for pieza in piezas:
        coste = contar(seccion[pieza.inicio : pieza.fin])
        if coste > tope:
            cerrar()
            if pieza.tabla and pieza.atomica:
                salida.extend(_partir_tabla(seccion, pieza, contar, tope))
            elif por_oraciones and not pieza.tabla:
                salida.extend(
                    _agrupar_oraciones(
                        seccion, pieza.inicio, pieza.fin, contar, tope, solape
                    )
                )
            else:
                salida.extend(
                    _ventanear(seccion, pieza.inicio, pieza.fin, tope, solape, bge)
                )
            continue
        if grupo and acumulado + coste > tope:
            cerrar()
        grupo.append(pieza)
        acumulado += coste
    cerrar()
    return [f for f in salida if seccion[f.inicio_car : f.fin_car].strip()]


VARIANTES = {
    # A reproduce el baseline: ni separa tablas ni las trata aparte.
    "A": dict(
        por_oraciones=False,
        tablas_atomicas=False,
        bge=False,
        tope=500,
        separar_tablas=False,
    ),
    "Ap": dict(por_oraciones=False, tablas_atomicas=False, bge=True, tope=TOPE_DURO),
    "B": dict(por_oraciones=True, tablas_atomicas=False, bge=True, tope=TOPE_DURO),
    "C": dict(por_oraciones=False, tablas_atomicas=True, bge=True, tope=TOPE_DURO),
    "D": dict(por_oraciones=True, tablas_atomicas=True, bge=True, tope=TOPE_DURO),
}
