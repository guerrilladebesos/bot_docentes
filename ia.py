import hashlib
import os
import threading
import time

import requests


# ============================================================
# CONFIGURACIÓN
# ============================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Utilizamos el modelo que Google indicó en el error recibido.
MODEL = "gemini-3.6-flash"

# API REST estándar de Gemini.
URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL}:generateContent"
)

MAX_FRAGMENTOS = 5
MAX_CARACTERES_POR_FRAGMENTO = 4500
MAX_CARACTERES_CONTEXTO = 18000
MAX_TOKENS_SALIDA = 1500

MAX_REINTENTOS = 4
ESPERA_INICIAL = 2

CACHE_MAXIMO = 100
_cache = {}
_cache_lock = threading.Lock()


def construir_contexto(fragmentos):
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
    retry_after = response.headers.get("Retry-After")

    if retry_after:
        try:
            return max(float(retry_after), 1)
        except (TypeError, ValueError):
            pass

    return ESPERA_INICIAL * (2 ** (intento - 1))


def _diagnostico_api_key():
    """
    Diagnóstico seguro:
    nunca imprime la API key completa.
    """
    if not GEMINI_API_KEY:
        return {
            "presente": False,
            "longitud": 0,
            "prefijo": "NO_DEFINIDA",
        }

    return {
        "presente": True,
        "longitud": len(GEMINI_API_KEY),
        "prefijo": GEMINI_API_KEY[:3],
        "tiene_espacios_extremos": (
            GEMINI_API_KEY != GEMINI_API_KEY.strip()
        ),
    }


def _diagnostico_respuesta(response):
    """
    Devuelve información útil del error sin exponer credenciales.
    """
    try:
        datos = response.json()
    except ValueError:
        datos = None

    diagnostico = {
        "status_code": response.status_code,
        "content_type": response.headers.get("Content-Type"),
        "retry_after": response.headers.get("Retry-After"),
    }

    if isinstance(datos, dict):
        error = datos.get("error", {})

        if isinstance(error, dict):
            diagnostico["error_status"] = error.get("status")
            diagnostico["error_message"] = error.get("message")
            diagnostico["error_reason"] = error.get("reason")
            diagnostico["error_code"] = error.get("code")

            detalles = error.get("details")

            if isinstance(detalles, list):
                razones = []

                for detalle in detalles:
                    if isinstance(detalle, dict):
                        razon = detalle.get("reason")
                        if razon:
                            razones.append(str(razon))

                if razones:
                    diagnostico["detail_reasons"] = razones

    return diagnostico


def consultar_ia(pregunta, fragmentos):
    """
    Consulta Gemini.

    Mantiene exactamente la misma interfaz que las versiones anteriores,
    por lo que bot.py no necesita cambios.
    """

    diagnostico_key = _diagnostico_api_key()

    if not diagnostico_key["presente"]:
        return (
            "ERROR DE CONFIGURACIÓN DE GEMINI\n\n"
            "GEMINI_API_KEY no está definida en el entorno.\n\n"
            "Diagnóstico seguro:\n"
            f"Clave presente: {diagnostico_key['presente']}"
        )

    if diagnostico_key.get("tiene_espacios_extremos"):
        return (
            "ERROR DE CONFIGURACIÓN DE GEMINI\n\n"
            "GEMINI_API_KEY contiene espacios al principio o al final. "
            "Corrige la variable en Railway."
        )

    contexto = construir_contexto(fragmentos)

    clave = _clave_cache(pregunta, contexto)
    respuesta_cache = _obtener_cache(clave)

    if respuesta_cache is not None:
        print("Gemini: respuesta recuperada de caché.")
        return respuesta_cache

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
indícalo expresamente.
"""

    prompt_usuario = f"""
PREGUNTA DEL USUARIO:

{pregunta}

DOCUMENTACIÓN ENCONTRADA:

{contexto}

