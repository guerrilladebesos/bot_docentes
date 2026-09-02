from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters
)

from config import TELEGRAM_TOKEN
from buscador import buscar
from ia import consultar_ia


# ==========================================================
# MENSAJE DE AYUDA
# ==========================================================

MENSAJE_AYUDA = """
👋 Hola.

Soy el asistente jurídico para el profesorado de Cantabria.

Puedes preguntarme sobre:

• Permisos y licencias
• Reducciones de jornada
• Vacaciones
• Profesorado interino
• Oposiciones
• Retribuciones
• Normativa educativa
• Procedimientos administrativos

Escribe tu consulta con lenguaje natural.

Ejemplos:

• ¿Cuántos días me corresponden por fallecimiento de mi padre?

• Soy interino. ¿Puedo pedir excedencia?

• ¿Qué documentación necesito para una reducción de jornada?
"""


# ==========================================================
# RESPONDER
# ==========================================================

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):

    pregunta = update.message.text.strip()

    if not pregunta:
        return

    print("=" * 70)
    print("Pregunta:", pregunta)

    # ------------------------------------------------------
    # Buscar fragmentos
    # ------------------------------------------------------

    resultados = buscar(pregunta)

    if not resultados:

        await update.message.reply_text(
            "No he encontrado información en la base documental."
        )

        return

    print(f"Fragmentos encontrados: {len(resultados)}")

    # ------------------------------------------------------
    # Consultar IA
    # ------------------------------------------------------

    try:

        respuesta = consultar_ia(
            pregunta,
            resultados
        )

    except Exception as e:

        respuesta = f"Error consultando la IA:\n\n{e}"

    # ------------------------------------------------------
    # Telegram tiene un límite de 4096 caracteres
    # ------------------------------------------------------

    LIMITE = 4000

    if len(respuesta) <= LIMITE:

        await update.message.reply_text(respuesta)

    else:

        for i in range(0, len(respuesta), LIMITE):

            await update.message.reply_text(
                respuesta[i:i + LIMITE]
            )


# ==========================================================
# COMANDO /start
# ==========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(MENSAJE_AYUDA)


# ==========================================================
# ARRANQUE
# ==========================================================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        responder
    )
)

app.add_handler(
    MessageHandler(
        filters.COMMAND,
        start
    )
)

print()
print("=" * 70)
print("ASISTENTE JURÍDICO DOCENTE")
print("=" * 70)
print("Bot iniciado correctamente.")
print()

app.run_polling(drop_pending_updates=True)