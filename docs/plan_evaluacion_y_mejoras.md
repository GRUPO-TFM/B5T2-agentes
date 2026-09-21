# B5T2 · Plan de evaluación y mejoras

*Documento de diseño para el equipo (Javi, Diego, Javier). 21-sep-2026. Repo `GRUPO-TFM/B5T2-agentes`, commit `14484a9`.*

---

## 0. La tarea, en cinco líneas (§4 del enunciado)

1. **Cinturón de herramientas**: las cuatro `@tool` con firmas intocables. El docstring es lo único que ve el modelo.
2. **Agente y guardrails**: salida estructurada `RespuestaFinanciera` obligatoria; **límite de llamadas** por invocación; **middleware propio** que extraiga las cifras de la respuesta, las contraste con XBRL y devuelva el desajuste al modelo.
3. **Golden set**: 20 preguntas, ≥6 comparativas, extractivas ancladas a **una frase literal**, no a un `chunk_id`. *Hecho y verificado.*
4. **Mejora medida del retrieval**: partiendo del denso, aplicar y medir **al menos** filtro por metadatos, híbrido BM25+denso y reescritura de consulta. **recall@k después de cada arreglo, contra el ancla.**
5. **Evaluación automática**: tres evaluadores (cita, cifra, trayectoria) y `responder(pregunta)` / `evaluar(ruta_jsonl)` ejecutables sobre un clon limpio.

§5 exige además: tabla baseline vs. final con **aciertos por familia, recall@k, coste medio, latencia media y llamadas/pregunta**, mejor valor remarcado; ficheros de resultados regenerables; baseline **etiquetado y guardado antes de mejorar**; ninguna clave en el repo. Presentación: qué mejoró, cuánto, a qué coste; hold-out con delta; cómo enruta; **qué se probó que no funcionó**.

---

## 1. Corrección de partida: "recall" no mide al agente

Hay dos preguntas distintas y dos tablas distintas. Mezclarlas es el error más fácil de cometer.

| | ¿Qué mide? | ¿Quién se ejecuta? | ¿Coste API? |
|---|---|---|---|
| **recall@5** | Si la frase-ancla aparece en los 5 fragmentos que devuelve **el buscador** para la pregunta | Solo `search_filings` (o su función interna), con los filtros del golden set | Cero (salvo la reescritura: 1 llamada barata, cacheable) |
| **Aciertos del agente** | Si la respuesta final tiene cita real, cifra correcta y trayectoria correcta | El agente entero | Sí, una invocación completa por pregunta |

El recall solo tiene sentido en las **14 preguntas con ancla** (6 extractivas + 8 comparativas). Las 6 numéricas no tienen recall: su verdad está en XBRL, no en un texto.

Consecuencia: el éxito del agente no es "el recall". Es la **tasa de acierto por evaluador y por familia**. El recall es la métrica del retriever y va en su propia tabla, que además es gratis de producir.

### 1.1 Cómo se calcula el recall y qué es el ancla (punto 11)

- **Ancla** = una frase literal del informe, de una sola frase, que responde a la pregunta. Se guarda con `ancla_texto`, `ancla_inicio` y `ancla_fin` (posición en caracteres dentro de la sección). Se elige frase y no `chunk_id` porque **si se re-trocea el corpus todos los `chunk_id` cambian** y la métrica quedaría sin referencia; la frase sobrevive a cualquier troceado.
- **acierta(item, recuperados)** — primitiva del profesor en `miax_s2.py`: devuelve `True` si **algún** fragmento recuperado (a) es del **mismo ticker y ejercicio**, y (b) contiene el ancla (por tramo de caracteres si el fragmento trae `inicio_car`/`fin_car`, o por texto normalizado si no). La condición (a) no es un detalle: los 10-K repiten factores de riesgo literalmente de un año a otro, y sin ella recuperar el FY2024 puntuaría como acierto del FY2025.
- **recall@k** = nº de preguntas con ancla en las que `acierta` es `True` con los k primeros / nº de preguntas con ancla. Con 14 preguntas cada una vale **7,1 puntos**. Es una tasa de acierto binaria, no un recall en sentido estadístico estricto (no hay varios "relevantes" por pregunta; hay uno).
- **posicion_del_ancla** — complemento: en qué puesto aparece el primer fragmento que la contiene. Un ancla en el puesto 6 y otra en el 900 fallan las dos el recall@5, pero no son el mismo problema. Esta columna es la que dice **qué** arreglar.

