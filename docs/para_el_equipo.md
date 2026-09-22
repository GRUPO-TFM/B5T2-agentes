# Rama `mejoras` — qué hay, por qué, y qué falta

*Javi · 22 de septiembre de 2026 · para Diego y Javier*

Este documento explica lo que he hecho en la rama `mejoras` para que podáis
leerla sin tener que reconstruirla desde los commits. Va de menos a más: primero
el resultado, luego cómo se mide, luego qué cambia en cada arquitectura y por
qué, después los cambios a vuestros ficheros, y al final lo que queda abierto.

Todo lo que digo aquí está medido y guardado en `resultados/`; ninguna cifra
sale de memoria.

---

## 1. El resultado en una tabla

Cuatro arquitecturas acumulativas, cada una medida tres veces sobre las 20
preguntas del golden set (`data/golden_set.jsonl`), mismo modelo
(`google/gemini-3.8-flash` vía OpenRouter):

| arquitectura | acierto | numéricas | extractivas | comparativas | cita | cifra | trayectoria | recall@5 | coste | latencia |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 61,7 % | 100 % | 94,4 % | 8,3 % | 52 % | 50 % | 83 % | 50 % | 1,62 ¢ | 20 s |
| a1_guardrails | 75,0 % | 100 % | 100 % | 37,5 % | 64 % | 100 % | 75 % | 50 % | 1,41 ¢ | 17 s |
| a2_retrieval | 75,0 % | 100 % | 100 % | 37,5 % | 64 % | 100 % | 77 % | 64 % | 1,44 ¢ | 29 s |
| **a4_comparativas** | **96,7 %** | 100 % | 94,4 % | **95,8 %** | **95 %** | 98 % | **100 %** | **86 %** | 1,52 ¢ | 49 s |

`a3_hibrido` (A2 + BM25, sin el prompt de comparativas) está definida y
predicha pero aún sin ejecutar; ver §7.

**La lectura corta.** El agujero del baseline eran las comparativas (8 de 20
preguntas, 40 % del golden set) y tenía **dos causas independientes**: el
agente ponía la *variación* en `cifra` en vez del valor del ejercicio (lo arregla
A1), y no buscaba texto, así que no podía citar (lo arregla A4). A2 y A3 atacan
una tercera causa —el retrieval— que en este golden set no existía: el buscador
mejora 36 puntos de recall y el agente no cambia ni una respuesta.

---

## 2. Cómo se mide

### La idea: crudo primero

Cada pregunta que el agente responde se guarda **entera** — la conversación
completa con todas las llamadas a herramientas y sus respuestas — en
`resultados/agente/<arquitectura>/rep<n>/crudo/<id>.json`. Los veredictos
(cita bien / cifra bien / trayectoria bien) **no se guardan: se calculan al
leer**. Esto tiene una consecuencia práctica que ya nos ha ahorrado dinero dos
veces: cuando encuentro un bug en un evaluador o en un contador, lo corrijo y
vuelvo a puntuar todo en segundos, sin repetir una sola llamada a la API.

### Tres funciones, una gasta API

| función | qué hace | API |
|---|---|---|
| `ejecutar(golden, arq, rep)` | corre el agente y guarda un JSON por pregunta; **idempotente** (si el JSON existe, salta) | sí |
| `puntuar(arq, rep)` | lee los JSON, aplica los evaluadores, escribe `tabla.csv` | no |
| `comparar()` | una fila por arquitectura, media de repeticiones, escribe `comparativa.md` | no |

Todo está en `agente/interfaz.py`; el notebook `notebooks/evaluacion.ipynb` solo
las llama y pinta. El día 24 el profesor corre `evaluar("holdout.jsonl")`, que es
una fachada sobre las tres.

### Los tres evaluadores del enunciado, y qué cuenta como acierto

- **`cita`**: el `chunk_id` citado existe, es del ticker y ejercicio correctos, y
  la `cita` es texto **literal** del fragmento.
- **`cifra`**: la `cifra` coincide con el hecho XBRL esperado (±1 %).
- **`trayectoria`**: el agente pasó por las herramientas esperadas
  (`get_xbrl_fact` en numéricas, `search_filings` en extractivas, las dos en
  comparativas).

**`acierto` = todos los evaluadores aplicables en verde.** Una comparativa con la
cifra perfecta y sin cita suspende. Es exigente a propósito: «acertar por el
camino equivocado cuenta como fallo».

### Tres repeticiones y una barra de ruido

El modelo no es determinista. Cada arquitectura se corre tres veces, con la
repetición dentro del `thread_id` para que no se contaminen. En el baseline,
**2 de 20 preguntas oscilan entre repeticiones**: ese es el ruido de fondo, y
cualquier mejora menor que eso no es una mejora.

