# B5T2 · Agente investigador sobre informes 10-K

Práctica de **LLMs aplicados a Finanzas · MIAX**: construir y evaluar un agente que responda preguntas sobre informes anuales 10-K de la SEC, con evidencia verificable y control sobre calidad, coste y latencia.

**Estado actual:** prototipo de la sesión 1 desarrollado y ejecutado en un notebook, con herramientas, bucle ReAct y agente con salida estructurada. El repositorio incluye los datos de partida y las salidas de esa ejecución. La evaluación completa de la práctica sigue pendiente.

El [enunciado de la práctica](Practica_LLM_Agente_10K.docx) define la entrega final; este README documenta el avance disponible y los siguientes pasos.

## Qué hay implementado hasta ahora

El punto de entrada es [S1_Herramientas_y_Bucle_Alumno.ipynb](Clase_1/S1_Herramientas_y_Bucle_Alumno.ipynb). Las herramientas y el agente se definen dentro del notebook y requieren ejecutar sus celdas previas.

| Componente | Implementación actual |
| --- | --- |
| Entorno | Python 3.12, dependencias en `pyproject.toml` y versiones resueltas en `uv.lock` |
| Preparación de datos | Localización de los ZIP, verificación de hashes y extracción del corpus y del índice |
| Herramientas | `list_available`, `get_xbrl_fact`, `search_filings` y `read_section`, definidas en el notebook |
| Búsqueda | Búsqueda densa FAISS en `miax_s1.buscar`, con prefijo BGE y filtros por ticker, ejercicio e Item aplicados después de la búsqueda |
| Bucle manual | `agente_manual`, ejecución de herramientas, devolución de `ToolMessage` y manejo de excepciones |
| Agente con framework | `create_agent` con cuatro herramientas, instrucciones de enrutado y esquema `RespuestaFinanciera` |
| Memoria | `InMemorySaver` y ejemplos de conversación con el mismo `thread_id` |
| Trazabilidad | `pretty_trace` para inspeccionar las llamadas a herramienta de una ejecución |
| Preguntas de ejemplo | Tres registros JSONL: uno numérico, uno extractivo y uno comparativo |
| Validación de preguntas | `validar`, con comprobaciones de campos, familias, datos disponibles y requisitos del conjunto propio |

### Qué muestran las ejecuciones guardadas

El notebook contiene salidas de una ejecución que monta los datos, realiza búsquedas y construye el agente con las cuatro herramientas. La comprobación numérica de NVIDIA FY2024 devuelve una `RespuestaFinanciera` con `fuente="xbrl"` y verifica que la trayectoria pasó por `get_xbrl_fact`. También hay un ejemplo de memoria que compara los ingresos de NVIDIA entre los dos ejercicios.

En la pregunta manual sobre riesgos de IA e ingresos de Microsoft, el bucle agota las ocho vueltas sin producir una respuesta final. El ejemplo sobre el margen bruto de Amazon también agota su límite. Estos casos muestran trabajo pendiente en el control de ejecución y el tratamiento de datos ausentes.

`max_vueltas` limita las iteraciones del bucle manual; una iteración puede solicitar varias herramientas. El agente con framework todavía no incorpora un límite explícito de llamadas ni el middleware de contraste de cifras exigidos en la entrega.

La demo de `demo_traza.json` está marcada como **provisional**: contiene prosa de ejemplo y no acredita una ejecución real del agente. Las salidas del notebook son ejemplos de funcionamiento; aún no hay una evaluación agregada ni una tabla de resultados baseline frente a final.

## Objetivo

El agente debe decidir qué herramienta necesita para cada pregunta:

- Consultar **XBRL** para obtener cifras exactas.
- Recuperar fragmentos de los informes para responder preguntas cualitativas y aportar citas.
- Leer una sección completa cuando los fragmentos sean insuficientes.
- Comprobar qué empresas, ejercicios y secciones existen antes de afirmar que un dato está disponible.

