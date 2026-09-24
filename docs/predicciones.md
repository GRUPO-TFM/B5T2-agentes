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

> **Resultado (medido el 2026-09-22, commit `aaaa10d`, 3 reps × 20, 0 errores):**
>
> | métrica | A1 | A2 | predicción |
> |---|---|---|---|
> | acierto | 75,0 % | **75,0 %** (0,75 en las tres reps) | «no mueve el acierto» ✔ |
> | numéricas · extractivas · comparativas | 100 · 100 · 37,5 | **100 · 100 · 37,5** | planas ✔ |
> | cita · cifra | 64,3 % · 100 % | **64,3 % · 100 %** | planas ✔ |
> | trayectoria | 75,0 % | 76,7 % | plana ✔ (gX-017 busca en 1 de 3 reps: ruido) |
> | **recall@5 del retriever** | 50,0 % | **64,3 %** | — |
> | coste | 1,41 ¢ | 1,44 ¢ | sube ✔ (+2 %, menos de lo previsto) |
> | latencia | 17,1 s | **29,4 s** | +1-3 s ✘ **+12,3 s** |
>
> **La predicción se cumple en su punto central, y con el contraste más limpio
> posible: el recall@5 del retriever sube 14 pp (50 % → 64 %, que es el 7/14 →
> 9/14 de la tabla del §4.4) y el acierto del agente no se mueve ni una pregunta.**
> `cambios por pregunta` sale literalmente vacío: las 20 preguntas dan el mismo
> veredicto en A1 y en A2. La posición mediana del ancla mejora de 5,5 a 3,5.
> Mejor retrieval, misma respuesta.
>
> **Y el mecanismo no es el que se predijo.** La predicción decía que la
> reescritura no cambiaría las consultas porque el modelo ya escribe en inglés.
> Falso: **cambió 53 de 63 búsquedas (84 %)**. Lo que pasa es lo que escribió:
> convirtió consultas en lenguaje natural en **sintaxis booleana de buscador por
> palabras clave**:
>
> | consulta del modelo | reescritura |
> |---|---|
> | `China competitive position competitors market export controls` | `China "competitive position" competition "export controls" "Item 1A" "Risk Factors"` |
> | `Digital Markets Act gatekeeper "obligations" OR "requirements"` | `"Digital Markets Act" AND gatekeeper AND (obligations OR requirements OR compliance)` |
> | `capital expenditures 2026 anticipate expect` | `MD&A "Liquidity and Capital Resources" "capital expenditures" (expect OR anticipate) 2026` |
>
> El retriever es **denso**: codifica la cadena entera con BGE y compara cosenos.
> Las comillas, los `AND`, los `OR` y los paréntesis no son operadores para él,
> son tokens más. La reescritura le está hablando en un idioma que no entiende.
> Que aun así no empeore se explica por los filtros de metadatos: dentro de un
> único `ticker`+`fiscal_year`+`item` quedan pocas decenas de fragmentos y el
> orden apenas cambia. **El filtro absorbe el ruido de la reescritura.**
>
> Esto sí sugiere un experimento con sentido para A3: esa sintaxis booleana es
> justo lo que BM25 **sí** aprovecha (términos literales, entrecomillados
> exactos). La reescritura podría no estar de más — podría estar esperando al
> retriever adecuado, que es el híbrido.
>
> **El coste real de A2 es la latencia: +72 % (17,1 → 29,4 s), y en las preguntas
> que buscan, +88 % (25,7 → 48,3 s).** El coste en dólares sube solo un 2 %,
> porque la llamada de reescritura gasta pocos tokens; lo que gasta es una vuelta
> de red por búsqueda con un modelo que razona antes de responder. La caché no
> ayuda dentro de una ejecución porque cada consulta del modelo es distinta.
> Para el día 24 esto importa: A2 tal cual añadiría ~4 minutos a las 10 preguntas
> ciegas sin cambiar una sola respuesta.
>
> **Hallazgo no previsto, y el más limpio del peldaño: el verificador de cifras
> dejó de dispararse por completo.** En A1, `% corrigió cifra` era 5 % (3 de 60,
> las tres la misma pregunta: gX-019). En A2 es **0,0 % en las tres repeticiones**,
> y `cifra` sigue al 100 %. La causa es el arreglo del `:,.0f` en
> `get_xbrl_fact`: la traza de A2 muestra «EarningsPerShareDiluted = 2.94
> USD/shares» y `correcciones: []` — el modelo copia el valor bueno a la primera
> y no hay nada que corregir. Es la confirmación medida de lo que se sospechaba
> al leer la traza de A1: **el guardrail estaba tapando un defecto de la
> herramienta, no un error del modelo.** Arreglada la herramienta, el guardrail
> no aporta nada en este golden set — lo cual no es un argumento para quitarlo
> (el hold-out del día 24 puede traer otra cosa), sino la prueba de que la
> instrumentación permite decir qué aportó cada pieza contando, no estimando.
>
> **Defecto menor detectado:** `reescribir_consulta` hace `.strip('"')`, que se
> come la comilla inicial y final legítimas de una consulta booleana
> (`"competitive position"` llega como `competitive position"`). Sin efecto aquí
> (el retriever denso las ignora igual), pero hay que arreglarlo antes de A3, que
> es donde las comillas empiezan a contar.