Redacta la respuesta basándote exclusivamente en esta documentación.
"""

    data = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            system_instruction
                            + "\n\n"
                            + prompt_usuario
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": MAX_TOKENS_SALIDA,
        },
    }

    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json",
    }

    print(
        "Gemini diagnóstico: "
        f"modelo={MODEL}, "
        f"clave_presente={diagnostico_key['presente']}, "
        f"longitud_clave={diagnostico_key['longitud']}, "
        f"prefijo={diagnostico_key['prefijo']}"
    )

    ultimo_error = None

    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            response = requests.post(
                URL,
                headers=headers,
                json=data,
                timeout=60,
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
                            "Gemini no devolvió texto en la respuesta."
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

            diagnostico = _diagnostico_respuesta(response)

            # ----------------------------------------------------
            # 401: MOSTRAR EL MOTIVO REAL
            # ----------------------------------------------------

            if response.status_code == 401:
                print(
                    "GEMINI 401 DIAGNÓSTICO:",
                    diagnostico,
                )

                return (
                    "ERROR DE AUTENTICACIÓN DE GEMINI (401)\n\n"
                    "Google ha rechazado la credencial.\n\n"
                    "DIAGNÓSTICO:\n"
                    f"- Modelo: {MODEL}\n"
                    f"- Clave presente: "
                    f"{diagnostico_key['presente']}\n"
                    f"- Longitud de clave: "
                    f"{diagnostico_key['longitud']}\n"
                    f"- Prefijo: "
                    f"{diagnostico_key['prefijo']}\n"
                    f"- Estado: "
                    f"{diagnostico.get('error_status', 'no indicado')}\n"
                    f"- Motivo: "
                    f"{diagnostico.get('error_reason', 'no indicado')}\n"
                    f"- Código: "
                    f"{diagnostico.get('error_code', 'no indicado')}\n"
                    f"- Mensaje de Google: "
                    f"{diagnostico.get('error_message', 'no indicado')}\n"
                    f"- Retry-After: "
                    f"{diagnostico.get('retry_after', 'no indicado')}\n"
                    f"- Razones adicionales: "
                    f"{diagnostico.get('detail_reasons', 'ninguna')}\n\n"
                    "La clave completa NO se muestra por seguridad."
                )

            # ----------------------------------------------------
            # 403
            # ----------------------------------------------------

            if response.status_code == 403:
                print(
                    "GEMINI 403 DIAGNÓSTICO:",
                    diagnostico,
                )

                return (
                    "ERROR DE PERMISOS DE GEMINI (403)\n\n"
                    "La clave existe, pero Google está rechazando "
                    "el acceso al servicio/modelo.\n\n"
                    f"Motivo: "
                    f"{diagnostico.get('error_reason', 'no indicado')}\n"
                    f"Mensaje: "
                    f"{diagnostico.get('error_message', 'no indicado')}"
                )

            # ----------------------------------------------------
            # 404
            # ----------------------------------------------------

            if response.status_code == 404:
                return (
                    "GEMINI NO ENCUENTRA EL MODELO (404)\n\n"
                    f"Modelo: {MODEL}\n\n"
                    f"Respuesta de Google:\n{response.text}"
                )

            # ----------------------------------------------------
            # 429
            # ----------------------------------------------------

            if response.status_code == 429:
                ultimo_error = response.text

                print(
                    "GEMINI 429:",
                    diagnostico,
                )

                if intento < MAX_REINTENTOS:
                    time.sleep(
                        _espera_retry(response, intento)
                    )
                    continue

                return (
                    "GEMINI ESTÁ LIMITANDO LAS PETICIONES (429).\n\n"
                    f"Se realizaron {MAX_REINTENTOS} intentos.\n\n"
                    f"Mensaje de Google:\n{response.text}"
                )

            # ----------------------------------------------------
            # OTROS 4XX
            # ----------------------------------------------------

            if 400 <= response.status_code < 500:
                return (
                    f"Error de Gemini ({response.status_code})\n\n"
                    f"{response.text}"
                )

            # ----------------------------------------------------
            # 5XX
            # ----------------------------------------------------

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
