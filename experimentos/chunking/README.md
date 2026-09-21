# Experimento de chunking sobre el corpus 10-K

Compara estrategias de troceado de bajo coste que mejoren la coherencia de
los fragmentos y el trato de las tablas, **aislando el efecto del troceado**.
Las cifras financieras se siguen consultando por XBRL: esto solo afecta al
retrieval textual.

Todo lo que hay aquí se regenera con código. Ninguna cifra de este documento
está escrita a mano: salen de `resultados/`, que produce
`experimentos.chunking.tabla`.

---

## 1. La conclusión, primero

**El idioma de la consulta tapaba el efecto del troceado.** Es el resultado
principal, y justifica por sí solo que §4 pidiera medir en dos modos.

Con la **pregunta original en español**, las cinco variantes son
indistinguibles: A, A′, B, C y D aciertan exactamente las mismas 8 de 14
preguntas. Con la **misma pregunta reescrita al inglés** —una sola llamada
al LLM, cacheada, idéntica para todas las variantes— se separan:

| Variante | Original, con filtro | Reescrita, con filtro | Reescrita, sin filtro | MRR reescrita |
| --- | ---: | ---: | ---: | ---: |
| Entregado | 7/14 | 9/14 | 4/14 | 0,421 |
| A (reimpl.) | 8/14 | 10/14 | 2/14 | 0,363 |
| A′ (BGE + tope) | 8/14 | 11/14 | 6/14 | 0,473 |
| B (sentence-window) | 8/14 | **12/14** | 7/14 | 0,542 |
| C (table-aware) | 8/14 | 10/14 | 8/14 | 0,536 |
| D (combinada) | 8/14 | 11/14 | **9/14** | **0,605** |

En el modo reescrito, **las cuatro variantes nuevas superan al índice
entregado** en la configuración sin filtro, y todas menos C lo superan con
filtro. El troceado sí importa: lo que pasaba es que el desajuste
español→inglés era tan grande que se lo comía todo.

**Recomendación: D (combinada).** Detalle y matices en §7.

### Lo que mejora sin depender de ninguna métrica de ranking

| | Índice entregado | Mejor variante | |
| --- | ---: | ---: | --- |
| Fragmentos truncados en silencio | 19,9 % | **0 %** | ↓ todo |
| Tablas partidas por una ventana | 4,3 % | **0,9 %** | ↓ 79 % |
| Fragmentos tabulares sin cabecera | 16,4 % | **0,3 %** | ↓ 98 % |
| Tokens en el top-5 (coste de contexto) | 2 093 | **1 773** | ↓ 15 % |

---

## 2. El hallazgo que condicionó todo: dos tokenizadores

El corpus entregado cuenta tokens con **`tiktoken cl100k_base`** (el de los
modelos GPT). Se descubrió por reconstrucción: coincide con el campo
`n_tokens` de `chunks.jsonl` en 60 de 60 fragmentos de una muestra, y
explica 1 063 de las 1 077 decisiones de partición a 500 tokens.

Pero el modelo de embeddings es `BAAI/bge-small-en-v1.5`, que tokeniza con
WordPiece y **trunca la entrada a 512 tokens sin dar ningún error**.

| | media | máx | > 512 |
| --- | ---: | ---: | ---: |
| `n_tokens` (cl100k, el del baseline) | 401,8 | 547 | — |
| Tokens BGE reales | 382,3 | 561 | **308 / 1 749 = 17,6 %** |

**Uno de cada seis fragmentos del índice entregado se embebe cortado.** Es
un error de contabilidad, no de estrategia de troceado, y afecta sobre todo
a la prosa (27,5 % de los fragmentos sin tabla) más que a las tablas (3,5 %).

Por eso el diseño lleva un brazo extra, A′: mide el tokenizador por separado
de la estrategia. Y el efecto es real: A′ le saca 4 puntos de recall a A en
el modo reescrito con filtro (11/14 frente a 10/14) y **el cuádruple sin
filtro** (6/14 frente a 2/14), con el mismo algoritmo de troceado. Lo único
que cambia entre A y A′ es contar bien los tokens.

---

## 3. La puerta de reproducción no se puede pasar (y por qué es un hallazgo)

