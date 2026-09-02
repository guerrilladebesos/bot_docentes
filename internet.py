import os
from urllib.parse import urlparse
from serpapi import GoogleSearch

# ===========================================
# CONFIGURACIÓN
# ===========================================

SERP_API_KEY = os.getenv("SERP_API_KEY")

DOMINIOS_OFICIALES = {
    "educantabria.es": 100,
    "boc.cantabria.es": 98,
    "boe.es": 96,
    "educacion.gob.es": 94,
    "administracion.gob.es": 92,
    "inap.es": 90,
    "empleopublico.gob.es": 88,
}


# ===========================================
# CONSULTA
# ===========================================

def construir_consulta(pregunta: str) -> str:
    return (
        f"{pregunta} "
        "docente Cantabria "
        "(site:educantabria.es OR "
        "site:boc.cantabria.es OR "
        "site:boe.es)"
    )


# ===========================================
# DOMINIO
# ===========================================

def dominio(url: str) -> str:

    try:
        return urlparse(url).netloc.replace("www.", "")
    except:
        return ""


# ===========================================
# SCORE
# ===========================================

def score(dominio_web):

    if dominio_web in DOMINIOS_OFICIALES:
        return DOMINIOS_OFICIALES[dominio_web]

    return 10


# ===========================================
# BUSCADOR
# ===========================================

def buscar_web(pregunta, max_resultados=5):

    if not SERP_API_KEY:
        return []

    consulta = construir_consulta(pregunta)

    parametros = {
        "engine": "google",
        "q": consulta,
        "hl": "es",
        "gl": "es",
        "num": 10,
        "api_key": SERP_API_KEY,
    }

    try:
        busqueda = GoogleSearch(parametros)
        resultados = busqueda.get_dict()
    except Exception as e:
        print(f"Error SerpAPI: {e}")
        return []

    salida = []
    vistos = set()

    for r in resultados.get("organic_results", []):

        url = r.get("link", "")

        if not url or url in vistos:
            continue

        vistos.add(url)

        dom = dominio(url)

        salida.append({
            "titulo": r.get("title", ""),
            "url": url,
            "descripcion": r.get("snippet", ""),
            "dominio": dom,
            "score": score(dom),
            "oficial": dom in DOMINIOS_OFICIALES
        })

    salida.sort(key=lambda x: x["score"], reverse=True)

    return salida[:max_resultados]


# ===========================================
# PRUEBA
# ===========================================

if __name__ == "__main__":

    while True:

        consulta = input("Consulta: ").strip()

        if consulta == "":
            break

        resultados = buscar_web(consulta)

        for r in resultados:

            print("=" * 70)

            print(r["titulo"])

            print(r["url"])

            print(r["dominio"])

            print(r["score"])

            print(r["descripcion"])

            print()