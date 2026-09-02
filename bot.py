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

    print("=" * 70)
    print("Pregunta:", pregunta)

    # ==========================================
    # 1. BÚSQUEDA EN LA BASE DOCUMENTAL
    # ==========================================

    try:
        resultados = buscar(pregunta)

    except Exception as e:

        print(f"Error en búsqueda documental: {e}")

        resultados = []

    # ==========================================
    # 2. BÚSQUEDA ADICIONAL EN INTERNET
    # ==========================================

    try:

        enlaces = buscar_web(
            pregunta,
            max_resultados=5
        )

    except Exception as e:

        print(f"Error en búsqueda web: {e}")

        enlaces = []

    # ==========================================
    # 3. RESPUESTA BASADA EN LA BASE DOCUMENTAL
    # ==========================================

    if resultados:

        print(
            f"Fragmentos encontrados: "
            f"{len(resultados)}"
        )

        try:

            respuesta = consultar_ia(
                pregunta,
                resultados
            )

        except Exception as e:

            respuesta = (
                "He encontrado información en la "
                "base documental, pero se produjo un "
                "error al elaborar la respuesta.\n\n"
                f"Error: {e}"
            )

    else:

        respuesta = (
            "📚 No he encontrado información suficiente "
            "en la base documental propia."
        )

    # ==========================================
    # 4. AÑADIR RESULTADOS DE INTERNET
    # ==========================================

    if enlaces:

        respuesta += (
            "\n\n"
            "────────────────────────\n"
            "🌐 FUENTES ADICIONALES\n"
            "────────────────────────\n\n"
        )

        for i, enlace in enumerate(
            enlaces,
            start=1
        ):

            titulo = enlace.get(
                "titulo",
                "Sin título"
            )

            url = enlace.get(
                "url",
                ""
            )

            respuesta += (
                f"{i}. {titulo}\n"
                f"{url}\n\n"
            )

    # ==========================================
    # 5. SI NO HAY NADA
    # ==========================================

    if not resultados and not enlaces:

        respuesta = (
            "No he encontrado información relevante "
            "ni en la base documental propia ni en "
            "las fuentes consultadas en Internet."
        )

    # ==========================================
    # 6. ENVIAR RESPUESTA
    # ==========================================

    await enviar_largo(
        update,
        respuesta
    )