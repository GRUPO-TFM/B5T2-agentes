| arquitectura | reps | acierto | acierto numerica | acierto extractiva | acierto comparativa | cita | cifra | trayectoria | recall@5 | coste medio (¢) | latencia media (s) | llamadas/pregunta | % fuente=ninguna |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 3 | 63.3% | **100.0%** | **100.0%** | 8.3% | 54.8% | 50.0% | 83.3% | 50.0% | 1.64 | 20.33 | 3.95 | 0.0% |
| a1_guardrails | 3 | 75.0% | **100.0%** | **100.0%** | 37.5% | 64.3% | **100.0%** | 75.0% | 50.0% | 1.41 | **17.15** | 3.25 | 0.0% |
| a2_retrieval | 3 | 75.0% | **100.0%** | **100.0%** | 37.5% | 64.3% | **100.0%** | 76.7% | 64.3% | 1.44 | 29.40 | 3.48 | 0.0% |
| a3_hibrido | 3 | 76.7% | **100.0%** | **100.0%** | 41.7% | 66.7% | **100.0%** | 76.7% | **85.7%** | **1.40** | 23.92 | 3.60 | 0.0% |
| a4_comparativas | 3 | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **85.7%** | 1.59 | 48.28 | 3.63 | 0.0% |
| a5_limites | 1 | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **85.7%** | 1.47 | 49.68 | 3.45 | 0.0% |
| a6_cifras_texto | 1 | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **85.7%** | 1.86 | 39.35 | **3.20** | 0.0% |

Media de las repeticiones. Mejor valor de cada columna en negrita. recall@5 sobre las preguntas con ancla, con los filtros del golden set. Coste y latencia por pregunta.