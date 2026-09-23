"""Primitivas de medición, comunes a todos los grupos.

Copiadas de `clase/s2/miax_s2.py` (Guillermo Fajardo) para que la entrega no
dependa del material de aula. NO se modifican: si cada grupo escribe su propia
métrica, la tabla del informe deja de comparar nada.

Qué hay aquí y para qué:

- `acierta`, `recall_en_k`, `posicion_del_ancla`: la métrica del retrieval,
  anclada a una frase del informe y no a un chunk_id.
- `cuadra`: la tolerancia con la que una cifra "coincide" con el XBRL.
- `extraer_cifras`: números que afirma un texto, en unidades absolutas.
- `tokenizar`: el tokenizador de BM25 que conserva $, % y decimales.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# recall@k anclado al texto
# ---------------------------------------------------------------------------
_ESPACIOS = re.compile(r"\s+")


def normalizar(texto: str) -> str:
    """Espacios colapsados, minúsculas. Lo justo para comparar dos frases."""
    return _ESPACIOS.sub(" ", texto).strip().lower()


def acierta(item_golden: dict, recuperados: list[dict]) -> bool:
    """¿Alguno de los fragmentos recuperados contiene el ancla entera?

    Un fragmento del ejercicio equivocado NO cuenta aunque contenga el ancla:
    los 10-K repiten factores de riesgo palabra por palabra de un año a otro.
    """
    ancla = item_golden.get("ancla_texto")
    if not ancla:
        return False
    objetivo = normalizar(ancla)
    inicio, fin = item_golden.get("ancla_inicio"), item_golden.get("ancla_fin")

    for fragmento in recuperados:
        sin_metadatos = (fragmento.get("ticker") is None
                         and fragmento.get("fiscal_year") is None)
        mismo_documento = (
            fragmento.get("ticker") == item_golden.get("ticker")
            and int(fragmento.get("fiscal_year", -1))
            == int(item_golden.get("fiscal_year", -2))
        )
        if not (sin_metadatos or mismo_documento):
            continue
        # 1. Por tramo de caracteres, si el fragmento lo trae. Exacto.
        if (inicio is not None
                and fragmento.get("inicio_car") is not None
                and fragmento.get("item") == item_golden.get("item_esperado")
                and fragmento["inicio_car"] <= inicio
                and fragmento["fin_car"] >= fin):
            return True
        # 2. Por texto normalizado. No le exige nada al troceador.
        if objetivo in normalizar(fragmento.get("texto", "")):
            return True
    return False


def recall_en_k(golden: list[dict], recuperados_por_id: dict) -> float:
    """recall@k sobre los ítems del golden set que llevan ancla."""
    con_ancla = [g for g in golden if g.get("ancla_texto")]
    if not con_ancla:
        return 0.0
    return sum(acierta(g, recuperados_por_id.get(g["id"], []))
               for g in con_ancla) / len(con_ancla)


def posicion_del_ancla(item_golden: dict, ordenados: list[dict]) -> int | None:
    """Puesto (desde 1) del primer fragmento que contiene el ancla, o None.

    recall@5 dice sí o no; esto dice por cuánto. Un ancla en el puesto 6 y
    otra en el 900 fallan las dos y no son el mismo problema.
    """
    for posicion, fragmento in enumerate(ordenados, 1):
        if acierta(item_golden, [fragmento]):
            return posicion
    return None


# ---------------------------------------------------------------------------
# Cifras
# ---------------------------------------------------------------------------
_MULTIPLICADOR = {
    "billion": 1e9, "billones": 1e9, "mil millones": 1e9,
    "million": 1e6, "millones": 1e6, "millón": 1e6,
    "thousand": 1e3, "miles": 1e3,
}
_CIFRA = re.compile(
    r"(\d[\d.,]*)\s*(billion|billones|mil millones|million|millones|millón|"
    r"thousand|miles)?",
    re.IGNORECASE,
)


def extraer_cifras(texto: str) -> list[float]:
    """Los números que afirma un texto, en unidades absolutas.

    Asume la convención española (punto de millares, coma decimal) cuando el
    número la usa de forma inequívoca; si no, la inglesa.
    """
    encontrados: list[float] = []
    for crudo, sufijo in _CIFRA.findall(texto):
        limpio = crudo.rstrip(".,")
        if not any(c.isdigit() for c in limpio):
            continue
        if "," in limpio and "." in limpio:
            if limpio.rfind(",") > limpio.rfind("."):
                limpio = limpio.replace(".", "").replace(",", ".")
            else:
                limpio = limpio.replace(",", "")
        elif "," in limpio:
            entera, _, decimal = limpio.rpartition(",")
            limpio = (f"{entera.replace(',', '')}.{decimal}"
                      if len(decimal) != 3 else limpio.replace(",", ""))
        elif "." in limpio:
            entera, _, decimal = limpio.rpartition(".")
            if len(decimal) == 3 and entera:
                limpio = limpio.replace(".", "")
        try:
            valor = float(limpio)
        except ValueError:
            continue
        encontrados.append(valor * _MULTIPLICADOR.get(sufijo.lower(), 1.0)
                           if sufijo else valor)
    return encontrados


TOLERANCIA = 0.01   # 1 %: redondear a «281.700 millones» no es inventarse un número


def cuadra(afirmada: float, real: float, tolerancia: float = TOLERANCIA) -> bool:
    """¿La cifra afirmada coincide con la del XBRL, con tolerancia relativa?"""
    if real == 0:
        return afirmada == 0
    return abs(afirmada - real) / abs(real) <= tolerancia


# ---------------------------------------------------------------------------
# BM25
# ---------------------------------------------------------------------------
_PALABRAS = re.compile(r"[a-z0-9$%.]+")


def tokenizar(texto: str) -> list[str]:
    """Minúsculas y palabras, conservando `$`, `%` y los puntos decimales.

    El caso en que BM25 gana al embedding son tickers, años y cifras. Un
    tokenizador que se coma el `$` tira justo la señal que se venía a buscar.
    """
    return _PALABRAS.findall(texto.lower())