§3 pedía reimplementar A desde `secciones.jsonl` y obtener 1 749 fragmentos
exactos. **No es alcanzable desde las entradas permitidas.** Lo que sí quedó
establecido, con `reproduccion.py` como prueba ejecutable:

1. **La mecánica del troceado es** partir la sección en bloques por
   encabezado y **ventanear cada bloque por separado** a 500 tokens con
   solape de 80, recortando el espacio en blanco de los bordes. No hay
   empaquetado. La aritmética cuadra exacta: **1 077 bloques + 672 ventanas
   de continuación = 1 749 fragmentos**.
2. Dados los bloques de verdad, esa mecánica reproduce **1 732 de los 1 749
   tramos (99,0 %)**.
3. **Las fronteras de bloque no salen del texto plano.** El **84,4 %** de
   ellas no las explica el tamaño: 624 de 739 cierran el bloque cuando el
   párrafo siguiente cabía de sobra (`475 tok + 13 tok`, `278 + 8`,
   `475 + 3`). Son cortes estructurales.
4. **Venían del marcado HTML.** El **88,6 %** de las fronteras coincide con
   un `<span>` en negrita del informe original, frente al 69 % de los
   párrafos de forma parecida que no son frontera. El corpus se construyó
   desde `fuentes_10k_html.zip`; `secciones.jsonl` conserva el texto pero no
   la marca.

El caso que lo demuestra: *«Risks Related to Our Industry and Markets»* es
frontera cuando es un encabezado real, y **no** lo es cuando el mismo texto
aparece repetido dentro del «Risk Factors Summary». En texto plano son
idénticos; en el HTML, no.

Las 1 029 fronteras son todas párrafos con forma de encabezado (línea ≤ 87
caracteres, sin punto final) — recall del 100 % —, pero hay 3 311 párrafos
así. Ningún filtro adicional probado (viñeta, dos puntos, Title Case,
mayúscula inicial, multilínea, dígitos) tiene cero falsos negativos salvo los
de puntuación, y esos solo quitan 581 de los 2 282 falsos positivos.

**Criterios débiles que sustituyeron a la puerta**, fijados antes de medir
(`puerta.py`):

| Criterio | Resultado | |
| --- | --- | --- |
| Cobertura de anclas en A | 14/14 | OK |
| recall@5 de A a ≤ 1 pregunta del entregado | 8/14 vs 7/14, difiere en `gX-020` | OK |
| Nº de fragmentos dentro del ±2 % de 1 749 | 1 779 (+1,72 %) | OK |

Que A reproduzca también el **defecto** del baseline (19,7 % de fragmentos
por encima de 510 tokens BGE, frente al 19,9 % del entregado) es la mejor
señal de que la reimplementación es fiel.

---

## 4. Diseño

Seis índices. Cada flecha aísla una cosa:

```
Entregado ──► A ──► A′ ──► B, C, D
          (1)    (2)     (3)
```

1. **Entregado ↔ A**: la pérdida por reconstrucción (las fronteras de bloque
   que ya no se pueden recuperar).
2. **A ↔ A′**: el tokenizador y el tope duro. Mismo algoritmo, cl100k→BGE.
3. **A′ ↔ B/C/D**: la estrategia. **B, C y D se comparan contra A′, nunca
   contra A.**

| Variante | Segmentación | Prosa | Tablas | Tokens |
| --- | --- | --- | --- | --- |
| A | encabezados | ventana 500/80 | como la prosa | cl100k |
| A′ | encabezados | ventana 480/80 | como la prosa | BGE |
| B | encabezados | por oraciones | como la prosa | BGE |
| C | encabezados | ventana 480/80 | atómicas, cabecera repetida | BGE |
| D | encabezados | por oraciones | atómicas, cabecera repetida | BGE |

**Constantes en las cinco**: la segmentación por encabezados, el modelo de
embeddings, la normalización L2, `IndexFlatIP`, el prefijo BGE *solo en la
consulta*, los filtros, el golden set y k=5. El tope duro está en 480, por
debajo de los 510 útiles (512 menos `[CLS]` y `[SEP]`).

