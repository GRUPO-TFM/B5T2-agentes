# B5T2 · Agente investigador sobre informes 10-K

Práctica de **LLMs aplicados a Finanzas · MIAX**: un agente que responde preguntas sobre 10-K de la SEC, con evidencia verificable y control de calidad, coste y latencia.

**Esta rama es el paso 4: retrieval mejorado.** El corpus está en inglés y las preguntas en español. El baseline busca solo con FAISS (`BAAI/bge-small-en-v1.5`). Aquí se añade reescritura de la consulta a inglés / vocabulario 10-K y un híbrido BM25 + denso fusionado con Reciprocal Rank Fusion. No hay cambio de chunking.

| Dónde | Qué |
| --- | --- |
| [`data/conclusiones_retrieval.md`](data/conclusiones_retrieval.md) | Lectura del experimento: ablación, aciertos, fallos, coste |
| [`data/recall_retrieval.json`](data/recall_retrieval.json) | Números de la corrida canónica (regenerable) |
| [`scripts/evaluar_recall.py`](scripts/evaluar_recall.py) | Cómo repetir baseline vs híbrido vs reescritura+híbrido |
| [`tests/`](tests/) | 17 tests sin red ni FAISS |

Resultado (14 anclas, k=5, mismos filtros y embedding): recall@5 **50 % → 85,7 %**. El híbrido sin traducir no mueve la métrica; la reescritura sí. Detalle y riesgos en las conclusiones.

El [enunciado](Practica_LLM_Agente_10K.docx) es el contrato de entrega.

El repositorio tiene **dos capas**, a propósito:

| Capa | Dónde | Qué es |
| --- | --- | --- |
| Material de aula | `clase/` | Notebooks, apuntes y helpers que se recibieron en clase |
| Entrega | `agente/`, `data/` | El pipeline que se importa, evalúa y defiende el día 24 |

No se trabaja sobre los notebooks de `clase/` para la entrega. Lo que salió de clase (herramientas, bucle, esquema) vive en `agente/`.

## Cómo se usa

```bash
git clone -b diegomuGit/traduccion-retrieval-mejorado https://github.com/GRUPO-TFM/B5T2-agentes.git
cd B5T2-agentes
uv sync --frozen --group dev
cp .env.example .env   # y pon tu OPENROUTER_API_KEY
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

`construir_agente(mejoras=False)` (y `responder(..., mejoras=False)`) es el sistema del día 10: retrieval denso FAISS, sin reescritura ni BM25.

`construir_agente(mejoras=True)` activa de verdad el retrieval mejorado: reescritura de la consulta a inglés / vocabulario 10-K, búsqueda densa + BM25 con los mismos filtros, fusión por RRF. El middleware del paso 5 sigue vacío.

```python
from agente.interfaz import responder

responder("¿Cómo describe NVIDIA el mercado chino en FY2025?", mejoras=True)
```

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
│   ├── retrieval.py                  # denso; híbrido BM25+RRF si mejoras=True
│   ├── reescritura.py                # consulta breve en inglés para 10-K
│   ├── middleware.py                 # vacío hasta el paso 5
│   ├── evaluadores.py                # vacío hasta el paso 3
│   ├── agente.py                     # construir_agente(mejoras=…)
│   └── interfaz.py                   # responder() y evaluar()
│
├── data/                             # artefactos nuestros
│   ├── golden_set.jsonl              # 20 preguntas propias
│   ├── recall_retrieval.json         # ablación recall@5 (regenerable)
│   └── conclusiones_retrieval.md     # lectura del experimento
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
├── tests/                            # pytest, sin red ni FAISS
├── scripts/evaluar_recall.py         # recall@5 baseline vs mejorado
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
| 4 | hecho | casi no | Retrieval y recall@5 (85.7 % vs 50 %) |
| 5 | martes | sí | Verificador + límites |
| 6 | miércoles | no | Tabla, PDF, clon limpio |

Guardar la salida cruda, no las métricas. Así 3 y 4 no gastan llamadas.

## Tests y recall@5 del retrieval

```bash
uv sync --frozen --group dev
uv run pytest tests/                  # 17 tests, sin red ni FAISS
uv run python scripts/evaluar_recall.py --reescribir
```

Corpus, embedding, filtros y k fijos. El delta se atribuye a reescritura + BM25/RRF. Corrida canónica en [`data/recall_retrieval.json`](data/recall_retrieval.json); lectura en [`data/conclusiones_retrieval.md`](data/conclusiones_retrieval.md).

| Configuración | recall@5 | Coste extra |
| --- | --- | --- |
| Baseline (denso + filtros) | 50.0 % (7/14) | — |
| Híbrido, query en español | 50.0 % (7/14) | +0,06 s, 0 USD |
| Reescritura + híbrido | **85.7 % (12/14)** | +5,05 s y ~0,002 USD / búsqueda |

El híbrido sin traducir no mueve el recall (sí cambia *qué* preguntas fallan). La reescritura es lo que sube la métrica. Siguen fuera `gX-007` (China/export controls, hace falta reranker) y `gX-016` (deriva: el LLM no dijo *effective tax rate*). `temperature=0` no hace la reescritura del todo determinista: una corrida anterior quedó en 71,4 %.

## Entrega

Grupos de 3. Repositorio e informe PDF el **23 de septiembre, 23:59**. El **24**, 10 preguntas ciegas sobre el clon entregado y presentación de 8 minutos (30 % repo, 70 % presentación).
