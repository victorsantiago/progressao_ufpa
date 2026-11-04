# -*- coding: utf-8 -*-
"""
Parser do XML do Currículo Lattes (formato CURRICULO-VITAE exportado pelo CNPq).

Produz:
  - dados gerais (nome, resumo, data de atualização...)
  - seções com todos os registros (para a página de perfil)
  - contagem por categoria (para a pontuação)
"""
import datetime as dt
import re
import xml.etree.ElementTree as ET

from scoring import CATEGORIAS_MAP

ANO_ATUAL = dt.date.today().year
PARSER_VERSAO = 2

_RE_PERIODO = re.compile(r"\((\d{4})(\s*[–-]\s*(\d{4}|atual)?)?\)")


def _extrair_periodo(texto):
    """Último '(AAAA)' ou '(AAAA – AAAA|atual)' do texto -> (ini, fim) ou (None, None)."""
    m = _RE_PERIODO.findall(texto or "")
    if not m:
        return None, None
    ini, traco, fim = m[-1]
    ini = int(ini)
    if traco:
        fim = int(fim) if fim.isdigit() else ANO_ATUAL
    else:
        fim = ini
    return ini, max(ini, fim)


def _attrs(elem):
    return dict(elem.attrib) if elem is not None else {}


def _merge(elem):
    """Junta atributos do elemento e de todos os filhos DADOS-BASICOS*/DETALHAMENTO*."""
    a = dict(elem.attrib)
    for ch in elem:
        if ch.tag.startswith("DADOS-BASICOS") or ch.tag.startswith("DETALHAMENTO"):
            a.update(ch.attrib)
            for sub in ch:  # ex.: REGISTRO-OU-PATENTE dentro do DETALHAMENTO
                for k, v in sub.attrib.items():
                    a.setdefault(f"{sub.tag}.{k}", v)
    return a


def _autores(elem):
    nomes = []
    for au in elem.findall("AUTORES"):
        n = au.get("NOME-PARA-CITACAO") or au.get("NOME-COMPLETO-DO-AUTOR")
        if n:
            nomes.append(n.split(";")[0].strip())
    return nomes


def _first(a, *keys):
    for k in keys:
        v = a.get(k)
        if v:
            return v
    return ""


def _titulo(a):
    for k in a:
        if k.startswith("TITULO") and not k.endswith("INGLES") and a[k]:
            return a[k]
    return _first(a, "NOME-DO-PROJETO", "NOME-DO-PREMIO-OU-TITULO", "NOME-CURSO", "NOME-INSTITUICAO")


def _ano(a):
    for k in ("ANO", "ANO-DO-ARTIGO", "ANO-DO-TRABALHO", "ANO-DA-PREMIACAO", "ANO-DE-CONCLUSAO",
              "ANO-DE-OBTENCAO-DO-TITULO", "ANO-FIM", "ANO-INICIO", "ANO-DO-TEXTO", "ANO-DESENVOLVIMENTO"):
        if a.get(k):
            return a[k]
    for k in a:
        if k.startswith("ANO") and a[k]:
            return a[k]
    return ""


def _years(ini, fim):
    try:
        i = int(ini)
    except (TypeError, ValueError):
        return 1
    try:
        f = int(fim) if fim else ANO_ATUAL
    except ValueError:
        f = ANO_ATUAL
    return max(1, f - i + 1)


def _is_brasil(pais):
    p = (pais or "").strip().lower()
    return p in ("", "brasil", "brazil")


def _is_portugues(idioma):
    return (idioma or "").strip().lower().startswith("portugu")


def _premio_internacional(nome, entidade):
    txt = f"{nome} {entidade}".lower()
    if re.search(r"internacional|international|ieee|acm|springer|elsevier|best paper|award|outstanding|certificate", txt):
        return True
    # título majoritariamente em inglês
    en = len(re.findall(r"\b(of|the|and|in|for|best|paper|award)\b", txt))
    return en >= 2


class Curriculo:
    def __init__(self):
        self.dados = {}
        self.secoes = []          # [{key, titulo, registros:[...]}]
        self.categorias = {}      # {cat: {qtd, registros:[str]}}

    # -- helpers ---------------------------------------------------------
    def _add_secao(self, key, titulo):
        s = {"key": key, "titulo": titulo, "registros": []}
        self.secoes.append(s)
        return s

    def _add_cat(self, cat, descricao, qtd=1.0):
        """Registra um item pontuável. O período (ano inicial/final) é lido do
        último '(AAAA)' ou '(AAAA – AAAA|atual)' da descrição."""
        if cat not in CATEGORIAS_MAP:
            raise KeyError(cat)
        ini, fim = _extrair_periodo(descricao)
        c = self.categorias.setdefault(cat, {"qtd": 0.0, "registros": []})
        c["qtd"] += qtd
        c["registros"].append({"desc": descricao, "qtd": float(qtd), "ini": ini, "fim": fim})

    def to_dict(self):
        return {"versao": PARSER_VERSAO, "dados": self.dados, "secoes": self.secoes, "categorias": self.categorias}


def _decodificar(xml_bytes):
    """O Lattes exporta em ISO-8859-1, mas aceita também UTF-8 (com ou sem declaração correta)."""
    if isinstance(xml_bytes, str):
        txt = xml_bytes
    else:
        try:
            txt = xml_bytes.decode("utf-8")
        except UnicodeDecodeError:
            txt = xml_bytes.decode("latin-1")
    # remove a declaração de encoding para o ElementTree não reinterpretar a string
    return re.sub(r"^\s*<\?xml[^>]*\?>", "", txt, count=1)


