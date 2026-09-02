"""
normalizador.py
Versión base profesional preparada para crecer.
"""

import re
import unicodedata
from dataclasses import dataclass, field

STOPWORDS = {
    "de","la","el","los","las","y","o","a","en","un","una","por","para",
    "con","del","que","se","su","al","como","es","son","me","mi","mis",
    "te","tu","sus","lo","le","les","ya","si","no"
}

SINONIMOS = {
    "ingresado":"hospitalizacion",
    "ingreso":"hospitalizacion",
    "hospital":"hospitalizacion",
    "operacion":"intervencion",
    "operan":"intervencion",
    "operado":"intervencion",
    "muerto":"fallecimiento",
    "murio":"fallecimiento",
    "fallecio":"fallecimiento",
    "boda":"matrimonio",
    "casamiento":"matrimonio",
    "embarazada":"gestacion",
    "embarazo":"gestacion",
}

PARENTESCOS = {
    "padre":"primer_grado",
    "madre":"primer_grado",
    "hijo":"primer_grado",
    "hija":"primer_grado",
    "abuelo":"segundo_grado",
    "abuela":"segundo_grado",
    "nieto":"segundo_grado",
    "nieta":"segundo_grado",
    "suegro":"afinidad",
    "suegra":"afinidad",
    "cunado":"afinidad",
    "cunada":"afinidad",
}

CATEGORIAS = {
    "permisos":{"permiso","licencia","vacaciones","fallecimiento","hospitalizacion","reduccion","jornada"},
    "interinos":{"interino","vacante","sustitucion","bolsa"},
    "oposiciones":{"oposicion","tribunal","baremo","temario"},
    "retribuciones":{"nomina","salario","trienio","sexenio","complemento"},
}

PESOS = {
    "fallecimiento":30,
    "hospitalizacion":30,
    "intervencion":25,
    "permiso":15,
    "licencia":15,
    "vacaciones":15,
    "interino":20,
    "oposicion":20,
}

@dataclass
class ResultadoNormalizacion:
    texto_original:str
    texto_normalizado:str
    tokens:list = field(default_factory=list)
    conceptos:list = field(default_factory=list)
    categorias:list = field(default_factory=list)
    pesos:dict = field(default_factory=dict)

class Normalizador:

    def quitar_tildes(self,texto):
        return ''.join(
            c for c in unicodedata.normalize("NFD", texto)
            if unicodedata.category(c)!="Mn"
        )

    def limpiar(self,texto):
        texto=self.quitar_tildes(texto.lower())
        texto=re.sub(r"[^\w\s]"," ",texto)
        texto=re.sub(r"\s+"," ",texto).strip()
        return texto

    def tokenizar(self,texto):
        return [t for t in texto.split() if t and t not in STOPWORDS]

    def expandir(self,tokens):
        salida=[]
        for t in tokens:
            salida.append(t)
            if t in SINONIMOS:
                salida.append(SINONIMOS[t])
            if t in PARENTESCOS:
                salida.append(PARENTESCOS[t])
        # quitar duplicados preservando orden
        vistos=set()
        res=[]
        for x in salida:
            if x not in vistos:
                vistos.add(x)
                res.append(x)
        return res

    def detectar_categorias(self,conceptos):
        cats=[]
        conj=set(conceptos)
        for cat,palabras in CATEGORIAS.items():
            if conj & palabras:
                cats.append(cat)
        return cats

    def calcular_pesos(self,conceptos):
        return {c:PESOS.get(c,5) for c in conceptos}

    def analizar(self,pregunta):
        limpio=self.limpiar(pregunta)
        tokens=self.tokenizar(limpio)
        conceptos=self.expandir(tokens)
        categorias=self.detectar_categorias(conceptos)
        pesos=self.calcular_pesos(conceptos)
        return ResultadoNormalizacion(
            texto_original=pregunta,
            texto_normalizado=limpio,
            tokens=tokens,
            conceptos=conceptos,
            categorias=categorias,
            pesos=pesos
        )

if __name__=="__main__":
    n=Normalizador()
    while True:
        q=input("Consulta: ").strip()
        if not q:
            break
        r=n.analizar(q)
        print(r)
