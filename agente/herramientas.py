"""Las cuatro herramientas. Las firmas son contrato: no se cambian."""

from __future__ import annotations

from langchain.tools import tool

from agente.corpus import cargar_secciones, cargar_xbrl
from agente.retrieval import buscar, formatear_fragmentos


def construir_herramientas() -> list:
    """Las cuatro @tool del día 10, con los docstrings que ya funcionaban."""
    secciones = cargar_secciones()
    xbrl = cargar_xbrl()

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
            ejercicios_txt = ", ".join(f"FY{e}" for e in ejercicios)
            items_txt = ", ".join(items)
            lineas.append(
                f"- {ticker} ({empresa}): ejercicios {ejercicios_txt}; "
                f"secciones disponibles: {items_txt}."
            )
        return "\n".join(lineas)

    @tool
    def get_xbrl_fact(ticker: str, fiscal_year: int, concept: str) -> str:
        """Devuelve el valor EXACTO de una magnitud financiera tal y como la
        compañía la reportó en XBRL.

        Es la fuente autorizada para cualquier cifra. Úsala SIEMPRE en lugar de
        leer un número del texto del informe.

        Args:
            ticker: Símbolo bursátil, p. ej. 'NVDA'.
            fiscal_year: Ejercicio fiscal reportado, p. ej. 2024.
            concept: Concepto en taxonomía US-GAAP, p. ej. 'Revenues',
                'NetIncomeLoss', 'Assets', 'OperatingIncomeLoss'.

        Devuelve el valor con su unidad y fecha de cierre, o un aviso explícito
        si la compañía no reportó ese concepto en ese ejercicio.
        """
        filas = xbrl[(xbrl.ticker == ticker)
                     & (xbrl.fiscal_year == int(fiscal_year))
                     & (xbrl.concept == concept)]
        if filas.empty:
            disponibles = sorted(
                xbrl[(xbrl.ticker == ticker)
                     & (xbrl.fiscal_year == int(fiscal_year))].concept.unique()
            )
            if not disponibles:
                return (f"No hay datos de {ticker} para FY{fiscal_year} en el "
                        f"corpus. Usa list_available para ver qué hay.")
            return (f"{ticker} no reportó '{concept}' en FY{fiscal_year}. "
                    f"Conceptos disponibles: {', '.join(disponibles)}")
        f = filas.iloc[0]
        return (f"{ticker} FY{fiscal_year} · {concept} = {f.value:,.0f} {f.unit} "
                f"(cierre de ejercicio {f.period_end}, según el {f.form})")

    @tool
    def search_filings(query: str, ticker: str | None = None,
                       fiscal_year: int | None = None,
                       item: str | None = None, k: int = 5) -> str:
        """Busca fragmentos de texto relevantes en los informes 10-K del corpus.

        Úsala para preguntas cualitativas: riesgos, estrategia, litigios,
        comentarios de la dirección. NO la uses para obtener cifras: para eso
        está get_xbrl_fact.

        Args:
            query: Qué buscar, en lenguaje natural.
            ticker: Filtra por compañía si la pregunta la menciona.
            fiscal_year: Filtra por ejercicio si la pregunta lo menciona.
            item: Filtra por sección: '1A' riesgos, '7' MD&A,
                '7A' riesgo de mercado, '8' estados financieros.
            k: Número de fragmentos a devolver.

        Devuelve k fragmentos, cada uno con su chunk_id para poder citarlo.
        """
        return formatear_fragmentos(
            buscar(query, ticker=ticker, fiscal_year=fiscal_year,
                   item=item, k=k)
        )

    @tool
    def read_section(ticker: str, fiscal_year: int, item: str) -> str:
        """Devuelve el TEXTO COMPLETO de una sección de un 10-K.

        Es una herramienta CARA: puede devolver decenas de miles de tokens.
        Úsala solo cuando search_filings devuelva fragmentos insuficientes y
        necesites el contexto entero de una sección concreta.

        Args:
            ticker: Símbolo bursátil, p. ej. 'META'.
            fiscal_year: Ejercicio fiscal, p. ej. 2025.
            item: '1A' riesgos, '7' MD&A, '7A' riesgo de mercado,
                '8' estados financieros.
        """
        filas = secciones[(secciones.ticker == ticker)
                          & (secciones.fiscal_year == int(fiscal_year))
                          & (secciones.item == item)]
        if filas.empty:
            return (f"No hay Item {item} de {ticker} FY{fiscal_year} en el "
                    f"corpus. Usa list_available para ver qué hay.")
        return filas.iloc[0].texto

    return [list_available, get_xbrl_fact, search_filings, read_section]