def parse_lattes_xml(xml_bytes):
    """Recebe bytes do XML e devolve um dict serializável."""
    root = ET.fromstring(_decodificar(xml_bytes))
    cv = Curriculo()
    dg = root.find("DADOS-GERAIS")
    dga = _attrs(dg)

    data_raw = root.get("DATA-ATUALIZACAO", "")   # DDMMAAAA
    hora_raw = root.get("HORA-ATUALIZACAO", "")   # HHMMSS
    data_iso = ""
    if len(data_raw) == 8:
        data_iso = f"{data_raw[4:8]}-{data_raw[2:4]}-{data_raw[0:2]}"
        if len(hora_raw) == 6:
            data_iso += f"T{hora_raw[0:2]}:{hora_raw[2:4]}:{hora_raw[4:6]}"

    resumo = ""
    r = dg.find("RESUMO-CV") if dg is not None else None
    if r is not None:
        resumo = r.get("TEXTO-RESUMO-CV-RH", "")

    cv.dados = {
        "id": root.get("NUMERO-IDENTIFICADOR", ""),
        "nome": dga.get("NOME-COMPLETO", ""),
        "nome_citacao": dga.get("NOME-EM-CITACOES-BIBLIOGRAFICAS", ""),
        "orcid": dga.get("ORCID-ID", ""),
        "nacionalidade": dga.get("PAIS-DE-NACIONALIDADE", ""),
        "resumo": resumo,
        "data_atualizacao": data_iso,
        "data_atualizacao_br": f"{data_raw[0:2]}/{data_raw[2:4]}/{data_raw[4:8]}" if len(data_raw) == 8 else "",
        "hora_atualizacao": f"{hora_raw[0:2]}:{hora_raw[2:4]}:{hora_raw[4:6]}" if len(hora_raw) == 6 else "",
        "areas": [],
        "idiomas": [],
    }
    if dg is not None:
        for ar in dg.iter("AREA-DE-ATUACAO"):
            partes = [ar.get(k) for k in ("NOME-GRANDE-AREA-DO-CONHECIMENTO", "NOME-DA-AREA-DO-CONHECIMENTO",
                                          "NOME-DA-SUB-AREA-DO-CONHECIMENTO", "NOME-DA-ESPECIALIDADE")]
            cv.dados["areas"].append(" / ".join(p.replace("_", " ").title() if p and p.isupper() else (p or "") for p in partes if p))
        for idm in dg.iter("IDIOMA"):
            cv.dados["idiomas"].append({
                "idioma": idm.get("DESCRICAO-DO-IDIOMA", ""),
                "leitura": idm.get("PROFICIENCIA-DE-LEITURA", ""), "fala": idm.get("PROFICIENCIA-DE-FALA", ""),
                "escrita": idm.get("PROFICIENCIA-DE-ESCRITA", ""), "compreensao": idm.get("PROFICIENCIA-DE-COMPREENSAO", ""),
            })

    _formacao(root, cv)
    _atuacao(root, cv)
    _projetos(root, cv)
    _premios(root, cv)
    _producao_bibliografica(root, cv)
    _producao_tecnica(root, cv)
    _producao_artistica(root, cv)
    _orientacoes_concluidas(root, cv)
    _orientacoes_andamento(root, cv)
    _bancas(root, cv)
    _eventos(root, cv)
    _formacao_complementar(root, cv)
    return cv.to_dict()


# ---------------------------------------------------------------------------
def _reg(a, titulo=None, ano=None, subtitulo="", categoria=None, autores=None, detalhes=None):
    ano = ano if ano is not None else _ano(a)
    ini, fim = _extrair_periodo(f"({ano.strip()})" if ano else "")
    return {
        "titulo": titulo if titulo is not None else _titulo(a),
        "ano": ano,
        "ini": ini,
        "fim": fim,
        "subtitulo": subtitulo,
        "categoria": categoria,
        "autores": autores or [],
        "detalhes": detalhes or {},
    }


def _formacao(root, cv):
    sec = cv._add_secao("formacao", "Formação acadêmica / titulação")
    ft = root.find("DADOS-GERAIS/FORMACAO-ACADEMICA-TITULACAO")
    if ft is None:
        return
    nomes = {"GRADUACAO": "Graduação", "ESPECIALIZACAO": "Especialização", "APERFEICOAMENTO": "Aperfeiçoamento",
             "MESTRADO": "Mestrado", "MESTRADO-PROFISSIONALIZANTE": "Mestrado profissional",
             "DOUTORADO": "Doutorado", "POS-DOUTORADO": "Pós-doutorado", "LIVRE-DOCENCIA": "Livre-docência",
             "RESIDENCIA-MEDICA": "Residência médica", "CURSO-TECNICO-PROFISSIONALIZANTE": "Curso técnico",
             "ENSINO-MEDIO-SEGUNDO-GRAU": "Ensino médio", "ENSINO-FUNDAMENTAL-PRIMEIRO-GRAU": "Ensino fundamental"}
    for el in ft:
        a = _attrs(el)
        nivel = nomes.get(el.tag, el.tag.title())
        status = a.get("STATUS-DO-CURSO", "")
        titulo = f"{nivel} em {a.get('NOME-CURSO', '')}".strip() if a.get("NOME-CURSO") else nivel
        sub = a.get("NOME-INSTITUICAO", "")
        periodo = f"{a.get('ANO-DE-INICIO', '')} – {a.get('ANO-DE-CONCLUSAO', '') or 'atual'}"
        det = {"Período": periodo, "Situação": status.title() if status else "",
               "Título do trabalho": _first(a, "TITULO-DA-DISSERTACAO-TESE", "TITULO-DO-TRABALHO-DE-CONCLUSAO-DE-CURSO", "TITULO-DO-TRABALHO"),
               "Orientador": _first(a, "NOME-COMPLETO-DO-ORIENTADOR", "NOME-DO-ORIENTADOR"),
               "Bolsa": a.get("NOME-AGENCIA", "") if a.get("FLAG-BOLSA") == "SIM" else ""}
        cat = None
        if status == "CONCLUIDO":
            cat = {"DOUTORADO": "form_doutorado", "LIVRE-DOCENCIA": "form_doutorado", "MESTRADO": "form_mestrado",
                   "MESTRADO-PROFISSIONALIZANTE": "form_mestrado", "POS-DOUTORADO": "form_posdoc",
                   "ESPECIALIZACAO": "form_especializacao"}.get(el.tag)
        if cat:
            cv._add_cat(cat, f"{titulo} ({a.get('ANO-DE-CONCLUSAO', '')}) – {sub}")
        sec["registros"].append(_reg(a, titulo=titulo, ano=a.get("ANO-DE-CONCLUSAO", ""), subtitulo=sub, categoria=cat, detalhes=det))


