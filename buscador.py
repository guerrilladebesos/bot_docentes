import json
from pathlib import Path

# ==========================================================
# CONFIGURACIÓN
# ==========================================================

CARPETA_CONOCIMIENTO = Path("conocimiento")

STOPWORDS = {
    "de", "la", "el", "los", "las",
    "y", "o", "a", "en",
    "un", "una",
    "por", "para",
    "con", "del",
    "que", "se", "su", "al"
}


# ==========================================================
# CARGAR BASE DOCUMENTAL
# ==========================================================

def cargar_base_documental():

    base = []

    archivos = list(CARPETA_CONOCIMIENTO.rglob("*_chunks.json"))

    print(f"\nSe han encontrado {len(archivos)} base(s) documental(es).\n")

    for archivo in archivos:

        try:

            with open(archivo, "r", encoding="utf8") as f:

                datos = json.load(f)

                base.extend(datos)

                print(f"✔ Cargado {archivo.name} ({len(datos)} fragmentos)")

        except Exception as e:

            print(f"❌ Error leyendo {archivo}: {e}")

    print(f"\nTotal de fragmentos cargados: {len(base)}\n")

    return base


BASE_DOCUMENTAL = cargar_base_documental()


# ==========================================================
# CALCULAR PUNTUACIÓN
# ==========================================================

def puntuacion(chunk, pregunta):

    pregunta = pregunta.lower()

    palabras = [
        p for p in pregunta.split()
        if p not in STOPWORDS
    ]

    texto = chunk.get("texto", "").lower()

    titulo = chunk.get("titulo", "").lower()

    categoria = chunk.get("categoria", "").lower()

    puntos = 0

    # -----------------------------------
    # Coincidencias en el título
    # -----------------------------------

    for palabra in palabras:

        if palabra in titulo:

            puntos += 15

    # -----------------------------------
    # Coincidencias en el texto
    # -----------------------------------

    for palabra in palabras:

        if palabra in texto:

            puntos += 5

    # -----------------------------------
    # Coincidencia exacta
    # -----------------------------------

    if pregunta in texto:

        puntos += 20

    # -----------------------------------
    # Coincidencia con la categoría
    # -----------------------------------

    for palabra in palabras:

        if palabra == categoria:

            puntos += 10

    return puntos


# ==========================================================
# BUSCADOR
# ==========================================================

def buscar(pregunta, limite=5):

    resultados = []

    for chunk in BASE_DOCUMENTAL:

        puntos = puntuacion(chunk, pregunta)

        if puntos > 0:

            resultado = chunk.copy()

            resultado["puntuacion"] = puntos

            resultados.append(resultado)

    resultados.sort(

        key=lambda x: x["puntuacion"],

        reverse=True

    )

    return resultados[:limite]


# ==========================================================
# PRUEBA
# ==========================================================

if __name__ == "__main__":

    print("=" * 60)
    print("BUSCADOR DOCUMENTAL")
    print("=" * 60)

    while True:

        pregunta = input("\nPregunta (ENTER para salir): ").strip()

        if pregunta == "":
            break

        resultados = buscar(pregunta)

        print(f"\nResultados encontrados: {len(resultados)}\n")

        if not resultados:

            print("No se ha encontrado información.")
            continue

        for r in resultados:

            print("=" * 70)

            print(f"Documento : {r.get('documento','')}")
            print(f"Categoría : {r.get('categoria','')}")
            print(f"Páginas   : {r.get('pagina_inicio','?')} - {r.get('pagina_fin','?')}")
            print(f"Puntuación: {r.get('puntuacion',0)}")

            if r.get("titulo"):

                print(f"Título    : {r['titulo']}")

            print("-" * 70)

            texto = r["texto"].replace("\n", " ")

            print(texto[:500])

            print()