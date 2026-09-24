# Reconciliación de resultados · 2026-09-24 17:53

Todo re-puntuado con el golden y los evaluadores ACTUALES, sin repetir las preguntas del agente. El recall puede usar el modelo si falta una consulta reescrita en la caché.

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

| arquitectura | original · reps | original · acierto | original · cita | original · cifra | original · trayectoria | original · honestidad | original · recall@5 | original · coste medio (¢) | original · latencia media (s) | original · llamadas/pregunta | original · % límite alcanzado | dificil · reps | dificil · acierto | dificil · cita | dificil · cifra | dificil · trayectoria | dificil · honestidad | dificil · recall@5 | dificil · coste medio (¢) | dificil · latencia media (s) | dificil · llamadas/pregunta | dificil · % límite alcanzado |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 3 | 63.3% | 54.8% | 50.0% | 83.3% | — | 50.0% | 1.64 | 20.3 | 3.95 | 0.0% | 1 | 61.1% | 50.0% | 76.9% | 100.0% | 66.7% | 75.0% | 1.46 | 23.3 | 5.50 | 0.0% |
| a1_guardrails | 3 | 75.0% | 64.3% | 100.0% | 75.0% | — | 50.0% | 1.41 | 17.1 | 3.25 | 3.3% | 1 | 72.2% | 100.0% | 58.3% | 100.0% | 100.0% | 75.0% | 1.77 | 25.4 | 5.06 | 16.7% |
| a2_retrieval | 3 | 75.0% | 64.3% | 100.0% | 76.7% | — | 64.3% | 1.44 | 29.4 | 3.48 | 3.3% | 1 | 72.2% | 100.0% | 58.3% | 100.0% | 100.0% | 100.0% | 1.75 | 34.7 | 5.06 | 22.2% |
| a3_hibrido | 3 | 76.7% | 66.7% | 100.0% | 76.7% | — | 85.7% | 1.40 | 23.9 | 3.60 | 5.0% | 1 | 72.2% | 100.0% | 58.3% | 100.0% | 100.0% | 100.0% | 1.91 | 39.9 | 5.28 | 11.1% |
| a4_comparativas | 3 | 100.0% | 100.0% | 100.0% | 100.0% | — | 85.7% | 1.59 | 48.3 | 3.63 | 3.3% | 1 | 72.2% | 100.0% | 58.3% | 100.0% | 100.0% | 100.0% | 1.89 | 39.1 | 5.17 | 16.7% |
| a5_limites | 1 | 100.0% | 100.0% | 100.0% | 100.0% | — | 85.7% | 1.47 | 49.7 | 3.45 | 0.0% | 1 | 83.3% | 100.0% | 75.0% | 100.0% | 100.0% | 100.0% | 2.34 | 53.7 | 5.39 | 0.0% |
| a6_cifras_texto | 1 | 100.0% | 100.0% | 100.0% | 100.0% | — | 85.7% | 1.86 | 39.4 | 3.20 | 0.0% | 1 | 94.4% | 100.0% | 91.7% | 100.0% | 100.0% | 100.0% | 2.25 | 46.6 | 5.22 | 0.0% |

Cada golden se lee por separado: no se promedian. El original es la regresión (una mejora no puede empeorarlo); el difícil mide capacidad. Con 18 preguntas y 1 repetición, cada pregunta vale 5,6 pp.

## Golden original: baseline frente a final (a6_cifras_texto)

| arquitectura | reps | acierto | acierto numerica | acierto extractiva | acierto comparativa | recall@5 | coste medio (¢) | latencia media (s) | llamadas/pregunta |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 3 | 63.3% | **100.0%** | **100.0%** | 8.3% | 50.0% | **1.64** | **20.33** | 3.95 |
| final | 1 | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **85.7%** | 1.86 | 39.35 | **3.20** |

Media de las repeticiones. Aciertos por familia en porcentaje. Recall@5 sobre las preguntas con ancla del golden; coste, latencia y llamadas por pregunta. Mejor valor de cada columna en negrita (los empates se remarcan en ambas filas).

## Golden dificil: baseline frente a final (a6_cifras_texto)

| arquitectura | reps | acierto | acierto honestidad | acierto multi | acierto multi_temporal | recall@5 | coste medio (¢) | latencia media (s) | llamadas/pregunta |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 1 | 61.1% | 80.0% | 66.7% | 42.9% | 75.0% | **1.46** | **23.34** | 5.50 |
| final | 1 | **94.4%** | **100.0%** | **83.3%** | **100.0%** | **100.0%** | 2.25 | 46.59 | **5.22** |

Media de las repeticiones. Aciertos por familia en porcentaje. Recall@5 sobre las preguntas con ancla del golden; coste, latencia y llamadas por pregunta. Mejor valor de cada columna en negrita (los empates se remarcan en ambas filas).