**Hay que usar `miax_s2.acierta` y `recall_en_k` tal cual**, no escribir una métrica propia: el profesor lo dice explícitamente para que las tablas de los grupos sean comparables.

---

## 2. Arquitectura de resultados: crudo primero, métricas después

Principio: **una invocación del agente se ejecuta una vez y se guarda entera**. Todo lo demás (evaluadores, tablas, gráficos) se deriva de lo guardado, sin volver a llamar a la API. Así:

- los evaluadores se pueden corregir y re-aplicar sin gastar,
- se puede añadir una métrica nueva a posteriori,
- y nada se sobreescribe: cada arquitectura y cada repetición tiene su carpeta.

### 2.1 Estructura de carpetas

```
resultados/
├── retrieval/                          # tabla del §4.4 — sin agente
│   ├── recall_por_config.csv           # una fila por configuración: recall@5, coste
│   ├── posiciones.csv                  # id × config → puesto del ancla (diagnóstico)
│   └── reescrituras.json               # caché de la reescritura LLM por id
│
├── agente/
│   ├── baseline/
│   │   ├── config.json                 # flags, modelo, commit, fecha, k, límites
│   │   ├── rep1/
│   │   │   ├── crudo/gX-001.json       # mensajes completos + structured_response
│   │   │   ├── crudo/gX-002.json       #   + tokens + latencia + coste
│   │   │   └── tabla.csv               # una fila por pregunta, ya evaluada
│   │   ├── rep2/  ...
│   │   ├── rep3/  ...
│   │   └── resumen.csv                 # una fila por rep + media ± rango
│   ├── a1_guardrails/     (misma estructura)
│   ├── a2_retrieval/      (misma estructura)
│   └── a3_comparativas/   (misma estructura)
│
├── comparativa.csv                     # UNA fila por arquitectura (media de reps)
├── comparativa_por_familia.csv         # arquitectura × familia
└── comparativa.md                      # la tabla del informe, mejor valor en negrita
```

Todo `resultados/` se commitea (son ficheros pequeños: ~20 JSON de 30 KB por rep). El enunciado pide que los resultados sean **regenerables**, no que no estén.

### 2.2 Las funciones

Se separa lo que hoy hace `evaluar()` en tres pasos independientes:

```python
ejecutar(ruta_jsonl, arquitectura, rep)    # API. Escribe crudo/<id>.json. Idempotente: si existe, salta.
puntuar(arquitectura, rep)                 # Sin API. Lee crudo/, aplica los 3 evaluadores → tabla.csv
comparar()                                 # Sin API. Lee todas las tabla.csv → comparativa.csv/.md
medir_recall(configs)                      # Sin agente. Retriever contra las 14 anclas → resultados/retrieval/
```

`evaluar(ruta_jsonl)` del §6 se mantiene como fachada: `ejecutar` + `puntuar` sobre la arquitectura por defecto (la final), y devuelve el DataFrame. Es lo que corre el día 24 sobre `holdout.jsonl`.

**Idempotencia**: `ejecutar` no repite una pregunta cuyo `crudo/<id>.json` ya existe. Si una ejecución se corta a la pregunta 13, se relanza y sigue en la 14. Eso también permite reintentar solo las que dieron excepción.

**Serialización del crudo**: `langchain_core.messages.messages_to_dict(r["messages"])` + `structured_response.model_dump()` + tokens (entrada, salida) + latencia + coste + `config` de la arquitectura. Es lo que el evaluador de trayectoria y `pretty_trace` necesitan para funcionar **sobre lo guardado**.

### 2.3 La arquitectura como configuración, no como rama

`construir_agente(mejoras: bool)` no basta para una escalera de cuatro peldaños. Se sustituye por un preset:

```python
ARQUITECTURAS = {
  "baseline":        dict(limites=False, verificador=False, filtros="modelo",  reescritura=False, hibrido=False, comparativas=False),
  "a1_guardrails":   dict(limites=True,  verificador=True,  filtros="modelo",  reescritura=False, hibrido=False, comparativas=False),
  "a2_retrieval":    dict(limites=True,  verificador=True,  filtros="forzado", reescritura=True,  hibrido=False, comparativas=False),
  "a3_comparativas": dict(limites=True,  verificador=True,  filtros="forzado", reescritura=True,  hibrido=True,  comparativas=True),
}
```

