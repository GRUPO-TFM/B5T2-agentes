# B5T2 · Agente investigador sobre informes 10-K

Agente de la práctica de **LLMs aplicados a Finanzas · MIAX**. Responde preguntas sobre informes 10-K de la SEC con una respuesta estructurada, evidencia verificable y medición de acierto, retrieval, coste y latencia. El [enunciado](Practica_LLM_Agente_10K.docx) define el contrato de la práctica.

## Estado del proyecto

Hay una sola implementación del agente y siete configuraciones acumulativas: `baseline`, `a1_guardrails`, `a2_retrieval`, `a3_hibrido`, `a4_comparativas`, `a5_limites` y `a6_cifras_texto`. El alias **`final` apunta a A6** en [`agente/config.py`](agente/config.py); también es la configuración por defecto de `responder()` y `evaluar()`.

Las siete configuraciones tienen resultados guardados en los dos golden sets propios: 20 preguntas en `data/golden_set.jsonl` y 18 en `data/golden_set_dificil.jsonl`. Esta es la comparación principal, calculada desde las ejecuciones guardadas:

| Golden | Sistema | Reps | Acierto | Recall@5 | Coste/pregunta (¢) | Latencia/pregunta (s) | Herramientas/pregunta |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original | baseline | 3 | 63,3 % | 50,0 % | **1,64** | **20,33** | 3,95 |
| Original | final (A6) | 1 | **100,0 %** | **85,7 %** | 1,86 | 39,35 | **3,20** |
| Difícil | baseline | 1 | 61,1 % | 75,0 % | **1,46** | **23,34** | 5,50 |
| Difícil | final (A6) | 1 | **94,4 %** | **100,0 %** | 2,25 | 46,59 | **5,22** |

El acierto es la media de las repeticiones disponibles. Recall@5 se mide sobre las preguntas con ancla textual: 14 en el golden original y 4 en el difícil. Coste, latencia y llamadas son medias por pregunta. Las tablas completas, con **aciertos por familia** y el mejor valor de *cada* columna remarcado, están en [original](resultados/reconciliacion/baseline_vs_final_original.md) y [difícil](resultados/reconciliacion/baseline_vs_final_dificil.md). Las [comparativas de todas las arquitecturas](resultados/reconciliacion/reconciliacion.md) conservan también los peldaños intermedios.

## Instalación y uso

Se necesita Python 3.12 y `uv`. Desde la raíz del repositorio:

```bash
uv sync --frozen
```

Para hacer preguntas o ejecutar nuevas evaluaciones, crea un `.env` local con `OPENROUTER_API_KEY=tu_clave`. El fichero está excluido de Git. Una pregunta con el sistema final:

```bash
uv run python -m agente.cli pregunta "¿Cuál fue el revenue de NVIDIA en FY2025?" --arq final
```

La API de Python devuelve la respuesta estructurada, coste y latencia. `evaluar()` ejecuta y puntúa un JSONL nuevo con A6 por defecto; `etiqueta` solo nombra la carpeta de resultados, no selecciona la arquitectura:

```python
from agente.interfaz import responder, evaluar

resultado = responder("¿Cuál fue el revenue de NVIDIA en FY2025?")
print(resultado["structured_response"])

tabla = evaluar("ruta/al/golden.jsonl", etiqueta="nueva_prueba")
```

## Arquitectura

El agente usa cuatro herramientas con la misma firma en todos los presets: `list_available`, `get_xbrl_fact`, `search_filings` y `read_section`. Cambian la configuración, los verificadores y el retrieval que hay detrás de la búsqueda:

| Preset | Cambio acumulado |
| --- | --- |
| `baseline` | Agente inicial con XBRL y búsqueda densa FAISS |
| `a1_guardrails` | Límites, verificadores de cifra y cita, esquema estricto y prompt de honestidad |
| `a2_retrieval` | Filtros de metadatos y reescritura de consultas |
| `a3_hibrido` | Retrieval híbrido BM25 + denso |
| `a4_comparativas` | Procedimiento explícito para comparativas |
| `a5_limites` | Límites de llamadas por herramienta |
| `a6_cifras_texto` | Contrato y verificación de cifras obtenidas del texto; preset `final` |

El corpus cubre NVDA, MSFT, AAPL, GOOGL, META y AMZN en FY2024 y FY2025, con texto de los items 1A, 7, 7A y 8, hechos XBRL e índice FAISS. [`agente/corpus.py`](agente/corpus.py) extrae y verifica los paquetes de `dataset/` en una única carpeta `corpus/`, excluida de Git.

## Evaluación reproducible

Cada pregunta ejecutada se guarda como JSON crudo con la trayectoria completa. La puntuación y las tablas se derivan de ese registro, de modo que se pueden recalcular sin repetir la pregunta al agente. El recall puede necesitar una llamada al modelo si falta una consulta reescrita en la caché.

```bash
# Estado de lo ejecutado y estimación de lo que falta; no hace llamadas
uv run python -m agente.lotes correr --plan

# Recalcula las métricas de las siete arquitecturas en ambos golden sets
# y regenera las tablas baseline frente a final en Markdown y CSV
uv run python -m agente.lotes reconciliar

# Pruebas locales
uv run --with pytest python -m pytest -q
```

`agente.lotes correr` ejecuta solo las preguntas que faltan; pide confirmación antes de hacer llamadas. El [notebook de evaluación](notebooks/evaluacion.ipynb) permite inspeccionar preguntas, trazas, retrieval y comparativas. El procedimiento y los ficheros de salida están descritos en [`docs/evaluacion.md`](docs/evaluacion.md).

## Organización

| Ruta | Contenido |
| --- | --- |
| `agente/` | Agente, herramientas, retrieval, evaluadores, métricas y comandos |
| `data/` | Golden original y golden difícil |
| `resultados/` | Ejecuciones y tablas del golden original; `reconciliacion/` reúne las comparativas de ambos |
| `resultados_dificil/` | Ejecuciones y tablas del golden difícil |
| `notebooks/evaluacion.ipynb` | Exploración y lectura de los resultados |
| `tests/` | Pruebas del contrato, evaluadores, retrieval y harness |
| `dataset/` | Paquetes originales del corpus y sus hashes |
| `clase/` | Material de aula, separado del pipeline de entrega |

Los resultados guardados forman parte del repositorio; `.env` y el corpus extraído permanecen locales.