La recuperación de texto es una herramienta dentro del bucle del agente. **Acertar una cifra por el camino equivocado cuenta como fallo**: si el dato está en XBRL, encontrarlo en la prosa no cumple el criterio de trayectoria del enunciado. Cuando un dato no esté en el corpus, el agente debe indicarlo sin inventarlo.

## Corpus

Los datos docentes ya están incluidos en `dataset/`; no es necesario descargar informes de EDGAR para ejecutar la práctica.

| Alcance | Contenido |
| --- | --- |
| Empresas | NVIDIA (`NVDA`), Microsoft (`MSFT`), Apple (`AAPL`), Alphabet (`GOOGL`), Meta (`META`) y Amazon (`AMZN`) |
| Ejercicios fiscales | FY2024 y FY2025 |
| Secciones | `1A`: factores de riesgo; `7`: MD&A; `7A`: riesgo de mercado; `8`: estados financieros |
| Texto | 48 secciones, aproximadamente 650.000 tokens y 1.749 fragmentos |
| Datos numéricos | 135 hechos XBRL |
| Búsqueda inicial | Índice FAISS con embeddings `BAAI/bge-small-en-v1.5` |

Los dos paquetes principales se descomprimen en una misma carpeta `corpus/`:

| Paquete | Archivos principales |
| --- | --- |
| `corpus_miax_2026.zip` | `secciones.jsonl`, `chunks.jsonl`, `xbrl_facts.parquet` y manifiesto del corpus |
| `indice_faiss.zip` | `indice/corpus.faiss`, `indice/chunks_meta.parquet` y manifiesto del índice |
| `fuentes_10k_html.zip` | Informes originales en HTML, como material de consulta |

La celda de preparación del notebook verifica los SHA-256 de los paquetes y la correspondencia entre los fragmentos y los manifiestos. El índice y sus metadatos deben mantenerse alineados si se modifica el troceado.

### Particularidades que afectan a las respuestas

- `fiscal_year` identifica el ejercicio fiscal, que puede diferir del año de presentación del informe.
- El concepto XBRL de ingresos varía entre compañías y ejercicios. Hay que consultar los conceptos disponibles en los datos.
- Hay ausencias reales: por ejemplo, Amazon no reporta `GrossProfit` en el corpus. No debe sustituirse un dato ausente por una estimación.
- El corpus normaliza los estados financieros de NVIDIA bajo el Item `8` y conserva su procedencia en `item_origen`.
- El texto está en inglés; las consultas de búsqueda deben formularse en ese idioma aunque la pregunta llegue en español.

## Estructura del repositorio

```text
.
├── README.md
├── Practica_LLM_Agente_10K.docx          # Enunciado
├── pyproject.toml                      # Dependencias y versión de Python
├── uv.lock                             # Resolución de dependencias
├── .python-version
├── Clase_1/
│   ├── S1_Herramientas_y_Bucle_Alumno.ipynb
│   ├── S1_Herramientas_y_Bucle_Apuntes.md
│   ├── miax_s1.py                      # Búsqueda densa y reproducción de demo
│   ├── demo_traza.json                 # Traza de ejemplo
│   ├── golden_set_ejemplo.jsonl        # Tres preguntas de ejemplo
│   └── Practica_LLM_Agente_10K.docx
└── dataset/
    ├── corpus_miax_2026.zip
    ├── indice_faiss.zip
    ├── fuentes_10k_html.zip
    ├── SHA256SUMS.txt
    └── celda_descarga.py               # Preparación del corpus de referencia
```

Las carpetas de corpus descomprimido, `.venv/`, las cachés y el archivo `.env` están excluidos de Git.

## Preparación y ejecución del material actual

### 1. Crear el entorno

Se necesita Git, **Python 3.12**, `uv` y un editor que permita ejecutar notebooks, por ejemplo VS Code con soporte de Jupyter.

