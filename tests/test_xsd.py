"""Testes da leitura do Lattes contra o XSD oficial (schema/CurriculoLattes_12_09_2022.xsd).

Rode com:  python3 tests/test_xsd.py

1. Cobertura: para cada tipo de registro repetível previsto no XSD, monta um XML mínimo e confere
   que o leitor o mostra no currículo (se algum tipo novo surgir no XSD e não for lido, o teste falha).
2. Verificação de estrutura: um elemento e um atributo inventados precisam gerar alerta; os
   atributos já conhecidos da exportação atual (PCD, REDE-SOCIAL...) não.
"""
import os
import sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from lattes_parser import parse_lattes_xml  # noqa: E402
from xsd_check import XSD_ARQUIVO  # noqa: E402

XS = "{http://www.w3.org/2001/XMLSchema}"
# repetíveis que são partes de um registro, não registros em si
PARTES = {"AUTORES", "PALAVRAS-CHAVE", "AREAS-DO-CONHECIMENTO", "SETORES-DE-ATIVIDADE", "INFORMACAO-ADICIONAL",
          "PARTICIPANTE-BANCA", "PARTICIPANTE-DE-EVENTOS-CONGRESSOS", "LINHA-DE-PESQUISA", "DISCIPLINA", "TREINAMENTO",
          "PRODUCAO-CT-DO-PROJETO", "INTEGRANTES-DO-PROJETO", "FINANCIADOR-DO-PROJETO", "AREA-DE-ATUACAO", "IDIOMA",
          "ENDERECO", "INFORMACAO-ADICIONAL-INSTITUICAO", "INFORMACAO-ADICIONAL-CURSO", "PREMIO-TITULO", "ORIENTACAO",
          "REGISTRO-OU-PATENTE", "HISTORICO-SITUACOES-PATENTE", "NOME-CITACAO", "PARTICIPANTE-BANCA-JULGADORA"}
# níveis de formação que só aparecem no currículo (não são itens pontuáveis)
SO_CURRICULO = {"ENSINO-FUNDAMENTAL-PRIMEIRO-GRAU", "ENSINO-MEDIO-SEGUNDO-GRAU", "VINCULOS"}


def _modelo():
    filhos, repet, attrs = {}, set(), {}
    raiz = ET.parse(XSD_ARQUIVO).getroot()

    def coleta(nome, no, rep):
        for ch in no:
            if ch.tag in (XS + "sequence", XS + "choice", XS + "all"):
                coleta(nome, ch, rep or ch.get("maxOccurs") == "unbounded")
            elif ch.tag == XS + "element":
                f = ch.get("ref") or ch.get("name")
                filhos[nome].append(f)
                if rep or ch.get("maxOccurs") == "unbounded":
                    repet.add((nome, f))

    for e in raiz.findall(XS + "element"):
        nome = e.get("name")
        filhos[nome], attrs[nome] = [], []
        ct = e.find(XS + "complexType")
        if ct is not None:
            coleta(nome, ct, False)
            attrs[nome] = [(a.get("name"), [x.get("value") for x in a.iter(XS + "enumeration")]) for a in ct.iter(XS + "attribute")]
    return filhos, repet, attrs


def _valor(nome, enum):
    if nome in ("STATUS-DO-CURSO",):
        return "CONCLUIDO"
    if enum:
        return enum[0]
    if nome.startswith("ANO"):
        return "2024"
    if nome.startswith("DATA"):
        return "01032024"
    if nome.startswith("MES"):
        return "3"
    return "Teste"


def test_cobertura():
    filhos, repet, attrs = _modelo()
    tipos = []

    def anda(n, cam):
        for f in filhos.get(n, []):
            if f in cam:
                continue
            c = cam + [f]
            if (n, f) in repet and f not in PARTES and not f.startswith(("DADOS-BASICOS", "DETALHAMENTO")):
                tipos.append(c)
            anda(f, c)

    anda("CURRICULO-VITAE", [])
    tipos = [c for c in tipos if not any(len(o) > len(c) and o[:len(c)] == c for o in tipos)]   # só as folhas

    def el(tag, prof=0):
        at = " ".join(f"{a}={quoteattr(_valor(a, e))}" for a, e in attrs.get(tag, []))
        sub = "".join(el(f, prof + 1) for f in filhos.get(tag, []) if prof < 2 and f.startswith(("DADOS-BASICOS", "DETALHAMENTO")))
        return f"<{tag} {at}>{sub}</{tag}>"

    base = sum(len(s["registros"]) for s in parse_lattes_xml('<CURRICULO-VITAE><DADOS-GERAIS NOME-COMPLETO="T"/></CURRICULO-VITAE>')["secoes"])
    falhas = []
    for cam in tipos:
        corpo = el(cam[-1])
        for anc in reversed(cam[:-1]):
            corpo = f"<{anc}>{corpo}</{anc}>"
        pre = "" if cam[0] == "DADOS-GERAIS" else '<DADOS-GERAIS NOME-COMPLETO="T"/>'
        d = parse_lattes_xml(f"<CURRICULO-VITAE>{pre}{corpo}</CURRICULO-VITAE>")
        mostra = sum(len(s["registros"]) for s in d["secoes"]) > base
        categorizado = bool(d["categorias"]) or cam[-1] in SO_CURRICULO
        if not (mostra and categorizado):
            falhas.append(" › ".join(cam))
    assert not falhas, "Tipos do XSD não lidos:\n  " + "\n  ".join(falhas)
    return len(tipos)


def test_estrutura():
    xml = ('<CURRICULO-VITAE SISTEMA-ORIGEM-XML="LATTES_OFFLINE"><DADOS-GERAIS NOME-COMPLETO="T" PCD="NAO" CAMPO-NOVO="1"/>'
           '<PRODUCAO-TECNICA><TIPO-NOVO/></PRODUCAO-TECNICA></CURRICULO-VITAE>')
    est = parse_lattes_xml(xml)["estrutura"]
    assert [e["caminho"] for e in est["elementos"]] == ["CURRICULO-VITAE › PRODUCAO-TECNICA › TIPO-NOVO"], est
    assert [a["nome"] for a in est["atributos"]] == ["CAMPO-NOVO"], est
    ok = parse_lattes_xml('<CURRICULO-VITAE SISTEMA-ORIGEM-XML="X"><DADOS-GERAIS NOME-COMPLETO="T"/></CURRICULO-VITAE>')["estrutura"]
    assert not ok["elementos"] and not ok["atributos"], ok


if __name__ == "__main__":
    n = test_cobertura()
    print(f"cobertura: {n} tipos de registro do XSD lidos")
    test_estrutura()
    print("estrutura: alertas corretos")