def _atuacao(root, cv):
    sec = cv._add_secao("atuacao", "Atuação profissional")
    for ap in root.iter("ATUACAO-PROFISSIONAL"):
        inst = ap.get("NOME-INSTITUICAO", "")
        for v in ap.iter("VINCULOS"):
            a = _attrs(v)
            enquad = _first(a, "OUTRO-ENQUADRAMENTO-FUNCIONAL-INFORMADO", "ENQUADRAMENTO-FUNCIONAL").replace("_", " ").title()
            tipo = _first(a, "OUTRO-VINCULO-INFORMADO", "TIPO-DE-VINCULO").replace("_", " ").title()
            periodo = f"{a.get('ANO-INICIO', '')} – {a.get('ANO-FIM', '') or 'atual'}"
            det = {"Vínculo": tipo, "Enquadramento": enquad, "Carga horária": a.get("CARGA-HORARIA-SEMANAL", ""),
                   "Dedicação exclusiva": "Sim" if a.get("FLAG-DEDICACAO-EXCLUSIVA") == "SIM" else "",
                   "Outras informações": a.get("OUTRAS-INFORMACOES", "")}
            cat = None
            if "revisor" in tipo.lower() or "revisor" in enquad.lower():
                cat = "revisor_periodico"
                cv._add_cat(cat, f"Revisor – {inst} ({periodo})", _years(a.get("ANO-INICIO"), a.get("ANO-FIM")))
            elif "editorial" in tipo.lower() or "editorial" in enquad.lower():
                cat = "corpo_editorial"
                cv._add_cat(cat, f"Corpo editorial – {inst} ({periodo})", _years(a.get("ANO-INICIO"), a.get("ANO-FIM")))
            sec["registros"].append(_reg(a, titulo=inst, ano=periodo, subtitulo=f"{tipo} – {enquad}".strip(" –"), categoria=cat, detalhes=det))
        for en in ap.iter("ENSINO"):
            a = _attrs(en)
            disc = [d.text for d in en.findall("DISCIPLINA") if d.text]
            tipo = a.get("TIPO-ENSINO", "").replace("-", " ").title()
            cat = "ensino_pos" if "POS" in a.get("TIPO-ENSINO", "") else "ensino_graduacao"
            periodo = f"{a.get('ANO-INICIO', '')} – {a.get('ANO-FIM', '') or 'atual'}"
            cv._add_cat(cat, f"{tipo}: {a.get('NOME-CURSO', '')} ({periodo}) – {len(disc)} disciplina(s)", max(1, len(disc)))
            sec["registros"].append(_reg(a, titulo=f"Ensino ({tipo}) – {a.get('NOME-CURSO', '')}", ano=periodo, subtitulo=inst,
                                         categoria=cat, detalhes={"Disciplinas": "; ".join(disc)}))
        for d in ap.iter("DIRECAO-E-ADMINISTRACAO"):
            a = _attrs(d)
            periodo = f"{a.get('ANO-INICIO', '')} – {a.get('ANO-FIM', '') or 'atual'}"
            cargo = a.get("CARGO-OU-FUNCAO", "")
            cv._add_cat("cargo_direcao", f"{cargo} – {inst} ({periodo})", _years(a.get("ANO-INICIO"), a.get("ANO-FIM")))
            sec["registros"].append(_reg(a, titulo=cargo, ano=periodo, subtitulo=f"{inst} – {a.get('NOME-ORGAO', '')}", categoria="cargo_direcao"))
        for c in ap.iter("CONSELHO-COMISSAO-E-CONSULTORIA"):
            a = _attrs(c)
            periodo = f"{a.get('ANO-INICIO', '')} – {a.get('ANO-FIM', '') or 'atual'}"
            esp = a.get("ESPECIFICACAO", "")
            cv._add_cat("conselho_comissao", f"{esp} – {inst} ({periodo})", _years(a.get("ANO-INICIO"), a.get("ANO-FIM")))
            sec["registros"].append(_reg(a, titulo=esp, ano=periodo, subtitulo=inst, categoria="conselho_comissao"))
        for e in ap.iter("ESTAGIO"):
            a = _attrs(e)
            periodo = f"{a.get('ANO-INICIO', '')} – {a.get('ANO-FIM', '') or 'atual'}"
            cv._add_cat("estagio_realizado", f"{a.get('ESTAGIO-REALIZADO', '')} – {inst} ({periodo})")
            sec["registros"].append(_reg(a, titulo=f"Estágio: {a.get('ESTAGIO-REALIZADO', '')}", ano=periodo, subtitulo=inst, categoria="estagio_realizado"))
        for t in ap.iter("TREINAMENTO-MINISTRADO"):
            a = _attrs(t)
            periodo = f"{a.get('ANO-INICIO', '')} – {a.get('ANO-FIM', '') or 'atual'}"
            tr = [x.text for x in t.findall("TREINAMENTO") if x.text]
            cv._add_cat("treinamento_ministrado", f"{'; '.join(tr)} – {inst} ({periodo})", max(1, len(tr)))
            sec["registros"].append(_reg(a, titulo=f"Treinamento ministrado: {'; '.join(tr)}", ano=periodo, subtitulo=inst, categoria="treinamento_ministrado"))