### Reglas fijadas y documentadas (§3 las exigía explícitas)

- **(a) Encabezado de columnas**: las filas iniciales de la tabla que no
  contienen ninguna *celda numérica* — una celda que sea solo una cifra, con
  `$`, `%`, paréntesis de negativo, comas y decimales. «Jan 28, 2024» lleva
  dígitos pero no es celda numérica, así que una fila de fechas cuenta como
  cabecera, que es lo que se quiere.
- **(b) Contexto de la tabla**: el párrafo inmediatamente anterior si es una
  línea corta sin punto final. Es el «(In millions, except par value)» o el
  «Year Ended» que da sentido a las cifras. Se arrastra con la tabla y se
  repite si la tabla se parte.
- **(c) Tamaño mínimo**: al partir una tabla, las filas se reparten entre
  `ceil(total/tope)` fragmentos igualados, subiendo el número hasta que
  ninguno se pase. Nada de llenar y dejar una cola de 10 tokens. Y una tabla
  que cabe entera nunca se emite sola: se empaqueta con la prosa vecina.

### Offsets y trazabilidad

`inicio_car` y `fin_car` se refieren **siempre al cuerpo** del fragmento
dentro del texto de la sección. La cabecera repetida de una tabla partida no
está en ese tramo: va en el campo `encabezado_repetido` y se antepone al
texto que se embebe. Así ni el matching por tramo ni el evaluador de citas se
descuadran.

---

## 5. Resultados

Tablas completas en [`resultados/comparativa.md`](resultados/comparativa.md),
posición del ancla pregunta a pregunta en
[`resultados/por_pregunta.csv`](resultados/por_pregunta.csv).

### 5.1 Consulta original (español): nada se mueve

| Variante | recall@5 con filtro | MRR | recall@5 sin filtro | Tokens top-5 |
| --- | ---: | ---: | ---: | ---: |
| Entregado | 7/14 | 0,374 | 2/14 | 2 093 |
| A | 8/14 | 0,387 | 2/14 | 1 983 |
| A′ | 8/14 | 0,407 | 3/14 | 1 948 |
| B | 8/14 | 0,413 | 2/14 | 1 888 |
| C | 8/14 | 0,387 | 3/14 | 1 820 |
| D | 8/14 | 0,389 | 3/14 | 1 773 |

**Las cinco aciertan las mismas 8 preguntas.** Respecto a A′: B no cambia
ninguna; C y D ganan `gX-018` y pierden `gX-019`, neto cero. Con la pregunta
en español, el troceado es invisible.

### 5.2 Consulta reescrita al inglés: se separan

| Variante | recall@5 con filtro | MRR | recall@5 sin filtro | MRR | Tokens top-5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Entregado | 9/14 | 0,421 | 4/14 | 0,181 | 1 982 |
| A | 10/14 | 0,363 | 2/14 | 0,099 | 2 036 |
| A′ | 11/14 | 0,473 | 6/14 | 0,212 | 1 918 |
| B | **12/14** | 0,542 | 7/14 | 0,271 | 1 886 |
| C | 10/14 | 0,536 | 8/14 | 0,299 | 1 882 |
| D | 11/14 | **0,605** | **9/14** | **0,347** | 1 856 |

**Qué preguntas mueve cada estrategia** (posición del ancla, con filtro):

| Pregunta | A′ | B | C | D | Qué pasa |
| --- | ---: | ---: | ---: | ---: | --- |
| `gX-010` | 19 | **1** | 19 | **1** | Sentence-window: de la 19 a la 1 |
| `gX-019` | 8 | 8 | **3** | **3** | Table-aware la rescata |
| `gX-018` | 3 | 3 | **1** | **1** | Table-aware la sube |
| `gX-015` | **5** | **5** | 7 | 7 | Table-aware la pierde |
| `gX-016` | **5** | **5** | 10 | 10 | Table-aware la pierde |

B suma exactamente una pregunta sobre A′ (`gX-010`). C suma `gX-019` y
`gX-018` pero pierde `gX-015` y `gX-016`: **neto −1 con filtro, +2 sin
filtro**. D acumula los dos efectos.

### 5.3 Estructura (no depende de embeddings ni del golden set)

