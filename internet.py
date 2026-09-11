import requests
from urllib.parse import urlparse

from config import SERP_API_KEY

SERP_URL = "https://serpapi.com/search.json"

# Fuentes permitidas:
# 1. Portal educativo oficial de Cantabria
# 2. Federación de Enseñanza de CCOO de Cantabria
DOMINIOS_PERMITIDOS = (
    "educantabria.es",
    "cantabria.fe.ccoo.es",
)

MAX_RESULTADOS = 3


def es_dominio_permitido(url):
    """Comprueba que la URL pertenece a una de las fuentes autorizadas."""
    try:
        hostname = urlparse(url).hostname

        if not hostname:
            return False

        hostname = hostname.lower().rstrip(".")

        return any(
            hostname == dominio
            or hostname.endswith("." + dominio)
            for dominio in DOMINIOS_PERMITIDOS
        )

    except Exception:
        return False


def buscar_web(pregunta, max_resultados=3):
    """
    Busca información adicional en Internet exclusivamente en:

    - educantabria.es
    - cantabria.fe.ccoo.es

    Devuelve como máximo 3 enlaces.
    """

    if not SERP_API_KEY:
        print("SERP_API_KEY no está configurada.")
        return []

    # Límite absoluto: nunca se devolverán más de 3 resultados.
    limite = 3

    try:
        # Google/SerpAPI acepta OR para buscar simultáneamente
        # en los dos dominios autorizados.
        consulta = (
            f"{pregunta} "
            f"(site:educantabria.es OR site:cantabria.fe.ccoo.es)"
        )

        params = {
            "engine": "google",
            "q": consulta,
            "api_key": SERP_API_KEY,
            "num": limite,
            "hl": "es",
            "gl": "es",
        }

        respuesta = requests.get(
            SERP_URL,
            params=params,
            timeout=20
        )

        respuesta.raise_for_status()
        datos = respuesta.json()

        if datos.get("error"):
            print("Error de SerpAPI:", datos["error"])
            return []

        resultados = []

        for resultado in datos.get("organic_results", []):
            enlace = resultado.get("link")
            titulo = resultado.get("title")

            if not enlace or not titulo:
                continue

            # Segunda barrera de seguridad:
            # aunque Google ignore parcialmente el filtro site:,
            # aquí rechazamos cualquier dominio no autorizado.
            if not es_dominio_permitido(enlace):
                continue

            resultados.append({
                "titulo": titulo,
                "url": enlace,
                "descripcion": resultado.get("snippet", "")
            })

            if len(resultados) >= limite:
                break

        print(f"Resultados web autorizados: {len(resultados)}")

        return resultados

    except requests.RequestException as e:
        print(f"Error de conexión con SerpAPI: {e}")
        return []

    except Exception as e:
        print(f"Error en búsqueda web: {e}")
        return []
