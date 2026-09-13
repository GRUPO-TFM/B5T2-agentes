# Sesión 1 — Herramientas, RAG agéntico y bucle ReAct

| Propiedad | Valor |
| --- | --- |
| **Tipo** | Apuntes de estudio / referencia técnica |
| **Asignatura** | LLMs aplicados a Finanzas — MIAX |
| **Notebook fuente** | `S1_Herramientas_y_Bucle_Alumno.ipynb` |
| **Temas** | Agentes, tools, ReAct, RAG, XBRL, FAISS, LangChain, LangGraph |
| **Nivel** | Python intermedio |
| **Estado** | Apuntes completos para estudio |
| **Última revisión** | 10 de septiembre de 2026 |

> 💡 **Idea central**
>
> El notebook construye un agente investigador sobre informes 10-K. La recuperación de documentos no es un paso fijo del sistema: es una herramienta más. El modelo decide cuándo consultar XBRL, cuándo buscar fragmentos, cuándo leer una sección completa y cuándo comprobar primero qué información existe.

---

## Índice

1. [Objetivos de aprendizaje](#1-objetivos-de-aprendizaje)
2. [La arquitectura completa](#2-la-arquitectura-completa)
3. [El dominio financiero: 10-K, secciones y XBRL](#3-el-dominio-financiero-10-k-secciones-y-xbrl)
4. [Por qué el notebook no usa un RAG clásico](#4-por-qué-el-notebook-no-usa-un-rag-clásico)
5. [Qué es una herramienta](#5-qué-es-una-herramienta)
6. [Las cuatro herramientas del agente](#6-las-cuatro-herramientas-del-agente)
7. [El modelo, el proveedor y las llamadas a API](#7-el-modelo-el-proveedor-y-las-llamadas-a-api)
8. [Cómo funciona la búsqueda semántica](#8-cómo-funciona-la-búsqueda-semántica)
9. [`bind_tools` y el protocolo de tool calling](#9-bind_tools-y-el-protocolo-de-tool-calling)
10. [El bucle manual ReAct](#10-el-bucle-manual-react)
11. [Del bucle manual a `create_agent`](#11-del-bucle-manual-a-create_agent)
12. [Salida estructurada con Pydantic](#12-salida-estructurada-con-pydantic)
13. [Memoria y `thread_id`](#13-memoria-y-thread_id)
14. [Trazabilidad y observabilidad](#14-trazabilidad-y-observabilidad)
15. [Coste y elección de herramientas](#15-coste-y-elección-de-herramientas)
16. [Fallos deliberados y guardrails](#16-fallos-deliberados-y-guardrails)
17. [Los ejercicios del alumno](#17-los-ejercicios-del-alumno)
18. [Golden set y evaluación](#18-golden-set-y-evaluación)
19. [Orden de ejecución del notebook](#19-orden-de-ejecución-del-notebook)
20. [Problemas prácticos del workspace](#20-problemas-prácticos-del-workspace)
21. [Resumen para memorizar](#21-resumen-para-memorizar)
22. [Preguntas de autoevaluación](#22-preguntas-de-autoevaluación)
23. [Glosario](#23-glosario)
24. [Documentación y lecturas](#24-documentación-y-lecturas)

---

## 1. Objetivos de aprendizaje

Al terminar el notebook deberíamos saber:

- Distinguir un **RAG clásico** de un **RAG agéntico**.
- Explicar qué es una herramienta y qué información de ella recibe el modelo.
- Diseñar docstrings que ayuden al modelo a elegir correctamente una herramienta.
- Diferenciar una fuente estructurada y exacta —XBRL— de una búsqueda semántica aproximada.
- Entender qué hace `bind_tools()` y qué no hace.
- Ejecutar manualmente una petición de herramienta y devolver un `ToolMessage`.
- Implementar el ciclo **modelo → herramienta → observación → modelo**.
- Entender por qué `tool_call_id` debe conservarse.
- Reconocer el patrón ReAct dentro de ese ciclo.
- Sustituir el bucle manual por `create_agent()`.
- Forzar una salida estructurada y validable mediante Pydantic.
- Mantener memoria de conversación usando un checkpointer y un `thread_id`.
- Inspeccionar la trayectoria del agente, no solo su respuesta final.
- Detectar bucles, costes descontrolados, conceptos inexistentes y alucinaciones.
- Diseñar un golden set que evalúe respuesta, evidencia y elección de herramientas.

> ✅ **Criterio de dominio**
>
> No basta con obtener la cifra correcta. Si la pregunta es numérica, el agente debe llegar a ella mediante XBRL. Una respuesta correcta obtenida por el camino equivocado es frágil y debe considerarse un fallo de trayectoria.

---

## 2. La arquitectura completa

```text
Usuario
  │
  ▼
Pregunta en lenguaje natural
  │
  ▼
Modelo de chat con esquemas de herramientas
  │
  ├── Responde directamente ────────────────────────────────┐
  │                                                         │
  └── Solicita una o varias herramientas                    │
          │                                                  │
          ▼                                                  │
      Código Python ejecuta la función                       │
          │                                                  │
          ▼                                                  │
      ToolMessage con resultado + tool_call_id               │
          │                                                  │
          └────────── vuelve al modelo ────────────────┐      │
                                                       │      │
                                                       ▼      ▼
                                                Respuesta final
```

El modelo no accede directamente al corpus, a pandas ni a FAISS. Solo ve mensajes y esquemas de herramientas. El código Python conserva el control sobre qué función se ejecuta y devuelve el resultado al modelo.

### Capas del sistema

| Capa | Responsabilidad |
| --- | --- |
| **Datos** | Secciones 10-K, hechos XBRL, fragmentos e índice FAISS |
| **Herramientas** | Exponer operaciones concretas con entradas y salidas claras |
| **Modelo** | Interpretar la pregunta y elegir la siguiente acción |
| **Bucle agéntico** | Ejecutar tools, devolver observaciones y decidir cuándo terminar |
| **Contrato de salida** | Validar la respuesta final con Pydantic |
| **Memoria** | Mantener el contexto de una conversación mediante checkpoints |
| **Observabilidad** | Registrar herramientas, argumentos, resultados y orden de ejecución |
| **Evaluación** | Comparar respuesta, fuente, cita y trayectoria contra un golden set |

---

## 3. El dominio financiero: 10-K, secciones y XBRL

### 3.1 ¿Qué es un 10-K?

El 10-K es el informe anual que presentan ante la SEC las empresas cotizadas en Estados Unidos. Tiene una estructura relativamente normalizada, lo que permite formular consultas semejantes para compañías y ejercicios diferentes.

El corpus del notebook conserva cuatro secciones:

| Item | Contenido | Preguntas típicas |
| --- | --- | --- |
| **1A — Risk Factors** | Riesgos declarados por la compañía | ¿Qué riesgos aparecieron o cambiaron? |
| **7 — MD&A** | Explicación de resultados por la dirección | ¿Por qué aumentaron los ingresos o los costes? |
| **7A — Market Risk** | Exposición a tipos, divisas y precios | ¿Qué riesgo de mercado declara? |
| **8 — Financial Statements** | Estados financieros y notas | ¿Cuál fue una cifra y cómo se descompone? |

### 3.2 Ejercicio fiscal frente a fecha de presentación

`fiscal_year` representa el ejercicio económico, no necesariamente el año natural ni el año en el que se presentó el documento. Las empresas cierran sus ejercicios en meses diferentes.

> ⚠️ **Error frecuente**
>
> Inferir el ejercicio a partir de la fecha de presentación puede seleccionar el documento equivocado. La consulta debe usar el campo `fiscal_year` preparado en el corpus.

### 3.3 La excepción de NVIDIA

NVIDIA sitúa originalmente sus estados financieros bajo el Item 15 y en el Item 8 deja una remisión. El corpus normaliza ese contenido y lo sirve con la clave `"8"`, conservando el origen real en `item_origen`.

Esta normalización evita que `read_section("NVDA", 2025, "8")` devuelva únicamente una referencia de pocas líneas.

### 3.4 ¿Qué es XBRL?

XBRL representa hechos financieros como datos estructurados. Cada hecho incluye elementos como:

- Empresa o ticker.
- Ejercicio fiscal.
- Concepto de la taxonomía, por ejemplo `Revenues` o `NetIncomeLoss`.
- Valor.
- Unidad, por ejemplo `USD`.
- Fecha de cierre del periodo.
- Formulario de origen.

Esto permite consultar una cifra mediante filtros exactos, en vez de intentar encontrarla por similitud semántica dentro de la prosa.

> 💡 **Regla del notebook**
>
> XBRL es la fuente autorizada para cifras. El texto del informe se usa para explicaciones cualitativas y para aportar contexto, no para extraer una cifra que ya existe de forma estructurada.

---

## 4. Por qué el notebook no usa un RAG clásico

### 4.1 RAG clásico o 2-Step RAG

Un RAG clásico suele ejecutar siempre la misma secuencia:

```text
Pregunta → recuperar top-k fragmentos → añadirlos al prompt → generar respuesta
```

La recuperación se decide antes de que el modelo razone sobre la tarea. Normalmente se ejecuta una sola vez, con una consulta y un valor de `k` fijados de antemano.

### 4.2 Sus limitaciones en este caso

#### Una respuesta puede requerir varias búsquedas

Para identificar riesgos nuevos entre FY2024 y FY2025 hay que recuperar evidencia de ambos ejercicios y compararla. Una única recuperación puede mezclar fragmentos y omitir una de las dos partes.

#### El dato adecuado puede estar en una tabla estructurada

Una búsqueda por “beneficio neto de Apple” encuentra párrafos relacionados con el beneficio. No garantiza recuperar el hecho contable exacto. Si existe `NetIncomeLoss` en XBRL, la operación apropiada es una consulta estructurada.

#### La entidad solicitada puede no existir

Un recuperador siempre intenta devolver los fragmentos más parecidos, incluso cuando se pregunta por Tesla y Tesla no está en el corpus. “Más parecido” no significa “válido”.

### 4.3 RAG agéntico

En un RAG agéntico, retrieval se convierte en una herramienta opcional:

```text
Pregunta
  ├─ comprobar disponibilidad
  ├─ consultar XBRL
  ├─ buscar una o varias veces
  ├─ leer una sección completa
  └─ combinar resultados y responder
```

El modelo puede decidir no recuperar, recuperar varias veces, reformular una consulta o cambiar de herramienta según las observaciones recibidas.

> 💡 **Definición útil**
>
> El RAG clásico fija el flujo y deja variable la respuesta. El RAG agéntico también deja variable la trayectoria.

Esta flexibilidad mejora la capacidad de resolver preguntas compuestas, pero reduce la predictibilidad. Por eso hacen falta límites, trazas y evaluación de trayectoria.

---

## 5. Qué es una herramienta

Una herramienta es una función que se presenta al modelo mediante un esquema. En LangChain, el decorador `@tool` genera ese esquema a partir de la firma, los tipos y el docstring.

### 5.1 Qué ve el modelo

| El modelo ve | El modelo no ve |
| --- | --- |
| Nombre de la función | Cuerpo de Python |
| Nombres de parámetros | Comentarios internos |
| Tipos de parámetros | Algoritmo exacto |
| Docstring | Coste real si no se explica |
| Resultado después de ejecutarla | Variables locales y estructuras internas |

Por tanto, el docstring no es solamente documentación para desarrolladores. Forma parte del contexto que condiciona la decisión del modelo.

### 5.2 Un buen docstring debe indicar

- **Qué** hace la herramienta.
- **Cuándo** debe utilizarse.
- **Cuándo no** debe utilizarse.
- Qué significa cada parámetro.
- Qué vocabulario o valores acepta.
- Qué devuelve.
- Qué ocurre si no encuentra datos.
- Si es cara, aproximada o debe usarse como último recurso.

### 5.3 Ejemplo: docstring útil frente a docstring vago

```python
@tool
def get_xbrl_fact_vago(ticker: str, fiscal_year: int, concept: str) -> str:
    """Devuelve un dato financiero."""
```

El código puede ser idéntico al de la herramienta completa, pero el modelo no sabe que:

- Es la fuente autorizada para cifras.
- Debe preferirla frente al retrieval textual.
- `concept` espera nombres US-GAAP.
- `NetIncomeLoss`, `Revenues` o `Assets` son ejemplos válidos.

> ✅ **Principio de diseño**
>
> La descripción de una tool es prompt engineering aplicado al enrutamiento.

---

## 6. Las cuatro herramientas del agente

### 6.1 Tabla comparativa

| Tool | Entradas | Salida | Fuente | Red/API | Propiedad |
| --- | --- | --- | --- | --- | --- |
| `list_available()` | Ninguna | Texto con compañías, ejercicios e Items | DataFrame `secciones` | No | Local, determinista |
| `get_xbrl_fact()` | `ticker`, `fiscal_year`, `concept` | Hecho financiero o aviso | Parquet XBRL | No | Exacta, barata |
| `search_filings()` | `query`, filtros y `k` | Fragmentos con `chunk_id` | FAISS + metadatos | Normalmente no durante la consulta; el modelo de embeddings puede descargarse la primera vez | Aproximada |
| `read_section()` | `ticker`, `fiscal_year`, `item` | Texto completo | DataFrame `secciones` | No | Exacta pero cara en tokens posteriores |

Las funciones son locales. El coste de API aparece cuando sus resultados se incluyen en una nueva invocación al modelo.

### 6.2 `list_available()`

#### Contrato

```python
list_available() -> str
```

No recibe argumentos. Lee el DataFrame global `secciones`, elimina duplicados, agrupa por empresa y devuelve texto legible por el modelo.

Ejemplo conceptual de salida:

```text
Contenido disponible en el corpus:
- AAPL (Apple Inc.): ejercicios FY2024, FY2025; secciones: 1A, 7, 7A, 8.
- NVDA (NVIDIA Corporation): ejercicios FY2024, FY2025; secciones: 1A, 7, 7A, 8.
```

No llama al modelo ni a una API. Su función es reducir alucinaciones sobre la cobertura del corpus.

### 6.3 `get_xbrl_fact()`

#### Contrato

```python
get_xbrl_fact(
    ticker: str,
    fiscal_year: int,
    concept: str,
) -> str
```

Filtra `xbrl_facts.parquet` mediante igualdad exacta. Si encuentra una fila, devuelve valor, unidad, fecha de cierre y formulario. Si no la encuentra:

- Distingue entre ejercicio inexistente y concepto inexistente.
- Enumera los conceptos disponibles para ayudar al modelo a corregir su petición.
- No estima ni calcula una cifra inventada.

> ⚠️ **Ausencia de etiqueta ≠ ausencia económica**
>
> Amazon puede presentar información suficiente para calcular el beneficio bruto sin etiquetar directamente `GrossProfit`. La herramienta afirma que ese concepto no fue reportado; no afirma que la magnitud económica sea imposible de calcular.

### 6.4 `search_filings()`

#### Contrato

```python
search_filings(
    query: str,
    ticker: str | None = None,
    fiscal_year: int | None = None,
    item: str | None = None,
    k: int = 5,
) -> str
```

Realiza una búsqueda semántica sobre fragmentos del corpus. Devuelve los `k` fragmentos más relevantes que cumplen los filtros. Cada fragmento incluye:

- `chunk_id`.
- Ticker.
- Ejercicio fiscal.
- Item.
- Similitud.
- Texto.

La consulta debe formularse en inglés porque los documentos están en inglés.

> 💡 **La herramienta recupera evidencia, no respuestas**
>
> Un fragmento semánticamente parecido puede ser incompleto, pertenecer a un contexto distinto o empezar a mitad de una frase. El modelo todavía debe interpretar y contrastar lo recuperado.

### 6.5 `read_section()`

#### Contrato

```python
read_section(
    ticker: str,
    fiscal_year: int,
    item: str,
) -> str
```

Filtra la sección solicitada y devuelve su texto completo. No genera coste de red por sí misma, pero el texto se añadirá al contexto del modelo en la siguiente vuelta. Una sección puede contener decenas de miles de tokens.

Debe utilizarse cuando los fragmentos de `search_filings()` sean insuficientes, no como primera opción.

---

## 7. El modelo, el proveedor y las llamadas a API

### 7.1 Configuración del notebook

```python
from langchain.chat_models import init_chat_model

MODELO = "openrouter:google/gemini-3.8-flash"
modelo = init_chat_model(MODELO, temperature=0)
```

El notebook está configurado para utilizar **Gemini 3.8 Flash a través de OpenRouter**. La forma general de la cadena es:

```text
proveedor:modelo-del-proveedor
```

`init_chat_model()` ofrece una interfaz común para distintos proveedores. Cambiar la cadena permite cambiar de modelo sin reescribir el resto del agente, siempre que la integración soporte las capacidades necesarias.

### 7.2 Gestión de la clave

La celda de configuración busca `OPENROUTER_API_KEY` en las variables de entorno. Si no existe, la solicita con `getpass`, que evita mostrarla en la salida.

```python
HAY_CLAVE = pedir_clave("OPENROUTER_API_KEY", "openrouter.ai/keys")
```

Si no hay clave:

- `modelo` queda como `None`.
- Las celdas que invocan al LLM no funcionan.
- Las operaciones locales sobre corpus y XBRL sí pueden funcionar.

### 7.3 Qué operaciones llaman a la API

| Operación | ¿Llama al LLM? |
| --- | --- |
| `list_available.invoke({})` | No |
| `get_xbrl_fact.invoke(...)` | No |
| `read_section.invoke(...)` | No |
| `search_filings.invoke(...)` | No llama al chat model; calcula embeddings localmente |
| `modelo.invoke(...)` | Sí |
| `modelo_con_tools.invoke(...)` | Sí |
| `agente.invoke(...)` | Sí, posiblemente varias veces |

> ⚠️ **Una pregunta puede producir varias facturas**
>
> Una invocación de `agente.invoke()` puede contener varias llamadas internas al modelo, una por cada vuelta del bucle. El límite relevante no es solo el número de preguntas del usuario, sino el número total de vueltas y tokens.

### 7.4 `temperature=0`

Se utiliza para reducir variabilidad en evaluación. No convierte al modelo en completamente determinista, pero disminuye el ruido entre ejecuciones y hace más interpretable una comparación baseline-final.

---

## 8. Cómo funciona la búsqueda semántica

La implementación de `search_filings()` está en `miax_s1.py` y se trata como caja negra durante esta sesión. Su flujo es:

```text
Consulta en inglés
  ↓
Prefijo de consulta de BGE
  ↓
Embedding normalizado
  ↓
Búsqueda en índice FAISS
  ↓
Orden por similitud
  ↓
Filtros por ticker, fiscal_year e item
  ↓
Primeros k fragmentos
  ↓
Texto formateado con chunk_id
```

### 8.1 Embeddings

Un embedding representa un texto como un vector numérico. Textos con significado parecido tienden a ocupar posiciones próximas en el espacio vectorial.

El notebook usa:

```python
MODELO_EMBEDDINGS = "BAAI/bge-small-en-v1.5"
```

El modelo BGE requiere un prefijo específico en la consulta:

```python
"Represent this sentence for searching relevant passages: "
```

Omitir el prefijo no suele generar una excepción: simplemente degrada la recuperación. Es un ejemplo de fallo silencioso.

### 8.2 FAISS

FAISS almacena los embeddings de los fragmentos y permite buscar rápidamente los vectores más similares. El índice del notebook usa producto interno sobre vectores normalizados, equivalente a similitud coseno.

### 8.3 Integridad entre índice y metadatos

La posición `i` del índice debe corresponder exactamente a la fila `i` de `chunks_meta.parquet`. Por eso el setup valida:

- Hash de los ZIP.
- Número de vectores frente a número de filas.
- Huella de `chunks.jsonl` en los manifiestos.

Si índice y metadatos se desalinean, el sistema puede devolver texto incorrecto sin lanzar ningún error.

### 8.4 Troceado y top-k

El documento se divide en chunks. Dos decisiones afectan mucho al resultado:

- **Tamaño y solapamiento del chunk:** demasiado corto pierde contexto; demasiado largo introduce ruido y coste.
- **Valor de `k`:** pequeño puede omitir evidencia; grande aumenta tokens y distractores.

El notebook muestra un fragmento que empieza a mitad de frase para hacer visible que los límites del chunk son una decisión técnica, no límites semánticos naturales.

### 8.5 Filtros posteriores a la búsqueda

La implementación recupera primero el orden completo y después filtra por compañía, ejercicio e Item. Con 1.749 vectores es aceptable; a gran escala sería preferible aplicar filtros antes o dentro del sistema de búsqueda.

---

## 9. `bind_tools` y el protocolo de tool calling

```python
HERRAMIENTAS = [
    list_available,
    get_xbrl_fact,
    search_filings,
    read_section,
]

modelo_con_tools = modelo.bind_tools(HERRAMIENTAS)
```

`bind_tools()` añade a la petición los esquemas de las herramientas. No las ejecuta y no crea por sí solo un agente completo.

Cuando el modelo quiere usar una herramienta, responde con una petición estructurada:

```python
{
    "name": "get_xbrl_fact",
    "args": {
        "ticker": "NVDA",
        "fiscal_year": 2025,
        "concept": "Revenues",
    },
    "id": "call_abc123",
}
```

En ese momento:

1. El modelo **no ha ejecutado** la función.
2. El contenido textual de la respuesta puede estar vacío.
3. Nuestro programa debe validar el nombre y ejecutar la tool.
4. Debe devolver el resultado en un `ToolMessage`.
5. Ese mensaje debe conservar el identificador original.

### Por qué importa `tool_call_id`

```python
ToolMessage(
    content=str(resultado),
    tool_call_id=tc["id"],
    name=tc["name"],
)
```

El identificador empareja una observación con la petición que la produjo. Si el modelo solicita dos herramientas en paralelo, cada resultado necesita el ID correspondiente. Sin él, el historial queda incompleto o ambiguo y el proveedor puede rechazarlo.

---

## 10. El bucle manual ReAct

### 10.1 El patrón

ReAct combina:

- **Reason:** interpretar lo observado y decidir la siguiente acción.
- **Act:** pedir una herramienta.
- **Observe:** recibir su resultado.
- **Repeat:** continuar hasta emitir una respuesta final.

El notebook implementa el patrón con un `for` alrededor de `modelo_con_tools.invoke()`.

### 10.2 Implementación de referencia

```python
from langchain.messages import ToolMessage


def agente_manual(
    pregunta: str,
    max_vueltas: int = 6,
    verboso: bool = True,
) -> str:
    mensajes = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": pregunta},
    ]

    for vuelta in range(max_vueltas):
        respuesta = modelo_con_tools.invoke(mensajes)
        mensajes.append(respuesta)

        if not respuesta.tool_calls:
            return respuesta.text

        for tc in respuesta.tool_calls:
            if verboso:
                print(
                    f"Vuelta {vuelta + 1}: "
                    f"{tc['name']}({tc['args']})"
                )

            try:
                herramienta = POR_NOMBRE[tc["name"]]
                resultado = herramienta.invoke(tc["args"])
            except Exception as error:
                resultado = (
                    f"Error al ejecutar {tc['name']}: "
                    f"{type(error).__name__}: {error}"
                )

            mensajes.append(
                ToolMessage(
                    content=str(resultado),
                    tool_call_id=tc["id"],
                    name=tc["name"],
                )
            )

    return "Se agotaron las vueltas sin llegar a una respuesta."
```

### 10.3 Decisiones de diseño

#### Se añade primero la respuesta del modelo

El mensaje que contiene `tool_calls` debe aparecer en el historial antes de sus `ToolMessage`.

#### Se responden todas las llamadas

Si `respuesta.tool_calls` contiene varias peticiones, el bucle debe ejecutar y responder a cada una.

#### Los errores se convierten en observaciones

Una excepción no debería romper todo el agente. Al convertirla en texto, el modelo puede cambiar argumentos, usar otra herramienta o reconocer que no puede responder.

#### Existe un límite de vueltas

`max_vueltas` evita un ciclo realmente infinito, aunque un valor demasiado alto todavía puede generar un coste innecesario.

> 💡 **Definición mínima de agente en este notebook**
>
> Un agente es un modelo con herramientas dentro de un bucle de ejecución y una condición de parada.

---

## 11. Del bucle manual a `create_agent`

LangChain ofrece un runtime que encapsula ese ciclo:

```python
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

agente = create_agent(
    model=MODELO,
    tools=HERRAMIENTAS,
    system_prompt=SYSTEM,
    response_format=RespuestaFinanciera,
    checkpointer=InMemorySaver(),
)
```

### Correspondencia con el código manual

| `create_agent()` | Equivalente manual |
| --- | --- |
| `tools=` | `bind_tools()` y `POR_NOMBRE` |
| Runtime agéntico | Bucle y ejecución de las tools |
| `system_prompt=` | Primer mensaje de sistema |
| `response_format=` | Validación y reintentos de formato |
| `checkpointer=` | Persistencia del historial por hilo |

Además facilita middleware, streaming, callbacks, reintentos, manejo de errores e interrupciones humanas.

> ⚠️ **Abstracción no significa magia**
>
> `create_agent()` sigue ejecutando conceptualmente el mismo ciclo. Haberlo construido a mano permite depurar qué ocurre cuando el agente se atasca o el historial de mensajes queda mal formado.

---

## 12. Salida estructurada con Pydantic

La clase `RespuestaFinanciera` define el contrato de la respuesta:

| Campo | Significado |
| --- | --- |
| `respuesta` | Explicación breve en lenguaje natural |
| `cifra` | Valor numérico, si procede |
| `unidad` | USD, porcentaje, acciones, etc. |
| `ticker` | Empresa correspondiente |
| `ejercicio` | Ejercicio fiscal |
| `fuente` | `xbrl`, `texto`, `ambas` o `ninguna` |
| `cita` | Texto literal que respalda la respuesta |
| `chunk_id` | Fragmento citado |

### Por qué es importante

Sin esquema, “incluye una fuente” es una petición blanda dentro del prompt. Con Pydantic:

- La aplicación recibe un objeto tipado.
- Los valores admitidos se restringen.
- Los evaluadores leen campos directamente.
- Se detectan respuestas incompletas.
- Se pueden aplicar reintentos ante errores de validación.

El resultado se obtiene desde:

```python
resultado["structured_response"]
```

Si el proveedor no admite salida estructurada nativa de manera fiable, puede utilizarse una estrategia basada en tool calling:

```python
from langchain.agents.structured_output import ToolStrategy

response_format=ToolStrategy(RespuestaFinanciera)
```

---

## 13. Memoria y `thread_id`

```python
CONFIG = {"configurable": {"thread_id": "clase-s1"}}
```

`InMemorySaver()` guarda checkpoints del estado. `thread_id` identifica a qué conversación pertenece cada invocación.

Con el mismo hilo:

```text
Usuario: ¿Cuál fue el revenue de NVIDIA en FY2025?
Usuario: ¿Y cuánto es eso comparado con el ejercicio anterior?
```

La segunda pregunta puede resolver “eso”, “NVIDIA” y “el ejercicio anterior” gracias al historial.

Con un `thread_id` diferente, la segunda pregunta queda aislada y pierde sus referentes.

> 💡 **Fórmula mental**
>
> Checkpointer sin `thread_id` no sabe qué conversación recuperar. `thread_id` sin checkpointer no tiene estado persistido que recuperar.

`InMemorySaver` sirve para clase, desarrollo y pruebas. En producción se utiliza normalmente un almacenamiento persistente.

---

## 14. Trazabilidad y observabilidad

`pretty_trace()` recorre todos los mensajes y muestra:

- Herramienta solicitada.
- Argumentos.
- Orden de las llamadas.
- Resultado resumido.
- Número total de llamadas.
- Respuesta estructurada final.
- Fuente, cifra y cita.

### Por qué no basta con evaluar la respuesta final

Dos agentes pueden devolver la misma cifra:

- El primero la consulta en XBRL.
- El segundo la encuentra casualmente en un fragmento de texto.

El resultado coincide, pero el segundo camino es menos reproducible y puede fallar cuando cambie el documento. Una evaluación robusta debe medir:

1. Exactitud de la respuesta.
2. Corrección de la fuente.
3. Evidencia citada.
4. Elección de herramienta.
5. Número y orden razonable de llamadas.
6. Ausencia de pasos innecesarios.

---

## 15. Coste y elección de herramientas

### 15.1 Fórmula de coste

```python
coste = (
    tokens_entrada / 1_000_000 * precio_entrada
    + tokens_salida / 1_000_000 * precio_salida
)
```

El notebook compara:

- Informe completo en contexto.
- Cinco fragmentos recuperados.
- Una consulta XBRL.

En tokens de entrada, XBRL puede ser miles de veces más barato que cargar el informe. En coste total por pregunta la diferencia relativa se reduce, porque los tokens de salida se pagan en todos los caminos.

### 15.2 Por qué sigue siendo importante

El coste se multiplica por:

- Número de preguntas.
- Número de grupos.
- Iteraciones durante el desarrollo.
- Número de vueltas del agente.
- Lecturas repetidas de secciones grandes.

### 15.3 Auditabilidad

Retrieval no solo reduce tokens. También produce un fragmento y un `chunk_id` que permiten inspeccionar la evidencia. El contexto largo puede contener la respuesta, pero no garantiza que quede claro qué pasaje la sustenta.

> ⚠️ **Precios volátiles**
>
> La tabla de precios del notebook es una fotografía fechada. Debe revisarse antes de utilizarla para presupuestar o evaluar costes actuales.

---

## 16. Fallos deliberados y guardrails

### 16.1 Empresa fuera del corpus

Pregunta de prueba: revenue de Tesla en FY2025.

Sin `list_available()`, el modelo puede:

- Consultar XBRL con `TSLA` y recibir un vacío.
- Responder de memoria.
- Recuperar fragmentos irrelevantes de otra compañía.

Con `list_available()`, dispone de una forma explícita de comprobar cobertura. Sin embargo, ofrecer la herramienta no garantiza que siempre la use: un guardrail debe convertir la recomendación en una restricción verificable.

### 16.2 Concepto XBRL inexistente

Amazon no etiqueta `GrossProfit` en el conjunto utilizado. El modelo puede reintentar con nombres parecidos indefinidamente.

Lección: una respuesta negativa de una tool también es información. El agente debe saber detenerse, cambiar de estrategia o explicar la limitación.

### 16.3 Bucle costoso

`max_vueltas=100` está diseñado para demostrar un fallo. Cada vuelta puede generar otra llamada pagada al modelo.

Guardrails recomendables:

- Límite estricto de llamadas.
- Límite de tokens o presupuesto.
- Detección de llamadas repetidas con los mismos argumentos.
- Política de escalado: retrieval antes de sección completa.
- Validación de ticker, ejercicio, Item y concepto.
- Timeout por tool.
- Manejo explícito de excepciones.
- Respuesta segura cuando no existe evidencia suficiente.

### 16.4 Otros fallos silenciosos

- Índice FAISS desalineado con metadatos.
- Consulta en español sobre un corpus en inglés.
- Prefijo BGE omitido.
- Chunk cortado en un límite poco informativo.
- `k` demasiado pequeño o demasiado grande.
- Confundir `fiscal_year` con la fecha de presentación.
- Usar `Series.item` en vez de `serie["item"]` cuando una columna se llama `item`.
- Cambiar de modelo entre baseline y evaluación.

---

## 17. Los ejercicios del alumno

El notebook contiene tres bloques `TODO`.

### 17.1 Ejercicio 1 — `list_available()`

Objetivo: construir un inventario textual del corpus.

```python
@tool
def list_available() -> str:
    """Lista qué compañías, ejercicios y secciones existen en el corpus.

    Úsala SIEMPRE antes de responder que un dato no existe, y antes de
    llamar a cualquier otra herramienta si no estás seguro de que la
    compañía o el ejercicio que te piden estén en el corpus.
    """
    columnas = ["ticker", "empresa", "fiscal_year", "item"]

    disponibles = (
        secciones[columnas]
        .drop_duplicates()
        .sort_values(["ticker", "fiscal_year", "item"])
    )

    lineas = ["Contenido disponible en el corpus:"]

    for (ticker, empresa), grupo in disponibles.groupby(
        ["ticker", "empresa"], sort=True
    ):
        ejercicios = sorted(grupo["fiscal_year"].astype(int).unique())
        items = sorted(grupo["item"].unique())

        ejercicios_txt = ", ".join(
            f"FY{ejercicio}" for ejercicio in ejercicios
        )
        items_txt = ", ".join(items)

        lineas.append(
            f"- {ticker} ({empresa}): ejercicios {ejercicios_txt}; "
            f"secciones disponibles: {items_txt}."
        )

    return "\n".join(lineas)
```

Conceptos evaluados:

- Agrupación y deduplicación con pandas.
- Diseño de una salida pensada para el modelo.
- Docstring como instrucción de uso.
- Tool local sin llamadas a API.

### 17.2 Ejercicio 2 — dos docstrings, mismo código

Objetivo: hacer la misma pregunta con dos configuraciones:

```python
[get_xbrl_fact, search_filings]
[get_xbrl_fact_vago, search_filings]
```

Debe observarse:

- Qué herramienta elige el modelo.
- Qué argumentos genera.
- Qué concepto XBRL propone.
- Si confunde una pregunta numérica con una búsqueda textual.

El experimento aísla una variable: la descripción de la herramienta.

### 17.3 Ejercicio 3 — bucle manual

Objetivo: completar la ejecución, creación y anexado de `ToolMessage` dentro de `agente_manual()`.

Conceptos evaluados:

- Dispatcher `POR_NOMBRE`.
- `.invoke()` sobre una tool.
- Conversión del resultado a texto.
- Conservación del `tool_call_id`.
- Respuesta a múltiples tool calls.
- Manejo de excepciones.
- Trazas legibles.

---

## 18. Golden set y evaluación

Un golden set contiene preguntas con respuestas y evidencias conocidas. El entregable distingue tres familias:

| Familia | Qué evalúa | Campos principales |
| --- | --- | --- |
| `extractiva` | Retrieval y cita | `item_esperado`, `ancla_texto` |
| `numerica` | Uso correcto de XBRL | `cifra_esperada`, `unidad`, `concept_xbrl` |
| `comparativa` | Descomposición y comparación | Evidencia de cada ejercicio |

### 18.1 Por qué hacen falta preguntas comparativas

Una comparación obliga al agente a:

1. Identificar dos periodos.
2. Ejecutar varias consultas.
3. Separar correctamente las evidencias.
4. Calcular o explicar la diferencia.
5. Integrar el resultado.

Es la familia que demuestra que el agente aporta algo más que un pipeline fijo.

### 18.2 `ancla_texto` frente a `chunk_id`

El golden set se ancla a una frase literal del informe. No debe depender únicamente de un `chunk_id`, porque al cambiar el troceado cambian los identificadores.

La frase de referencia debe ser corta —una frase, no varios párrafos— para medir la recuperación y no el tamaño de la ventana.

### 18.3 Qué valida el notebook

- Presencia de todos los campos.
- IDs únicos.
- Familia admitida.
- Ticker y ejercicio existentes.
- Concepto XBRL disponible.
- Cifra para preguntas numéricas.
- Ancla para preguntas extractivas.
- Longitud razonable del ancla.
- Herramienta esperada.
- Veinte preguntas propias.
- Al menos seis comparativas.

---

## 19. Orden de ejecución del notebook

El notebook debe ejecutarse de arriba abajo porque las celdas comparten estado.

```text
1. Demo grabada
2. Instalación
3. Clave de OpenRouter
4. Montaje y validación del corpus
5. Inicialización del modelo
6. Carga de secciones y análisis de tokens
7. Carga de XBRL
8. Definición de tools
9. Ejercicios sobre disponibilidad y docstrings
10. bind_tools
11. Bucle manual
12. Pruebas compuestas y bucle deliberado
13. Esquema Pydantic
14. create_agent
15. Memoria y trazas
16. Golden set y validador
```

> ⚠️ **Estado compartido**
>
> Si se reinicia el kernel o se salta una celda, pueden faltar variables como `secciones`, `xbrl`, `modelo_con_tools`, `HERRAMIENTAS` o `POR_NOMBRE`.

Los `assert` actúan como checkpoints didácticos. Si uno falla, no conviene continuar hasta corregir la sección anterior.

---

## 20. Problemas prácticos del workspace

### 20.1 Ubicación de los ZIP

En este workspace los ficheros están en:

```text
dataset/corpus_miax_2026.zip
dataset/indice_faiss.zip
```

El notebook no incluye `../dataset` en `CANDIDATOS`. Si se ejecuta con `Clase_1` como directorio actual, puede añadirse:

```python
CANDIDATOS = [
    pathlib.Path("."),
    pathlib.Path("../dataset"),
    pathlib.Path("/content"),
    pathlib.Path("/content/drive/MyDrive/MIAX_2026"),
    pathlib.Path("/content/drive/Shareddrives/MIAX_2026"),
]
```

### 20.2 Golden set oficial

No está presente `golden_set.jsonl`. El notebook cae automáticamente en:

```text
golden_set_ejemplo.jsonl
```

Ese fichero sirve para revisar el esquema y probar el validador, pero no sustituye las veinte preguntas oficiales.

### 20.3 Salidas del notebook

El fichero analizado no contiene resultados guardados. Sus 24 celdas de código deben ejecutarse para producir tablas, llamadas de herramientas y trazas.

---

## 21. Resumen para memorizar

> 🧠 **RAG clásico**
>
> Recupera siempre antes de responder. El flujo está fijado.

> 🧠 **RAG agéntico**
>
> Retrieval es una tool. El modelo decide si buscar, cuántas veces y con qué filtros.

> 🧠 **Tool**
>
> Función + esquema de argumentos + docstring + resultado observable.

> 🧠 **Docstring**
>
> Es la instrucción de enrutamiento que ayuda al modelo a elegir la tool.

> 🧠 **`bind_tools()`**
>
> Enseña los esquemas al modelo; no ejecuta las funciones.

> 🧠 **`ToolMessage`**
>
> Devuelve al modelo la observación producida por una ejecución real.

> 🧠 **`tool_call_id`**
>
> Une cada resultado con la petición correspondiente.

> 🧠 **ReAct**
>
> Razonar, actuar mediante una tool, observar y repetir.

> 🧠 **XBRL**
>
> Fuente estructurada y exacta para cifras reportadas.

> 🧠 **Retrieval**
>
> Fuente aproximada para recuperar evidencia textual relevante.

> 🧠 **Salida estructurada**
>
> Convierte una recomendación del prompt en un contrato validable.

> 🧠 **Memoria**
>
> Checkpointer + `thread_id` mantienen el estado de una conversación.

> 🧠 **Evaluación de trayectoria**
>
> Comprueba cómo llegó el agente a la respuesta, no solo si acertó el texto final.

---

## 22. Preguntas de autoevaluación

- [ ] ¿Por qué una búsqueda semántica no es la fuente adecuada para una cifra XBRL?
- [ ] ¿Qué diferencia existe entre ofrecer una tool y obligar a utilizarla?
- [ ] ¿Qué parte de una función decorada con `@tool` ve el modelo?
- [ ] ¿Por qué un docstring puede cambiar el comportamiento sin cambiar el cuerpo de Python?
- [ ] ¿Qué devuelve realmente un modelo cuando solicita una herramienta?
- [ ] ¿Quién ejecuta la tool: el modelo, LangChain o nuestro código?
- [ ] ¿Por qué debe existir un `ToolMessage` por cada `tool_call_id`?
- [ ] ¿Qué condición termina el bucle manual?
- [ ] ¿Por qué una sección local puede ser “cara” si leer el fichero no cuesta dinero?
- [ ] ¿Cómo puede un agente entrar en bucle al no encontrar `GrossProfit`?
- [ ] ¿Qué relación existe entre `InMemorySaver` y `thread_id`?
- [ ] ¿Por qué la cita esperada debe ser una frase y no un `chunk_id` fijo?
- [ ] ¿Qué mide una pregunta comparativa que no mide una pregunta extractiva simple?
- [ ] ¿Por qué conviene fijar modelo, versión y temperatura durante la evaluación?

### Respuestas breves

1. Porque la similitud devuelve texto relacionado, no garantiza el hecho contable exacto.
2. Una tool disponible es una opción; un guardrail convierte la política en una condición verificable.
3. Nombre, parámetros, tipos y docstring; después ve el resultado de la ejecución.
4. Porque el docstring se envía al modelo como parte del esquema.
5. Una petición estructurada con nombre, argumentos e identificador.
6. En el bucle manual lo ejecuta nuestro Python; `create_agent` automatiza esa capa.
7. Para mantener un historial válido y asociar cada observación con su petición.
8. Que el modelo responda sin `tool_calls` o que se alcance el límite de vueltas.
9. Porque el contenido completo se envía después al LLM y consume tokens de entrada.
10. Puede reintentar conceptos parecidos sin interpretar la ausencia como condición de parada.
11. El saver almacena estado y el ID selecciona el hilo correcto.
12. Porque el troceado puede cambiar y regenerar todos los IDs.
13. Descomposición, varias recuperaciones, separación temporal e integración.
14. Para que las diferencias de métricas representen cambios del sistema y no ruido experimental.

---

## 23. Glosario

| Término | Definición |
| --- | --- |
| **Agente** | Sistema que usa un modelo para decidir acciones dentro de un bucle |
| **RAG** | Generación aumentada con información recuperada de una fuente externa |
| **RAG agéntico** | Arquitectura en la que el modelo decide cuándo y cómo recuperar |
| **Tool calling** | Protocolo por el que el modelo solicita la ejecución de una función |
| **Tool schema** | Descripción estructurada del nombre, argumentos y tipos de una tool |
| **ReAct** | Patrón que intercala razonamiento, acciones y observaciones |
| **Embedding** | Vector numérico que representa el significado aproximado de un texto |
| **FAISS** | Biblioteca para búsqueda eficiente de vectores similares |
| **Chunk** | Fragmento de un documento utilizado como unidad de recuperación |
| **Top-k** | Los `k` resultados con mayor puntuación de similitud |
| **XBRL** | Estándar para representar datos financieros estructurados |
| **US-GAAP concept** | Etiqueta contable como `Revenues` o `NetIncomeLoss` |
| **System prompt** | Instrucciones de alto nivel que gobiernan el comportamiento del modelo |
| **ToolMessage** | Mensaje que comunica al modelo el resultado de una tool |
| **Checkpoint** | Estado persistido de una ejecución o conversación |
| **Golden set** | Conjunto de ejemplos con resultados conocidos para evaluación |
| **Guardrail** | Restricción o validación que limita comportamientos no deseados |
| **Trayectoria** | Secuencia de decisiones, tools, argumentos y observaciones del agente |
| **Auditabilidad** | Capacidad de reconstruir y verificar de dónde salió una respuesta |

---

## 24. Documentación y lecturas

### LangChain y LangGraph

- [Tools — LangChain](https://docs.langchain.com/oss/python/langchain/tools): creación con `@tool`, esquemas, docstrings, entradas y salidas.
- [Models — LangChain](https://docs.langchain.com/oss/python/langchain/models): `init_chat_model()`, `invoke()`, parámetros y `bind_tools()`.
- [Providers and models — LangChain](https://docs.langchain.com/oss/python/concepts/providers-and-models): interfaz común y formato `provider:model`.
- [Agents — LangChain](https://docs.langchain.com/oss/python/langchain/agents): `create_agent()`, herramientas, middleware e invocación.
- [Messages — LangChain](https://docs.langchain.com/oss/python/langchain/messages): tipos de mensajes, `ToolMessage` y `tool_call_id`.
- [Structured output — LangChain](https://docs.langchain.com/oss/python/langchain/structured-output): Pydantic, `ProviderStrategy` y `ToolStrategy`.
- [Short-term memory — LangChain](https://docs.langchain.com/oss/python/langchain/short-term-memory): checkpointers y separación por `thread_id`.
- [Custom RAG agent — LangGraph](https://docs.langchain.com/oss/python/langgraph/agentic-rag): construcción de un agente que decide cuándo recuperar.
- [LangGraph Quickstart](https://docs.langchain.com/oss/python/langgraph/quickstart): ejemplo de ciclo con `ToolMessage`.

### Papers fundamentales

- [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401): paper que popularizó el patrón RAG.
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629): formulación del patrón de razonamiento y actuación intercalados.

### Datos financieros y recuperación

- [EDGAR Application Programming Interfaces — SEC](https://www.sec.gov/search-filings/edgar-application-programming-interfaces): APIs oficiales de submissions y hechos XBRL.
- [EDGAR XBRL Guide — SEC](https://www.sec.gov/file/xbrl-guide): guía técnica oficial de XBRL en EDGAR.
- [FAISS Documentation](https://faiss.ai/): búsqueda de similitud y clustering de vectores densos.
- [BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5): ficha del modelo de embeddings utilizado.

---

> ✅ **Checklist final de la sesión**
>
> - [ ] El corpus y el índice están montados y verificados.
> - [ ] `list_available()` devuelve un texto útil.
> - [ ] Las cuatro tools están definidas.
> - [ ] El modelo diferencia cifras de preguntas cualitativas.
> - [ ] El bucle devuelve un `ToolMessage` por cada petición.
> - [ ] Existe un límite de vueltas.
> - [ ] La respuesta final valida contra `RespuestaFinanciera`.
> - [ ] Las preguntas relacionadas comparten `thread_id`.
> - [ ] La trayectoria se puede imprimir e inspeccionar.
> - [ ] El golden set pasa el validador.
> - [ ] Las métricas evalúan respuesta, cita y herramienta utilizada.

