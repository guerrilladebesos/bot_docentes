import hashlib
import os
import threading
import time

import requests


# ============================================================
# CONFIGURACIÓN DE GEMINI
# ============================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Modelo estable de Gemini adecuado para tareas de alta frecuencia.
MODEL = "gemini-2.5-flash"

URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL}:generateContent"
)

# ============================================================
# LÍMITES DE SEGURIDAD
# ============================================================

MAX_FRAGMENTOS = 5
MAX_CARACTERES_POR_FRAGMENTO = 4500
MAX_CARACTERES_CONTEXTO = 18000
MAX_TOKENS_SALIDA = 1500

# Reintentos para errores temporales.
MAX_REINTENTOS = 4
ESPERA_INICIAL = 2

# Caché local para preguntas repetidas.
CACHE_MAXIMO = 100
_cache = {}
_cache_lock = threading.Lock()


def construir_contexto(fragmentos):
    """
    Construye un contexto compacto con los fragmentos más relevantes.
    Limitar el contexto evita enviar información innecesaria al modelo.
    """
    contexto = ""
    caracteres = 0

    for i, fragmento in enumerate(fragmentos[:MAX_FRAGMENTOS], start=1):
        texto = str(fragmento.get("texto", "") or "")

        if len(texto) > MAX_CARACTERES_POR_FRAGMENTO:
            texto = (
                texto[:MAX_CARACTERES_POR_FRAGMENTO]
                + "\n[Fragmento recortado]"
            )

        bloque = f"""
=============================
FRAGMENTO {i}

Documento:
{fragmento.get("documento", "")}

Categoría:
{fragmento.get("categoria", "")}

Páginas:
{fragmento.get("pagina_inicio", "?")} - {fragmento.get("pagina_fin", "?")}

Texto:
{texto}

"""

        if caracteres + len(bloque) > MAX_CARACTERES_CONTEXTO:
            espacio = MAX_CARACTERES_CONTEXTO - caracteres

            if espacio <= 0:
                break

            contexto += bloque[:espacio]
            contexto += (
                "\n[Contexto limitado para controlar el consumo de tokens]\n"
            )
            break

        contexto += bloque
        caracteres += len(bloque)

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
    """
    Respeta Retry-After si Google lo proporciona.
    Si no, utiliza exponential backoff.
    """
    retry_after = response.headers.get("Retry-After")

    if retry_after:
        try:
            return max(float(retry_after), 1)

        except (TypeError, ValueError):
            pass

    return ESPERA_INICIAL * (2 ** (intento - 1))


def consultar_ia(pregunta, fragmentos):
    """
    Genera la respuesta utilizando Gemini en lugar de Mistral.

    La función conserva la misma interfaz que la anterior:
        consultar_ia(pregunta, fragmentos)

    Por tanto, bot.py no necesita cambios.
    """

    if not GEMINI_API_KEY:
        return (
            "Error de configuración: no se ha encontrado "
            "GEMINI_API_KEY."
        )

    contexto = construir_contexto(fragmentos)

    # Evita llamadas repetidas para la misma pregunta y contexto.
    clave = _clave_cache(pregunta, contexto)
    respuesta_cache = _obtener_cache(clave)

    if respuesta_cache is not None:
        return respuesta_cache

    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json",
    }

    system_instruction = """
Eres una especialista en normativa educativa de Cantabria.

Debes responder EXCLUSIVAMENTE utilizando la información
contenida en los fragmentos documentales proporcionados.

Normas obligatorias:

1. No inventes información.

2. Si la respuesta no aparece en los fragmentos,
indica expresamente que no has encontrado base documental suficiente.

3. Cuando sea posible indica:
- documento
- páginas
- fundamento normativo
- artículo, disposición, apartado o epígrafe relevante.

4. Responde de forma clara, rigurosa y directa.

5. Si existen varias normas relacionadas,
explica claramente la diferencia entre ellas.

6. Prioriza la respuesta concreta a la pregunta.

7. No añadas información externa que no aparezca
en los fragmentos proporcionados.

8. Si los fragmentos son insuficientes o contradictorios,
indícalo expresamente en lugar de completar la respuesta
con conocimientos propios.
"""

    prompt_usuario = f"""
PREGUNTA DEL USUARIO:

{pregunta}

DOCUMENTACIÓN ENCONTRADA:

{contexto}

Redacta la respuesta basándote exclusivamente en esta documentación.
"""

    data = {
        "system_instruction": {
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
            "temperature": 0.1,
            "maxOutputTokens": MAX_TOKENS_SALIDA,
        },
    }

    ultimo_error = None

    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            response = requests.post(
                URL,
                headers=headers,
                json=data,
                timeout=60,
            )

            # ----------------------------------------------------
            # RESPUESTA CORRECTA
            # ----------------------------------------------------

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
                    ValueError,
                ) as e:
                    return (
                        "Respuesta inesperada de Gemini:\n\n"
                        f"{e}\n\n"
                        f"Respuesta recibida:\n{response.text}"
                    )

            # ----------------------------------------------------
            # RATE LIMIT
            # ----------------------------------------------------

            if response.status_code == 429:
                ultimo_error = response.text

                if intento < MAX_REINTENTOS:
                    espera = _espera_retry(response, intento)
                    time.sleep(espera)
                    continue

                return (
                    "Gemini está limitando temporalmente las peticiones "
                    "(429).\n\n"
                    f"Se realizaron {MAX_REINTENTOS} intentos.\n\n"
                    "Espera unos segundos y vuelve a realizar la consulta."
                )

            # ----------------------------------------------------
            # ERRORES DE AUTENTICACIÓN
            # ----------------------------------------------------

            if response.status_code in (401, 403):
                return (
                    f"Error de autenticación de Gemini "
                    f"({response.status_code}).\n\n"
                    "Comprueba que GEMINI_API_KEY esté correctamente "
                    "configurada en Railway y que la API de Gemini "
                    "esté habilitada para el proyecto."
                )

            # ----------------------------------------------------
            # OTROS ERRORES 4XX
            # ----------------------------------------------------

            if 400 <= response.status_code < 500:
                return (
                    f"Error de Gemini ({response.status_code})\n\n"
                    f"{response.text}"
                )

            # ----------------------------------------------------
            # ERRORES 5XX
            # ----------------------------------------------------

            ultimo_error = response.text

            if intento < MAX_REINTENTOS:
                espera = _espera_retry(response, intento)
                time.sleep(espera)
                continue

            return (
                f"Error de servidor de Gemini "
                f"({response.status_code})\n\n"
                f"{response.text}"
            )

        except requests.exceptions.Timeout as e:
            ultimo_error = str(e)

            if intento < MAX_REINTENTOS:
                espera = ESPERA_INICIAL * (2 ** (intento - 1))
                time.sleep(espera)
                continue

            return (
                "Gemini no respondió dentro del tiempo esperado "
                f"después de {MAX_REINTENTOS} intentos."
            )

        except requests.exceptions.RequestException as e:
            ultimo_error = str(e)

            if intento < MAX_REINTENTOS:
                espera = ESPERA_INICIAL * (2 ** (intento - 1))
                time.sleep(espera)
                continue

            return f"Error de conexión con Gemini:\n\n{e}"

        except Exception as e:
            return f"Error consultando Gemini:\n\n{e}"

    return f"Error consultando Gemini:\n\n{ultimo_error}"
