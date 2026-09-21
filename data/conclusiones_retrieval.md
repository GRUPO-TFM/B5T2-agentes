# Conclusiones: retrieval mejorado (paso 4)

Fecha de la corrida canónica: **21 de septiembre de 2026**.  
Artefacto numérico: [`recall_retrieval.json`](recall_retrieval.json), regenerable con `uv run python scripts/evaluar_recall.py --reescribir`.

## Qué se midió

Se compara el retrieval del día 10 con el sistema que activa `construir_agente(mejoras=True)`. Para que el delta se atribuya **solo** a reescritura + híbrido, se mantienen fijos:

| Constante | Valor |
| --- | --- |
| Corpus | 1.749 chunks de `dataset/*.zip` (sin re-trocear) |
| Embeddings | `BAAI/bge-small-en-v1.5` + prefijo BGE en la consulta |
| Filtros | `ticker`, `fiscal_year`, `item_esperado` del golden |
| k | 5 |
| Métrica | recall@5 sobre `ancla_texto` (mismo ticker y FY) |
| Golden | `data/golden_set.jsonl`, 14 ítems con ancla (gX-007 … gX-020) |

Tres configuraciones, en este orden:

1. **Baseline** — FAISS denso + filtros. Sin LLM, sin BM25.
2. **Híbrido** — FAISS + BM25, Reciprocal Rank Fusion (`rrf_k=60`), query **original** (español).
3. **Reescritura + híbrido** — la misma query, reescrita a inglés / vocabulario 10-K, alimenta las **dos** ramas; luego RRF.

El agente no entra en esta tabla: se llama a `buscar()` directo, como haría `search_filings` si el modelo pasara los filtros correctos.

## Resultado

| Configuración | Aciertos | recall@5 | Latencia media |
| --- | --- | --- | --- |
| 1 · Denso + filtros | 7 / 14 | **50.0 %** | 0.02 s |
| 2 · Híbrido, query en español | 7 / 14 | **50.0 %** | 0.08 s |
| 3 · Reescritura + híbrido | 12 / 14 | **85.7 %** | 0.08 s retrieval + **5.05 s** LLM |

- **Delta 3 vs 1: +35.7 puntos.**
- **Delta 2 vs 1: +0.0 puntos.** El híbrido sin traducir no mueve el recall. Sí mueve *cuáles* fallan: pierde `gX-019` (split de NVIDIA) y gana `gX-020` (regiones de Meta). Es el resultado que anticipaba la sesión 2: BM25 cuenta palabras, y las preguntas están en español contra un corpus inglés.
- La reescritura es lo que sube la métrica. Sin ella, añadir BM25 es complejidad y 4× latencia de retrieval a cambio de ruido.

### Coste de la reescritura

| | |
| --- | --- |
| Modelo | `openrouter:google/gemini-3.8-flash`, `temperature=0` |
| Llamadas | 1 por búsqueda (14 en esta corrida) |
| Tokens | 1.534 entrada + 5.915 salida |
| Coste OpenRouter | **0,023 USD** el lote (~0,0017 USD / consulta) |
| Latencia extra | **5,05 s** de media (el retrieval híbrido sigue en 0,08 s) |

La salida es corta (una consulta de una línea). Los tokens de salida altos (~400–500 por llamada) son razonamiento interno de Gemini 3.8 que OpenRouter factura; no aparecen en el texto que se manda al índice.

## Qué se activó en el código

```python
from agente.interfaz import responder
responder("¿Cómo describe NVIDIA el mercado chino en FY2025?", mejoras=True)
```

`mejoras=False` (default) no llama al reescritor ni construye BM25.  
`mejoras=True` hace: query → reescritura EN/10-K → FAISS y BM25 con la **misma** consulta → mismos filtros → RRF → top-k.

Las firmas de `responder()` y `search_filings()` no cambian. El cableado es explícito: `construir_agente(mejoras=True)` pasa el flag a `construir_herramientas(mejoras=True)`. El middleware del paso 5 sigue vacío.

## Ablación por pregunta

| id | Familia | Ticker | Base | Hib. | Rew+hib. | Consulta reescrita |
| --- | --- | --- | --- | --- | --- | --- |
| gX-007 | extractiva | NVDA | no | no | **no** | `NVIDIA FY2025 10-K China competition … export controls` |
| gX-008 | extractiva | GOOGL | sí | sí | sí | `Alphabet FY2025 Risk Factors DOJ … antitrust lawsuit` |
| gX-009 | extractiva | META | sí | sí | sí | `Meta Digital Markets Act DMA gatekeeper obligations FY2025` |
| gX-010 | extractiva | AAPL | no | no | **sí** | `AAPL FY2025 risk factors natural disasters facilities suppliers` |
| gX-011 | extractiva | META | sí | sí | sí | `META FY2025 MD&A anticipate capital expenditures 2026` |
| gX-012 | extractiva | NVDA | sí | sí | sí | `NVIDIA FY2025 sensitivity analysis investment portfolio …` |
| gX-013 | comparativa | MSFT | sí | sí | sí | `Microsoft revenue increased FY2024 FY2025` |
| gX-014 | comparativa | NVDA | no | no | **sí** | `NVIDIA net income FY2025 FY2024` |
| gX-015 | comparativa | GOOGL | no | no | **sí** | `Alphabet revenues FY2024 FY2025 revenue increased` |
| gX-016 | comparativa | META | no | no | **no** | `META … net income decreased … provision for income taxes` |
| gX-017 | comparativa | AAPL | sí | sí | sí | *(el modelo devolvió la pregunta en español; el hit ya venía del baseline)* |
| gX-018 | comparativa | AMZN | no | no | **sí** | `AMZN … net cash provided by operating activities … increase` |
| gX-019 | comparativa | NVDA | sí | **no** | sí | `NVIDIA diluted net income per share … stock split …` |
| gX-020 | comparativa | META | no | **sí** | sí | `Meta revenue increased FY2024 FY2025 revenue by geographic region` |