def _projetos(root, cv):
    sec = cv._add_secao("projetos", "Projetos")
    meu_id = cv.dados.get("id")
    meu_nome = (cv.dados.get("nome") or "").lower()
    vistos = set()
    for p in root.iter("PROJETO-DE-PESQUISA"):
        a = _attrs(p)
        chave = (a.get("NOME-DO-PROJETO"), a.get("ANO-INICIO"))
        if chave in vistos:
            continue
        vistos.add(chave)
        natureza = a.get("NATUREZA", "PESQUISA")
        responsavel = False
        integrantes = []
        for i in p.iter("INTEGRANTES-DO-PROJETO"):
            integrantes.append(i.get("NOME-COMPLETO", ""))
            if i.get("FLAG-RESPONSAVEL") == "SIM" and (
                    (meu_id and i.get("NRO-ID-CNPQ") == meu_id) or (i.get("NOME-COMPLETO", "").lower() == meu_nome)):
                responsavel = True
        financiadores = [f.get("NOME-INSTITUICAO", "") for f in p.iter("FINANCIADOR-DO-PROJETO")]
        fin_txt = " ".join(financiadores).lower()
        interno = bool(fin_txt) and bool(re.search(r"ufpa|universidade federal do par|propesp|proex|proeg", fin_txt))
        anos = _years(a.get("ANO-INICIO"), a.get("ANO-FIM"))
        periodo = f"{a.get('ANO-INICIO', '')} – {a.get('ANO-FIM', '') or 'atual'}"
        papel = "Coordenador" if responsavel else "Integrante"
        if natureza == "EXTENSAO":
            cat = "proj_extensao_coord" if responsavel else "proj_extensao_part"
            qtd = anos
        elif natureza == "ENSINO":
            cat = "proj_ensino_coord" if responsavel else "proj_ensino_part"
            qtd = 1
        elif natureza in ("PESQUISA", "DESENVOLVIMENTO"):
            if responsavel:
                cat = "proj_pesquisa_coord_sem_fin" if not financiadores else ("proj_pesquisa_coord_fin_int" if interno else "proj_pesquisa_coord_fin_ext")
                qtd = 1 if not financiadores else anos
            else:
                cat = "proj_pesquisa_part_sem_fin" if not financiadores else ("proj_pesquisa_part_fin_int" if interno else "proj_pesquisa_part_fin_ext")
                qtd = anos
        else:
            cat, qtd = "proj_outro", 1
        desc = f"{a.get('NOME-DO-PROJETO', '')} ({periodo}) – {papel}"
        cv._add_cat(cat, desc, qtd)
        det = {"Natureza": natureza.title(), "Situação": a.get("SITUACAO", "").replace("_", " ").title(), "Papel": papel,
               "Financiadores": "; ".join(financiadores), "Integrantes": "; ".join(integrantes),
               "Descrição": a.get("DESCRICAO-DO-PROJETO", "")}
        sec["registros"].append(_reg(a, titulo=a.get("NOME-DO-PROJETO", ""), ano=periodo, subtitulo=f"{natureza.title()} – {papel}", categoria=cat, detalhes=det))


def _premios(root, cv):
    sec = cv._add_secao("premios", "Prêmios e títulos")
    for p in root.iter("PREMIO-TITULO"):
        a = _attrs(p)
        nome = a.get("NOME-DO-PREMIO-OU-TITULO", "")
        ent = a.get("NOME-DA-ENTIDADE-PROMOTORA", "")
        cat = "premio_internacional" if _premio_internacional(nome, ent) else "premio_nacional"
        cv._add_cat(cat, f"{nome} – {ent} ({a.get('ANO-DA-PREMIACAO', '')})")
        sec["registros"].append(_reg(a, titulo=nome, ano=a.get("ANO-DA-PREMIACAO", ""), subtitulo=ent, categoria=cat))