---

## A3 y A4 · el orden se invierte (decidido el 2026-09-22, antes de ejecutar)

**Por qué A4 antes que A3.** Las 5 preguntas que siguen fallando en A2 son
comparativas que responden `fuente='xbrl'` y **nunca llaman a `search_filings`**
(gX-013, gX-014, gX-015, gX-017, gX-018). Ningún cambio de retrieval puede
tocarlas: no hay búsqueda que mejorar. Luego **A3 está predicho plano con casi
certeza** y **A4 es el único peldaño que puede subir el acierto**. Como A4 es
además `final` — lo que el evaluador ejecuta el día 24 — y la entrega es mañana,
se mide A4 primero y A3 después, para rellenar el peldaño. La escalera del
informe se ordena igual al leerla.

## A4 · `a4_comparativas` (predicho el 2026-09-22, antes de ejecutar)

Qué añade sobre A2: el híbrido BM25 (que es A3) y el prompt `COMPARATIVAS`, cuyo
paso 3 dice explícitamente «busca la explicación de la variación con
search_filings en el Item 7 (MD&A) del ejercicio más reciente, con ticker y
fiscal_year como filtros», más el procedimiento de conceptos por acción (splits).

**Predicción principal: las 5 comparativas mudas empiezan a buscar, y aciertan.**
El argumento no es optimismo, es la tabla de posiciones del ancla con el
retrieval de A4 (`reescritura + híbrido`, la fila 5 del §4.4):

| pregunta | pos. del ancla con el retrieval de A4 |
|---|---|
| gX-013 | **1** |
| gX-014 | **2** |
| gX-015 | **2** |
| gX-017 | **1** |
| gX-018 | **2** |

Las cinco tienen el ancla entre la posición 1 y la 2. **El retrieval no es el
cuello de botella: el cuello de botella era que el agente no buscaba.** Si el
paso 3 consigue que busquen, el fragmento con la cita literal les aparece el
primero o el segundo.

Números concretos, para que la predicción sea falsable:
- comparativas: 37,5 % → **entre 75 % y 100 %** (de 3/8 a 6-8/8)
- acierto global: 75,0 % → **entre 87,5 % y 100 %**
- `cita`: 64,3 % → **≥ 85 %**
- `trayectoria`: 76,7 % → **≥ 95 %** (es la métrica que más directamente mide
  «ahora sí pasa por search_filings»)
- numéricas y extractivas: **100 %, no deben bajar**
- coste y latencia: **suben**. Más búsquedas en 8 preguntas, cada una con su
  llamada de reescritura, más el índice BM25. Estimación: ~2,0 ¢ y ~40 s.

**Riesgos identificados, en orden de probabilidad:**
1. **El límite de 8 llamadas.** Una comparativa con el procedimiento completo
   gasta 2 `get_xbrl_fact` + 1 búsqueda de split + 1 búsqueda de MD&A, y
   `list_available` suele ir de primera: 5. Con una reformulación de más, 7.
   gX-019 ya tocaba el techo en A1 y A2. Si `% límite alcanzado` sube por encima
   del 10 %, el techo hay que subirlo a 10 — no quitarlo.
