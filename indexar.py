import os
import re
import json
import hashlib
import pymupdf
from pathlib import Path
from collections import Counter

CARPETA_CONOCIMIENTO = Path("conocimiento")

PATRONES = {
    "articulo": re.compile(r"(Artículo|Art\.)\s+\d+[^\n]*", re.IGNORECASE),
    "capitulo": re.compile(r"CAP[IÍ]TULO\s+[IVXLCDM0-9]+", re.IGNORECASE),
    "titulo": re.compile(r"T[IÍ]TULO\s+[IVXLCDM0-9]+", re.IGNORECASE),
    "anexo": re.compile(r"ANEXO\s+[IVXLCDM0-9A-Z]+", re.IGNORECASE),
    "disposicion": re.compile(r"Disposición\s+(adicional|transitoria|final)[^\n]*", re.IGNORECASE),
}

STOPWORDS={"de","la","el","los","las","y","o","a","en","un","una","por","para","con","del","que","se","su","al"}

def sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        while True:
            b=f.read(65536)
            if not b: break
            h.update(b)
    return h.hexdigest()

def localizar_pdfs():
    return list(CARPETA_CONOCIMIENTO.rglob("*.pdf"))

def leer_pdf(pdf):
    doc=pymupdf.open(pdf)
    paginas=[]
    for i,p in enumerate(doc,1):
        bloques=sorted(p.get_text("blocks"),key=lambda b:(b[1],b[0]))
        texto="\n".join(b[4].strip() for b in bloques if b[4].strip())
        paginas.append({"pagina":i,"texto":texto})
    doc.close()
    return paginas

def keywords(texto,limite=12):
    palabras=re.findall(r"\b[\wáéíóúñÁÉÍÓÚÑ]{4,}\b",texto.lower())
    palabras=[p for p in palabras if p not in STOPWORDS]
    return [p for p,_ in Counter(palabras).most_common(limite)]

def crear_chunks(paginas,min_chars=700,max_chars=1500):
    chunks=[]
    actual=""
    ini=1
    cid=1
    meta={"articulo":"","capitulo":"","titulo":"","anexo":"","disposicion":""}
    for pag in paginas:
        for linea in pag["texto"].splitlines():
            l=linea.strip()
            if not l:
                actual+="\n"
                continue
            for k,pat in PATRONES.items():
                m=pat.match(l)
                if m:
                    if len(actual)>=min_chars:
                        chunks.append({
                            "id":cid,"pagina_inicio":ini,"pagina_fin":pag["pagina"],
                            "texto":actual.strip(),**meta})
                        cid+=1
                        actual=""
                        ini=pag["pagina"]
                    meta[k]=l
            actual+=l+"\n"
            if len(actual)>=max_chars:
                chunks.append({
                    "id":cid,"pagina_inicio":ini,"pagina_fin":pag["pagina"],
                    "texto":actual.strip(),**meta})
                cid+=1
                actual=""
                ini=pag["pagina"]
    if actual.strip():
        chunks.append({
            "id":cid,"pagina_inicio":ini,"pagina_fin":paginas[-1]["pagina"],
            "texto":actual.strip(),**meta})
    return chunks

def guardar(pdf,chunks):
    salida=pdf.with_name(pdf.stem+"_chunks.json")
    datos=[]
    for c in chunks:
        datos.append({
            "id":c["id"],
            "documento":pdf.name,
            "categoria":pdf.parent.name,
            "hash_documento":sha256(pdf),
            "articulo":c["articulo"],
            "capitulo":c["capitulo"],
            "titulo":c["titulo"],
            "anexo":c["anexo"],
            "disposicion":c["disposicion"],
            "tipo_norma":"",
            "vigente":True,
            "pagina_inicio":c["pagina_inicio"],
            "pagina_fin":c["pagina_fin"],
            "palabras_clave":keywords(c["texto"]),
            "texto":c["texto"]
        })
    with open(salida,"w",encoding="utf8") as f:
        json.dump(datos,f,ensure_ascii=False,indent=2)
    print(f"Generado {salida} ({len(datos)} chunks)")

if __name__=="__main__":
    pdfs=localizar_pdfs()
    print(f"{len(pdfs)} PDF(s) encontrados")
    for pdf in pdfs:
        print("Procesando",pdf)
        guardar(pdf,crear_chunks(leer_pdf(pdf)))
    print("Finalizado")
