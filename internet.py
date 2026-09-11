import requests
from urllib.parse import urlparse

from config import SERP_API_KEY

SERP_URL = "https://serpapi.com/search.json"
DOMINIO = "educantabria.es"
MAX_RESULTADOS = 2


def es_educantabria(url):
    """Comprueba que la URL pertenece realmente a educantabria.es."""
    try:
        hostname = urlparse(url).hostname
        if not hostname:
            return False

        hostname = hostname.lower().rstrip(".")

        return (
            hostname == DOMINIO
            or hostname.endswith("." + DOMINIO)
        )

    except Exception:
        return False


def buscar_web(pregunta, max_resultados=2):
    """
    Busca información adicional en Internet exclusivamente en
    educantabria.es.

    IMPORTANTE:
    Aunque bot.py llame a buscar_web(..., max_resultados=5),
    esta función impone un máximo real de 2 resultados.
    """

    if not SERP_API_KEY:
        print("SERP_API_KEY no está configurada.")
        return []

    # Límite ABSOLUTO: nunca devolver más de 2 resultados.
    limite = 2

    try:
        consulta = f"site:{DOMINIO} {pregunta}"

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

        # SerpAPI puede devolver un mensaje de error dentro del JSON
        # aunque HTTP sea 200.
        if datos.get("error"):
            print("Error de SerpAPI:", datos["error"])
            return []

        resultados = []

        for resultado in datos.get("organic_results", []):
            enlace = resultado.get("link")
            titulo = resultado.get("title")

            if not enlace or not titulo:
                continue

            # Segunda barrera: rechazamos cualquier URL que no sea
            # realmente de educantabria.es.
            if not es_educantabria(enlace):
                continue

            resultados.append({
                "titulo": titulo,
                "url": enlace,
                "descripcion": resultado.get("snippet", "")
            })

            # Límite absoluto.
            if len(resultados) >= limite:
                break

        print(f"Resultados web Educantabria: {len(resultados)}")

        return resultados

    except requests.RequestException as e:
        print(f"Error de conexión con SerpAPI: {e}")
        return []

    except Exception as e:
        print(f"Error en búsqueda web: {e}")
        return []