2. **El verificador de cita.** Al empezar a citar donde antes no se citaba,
   puede dispararse (en A2 estaba al 0 %). Que se dispare es que funciona; lo
   que hay que mirar es si la corrección arregla o si el modelo insiste.
3. **La respuesta larga.** El procedimiento pide explicar la variación Y el
   split; el esquema estricto exige coherencia entre `fuente`, `cifra` y
   `cita`. `reintentos_esquema` lo dirá.

**Si A4 no mueve las comparativas**, la conclusión sería que el problema no es
que no se lo hayamos pedido, sino que el modelo prefiere cerrar con XBRL porque
el prompt honesto de A1 le dio permiso — y entonces la ablación que toca es
quitar de `HONESTO` la línea de «a la tercera, cierra» y medir solo eso.

> **Resultado (medido el 2026-09-22, 3 reps × 20, 0 errores de proveedor, 0,91 $ y 49 min):**
>
> | métrica | A2 | **A4** | predicción |
> |---|---|---|---|
> | acierto | 75,0 % | **96,7 %** (0,95 / 1,00 / 0,95) | 87,5-100 % ✔ |
> | comparativas | 37,5 % | **95,8 %** | 75-100 % ✔ |
> | cita | 64,3 % | **95,2 %** | ≥ 85 % ✔ |
> | trayectoria | 76,7 % | **100 %** | ≥ 95 % ✔ |
> | cifra | 100 % | 97,6 % | — |
> | numéricas · extractivas | 100 · 100 | 100 · 94,4 | no bajar ✘ (una repetición) |
> | coste · latencia | 1,44 ¢ · 29,4 s | 1,52 ¢ · **49,2 s** | ~2,0 ¢ y ~40 s (coste sobreestimado) |
>
> **La predicción se cumple entera, y el mecanismo es el que se dijo.** Las cinco
> comparativas mudas empiezan a buscar y aciertan: gX-013, gX-014, gX-015 y
> gX-017 pasan de 0/3 a **3/3**, gX-018 a 2/3. En las comparativas, `fuente`
> pasa de **15 `xbrl` + 9 `ambas`** a **23 `ambas` y ningún `xbrl`**, y las
> búsquedas por pregunta de 1,12 a 1,67. El paso 3 del prompt hizo exactamente
> lo que se le pidió, y el ancla estaba donde decía la tabla de posiciones.
>
> Con esto, **la lectura de toda la escalera queda cerrada**: el agujero del
> baseline eran las comparativas, y tenía dos causas independientes —la
> convención de `cifra` (arreglada en A1, `cifra` 50 % → 100 %) y que el agente
> no buscaba texto (arreglada en A4, `trayectoria` 75 % → 100 %)—. A2 y A3 no
> mueven el acierto porque atacaban una tercera causa que en este golden set no
> existía: el retrieval nunca fue el cuello de botella.
>
> **Los dos únicos fallos de 60, y son el mismo fallo.** gX-009 rep1 (extractiva)
> y gX-018 rep3 (comparativa) terminan con `structured_response: null`: el modelo
> emite un turno vacío —sin texto y sin tool call— y `create_agent` cierra sin
> salida estructurada. No es un error de red (no hay excepción), ni un límite
> alcanzado (5 y 6 vueltas de modelo frente al techo de 10), ni un problema de
> retrieval (los fragmentos correctos estaban delante). Es el modelo gastando el
> turno en razonamiento y no produciendo nada. Ocurre en el **3,3 %** de las
> invocaciones y el harness lo cuenta honestamente como fallo.
>
> Es un modo de fallo que hay que cerrar antes del día 24: una pregunta ciega que
> caiga aquí se pierde entera. Con 10 preguntas y una tasa del 3,3 %, la
> probabilidad de perder al menos una es del **28 %**. **Corregido el mismo día:**
> `ejecutar` reintenta una vez en un hilo nuevo cuando no hay
> `structured_response`, con la misma mecánica que el 400 del proveedor y
> columnas propias (`reintentos_vacios`, `% sin respuesta`) para no mezclar las
> dos causas. Si el turno vacío persiste, la fila se guarda vacía y cuenta como
> fallo: el reintento no puede servir para esconder nada. Y solo se repara lo
> que no dejó respuesta — una respuesta equivocada nunca se repite, porque eso
> sería re-tirar el dado hasta que salga bien.
>
> **Defecto cosmético detectado:** con el híbrido, `formatear_fragmentos` imprime
> «similitud 0.032» porque el campo `puntuacion` lleva la suma RRF
> (≈ 1/(60+1) + 1/(60+1)), no un coseno. No afecta al ranking ni a ninguna
> métrica, pero la etiqueta miente y el modelo la lee. Renombrar a «score» en el
> texto del fragmento cuando `hibrido=True`.

