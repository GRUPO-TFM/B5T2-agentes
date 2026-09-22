# Errores, bugs y reparaciones — el registro para la presentación

El enunciado pide contar lo que se probó y no funcionó. Este fichero es ese
registro: cada problema con su síntoma, cómo se detectó, la causa, la
reparación y **lo que enseña**. Se añade una entrada cada vez que se repara
algo; no se borra ninguna. Las que siguen abiertas están al final.

Leyenda de categorías:
- **medición** — el harness medía mal; el agente no tenía la culpa
- **agente** — el agente o sus herramientas hacían algo mal
- **proveedor** — la API o la red
- **predicción** — se predijo antes de medir y salió al revés (esto no es un error, es el método funcionando)
- **proceso** — cómo trabajamos, no qué construimos

---

## Resumen en una tabla

| # | cat. | qué pasó | cómo se detectó | reparación |
|---|---|---|---|---|
| 1 | medición | la carga del índice FAISS y del codificador caía DENTRO de la latencia de la primera pregunta (25 s frente a 8 s) | aviso de tqdm/HF Hub en gX-003 y latencia anómala | `calentar()` fuera del cronómetro; `ejecutar()` la llama antes del bucle |
| 2 | medición | las columnas `cifra` y `cita` eran a la vez respuesta del agente y veredicto: el booleano pisaba el dato (`cifra = 0.0` donde el agente dijo 36.602 M) | al leer la tabla del baseline con las trazas al lado | `cifra_dada` / `cita_dada` + `cifra_esperada` + `ratio_cifra`; test de regresión |
| 3 | medición | el detector de «límite alcanzado» buscaba *limit* y *exceed* sueltos y saltaba con el texto de NVIDIA sobre controles de exportación: 5 % de límites en un baseline SIN límites | la columna no podía ser > 0 en el baseline | comparar con el prefijo exacto de LangChain `Tool call limit exceeded`; test con el texto real del 10-K |
| 4 | medición | `limite_alcanzado` y `reintentos_esquema` se calculaban al ejecutar y se guardaban: un detector corregido no se aplicaba a lo ya medido | al preguntarnos si los bugs 2 y 3 obligaban a repetir el baseline | se recalculan al puntuar desde `messages`; test que ensucia el valor guardado y comprueba que se ignora |
| 5 | medición | los errores de la API se guardaban como «Provider returned error», sin el `body` que lleva el error real de Google | 5 errores en A1 imposibles de diagnosticar | se guarda `status_code` + `body` entero; reintento ×1 en hilo nuevo; una segunda pasada repara solas las filas con error; columna `reintentos_proveedor` |
| 6 | medición | `ToolCallLimitMiddleware` global contaba la llamada de salida estructurada como herramienta: con 8, la respuesta y su corrección gastaban dos y la propia respuesta recibía «Tool call limit exceeded» | traza de gX-019 en A1 | `LimiteDeHerramientas`: la respuesta no cuenta |
| 7 | medición | la lista de hechos XBRL que el verificador enseña al modelo usaba `:,.0f`: «EarningsPerShareDiluted = 3» | misma traza de gX-019 | `formatear_valor`: 2 decimales para valores por acción o < 1000 |
| 8 | agente | `get_xbrl_fact` devuelve «= 3 USD/shares» para 2,94 y «= 12» para 11,93 (`:,.0f`, pensado para dólares); el modelo copia el 3 y el evaluador lo tumba (3/2,94 = +2 %) | traza de gX-019 en A1: el verificador rechazó el 3 y el modelo recuperó 2,94 del Item 8 — **el verificador tapó un bug de la herramienta** | corregido en `herramientas.py` (fichero de Diego, una línea) a partir de A2. **Confirmado al medir A2:** `% corrigió cifra` pasa de 5 % a **0 % en las tres repeticiones** con `cifra` al 100 % — el guardrail dejó de hacer falta porque la herramienta ya no miente |
| 9 | agente | el `interfaz.py` original tiraba `r["messages"]`, contaba `RespuestaFinanciera` como herramienta (llamadas infladas en 1) y `evaluar()` no propagaba `mejoras` | revisión del repo el 21-sep | reescritura completa del harness: crudo primero, `ejecutar`/`puntuar`/`comparar` separados |
| 10 | agente | comparativas: el agente pone la **variación** en `cifra` en vez del valor del ejercicio reciente, en 7 de 8, en las tres repeticiones (`ratio_cifra` idéntico: determinista) | análisis del baseline; verificado contra el `ej-003` del profesor que el golden set usa la convención correcta | una línea del prompt `HONESTO` → 8/8 en A1 |
| 11 | agente | 4 de 8 comparativas responden solo con XBRL (`fuente='xbrl'`), sin buscar texto: suspenden cita y trayectoria a la vez | tablas del baseline | queda para A4 (paso 3 del prompt `COMPARATIVAS`: buscar el MD&A) |
| 12 | proveedor | `BadRequestResponseError: Provider returned error` en 5 de 60 llamadas de A1 (0 en baseline) | tablas de A1 | `body` capturado en el reintento: *«Gemini models require OpenRouter reasoning details to be preserved… Corrupted thought signature»*; no determinista; el reintento en hilo nuevo lo resolvió 5/5 |
| 13 | predicción | «la ganancia de A2 vendrá de forzar los filtros» | baseline: el 100 % de las 81 búsquedas ya llevaba ticker y el 94 % item | la ganancia de A2 tiene que venir de la reescritura; anotado en `predicciones.md` |
| 14 | predicción | «A1 no mueve la trayectoria» | A1: 83 → 75 %; gX-017 deja de llamar a `search_filings` en las 3 reps | el prompt honesto («a la tercera, cierra») hace al agente **más tacaño con el texto**: efecto secundario real de un guardrail; A4 debe revertirlo |
| 15 | predicción | «A1 sube coste y latencia por los verificadores» | A1: bajan (1,62 → 1,41 ¢; 20,3 → 17,2 s) | los verificadores se dispararon 4 veces en 60; el ahorro por buscar menos y por cortar gX-019 pesa más |
| 16 | predicción | «gX-020 lo arreglará el verificador de cita» | A1: cita literal sin que el verificador se disparara | lo hizo la línea del prompt «una frase LITERAL, copiada tal cual»: el prompt hizo el trabajo del middleware |
| 17 | proceso | tres veces aparecieron en disco versiones antiguas de ficheros ya corregidos (pytest 39 en vez de 41) | comparando byte a byte el disco con lo enviado | el trabajo estaba sin commitear y un `git restore`/`checkout` lo devolvía a `d7e2f30`; **commitear en cuanto los tests pasan** |
| 18 | proceso | se borró la rep 1 de un baseline completo creyendo que no había corrido | `rep1: 0 preguntas guardadas` | se rehízo desde cero; lección: mirar `crudo/` antes de borrar, y el bloque de limpieza ahora solo informa si los dos flags están apagados |
| 19 | proceso | «0,53 ¢» leído como 53 céntimos | contraste con openrouter.ai/activity | es 0,0053 $; pendiente cambiar el formato a USD con 4 decimales |
| 20 | proceso | el primer `pytest` de una sesión dio 39 y el segundo, sin tocar nada, 41 | — | sin explicación confirmada (caché/sincronía de Windows); irrelevante una vez commiteado |
| 21 | medición | el `k` de la arquitectura no llegaba a `search_filings`: la firma decía `k: int = 5` y LangChain rellena ese 5 antes de que el código pueda sustituirlo — el parámetro existía pero era inerte | el test de integración con el FAISS real pidió `k=3` y recibió 5 fragmentos (el test de cableado pasaba `k=0` y no lo pilló) | el valor por defecto de la firma es ahora el `k` de la arquitectura (el esquema que ve el modelo lo refleja); test con los tres casos: sin `k`, `k` explícito, `k=0`. Nada medido afectado: todos los presets tienen `k=5` |
| 22 | proceso | `uv run --with pytest pytest` deja de arrancar: «An Application Control policy has blocked this file (os error 4551)» | al lanzar los tests tras A1 | es Windows (App Control) bloqueando el lanzador `pytest.exe` que uv crea en una carpeta temporal; `python -m pytest` no pasa por el `.exe` y funciona. Regla: siempre `uv run --with pytest python -m pytest -q` |
| 23 | proceso | el test de integración (`hibrido=True` con FAISS y BM25 reales) no corre en el contenedor de Claude porque no alcanza huggingface.co; solo corre en el PC de Javi | `53 passed, 1 skipped` aquí frente a `54 passed` allí | `skipif` cuando el codificador no está en caché; la verificación final es siempre en el PC de Javi |

