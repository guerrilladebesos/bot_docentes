from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

from config import TELEGRAM_TOKEN
from buscador import buscar
from ia import consultar_ia
from internet import buscar_web

MENSAJE_AYUDA = """👋 Hola.

Soy el asistente jurídico para el profesorado de Cantabria.
Puedes preguntarme sobre permisos, licencias, oposiciones, interinos,
retribuciones, normativa educativa y procedimientos administrativos.
"""

LIMITE_TELEGRAM = 4000

async def enviar_largo(update: Update, texto: str):
    for i in range(0, len(texto), LIMITE_TELEGRAM):
        await update.message.reply_text(texto[i:i+LIMITE_TELEGRAM])

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    pregunta = update.message.text.strip()
    if not pregunta:
        return

    try:
        resultados = buscar(pregunta)
    except Exception as e:
        await update.message.reply_text(f"Error en la búsqueda:\n\n{e}")
        return

    if not resultados:
        enlaces = buscar_web(pregunta)
        if enlaces:
            mensaje = "❌ No he encontrado información en la base documental.\n\n🌐 Recursos encontrados:\n\n"
            for i, e in enumerate(enlaces, 1):
                mensaje += f"{i}. {e.get('titulo','Sin título')}\n{e.get('url','')}\n\n"
            await enviar_largo(update, mensaje)
        else:
            await update.message.reply_text("No he encontrado información en la base documental ni en Internet.")
        return

    try:
        respuesta = consultar_ia(pregunta, resultados)
    except Exception as e:
        respuesta = f"Error consultando la IA:\n\n{e}"

    try:
        if len(resultados) < 3:
            enlaces = buscar_web(pregunta, max_resultados=3)
            if enlaces:
                respuesta += "\n\n🌐 Recursos oficiales relacionados:\n"
                for e in enlaces:
                    respuesta += f"\n• {e.get('titulo','Sin título')}\n{e.get('url','')}"
    except Exception:
        pass

    await enviar_largo(update, respuesta)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(MENSAJE_AYUDA)

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    print("Bot iniciado correctamente.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