Cada peldaño **añade** al anterior y no quita nada: así la diferencia entre dos filas consecutivas de la tabla es atribuible a una sola cosa. El mismo código, con el mismo commit, genera las cuatro filas. Eso es lo que hace la tabla defendible.

Lo que se prueba y **no funciona** se guarda igual, con su carpeta (`x_hibrido_sin_reescritura/`, por ejemplo) y va a la diapositiva de "lo que probamos".

### 2.4 Repeticiones y varianza

El modelo no es determinista aunque `temperature=0`: el orden de las tool calls cambia, OpenRouter puede enrutar a réplicas distintas, y una sola llamada que se desvía cambia la trayectoria entera.

Propuesta: **3 repeticiones del baseline primero**. Si la dispersión entre repeticiones es ≤1 pregunta por evaluador, las arquitecturas siguientes se corren ×1 y se reporta la media del baseline. Si es mayor, todas ×3. Se reporta siempre **media y rango** (mín–máx), no solo la media: un salto de 2 preguntas con un rango de ±2 no es una mejora, y eso también hay que poder decirlo.

Coste estimado con `gemini-3.8-flash`: ~1–3 ¢/pregunta → 20 × 3 reps × 4 arquitecturas ≈ **2–7 $** y **~1 h de reloj**. Asumible.

**Detalle obligatorio**: el `thread_id` debe incluir la repetición (`f"{arq}-rep{n}-{id}"`). El `InMemorySaver` vive en el `lru_cache` de `construir_agente`; con el mismo `thread_id`, la repetición 2 vería la conversación de la repetición 1.

### 2.5 Lo que se ve por pregunta (punto 12)

| Columna | De dónde sale | Para qué |
|---|---|---|
| `id`, `familia`, `ticker` | golden set | agrupar |
| `respuesta` | `structured_response.respuesta` | leer |
| `cifra`, `unidad`, `ejercicio` | `structured_response` | evaluador de cifra |
| `fuente` | `structured_response.fuente` | ¿dijo "ninguna" cuando tocaba? |
| **`cita`** | `structured_response.cita` | **la frase literal de la que lo sacó** — ya es campo obligatorio del esquema |
| `chunk_id` | `structured_response.chunk_id` | verificar la cita |
| **`herramientas`** | trayectoria, en orden, sin `RespuestaFinanciera` | **qué camino siguió** |
| `n_llamadas` | `len(herramientas)` | coste de razonamiento |
| `tokens_in`, `tokens_out` | `usage_metadata` de cada mensaje | coste |
| **`coste_usd`** | tokens × precio | **columna de la tabla, no nota al pie** |
| `latencia_s` | cronómetro | columna de la tabla |
| `cita_ok`, `cifra_ok`, `trayectoria_ok` | los 3 evaluadores (`True/False/None`) | aciertos |
| `acierto` | todos los evaluadores aplicables `True` | la cifra-resumen por pregunta |
| `recall5`, `pos_ancla` | `medir_recall` para la config de retrieval de esa arquitectura | retriever |
| `limite_alcanzado` | ¿se bloqueó alguna herramienta? | detectar bucles |
| `error` | excepción, si la hubo | no perder filas |

Y por arquitectura (la fila de `comparativa.csv`, el formato que `resumir()` del profesor ya fija): `cita`, `cifra`, `trayectoria` (tasas), **acierto por familia** (numérica / extractiva / comparativa), `recall@5`, `coste medio (¢)`, `latencia media (s)`, `llamadas/pregunta`, `% fuente=ninguna cuando tocaba`.

---

## 3. Mejoras: qué atacar primero y por qué

### 3.1 Criterio

Tres preguntas para cada idea: (1) ¿a cuántas de las 20 preguntas afecta?, (2) ¿el enunciado la exige o la penaliza?, (3) ¿qué cuesta implementarla y medirla? Y una regla del propio profesor, demostrada en clase: **el orden en que se prueban los arreglos cambia la conclusión**. El híbrido BM25 medido *antes* de arreglar el idioma no aporta nada; medido *después*, sí.

### 3.2 Lo que hay que decir sobre la mitad de las pistas del equipo

