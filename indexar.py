import os
import json
import pymupdf
from pathlib import Path

CARPETA_CONOCIMIENTO = Path("conocimiento")


def localizar_pdfs():
    pdfs = []

    for carpeta, _, archivos in os.walk(CARPETA_CONOCIMIENTO):
        for archivo in archivos:
            if archivo.lower().endswith(".pdf"):
                pdfs.append(Path(carpeta) / archivo)

    return pdfs


def leer_pdf(ruta_pdf):
    documento = pymupdf.open(ruta_pdf)

    paginas = []

    for numero, pagina in enumerate(documento):

        texto = pagina.get_text("text")

        paginas.append(
            {
                "pagina": numero + 1,
                "texto": texto
            }
        )

    documento.close()

    return paginas


def crear_chunks(paginas, tamaño=1200):

    chunks = []

    texto_actual = ""

    pagina_inicio = 1

    chunk_id = 1

    for pagina in paginas:

        texto = pagina["texto"]

        if len(texto_actual) + len(texto) < tamaño:

            texto_actual += "\n" + texto

        else:

            chunks.append(
                {
                    "id": chunk_id,
                    "pagina_inicio": pagina_inicio,
                    "pagina_fin": pagina["pagina"] - 1,
                    "texto": texto_actual.strip()
                }
            )

            chunk_id += 1

            texto_actual = texto

            pagina_inicio = pagina["pagina"]

    if texto_actual:

        chunks.append(
            {
                "id": chunk_id,
                "pagina_inicio": pagina_inicio,
                "pagina_fin": paginas[-1]["pagina"],
                "texto": texto_actual.strip()
            }
        )

    return chunks


def guardar_chunks(pdf, chunks):

    categoria = pdf.parent.name

    nombre = pdf.stem + "_chunks.json"

    salida = pdf.parent / nombre

    datos = []

    for chunk in chunks:

        datos.append(
            {
    "id": chunk["id"],
    "documento": pdf.name,
    "categoria": categoria,

    "titulo": "",

    "palabras_clave": [],

    "tipo_norma": "",

    "vigente": True,

    "pagina_inicio": chunk["pagina_inicio"],

    "pagina_fin": chunk["pagina_fin"],

    "texto": chunk["texto"]
}
        )

    with open(salida, "w", encoding="utf8") as f:

        json.dump(datos, f, ensure_ascii=False, indent=4)

    print(f"✔ Generado {salida}")


if __name__ == "__main__":

    documentos = localizar_pdfs()

    print(f"\nSe han encontrado {len(documentos)} PDF(s).\n")

    for pdf in documentos:

        print(f"Procesando: {pdf}")

        paginas = leer_pdf(pdf)

        chunks = crear_chunks(paginas)

        guardar_chunks(pdf, chunks)

    print("\nProceso terminado.")