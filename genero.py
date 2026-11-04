# -*- coding: utf-8 -*-
"""
Palpite de persona (masculina/feminina) pelo primeiro nome, usado só para escolher o avatar.
O XML do Lattes não traz sexo/gênero; o administrador pode corrigir manualmente cada professor.
Retorna "M", "F" ou "N" (neutro, quando não há segurança no palpite).
"""
import unicodedata

FEM = set("""
alice aline ana andrea andreia beatriz carmen caroline cecilia cristiane daniele daniela denise elaine eliane
elisabete elizabeth ester esther gisele iris isabel ines jaqueline lais laise liliane lis luz marlene michele
miriam nadia nair noemi raquel rosane rosilene rute ruth simone suely sueli tais thais vivian viviane ingrid
irene ivone ivete juliete lucimar rosemary rosimeire edileuza lucineide marilene solange socorro conceicao
judite raimunda graca carmem ester joyce clarice lourdes maryanne nazare yasmin ketlin kelly sheila
""".split())
MASC = set("""
abel adriano alexandre anderson andre antonio augusto bruno carlos cesar daniel davi david diego eduardo elias
emanuel enzo fabio felipe fernando francisco gabriel gerson gustavo heitor henrique hugo igor jair jefferson
joao joel jonas jorge jose josue julio kleber leandro leonardo lucas luis luiz manoel marcelo marcio marcos
mario mateus matheus mauricio miguel moises nelson nicolas otavio paulo pedro rafael raimundo reginaldo renato
ricardo roberto rodrigo rogerio samuel sergio thiago tiago vicente victor vitor wagner walter wellington william
alan allan denis dennis cleber edson emerson gilson nilson robson wilson ailton milton nilton everton elton
guilherme rui ruy dante duarte felix luan ian juan jean noah thomas alex max
""".split())
# terminados em "a" que são masculinos
MASC_A = set("luca lucca joshua nicola jonata jonatha".split())
SUF_FEM = ("iane", "ane", "ene", "ine", "ele", "ise", "ice", "ete", "ilde", "ia", "na", "la", "ra", "da", "ta", "sa", "ca", "za", "ly", "lly")
SUF_MASC = ("o", "os", "son", "el", "or", "us", "ir", "an", "on", "ur", "que", "pe", "ge", "dre", "rme", "nte", "rto", "ey")


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return "".join(ch for ch in s if ch.isalpha() or ch == " ").strip()


def inferir_genero(nome):
    partes = _norm(nome).split()
    if not partes:
        return "N"
    p = partes[0]
    if p in FEM:
        return "F"
    if p in MASC or p in MASC_A:
        return "M"
    if p == "maria":  # Maria José, Maria Eduarda… são femininos
        return "F"
    if p.endswith(SUF_FEM) or p.endswith("a"):
        return "F"
    if p.endswith(SUF_MASC):
        return "M"
    return "N"
