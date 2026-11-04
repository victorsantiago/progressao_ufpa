# -*- coding: utf-8 -*-
"""Relatório de pontuação do professor em PDF (reportlab): interstício, grupos escolhidos, itens e pontos."""
import datetime as dt
import io

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)
from xml.sax.saxutils import escape

UFPA = colors.HexColor("#b8202e")
UFPA_ESC = colors.HexColor("#6e1a20")
TINTA = colors.HexColor("#2a1b1d")
CINZA = colors.HexColor("#76605f")
LINHA = colors.HexColor("#eedfe0")
FUNDO = colors.HexColor("#fbe9eb")
CONTAGEM = {"registro": "por registro", "ano": "por ano", "semestre": "por semestre"}


def _t(v):
    """Texto seguro para as fontes padrão do PDF (cp1252) e para o marcador de Paragraph."""
    s = "" if v is None else str(v)
    s = s.encode("cp1252", "replace").decode("cp1252")
    return escape(s)


def _n(v, casas=1):
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _q(v):
    return _n(v, 2).rstrip("0").rstrip(",") if v != int(v) else str(int(v))


class _CanvasNumerado(rl_canvas.Canvas):
    """Canvas que conhece o total de páginas (para 'página X de Y')."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._paginas = []

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self._rodape(total)
            super().showPage()
        super().save()

    def _rodape(self, total):
        w, _ = A4
        self.setFont("Helvetica", 7.5)
        self.setFillColor(CINZA)
        self.drawString(18 * mm, 10 * mm, self._texto_rodape)
        self.drawRightString(w - 18 * mm, 10 * mm, f"Página {self._pageNumber} de {total}")


def gerar_pdf(*, prof, cv, pont, sit, fl, grupos, periodo_txt, app_nome, logo_path=None, logo_ext=None,
              logo_selo=False):
    buf = io.BytesIO()
    gerado = dt.datetime.now().strftime("%d/%m/%Y %H:%M")
    rodape = f"{app_nome} · Fonte: Plataforma Lattes/CNPq · Relatório gerado em {gerado}"

    def cabecalho(c, doc):
        w, h = A4
        c.saveState()
        c.setFillColor(UFPA_ESC)
        c.rect(0, h - 4 * mm, w, 4 * mm, stroke=0, fill=1)
        c.setFillColor(UFPA)
        c.rect(0, h - 26 * mm, w, 22 * mm, stroke=0, fill=1)
        x = 18 * mm
        if logo_path and logo_ext in ("png", "jpg", "jpeg", "webp"):
            try:
                from reportlab.lib.utils import ImageReader
                img = ImageReader(logo_path)
                iw, ih = img.getSize()
                alt = 16 * mm
                larg = alt * iw / ih
                if logo_selo:
                    c.setFillColor(colors.white)
                    c.roundRect(x - 1.5 * mm, h - 24 * mm, larg + 3 * mm, alt + 2 * mm, 2 * mm, stroke=0, fill=1)
                c.drawImage(img, x, h - 23 * mm, width=larg, height=alt, mask="auto")
                x += larg + 6 * mm
            except Exception:  # noqa – sem logo no PDF
                pass
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(x, h - 14 * mm, app_nome)
        c.setFont("Helvetica", 9.5)
        c.drawString(x, h - 19.5 * mm, "Relatório de pontuação para progressão funcional docente")
        c.restoreState()
        c._texto_rodape = rodape

    est = getSampleStyleSheet()
    s_nome = ParagraphStyle("nome", parent=est["Heading1"], fontName="Helvetica-Bold", fontSize=16, leading=19,
                            textColor=TINTA, spaceAfter=2)
    s_meta = ParagraphStyle("meta", parent=est["Normal"], fontName="Helvetica", fontSize=8.5, leading=11, textColor=CINZA)
    s_txt = ParagraphStyle("txt", parent=est["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=TINTA)
    s_h2 = ParagraphStyle("h2", parent=est["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, leading=14,
                          textColor=UFPA_ESC, spaceBefore=10, spaceAfter=4)
    s_cel = ParagraphStyle("cel", parent=s_txt, fontSize=8, leading=10)
    s_cel_b = ParagraphStyle("celb", parent=s_cel, fontName="Helvetica-Bold")
    s_reg = ParagraphStyle("reg", parent=s_cel, fontSize=7.2, leading=9, textColor=CINZA, leftIndent=6)
    s_num = ParagraphStyle("num", parent=s_cel, alignment=TA_RIGHT)
    s_num_b = ParagraphStyle("numb", parent=s_num, fontName="Helvetica-Bold")
    s_nota = ParagraphStyle("nota", parent=s_txt, fontSize=7.5, leading=10, textColor=CINZA)

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=33 * mm,
                            bottomMargin=17 * mm, title=f"Relatório de pontuação – {cv['dados'].get('nome', '')}",
                            author=app_nome)
    larg = A4[0] - 36 * mm
    els = []

    # identificação
    els.append(Paragraph(_t(cv["dados"].get("nome", "")), s_nome))
    els.append(Paragraph(
        f"ID Lattes {_t(prof['id'])}"
        + (f" · ORCID {_t(cv['dados'].get('orcid'))}" if cv["dados"].get("orcid") else "")
        + f" · Lattes atualizado em {_t(prof['data_atualizacao_br'])}", s_meta))
    els.append(Spacer(1, 6))

    # resumo da análise
    grupos_txt = ", ".join(fl["grupos"]) if fl["grupos"] else "nenhum"
    resumo = [
        [Paragraph("<b>Interstício avaliado</b>", s_cel), Paragraph(_t(periodo_txt), s_cel)],
        [Paragraph("<b>Grupos considerados</b>", s_cel), Paragraph(_t(grupos_txt), s_cel)],
        [Paragraph("<b>Total considerado</b>", s_cel), Paragraph(f"<b>{_n(sit['total'])} pontos</b>", s_cel)],
    ]
    if sit.get("considera_i"):
        if sit["excedente_i"] > 0:
            regra = (f"Grupo I (ensino) limitado a 50% da pontuação total: obteve {_n(sit['grupo_i'])}, "
                     f"considerados {_n(sit['grupo_i_considerado'])} (−{_n(sit['excedente_i'])}).")
        else:
            regra = f"Grupo I (ensino): {_n(sit['grupo_i'])} pontos, {_n(sit['pct_i'])}% do total — dentro do limite de 50%."
        resumo.append([Paragraph("<b>Regra do Grupo I</b>", s_cel), Paragraph(_t(regra), s_cel)])
    t = Table(resumo, colWidths=[42 * mm, larg - 42 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), FUNDO), ("BOX", (0, 0), (-1, -1), 0.6, UFPA),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, LINHA), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    els.append(t)

    # pontos por grupo
    els.append(Paragraph("Pontos por grupo", s_h2))
    linhas = [[Paragraph("<b>Grupo</b>", s_cel), Paragraph("<b>Descrição</b>", s_cel), Paragraph("<b>Pontos</b>", s_num)]]
    for g in fl["grupos"]:
        pts = pont["totais_grupo"].get(g, 0.0)
        obs = ""
        if g == "I" and sit.get("excedente_i", 0) > 0:
            obs = f" (considerados {_n(sit['grupo_i_considerado'])})"
        linhas.append([Paragraph(_t(g), s_cel), Paragraph(_t(grupos.get(g, "")), s_cel), Paragraph(_n(pts) + _t(obs), s_num)])
    linhas.append([Paragraph("", s_cel), Paragraph("<b>Total considerado</b>", s_cel), Paragraph(f"<b>{_n(sit['total'])}</b>", s_num)])
    t = Table(linhas, colWidths=[16 * mm, larg - 16 * mm - 38 * mm, 38 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, UFPA), ("LINEBELOW", (0, 1), (-1, -2), 0.3, LINHA),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, TINTA), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    els.append(t)

    # detalhamento por grupo
    cw = [58 * mm, larg - 58 * mm - 20 * mm - 12 * mm - 12 * mm - 16 * mm, 20 * mm, 12 * mm, 12 * mm, 16 * mm]
    for g in fl["grupos"]:
        do_grupo = [l for l in pont["linhas"] if l["grupo"] == g and l["item_key"] and l["registros"]]
        titulo = Paragraph(f"Grupo {_t(g)} — {_t(grupos.get(g, ''))} · {_n(pont['totais_grupo'].get(g, 0.0))} pontos", s_h2)
        if not do_grupo:
            els.append(KeepTogether([titulo, Paragraph("Nenhum item do Lattes pontuado neste grupo no interstício.", s_nota)]))
            continue
        dados = [[Paragraph("<b>Item do Lattes</b>", s_cel), Paragraph("<b>Item da tabela</b>", s_cel),
                  Paragraph("<b>Contagem</b>", s_cel), Paragraph("<b>Qtd.</b>", s_num), Paragraph("<b>Valor</b>", s_num),
                  Paragraph("<b>Pontos</b>", s_num)]]
        for l in do_grupo:
            cel = [Paragraph(f"<b>{_t(l['label'])}</b>", s_cel)]
            for r in l["registros"]:
                extra = ""
                if l["contagem"] in ("ano", "semestre"):
                    un = "ano(s)" if l["contagem"] == "ano" else "semestre(s)"
                    extra = f" — {_q(r.get('qtd_considerada', 0))} {un}"
                cel.append(Paragraph("• " + _t(r["desc"]) + _t(extra), s_reg))
            dados.append([
                cel,
                Paragraph(f"<b>{_t(l['item_codigo'])}</b> {_t(l['item_atividade'])}", s_cel),
                Paragraph(_t(CONTAGEM.get(l["contagem"], l["contagem"])), s_cel),
                Paragraph(_q(l["qtd"]), s_num),
                Paragraph(_q(l["valor"]), s_num),
                Paragraph(f"<b>{_n(l['pontos'])}</b>", s_num_b),
            ])
        dados.append(["", Paragraph("<b>Subtotal do grupo</b>", s_cel), "", "", "",
                      Paragraph(f"<b>{_n(pont['totais_grupo'].get(g, 0.0))}</b>", s_num_b)])
        t = Table(dados, colWidths=cw, repeatRows=1)
        t.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, UFPA), ("LINEBELOW", (0, 1), (-1, -2), 0.3, LINHA),
            ("LINEABOVE", (0, -1), (-1, -1), 0.8, TINTA), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ]))
        els.append(titulo)
        els.append(t)

    els.append(Spacer(1, 10))
    els.append(Paragraph(
        "Pontuação calculada automaticamente a partir do XML do Currículo Lattes, com os valores e o mapeamento definidos "
        "na gestão. Entram os registros cujo período intercepta o interstício; itens contados por ano ou semestre "
        "consideram apenas os meses dentro dele. Registros que trazem só o ano valem de janeiro a dezembro. "
        "O Grupo I (ensino) é limitado a 50% da pontuação total. Itens sem correspondência no Lattes devem ser "
        "comprovados à parte.", s_nota))

    doc.build(els, onFirstPage=cabecalho, onLaterPages=cabecalho, canvasmaker=_CanvasNumerado)
    return buf.getvalue()