Cinco anclas que el baseline perdía pasan a acierto con reescritura: `gX-010`, `gX-014`, `gX-015`, `gX-018`, `gX-020`. Ningún acierto del baseline se pierde en el modo 3.

## Lectura de los aciertos nuevos

- **gX-010 (Apple, desastres naturales).** En español el denso recupera otros riesgos de 1A. Con `natural disasters facilities suppliers` el ancla (`AAPL-2025-1A-0003`) pasa a ser el primer resultado.
- **gX-015 / gX-018 / gX-020.** Las comparativas de ingresos y caja: `revenue increased`, `net cash provided by operating activities`, `geographic region` alinean con el inglés del MD&A. BM25, una vez en inglés, deja de estar ciego.
- **gX-014 (NVIDIA, beneficio neto).** La consulta `net income` mete `NVDA-2025-7-0007` en quinta posición. El ancla habla de *Data Center revenue +142 %*, no del beneficio neto: el hit es real para recall@5, pero el golden ancla un párrafo de contexto, no la cifra. El número en sí debe salir de `get_xbrl_fact`.
- **gX-019.** El híbrido en español la rompe (BM25 no ve `stock split`). La reescritura recupera `ten-for-one stock split`. Ejemplo claro de por qué no se debe desplegar BM25 sin traducir.

## Lo que sigue fallando (2 / 14)

### gX-007 — China / NVIDIA, Item 1A

La reescritura pide `China competition export controls` y el índice devuelve párrafos largos de controles de exportación (`1A-0036`, `0037`, `0031`…). El ancla (`NVDA-2025-1A-0013`: *«The market in China, where our offerings are limited by export controls, is highly competitive…»*) no entra en el top-5. Es el caso que ya señalaba la sesión 2: la frase vive en un Item 1A enorme lleno de texto semánticamente cercano. Retrieval léxico y denso recuperan el *tema*, no la *oración*. Un cross-encoder o subir `k` lo atacarían; no forma parte de este paso.

### gX-016 — Meta, tipo impositivo efectivo

La pregunta pide el *porqué* de una caída de beneficio neto con el EBIT al alza. El ancla es `valuation allowance` / `effective tax rate` (`META-2025-7-0003`). El reescritor eligió `provision for income taxes` y no esos términos, pese a que el propio prompt cita `effective tax rate` como ejemplo. Los top-5 van a capex, regiones e impuestos genéricos. Fallo de **deriva de traducción**: el LLM no usó el vocabulario que el filing sí usa.

## Tests

`uv run pytest tests/` → **17 passed**, sin red ni FAISS:

1. El reescritor inyectado se usa; si lanza o devuelve vacío, se conserva la query original.
2. BM25 sobre un corpus sintético es determinista.
3. RRF combina rangos, no cosenos ni scores BM25.
4. Un chunk de otro ticker / FY / item no entra en el top-k.
5. `mejoras=False` no llama a reescritura ni a BM25.
6. Con `mejoras=True`, la query reescrita llega a las dos ramas.
7. `construir_agente(mejoras=True)` pasa el flag a las herramientas.

## Cómo reproducir

```bash
uv sync --frozen --group dev
uv run pytest tests/
uv run python scripts/evaluar_recall.py --reescribir   # escribe data/recall_retrieval.json
```

Sin `OPENROUTER_API_KEY` el script solo mide (1) vs (2) y lo declara.

## Riesgos que quedan

1. **Deriva de traducción.** `gX-016` y el eco en español de `gX-017` muestran que el reescritor no es un traductor fiel. `temperature=0` reduce ruido; no lo elimina (Gemini 3.8 razona por dentro).
2. **No determinismo entre corridas.** Una corrida previa del mismo sistema, el 20 de septiembre, dio **71,4 %** (10/14): `gX-010` y `gX-014` no entraron. Esta corrida da **85,7 %**. El informe debe citar la corrida canónica (`recall_retrieval.json`) y no un máximo puntual.
3. **Coste y latencia.** ~5 s y ~0,002 USD extra por `search_filings`. En el bucle del agente una pregunta puede lanzar varias búsquedas. Hay caché por query idéntica.
4. **Sobreajuste al golden.** Se iteró con estas 14 anclas. El hold-out del día 24 es la prueba de si la mejora generaliza. `gX-014` acierta un ancla que no es la cifra pedida: un recall alto no implica respuesta correcta si el agente lee el chunk equivocado o no usa XBRL.
5. **El system prompt sigue pidiendo inglés.** La reescritura cubre el caso en que el agente mande español o un inglés coloquial. Las dos capas no se pisan.
6. **Sin reranker.** `gX-007` no se arregla con RRF. Está fuera de alcance de este paso (tampoco hay cambio de chunking).

## Archivos de este paso

| Archivo | Papel |
| --- | --- |
| `agente/reescritura.py` | Consulta breve EN/10-K, caché, fallback, inyectable |
| `agente/retrieval.py` | Denso separable, BM25, RRF, flag `mejoras` |
| `agente/herramientas.py` / `agente/agente.py` | Cableado explícito de `mejoras=True` |
| `tests/` | 17 tests sin red |
| `scripts/evaluar_recall.py` | Ablación reproducible |
| `data/recall_retrieval.json` | Números de la corrida canónica |
| `data/conclusiones_retrieval.md` | Este texto |

No se modifican corpus, ZIP de `dataset/`, notebooks de `clase/` ni el troceado.
