import requests

from config import MISTRAL_API_KEY


URL = "https://api.mistral.ai/v1/chat/completions"


def construir_contexto(fragmentos):

    contexto = ""

    for i, fragmento in enumerate(fragmentos, start=1):

        contexto += f"""
=============================
FRAGMENTO {i}

Documento:
{fragmento.get("documento","")}

Categoría:
{fragmento.get("categoria","")}

Páginas:
{fragmento.get("pagina_inicio","?")} - {fragmento.get("pagina_fin","?")}

Texto:
{fragmento.get("texto","")}

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

    try:

        response = requests.post(
            URL,
            headers=headers,
            json=data,
            timeout=60
        )

        if response.status_code != 200:

            return f"Error de Mistral ({response.status_code})\n\n{response.text}"

        respuesta = response.json()["choices"][0]["message"]["content"]

        return respuesta

    except Exception as e:

        return f"Error consultando Mistral:\n\n{e}"