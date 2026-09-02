"""
Buscador documental avanzado v2
================================

Características:
- Normalización Unicode y acentos.
- Tokenización y stopwords.
- Lematización ligera.
- Detección de referencias jurídicas (artículo, ley, decreto, orden...).
- Coincidencia exacta de frases.
- Búsqueda por proximidad.
- Ponderación por título, categoría y palabras clave.
- BM25 simplificado.
- Re-ranking final.
"""

import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

CARPETA_CONOCIMIENTO = Path("conocimiento")

STOPWORDS = {
    "de","la","el","los","las","y","o","a","en","un","una","para","por",
    "con","del","al","que","se","su","sus","es","son","como","sobre"
}

LEMAS = {
    "docentes":"docente",
    "profesores":"profesor",
    "maestros":"maestro",
    "permisos":"permiso",
    "licencias":"licencia",
    "alumnos":"alumno",
    "centros":"centro",
}

PATRON_LEGAL = re.compile(
    r"(art(?:\.|ículo)?\s*\d+[a-z]?|ley\s+\d+/\d+|decreto\s+\d+/\d+|"
    r"orden\s+[a-z]+/\d+/\d+|real decreto\s+\d+/\d+)",
    re.I,
)

def normalizar(txt):
    txt = unicodedata.normalize("NFKD", txt.lower())
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = re.sub(r"[^\w\s/.-]", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

def tokens(txt):
    out=[]
    for t in normalizar(txt).split():
        if t in STOPWORDS:
            continue
        out.append(LEMAS.get(t,t))
    return out

def cargar():
    base=[]
    for f in CARPETA_CONOCIMIENTO.rglob("*_chunks.json"):
        with open(f,encoding="utf8") as fh:
            base.extend(json.load(fh))
    return base

BASE=cargar()

DOCS=[]
DF=Counter()

for c in BASE:
    txt=" ".join([
        c.get("titulo",""),
        c.get("categoria",""),
        c.get("texto",""),
        " ".join(c.get("keywords",[]))
    ])
    tk=tokens(txt)
    DOCS.append(tk)
    for t in set(tk):
        DF[t]+=1

N=max(len(DOCS),1)
AVGDL=sum(len(d) for d in DOCS)/N if N else 1

def bm25(q,d,k1=1.5,b=0.75):
    score=0
    freq=Counter(d)
    dl=len(d)
    for term in q:
        if term not in freq:
            continue
        idf=math.log((N-DF[term]+0.5)/(DF[term]+0.5)+1)
        f=freq[term]
        score += idf*((f*(k1+1))/(f+k1*(1-b+b*dl/AVGDL)))
    return score

def proximidad(q,texto):
    pos=[]
    words=tokens(texto)
    for t in q:
        if t in words:
            pos.append(words.index(t))
    if len(pos)<2:
        return 0
    pos.sort()
    return max(0,20-(max(pos)-min(pos)))

def score(chunk,q):
    qtok=tokens(q)
    texto=chunk.get("texto","")
    titulo=normalizar(chunk.get("titulo",""))
    categoria=normalizar(chunk.get("categoria",""))
    kw=[normalizar(k) for k in chunk.get("keywords",[])]

    s=0
    s+=bm25(qtok,tokens(" ".join([texto,titulo,categoria," ".join(kw)])))*25

    if normalizar(q) in normalizar(texto):
        s+=60

    for t in qtok:
        if t in titulo:
            s+=25
        if t in categoria:
            s+=15
        if t in kw:
            s+=18

    s+=proximidad(qtok,texto)

    refs_q=PATRON_LEGAL.findall(q)
    refs_t=PATRON_LEGAL.findall(texto)
    for r in refs_q:
        if any(normalizar(r)==normalizar(x) for x in refs_t):
            s+=120

    if re.match(r"^\s*art", normalizar(texto)):
        s+=10

    return round(s,2)

def buscar(pregunta,limite=10):
    res=[]
    for c in BASE:
        p=score(c,pregunta)
        if p>0:
            x=c.copy()
            x["puntuacion"]=p
            res.append(x)
    res.sort(key=lambda x:(x["puntuacion"],len(x.get("texto",""))),reverse=True)
    return res[:limite]

if __name__=="__main__":
    while True:
        q=input("Pregunta: ").strip()
        if not q:
            break
        for r in buscar(q):
            print("="*80)
            print(r.get("documento"))
            print(r.get("titulo"))
            print(r.get("pagina_inicio"),"-",r.get("pagina_fin"))
            print("Score:",r["puntuacion"])
            print(r["texto"][:800])
