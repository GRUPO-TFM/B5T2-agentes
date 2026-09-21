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

> Resultado: _(pendiente)_

---

## A2 · `a2_retrieval` — corrección de una predicción anterior

En el diseño inicial se afirmó que la ganancia de A2 vendría de **forzar los
filtros de metadatos**. Los datos del baseline lo desmienten: de las 81 búsquedas
ejecutadas, **el 100 % ya llevaba `ticker` y el 94 % ya llevaba `item`**. El margen
de `forzar_filtros` es casi nulo. La ganancia de A2, si la hay, tiene que venir de
la **reescritura de la consulta a inglés**, que en la tabla de recall sube de 7/14
a 9/14 por sí sola.

Queda anotado como error de predicción, no corregido a posteriori.