---

## Detalle de los que dan diapositiva

### 1 · El calentamiento (medición)

**Síntoma.** gX-003 tardó 25,1 s; las anteriores, unos 8. Y solo en la repetición 1.

**Por qué importa.** El kernel sobrevive entre repeticiones, así que solo la
primera pagaba los 15-20 s de cargar 1.749 vectores y 199 tensores del
codificador. En la tabla eso aparece como «varianza entre repeticiones» —
exactamente lo que las tres repeticiones intentan medir. Un artefacto de
arranque disfrazado de ruido del modelo.

**Lección.** Todo lo que se cargue una vez se carga *antes* del cronómetro. Y
un aviso «inocuo» (tqdm sin ipywidgets) puede estar tapando un defecto real.

### 2 + 3 + 4 · Tres bugs del harness y una regla (medición)

Los tres se encontraron leyendo la tabla del baseline *con las trazas al lado*.
Ninguno cambiaba las métricas agregadas; los tres desvirtuaban el diagnóstico.

La regla que salió de ahí: **crudo primero**. Lo que se guarda al ejecutar es
la conversación entera; todo lo derivado (veredictos, contadores, marcas de
corrección) se calcula al puntuar. Así un detector corregido se aplica a lo ya
medido sin gastar una llamada, y el baseline no hubo que repetirlo (bug 4 fue
descubrir que esa promesa estaba rota en dos columnas).

