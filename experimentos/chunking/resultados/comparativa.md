# Comparativa de estrategias de troceado

Generado por `experimentos.chunking.tabla` el 2026-09-21.

Golden set: `data/golden_set.jsonl`, SHA-256 `3386db90f9c49d9e5c8a749701939ca41b3d7d21646b6b9ea28b107bd0f2bf1d`, 20 preguntas, 14 con ancla.

## Consulta original, con filtro

| Variante | Chunks | Tok. medios | > 510 tok | Cobertura anclas | Cobertura oraciones | Tablas partidas | Tabulares sin cabecera | recall@5 | MRR | Tokens top-5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Entregado | 1749 | 382 | 19.9 % | 14/14 | 99.91 % | 4.3 % | 16.4 % | 7/14 (50%) | 0.374 | 2093 |
| A (baseline reimpl.) | 1779 | 375 | 19.7 % | 14/14 | 99.93 % | 3.8 % | 12.7 % | 8/14 (57%) | 0.387 | 1983 |
| A′ (BGE + tope) | 1756 | 381 | 0.0 % | 14/14 | 99.91 % | 1.6 % | 8.3 % | 8/14 (57%) | 0.407 | 1948 |
| B (sentence-window) | 1774 | 368 | 0.0 % | 14/14 | 99.91 % | 0.9 % | 1.9 % | 8/14 (57%) | 0.413 | 1888 |
| C (table-aware) | 1718 | 384 | 0.0 % | 14/14 | 99.91 % | 0.9 % | 0.3 % | 8/14 (57%) | 0.387 | 1820 |
| D (combinada) | 1722 | 377 | 0.0 % | 14/14 | 99.91 % | 0.9 % | 0.3 % | 8/14 (57%) | 0.389 | 1773 |

Preguntas que cambian respecto a A′:

- **B**: gana —, pierde —
- **C**: gana ['gX-018'], pierde ['gX-019']
- **D**: gana ['gX-018'], pierde ['gX-019']
- **A frente al entregado**: gana ['gX-020'], pierde —

## Consulta original, sin filtro

| Variante | Chunks | Tok. medios | > 510 tok | Cobertura anclas | Cobertura oraciones | Tablas partidas | Tabulares sin cabecera | recall@5 | MRR | Tokens top-5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Entregado | 1749 | 382 | 19.9 % | 14/14 | 99.91 % | 4.3 % | 16.4 % | 2/14 (14%) | 0.167 | 2009 |
| A (baseline reimpl.) | 1779 | 375 | 19.7 % | 14/14 | 99.93 % | 3.8 % | 12.7 % | 2/14 (14%) | 0.161 | 1694 |
| A′ (BGE + tope) | 1756 | 381 | 0.0 % | 14/14 | 99.91 % | 1.6 % | 8.3 % | 3/14 (21%) | 0.149 | 1860 |
| B (sentence-window) | 1774 | 368 | 0.0 % | 14/14 | 99.91 % | 0.9 % | 1.9 % | 2/14 (14%) | 0.126 | 1729 |
| C (table-aware) | 1718 | 384 | 0.0 % | 14/14 | 99.91 % | 0.9 % | 0.3 % | 3/14 (21%) | 0.125 | 1650 |
| D (combinada) | 1722 | 377 | 0.0 % | 14/14 | 99.91 % | 0.9 % | 0.3 % | 3/14 (21%) | 0.132 | 1602 |