### Instrumentación: atribuir contando, no estimando

Con 20 preguntas, cada una vale 5 puntos y la mayoría de los cambios
individuales son indistinguibles del ruido. Por eso no hago ablaciones de cada
pieza: en vez de eso, cada tabla lleva columnas que dicen **cuántas veces actuó
cada mecanismo**: `corrigio_cifra`, `corrigio_cita`, `limite_alcanzado`,
`reintentos_esquema`, `busquedas_reescritas`, `reintentos_proveedor`. Un
guardrail que nunca se disparó no aportó nada — y eso se cuenta, no se
estima. Ejemplo real: el verificador de cifras se disparó 3 veces en A1 y 0 en
A2; la diferencia es que entre medias arreglé un bug de `get_xbrl_fact` (§5).

### Predicciones antes de medir

`docs/predicciones.md` tiene, para cada peldaño, lo que predije **antes** de
ejecutarlo y lo que salió. No se edita después. Cuatro predicciones han fallado
y cada una obligó a leer trazas y explicar algo que no sabíamos; ese fichero es
la mitad de la presentación.

---

## 3. Los peldaños, uno a uno

Las arquitecturas son **presets de configuración** en `agente/config.py`, no
ramas: el mismo código, con interruptores. Cada peldaño añade y no quita nada.

### Baseline — el agente del día 10, sin tocar

Prompt del profesor, `RespuestaFinanciera` sin validadores, sin middleware,
retrieval denso con filtros. **61,7 %.** Numéricas 100 %, extractivas 94 %,
comparativas 8 %.

Lo que encontré leyendo las trazas: el agente **razona bien las ocho
comparativas** (deltas, porcentajes, el signo de la caída de Meta, hasta el
split 10:1 de NVIDIA) y suspende siete. Pone la variación en `cifra`; el golden
set espera el valor del ejercicio reciente. `ratio_cifra` es idéntico en las
tres repeticiones — es una convención que nadie le había dicho, no falta de
capacidad. Verificado contra el `ej-003` del propio Guillermo: el golden set
tiene razón, y el hold-out usará la misma convención.

### A1 — guardrails: límites, dos verificadores, esquema estricto, prompt honesto

- `ToolCallLimitMiddleware` (8 herramientas, 1 `read_section`) y
  `ModelCallLimitMiddleware` (10 vueltas), con `exit_behavior="continue"` para
  que el agente cierre con lo que tenga.
- **Verificador de cifras** (`after_model`): si la `cifra` no cuadra con ningún
  hecho XBRL del ticker y ejercicio, devuelve el mensaje al modelo con la lista
  de hechos y `jump_to="model"`. Una corrección por invocación, sin bucles.
- **Verificador de cita**: el `chunk_id` existe y contiene la `cita`.
- `RespuestaFinancieraEstricta`: validadores de coherencia (`fuente='xbrl'` ⇒
  hay cifra; `fuente='texto'` ⇒ hay cita y chunk; ticker de los seis; etc.).
  El contrato `RespuestaFinanciera` del enunciado queda intacto.
- Prompt `HONESTO`: cómo rellenar cada campo, y la convención de `cifra`.

**75,0 %.** `cifra` 50 → 100 %: la línea del prompt bastó. Dos sorpresas: la
trayectoria **bajó** (83 → 75 %) porque el prompt honesto («a la tercera,
cierra») hace al agente más tacaño y deja de buscar texto en comparativas — un
efecto secundario real de un guardrail; y el coste **bajó** porque los
verificadores casi no se disparan.

### A2 — retrieval: filtros forzados y reescritura de la consulta

- `forzar_filtros` (`wrap_tool_call`): si la pregunta identifica ticker/año/
  sección y el modelo los olvida, se rellenan.
- `reescritura`: la consulta del modelo pasa por una llamada barata que la
  reescribe con vocabulario de 10-K, cacheada en disco.

**75,0 %, sin cambiar una sola respuesta.** Pero el recall@5 del retriever sube
de 50 a 64 %. Es el hallazgo más limpio del proyecto: *lo que mejora al buscador
no mejora necesariamente al agente*, porque el prompt del profesor ya obliga al
modelo a escribir las consultas en inglés — el modelo ya era el reescritor. Y
lo que la reescritura hizo de verdad fue convertir lenguaje natural en sintaxis
booleana (`"Digital Markets Act" AND gatekeeper AND (obligations OR
requirements)`), que un retriever denso no entiende: comillas y `AND` son
tokens más para BGE. No empeora porque los filtros de metadatos absorben el
ruido. El coste real: **+72 % de latencia** (una vuelta de red por búsqueda con
un modelo que razona).

