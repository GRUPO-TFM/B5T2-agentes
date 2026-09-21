"""Las arquitecturas que se comparan, como configuración y no como ramas.

Cada preset AÑADE algo al anterior y no quita nada. Así la diferencia entre
dos filas consecutivas de la tabla del informe es atribuible a una sola cosa,
y el mismo código (mismo commit) genera todas las filas.

Para probar algo que quizá no funcione, se añade un preset nuevo (por ejemplo
`x_hibrido_sin_reescritura`) y se corre igual: su carpeta de resultados se
queda como evidencia para la diapositiva de «lo que probamos».
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace

MODELO = "openrouter:google/gemini-3.8-flash"   # fijo en todas las arquitecturas
REPETICIONES = 3                                # el modelo no es determinista
K = 5                                           # top-k del retrieval que se mide


@dataclass(frozen=True)
class Arquitectura:
    nombre: str
    # --- guardrails (agente/middleware.py) ---
    limites: bool = False              # ToolCallLimit + ModelCallLimit
    max_llamadas: int = 8              # herramientas por invocación
    max_read_section: int = 1          # la herramienta cara, aparte
    max_vueltas_modelo: int = 10       # acota también el bucle verificador→modelo
    verificador_cifras: bool = False   # after_model: cifra vs. XBRL
    verificador_cita: bool = False     # after_model: cita ⊂ chunk citado
    esquema_estricto: bool = False     # validadores de coherencia en la salida
    prompt: str = "base"               # "base" | "honesto" | "comparativas"
    # --- retrieval (agente/retrieval.py) ---
    filtros_forzados: bool = False     # wrap_tool_call: rellena ticker/fy si faltan
    reescritura: bool = False          # consulta reescrita a inglés antes de buscar
    hibrido: bool = False              # BM25 + denso con RRF
    k: int = K
    # --- documentación ---
    descripcion: str = ""

    def como_dict(self) -> dict:
        return asdict(self)


BASELINE = Arquitectura(
    nombre="baseline",
    descripcion="El agente del día 10, tal cual. Congelado antes de tocar nada.",
)

A1 = replace(
    BASELINE, nombre="a1_guardrails",
    limites=True, verificador_cifras=True, verificador_cita=True,
    esquema_estricto=True, prompt="honesto",
    descripcion="+ límites de llamadas, verificador XBRL, verificador de cita, "
                "esquema estricto y prompt de honestidad.",
)

A2 = replace(
    A1, nombre="a2_retrieval",
    filtros_forzados=True, reescritura=True,
    descripcion="+ filtros por metadatos forzados y reescritura de la consulta "
                "a inglés.",
)

# A3 y A4 estaban juntos y se separaron: el híbrido es retrieval y el prompt de
# comparativas es procedimiento. Van a las mismas 8 preguntas, así que mezclados
# no habría forma de atribuir el salto a uno o a otro.
A3 = replace(
    A2, nombre="a3_hibrido",
    hibrido=True,
    descripcion="+ híbrido BM25 con RRF, medido DESPUÉS de la reescritura.",
)

A4 = replace(
    A3, nombre="a4_comparativas",
    prompt="comparativas",
    descripcion="+ procedimiento explícito de comparativas y conceptos por "
                "acción (splits).",
)

ARQUITECTURAS: dict[str, Arquitectura] = {a.nombre: a for a in (BASELINE, A1, A2, A3, A4)}
ARQUITECTURAS["final"] = A4          # alias: lo que corre `evaluar()` el día 24


def arquitectura(nombre: str | Arquitectura) -> Arquitectura:
    if isinstance(nombre, Arquitectura):
        return nombre
    try:
        return ARQUITECTURAS[nombre]
    except KeyError:
        raise KeyError(
            f"Arquitectura desconocida: {nombre!r}. "
            f"Disponibles: {', '.join(ARQUITECTURAS)}"
        ) from None
