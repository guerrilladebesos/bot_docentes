import os
import requests

from config import SERP_API_KEY

SERP_URL = "https://serpapi.com/search.json"
DOMINIO = "educantabria.es"


def buscar_web(pregunta, max_resultados=2):
    """
    Busca información adicional en Internet utilizando exclusivamente
    el dominio oficial educantabria.es.

    Devuelve como máximo 2 resultados.
    """
    if not SERP_API_KEY:
        return []

    try:
        # Restringimos explícitamente la búsqueda al dominio de Educantabria.
        consulta = f"{pregunta} site:{DOMINIO}"

        params = {
            "engine": "google",
            "q": consulta,
            "api_key": SERP_API_KEY,
            "num": max_resultados,
            "hl": "es",
            "gl": "es",
        }

        respuesta = requests.get(
            SERP_URL,
            params=params,
            timeout=15
        )

        respuesta.raise_for_status()
        datos = respuesta.json()

        resultados = []

        for resultado in datos.get("organic_results", []):
            enlace = resultado.get("link")
            titulo = resultado.get("title")

            if not enlace or not titulo:
                continue

            # Comprobación adicional de seguridad:
            # solo aceptamos URLs pertenecientes a educantabria.es.
            if "educantabria.es" not in enlace.lower():
                continue

            resultados.append({
                "titulo": titulo,
                "url": enlace,
                "descripcion": resultado.get("snippet", "")
            })

            if len(resultados) >= max_resultados:
                break

        return resultados

    except requests.RequestException:
        return []
    except Exception:
        return []