### A3 — híbrido BM25 (definida, predicha, no ejecutada)

RRF del orden denso y el orden BM25, medido **después** de la reescritura,
porque la tabla del §4.4 dice que antes no aporta nada (7/14 → 7/14) y después
sí (9/14 → 12/14). Predicción: plano en acierto, por la misma razón que A2.

### A4 — el procedimiento de comparativas (y es `final`)

Prompt `COMPARATIVAS`: dos `get_xbrl_fact` con el mismo concepto, calcular la
variación, **buscar la explicación en el Item 7 con `search_filings`**, y el
procedimiento de conceptos por acción (buscar el split antes de comparar EPS).

**96,7 %** (0,95 / 1,00 / 0,95). Comparativas 37,5 → 95,8 %. Trayectoria 100 %.
Las cinco comparativas mudas empiezan a buscar: en esa familia `fuente` pasa de
15 `xbrl` + 9 `ambas` a **23 `ambas` y ningún `xbrl`**. Lo había predicho con
la tabla de posiciones del ancla: con el retrieval de A4, las cinco tenían el
fragmento correcto en posición 1 o 2. El cuello de botella nunca fue encontrar;
era buscar.

Los dos únicos fallos de 60 son el mismo: el modelo emite un turno vacío y
`create_agent` cierra sin respuesta estructurada. 3,3 % de las invocaciones.
Ver §7.

---

## 4. Lo que he cambiado en vuestros ficheros, y por qué

Regla que me impuse: **no tocar `retrieval.py`, `corpus.py` ni las firmas de
las cuatro herramientas** (son contrato del enunciado). He cumplido las tres.
Lo que sí he cambiado:

### `agente/herramientas.py` (Diego)

**`construir_herramientas(*, reescritura=False, hibrido=False, k=5)`.** Tres
argumentos con valor por defecto. Con los defectos es *exactamente* el agente
del día 10; baseline y A1 no se ven afectados. Lo que cambia es lo que hay
*detrás* de `search_filings`: si `reescritura`, la consulta se reescribe antes;
si `hibrido`, se llama a `recall.hibrido` en vez de a `retrieval.buscar`. La
firma que ve el modelo es la misma. Necesitaba esto porque `agente.py` construye
todas las arquitecturas con el mismo código y solo cambia los interruptores.

**Una línea en `get_xbrl_fact`:** `f"{f.value:,.0f}"` → `formatear_valor(f.value,
f.unit)`. El `:,.0f` está pensado para dólares, pero redondea los valores por
acción: devolvía «EarningsPerShareDiluted = **3** USD/shares» para 2,94. El
modelo copiaba el 3, el evaluador lo tumbaba (3/2,94 = +2 %), y en A1 el
verificador lo rescataba del texto — es decir, **el guardrail estaba tapando un
bug de la herramienta**. Lo vi en la traza de gX-019. Ahora los valores por
acción (y cualquier valor < 1000) salen con dos decimales. Afecta a cualquier
pregunta de EPS del hold-out.

**Detalle de `k`:** el valor por defecto de la firma de `search_filings` es ahora
el `k` de la arquitectura en vez de un 5 fijo. Hoy todos los presets tienen 5,
así que no cambia nada; lo arreglé porque un test de integración pidió `k=3` y
recibió 5.

### `agente/interfaz.py`, `agente/agente.py` — reescritos

El `interfaz.py` original tiraba `r["messages"]` (y los evaluadores los
necesitan), contaba `RespuestaFinanciera` como herramienta (llamadas infladas
en 1) y `evaluar()` no propagaba `mejoras`. Lo reescribí entero con el diseño de
§2. `agente.py` construye el agente a partir de un preset; `construir_agente(mejoras=True)`
sigue funcionando como alias de `"final"`.

### Ficheros nuevos

`config.py` (presets), `esquema.py` (esquema estricto), `middleware.py`,
`prompts.py`, `resultado.py` (normalización de trazas), `evaluadores.py`,
`recall.py` (las cinco configuraciones del §4.4, la reescritura y el recall
sobre las consultas reales del agente), `cli.py`, `tests/` (55 tests, sin API),
`notebooks/evaluacion.ipynb`, y los tres documentos de `docs/`.

---

## 5. Bugs que he encontrado y arreglado

El detalle está en `docs/errores_y_reparaciones.md` (26 entradas). Los que os
afectan directamente:

| # | qué | dónde |
|---|---|---|
| 8 | `get_xbrl_fact` redondea EPS a entero | `herramientas.py`, corregido |
| 9 | el `interfaz.py` original tiraba los mensajes y contaba mal las llamadas | reescrito |
| 12 | Gemini 3 devuelve 400 «Corrupted thought signature» en ~8 % de las llamadas con middleware | `ejecutar` reintenta una vez en hilo nuevo; funcionó 5/5 |
| 25 | el modelo emite un turno vacío y no hay respuesta estructurada (2 de 60 en A4) | pendiente: mismo reintento, disparado por `structured_response is None` |
| 26 | con el híbrido, los fragmentos se imprimen como «similitud 0.032» (es la suma RRF, no un coseno) | cosmético, pendiente |

Y tres cosas de método que descubrí a base de equivocarme: el calentamiento
del índice caía dentro de la latencia de la primera pregunta (`calentar()` lo
saca fuera); el detector de «límite alcanzado» saltaba con el texto de NVIDIA
sobre controles de exportación; y `ToolCallLimitMiddleware` contaba la
respuesta estructurada como una herramienta más.

---

## 6. Cómo trabajar con la rama

```powershell
git fetch
git checkout mejoras
uv sync --frozen
uv run --with pytest python -m pytest -q      # 55 passed
```

- **`python -m pytest`, no `pytest` a secas**: Windows (App Control) bloquea el
  lanzador `.exe` que uv genera en una carpeta temporal.
- El notebook: cambia `ARQ` en el bloque 1 y ejecuta 1 → 3 → 5. El bloque 3 es
  idempotente: si se corta, se relanza y sigue. Un JSON con error se repite solo.
- Sin clave, todo lo que no gasta API funciona: puntuar, comparar, recall
  (menos la reescritura).
- **Commitear en cuanto los tests pasan.** Tres veces perdí trabajo porque
  estaba solo en el árbol de trabajo y un `git restore` lo devolvió al commit
  anterior.
- La clave va en `.env` y nunca en el repo (está en `.gitignore`; el notebook
  solo imprime `bool(os.environ.get("OPENROUTER_API_KEY"))`).

---

## 7. Lo que falta y lo que mejoraría

**Antes de la entrega (23-sep 23:59):**

1. **Reintento cuando no hay respuesta estructurada** (bug 25). Con 10
   preguntas ciegas y un 3,3 % de turnos vacíos, hay un 28 % de probabilidad de
   perder una pregunta entera. Son ~15 líneas, el mismo patrón que el reintento
   del 400.
2. **Ejecutar A3** para que la escalera tenga los cuatro peldaños. Predicción
   escrita: plano en acierto.
3. **Merge de `mejoras` en `main`.** El profesor clona `main`; hay que
   fusionar antes del plazo. Diego: tu rama `traduccion-retrieval-mejorado` toca
   `retrieval.py`; la mía toca `herramientas.py`. No deberían chocar, pero
   miradlo.
4. **Ensayar `evaluar("holdout.jsonl")` en un clon limpio**, con el índice
   FAISS descargado y el codificador en caché, cronometrado: A4 tarda 49 s por
   pregunta, o sea ~8 minutos para las 10 ciegas. Hay que saber si eso cabe en
   la clase.
5. El informe PDF.

**Mejoras que dejaría anotadas pero no haría ya:**

- **La latencia de la reescritura.** +72 % por una llamada que no cambia
  ninguna respuesta. Si el tiempo del día 24 aprieta, `reescritura=False` en
  `final` es una decisión defendible con los datos de A2.
- **La etiqueta «similitud»** con el híbrido: renombrar a «score».
- **Validar `PRECIOS_OPENROUTER`** contra openrouter.ai/activity; la ficha del
  modelo lleva un «50 % off». Si cambia, se repuntúa sin repetir nada.
- **Ablación de «a la tercera, cierra»**: es la línea del prompt honesto que
  hizo al agente tacaño en A1. Merecería medirse sola.
- **Un golden set con fallos de retrieval de verdad**: en este, cuando el agente
  busca, encuentra. Para que A2/A3 tuvieran algo que arreglar habría que añadir
  preguntas cuyo ancla esté enterrada (posición > 20 con el denso).
- **Diego:** en tu tabla de recall falta la fila «reescritura sola». Sin ella el
  salto de 7 a 12 no se puede atribuir entre reescritura e híbrido; la mía sí la
  tiene (9/14).

**Preguntas para vosotros:**

- ¿Os parece bien que `final` sea A4 tal cual (con reescritura e híbrido), o
  preferís `final` = A1 + prompt de comparativas, que da lo mismo en acierto y
  tarda la mitad? Yo lo decidiría con el cronómetro del punto 4.
- ¿Alguien tiene un caso del hold-out del profesor de otros años? Serviría para
  ensayar con preguntas que no hayamos visto.