```bash
git clone https://github.com/GRUPO-TFM/B5T2-agentes.git
cd B5T2-agentes
uv sync --frozen
```

Selecciona el intérprete de `.venv` como kernel del notebook. Si necesitas registrarlo en Jupyter:

```bash
uv run python -m ipykernel install --user --name miax-agentes --display-name "MIAX · Agentes"
```

### 2. Configurar la clave del modelo

El notebook actual utiliza OpenRouter. Crea un archivo `.env` en la raíz del repositorio con tu propia clave:

```dotenv
OPENROUTER_API_KEY=tu_clave_aqui
```

También puedes proporcionar la variable de entorno o introducir la clave mediante el diálogo de `getpass` del notebook. No incluyas credenciales en código, resultados ni commits.

El proveedor y el modelo se configuran en la variable `MODELO` del notebook, con `temperature=0`. El notebook incluye un cálculo ilustrativo de costes por tokens; la medición del coste real por pregunta sigue pendiente.

### 3. Ejecutar el notebook

Abre [S1_Herramientas_y_Bucle_Alumno.ipynb](Clase_1/S1_Herramientas_y_Bucle_Alumno.ipynb) y ejecuta las celdas **de arriba abajo**, con `Clase_1/` como directorio de trabajo del kernel.

La celda de preparación encuentra los ZIP en `../dataset/`, comprueba sus hashes y los extrae en `Clase_1/corpus/`. El notebook contiene verificaciones con `assert` para comprobar el montaje de datos, las herramientas y la respuesta estructurada.

Las llamadas al agente requieren una clave válida y acceso al proveedor. La primera búsqueda también puede descargar el modelo de embeddings si no está en caché. La demo grabada puede reproducirse sin llamadas al modelo.

Los [apuntes de la sesión 1](Clase_1/S1_Herramientas_y_Bucle_Apuntes.md) explican las herramientas, el bucle ReAct, la salida estructurada y la inspección de trazas.

### 4. Consultar el agente construido

Después de ejecutar las celdas que crean `agente`, puedes invocarlo desde una celda del mismo notebook:

```python
resultado = agente.invoke(
    {"messages": [{"role": "user", "content":
                   "¿Cuál fue el revenue de NVIDIA en FY2024?"}]},
    config={"configurable": {"thread_id": "consulta-readme"}},
)
respuesta = resultado["structured_response"]
print(respuesta.model_dump())
```

El esquema implementado contiene `respuesta`, `cifra`, `unidad`, `ticker`, `ejercicio`, `fuente`, `cita` y `chunk_id`. `fuente` admite `xbrl`, `texto`, `ambas` o `ninguna`. La salida estructurada valida esos campos; el contraste automático de las afirmaciones con la evidencia requiere los evaluadores pendientes.

## Requisitos pendientes para completar el enunciado

### Conservar los contratos actuales

Los nombres y parámetros existentes deben conservarse para la evaluación con preguntas ciegas. Se puede mejorar su implementación y añadir parámetros con valor por defecto.

| Firma | Responsabilidad |
| --- | --- |
| `list_available()` | Informar del contenido disponible en el corpus |
| `get_xbrl_fact(ticker, fiscal_year, concept)` | Consultar el valor exacto, su unidad y periodo en XBRL |
| `search_filings(query, ticker=None, fiscal_year=None, item=None, k=5)` | Recuperar fragmentos con identificadores para poder citarlos |
| `read_section(ticker, fiscal_year, item)` | Devolver una sección completa cuando haga falta más contexto |

Las herramientas actuales incluyen docstrings que orientan al modelo sobre cuándo usarlas y los filtros admitidos. Las mejoras deben conservar también los campos obligatorios de `RespuestaFinanciera`.

### Respuesta estructurada y guardrails