| Variante | Chunks | > 510 tok | Cob. oraciones | Tablas partidas | Tabulares sin cabecera |
| --- | ---: | ---: | ---: | ---: | ---: |
| Entregado | 1 749 | 19,9 % | 99,91 % | 4,3 % | 16,4 % |
| A | 1 779 | 19,7 % | 99,93 % | 3,8 % | 12,7 % |
| A′ | 1 756 | 0 % | 99,91 % | 1,6 % | 8,3 % |
| B | 1 774 | 0 % | 99,91 % | 0,9 % | 1,9 % |
| C | 1 718 | 0 % | 99,91 % | 0,9 % | **0,3 %** |
| D | 1 722 | 0 % | 99,91 % | 0,9 % | **0,3 %** |

La cobertura de oraciones se mide sobre **las 15 123 oraciones de prosa del
corpus**, no sobre las 14 anclas. Se queda clavada en 99,91 % en todas.

Esto merece subrayarse porque desmonta la justificación de B sin desmontar a
B: **el solape de 80 tokens ya rescataba el 99,9 % de las oraciones** (solo
13 quedaban partidas en todo el corpus). Si B gana `gX-010`, no es porque
haya dejado de partir oraciones. Es porque un fragmento alineado con
fronteras de oración se embebe mejor: el vector no arrastra media frase
descabezada. El beneficio es real; el mecanismo no era el que se suponía.

### 5.4 Sonda de tablas (diagnóstico aparte, **no** golden set)

Como ninguna ancla del golden set cae en una tabla, el recall@5 no puede ver
lo que C y D arreglan. Cinco preguntas escritas para este experimento con el
ancla en una fila de tabla ([`sonda.md`](resultados/sonda.md)):

| Variante | Cobertura | recall@5 | MRR |
| --- | ---: | ---: | ---: |
| Entregado | 5/5 | 3/5 | 0,198 |
| A | 5/5 | 3/5 | 0,194 |
| A′ | 5/5 | 2/5 | 0,175 |
| B | 5/5 | 2/5 | 0,175 |
| C | 5/5 | **4/5** | 0,212 |
| D | 5/5 | **4/5** | **0,245** |

Es coherente con §5.2, pero **son cinco preguntas: cada una vale 20 puntos.**
Es un indicio, no una prueba, y no entra en la tabla principal.

### 5.5 Ejemplos cualitativos

En [`resultados/ejemplos.md`](resultados/ejemplos.md), localizados por código
y no elegidos a dedo:

- **Tabla**: la de AOCI de Alphabet FY2024 (17 filas). A la parte en dos y el
  segundo fragmento empieza a media palabra — `ifications | ( 1,673 ) | ...`
  — sin cabecera de columnas y sin nada que diga de qué son esas cifras. C la
  deja entera en un fragmento de 441 tokens, con su línea de contexto.
- **Prosa**: una oración de 1 139 caracteres de Meta FY2024 Item 1A que A
  corta por la mitad y B mantiene entera. **Es uno de solo 13 casos en todo
  el corpus**: el ejemplo se ve bien, pero no es lo que mueve la métrica.

---

## 6. Los límites de este experimento

Dicho sin adornos, porque condiciona cuánto se puede concluir:

1. **14 preguntas con ancla.** Cada una vale 7 puntos de recall. La ventaja
   de B sobre D con filtro es **una pregunta**; la de D sobre B sin filtro,
   **dos**. Ninguna de esas ventajas está establecida.
2. **El orden no es estable entre configuraciones.** B es la mejor con
   filtro (12/14) y la tercera sin filtro (7/14). D es la mejor sin filtro
   (9/14) y empata con A′ con filtro (11/14). Quien elija por una sola
   celda de la tabla elegirá mal.
3. **Cobertura saturada de salida.** El baseline ya cubría el 100 % de las
   anclas y el 99,91 % de la prosa. La métrica de cobertura, que era la
   número 1 del enunciado, no podía discriminar nada.
4. **Ninguna ancla en tabla.** El golden set no mide lo que C y D mejoran.
   La sonda tapa el hueco a título de diagnóstico.
