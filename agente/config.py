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
    limites_por_herramienta: bool = False  # A5: techo por herramienta según su coste
    max_xbrl: int = 16                 # get_xbrl_fact: barata (≈100 caracteres por llamada)
    max_busquedas: int = 6             # search_filings: cara (5 fragmentos ≈ 2.300 tokens)
    verificador_cifras: bool = False   # after_model: cifra vs. XBRL
    verificador_cita: bool = False     # after_model: cita ⊂ chunk citado
    cifras_de_texto: bool = False      # A6: contrato y verificación para cifras que solo están en el texto
    esquema_estricto: bool = False     # validadores de coherencia en la salida
    prompt: str = "base"               # "base" | "honesto" | "comparativas" | "cifras_texto"
    # --- retrieval (agente/retrieval.py) ---
    filtros_forzados: bool = False     # wrap_tool_call: rellena ticker/fy si faltan
    reescritura: bool = False          # consulta reescrita a inglés antes de buscar
    reescritura_rapida: bool = False   # experimento descartado: misma reescritura, razonamiento mínimo
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

# --- Segunda escalera (23-sep), medida sobre el golden difícil v2 y con el
# original como regresión. Cada peldaño ataca un fallo MEDIDO, no una idea:

A5 = replace(
    A4, nombre="a5_limites",
    limites_por_herramienta=True, max_llamadas=24,
    descripcion="+ límite por herramienta según su coste (XBRL 16, búsqueda 6, "
                "read_section 1) en vez de 8 llamadas en total. El modelo ya pide "
                "hasta 6 datos XBRL por turno: el límite global contaba llamadas, "
                "no turnos, y tumbaba gY-012 y gY-015.",
)

# Experimento que NO entra en la escalera (medido el 23-sep antes de lanzarlo):
# la reescritura con razonamiento mínimo tarda lo mismo que la normal (media
# 12,9 s frente a 12,8 s en tres llamadas en caliente, con 7-19 s de dispersión
# en ambas). Lo que cuesta es la ida y vuelta al proveedor, no el razonamiento.
# Se deja definida, sin registrar, como evidencia del resultado nulo.
X_REESCRITURA_RAPIDA = replace(
    A5, nombre="x_reescritura_rapida",
    reescritura_rapida=True,
    descripcion="A5 + reescritura con razonamiento mínimo. Descartada: no baja "
                "la latencia de la reescritura (12,9 s frente a 12,8 s).",
)

A6 = replace(
    A5, nombre="a6_cifras_texto",
    cifras_de_texto=True, prompt="cifras_texto",
    descripcion="+ contrato para cifras que solo están en el texto (fuente='texto', "
                "unidades completas, la cifra dentro de la cita) y un verificador que "
                "las comprueba contra la cita en vez de contra XBRL. Ataca gY-016..018.",
)

ARQUITECTURAS: dict[str, Arquitectura] = {a.nombre: a for a in (BASELINE, A1, A2, A3, A4,
                                                                 A5, A6)}
# `final` es A6 desde que A5 y A6 están medidas en los dos golden: iguala a A4 en
# el original (100 %, sin regresión) y la supera en el difícil (94,4 % frente a
# 72,2 %), con menos latencia que A5. Lo que corre `evaluar()` el día 24.
ARQUITECTURAS["final"] = A6


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