---

## Golden set adversario · A4 tal cual (predicho el 2026-09-23, antes de ejecutar)

`data/golden_set_dificil.jsonl`: 15 preguntas en tres familias nuevas —
**honestidad** (5, el dato no está en el corpus), **multi** (5, varias compañías
en un ejercicio) y **multi_temporal** (5, compañías × ejercicios). Se corre A4
sin cambiar nada: primero se mide cuánto falla, después se arregla. Convención
de `cifra` en multi-entidad: si se pregunta *quién*, `ticker`=ganadora y
`cifra`=su valor; si se pregunta una diferencia o ratio, `cifra`=esa magnitud.

**Predicción global: acierto entre 40 % y 60 %** (6-9 de 15). Por familia:

**Honestidad — 3 a 5 de 5.** El prompt `HONESTO` ya dice «si get_xbrl_fact te
dice que la compañía NO reportó un concepto, NO lo busques en el texto ni lo
calcules: fuente='ninguna'». Debería funcionar en gY-001 (GrossProfit de AMZN) y
gY-004 (Tesla). Las dudosas son las trampas de texto: gY-002 (el revenue de
FY2023 **está** en una tabla del Item 8 de FY2025) y gY-003 (trimestrales). Si el
modelo busca, lo encuentra y lo da como `fuente='texto'`, suspende — y eso es
justo lo que queremos saber.

**Multi — 2 a 3 de 5.**
- gY-006 (¿quién, AAPL o MSFT?) y gY-007 (¿cuál de las seis?): deberían
  acertar; gY-007 gasta 7 de 8 llamadas y es la prueba fina del límite.
- gY-008 (diferencia GOOGL − META en USD): **predicho fallo por el verificador
  de cifras** — 3.715 M no es un hecho XBRL de ningún ticker, así que el
  verificador lo rechazará y empujará al modelo a poner el I+D de una sola
  compañía. Es la limitación del esquema mono-entidad, medida.
- gY-009 (margen operativo NVDA vs AAPL): 50/50. El verificador salta los
  porcentajes, pero hay riesgo de convención (62,42 frente a 0,6242).
- gY-010 (I+D de AMZN y META): acierto probable en `cifra`; lo que importa es si
  la `respuesta` dice que Amazon no lo reporta o se lo inventa.

**Multi_temporal — 1 a 2 de 5.**
- gY-011 (diferencial NVDA−MSFT): 6-7 llamadas; cabe justo. 50/50.
- gY-012 (ratio pasivo/activos AAPL vs META, 9 llamadas) y gY-015 (las seis,
  12 llamadas): **predicho `limite_alcanzado=True` en ambas** y fallo.
- gY-013 (BPA con split): el procedimiento de splits del prompt es para *una*
  compañía; con dos, 50/50.
- gY-014 (flujo de caja + MD&A): probable acierto; el ancla está en posición
  1-2 con el retrieval de A4.

**Latencia**: ~70 s de media (más llamadas por pregunta que el golden original).

**Lo que este experimento tiene que enseñar, gane o pierda:** qué bloquea el
esquema mono-entidad, qué bloquea el límite de 8, y si la honestidad aguanta
cuando la cifra prohibida está a la vista en el texto. Cada uno de esos tres es
una decisión de diseño de A5, y ninguno se puede tomar sin estos datos.