def _producao_bibliografica(root, cv):
    pb = root.find("PRODUCAO-BIBLIOGRAFICA")
    sec_art = cv._add_secao("artigos", "Artigos completos publicados em periódicos")
    sec_liv = cv._add_secao("livros", "Livros e capítulos")
    sec_ev = cv._add_secao("eventos", "Trabalhos publicados em anais de eventos")
    sec_jor = cv._add_secao("jornais", "Textos em jornais ou revistas")
    sec_out = cv._add_secao("outra_bib", "Demais produções bibliográficas")
    if pb is None:
        return
    for el in pb.iter("ARTIGO-PUBLICADO"):
        a = _merge(el)
        cat = "artigo_nacional" if _is_portugues(a.get("IDIOMA")) else "artigo_internacional"
        per = a.get("TITULO-DO-PERIODICO-OU-REVISTA", "")
        cv._add_cat(cat, f"{_titulo(a)} – {per} ({_ano(a)})")
        det = {"Periódico": per, "ISSN": a.get("ISSN", ""), "Volume": a.get("VOLUME", ""), "Páginas": f"{a.get('PAGINA-INICIAL', '')}-{a.get('PAGINA-FINAL', '')}".strip("-"),
               "DOI": a.get("DOI", ""), "Idioma": a.get("IDIOMA", "")}
        sec_art["registros"].append(_reg(a, subtitulo=per, categoria=cat, autores=_autores(el), detalhes=det))
    for el in pb.iter("LIVRO-PUBLICADO-OU-ORGANIZADO"):
        a = _merge(el)
        tipo = a.get("TIPO", "LIVRO_PUBLICADO")
        if tipo == "LIVRO_PUBLICADO":
            cat = "livro_publicado"
        else:
            cat = "livro_organizado_nacional" if _is_brasil(a.get("PAIS-DE-PUBLICACAO")) else "livro_organizado_internacional"
        ed = a.get("NOME-DA-EDITORA", "")
        cv._add_cat(cat, f"{_titulo(a)} – {ed} ({_ano(a)})")
        det = {"Tipo": tipo.replace("_", " ").title(), "Editora": ed, "ISBN": a.get("ISBN", ""), "País": a.get("PAIS-DE-PUBLICACAO", ""), "Páginas": a.get("NUMERO-DE-PAGINAS", "")}
        sec_liv["registros"].append(_reg(a, subtitulo=f"Livro – {ed}", categoria=cat, autores=_autores(el), detalhes=det))
    for el in pb.iter("CAPITULO-DE-LIVRO-PUBLICADO"):
        a = _merge(el)
        cat = "capitulo_nacional" if _is_brasil(a.get("PAIS-DE-PUBLICACAO")) else "capitulo_internacional"
        livro = a.get("TITULO-DO-LIVRO", "")
        cv._add_cat(cat, f"{_titulo(a)} – em: {livro} ({_ano(a)})")
        det = {"Livro": livro, "Editora": a.get("NOME-DA-EDITORA", ""), "ISBN": a.get("ISBN", ""), "País": a.get("PAIS-DE-PUBLICACAO", ""),
               "Organizadores": a.get("ORGANIZADORES", ""), "Páginas": f"{a.get('PAGINA-INICIAL', '')}-{a.get('PAGINA-FINAL', '')}".strip("-")}
        sec_liv["registros"].append(_reg(a, subtitulo=f"Capítulo – {livro}", categoria=cat, autores=_autores(el), detalhes=det))
    for el in pb.iter("TRABALHO-EM-EVENTOS"):
        a = _merge(el)
        nat = a.get("NATUREZA", "COMPLETO")
        clas = a.get("CLASSIFICACAO-DO-EVENTO", "")
        if nat in ("COMPLETO", "RESUMO_EXPANDIDO"):
            cat = "trabalho_evento_regional" if clas in ("REGIONAL", "LOCAL") else "trabalho_evento_completo"
        else:
            cat = "resumo_evento"
        ev = a.get("NOME-DO-EVENTO", "")
        cv._add_cat(cat, f"{_titulo(a)} – {ev} ({_ano(a)})")
        det = {"Evento": ev, "Classificação": clas.replace("_", " ").title(), "Natureza": nat.replace("_", " ").title(),
               "Anais": a.get("TITULO-DOS-ANAIS-OU-PROCEEDINGS", ""), "Cidade": a.get("CIDADE-DO-EVENTO", ""), "DOI": a.get("DOI", "")}
        sec_ev["registros"].append(_reg(a, subtitulo=ev, categoria=cat, autores=_autores(el), detalhes=det))
    for el in pb.iter("TEXTO-EM-JORNAL-OU-REVISTA"):
        a = _merge(el)
        jr = a.get("TITULO-DO-JORNAL-OU-REVISTA", "")
        cv._add_cat("texto_jornal", f"{_titulo(a)} – {jr} ({_ano(a)})")
        sec_jor["registros"].append(_reg(a, subtitulo=jr, categoria="texto_jornal", autores=_autores(el),
                                         detalhes={"Natureza": a.get("NATUREZA", "").replace("_", " ").title(), "Data": a.get("DATA-DE-PUBLICACAO", "")}))
    demais = pb.find("DEMAIS-TIPOS-DE-PRODUCAO-BIBLIOGRAFICA")
    if demais is not None:
        for el in demais:
            a = _merge(el)
            cat = {"PREFACIO-POSFACIO": "prefacio_posfacio", "TRADUCAO": "traducao"}.get(el.tag, "outra_prod_bibliografica")
            nat = a.get("NATUREZA", el.tag.replace("-", " ").title())
            cv._add_cat(cat, f"{_titulo(a)} ({_ano(a)}) – {nat}")
            sec_out["registros"].append(_reg(a, subtitulo=nat, categoria=cat, autores=_autores(el), detalhes={"Editora": a.get("EDITORA", ""), "ISSN/ISBN": a.get("ISSN-ISBN", "")}))


