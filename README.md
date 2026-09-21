# B5T2 · Agente investigador sobre informes 10-K

Práctica de **LLMs aplicados a Finanzas · MIAX**: un agente que responde preguntas sobre 10-K de la SEC, con evidencia verificable y control de calidad, coste y latencia.

El [enunciado](Practica_LLM_Agente_10K.docx) es el contrato de entrega.

El repositorio tiene **dos capas**, a propósito:

| Capa | Dónde | Qué es |
| --- | --- | --- |
| Material de aula | `clase/` | Notebooks, apuntes y helpers que se recibieron en clase |
| Entrega | `agente/`, `data/` | El pipeline que se importa, evalúa y defiende el día 24 |

No se trabaja sobre los notebooks de `clase/` para la entrega. Lo que salió de clase (herramientas, bucle, esquema) vive en `agente/`.

> **En esta rama** hay una tercera capa, `experimentos/`, que **no toca la
> entrega**: es trabajo de laboratorio sobre el retrieval. El primero es
> [**el experimento de chunking**](experimentos/chunking/README.md) — compara
> cinco estrategias de troceado y explica por qué el idioma de la pregunta
> tapaba el efecto del troceado, y por qué el índice entregado embebe
> truncado uno de cada seis fragmentos. Ese README se lee solo: conclusión,
> diseño, resultados, límites y recomendación.

## Cómo se usa

```bash
uv sync --frozen
```

`.env` en la raíz:

```dotenv
OPENROUTER_API_KEY=tu_clave_aqui
```

```bash
uv run python -c "from agente.interfaz import responder; r = responder('¿Cuál fue el revenue de NVIDIA en FY2025?'); print(r['structured_response'].cifra)"
```

```python
from agente.interfaz import responder, evaluar

r = responder("¿Cuál fue el revenue de NVIDIA en FY2025?")
tabla = evaluar("data/golden_set.jsonl", etiqueta="baseline")
```

`construir_agente(mejoras=False)` es el sistema del día 10. `mejoras=True` es el mismo código con el interruptor listo para middleware y retrieval; hoy no cambia el comportamiento. No activar mejoras hasta congelar el baseline.

## Estructura

```text
.
├── README.md
├── Practica_LLM_Agente_10K.docx      # enunciado
├── pyproject.toml / uv.lock
│
├── agente/                           # pipeline de entrega
│   ├── corpus.py                     # una sola ruta: ./corpus
│   ├── esquema.py                    # RespuestaFinanciera
│   ├── herramientas.py               # 4 tools (firmas = contrato)
│   ├── retrieval.py
│   ├── middleware.py                 # vacío hasta el paso 5
│   ├── evaluadores.py                # vacío hasta el paso 3
│   ├── agente.py                     # construir_agente(mejoras=…)
│   └── interfaz.py                   # responder() y evaluar()
│
├── data/                             # artefactos nuestros
│   └── golden_set.jsonl              # 20 preguntas propias
│
├── dataset/                          # ZIP oficiales del corpus
│   ├── corpus_miax_2026.zip
│   ├── indice_faiss.zip
│   ├── fuentes_10k_html.zip
│   └── SHA256SUMS.txt
│
├── clase/                            # material de aula (no es la entrega)
│   ├── s1/                           # sesión 1
│   └── s2/                           # sesión 2
│
├── experimentos/                     # laboratorio, no entra en la entrega
│   └── chunking/                     # 5 estrategias de troceado + resultados
│
└── corpus/                           # extraído, no se commitea
```

`corpus/` existe **una vez**, en la raíz. Lo crea `agente.corpus` a partir de `dataset/*.zip`. No hay copia dentro de `clase/`.

## Corpus

Seis compañías (NVDA, MSFT, AAPL, GOOGL, META, AMZN), FY2024 y FY2025, items 1A / 7 / 7A / 8. 135 hechos XBRL e índice FAISS (`BAAI/bge-small-en-v1.5`).

`fiscal_year` no es el año de presentación. El concepto XBRL de ingresos cambia entre compañías. Amazon no reporta `GrossProfit`. El texto está en inglés.

## Orden de trabajo

El baseline no se reconstruye después de meter middleware y límites.

| Paso | Cuándo | API | Qué |
| --- | --- | --- | --- |
| 1 | hecho | no | Empaquetar en `agente/` |
| 2 | hoy/lunes | sí | Congelar baseline (JSON crudo por pregunta) |
| 3 | lunes | no | Evaluadores sobre lo guardado |
| 4 | martes | casi no | Retrieval y recall@5 |
| 5 | martes | sí | Verificador + límites |
| 6 | miércoles | no | Tabla, PDF, clon limpio |

Guardar la salida cruda, no las métricas. Así 3 y 4 no gastan llamadas.

## Entrega

Grupos de 3. Repositorio e informe PDF el **23 de septiembre, 23:59**. El **24**, 10 preguntas ciegas sobre el clon entregado y presentación de 8 minutos (30 % repo, 70 % presentación).