> **Resultado (23-sep, 1 rep, golden v1): 46,7 % (7/15).** Honestidad 5/5,
> multi 2/5, multi_temporal 0/5; latencia 36 s (no 70); 1,65 ¢.
>
> - **Acerté el número por la razón equivocada.** De los 8 fallos, **5 son
>   del golden, no del agente**: gY-008, 009, 011, 013 y 014 tienen el
>   razonamiento correcto en `respuesta` (99,27 pp; 146,44 % frente a 22,70 %;
>   128,16 %…) y ponen en `cifra` el valor XBRL de la ganadora. Es exactamente
>   lo que manda el prompt desde A1 («`cifra` = valor del ejercicio más
>   reciente; la variación va en `respuesta`»), alineado con el golden del
>   profesor. El golden adversario pedía otra convención que el agente nunca
>   recibió. Error de diseño mío: no contrasté la convención con el prompt.
> - El mecanismo tampoco fue el predicho: el verificador no llegó a actuar
>   (`% corrigió cifra` = 0 %); lo hizo el prompt antes.
> - **2 fallos reales, los predichos**: gY-012 y gY-015 agotan el límite de 8.
>   El modelo ya pide los datos en paralelo (6 llamadas por turno en gY-015):
>   el problema es que el límite cuenta llamadas, no turnos.
> - **1 etiqueta discutible**: gY-010 responde bien en el texto pero marca
>   `fuente='ninguna'` en todo. Honestidad de más, no de menos.
> - La trampa de gY-002 no llegó a probarse: el agente no buscó en texto.
> - Latencia: 25 s de media sin búsquedas de texto, 59 s con ellas.
>
> **Re-puntuado con el golden v2** (mismos JSON crudos, sin volver a llamar al
> agente): **86,7 % (13/15)**. Los dos fallos que quedan son los del límite.

---

## Golden adversario v2 (18 preguntas) · la escalera entera

**Qué cambia en el golden (v2).** Se registra aparte y el 46,7 % de arriba se
mantiene como el resultado v1:

- `cifras_aceptables` en las 7 preguntas multi-entidad con magnitud derivada:
  vale la magnitud (el diferencial, el margen…) **o** el valor XBRL de la
  ganadora, que es lo que manda el prompt. Se aceptan las dos porque las dos
  son defendibles; lo que no se acepta es una cifra de la compañía perdedora.
- gY-010 acepta `fuente` `xbrl` o `ninguna` (honestidad parcial).
- **Tres preguntas nuevas con la cifra SOLO en texto (Item 7A)**, que el golden
  original no tiene (allí toda cifra es un hecho XBRL):
  - gY-016 · multi · Alphabet frente a Meta, pérdida ante −10 % en acciones
    cotizadas (631 M frente a 599 M).
  - gY-017 · multi_temporal · la misma magnitud, 2 compañías × 2 ejercicios
    (Meta 123 → 599 M; Alphabet 508 → 631 M): cuatro búsquedas.
  - gY-018 · multi_temporal · Apple, las dos medidas de riesgo del Item 7A
    (VaR de divisas 538 → 590 M; sensibilidad a +100 pb 2.755 → 2.416 M).
    Pensada para `read_section`, sin exigirla: `search_filings` con item='7A'
    es igual de válido y la trayectoria no debe castigar al agente eficiente.

**La hipótesis que prueban las tres nuevas.** El verificador de cifras de A1
compara **toda** `cifra` con los hechos XBRL de esa compañía y ejercicio, aunque
`fuente='texto'`. 631 M no es un hecho XBRL de GOOGL, así que lo rechazará y le
dirá al modelo que use un valor XBRL o `fuente='ninguna'`. Es un bug latente que
el golden original no puede ver. Si se confirma, afecta a cualquier pregunta a
ciegas de clase con una cifra del MD&A o del 7A.

**Predicciones (1 repetición, 18 preguntas; cada pregunta = 5,6 pp):**

