import hashlib
import threading
import time

import requests

from config import MISTRAL_API_KEY

URL = "https://api.mistral.ai/v1/chat/completions"
MODEL = "mistral-small-latest"
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
            texto = texto[:MAX_CARACTERES_POR_FRAGMENTO] + "\n[Fragmento recortado]"
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
            contexto += "\n[Contexto limitado para controlar el consumo de tokens]\n"
            break
        contexto += bloque
        caracteres += len(bloque)
    return contexto


def _clave_cache(pregunta, contexto):
    contenido = f"{pregunta.strip()}\n---\n{contexto}"
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


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
    contexto = construir_contexto(fragmentos)
    clave = _clave_cache(pregunta, contexto)
    respuesta_cache = _obtener_cache(clave)
    if respuesta_cache is not None:
        return respuesta_cache

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }

    prompt_sistema = """
Eres una especialista en normativa educativa de Cantabria.

Debes responder EXCLUSIVAMENTE utilizando la información
contenida en los fragmentos proporcionados.

Normas:

1. No inventes información.

2. Si la respuesta no aparece en los fragmentos,
indica expresamente que no has encontrado base documental suficiente.

3. Cuando sea posible indica:
- documento
- páginas
- fundamento normativo

4. Responde de forma clara, rigurosa y directa.

5. Si existen varias normas relacionadas,
explica la diferencia.

6. Prioriza la respuesta concreta a la pregunta.
No repitas innecesariamente el contenido de los documentos.
"""

    prompt_usuario = f"""
Pregunta del usuario:

{pregunta}

Fragmentos encontrados:

{contexto}
"""

    data = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": prompt_usuario},
        ],
        "temperature": 0.1,
        "max_tokens": MAX_TOKENS_SALIDA,
    }

    ultimo_error = None

    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            response = requests.post(URL, headers=headers, json=data, timeout=60)

            if response.status_code == 200:
                try:
                    respuesta = response.json()["choices"][0]["message"]["content"]
                    if not respuesta:
                        return "Mistral no devolvió contenido en la respuesta."
                    _guardar_cache(clave, respuesta)
                    return respuesta
                except (KeyError, IndexError, TypeError, ValueError) as e:
                    return f"Respuesta inesperada de Mistral:\n\n{e}"

            if response.status_code == 429:
                ultimo_error = response.text
                if intento < MAX_REINTENTOS:
                    time.sleep(_espera_retry(response, intento))
                    continue
                return (
                    "Mistral está limitando temporalmente las peticiones (429).\n\n"
                    f"Se realizaron {MAX_REINTENTOS} intentos.\n\n"
                    "El bot ha reducido el contexto y limitado la respuesta "
                    "para controlar el consumo. Espera un poco y vuelve a "
                    "realizar la consulta."
                )

            if 400 <= response.status_code < 500:
                return f"Error de Mistral ({response.status_code})\n\n{response.text}"

            ultimo_error = response.text
            if intento < MAX_REINTENTOS:
                time.sleep(_espera_retry(response, intento))
                continue
            return f"Error de servidor de Mistral ({response.status_code})\n\n{response.text}"

        except requests.exceptions.Timeout as e:
            ultimo_error = str(e)
            if intento < MAX_REINTENTOS:
                time.sleep(ESPERA_INICIAL * (2 ** (intento - 1)))
                continue
            return (
                "Mistral no respondió dentro del tiempo esperado después de "
                f"{MAX_REINTENTOS} intentos."
            )

        except requests.exceptions.RequestException as e:
            ultimo_error = str(e)
            if intento < MAX_REINTENTOS:
                time.sleep(ESPERA_INICIAL * (2 ** (intento - 1)))
                continue
            return f"Error de conexión con Mistral:\n\n{e}"

        except Exception as e:
            return f"Error consultando Mistral:\n\n{e}"

    return f"Error consultando Mistral:\n\n{ultimo_error}"
