import PyPDF2
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# 🔑 TOKEN TELEGRAM
TELEGRAM_TOKEN = "8715967826:AAFlTRYeY_HlZoSL4kzKVtpgccssTMS76VA"

# 📄 Leer PDF completo
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

# 🔍 Buscar en PDF
def buscar_en_pdf(pregunta):
    pregunta = pregunta.lower()
    texto = texto_pdf.lower()

    palabras = pregunta.split()
    resultados = []

    for palabra in palabras:
        if palabra in texto:
            indice = texto.find(palabra)
            inicio = max(0, indice - 500)
            fin = indice + 1000
            fragmento = texto_pdf[inicio:fin]
            resultados.append(fragmento)

    if resultados:
        return "\n---\n".join(resultados[:2])
    else:
        return None

# 🤖 Responder
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pregunta = update.message.text

    resultado = buscar_en_pdf(pregunta)

    if resultado:
        respuesta = f"""
📄 Fragmento de la normativa:

{resultado}

ℹ️ Texto extraído directamente del documento oficial.
"""
    else:
        respuesta = "No he encontrado información en el documento."

    await update.message.reply_text(respuesta)

# 🚀 Arranque
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

print("Bot funcionando (modo PDF)...")
app.run_polling()