| | acierto | honestidad (5) | multi (6) | multi_temporal (7) | texto 016-018 |
|---|---|---|---|---|---|
| baseline | 45-65 % | 2-4 | 3-5 | 2-4 | 2-3 |
| a1_guardrails | 60-75 % | 4-5 | 4-5 | 3-4 | 0-2 |
| a2_retrieval | ≈ a1 (±1 pregunta) | | | | |
| a3_hibrido | ≈ a2 (±1 pregunta) | | | | |
| a4_comparativas | 70-85 % | 5 | 5-6 | 4-5 | 1-2 |

Razonamiento:

- **baseline**: sin límites (gY-012 y gY-015 pueden completarse) y sin
  verificador (las tres de texto no se sabotean), pero sin el prompt de
  honestidad. Espero que calcule el margen bruto de Amazon desde el texto
  (gY-001) o dé el FY2023 de NVIDIA. Puede **ganar a A1-A4 en las de límite y
  en las de texto**: sería la prueba de que dos guardrails de A1 tienen coste.
- **a1**: la honestidad sube; gY-012 y gY-015 caen por el límite; en 016-018
  el verificador salta (`corrigió cifra` = True) y predigo que el modelo cede
  en al menos una.
- **a2/a3**: el cambio es de retrieval y aquí solo 4 preguntas dependen de él.
  Diferencias de ±1 pregunta son ruido.
- **a4**: 13/15 re-puntuado + 1-2 de las nuevas.

> **Resultado (23-sep, 1 rep, 18 preguntas):**
>
> | | acierto | honestidad | multi | multi_temporal | texto 016-018 | coste | latencia |
> |---|---|---|---|---|---|---|---|
> | baseline | 61,1 % | 3/5 | 4/6 | 3/7 | 0/3 | 1,46 ¢ | 23 s |
> | a1_guardrails | 72,2 % | 5/5 | 5/6 | 3/7 | 0/3 | 1,77 ¢ | 25 s |
> | a2_retrieval | 72,2 % | 5/5 | 5/6 | 3/7 | 0/3 | 1,75 ¢ | 35 s |
> | a3_hibrido | 66,7 %* | 5/5 | 4/6 | 3/7 | 0/3 | 1,89 ¢ | 40 s |
> | a4_comparativas | 72,2 % | 5/5 | 5/6 | 3/7 | 0/3 | 1,89 ¢ | 39 s |
>
> \* gY-008 en A3 es un turno vacío (sin respuesta), no un fallo de razonamiento: se repara solo al volver a correr.
>
> - **Los números globales caen dentro de lo predicho en las cinco arquitecturas.** De A1 a A4
>   no se mueve nada: la escalera en este golden es «A1 y ya». A2-A4 atacaban la búsqueda y la
>   cita de texto, que aquí no es lo que falla (el ancla aparece en la trayectoria de las 4
>   preguntas con ancla en las cinco arquitecturas).
> - **Texto (016-018): 0/3 en todas, y el mecanismo NO es el predicho.** El verificador no se
>   disparó nunca. En A1-A4 las 12 respuestas son correctas en prosa y citan el fragmento
>   exacto (`cita` = 100 %), pero dejan `cifra=null`: el prompt de A1 dice que `cifra` solo sale
>   de `get_xbrl_fact`, y el modelo obedece. El prompt vuelve a actuar antes que el middleware
>   (igual que en la v1). El baseline, que no tiene esa regla, sí da la cifra, pero **en millones**
>   (476 y 590 en vez de 476.000.000 y 590.000.000) y en gY-016 cita dos `chunk_id` a la vez.
>   Conclusión: **ninguna arquitectura tiene contrato para una cifra que sale del texto.** El
>   bug del verificador sigue latente: no ha llegado a probarse porque el prompt lo tapa.
> - **Honestidad: predicción del baseline equivocada.** Esperaba que calculara el margen bruto de
>   Amazon. No lo hizo: en gY-001 y gY-010 la respuesta del baseline es honesta en prosa («no se
>   realiza una estimación»), pero etiqueta `fuente='texto'`/`'ambas'`. Lo que A1 aporta en
>   honestidad es **la etiqueta coherente**, no evitar que el modelo invente: no inventa ni sin
>   guardrails.
> - **El límite, confirmado como coste**: el baseline, sin límite, acierta gY-015 (13 llamadas);
>   A1-A4 la pierden. gY-012 falla en las cinco (en el baseline por dejar `cifra=null` con
>   `fuente='xbrl'`, que el esquema estricto habría rechazado).
> - `read_section` se usó 3 veces (A2 en 017 y 018, A3 en 018) y es lo más lento de la
>   ejecución: 112 s y 128 s en gY-018, frente a 46 s en A4, que resolvió con una búsqueda.
> - Coste casi plano (1,5-1,9 ¢). La latencia es la que paga cada peldaño: 23 → 39 s aquí y
>   20 → 49 s en el original.


