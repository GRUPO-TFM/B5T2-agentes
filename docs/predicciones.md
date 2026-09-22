# Predicciones antes de medir

Cada peldaño de la escalera se predice **antes** de ejecutarlo, con la fecha y el
commit desde el que se predice. El valor de este fichero no es acertar: es que una
predicción fallida obliga a explicar por qué, y esa explicación suele ser el
hallazgo. Ya ha pasado una vez (ver A2 más abajo).

Convención: cada bloque se escribe antes de lanzar la arquitectura y **no se
edita después**. El resultado se anota debajo, en una línea aparte.

---

## Baseline (medido el 2026-09-22, commit `d7e2f30`)

Punto de partida contra el que se miden todos los peldaños. Media de 3 repeticiones:

| métrica | valor |
|---|---|
| acierto | 61,7 % |
| acierto numéricas (6) | 100 % |
| acierto extractivas (6) | 94,4 % |
| acierto comparativas (8) | 8,3 % |
| evaluador cita | 52 % |
| evaluador cifra | 50 % |
| evaluador trayectoria | 83 % |
| llamadas/pregunta | 3,95 |
| coste/pregunta | 0,0162 $ |
| latencia/pregunta | 20,3 s |

Ruido de fondo medido: **2 preguntas de 20 oscilan** entre repeticiones (gX-007 y
gX-019). Cualquier peldaño que mueva menos de 2 preguntas es indistinguible del
ruido y así hay que reportarlo.

### Diagnóstico de las 8 comparativas (leído de las trazas crudas)

El agujero tiene **dos causas independientes**, y de ahí que se arreglen en dos
peldaños distintos:

| causa | a quién afecta | qué peldaño la ataca |
|---|---|---|
| (a) `cifra` lleva la **variación** en vez del valor del ejercicio reciente | 7 de 8 (todas menos gX-019) | **A1**, vía la convención explícita del prompt `HONESTO` |
| (b) el agente **no busca texto**: responde `fuente='xbrl'`, sin cita y sin pasar por `search_filings` | 4 de 8 (gX-013, gX-014, gX-015, gX-018) | **A4**, vía el paso 3 del prompt `COMPARATIVAS` |
| (b') cita un chunk correcto con texto **no literal** (tabla reconstruida) | gX-017, gX-020 y gX-019 rep3 | **A1**, vía `verificar_cita` |

La causa (a) es determinista: `ratio_cifra` es idéntico en las tres repeticiones
(0,130 MSFT · 0,592 NVDA · 0,031 META). No es falta de capacidad — la prosa de
`respuesta` es correcta en las ocho, incluido el split 10:1 de NVDA.

---

## A1 · `a1_guardrails` (predicho el 2026-09-22, commit `485328a`, antes de ejecutar)

Qué añade sobre el baseline: límites de llamadas (8 herramientas, 1 `read_section`,
10 vueltas de modelo), verificador de cifra contra XBRL, verificador de cita,
esquema estricto y prompt `HONESTO`.

**Predicción principal — el evaluador `cifra` en comparativas sube de 1/8 a ≥ 6/8.**
La razón es una sola línea del prompt `HONESTO`: «si la pregunta es una variación
entre dos ejercicios, `cifra` lleva el valor del ejercicio más reciente y la
variación se explica en `respuesta`». Es una convención, no una capacidad, así que
basta con decirla.

**Predicción secundaria, y es la importante para leer la tabla — el `acierto`
global apenas se mueve: 61,7 % → entre 62 % y 70 %.** `acierto` exige que *todos*
los evaluadores aplicables estén en verde, y las comparativas seguirán suspendiendo
`cita` y `trayectoria` por la causa (b), que A1 no toca. Es decir: **A1 arregla la
mitad del problema y la tabla de `acierto` no lo enseñará.** Lo enseñará la columna
`cifra`. Esto no es un defecto del peldaño sino la razón por la que el informe
reporta los tres evaluadores por separado y no solo el agregado.

Resto de predicciones:

- `cita` global: plano (52 % → 52-60 %). Solo puede subir por gX-017/gX-020, donde
  `verificar_cita` debería forzar una cita literal. `corrigio_cita` debe ser > 0 en
  esas dos; si sale 0 en las tres repeticiones, el verificador no está enganchado.
- `trayectoria`: plano (83 %). Nada en A1 le dice al agente que busque texto.
- Numéricas (100 %) y extractivas (94,4 %): **no deben bajar**. Usan 2,0 y 3,7
  llamadas de media, muy por debajo del límite de 8. Si bajan, el culpable es el
  esquema estricto rechazando respuestas válidas, y se ve en `reintentos_esquema`.
- Coste y latencia: **suben**. Cada corrección del verificador es una vuelta de
  modelo extra. Estimación: +15 a +30 % sobre 0,0162 $ y 20,3 s.

**Riesgo identificado — el límite de 8 llamadas muerde en gX-019.** En el baseline
esa pregunta usó 8, 8 y **17** llamadas. La repetición que se fue a 17 (54 s) será
cortada en la novena. Como esa repetición ya suspendía `cita`, la predicción es que
el corte sea **neutro o favorable**: menos deriva, misma respuesta. Si en cambio
gX-019 empeora en las tres repeticiones, el límite está mal calibrado y hay que
subirlo a 10, no quitarlo. `limite_alcanzado` es la columna que lo dice.

> **Resultado (medido el 2026-09-22, commit `aea6ec7`, 3 reps × 20, 5 filas con error del proveedor):**
>
> | métrica | baseline | A1 (60 filas) | A1 sin los 5 errores (55) | predicción |
> |---|---|---|---|---|
> | acierto | 61,7 % | 66,7 % | 72,7 % | 62-70 % ✔ (por arriba) |
> | cifra | 50 % | 89,3 % | **100 %** | ≥ 6/8 en comparativas ✔ (8/8, en las tres reps) |
> | cita | 52 % | 53,7 % | 60,5 % | plano ✔ |
> | trayectoria | 83 % | 66,7 % | 72,7 % | plano ✘ **baja** |
> | comparativas | 8,3 % | 37,5 % | 37,5 % | ≤ 25 % ✘ (mejor de lo previsto) |
> | numéricas | 100 % | 94,4 % | 100 % | no bajar ✔ (el fallo es un error de red) |
> | extractivas | 94,4 % | 77,8 % | 100 % | no bajar ✔ (los 4 fallos son errores de red) |
> | coste / latencia / llamadas | 1,62 ¢ / 20,3 s / 3,95 | 1,39 ¢ / 16,7 s / 3,27 | — | subir ✘ **bajan** |
>
> **Tras reparar los 5 errores** (segunda pasada del bloque 3; 6 reintentos en total, gX-009 rep2 necesitó dos),
> **A1 definitivo con 60 filas válidas: acierto 75,0 % · numéricas 100 % · extractivas 100 % · comparativas 37,5 % ·
> cita 64,3 % · cifra 100 % · trayectoria 75,0 % · 1,41 ¢ · 17,2 s · 3,25 llamadas.** Las tres repeticiones dan
> exactamente 0,75: el peldaño es estable. La causa del 400 quedó capturada en el `body` del reintento fallido:
> «Gemini models require OpenRouter reasoning details to be preserved in each request … Upstream error: Corrupted
> thought signature». Es el requisito de Gemini 3 de que las firmas de razonamiento vuelvan intactas en cada vuelta
> de herramientas; no es determinista y el reintento en hilo nuevo lo resuelve (5/5).
>
> **Lo que salió como se predijo.** `cifra` pasa a 8/8 en comparativas en las tres repeticiones: la convención
> del prompt bastó, era una convención y no una capacidad. El `acierto` global se mueve poco, como se dijo, porque
> exige los tres evaluadores. gX-019 (split de NVDA) pasa de 2/3 a 3/3 con el límite mordiendo en 2 de 3 reps:
> el corte fue favorable, como se predijo. Numéricas y extractivas no bajan por el agente: los 5 fallos son
> `BadRequestResponseError: Provider returned error` (400 del proveedor), 0 en el baseline. Sin ellos, 100 % y 100 %.
>
> **Lo que salió mal, y por qué — tres hallazgos.**
>
> 1. **Trayectoria baja 83 → 73 % (sin errores) porque A1 hace al agente más tacaño.** gX-017 (AAPL) llamaba a
>    `search_filings` en las 3 reps del baseline y en A1 en ninguna; gX-013 y gX-015 pierden la búsqueda ocasional.
>    Causa: el prompt `HONESTO` empuja a cerrar («a la tercera, cierra», «responde con lo que tengas») y define
>    `fuente='xbrl'` como respuesta legítima. Un guardrail contra el bucle infinito tiene como efecto secundario
>    menos búsqueda de texto en comparativas. Esto es lo que A4 tiene que revertir (paso 3: buscar el MD&A).
>    Efecto secundario real, medido, y es el hallazgo más valioso del peldaño.
> 2. **Coste y latencia bajan en vez de subir.** Los verificadores se dispararon 4 veces en 60 (3 de cifra, todas en
>    gX-019; 1 de cita), así que su coste es ~0; mientras, el agente busca menos (punto 1) y gX-019 dejó de derivar.
>    La predicción asumía verificadores frecuentes; no lo son.
> 3. **Comparativas 3/8 en vez de ≤ 2/8**: gX-020 (META por regiones) pasa a citar literalmente sin que el
>    verificador se dispare. Lo arregló la línea del prompt «`cita`: una frase LITERAL … copiada tal cual», no el
>    middleware. El prompt hizo el trabajo que se le había asignado al verificador.
>
> **Dos bugs encontrados en las trazas de gX-019:**
> - `get_xbrl_fact` formatea con `:,.0f` y devuelve «EarningsPerShareDiluted = 3 USD/shares» para 2,94 (y 12 para
>   11,93). El modelo copia el 3, el verificador lo rechaza (3/2,94 = +2 %), y el modelo recupera 2,94 del texto del
>   Item 8. El verificador tapó un bug de la herramienta. Afecta a cualquier concepto por acción; en el golden solo a
>   gX-019, pero el hold-out puede traer más. Corregido en el verificador (`formatear_valor`); la corrección en
>   `herramientas.py` (fichero de Diego) se aplica a partir de A2 y se deja anotada.
> - `ToolCallLimitMiddleware` global contaba la llamada de salida estructurada como una herramienta: con 8, la
>   respuesta y su corrección gastaban dos, y con el presupuesto agotado la propia respuesta recibía un «Tool call
>   limit exceeded». Corregido con `LimiteDeHerramientas`. En A1 solo tocó a gX-019 y la respuesta se capturó igual,
>   así que la medición se mantiene; no se repite A1 por esto.
>
> **Los 5 errores del proveedor** (gX-009 ×2, gX-010 ×2, gX-005 ×1; no deterministas — cada pregunta también
> tiene reps buenas). El harness solo guardó «Provider returned error» y no el `body` con el error real de Google;
> corregido: ahora se guarda entero, se reintenta una vez en un hilo nuevo y una segunda pasada repara solo las
> filas con error, contando el reintento como instrumentación (`reintentos_proveedor`).

---

## A2 · `a2_retrieval` (predicho el 2026-09-22, tras A1, antes de ejecutar)

Qué añade sobre A1: `forzar_filtros` (rellena ticker/año/item en `search_filings`
si el modelo los olvida) y `reescritura` (la consulta del modelo pasa por una
llamada barata que la reescribe con el vocabulario del 10-K, cacheada). Entre A1
y A2 cambia además una herramienta: `get_xbrl_fact` deja de redondear los valores
por acción (bug 8 del registro de errores); afecta solo a gX-019.

### Primero, una corrección de una predicción anterior

En el diseño inicial se afirmó que la ganancia de A2 vendría de **forzar los
filtros de metadatos**. Los datos del baseline lo desmienten: de las 81 búsquedas
ejecutadas, **el 100 % ya llevaba `ticker` y el 94 % ya llevaba `item`**. El margen
de `forzar_filtros` es casi nulo. Queda anotado como error de predicción.

### Y una sospecha que cambia la predicción

La tabla de recall del §4.4 mide el retriever con la **pregunta del golden en
español**, y ahí la reescritura sube de 7/14 a 9/14. Pero el agente no manda esa
pregunta: manda **su propia consulta**, y el prompt base ya le dice «el corpus está
en inglés: escribe las consultas en inglés». Las trazas lo confirman: «ten-for-one
stock split retroactive basis earnings per share», «revenue by geographic region
United States Europe Asia-Pacific». **El modelo ya es el reescritor.** La mejora
que la tabla atribuye a la reescritura ya está dentro del baseline del agente.

Y más: en A1, de las preguntas en las que el agente buscó texto, el evaluador de
cita pasa en **todas** (6/6 extractivas, 3/3 comparativas que buscaron). En el golden
set no queda ningún fallo de retrieval que arreglar del lado del agente.

**Predicción principal: A2 no mueve el acierto** (75 % ± el ruido de 2 preguntas).
`cifra`, `cita` y `trayectoria` planas. Numéricas y extractivas al 100 %.

**Predicción de coste: sube.** Cada búsqueda paga una llamada extra de reescritura
la primera vez (después va de caché): +0,1 a +0,3 ¢ por pregunta y +1 a +3 s.

**Instrumentación que lo dirá:** `% búsquedas reescritas` (cuántas veces la
reescritura cambió algo en la consulta del modelo; si es < 30 %, el modelo ya
escribía consultas de 10-K) y `recall_de_trazas` (con las consultas reales del
agente, ¿otro retriever habría visto el ancla? — predicción: denso y reescrito
empatan; el híbrido, si acaso, +1).

Si A2 no mueve nada, no es un peldaño fallido: es la diapositiva «lo que mejora
el retriever no siempre mejora al agente, porque el agente ya hace parte del
trabajo del retriever». Y la tabla del §4.4 sigue siendo válida para lo que mide.

> Resultado: _(pendiente)_