Las pistas **1, 2, 3, 4, 9 y 15** (limpiar texto, troceado, paréntesis, tablas partidas, formato, parser) atacan todas la misma capa: **cómo se convierte el HTML en fragmentos**. Son intuiciones correctas para un RAG genérico. Para **esta** práctica su rendimiento es bajo, por tres razones que conviene tener claras:

1. **Las cifras no salen del texto.** El diseño de la práctica obliga a que todo número venga de `get_xbrl_fact`, y el evaluador de trayectoria **penaliza** leer un número de la prosa aunque sea correcto. Una tabla del Item 8 mejor troceada mejora un camino que el evaluador castiga. Los paréntesis-como-negativo y las notas al pie viven en ese camino.
2. **Las anclas del golden set ya están en los fragmentos.** Verificado: las 14 anclas aparecen literalmente en su `chunk_id` esperado. El fallo de retrieval, cuando lo hay, es de **ranking** (el fragmento existe, no queda entre los 5 primeros) o de **idioma**, no de troceado. La pregunta que sigue fallando tras los tres arreglos del profesor es la de China: la frase está en un Item 1A de 19.000 tokens lleno de párrafos sobre controles de exportación que se le parecen más.
3. **Cuesta lo que más.** Re-trocear obliga a re-embeber (gratis pero lento), re-indexar, y descartar `chunks.jsonl` oficial. El parser del profesor (`data_source/chunks.py`) no se reparte; habría que escribir uno desde `fuentes_10k_html.zip`.

Está permitido (el enunciado lo contempla, por eso las anclas son frases) y puede ser una buena diapositiva de **"lo probamos y no movió la aguja"**. Pero no es por donde se empieza.

La pista **5** (filtrar por fecha de publicación): **no**. El enunciado avisa de que `fiscal_year` no es el año de presentación; el filtro es por `fiscal_year`, y ya existe.

La pista **8**, la parte de traducir el corpus: **no**. `cita` tiene que ser texto literal del informe y `cita_correcta` la comprueba contra el fragmento; un corpus traducido rompe el evaluador. La otra mitad de la pista (cambiar de embedding) va en el nivel 3.

### 3.3 Orden propuesto

**Nivel 1 — obligatorio, barato, mueve la tabla del agente**

| # | Mejora | Fallos que cierra | Preguntas afectadas | Coste |
|---|---|---|---|---|
| A1.1 | `ToolCallLimitMiddleware(run_limit=8, exit_behavior="continue")` + `ModelCallLimitMiddleware(run_limit=10)` + límite específico `read_section ≤ 1` | bucle infinito; coste descontrolado | todas las que hoy agotan vueltas (2 de los 3 ejemplos guardados) | 3 líneas |
| A1.2 | Middleware `verificar_cifras_contra_xbrl` (after_model, una corrección máx., `jump_to="model"`) | "se inventó la cifra" | 14 con cifra | el ejercicio central de la S2 |
| A1.3 | Validadores Pydantic en `RespuestaFinanciera` (ver §4) | respuestas incoherentes (`fuente="ninguna"` con cifra, etc.) | todas | 15 líneas |
| A1.4 | Prompt: procedimiento explícito y regla de honestidad ("si te bloquean las herramientas, responde `fuente='ninguna'`") | inventar; no parar | todas | prompt |

**Nivel 2 — obligatorio medir, mueve el recall**

| # | Mejora | Cómo se mide |
|---|---|---|
| A2.1 | **Filtros por metadatos forzados**: pre-router determinista (regex sobre nombres/tickers/años de la pregunta) que rellena `ticker` y `fiscal_year` cuando el modelo no lo hace; `item` inferido por palabras clave (riesgo→1A, divisas/tipos→7A) | recall@5 y `% de search_filings con ticker` |
| A2.2 | **Reescritura de consulta a inglés** con vocabulario del informe (1 llamada barata, cacheada por pregunta) | recall@5; es el arreglo que más sube según la S2 |
| A2.3 | Barrido de **k** ∈ {3, 5, 8, 10} offline | recall@k vs. tokens por búsqueda |

**Nivel 3 — medir, rendimiento incierto, buenos candidatos a "no funcionó"**