5. **La reconstrucción no es idéntica al entregado** (75,8 % de tramos
   idénticos partiendo de `secciones.jsonl`). Por eso la comparación de
   estrategia se hace **A′ ↔ B/C/D** y no contra el entregado.
6. **Una sola reescritura por pregunta, sin validar.** La caché fija la
   consulta para que todas las variantes vean lo mismo, que es lo correcto
   para comparar, pero el nivel absoluto de recall del modo reescrito
   depende de una reescritura que nadie ha revisado.

---

## 7. Recomendación

**D (combinada).** Es la única variante que gana en las dos dimensiones y la
más consistente de las cuatro:

- **Mejor MRR en los dos modos reescritos** (0,605 con filtro, 0,347 sin
  filtro), y el MRR usa el ranking completo, así que es bastante más estable
  que un recall@5 sobre 14 preguntas.
- **Mejor recall sin filtro** (9/14 frente a 4/14 del entregado). La
  configuración sin filtro es la que se parece a una pregunta ciega que no
  trae ticker ni ejercicio: es la del día 24.
- **Corrige el truncado silencioso** (19,9 % → 0 %). Un fragmento que se
  embebe cortado se recupera peor y nadie se entera.
- **Trazabilidad**: 0,3 % de fragmentos tabulares sin cabecera frente al
  16,4 %. Una cita a una fila de tabla sin su cabecera de columnas no es
  verificable, y la verificación de citas es parte del contrato de entrega.
- **El coste de contexto más bajo**: 1 773 tokens en el top-5 frente a los
  2 093 del entregado (−15 %), con más recall.

**Lo que no sostengo**: que D sea mejor que B. Con filtro B acierta una
pregunta más (12 vs 11), y una pregunta es ruido con esta muestra. Elijo D
porque gana en MRR en las dos configuraciones y porque su ventaja sin filtro
(dos preguntas) va en la misma dirección que la sonda de tablas y que las
métricas estructurales, que no dependen del golden set. Es convergencia de
indicios, no significación estadística.

**Si hubiera que elegir una sola cosa**, sería **el tokenizador**: A → A′ es
el salto más grande y más barato de todo el experimento (de 2/14 a 6/14 sin
filtro, de 10/14 a 11/14 con filtro) y no es una estrategia de troceado, es
arreglar una contabilidad mal hecha.

---

## 8. Cómo reproducirlo

```bash
uv sync --frozen                                      # incluye el grupo `experimentos`
uv run python -m experimentos.chunking.reproduccion   # la puerta: qué se reproduce y qué no
uv run python -m experimentos.chunking.construir      # los cinco índices
uv run python -m experimentos.chunking.puerta         # criterios débiles sobre A
uv run python -m experimentos.chunking.consultas      # caché de consultas (única llamada al LLM)
uv run python -m experimentos.chunking.tabla          # comparativa.md y por_pregunta.csv
uv run python -m experimentos.chunking.ejemplos       # ejemplos.md
uv run python -m experimentos.chunking.sonda          # sonda.md
```

`consultas.py` es lo único que necesita `OPENROUTER_API_KEY`, hace una
llamada por pregunta y guarda el resultado en `cache_consultas.json`
(versionado). Ninguna variante vuelve a llamar al modelo: las cinco ven la
misma consulta, que es la única forma de que la comparación mida el troceado.

### Qué se versiona y qué no

Se versionan el código, los `manifiesto.json`, las tablas de `resultados/`,
`cache_consultas.json` y `sonda_tablas.jsonl`. **No** se versionan los
artefactos regenerables (`chunks.jsonl`, `embeddings.npy`, `corpus.faiss`,
`chunks_meta.parquet`): están en `.gitignore`.

Cada manifiesto ata el índice a sus fragmentos por SHA-256. Si alguien
regenera `chunks.jsonl` sin regenerar el índice, `construir.cargar()` falla
en vez de devolver texto equivocado en silencio. Además `construir()` aborta
si una variante con tope duro deja algún fragmento por encima del límite del
modelo.

### Lo que este experimento no toca

`corpus/`, `agente/` y `data/`. El baseline congelado queda intacto:
`corpus/chunks.jsonl` sigue en `388ff367…`, el hash de su manifiesto.