---

## Segunda escalera · A5, A6 y A7 (escrita el 23-sep, ANTES de ejecutar)

Cada peldaño ataca un fallo **medido** en el golden difícil v2, y cada uno cambia
una sola cosa sobre el anterior (hay un test que lo exige). `final` sigue siendo
A4 hasta que las tres estén medidas en los dos golden.

| | cambio | fallo que ataca |
|---|---|---|
| **A5** `a5_limites` | techo por herramienta: XBRL 16, búsqueda 6, `read_section` 1 (global 24 como red) | gY-012 y gY-015: el límite de 8 contaba llamadas y el modelo ya pide 6 datos XBRL por turno |
| **A6** `a6_reescritura_rapida` | la misma reescritura, con `reasoning={"effort": "minimal"}` y caché propia | la latencia: en A2 cada reescritura costó ~11 s (17,1 → 29,4 s con ~1 búsqueda por pregunta) |
| **A7** `a7_cifras_texto` | prompt con contrato para cifras de texto (unidades completas, cifra dentro de la cita, un solo `chunk_id`) + verificador que las comprueba contra la cita y no contra XBRL | gY-016..018: bien en prosa en las 12 ejecuciones de A1-A4, `cifra=null` por contrato |

**Predicciones (golden difícil: 1 rep × 18; original: 1 rep × 20 como regresión):**

- **A5**: difícil **72,2 % → 83,3 %** (gY-012 y gY-015 pasan; 016-018 siguen fallando).
  `% límite alcanzado` → 0 %. Latencia de esas dos preguntas algo mayor, media casi
  igual. Original: igual que A4 (19-20 de 20). Confianza alta.
- **A6**: acierto igual que A5 (±1 pregunta) en los dos golden. **Latencia −20 a
  −30 %**: ~49 → 35-40 s en el original y ~39 → 28-33 s en el difícil, si el
  proveedor respeta `minimal` (la caché lo apunta en `razonamiento`). Riesgo que
  preocupa al equipo, la precisión: se mide aparte y gratis con
  `recall_de_trazas("a4_comparativas")`, que ahora incluye «reescritura rápida +
  híbrido» con las consultas reales del agente. Predicción: recall igual ±1 ancla.
  Confianza media-baja en el tamaño del ahorro, alta en que el acierto no cae.
- **A7**: difícil **83,3 % → 94-100 %** (016-018 pasan; como mucho una falla por
  escala o cita). El riesgo es la honestidad: gY-002 (el revenue de FY2023 SÍ está
  en una tabla del texto) podría empezar a responderse con `fuente='texto'`. El
  prompt lo prohíbe explícitamente para partidas contables; predigo que aguanta.
  Original: igual (ninguna pregunta del original tiene cifra de texto).
  `% corrigió cifra` > 0 solo si el modelo pone la cifra en millones.

> **Actualización ANTES de ejecutar (23-sep): A6 descartada por una prueba de humo.**
> Reescritura con razonamiento `minimal` frente a la normal, en caliente y con
> consultas nuevas (sin caché): 12,0 · 7,3 · 19,5 s (media 12,9 s) frente a
> 14,5 · 9,0 · 15,0 s (media 12,8 s). El proveedor acepta `minimal`, pero no
> baja nada: lo que cuesta es la ida y vuelta, no el razonamiento. La predicción
> de A6 (−20 a −30 % de latencia) queda **refutada sin gastar la ejecución**.
> Consecuencias: A6 sale de la escalera (se conserva como `x_reescritura_rapida`,
> sin registrar) y **A7 pasa a llamarse A6 y se monta directamente sobre A5**. Sus
> predicciones se mantienen sin cambios (difícil 83,3 % → 94-100 %, original igual):
> el peldaño retirado no cambiaba nada, así que la base es equivalente.
> La latencia sigue abierta; la palanca real sería un modelo más rápido para la
> reescritura, o quitarla (A2 ya mostró que no mueve el acierto).