| # | Mejora | Nota |
|---|---|---|
| A3.1 | **Híbrido BM25 + denso (RRF)**, medido **después** de A2.2 | antes de la reescritura no aporta (lección de la S2); después puede aportar en tickers/cifras |
| A3.2 | **Procedimiento para comparativas** en el prompt: dos `get_xbrl_fact` con el mismo concepto, comprobar que el concepto existe en ambos años, restar, una búsqueda de texto en el Item 7 del año reciente para la explicación | 8 de 20 preguntas son comparativas: **40 % del golden set** |
| A3.3 | **Robustez a splits**: para conceptos por acción (`EarningsPerShare*`, acciones en circulación, dividendo/acción), buscar "stock split" en el Item 8 del ejercicio reciente antes de comparar; ajustar y decirlo | la gX-019 y cualquier ciega parecida; ojo con el verificador (§4) |
| A3.4 | Embedding multilingüe (`bge-m3` o `multilingual-e5-small`), re-embeber los 1.749 fragmentos | quita la dependencia de la reescritura; coste: modelo ~5× mayor, re-indexar; medir si supera a A2.2 |

**Fuera de alcance salvo que sobre tiempo**: re-troceado consciente de tablas (§3.2), parser propio desde HTML.

### 3.4 Los cuatro peldaños de la tabla

| Arquitectura | Qué añade sobre la anterior |
|---|---|
| **baseline** | El agente del día 10, tal cual. Congelado antes de tocar nada. |
| **a1_guardrails** | Límites + verificador XBRL + validadores + prompt honesto |
| **a2_retrieval** | + filtros forzados + reescritura a inglés |
| **a3_comparativas** | + híbrido + procedimiento comparativas + splits |

Cada fila responde a una pregunta distinta de la defensa: A1 "¿es honesto y para?", A2 "¿encuentra?", A3 "¿compara bien?". Si A3 empeora coste sin subir aciertos, se dice y se deja el sistema final en A2 — esa decisión también puntúa.

---

## 4. Guardrails (punto 13)

En capas, de fuera hacia dentro:

1. **Esquema** (ya existe): `RespuestaFinanciera` con tipos estrictos y `Literal` en `fuente`. Es el guardrail que hace la evaluación automática.
2. **Validadores de coherencia** (añadir, `model_validator`):
   - `fuente == "ninguna"` ⇒ `cifra is None` y `chunk_id is None`.
   - `fuente in ("xbrl","ambas")` ⇒ `cifra is not None`.
   - `fuente in ("texto","ambas")` ⇒ `cita` y `chunk_id` no vacíos.
   - `ticker` ∈ {los 6}; `ejercicio` ∈ {2024, 2025}.
   - Si falla, el error vuelve al modelo como corrección (una vez), igual que el verificador.
3. **Límites**: `ToolCallLimitMiddleware` (global 8; `read_section` 1) y `ModelCallLimitMiddleware` (10). Con `exit_behavior="continue"` el modelo recibe un aviso de herramienta bloqueada y **tiene que cerrar**; el prompt le dice cómo: `fuente="ninguna"` y explicar qué buscó.
4. **Verificador de cifras** (obligatorio): cifra afirmada vs. XBRL del ticker/ejercicio, tolerancia 1 %, una corrección máxima, `jump_to="model"`.
5. **Verificador de cita** (propio, simétrico al anterior): si `chunk_id` no existe en el corpus o `cita` no está en el texto de ese fragmento (normalizado, primeros ~120 caracteres), devolver el desajuste al modelo una vez. Cierra las citas inventadas **antes** de que las cace el evaluador.
6. **Guardas dentro de las herramientas**: normalizar `ticker` a mayúsculas, `fiscal_year` a `int`, y en `get_xbrl_fact` devolver los conceptos disponibles cuando el pedido no existe (ya está). Es lo que evita que el modelo "rellene": le da la lista real para elegir.

**Interacción a vigilar (splits)**: si el agente responde correctamente "BPA FY2024 ajustado = 1,19", el verificador no encontrará ningún hecho XBRL que cuadre con 1,19 (el XBRL dice 11,93) y lo rebotará. Regla: `cifra` lleva **la magnitud del ejercicio preguntado tal y como está en XBRL**; los ajustes van en `respuesta`. O bien el verificador tolera múltiplos enteros cuando el concepto es por acción y hay un split documentado. Hay que decidirlo antes de A3.3.

---

## 5. Los tests (punto 16)

Tres niveles, y solo el tercero gasta API.

