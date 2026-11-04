"""Confere a estrutura de um XML do Lattes contra o XSD oficial do Extrator Lattes (CNPq).

Não é uma validação completa (ordem, obrigatoriedade e valores não são checados): o objetivo é
detectar ELEMENTOS e ATRIBUTOS que o XSD não prevê, sinal de que o formato do Lattes mudou e de que
algum item do currículo pode estar sendo ignorado pela leitura.
"""
import os
import xml.etree.ElementTree as ET

XSD_ARQUIVO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema", "CurriculoLattes_12_09_2022.xsd")
XSD_VERSAO = "12/09/2022"
_XS = "{http://www.w3.org/2001/XMLSchema}"

# Atributos que a exportação atual da Plataforma Lattes já envia e o XSD de 12/09/2022 não declara.
# São conhecidos e não afetam a pontuação, por isso não geram alerta.
ATRIBUTOS_CONHECIDOS = {
    ("DADOS-GERAIS", "PCD"),
    ("ENDERECO", "ELETRONICO"), ("ENDERECO", "OUTRA-FORMA-DE-CONTATO"), ("ENDERECO", "REDE-SOCIAL"),
}

_modelo = None


def _carregar():
    """{elemento: (filhos permitidos, atributos permitidos)} a partir do XSD (lido uma vez)."""
    global _modelo
    if _modelo is None:
        modelo = {}
        raiz = ET.parse(XSD_ARQUIVO).getroot()
        for el in raiz.findall(_XS + "element"):
            filhos = {c.get("ref") or c.get("name") for c in el.iter(_XS + "element") if c is not el}
            attrs = {a.get("name") for a in el.iter(_XS + "attribute")}
            modelo[el.get("name")] = (filhos, attrs)
        _modelo = modelo
    return _modelo


def verificar(root):
    """Recebe a raiz (ElementTree) do XML e devolve
    {"xsd": versão, "elementos": [{"caminho", "qtd"}], "atributos": [{"caminho", "nome", "qtd"}]}
    ou None se o XSD não estiver disponível."""
    try:
        modelo = _carregar()
    except (OSError, ET.ParseError):
        return None
    elementos, atributos = {}, {}

    def anda(el, caminho):
        filhos, attrs = modelo[el.tag]
        for nome in el.attrib:
            if nome not in attrs and (el.tag, nome) not in ATRIBUTOS_CONHECIDOS:
                atributos[(caminho, nome)] = atributos.get((caminho, nome), 0) + 1
        for ch in el:
            if not isinstance(ch.tag, str):  # comentários / instruções
                continue
            cam = f"{caminho} › {ch.tag}"
            if ch.tag not in filhos or ch.tag not in modelo:
                elementos[cam] = elementos.get(cam, 0) + 1   # não desce: tudo abaixo também é desconhecido
                continue
            anda(ch, cam)

    if root.tag not in modelo:
        elementos[root.tag] = 1
    else:
        anda(root, root.tag)
    return {
        "xsd": XSD_VERSAO,
        "elementos": [{"caminho": c, "qtd": n} for c, n in sorted(elementos.items())],
        "atributos": [{"caminho": c, "nome": a, "qtd": n} for (c, a), n in sorted(atributos.items())],
    }
