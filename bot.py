import json
import PyPDF2
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# 🔑 CLAVES

import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")


# 📚 Cargar base de permisos
with open("permisos_cantabria_pro.json", "r", encoding="utf-8") as f:
    permisos = json.load(f)

# 🔍 Buscar en JSON
def buscar_respuesta_avanzada(pregunta):
    pregunta = pregunta.lower()

    mejor = None
    max_score = 0

    for permiso in permisos:
        score = 0

        # Coincidencias por palabras clave
        for palabra in permiso.get("palabras_clave", []):
            if palabra in pregunta:
                score += 2

        # Coincidencias por título
        if permiso["titulo"].lower() in pregunta:
            score += 3

        if score > max_score:
            max_score = score
            mejor = permiso

    return mejor

# 📄 Leer PDF
def leer_pdf():
    texto = ""
    with open("permisos_cantabria.pdf", "rb") as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            contenido = page.extract_text()
            if contenido:
                texto += contenido + "\n"
    return texto

texto_pdf = leer_pdf()

# 🔎 Buscar en PDF
def buscar_en_pdf(pregunta):
    pregunta = pregunta.lower()
    texto = texto_pdf.lower()

    for palabra in pregunta.split():
        if palabra in texto:
            indice = texto.find(palabra)
            inicio = max(0, indice - 200)
            fin = indice + 500
            return texto_pdf[inicio:fin]

    return None

# 🤖 LLAMADA A MISTRAL (SIN LIBRERÍA)
def consultar_mistral(pregunta, contexto):
    url = "https://api.mistral.ai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "mistral-small-latest",
        "messages": [
            {
                "role": "system",
                "content": "Eres experta en normativa docente de Cantabria. Responde con precisión jurídica y base legal."
            },
            {
                "role": "user",
                "content": f"Pregunta: {pregunta}\n\nTexto legal:\n{contexto}"
            }
        ]
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return f"Error en Mistral: {response.text}"

# 🤖 FUNCIÓN PRINCIPAL
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pregunta = update.message.text

    resultado = buscar_respuesta_avanzada(pregunta)

    if resultado:
        respuesta = f"""
📌 {resultado['titulo']}

🧾 Descripción:
{resultado['descripcion']}

⏱️ Duración:
{resultado.get('duracion', 'No especificada')}

⚖️ Base legal:
{resultado['normativa']}
"""
    else:
        contexto_pdf = buscar_en_pdf(pregunta)

        if contexto_pdf:
            respuesta = consultar_mistral(pregunta, contexto_pdf)
        else:
            respuesta = "No he encontrado información en la normativa."

    await update.message.reply_text(respuesta)

# 🚀 ARRANQUE
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

print("Bot funcionando con Mistral (sin librerías problemáticas)...")
app.run_polling()