### 8 · El verificador tapó un bug de la herramienta (agente)

La traza de gX-019 (split 10:1 de NVIDIA) en A1:

1. `get_xbrl_fact` → «EarningsPerShareDiluted = **3** USD/shares» (el valor es 2,94)
2. el modelo responde `cifra = 3.00`
3. el verificador compara con el parquet: 3/2,94 = +2 %, fuera de la tolerancia → rechaza
4. el modelo recupera «Diluted (2) $ 2.94» del Item 8 y corrige

Sin verificador, el baseline habría dado 3 y habría suspendido. Con el
verificador acertó — **por el camino equivocado**: una herramienta que
redondea EPS a entero es un bug, no una fuente. Lo que enseña: los guardrails
tapan errores de capas inferiores, y por eso hay que leer *por qué* se
dispararon, no solo *cuántas veces*. `% corrigió cifra = 5 %` no dice nada;
«las tres veces fueron la misma pregunta y la causa fue la herramienta» sí.

### 10 · La convención de `cifra` en las comparativas (agente)

El baseline razonaba bien las ocho comparativas — deltas, porcentajes, el signo
de la caída de Meta, hasta el split de NVIDIA («ganó un 147 % más por
acción») — y suspendía siete. Ponía la variación en `cifra`; el golden set
espera el valor del ejercicio reciente. `ratio_cifra` era idéntico en las tres
repeticiones (0,130 MSFT, 0,592 NVDA, 0,031 META): determinista, luego
convención y no capacidad. Se verificó contra el `ej-003` del propio profesor
que el golden set tiene razón — y que el hold-out del día 24 usará la misma
convención. Una línea de prompt: 1/8 → 8/8.

### 12 · «Corrupted thought signature» (proveedor)

Gemini 3 exige que las firmas de razonamiento de cada vuelta de herramientas
vuelvan intactas en la siguiente petición. Cuando no vuelven, 400. No es
determinista: la misma pregunta pasa en otra repetición. En A1 fue el 8 % de
las llamadas; en el baseline, 0 — y no sabemos si es azar (0 de 60 con una
tasa del 4 % tiene un 9 % de probabilidad) o si el middleware que inyecta
mensajes lo provoca. Lo que sí sabemos: el reintento en hilo nuevo lo
resolvió 5 de 5, y `evaluar()` pasa por el mismo camino, así que el día 24
está cubierto.

Antes de este error el harness guardaba solo «Provider returned error». La
reparación más importante no fue el reintento sino **guardar el `body`**: sin
él, este párrafo no existiría.

### 13-16 · Cuatro predicciones falladas (predicción)

Cada peldaño se predice antes de ejecutarlo (`docs/predicciones.md`) y no se
edita después. Cuatro han fallado ya, y las cuatro obligaron a mirar las
trazas y explicar algo que no sabíamos:

- que los filtros forzados no tienen margen porque el modelo ya filtra (13);
- que un guardrail contra el bucle infinito hace al agente más tacaño con el
  texto — el efecto secundario que A4 tiene que revertir (14);
- que los verificadores casi no se disparan y por tanto casi no cuestan (15);
- que el prompt hizo el trabajo que se le había asignado al middleware (16).

Ninguna de las cuatro habría salido de una tabla que solo dijera «A1: 75 %».

---

## Trampas del corpus (conocidas de antemano, verificadas)

- `fiscal_year` ≠ año de presentación (NVDA FY2025 cierra en enero de 2025).
- El concepto de ingresos cambia por compañía: NVDA `Revenues`; AAPL, MSFT,
  META y AMZN `RevenueFromContractWithCustomerExcludingAssessedTax`; GOOGL los
  dos en FY2024 y solo `Revenues` en FY2025.
- AMZN no reporta `GrossProfit`, `Liabilities` ni I+D.
- Split 10:1 de NVDA en junio de 2024: el EPS de FY2024 en XBRL no está ajustado.
- El 41 % de los fragmentos contiene una tabla; META Item 1A tiene 34.751 tokens.

---

## Abiertos

- **`herramientas.py` línea 75** (`:,.0f`): corregir antes de A2, avisar a Diego. Afecta a cualquier concepto por acción del hold-out.
- **`construir_herramientas()` no acepta flags**: `reescritura` e `hibrido` están declarados en `config.py` pero inertes en el agente. A2 los implementa como middleware sin tocar los ficheros de Diego.
- **Formato del coste**: pasar de `¢` a USD con 4 decimales.
- **`PRECIOS_OPENROUTER`**: validar contra openrouter.ai/activity (la ficha del modelo lleva «50 % off»).
- **Causa del 400**: ¿lo provoca el middleware que inyecta mensajes o es azar? Se sabrá comparando `reintentos_proveedor` entre arquitecturas.
- Pedir a Diego la fila «reescritura sola» de su tabla de recall.