**Nivel 1 — unitarios, sin API, corren en segundos (`pytest`)**
- Herramientas: `get_xbrl_fact("NVDA", 2025, "Revenues")` devuelve 130.497 M; `get_xbrl_fact("AMZN", 2025, "GrossProfit")` devuelve el aviso de hueco con la lista de conceptos; `search_filings` con filtro devuelve solo ese ticker/año; `list_available` lista 6 × 2 × 4.
- Evaluadores con resultados sintéticos: `chunk_id` inventado → `cita=False`; cifra redondeada al 0,5 % → `cifra=True`; cifra al 20 % → `False`; numérica sin `get_xbrl_fact` en la trayectoria → `trayectoria=False`; `RespuestaFinanciera` en la trayectoria **no** cuenta como herramienta.
- Validadores del esquema: `fuente="ninguna"` con `cifra=5` → `ValidationError`.
- Verificador de cifras con un estado falso: cifra que no cuadra → devuelve mensaje y `jump_to`; segunda vez → `None`.
- Golden set: pasa el validador del profesor; 20 ítems; ≥6 comparativas; las 14 cifras cuadran con XBRL; las 14 anclas están en su chunk (esto ya está hecho a mano; se deja como test).

**Nivel 2 — retrieval, sin API salvo la caché de reescrituras**
- `medir_recall` sobre las 14 anclas para cada configuración. Es la tabla del §4.4 y a la vez un test de regresión: si un cambio baja el recall, se ve.

**Nivel 3 — extremo a extremo, con API**
- `ejecutar` + `puntuar` sobre el golden set, por arquitectura y repetición. Es la evaluación, no un test.
- **Ensayo del día 24**: clon limpio en otra carpeta, `uv sync --frozen`, `.env`, `uv run python -c "from agente.interfaz import evaluar; print(evaluar('data/golden_set.jsonl').head())"`. Cinco minutos. Antes del 23.

---

## 6. Robustez a comparativas y a splits (puntos 10 y 14)

Una comparativa necesita **dos cifras del mismo concepto en dos ejercicios, restar, y una frase de la prosa que explique el cambio**. Un RAG plano no puede decidir que hacen falta dos búsquedas; el agente sí, y eso es lo único que lo justifica frente al RAG plano (es la tesis de la S2). Lo que hay que asegurar:

- **Mismo concepto en ambos años.** Verificado: las 8 comparativas del golden set lo cumplen. Pero Alphabet etiqueta `Revenues` y `RevenueFromContract…` en FY2024 y solo `Revenues` en FY2025: el agente tiene que comprobar disponibilidad en cada año, no asumirla.
- **Explicación en el año reciente**: la variación FY2024→FY2025 se explica en el MD&A (Item 7) de FY2025. Filtro `fiscal_year=2025, item="7"`.
- **Dirección del cambio**: gX-016 (Meta) baja el beneficio pese a subir el operativo. El prompt debe pedir signo y explicación, no solo magnitud.
- **Splits**: NVDA 10:1 en junio de 2024. El XBRL del FY2024 lleva el BPA pre-split (11,93) y el del FY2025 el post-split (2,94). Comparar en bruto da un −75 % que es falso. Regla para conceptos **por acción**: antes de comparar, `search_filings("stock split", ticker, fy_reciente, item="8")`; si aparece, ajustar y **decirlo en la respuesta**. En el corpus solo NVDA tiene split en la ventana, pero la regla es general y no memoriza el golden set.

---

## 7. Dudas que hay que cerrar antes de escribir código

1. **Repeticiones**: ¿3 en baseline y luego decidir (mi propuesta), o 3 en todo desde el principio?
2. **Rama**: propongo una sola, `mejoras`, y que cada arquitectura sea un **preset de configuración**, no un estado de git. Se etiqueta el commit con el que se congela el baseline (`git tag baseline-congelado`). ¿De acuerdo, o prefiere Diego una rama por mejora?
3. **Propiedad del código**: `interfaz.py` y `agente.py` son de Diego. Las tres correcciones detectadas y el desdoble `ejecutar/puntuar/comparar` le tocan a él o los hago yo en la rama y él revisa el PR. ¿Cómo lo repartimos?
4. **Modelo fijo**: `gemini-3.8-flash` en las cuatro arquitecturas. Cambiar de modelo entre filas confunde la comparación. ¿Confirmado? (Y comprobar el nombre y los precios en openrouter.ai/models antes de congelar: los del código son del 2-sep.)
5. **Alcance de A3.4** (embedding multilingüe): ¿se intenta si hay tiempo o se descarta ya para no dispersar?
