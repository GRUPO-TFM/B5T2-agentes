| arquitectura | reps | acierto | acierto honestidad | acierto multi | acierto multi_temporal | cita | cifra | trayectoria | honestidad | coste medio (¢) | latencia media (s) | llamadas/pregunta | % fuente=ninguna |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 1 | 61.1% | 80.0% | 66.7% | **42.9%** | 50.0% | **76.9%** | **100.0%** | 66.7% | **1.46** | **23.34** | 5.50 | 22.2% |
| a1_guardrails | 1 | **72.2%** | **100.0%** | **83.3%** | **42.9%** | **100.0%** | 58.3% | **100.0%** | **100.0%** | 1.77 | 25.43 | **5.06** | 44.4% |
| a2_retrieval | 1 | **72.2%** | **100.0%** | **83.3%** | **42.9%** | **100.0%** | 58.3% | **100.0%** | **100.0%** | 1.75 | 34.73 | **5.06** | 44.4% |
| a3_hibrido | 1 | 66.7% | **100.0%** | 66.7% | **42.9%** | **100.0%** | 50.0% | **100.0%** | **100.0%** | 1.89 | 40.38 | 5.28 | 44.4% |
| a4_comparativas | 1 | **72.2%** | **100.0%** | **83.3%** | **42.9%** | **100.0%** | 58.3% | **100.0%** | **100.0%** | 1.89 | 39.13 | 5.17 | 44.4% |

Media de las repeticiones. Mejor valor de cada columna en negrita. recall@5 sobre las preguntas con ancla, con los filtros del golden set. Coste y latencia por pregunta.