def _producao_tecnica(root, cv):
    pt = root.find("PRODUCAO-TECNICA")
    sec_sw = cv._add_secao("software", "Softwares")
    sec_pat = cv._add_secao("patentes", "Patentes e registros")
    sec_tt = cv._add_secao("trabalho_tecnico", "Trabalhos técnicos")
    sec_apr = cv._add_secao("apresentacoes", "Apresentações de trabalho")
    sec_dem = cv._add_secao("demais_tecnica", "Demais produções técnicas")
    if pt is None:
        return
    for el in pt.findall("SOFTWARE"):
        a = _merge(el)
        reg = el.find("DETALHAMENTO-DO-SOFTWARE/REGISTRO-OU-PATENTE")
        cat = "software_registrado" if reg is not None else "software_sem_registro"
        cv._add_cat(cat, f"{_titulo(a)} ({_ano(a)})")
        det = {"Finalidade": a.get("FINALIDADE", ""), "Plataforma": a.get("PLATAFORMA", ""), "Ambiente": a.get("AMBIENTE", ""),
               "Registro": reg.get("CODIGO-DO-REGISTRO-OU-PATENTE", "") if reg is not None else "",
               "Instituição de registro": reg.get("INSTITUICAO-DEPOSITO-REGISTRO", "") if reg is not None else ""}
        sec_sw["registros"].append(_reg(a, subtitulo="Registrado" if reg is not None else "Sem registro", categoria=cat, autores=_autores(el), detalhes=det))
    for el in pt.findall("PATENTE"):
        a = _merge(el)
        reg = el.find("DETALHAMENTO-DA-PATENTE/REGISTRO-OU-PATENTE")
        concedida = reg is not None and bool(reg.get("DATA-DE-CONCESSAO"))
        cat = "patente_concedida" if concedida else "patente_depositada"
        cv._add_cat(cat, f"{_titulo(a)} ({_ano(a)})")
        det = {"Código": reg.get("CODIGO-DO-REGISTRO-OU-PATENTE", "") if reg is not None else "", "Depósito": reg.get("DATA-PEDIDO-DE-DEPOSITO", "") if reg is not None else "",
               "Concessão": reg.get("DATA-DE-CONCESSAO", "") if reg is not None else "", "Finalidade": a.get("FINALIDADE", "")}
        sec_pat["registros"].append(_reg(a, subtitulo="Concedida" if concedida else "Depositada", categoria=cat, autores=_autores(el), detalhes=det))
    for tag, cat, label in (("PRODUTO-TECNOLOGICO", "produto_tecnologico", "Produto tecnológico"), ("PROCESSOS-OU-TECNICAS", "processo_tecnica", "Processo ou técnica")):
        for el in pt.findall(tag):
            a = _merge(el)
            cv._add_cat(cat, f"{_titulo(a)} ({_ano(a)})")
            sec_pat["registros"].append(_reg(a, subtitulo=label, categoria=cat, autores=_autores(el), detalhes={"Finalidade": a.get("FINALIDADE", "")}))
    for el in pt.findall("TRABALHO-TECNICO"):
        a = _merge(el)
        nat = a.get("NATUREZA", "").replace("_", " ").title()
        cv._add_cat("trabalho_tecnico", f"{_titulo(a)} ({_ano(a)}) – {nat}")
        sec_tt["registros"].append(_reg(a, subtitulo=nat, categoria="trabalho_tecnico", autores=_autores(el),
                                        detalhes={"Finalidade": a.get("FINALIDADE", ""), "Instituição financiadora": a.get("INSTITUICAO-FINANCIADORA", ""), "Duração (meses)": a.get("DURACAO-EM-MESES", "")}))
    demais = pt.find("DEMAIS-TIPOS-DE-PRODUCAO-TECNICA")
    if demais is None:
        return
    for el in demais:
        a = _merge(el)
        if el.tag == "APRESENTACAO-DE-TRABALHO":
            nat = a.get("NATUREZA", "")
            if nat == "CONFERENCIA":
                cat = "apresentacao_conferencia"
            else:
                cat = "apresentacao_nacional" if _is_brasil(a.get("PAIS")) else "apresentacao_internacional"
            ev = a.get("NOME-DO-EVENTO", "")
            cv._add_cat(cat, f"{_titulo(a)} – {ev} ({_ano(a)})")
            sec_apr["registros"].append(_reg(a, subtitulo=f"{nat.title()} – {ev}", categoria=cat, autores=_autores(el),
                                             detalhes={"Evento": ev, "Instituição promotora": a.get("INSTITUICAO-PROMOTORA", ""), "Cidade": a.get("CIDADE-DA-APRESENTACAO", ""), "País": a.get("PAIS", "")}))
            continue
        if el.tag == "CURSO-DE-CURTA-DURACAO-MINISTRADO":
            dur = a.get("DURACAO", "")
            unidade = (a.get("UNIDADE", "") or "").lower()
            qtd = 1.0
            try:
                h = float(dur.replace(",", "."))
                if unidade.startswith("hora") or unidade == "":
                    qtd = max(1.0, float(int(h // 3)))
                elif unidade.startswith("dia"):
                    qtd = max(1.0, float(int(h * 8 // 3)))
                elif unidade.startswith("semana"):
                    qtd = max(1.0, float(int(h * 40 // 3)))
            except ValueError:
                pass
            cv._add_cat("curso_curta_ministrado", f"{_titulo(a)} ({_ano(a)}) – {dur} {unidade}", qtd)
            sec_dem["registros"].append(_reg(a, subtitulo=f"Curso de curta duração ministrado – {dur} {unidade}", categoria="curso_curta_ministrado", autores=_autores(el),
                                             detalhes={"Nível": a.get("NIVEL-DO-CURSO", ""), "Instituição promotora": a.get("INSTITUICAO-PROMOTORA-DO-CURSO", ""), "Duração": f"{dur} {unidade}"}))
            continue
        cat, label = {
            "DESENVOLVIMENTO-DE-MATERIAL-DIDATICO-OU-INSTRUCIONAL": ("material_didatico", "Material didático"),
            "ORGANIZACAO-DE-EVENTO": ("organizacao_evento", "Organização de evento"),
            "PROGRAMA-DE-RADIO-OU-TV": ("programa_radio_tv", "Programa de rádio ou TV"),
            "EDITORACAO": ("editoracao", "Editoração"),
            "RELATORIO-DE-PESQUISA": ("relatorio_pesquisa", "Relatório de pesquisa"),
        }.get(el.tag, ("outra_prod_tecnica", el.tag.replace("-", " ").title()))
        nat = a.get("NATUREZA", "")
        cv._add_cat(cat, f"{_titulo(a)} ({_ano(a)}) – {label}")
        sec_dem["registros"].append(_reg(a, subtitulo=f"{label}{' – ' + nat if nat and nat != 'NAO_INFORMADO' else ''}", categoria=cat, autores=_autores(el),
                                         detalhes={"Finalidade": a.get("FINALIDADE", ""), "Instituição promotora": a.get("INSTITUICAO-PROMOTORA", ""), "Emissora": a.get("EMISSORA", ""), "Tema": a.get("TEMA", "")}))


def _producao_artistica(root, cv):
    sec = cv._add_secao("artistica", "Produção artística/cultural")
    pa = root.find("OUTRA-PRODUCAO/PRODUCAO-ARTISTICA-CULTURAL")
    if pa is None:
        return
    for el in pa:
        a = _merge(el)
        cv._add_cat("producao_artistica", f"{_titulo(a)} ({_ano(a)}) – {el.tag.replace('-', ' ').title()}")
        sec["registros"].append(_reg(a, subtitulo=el.tag.replace("-", " ").title(), categoria="producao_artistica", autores=_autores(el)))


def _orientacoes_concluidas(root, cv):
    sec = cv._add_secao("orientacoes_concluidas", "Orientações e supervisões concluídas")
    oc = root.find("OUTRA-PRODUCAO/ORIENTACOES-CONCLUIDAS")
    if oc is None:
        return
    for el in oc:
        a = _merge(el)
        tipo_or = a.get("TIPO-DE-ORIENTACAO", "ORIENTADOR_PRINCIPAL")
        co = tipo_or == "CO_ORIENTADOR"
        if el.tag == "ORIENTACOES-CONCLUIDAS-PARA-MESTRADO":
            cat, label = ("coorient_mestrado_concl" if co else "orient_mestrado_concl"), "Dissertação de mestrado"
        elif el.tag == "ORIENTACOES-CONCLUIDAS-PARA-DOUTORADO":
            cat, label = ("coorient_doutorado_concl" if co else "orient_doutorado_concl"), "Tese de doutorado"
        elif el.tag == "ORIENTACOES-CONCLUIDAS-PARA-POS-DOUTORADO":
            cat, label = "orient_posdoc_concl", "Supervisão de pós-doutorado"
        else:
            nat = a.get("NATUREZA", "")
            if nat == "INICIACAO_CIENTIFICA":
                cat, label = "orient_ic_concl", "Iniciação científica"
            elif nat == "TRABALHO_DE_CONCLUSAO_DE_CURSO_GRADUACAO":
                cat, label = "orient_tcc_concl", "TCC de graduação"
            elif "ESPECIALIZACAO" in nat or "APERFEICOAMENTO" in nat:
                cat, label = "orient_especializacao_concl", "Monografia de especialização"
            else:
                cat, label = "orient_outra_concl", nat.replace("_", " ").replace("-", " ").title() or "Outra orientação"
        orientado = a.get("NOME-DO-ORIENTADO", "")
        cv._add_cat(cat, f"{orientado} – {_titulo(a)} ({_ano(a)})")
        det = {"Orientado": orientado, "Instituição": a.get("NOME-DA-INSTITUICAO", ""), "Curso": a.get("NOME-DO-CURSO", ""),
               "Tipo": "Coorientação" if co else "Orientação principal", "Bolsa": a.get("NOME-DA-AGENCIA", "") if a.get("FLAG-BOLSA") == "SIM" else ""}
        sec["registros"].append(_reg(a, subtitulo=f"{label}{' (coorientação)' if co else ''} – {orientado}", categoria=cat, detalhes=det))


def _orientacoes_andamento(root, cv):
    sec = cv._add_secao("orientacoes_andamento", "Orientações e supervisões em andamento")
    oa = root.find("DADOS-COMPLEMENTARES/ORIENTACOES-EM-ANDAMENTO")
    if oa is None:
        return
    for el in oa:
        a = _merge(el)
        co = a.get("TIPO-DE-ORIENTACAO", "") == "CO_ORIENTADOR"
        cat, label = {
            "ORIENTACAO-EM-ANDAMENTO-DE-MESTRADO": ("orient_mestrado_and", "Dissertação de mestrado"),
            "ORIENTACAO-EM-ANDAMENTO-DE-DOUTORADO": ("orient_doutorado_and", "Tese de doutorado"),
            "ORIENTACAO-EM-ANDAMENTO-DE-POS-DOUTORADO": ("orient_posdoc_and", "Supervisão de pós-doutorado"),
            "ORIENTACAO-EM-ANDAMENTO-DE-INICIACAO-CIENTIFICA": ("orient_ic_and", "Iniciação científica"),
            "ORIENTACAO-EM-ANDAMENTO-DE-GRADUACAO": ("orient_tcc_and", "TCC de graduação"),
        }.get(el.tag, ("orient_outra_and", el.tag.replace("ORIENTACAO-EM-ANDAMENTO-DE-", "").replace("-", " ").title()))
        orientando = _first(a, "NOME-DO-ORIENTANDO", "NOME-DO-ORIENTADO")
        cv._add_cat(cat, f"{orientando} – {_titulo(a)} ({_ano(a)})")
        det = {"Orientando": orientando, "Instituição": a.get("NOME-INSTITUICAO", ""), "Curso": a.get("NOME-CURSO", ""),
               "Tipo": "Coorientação" if co else "Orientação principal", "Bolsa": a.get("NOME-DA-AGENCIA", "") if a.get("FLAG-BOLSA") == "SIM" else ""}
        sec["registros"].append(_reg(a, subtitulo=f"{label}{' (coorientação)' if co else ''} – {orientando}", categoria=cat, detalhes=det))


def _bancas(root, cv):
    sec = cv._add_secao("bancas", "Participação em bancas")
    dc = root.find("DADOS-COMPLEMENTARES")
    if dc is None:
        return
    mapa = {
        "PARTICIPACAO-EM-BANCA-DE-MESTRADO": ("banca_mestrado", "Banca de mestrado"),
        "PARTICIPACAO-EM-BANCA-DE-DOUTORADO": ("banca_doutorado", "Banca de doutorado"),
        "PARTICIPACAO-EM-BANCA-DE-EXAME-QUALIFICACAO": ("banca_qualificacao", "Exame de qualificação"),
        "PARTICIPACAO-EM-BANCA-DE-APERFEICOAMENTO-ESPECIALIZACAO": ("banca_especializacao", "Banca de especialização"),
        "PARTICIPACAO-EM-BANCA-DE-GRADUACAO": ("banca_graduacao", "Banca de graduação"),
        "BANCA-JULGADORA-PARA-PROFESSOR-TITULAR": ("banca_prof_titular", "Banca para professor titular"),
        "BANCA-JULGADORA-PARA-CONCURSO-PUBLICO": ("banca_concurso", "Banca de concurso público"),
        "BANCA-JULGADORA-PARA-LIVRE-DOCENCIA": ("banca_livre_docencia", "Banca de livre-docência"),
        "BANCA-JULGADORA-PARA-AVALIACAO-CURSOS": ("banca_avaliacao_cursos", "Banca de avaliação de cursos"),
        "OUTRAS-BANCAS-JULGADORAS": ("banca_outra", "Outra banca julgadora"),
    }
    for grupo_tag in ("PARTICIPACAO-EM-BANCA-TRABALHOS-CONCLUSAO", "PARTICIPACAO-EM-BANCA-JULGADORA"):
        g = dc.find(grupo_tag)
        if g is None:
            continue
        for el in g:
            a = _merge(el)
            cat, label = mapa.get(el.tag, ("banca_outra", el.tag.replace("-", " ").title()))
            cand = a.get("NOME-DO-CANDIDATO", "")
            nat = a.get("NATUREZA", "")
            cv._add_cat(cat, f"{cand + ' – ' if cand else ''}{_titulo(a)} ({_ano(a)})")
            det = {"Candidato": cand, "Natureza": nat, "Instituição": a.get("NOME-INSTITUICAO", ""), "Curso": a.get("NOME-CURSO", "")}
            sec["registros"].append(_reg(a, subtitulo=f"{label}{' – ' + cand if cand else ''}", categoria=cat, detalhes=det))


def _eventos(root, cv):
    sec = cv._add_secao("participacao_eventos", "Participação em eventos")
    pe = root.find("DADOS-COMPLEMENTARES/PARTICIPACAO-EM-EVENTOS-CONGRESSOS")
    if pe is None:
        return
    for el in pe:
        a = _merge(el)
        tipo_part = (a.get("TIPO-PARTICIPACAO", "") or "").lower()
        forma = (a.get("FORMA-PARTICIPACAO", "") or "")
        if re.search(r"conferencista|palestrante|moderador|mesa|debatedor|coordenador", tipo_part):
            cat = "evento_palestrante"
        elif "apresenta" in tipo_part:
            cat = None  # já pontuado em "Apresentação de trabalho"
        else:
            cat = "evento_participante"
        ev = a.get("NOME-DO-EVENTO", "")
        nat = a.get("NATUREZA", "")
        if cat:
            cv._add_cat(cat, f"{ev or _titulo(a)} ({_ano(a)}) – {forma}{' / ' + a.get('TIPO-PARTICIPACAO', '') if a.get('TIPO-PARTICIPACAO') else ''}")
        det = {"Evento": ev, "Natureza": nat, "Forma de participação": forma, "Tipo de participação": a.get("TIPO-PARTICIPACAO", ""),
               "Instituição": a.get("NOME-INSTITUICAO", ""), "Cidade": a.get("CIDADE-DO-EVENTO", "")}
        sec["registros"].append(_reg(a, subtitulo=f"{nat} – {forma}", categoria=cat, detalhes=det))


def _formacao_complementar(root, cv):
    sec = cv._add_secao("formacao_complementar", "Formação complementar")
    fc = root.find("DADOS-COMPLEMENTARES/FORMACAO-COMPLEMENTAR")
    if fc is None:
        return
    for el in fc:
        a = _attrs(el)
        cat = "form_curso_curta" if "CURTA" in el.tag else "form_outros"
        ch = a.get("CARGA-HORARIA", "")
        periodo = f"{a.get('ANO-DE-INICIO', '')} – {a.get('ANO-DE-CONCLUSAO', '') or 'atual'}"
        cv._add_cat(cat, f"{a.get('NOME-CURSO', '')} – {a.get('NOME-INSTITUICAO', '')} ({periodo}){' – ' + ch + ' h' if ch else ''}")
        sec["registros"].append(_reg(a, titulo=a.get("NOME-CURSO", ""), ano=periodo, subtitulo=a.get("NOME-INSTITUICAO", ""), categoria=cat,
                                     detalhes={"Carga horária": f"{ch} h" if ch else "", "Situação": a.get("STATUS-DO-CURSO", "").title()}))
