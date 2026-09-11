import hashlib
import os
import threading
import time

import requests


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

MODEL = "gemini-3.6-flash"

URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL}:generateContent"
)

# ============================================================
# CONFIGURACIÓN DE RESPUESTA
# ============================================================

# Restaurado el comportamiento amplio del ia.py original:
# se envían TODOS los fragmentos encontrados y su texto completo.
# No se recortan fragmentos ni el contexto documental.

MAX_TOKENS_SALIDA = 4000

# Reintentos para errores temporales.
MAX_REINTENTOS = 4
ESPERA_INICIAL = 2

# Caché local para preguntas repetidas.
CACHE_MAXIMO = 100
_cache = {}
_cache_lock = threading.Lock()


def construir_contexto(fragmentos):
    """
    Construye el contexto utilizando TODOS los fragmentos encontrados,
    sin limitar número de fragmentos ni longitud del texto.
    """
    contexto = ""

    for i, fragmento in enumerate(fragmentos, start=1):
        contexto += f"""
=============================
FRAGMENTO {i}

Documento:
{fragmento.get("documento", "")}

Categoría:
{fragmento.get("categoria", "")}

Páginas:
{fragmento.get("pagina_inicio", "?")} - {fragmento.get("pagina_fin", "?")}

Texto:
{fragmento.get("texto", "")}

"""

    return contexto


def _clave_cache(pregunta, contexto):
    contenido = f"{pregunta.strip()}\n---\n{contexto}"
    return hashlib.sha256(
        contenido.encode("utf-8")
    ).hexdigest()


def _obtener_cache(clave):
    with _cache_lock:
        return _cache.get(clave)


def _guardar_cache(clave, respuesta):
    with _cache_lock:
        if len(_cache) >= CACHE_MAXIMO:
            primera_clave = next(iter(_cache))
            del _cache[primera_clave]

        _cache[clave] = respuesta


def _espera_retry(response, intento):
    retry_after = response.headers.get("Retry-After")

    if retry_after:
        try:
            return max(float(retry_after), 1)
        except (TypeError, ValueError):
            pass

    return ESPERA_INICIAL * (2 ** (intento - 1))


def consultar_ia(pregunta, fragmentos):
    """
    Genera una respuesta amplia con Gemini.

    Mantiene la misma interfaz que las versiones anteriores,
    por lo que bot.py no necesita cambios.
    """

    if not GEMINI_API_KEY:
        return (
            "Error de configuración: no se ha encontrado "
            "GEMINI_API_KEY."
        )

    contexto = construir_contexto(fragmentos)

    # Evita repetir una llamada si llega exactamente la misma
    # pregunta con exactamente el mismo contexto.
    clave = _clave_cache(pregunta, contexto)
    respuesta_cache = _obtener_cache(clave)

    if respuesta_cache is not None:
        return respuesta_cache

    system_instruction = """
Eres una especialista en normativa educativa de Cantabria.

Debes responder utilizando exclusivamente la información
contenida en los fragmentos documentales proporcionados.

Normas:

1. No inventes información.

2. Si la respuesta no aparece en los fragmentos,
indica expresamente que no has encontrado base documental suficiente.

3. Cuando sea posible indica:
- documento
- páginas
- fundamento normativo
- artículo, disposición, apartado o epígrafe relevante.

4. Responde de forma clara, rigurosa y suficientemente desarrollada.

5. Si existen varias normas relacionadas,
explica claramente la diferencia entre ellas.

6. Responde de forma completa a la pregunta.
No reduzcas innecesariamente la respuesta por brevedad.

7. Utiliza los diferentes fragmentos disponibles para
contrastar y completar la respuesta.

8. Si los fragmentos contienen información relacionada
pero no suficiente para responder con seguridad,
indícalo expresamente.

9. No añadas como hechos jurídicos datos que no estén
respaldados por la documentación proporcionada.

10. Cuando la pregunta requiera una explicación,
desarrolla los aspectos relevantes y, cuando proceda,
incluye requisitos, excepciones, plazos, destinatarios,
procedimiento y fundamento normativo que aparezcan
en los documentos.
"""

    prompt_usuario = f"""
PREGUNTA DEL USUARIO:

{pregunta}

FRAGMENTOS DOCUMENTALES ENCONTRADOS:

{contexto}

Elabora una respuesta completa, rigurosa y útil para un
docente de la enseñanza pública de Cantabria.

Utiliza toda la documentación relevante proporcionada.
Si varios fragmentos aportan información complementaria,
intégrala en una única respuesta estructurada.
"""

    data = {
        "systemInstruction": {
            "parts": [
                {
                    "text": system_instruction
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt_usuario
                    }
                ]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": MAX_TOKENS_SALIDA
        }
    }

    headers = {
    "Content-Type": "application/json",
    "x-goog-api-key": GEMINI_API_KEY
}

    ultimo_error = None

    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            response = requests.post(
                URL,
                headers=headers,
                json=data,
                timeout=90
            )

            if response.status_code == 200:
                try:
                    respuesta_json = response.json()

                    respuesta = (
                        respuesta_json["candidates"][0]
                        ["content"]["parts"][0]["text"]
                    )

                    if not respuesta:
                        return (
                            "Gemini no devolvió contenido en la respuesta."
                        )

                    _guardar_cache(clave, respuesta)

                    return respuesta

                except (
                    KeyError,
                    IndexError,
                    TypeError,
                    ValueError
                ) as e:
                    return (
                        "Respuesta inesperada de Gemini:\n\n"
                        f"{e}\n\n"
                        f"Respuesta recibida:\n{response.text}"
                    )

            if response.status_code == 429:
                ultimo_error = response.text

                if intento < MAX_REINTENTOS:
                    time.sleep(
                        _espera_retry(response, intento)
                    )
                    continue

                return (
                    "Gemini está limitando temporalmente las peticiones "
                    "(429).\n\n"
                    f"Se realizaron {MAX_REINTENTOS} intentos.\n\n"
                    "Espera unos segundos y vuelve a realizar la consulta."
                )

            if response.status_code in (401, 403):
                return (
                    f"Error de autenticación/permisos de Gemini "
                    f"({response.status_code}).\n\n"
                    f"{response.text}"
                )

            if response.status_code == 404:
                return (
                    "Gemini no encuentra el modelo solicitado (404).\n\n"
                    f"Modelo: {MODEL}\n\n"
                    f"Respuesta de Google:\n{response.text}"
                )

            if 400 <= response.status_code < 500:
                return (
                    f"Error de Gemini ({response.status_code})\n\n"
                    f"{response.text}"
                )

            ultimo_error = response.text

            if intento < MAX_REINTENTOS:
                time.sleep(
                    _espera_retry(response, intento)
                )
                continue

            return (
                f"Error de servidor de Gemini "
                f"({response.status_code})\n\n"
                f"{response.text}"
            )

        except requests.exceptions.Timeout as e:
            ultimo_error = str(e)

            if intento < MAX_REINTENTOS:
                time.sleep(
                    ESPERA_INICIAL * (2 ** (intento - 1))
                )
                continue

            return (
                "Gemini no respondió dentro del tiempo esperado "
                f"después de {MAX_REINTENTOS} intentos."
            )

        except requests.exceptions.RequestException as e:
            ultimo_error = str(e)

            if intento < MAX_REINTENTOS:
                time.sleep(
                    ESPERA_INICIAL * (2 ** (intento - 1))
                )
                continue

            return f"Error de conexión con Gemini:\n\n{e}"

        except Exception as e:
            return f"Error consultando Gemini:\n\n{e}"

    return f"Error consultando Gemini:\n\n{ultimo_error}"
