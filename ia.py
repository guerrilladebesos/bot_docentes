import time
import requests

from config import MISTRAL_API_KEY


URL = "https://api.mistral.ai/v1/chat/completions"

# Número máximo de intentos ante errores temporales de Mistral.
MAX_REINTENTOS = 4

# Espera inicial entre reintentos (segundos).
ESPERA_INICIAL = 2


def construir_contexto(fragmentos):
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


def consultar_ia(pregunta, fragmentos):
    contexto = construir_contexto(fragmentos)

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
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

4. Responde de forma clara y rigurosa.

5. Si existen varias normas relacionadas,
explica la diferencia.
"""

    prompt_usuario = f"""
Pregunta del usuario:

{pregunta}


Fragmentos encontrados:

{contexto}
"""

    data = {
        "model": "mistral-small-latest",
        "messages": [
            {
                "role": "system",
                "content": prompt_sistema
            },
            {
                "role": "user",
                "content": prompt_usuario
            }
        ],
        "temperature": 0.1
    }

    ultimo_error = None

    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            response = requests.post(
                URL,
                headers=headers,
                json=data,
                timeout=60
            )

            # Petición correcta.
            if response.status_code == 200:
                try:
                    return response.json()["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError, ValueError) as e:
                    return f"Respuesta inesperada de Mistral:\n\n{e}"

            # Límite de peticiones: esperamos y volvemos a intentar.
            if response.status_code == 429:
                ultimo_error = response.text

                if intento < MAX_REINTENTOS:
                    espera = ESPERA_INICIAL * (2 ** (intento - 1))
                    time.sleep(espera)
                    continue

                return (
                    "Mistral está limitando temporalmente las peticiones "
                    f"(429). Se realizaron {MAX_REINTENTOS} intentos.\n\n"
                    "Espera unos segundos y vuelve a realizar la consulta."
                )

            # Otros errores HTTP: no tiene sentido repetir automáticamente.
            return (
                f"Error de Mistral ({response.status_code})\n\n"
                f"{response.text}"
            )

        except requests.exceptions.Timeout as e:
            ultimo_error = str(e)

            if intento < MAX_REINTENTOS:
                espera = ESPERA_INICIAL * (2 ** (intento - 1))
                time.sleep(espera)
                continue

            return (
                "Mistral no respondió dentro del tiempo esperado después de "
                f"{MAX_REINTENTOS} intentos."
            )

        except requests.exceptions.RequestException as e:
            ultimo_error = str(e)

            if intento < MAX_REINTENTOS:
                espera = ESPERA_INICIAL * (2 ** (intento - 1))
                time.sleep(espera)
                continue

            return f"Error de conexión con Mistral:\n\n{e}"

        except Exception as e:
            return f"Error consultando Mistral:\n\n{e}"

    return f"Error consultando Mistral:\n\n{ultimo_error}"
