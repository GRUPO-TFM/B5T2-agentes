# Cómo se evalúa: el harness

*Complemento operativo de `plan_evaluacion_y_mejoras.md`. Rama `mejoras`.*

## Idea

Una invocación del agente se ejecuta **una vez** y se guarda entera en un JSON.
Los evaluadores y las tablas se derivan de lo guardado sin repetir preguntas
del agente. El recall puede llamar al modelo si falta una consulta reescrita
en la caché. Las arquitecturas son **presets de configuración**
(`agente/config.py`), no ramas: el mismo commit genera todas las filas.

```
baseline → a1_guardrails → a2_retrieval → a3_hibrido → a4_comparativas
         → a5_limites → a6_cifras_texto (= final)
```

Cada preset añade algo al anterior y no quita nada.

## Comandos

```powershell
# tests sin API (0,5 s)
uv run --with pytest pytest -q

# baseline, 3 repeticiones, puntuado, y la comparativa actualizada
uv run python -m agente.cli todo --arq baseline --reps 3

# una arquitectura más, cuando esté lista
uv run python -m agente.cli todo --arq a1_guardrails --reps 3

# solo repetir las preguntas que fallaron con excepción
uv run python -m agente.cli ejecutar --arq baseline --rep 2 --ids gX-013,gX-016 --forzar
uv run python -m agente.cli puntuar  --arq baseline --rep 2

# la tabla del retrieval (§4.4): cinco configuraciones, recall@5 y posición del ancla
uv run python -m agente.cli recall

# repuntuar las arquitecturas probadas en ambos golden sets y regenerar
# las tablas baseline frente a final (Markdown y CSV, con coste y latencia)
uv run python -m agente.lotes reconciliar

# ver una trayectoria guardada, sin gastar
uv run python -m agente.cli traza --arq baseline --rep 1 --id gX-016

# una pregunta suelta
uv run python -m agente.cli pregunta "¿Cuál fue el margen bruto de Amazon en FY2025?" --arq final
```

## Lo que sale

```
resultados/
├── retrieval/
│   ├── recall_por_config.csv      recall@5 por configuración
│   ├── posiciones.csv             id × config → puesto del ancla
│   └── reescrituras.json          caché de la reescritura LLM (no se paga dos veces)
├── agente/<arquitectura>/
│   ├── config.json                flags, modelo, commit, fecha
│   ├── rep1/crudo/<id>.json       la trayectoria entera + respuesta + tokens
│   ├── rep1/tabla.csv             una fila por pregunta, ya evaluada
│   └── resumen.csv                una fila por repetición
├── comparativa.csv                una fila por arquitectura (media ± rango)
├── comparativa_por_familia.csv
├── comparativa.md                 la tabla completa, mejor valor en negrita
└── reconciliacion/
    ├── baseline_vs_final_original.md/.csv
    └── baseline_vs_final_dificil.md/.csv
```

Se commitea todo `resultados/`. El enunciado pide resultados regenerables, no
ausentes; y el baseline hay que congelarlo antes de mejorar.

## Columnas por pregunta (`tabla.csv`)

| Columna | Qué es |
|---|---|
| `respuesta`, `cifra`, `unidad`, `ejercicio`, `fuente` | la respuesta estructurada |
| `cita`, `chunk_id` | la frase literal y su fragmento |
| `herramientas` | la trayectoria, en orden, sin la llamada de salida estructurada |
| `n_llamadas`, `tokens_in`, `tokens_out`, `coste_usd`, `latencia_s` | coste |
| `cita`, `cifra`, `trayectoria`, `honestidad` | los evaluadores (`True`/`False`/vacío = no aplica) |
| `acierto` | todos los aplicables en `True` |
| `recall5`, `pos_ancla` | el retriever de esa arquitectura, con los filtros del golden |
| `limite_alcanzado`, `correcciones` | ¿bloqueó el límite? ¿saltó algún verificador? |
| `error` | excepción, si la hubo (la fila no se pierde) |

## Los evaluadores (`agente/evaluadores.py`)

- **cita_correcta** (ítems con ancla): el `chunk_id` existe, es del ticker y
  ejercicio del ítem, y los primeros 120 caracteres de `cita` (normalizados)
  están en su texto. Más estricto que el mínimo del profesor en lo del
  ejercicio: un fragmento del FY2024 no respalda una pregunta del FY2025.
- **cifra_coincide_xbrl** (ítems con `cifra_esperada`): `cuadra()` al 1 %.
  Sin cifra, o `fuente="ninguna"`, es fallo.
- **uso_la_tool_correcta** (ítems con `herramienta_esperada`): todas las
  esperadas están en la trayectoria. Acertar el número sin `get_xbrl_fact`
  suspende aquí, a propósito.
- **honestidad** (extensión): solo si el ítem trae `fuente_esperada`. Sirve
  para añadir preguntas de hueco al golden.

## Guardrails (`agente/middleware.py`, `agente/esquema.py`)

| Capa | Qué hace | Desde |
|---|---|---|
| `ToolCallLimitMiddleware(8, continue)` | bloquea la herramienta y obliga a cerrar | a1 |
| `ToolCallLimitMiddleware(read_section, 1)` | la herramienta cara, una vez | a1 |
| `ModelCallLimitMiddleware(10)` | acota el bucle verificador→modelo | a1 |
| `verificar_cifras_contra_xbrl` | cifra ∉ XBRL del ticker/año → devuelve la lista real y `jump_to="model"`, una vez | a1 |
| `verificar_cita` | chunk inexistente o cita no literal → devuelve el fragmento real, una vez | a1 |
| `RespuestaFinancieraEstricta` | `fuente="ninguna"` ⇒ sin cifra/chunk; `xbrl` ⇒ cifra; `texto` ⇒ cita+chunk; ticker ∈ corpus | a1 |
| `forzar_filtros` | rellena ticker/año en `search_filings` si faltan; `item` solo en la primera búsqueda | a2 |

Sobre `forzar_filtros` e `item`: las palabras clave que delatan la sección
aciertan 13/14 en nuestro golden y no fuerzan ninguna equivocada — pero se
escribieron mirando ese golden. El hold-out dirá cuánto de eso es general.
Es exactamente el tipo de hallazgo que el enunciado pide contar.

## Lo que falta por enchufar

- `agente/retrieval.py` (Diego): cuando `construir_herramientas` acepte
  `reescritura=`, `hibrido=`, `k=`, `agente.py` se los pasará solo; hoy detecta
  la firma antigua y llama sin argumentos. Las funciones de referencia para
  medir (`hibrido`, `reescribir`) están en `agente/recall.py` y se pueden
  sustituir por las suyas.
- Verificar en openrouter.ai/models el nombre `google/gemini-3.8-flash` y los
  precios de `PRECIOS_OPENROUTER` antes de congelar el baseline.