> **Resultado (23-sep, 1 rep en cada golden):**
>
> | | difícil (18) | original (20) | latencia dif. / orig. | coste dif. / orig. |
> |---|---|---|---|---|
> | A4 (referencia) | 72,2 % | 96,7 % (3 reps) | 39 s / 49 s | 1,89 ¢ / 1,52 ¢ |
> | **A5** límite por herramienta | **83,3 %** | 95,0 %* | 54 s / 52 s | 2,35 ¢ / 1,44 ¢ |
> | **A6** cifras de texto | **88,9 %**† | **100 %** | 45 s / 39 s | 2,13 ¢ / 1,86 ¢ |
>
> \* El único fallo de A5 en el original (gX-019) es un turno vacío, no un error de razonamiento.
> † Uno de sus dos fallos (gY-011) también es un turno vacío.
>
> - **A5 cumple la predicción exacta**: 83,3 % en el difícil; recupera gY-012 y gY-015;
>   `% límite alcanzado` = 0 %. Original sin regresión (el único fallo es un turno vacío).
>   Latencia: predije «casi igual» y en el difícil sube de 39 a 54 s. Las preguntas del
>   límite ahora llegan hasta el final, con más llamadas, en lugar de cortarse.
> - **A6 cumple a medias**: recupera las tres de cifras de texto (gY-016..018) y la
>   honestidad aguanta (gY-002, el FY2023 de la tabla, sigue siendo `fuente='ninguna'`),
>   pero se queda en 88,9 %, por debajo del 94-100 % predicho:
>   - gY-011 es un turno vacío (se repara solo al volver a correr).
>   - **gY-009 es una regresión real y la causa el prompt nuevo**: el agente pide a XBRL un
>     concepto `OperatingMargin`, le dicen que no está reportado, y aplica la regla «si una
>     partida no está reportada, fuente='ninguna'» a un ratio que se CALCULA con dos
>     partidas que sí están (OperatingIncomeLoss / ingresos). En A5 lo calculaba bien
>     (62,42 %). La lista de partidas contables del prompt incluye «margen bruto», y el
>     modelo generaliza a «margen operativo». Una sola repetición: posible, no seguro, que
>     sea sistemático. Arreglo candidato, sin medir: decir en el prompt que un ratio entre
>     partidas XBRL se calcula, no se da por no reportado.
> - En el original, A6 da 20 de 20 con 1 repetición. Es compatible con el 96,7 % de A4
>   (3 reps): con 20 preguntas, una pregunta son 5 pp.
> - La latencia de A6 sale menor que la de A5 en los dos golden (45 frente a 54 s; 39
>   frente a 52 s). No lo atribuyo a nada: con 1 repetición y la dispersión del
>   proveedor (7-19 s por llamada) es ruido hasta que se demuestre lo contrario.

---

## Decisión · `final` = A6 (24-sep)

Con la reconciliación del 23-sep (turnos vacíos repetidos) las cifras vigentes son:
A6 100 % en el original (1 rep) y **94,4 %** en el difícil, frente al 72,2 % de A4.
La condición que se puso para cambiar `final` —A5 y A6 medidas en los dos golden—
está cumplida, así que `ARQUITECTURAS["final"]` pasa de A4 a **A6**.

Lo que se asume al elegirla, dicho antes de las preguntas ciegas:
- Sin regresión en el original, pero con 1 repetición frente a las 3 de A4.
- gY-009 (un ratio que se calcula, no se reporta) sigue abierto (bug 33): una
  pregunta ciega de márgenes operativos podría caer en `fuente='ninguna'`.
- Latencia ~39-47 s por pregunta (A4: 39-48 s): ~7-8 minutos para 10 preguntas.

