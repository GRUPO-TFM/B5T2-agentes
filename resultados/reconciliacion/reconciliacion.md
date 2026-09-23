# Reconciliación de resultados · 2026-09-23 23:12

Todo re-puntuado con el golden y los evaluadores ACTUALES, sin llamar al agente.

## Estado por golden, arquitectura y repetición

| golden | arquitectura | rep | hechas | faltan | reparables | obsoletas | desde | hasta | config cambiada |
|---|---|---|---|---|---|---|---|---|---|
| original | baseline | 1 | 20/20 | 0 | 0 | 0 | 2026-09-23T17:21 | 2026-09-23T17:21 | — |
| original | baseline | 2 | 20/20 | 0 | 0 | 0 | 2026-09-23T17:21 | 2026-09-23T23:06 | — |
| original | baseline | 3 | 20/20 | 0 | 0 | 0 | 2026-09-23T17:21 | 2026-09-23T17:21 | — |
| original | a1_guardrails | 1 | 20/20 | 0 | 0 | 0 | 2026-09-23T17:21 | 2026-09-23T17:21 | — |
| original | a1_guardrails | 2 | 20/20 | 0 | 0 | 0 | 2026-09-23T17:21 | 2026-09-23T17:21 | — |
| original | a1_guardrails | 3 | 20/20 | 0 | 0 | 0 | 2026-09-23T17:21 | 2026-09-23T17:21 | — |
| original | a2_retrieval | 1 | 20/20 | 0 | 0 | 0 | 2026-09-23T17:21 | 2026-09-23T17:21 | — |
| original | a2_retrieval | 2 | 20/20 | 0 | 0 | 0 | 2026-09-23T17:21 | 2026-09-23T17:21 | — |
| original | a2_retrieval | 3 | 20/20 | 0 | 0 | 0 | 2026-09-23T17:21 | 2026-09-23T17:21 | — |
| original | a3_hibrido | 1 | 20/20 | 0 | 0 | 0 | 2026-09-23T22:41 | 2026-09-23T22:47 | — |
| original | a3_hibrido | 2 | 20/20 | 0 | 0 | 0 | 2026-09-23T22:48 | 2026-09-23T22:55 | — |
| original | a3_hibrido | 3 | 20/20 | 0 | 0 | 0 | 2026-09-23T22:56 | 2026-09-23T23:04 | — |
| original | a4_comparativas | 1 | 20/20 | 0 | 0 | 0 | 2026-09-23T17:21 | 2026-09-23T23:07 | — |
| original | a4_comparativas | 2 | 20/20 | 0 | 0 | 0 | 2026-09-23T17:21 | 2026-09-23T17:21 | — |
| original | a4_comparativas | 3 | 20/20 | 0 | 0 | 0 | 2026-09-23T17:21 | 2026-09-23T23:08 | — |
| original | a5_limites | 1 | 20/20 | 0 | 0 | 0 | 2026-09-23T19:15 | 2026-09-23T23:09 | — |
| original | a6_cifras_texto | 1 | 20/20 | 0 | 0 | 0 | 2026-09-23T19:33 | 2026-09-23T19:46 | — |
| dificil | baseline | 1 | 18/18 | 0 | 0 | 0 | 2026-09-23T16:57 | 2026-09-23T17:04 | — |
| dificil | a1_guardrails | 1 | 18/18 | 0 | 0 | 0 | 2026-09-23T17:05 | 2026-09-23T17:12 | — |
| dificil | a2_retrieval | 1 | 18/18 | 0 | 0 | 0 | 2026-09-23T17:13 | 2026-09-23T17:21 | — |
| dificil | a3_hibrido | 1 | 18/18 | 0 | 0 | 0 | 2026-09-23T17:23 | 2026-09-23T23:09 | — |
| dificil | a4_comparativas | 1 | 18/18 | 0 | 0 | 0 | 2026-09-23T17:36 | 2026-09-23T22:10 | — |
| dificil | a5_limites | 1 | 18/18 | 0 | 0 | 0 | 2026-09-23T18:42 | 2026-09-23T18:56 | — |
| dificil | a6_cifras_texto | 1 | 18/18 | 0 | 0 | 0 | 2026-09-23T18:59 | 2026-09-23T23:10 | — |

## Pendiente

Nada: todas las arquitecturas ejecutadas están completas.

## Las dos tablas, lado a lado

| arquitectura | original · reps | original · acierto | original · cita | original · cifra | original · trayectoria | original · honestidad | original · coste medio (¢) | original · latencia media (s) | original · % límite alcanzado | dificil · reps | dificil · acierto | dificil · cita | dificil · cifra | dificil · trayectoria | dificil · honestidad | dificil · coste medio (¢) | dificil · latencia media (s) | dificil · % límite alcanzado |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 3 | 63.3% | 54.8% | 50.0% | 83.3% | — | 1.64 | 20.3 | 0.0% | 1 | 61.1% | 50.0% | 76.9% | 100.0% | 66.7% | 1.46 | 23.3 | 0.0% |
| a1_guardrails | 3 | 75.0% | 64.3% | 100.0% | 75.0% | — | 1.41 | 17.1 | 3.3% | 1 | 72.2% | 100.0% | 58.3% | 100.0% | 100.0% | 1.77 | 25.4 | 16.7% |
| a2_retrieval | 3 | 75.0% | 64.3% | 100.0% | 76.7% | — | 1.44 | 29.4 | 3.3% | 1 | 72.2% | 100.0% | 58.3% | 100.0% | 100.0% | 1.75 | 34.7 | 22.2% |
| a3_hibrido | 3 | 76.7% | 66.7% | 100.0% | 76.7% | — | 1.40 | 23.9 | 5.0% | 1 | 72.2% | 100.0% | 58.3% | 100.0% | 100.0% | 1.91 | 39.9 | 11.1% |
| a4_comparativas | 3 | 100.0% | 100.0% | 100.0% | 100.0% | — | 1.59 | 48.3 | 3.3% | 1 | 72.2% | 100.0% | 58.3% | 100.0% | 100.0% | 1.89 | 39.1 | 16.7% |
| a5_limites | 1 | 100.0% | 100.0% | 100.0% | 100.0% | — | 1.47 | 49.7 | 0.0% | 1 | 83.3% | 100.0% | 75.0% | 100.0% | 100.0% | 2.34 | 53.7 | 0.0% |
| a6_cifras_texto | 1 | 100.0% | 100.0% | 100.0% | 100.0% | — | 1.86 | 39.4 | 0.0% | 1 | 94.4% | 100.0% | 91.7% | 100.0% | 100.0% | 2.25 | 46.6 | 0.0% |

Cada golden se lee por separado: no se promedian. El original es la regresión (una mejora no puede empeorarlo); el difícil mide capacidad. Con 18 preguntas y 1 repetición, cada pregunta vale 5,6 pp.