Queda por añadir el límite de llamadas a herramienta por invocación y un middleware propio que extraiga las cifras de la respuesta, las contraste con XBRL y devuelva los desajustes al modelo para su corrección. El prompt actual instruye al agente para usar XBRL, pero ese control todavía no está implementado como middleware.

### Golden set y mejoras del retrieval

El fichero actual `golden_set_ejemplo.jsonl` contiene **tres preguntas** y pasa la validación de ejemplo con `exigir_20=False`. Queda por escribir el conjunto propio de **20 preguntas en JSONL, con al menos 6 comparativas entre ejercicios**, y validarlo con `exigir_20=True`. Las familias son `extractiva`, `numerica` y `comparativa`.

En las preguntas extractivas, la respuesta esperada se ancla a **una frase literal del informe** mediante `ancla_texto`. Un `chunk_id` puede servir para verificar la cita de una ejecución, pero no debe ser la referencia estable para medir mejoras de troceado.

A partir de la búsqueda densa actual, el enunciado exige aplicar y medir:

1. Filtrado por metadatos: ya existe en `miax_s1.buscar`; falta medir su efecto.
2. Combinación de BM25 con búsqueda densa: pendiente de implementar. `rank-bm25` está incluido como dependencia.
3. Reescritura de la consulta con el modelo: pendiente de implementar como mejora evaluable.

Se debe reportar `recall@k` tras cada mejora, usando el ancla de texto como referencia y documentando el valor de `k`.

### Evaluación y reproducibilidad

Queda por implementar tres evaluadores automáticos:

- **Cita:** existe en el corpus y respalda lo afirmado.
- **Cifra:** coincide con XBRL dentro de una tolerancia documentada.
- **Trayectoria:** el agente utilizó la herramienta que correspondía a la pregunta.

La entrega debe exponer **`responder(pregunta)` y `evaluar(ruta_jsonl)`**, ejecutables sobre un clon limpio sin editar código, para procesar las preguntas ciegas. Estas funciones aún no existen en el repositorio; la consulta actual se realiza mediante el notebook.

Antes de introducir mejoras, debe guardarse y etiquetarse el baseline con sus resultados. El código debe regenerar los resultados del baseline y del sistema final, así como todas las tablas del informe.

La comparación debe incluir aciertos por familia, `recall@k`, coste medio por pregunta, latencia media y llamadas a herramienta por pregunta, destacando el mejor valor de cada métrica. Coste y latencia deben aparecer como columnas de la tabla.

### Lista de trabajo pendiente

- [ ] Exponer `responder(pregunta)` y `evaluar(ruta_jsonl)` y ensayarlas sobre un clon limpio.
- [ ] Crear y validar las 20 preguntas propias, con al menos 6 comparativas.
- [ ] Guardar el baseline etiquetado y sus resultados antes de mejorarlo.
- [ ] Incorporar el límite de llamadas y el middleware de contraste de cifras.
- [ ] Medir el filtrado actual e implementar y medir BM25 con búsqueda densa y reescritura de consultas.
- [ ] Implementar los evaluadores de cita, cifra y trayectoria.
- [ ] Publicar resultados regenerables y la tabla baseline frente a final.
- [ ] Preparar el informe PDF y la presentación con resultados, costes y experimentos que no mejoraron las métricas.

## Entrega y presentación

Según el enunciado, la práctica se realiza en **grupos de 3 estudiantes**:

- **23 de septiembre, 23:59:** entrega del repositorio de GitHub y del informe PDF a través del aula virtual.
- **24 de septiembre:** ejecución en el aula de 10 preguntas ciegas contra el repositorio ya entregado y presentación de **8 minutos más preguntas**.
- **Evaluación:** 30 % repositorio y 70 % presentación del PDF entregado.

La defensa debe explicar qué mejoró respecto al baseline, cuánto costó, cómo se eligieron las herramientas y qué guardrail protege las cifras. También debe comparar los resultados de las preguntas ciegas con los del golden set propio y comentar los cambios que no mejoraron las métricas.
