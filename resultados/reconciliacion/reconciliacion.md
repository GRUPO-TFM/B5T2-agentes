# Reconciliación de resultados · 2026-09-23 17:40

Todo re-puntuado con el golden y los evaluadores ACTUALES, sin llamar al agente.

## Estado por golden, arquitectura y repetición

| golden | arquitectura | rep | hechas | faltan | reparables | obsoletas | desde | hasta | config cambiada |
|---|---|---|---|---|---|---|---|---|---|
| original | baseline | 1 | 20/20 | 0 | 0 | 0 | 2026-09-22T00:38 | 2026-09-22T00:45 | — |
| original | baseline | 2 | 19/20 | 0 | 1 | 0 | 2026-09-22T00:45 | 2026-09-22T00:51 | — |
| original | baseline | 3 | 20/20 | 0 | 0 | 0 | 2026-09-22T00:51 | 2026-09-22T00:58 | — |
| original | a1_guardrails | 1 | 20/20 | 0 | 0 | 0 | 2026-09-22T01:39 | 2026-09-22T09:51 | — |
| original | a1_guardrails | 2 | 20/20 | 0 | 0 | 0 | 2026-09-22T01:44 | 2026-09-22T09:52 | — |
| original | a1_guardrails | 3 | 20/20 | 0 | 0 | 0 | 2026-09-22T01:49 | 2026-09-22T09:53 | — |
| original | a2_retrieval | 1 | 20/20 | 0 | 0 | 0 | 2026-09-22T12:16 | 2026-09-22T12:25 | — |
| original | a2_retrieval | 2 | 20/20 | 0 | 0 | 0 | 2026-09-22T12:25 | 2026-09-22T12:35 | — |
| original | a2_retrieval | 3 | 20/20 | 0 | 0 | 0 | 2026-09-22T12:35 | 2026-09-22T12:45 | — |
| original | a3_hibrido | 1 | 0/20 | 20 | 0 | 0 |  |  | — |
| original | a4_comparativas | 1 | 19/20 | 0 | 1 | 0 | 2026-09-22T15:12 | 2026-09-22T15:27 | — |
| original | a4_comparativas | 2 | 20/20 | 0 | 0 | 0 | 2026-09-22T15:27 | 2026-09-22T15:44 | — |
| original | a4_comparativas | 3 | 19/20 | 0 | 1 | 0 | 2026-09-22T15:45 | 2026-09-22T16:03 | — |
| dificil | baseline | 1 | 18/18 | 0 | 0 | 0 | 2026-09-23T16:57 | 2026-09-23T17:04 | — |
| dificil | a1_guardrails | 1 | 18/18 | 0 | 0 | 0 | 2026-09-23T17:05 | 2026-09-23T17:12 | — |
| dificil | a2_retrieval | 1 | 18/18 | 0 | 0 | 0 | 2026-09-23T17:13 | 2026-09-23T17:21 | — |
| dificil | a3_hibrido | 1 | 17/18 | 0 | 1 | 0 | 2026-09-23T17:23 | 2026-09-23T17:33 | — |
| dificil | a4_comparativas | 1 | 18/18 | 0 | 0 | 0 | 2026-09-23T14:46 | 2026-09-23T17:38 | — |

## Pendiente

- **original · baseline · rep2**: sin respuesta (se repiten solas al volver a correr) gX-007
- **original · a3_hibrido · rep1**: no ejecutada
- **original · a4_comparativas · rep1**: sin respuesta (se repiten solas al volver a correr) gX-009
- **original · a4_comparativas · rep3**: sin respuesta (se repiten solas al volver a correr) gX-018
- **dificil · a3_hibrido · rep1**: sin respuesta (se repiten solas al volver a correr) gY-008

## Las dos tablas, lado a lado

| arquitectura | original · reps | original · acierto | original · cita | original · cifra | original · trayectoria | original · honestidad | original · coste medio (¢) | original · latencia media (s) | original · % límite alcanzado | dificil · reps | dificil · acierto | dificil · cita | dificil · cifra | dificil · trayectoria | dificil · honestidad | dificil · coste medio (¢) | dificil · latencia media (s) | dificil · % límite alcanzado |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 3 | 61.7% | 52.4% | 50.0% | 83.3% | — | 1.62 | 20.3 | 0.0% | 1 | 61.1% | 50.0% | 76.9% | 100.0% | 66.7% | 1.46 | 23.3 | 0.0% |
| a1_guardrails | 3 | 75.0% | 64.3% | 100.0% | 75.0% | — | 1.41 | 17.1 | 3.3% | 1 | 72.2% | 100.0% | 58.3% | 100.0% | 100.0% | 1.77 | 25.4 | 16.7% |
| a2_retrieval | 3 | 75.0% | 64.3% | 100.0% | 76.7% | — | 1.44 | 29.4 | 3.3% | 1 | 72.2% | 100.0% | 58.3% | 100.0% | 100.0% | 1.75 | 34.7 | 22.2% |
| a3_hibrido | — | — | — | — | — | — | — | — | — | 1 | 66.7% | 100.0% | 50.0% | 100.0% | 100.0% | 1.89 | 40.4 | 11.1% |
| a4_comparativas | 3 | 96.7% | 95.2% | 97.6% | 100.0% | — | 1.52 | 49.2 | 3.3% | 1 | 72.2% | 100.0% | 58.3% | 100.0% | 100.0% | 1.89 | 39.1 | 16.7% |

Cada golden se lee por separado: no se promedian. El original es la regresión (una mejora no puede empeorarlo); el difícil mide capacidad. Con 18 preguntas y 1 repetición, cada pregunta vale 5,6 pp.
