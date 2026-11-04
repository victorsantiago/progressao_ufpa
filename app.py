# -*- coding: utf-8 -*-
"""
Progressão Automatizada UFPA (Lattes) – importação de currículos via eLattes e pontuação para progressão docente.

Execução:  python app.py   (http://localhost:5000)
Admin:     /admin  (usuário: admin / senha: senha)
"""
import csv
import datetime as dt
import functools
import io
import json
import os
import re
import sqlite3
import threading
import unicodedata
import uuid

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template, request,
                   send_file, session, url_for)

import fotos
from genero import inferir_genero
from elattes_client import ELattesClient, ELattesError, extrair_xmls
from lattes_parser import PARSER_VERSAO, parse_lattes_xml
from scoring import CATEGORIAS, CATEGORIAS_MAP, CONTAGENS, calcular_pontuacao, serie_anual, tabela_itens
from scoring import GRUPOS as GRUPOS_ANEXO

APP_NOME = "Progressão Automatizada UFPA"
APP_SUB = "Lattes"
LOGO_EXTS = ("png", "svg", "jpg", "jpeg", "webp")
LOGO_MIME = {"png": "image/png", "svg": "image/svg+xml", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR") or os.path.join(BASE_DIR, "data")
XML_DIR = os.path.join(DATA_DIR, "curriculos")
FOTO_DIR = os.path.join(DATA_DIR, "fotos")
DB_PATH = os.path.join(DATA_DIR, "app.db")
os.makedirs(XML_DIR, exist_ok=True)

ADMIN_USER = os.environ.get("ADMIN_USER") or "admin"
ADMIN_PASS = os.environ.get("ADMIN_PASS") or "senha"

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "lattes-ufpa-dev-key")
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


def open_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    con = open_db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS professores (
        id TEXT PRIMARY KEY,
        nome TEXT,
        data_atualizacao TEXT,
        data_atualizacao_br TEXT,
        importado_em TEXT,
        remota_atualizacao TEXT,
        verificado_em TEXT,
        dados_json TEXT
    );
    CREATE TABLE IF NOT EXISTS itens (
        key TEXT PRIMARY KEY, grupo TEXT, numero INTEGER, variante TEXT,
        atividade TEXT, valor_padrao REAL, valor REAL, ordem INTEGER
    );
    CREATE TABLE IF NOT EXISTS mapeamento (categoria TEXT PRIMARY KEY, item_key TEXT);
    CREATE TABLE IF NOT EXISTS grupos (codigo TEXT PRIMARY KEY, nome TEXT, ordem INTEGER, original INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor TEXT);
    """)
    for i, (cod, nome) in enumerate(GRUPOS_ANEXO.items(), 1):
        con.execute("INSERT OR IGNORE INTO grupos (codigo, nome, ordem, original) VALUES (?,?,?,1)", (cod, nome, i))
    gcols = {r["name"] for r in con.execute("PRAGMA table_info(grupos)")}
    if "minimo" not in gcols:
        con.execute("ALTER TABLE grupos ADD COLUMN minimo REAL")
    icols = {r["name"] for r in con.execute("PRAGMA table_info(itens)")}
    for col in ("codigo", "contagem"):
        if col not in icols:
            con.execute(f"ALTER TABLE itens ADD COLUMN {col} TEXT")
    # Insere os itens do Anexo I que ainda não existem. Itens existentes NÃO são sobrescritos:
    # código, atividade, contagem e valor são editáveis na gestão.
    for it in tabela_itens():
        con.execute("INSERT OR IGNORE INTO itens (key, codigo, grupo, numero, variante, atividade, contagem, valor_padrao, valor, ordem) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (it["key"], it["codigo"], it["grupo"], it["numero"], it["variante"], it["atividade"], it["contagem_padrao"],
                     it["valor_padrao"], it["valor_padrao"], it["ordem"]))
        con.execute("UPDATE itens SET codigo=COALESCE(NULLIF(codigo,''), ?), contagem=COALESCE(NULLIF(contagem,''), ?) WHERE key=?",
                    (it["codigo"], it["contagem_padrao"], it["key"]))
    for c in CATEGORIAS:
        con.execute("INSERT OR IGNORE INTO mapeamento (categoria, item_key) VALUES (?,?)", (c[0], c[3]))
    cols = {r["name"] for r in con.execute("PRAGMA table_info(professores)")}
    for col in ("id_k", "foto_tentativa", "genero_manual"):
        if col not in cols:
            con.execute(f"ALTER TABLE professores ADD COLUMN {col} TEXT")
    for chave, valor in (("elattes_url", "https://elattes.ufpa.br"), ("interst_ini", ""), ("interst_fim", ""), ("exibir_fotos", "1"),
                         ("grupos", ",".join(GRUPOS_ANEXO))):
        con.execute("INSERT OR IGNORE INTO config (chave, valor) VALUES (?, ?)", (chave, valor))
    con.commit()
    reprocessar_desatualizados(con)
    con.close()


def reprocessar_desatualizados(con):
    """Reinterpreta, a partir do XML salvo, currículos importados com versão antiga do parser."""
    for row in con.execute("SELECT id, dados_json FROM professores").fetchall():
        try:
            versao = json.loads(row["dados_json"]).get("versao")
        except (TypeError, ValueError):
            versao = None
        if versao == PARSER_VERSAO:
            continue
        path = os.path.join(XML_DIR, f"{row['id']}.xml")
        if not os.path.exists(path):
            continue
        try:
            with open(path, "rb") as f:
                parsed = parse_lattes_xml(f.read())
            con.execute("UPDATE professores SET dados_json=? WHERE id=?", (json.dumps(parsed, ensure_ascii=False), row["id"]))
        except Exception:  # noqa
            continue
    con.commit()


def cfg(chave, default=None, con=None):
    c = con or get_db()
    row = c.execute("SELECT valor FROM config WHERE chave=?", (chave,)).fetchone()
    return row["valor"] if row else default


def carregar_itens(con=None):
    c = con or get_db()
    rows = c.execute("SELECT * FROM itens ORDER BY ordem").fetchall()
    return [dict(r) for r in rows]


def carregar_mapeamento(con=None):
    c = con or get_db()
    return {r["categoria"]: r["item_key"] for r in c.execute("SELECT * FROM mapeamento")}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def agora():
    return dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def fmt_dt(iso):
    if not iso:
        return "—"
    try:
        d = dt.datetime.fromisoformat(iso)
        return d.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso


def parse_remota(s):
    """'DD/MM/AAAA HH:MM:SS' -> datetime"""
    if not s:
        return None
    for f in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(s.strip(), f)
        except ValueError:
            continue
    return None


def status_atualizacao(prof):
    """Retorna 'atualizado', 'desatualizado' ou 'desconhecido'."""
    remota = parse_remota(prof["remota_atualizacao"])
    if remota is None or not prof["data_atualizacao"]:
        return "desconhecido"
    try:
        local = dt.datetime.fromisoformat(prof["data_atualizacao"])
    except ValueError:
        return "desconhecido"
    return "atualizado" if remota <= local else "desatualizado"


app.jinja_env.filters["fmt_dt"] = fmt_dt
app.jinja_env.globals["status_atualizacao"] = status_atualizacao
app.jinja_env.globals["APP_NOME"] = APP_NOME
app.jinja_env.globals["APP_SUB"] = APP_SUB


def carregar_grupos(con=None):
    c = con or get_db()
    return {r["codigo"]: r["nome"] for r in c.execute("SELECT codigo, nome FROM grupos ORDER BY ordem, rowid")}


def _num(v):
    try:
        x = float(str(v).replace(",", ".").strip())
        return x if x >= 0 else None
    except (TypeError, ValueError):
        return None


GRUPO_ENSINO = "I"
TETO_ENSINO = 0.5  # Grupo I não pode exceder 50% da pontuação total


def situacao(pont, fl, con=None):
    """Regra do Anexo I: o Grupo I (ensino) não pode exceder 50% da pontuação total.
    Com I ≤ 50% de (I + demais), o Grupo I conta no máximo o valor da soma dos demais grupos considerados.
    Devolve o total ajustado e o detalhe do Grupo I."""
    bruto_i = round(pont["totais_grupo"].get(GRUPO_ENSINO, 0.0), 2)
    considera_i = GRUPO_ENSINO in fl["grupos"]
    demais = round(pont["total"] - bruto_i, 2) if considera_i else round(pont["total"], 2)
    teto = round(demais * TETO_ENSINO / (1 - TETO_ENSINO), 2)  # = demais, para 50%
    excedente = round(max(0.0, bruto_i - teto), 2) if considera_i else 0.0
    total = round(pont["total"] - excedente, 2)
    return {"grupo_i": bruto_i, "grupo_i_considerado": round(bruto_i - excedente, 2), "teto_i": teto,
            "demais": demais, "excedente_i": excedente, "considera_i": considera_i and bruto_i > 0, "total": total,
            "pct_i": round(100.0 * (bruto_i - excedente) / total, 1) if total else 0.0}


def G():
    """Grupos atuais (código → nome), na ordem definida na gestão. Cache por requisição."""
    if "grupos" not in g:
        g.grupos = carregar_grupos()
    return g.grupos


ROMANOS = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
           (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def romano(n):
    out = ""
    for v, r in ROMANOS:
        while n >= v:
            out += r
            n -= v
    return out


def genero_de(prof):
    """Persona do avatar: escolha manual do admin ou palpite pelo primeiro nome."""
    try:
        manual = prof["genero_manual"]
    except (KeyError, IndexError):
        manual = None
    return manual if manual in ("M", "F", "N") else inferir_genero(prof["nome"])


app.jinja_env.globals["genero_de"] = genero_de


def regex_variante(codigo, grupo):
    m = re.fullmatch(rf"{re.escape(grupo)}\.(\d+)\.[a-z]", codigo or "")
    return f"{grupo}.{m.group(1)}" if m else ""


app.jinja_env.filters["regex_variante"] = regex_variante


def tag_partes(tags):
    """'A › B › C (cond)' → (['A', 'B', 'C'], 'cond'). A condição começa no primeiro ' (' ou ' — ' do último trecho."""
    partes = [p.strip() for p in (tags or "").split(" › ") if p.strip()]
    cond = ""
    if partes:
        ult = partes[-1]
        cortes = [i for i in (ult.find(" ("), ult.find(" — ")) if i > 0]
        if cortes:
            i = min(cortes)
            partes[-1], cond = ult[:i].strip(), ult[i:].strip(" —")
            if cond.startswith("(") and cond.endswith(")") and cond.count("(") == 1:
                cond = cond[1:-1]
    return partes, cond


app.jinja_env.filters["tag_partes"] = tag_partes
app.jinja_env.globals["inferir_genero"] = inferir_genero


def logo_path():
    for ext in LOGO_EXTS:
        p = os.path.join(DATA_DIR, f"logo.{ext}")
        if os.path.exists(p):
            return p, ext
    for ext in LOGO_EXTS:
        p = os.path.join(BASE_DIR, "static", f"logo-ufpa.{ext}")
        if os.path.exists(p):
            return p, ext
    return None, None


def logo_fundo():
    """'selo' (logo sobre selo branco) ou 'sem' (logo direto sobre o vermelho)."""
    escolha = cfg("logo_fundo", "auto")
    if escolha in ("selo", "sem"):
        return escolha
    auto = cfg("logo_fundo_auto", None)
    if auto is None:
        # logo enviada antes desta versão: analisa uma vez (apara margens e detecta se é clara)
        path, ext = logo_path()
        if not path:
            return "selo"
        auto = "sem" if preparar_logo(path, ext) else "selo"
        db = get_db()
        db.execute("INSERT INTO config (chave, valor) VALUES ('logo_fundo_auto', ?) "
                   "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (auto,))
        db.commit()
    return auto


def preparar_logo(path, ext):
    """Apara margens transparentes e diz se a logo é clara (branca), para exibir sem selo branco."""
    if ext == "svg":
        return False
    try:
        from PIL import Image
        im = Image.open(path)
        im.load()
        im = im.convert("RGBA")
        bbox = im.split()[3].getbbox()
        if bbox and bbox != (0, 0) + im.size:
            im = im.crop(bbox)
        vis = [p for p in im.resize((min(200, im.width), min(200, im.height))).getdata() if p[3] > 40]
        clara = bool(vis) and sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b, _ in vis) / len(vis) > 200
        if ext in ("png", "webp"):
            im.save(path)
        return clara
    except Exception:  # noqa – mantém o arquivo como veio
        return False


@app.context_processor
def _ctx():
    return {"tem_logo": logo_path()[0] is not None, "ANO_ATUAL": dt.date.today().year, "GRUPOS": G(),
            "logo_fundo": logo_fundo(), "logo_fundo_escolha": cfg("logo_fundo", "auto"),
            "logo_versao": int(os.path.getmtime(logo_path()[0])) if logo_path()[0] else 0,
            "fotos_on": False}  # busca de fotos no CNPq desativada (avatares no lugar)


# ---------------------------------------------------------------------------
# Filtros da análise (interstício + grupos)
# ---------------------------------------------------------------------------
def _ano(v):
    try:
        a = int(str(v).strip())
        return a if 1900 <= a <= 2100 else None
    except (TypeError, ValueError):
        return None


def _mes_ano(v, fim=False):
    """'AAAA-MM' (ou 'MM/AAAA', ou só 'AAAA') → (ano, mês). Só o ano: janeiro no início, dezembro no fim."""
    v = (v or "").strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", v) or None
    if m:
        a, ms = int(m.group(1)), int(m.group(2))
    else:
        m = re.fullmatch(r"(\d{1,2})/(\d{4})", v)
        if m:
            a, ms = int(m.group(2)), int(m.group(1))
        else:
            a = _ano(v)
            if a is None:
                return None
            ms = 12 if fim else 1
    if not (1900 <= a <= 2100 and 1 <= ms <= 12):
        return None
    return a, ms


def _monta_filtros(ini, fim, grupos):
    if ini and fim and ini > fim:
        ini, fim = fim, ini
    return {"ini": f"{ini[0]:04d}-{ini[1]:02d}" if ini else None, "fim": f"{fim[0]:04d}-{fim[1]:02d}" if fim else None,
            "ai": ini[0] if ini else None, "mi": ini[1] if ini else None,
            "af": fim[0] if fim else None, "mf": fim[1] if fim else None, "grupos": grupos}


def filtros_padrao(con=None):
    gs = [g for g in (cfg("grupos", ",".join(G()), con) or "").split(",") if g in G()]
    return _monta_filtros(_mes_ano(cfg("interst_ini", "", con)), _mes_ano(cfg("interst_fim", "", con), fim=True), gs)


def ler_filtros():
    """Lê ?ini=AAAA-MM&fim=AAAA-MM&g=...&f=1 da URL; sem f=1 usa os padrões definidos na Configuração."""
    if request.args.get("f") != "1":
        return filtros_padrao()
    grupos = [g for g in request.args.getlist("g") if g in G()]
    return _monta_filtros(_mes_ano(request.args.get("ini")), _mes_ano(request.args.get("fim"), fim=True), grupos)


def filtros_query(fl):
    q = {"f": "1", "ini": fl["ini"] or "", "fim": fl["fim"] or ""}
    parts = [f"{k}={v}" for k, v in q.items()] + [f"g={g}" for g in fl["grupos"]]
    return "&".join(parts)


def _mm_aaaa(v):
    return f"{v[5:7]}/{v[:4]}" if v else ""


def descreve_periodo(fl):
    if fl["ini"] and fl["fim"]:
        return f"{_mm_aaaa(fl['ini'])} a {_mm_aaaa(fl['fim'])}"
    if fl["ini"]:
        return f"a partir de {_mm_aaaa(fl['ini'])}"
    if fl["fim"]:
        return f"até {_mm_aaaa(fl['fim'])}"
    return "todo o currículo"


def descreve_filtros(fl):
    if len(fl["grupos"]) == len(G()):
        gtxt = "todos os grupos"
    elif not fl["grupos"]:
        gtxt = "nenhum grupo"
    else:
        gtxt = "grupos " + ", ".join(fl["grupos"])
    return f"Interstício: {descreve_periodo(fl)} · {gtxt}"


def presets_intersticio():
    """Atalhos: últimos 24 e 36 meses completos (terminando no mês anterior) e todo o currículo."""
    hoje = dt.date.today()
    fim_a, fim_m = (hoje.year, hoje.month - 1) if hoje.month > 1 else (hoje.year - 1, 12)
    out = []
    for meses in (24, 36):
        idx = fim_a * 12 + fim_m - 1 - (meses - 1)
        ini_a, ini_m = idx // 12, idx % 12 + 1
        out.append((f"Últimos {meses // 12} anos", f"{ini_a:04d}-{ini_m:02d}", f"{fim_a:04d}-{fim_m:02d}"))
    return out


app.jinja_env.globals["descreve_periodo"] = descreve_periodo
app.jinja_env.globals["presets_intersticio"] = presets_intersticio
app.jinja_env.globals["descreve_filtros"] = descreve_filtros


def extrair_ids(texto):
    return list(dict.fromkeys(re.findall(r"(?<!\d)\d{16}(?!\d)", texto or "")))


def salvar_curriculo(con, id_lattes, xml_bytes):
    parsed = parse_lattes_xml(xml_bytes)
    pid = parsed["dados"].get("id") or id_lattes
    with open(os.path.join(XML_DIR, f"{pid}.xml"), "wb") as f:
        f.write(xml_bytes)
    # currículo novo/atualizado: busca a foto de novo na próxima exibição
    try:
        os.remove(os.path.join(FOTO_DIR, f"{pid}.jpg"))
    except OSError:
        pass
    con.execute("UPDATE professores SET foto_tentativa=NULL WHERE id=?", (pid,))
    d = parsed["dados"]
    con.execute("""INSERT INTO professores (id, nome, data_atualizacao, data_atualizacao_br, importado_em, dados_json)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET nome=excluded.nome, data_atualizacao=excluded.data_atualizacao,
                   data_atualizacao_br=excluded.data_atualizacao_br, importado_em=excluded.importado_em, dados_json=excluded.dados_json""",
                (pid, d["nome"], d["data_atualizacao"], f"{d['data_atualizacao_br']} {d['hora_atualizacao']}".strip(), agora(), json.dumps(parsed, ensure_ascii=False)))
    con.commit()
    return pid, d["nome"]


def verificar_remoto(con, ids):
    """Consulta a data de atualização no eLattes e grava no banco. Retorna {id: 'DD/MM/AAAA HH:MM:SS'}."""
    client = ELattesClient(base_url=cfg("elattes_url", "https://elattes.ufpa.br", con))
    resultado = client.ultima_atualizacao(ids)
    for pid, data in resultado.items():
        con.execute("UPDATE professores SET remota_atualizacao=?, verificado_em=? WHERE id=?", (str(data) if data else None, agora(), pid))
    con.commit()
    return resultado


# ---------------------------------------------------------------------------
# Jobs de importação (em memória, thread em segundo plano)
# ---------------------------------------------------------------------------
JOBS = {}
JOBS_LOCK = threading.Lock()


def novo_job(ids, origem="elattes"):
    job_id = uuid.uuid4().hex[:12]
    job = {"id": job_id, "status": "pendente", "mensagem": "Aguardando...", "ids": ids, "total": len(ids),
           "baixados": 0, "importados": [], "erros": [], "criado_em": agora(), "origem": origem, "etapa": ""}
    with JOBS_LOCK:
        JOBS[job_id] = job
    t = threading.Thread(target=_executar_job, args=(job,), daemon=True)
    t.start()
    return job_id


def _executar_job(job):
    con = open_db()
    try:
        job["status"] = "executando"
        client = ELattesClient(base_url=cfg("elattes_url", "https://elattes.ufpa.br", con))
        LOTE = 25
        ids = job["ids"]
        for i in range(0, len(ids), LOTE):
            lote = ids[i:i + LOTE]
            job["etapa"] = f"Baixando lote {i // LOTE + 1} de {(len(ids) + LOTE - 1) // LOTE} "

            def on_progress(p, base=i):
                job["baixados"] = base + int(p.get("current") or 0)
                job["mensagem"] = f"Download: {p.get('status', '')} – {p.get('message') or ''} ({p.get('current', 0)}/{p.get('total', len(lote))})"

            try:
                xmls = client.baixar_curriculos(lote, on_progress=on_progress)
            except ELattesError as e:
                for pid in lote:
                    job["erros"].append({"id": pid, "erro": str(e)})
                continue
            job["etapa"] = "Importando currículos"
            for pid in lote:
                xml = xmls.get(pid)
                if not xml:
                    job["erros"].append({"id": pid, "erro": "XML não veio no download (ID inexistente ou falha no download)"})
                    continue
                try:
                    real_id, nome = salvar_curriculo(con, pid, xml)
                    job["importados"].append({"id": real_id, "nome": nome})
                    job["mensagem"] = f"Importado: {nome}"
                except Exception as e:  # noqa
                    job["erros"].append({"id": pid, "erro": f"Falha ao interpretar XML: {e}"})
        # atualiza data remota dos importados
        try:
            if job["importados"]:
                verificar_remoto(con, [p["id"] for p in job["importados"]])
        except Exception as e:  # noqa
            job["erros"].append({"id": "-", "erro": f"Falha ao consultar data de atualização: {e}"})
        job["status"] = "concluido"
        job["etapa"] = "Concluído"
        job["mensagem"] = f"{len(job['importados'])} currículo(s) importado(s), {len(job['erros'])} erro(s)."
    except Exception as e:  # noqa
        job["status"] = "erro"
        job["mensagem"] = str(e)
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Autenticação admin
# ---------------------------------------------------------------------------
def login_required(view):
    @functools.wraps(view)
    def wrapped(*a, **kw):
        if not session.get("admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*a, **kw)
    return wrapped


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    erro = None
    if request.method == "POST":
        if request.form.get("usuario") == ADMIN_USER and request.form.get("senha") == ADMIN_PASS:
            session["admin"] = True
            return redirect(request.args.get("next") or url_for("admin_professores"))
        erro = "Usuário ou senha inválidos."
    return render_template("login.html", erro=erro)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Páginas públicas
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    db = get_db()
    profs = db.execute("SELECT id, nome, data_atualizacao, data_atualizacao_br, importado_em, remota_atualizacao, verificado_em, genero_manual FROM professores ORDER BY nome").fetchall()
    return render_template("index.html", profs=profs)


def _montar_pontuacao(prof_row, filtros=None, itens=None, mapeamento=None):
    parsed = json.loads(prof_row["dados_json"])
    itens = itens if itens is not None else carregar_itens()
    itens_por_key = {i["key"]: i for i in itens}
    mapeamento = mapeamento if mapeamento is not None else carregar_mapeamento()
    fl = filtros or _monta_filtros(None, None, list(G()))
    pont = calcular_pontuacao(parsed["categorias"], itens_por_key, mapeamento,
                              ano_ini=fl["ai"], mes_ini=fl["mi"], ano_fim=fl["af"], mes_fim=fl["mf"],
                              grupos=fl["grupos"], todos_grupos=list(G()))
    return parsed, pont, itens


@app.route("/professor/<pid>")
def professor(pid):
    db = get_db()
    prof = db.execute("SELECT * FROM professores WHERE id=?", (pid,)).fetchone()
    if not prof:
        abort(404)
    fl = ler_filtros()
    parsed, pont, itens = _montar_pontuacao(prof, fl)
    sit = situacao(pont, fl)
    grafico = dados_grafico(parsed, itens, fl)
    pontos_cat = {l["categoria"]: l for l in pont["linhas"]}
    por_grupo = {g: [l for l in pont["linhas"] if l["grupo"] == g] for g in G()}
    grupo_ativo = request.args.get("grupo")
    if grupo_ativo not in G():
        # primeiro grupo considerado que tenha pontos; senão o primeiro considerado; senão I
        grupo_ativo = next((g for g in fl["grupos"] if pont["totais_grupo"][g] > 0),
                           fl["grupos"][0] if fl["grupos"] else "I")
    return render_template("professor.html", prof=prof, cv=parsed, pont=pont, por_grupo=por_grupo, fl=fl,
                           fl_query=filtros_query(fl), pontos_cat=pontos_cat, status=status_atualizacao(prof),
                           aba=request.args.get("aba", "pontuacao"), grupo_ativo=grupo_ativo, sit=sit, grafico=grafico)


# Paleta categórica de referência (ordem fixa; nunca reciclada). Grupos além do 8º viram "Outros grupos".
CORES_GRUPOS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
COR_OUTROS = "#5b6168"


def dados_grafico(parsed, itens, fl):
    """Série anual de pontos por grupo considerado, com os anos dentro/fora do interstício."""
    grupos = G()
    serie = serie_anual(parsed["categorias"], {i["key"]: i for i in itens}, carregar_mapeamento(), list(grupos))
    lo = fl["ai"] * 12 + fl["mi"] - 1 if fl["ai"] else None
    hi = fl["af"] * 12 + fl["mf"] - 1 if fl["af"] else None
    dentro = [(lo is None or a * 12 + 11 >= lo) and (hi is None or a * 12 <= hi) for a in serie["anos"]]
    ordem = list(grupos)
    datasets, outros = [], None
    for g_ in fl["grupos"]:
        i = ordem.index(g_)
        valores = serie["series"].get(g_, [0.0] * len(serie["anos"]))
        if i < len(CORES_GRUPOS):
            datasets.append({"grupo": g_, "nome": grupos[g_], "cor": CORES_GRUPOS[i], "valores": valores})
        else:
            if outros is None:
                outros = {"grupo": "outros", "nome": "Outros grupos", "cor": COR_OUTROS, "valores": [0.0] * len(valores)}
            outros["valores"] = [round(a + b, 2) for a, b in zip(outros["valores"], valores)]
    if outros:
        datasets.append(outros)
    totais = [round(sum(d["valores"][i] for d in datasets), 2) for i in range(len(serie["anos"]))]
    # série de cada grupo (inclusive os fora da análise), para o gráfico acompanhar a aba selecionada
    por_grupo = {g_: {"nome": grupos[g_], "cor": CORES_GRUPOS[i] if i < len(CORES_GRUPOS) else COR_OUTROS,
                      "valores": serie["series"].get(g_, [0.0] * len(serie["anos"])), "considerado": g_ in fl["grupos"]}
                 for i, g_ in enumerate(ordem)}
    return {"anos": serie["anos"], "dentro": dentro, "datasets": datasets, "totais": totais, "por_grupo": por_grupo,
            "tem_dados": any(any(v["valores"]) for v in por_grupo.values())}


@app.route("/professor/<pid>/relatorio.pdf")
def relatorio_pdf(pid):
    """Relatório em PDF com os itens e pontuações do interstício e dos grupos escolhidos."""
    from relatorio import gerar_pdf
    db = get_db()
    prof = db.execute("SELECT * FROM professores WHERE id=?", (pid,)).fetchone()
    if not prof:
        abort(404)
    fl = ler_filtros()
    parsed, pont, _ = _montar_pontuacao(prof, fl)
    sit = situacao(pont, fl)
    lp, ext = logo_path()
    pdf = gerar_pdf(prof=prof, cv=parsed, pont=pont, sit=sit, fl=fl, grupos=G(), periodo_txt=descreve_periodo(fl),
                    app_nome=APP_NOME, logo_path=lp, logo_ext=ext, logo_selo=(logo_fundo() == "selo"))
    nome = re.sub(r"[^A-Za-z0-9]+", "_", unicodedata.normalize("NFKD", parsed["dados"].get("nome", pid))
                  .encode("ascii", "ignore").decode()).strip("_") or pid
    periodo = f"_{fl['ini'] or 'inicio'}_a_{fl['fim'] or 'atual'}" if (fl["ini"] or fl["fim"]) else "_todo_curriculo"
    return app.response_class(pdf, mimetype="application/pdf",
                              headers={"Content-Disposition": f'inline; filename="relatorio_{nome}{periodo}.pdf"'})


@app.route("/professor/<pid>/xml")
def professor_xml(pid):
    path = os.path.join(XML_DIR, f"{pid}.xml")
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True, download_name=f"{pid}.xml")


@app.route("/professor/<pid>/atualizar", methods=["POST"])
def professor_atualizar(pid):
    if not re.fullmatch(r"\d{16}", pid):
        abort(400)
    job_id = novo_job([pid], origem="atualizar")
    return redirect(url_for("job_page", job_id=job_id, voltar=url_for("professor", pid=pid)))


@app.route("/api/professor/<pid>/verificar")
def api_verificar(pid):
    db = get_db()
    prof = db.execute("SELECT * FROM professores WHERE id=?", (pid,)).fetchone()
    if not prof:
        return jsonify({"erro": "não encontrado"}), 404
    try:
        res = verificar_remoto(db, [pid])
    except Exception as e:  # noqa
        return jsonify({"status": "desconhecido", "erro": str(e), "local": prof["data_atualizacao_br"]}), 200
    prof = db.execute("SELECT * FROM professores WHERE id=?", (pid,)).fetchone()
    return jsonify({"status": status_atualizacao(prof), "remota": res.get(pid), "local": prof["data_atualizacao_br"],
                    "verificado_em": fmt_dt(prof["verificado_em"])})


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------
@app.route("/jobs/<job_id>")
def job_page(job_id):
    job = JOBS.get(job_id)
    if not job:
        abort(404)
    return render_template("job.html", job=job, voltar=request.args.get("voltar") or url_for("admin_professores"))


@app.route("/api/jobs/<job_id>")
def api_job(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"erro": "job não encontrado"}), 404
    return jsonify(job)


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
@app.route("/admin")
@login_required
def admin_home():
    return redirect(url_for("admin_professores"))


@app.route("/admin/professores")
@login_required
def admin_professores():
    db = get_db()
    fl = ler_filtros()
    itens, mapa = carregar_itens(db), carregar_mapeamento(db)
    profs = []
    for p in db.execute("SELECT * FROM professores ORDER BY nome").fetchall():
        _, pont, _ = _montar_pontuacao(p, fl, itens, mapa)
        profs.append({**dict(p), "total": pont["total"], "totais_grupo": pont["totais_grupo"], "sit": situacao(pont, fl, db)})
    ordem = request.args.get("ordem", "nome")
    if ordem == "pontos":
        profs.sort(key=lambda x: -x["total"])
    jobs = sorted(JOBS.values(), key=lambda j: j["criado_em"], reverse=True)[:10]
    return render_template("admin_professores.html", profs=profs, jobs=jobs, fl=fl, fl_query=filtros_query(fl), ordem=ordem)


@app.route("/admin/professores/<pid>/persona", methods=["POST"])
@login_required
def admin_persona(pid):
    v = request.form.get("genero")
    db = get_db()
    db.execute("UPDATE professores SET genero_manual=? WHERE id=?", (v if v in ("M", "F", "N") else None, pid))
    db.commit()
    return redirect(request.referrer or url_for("admin_professores"))


@app.route("/admin/professores/<pid>/remover", methods=["POST"])
@login_required
def admin_remover(pid):
    db = get_db()
    db.execute("DELETE FROM professores WHERE id=?", (pid,))
    db.commit()
    try:
        os.remove(os.path.join(XML_DIR, f"{pid}.xml"))
    except OSError:
        pass
    flash(f"Professor {pid} removido.", "ok")
    return redirect(url_for("admin_professores"))


@app.route("/admin/verificar-todos", methods=["POST"])
@login_required
def admin_verificar_todos():
    db = get_db()
    ids = [r["id"] for r in db.execute("SELECT id FROM professores")]
    try:
        for i in range(0, len(ids), 50):
            verificar_remoto(db, ids[i:i + 50])
        flash(f"Versão do Lattes verificada para {len(ids)} professor(es).", "ok")
    except Exception as e:  # noqa
        flash(f"Falha ao consultar a versão do Lattes: {e}", "erro")
    return redirect(url_for("admin_professores"))


@app.route("/admin/atualizar-desatualizados", methods=["POST"])
@login_required
def admin_atualizar_desatualizados():
    db = get_db()
    profs = db.execute("SELECT * FROM professores").fetchall()
    ids = [p["id"] for p in profs if status_atualizacao(p) == "desatualizado"]
    if not ids:
        flash("Nenhum currículo desatualizado.", "ok")
        return redirect(url_for("admin_professores"))
    job_id = novo_job(ids, origem="atualizar")
    return redirect(url_for("job_page", job_id=job_id))


@app.route("/admin/importar", methods=["GET"])
@login_required
def admin_importar():
    return render_template("admin_importar.html")


@app.route("/admin/importar/elattes", methods=["POST"])
@login_required
def admin_importar_elattes():
    texto = request.form.get("ids", "")
    arq = request.files.get("csv")
    if arq and arq.filename:
        conteudo = arq.read()
        try:
            texto += "\n" + conteudo.decode("utf-8")
        except UnicodeDecodeError:
            texto += "\n" + conteudo.decode("latin-1")
    ids = extrair_ids(texto)
    if not ids:
        flash("Nenhum ID Lattes (16 dígitos) encontrado.", "erro")
        return redirect(url_for("admin_importar"))
    job_id = novo_job(ids)
    return redirect(url_for("job_page", job_id=job_id))


@app.route("/admin/importar/arquivo", methods=["POST"])
@login_required
def admin_importar_arquivo():
    arq = request.files.get("arquivo")
    if not arq or not arq.filename:
        flash("Selecione um arquivo .zip ou .xml.", "erro")
        return redirect(url_for("admin_importar"))
    dados = arq.read()
    xmls = extrair_xmls(dados) if arq.filename.lower().endswith(".zip") else {arq.filename: dados}
    db = get_db()
    ok, erros = [], []
    for pid, xml in xmls.items():
        try:
            real_id, nome = salvar_curriculo(db, pid, xml)
            ok.append(real_id)
        except Exception as e:  # noqa
            erros.append(f"{pid}: {e}")
    if ok:
        try:
            verificar_remoto(db, ok)
        except Exception:  # noqa
            pass
        flash(f"{len(ok)} currículo(s) importado(s) do arquivo.", "ok")
    for e in erros:
        flash(e, "erro")
    return redirect(url_for("admin_professores"))


@app.route("/admin/tabela", methods=["GET", "POST"])
@login_required
def admin_tabela():
    db = get_db()
    if request.method == "POST":
        acao = request.form.get("acao") or "salvar"
        destino = request.form.get("grupo") or None
        n = _salvar_edicoes_tabela(db)
        msg = f"{n} alteração(ões) salva(s)." if n else ""
        if acao.startswith("add_item:"):
            grp = acao.split(":", 1)[1]
            if grp in carregar_grupos(db):
                _adicionar_item(db, grp)
                destino = grp
                msg = (msg + " Item adicionado no fim do grupo.").strip()
        elif acao.startswith("del_item:"):
            key = acao.split(":", 1)[1]
            row = db.execute("SELECT codigo, grupo FROM itens WHERE key=?", (key,)).fetchone()
            if row:
                db.execute("DELETE FROM itens WHERE key=?", (key,))
                db.execute("UPDATE mapeamento SET item_key=NULL WHERE item_key=?", (key,))
                renumerar_grupo(db, row["grupo"])
                destino = row["grupo"]
                msg = (msg + f" Item {row['codigo']} removido.").strip()
        elif acao == "add_grupo":
            nome = (request.form.get("novo_grupo_nome") or "").strip()
            if not nome:
                flash("Informe o nome do novo grupo.", "erro")
            else:
                destino = _adicionar_grupo(db, nome)
                msg = (msg + f" Grupo {destino} criado.").strip()
        elif acao.startswith("del_grupo:"):
            cod = acao.split(":", 1)[1]
            row = db.execute("SELECT original FROM grupos WHERE codigo=?", (cod,)).fetchone()
            if row and not row["original"]:
                keys = [r["key"] for r in db.execute("SELECT key FROM itens WHERE grupo=?", (cod,))]
                for k in keys:
                    db.execute("UPDATE mapeamento SET item_key=NULL WHERE item_key=?", (k,))
                db.execute("DELETE FROM itens WHERE grupo=?", (cod,))
                db.execute("DELETE FROM grupos WHERE codigo=?", (cod,))
                padrao = [x for x in (cfg("grupos", "", db) or "").split(",") if x and x != cod]
                db.execute("UPDATE config SET valor=? WHERE chave='grupos'", (",".join(padrao),))
                destino = None
                msg = (msg + f" Grupo {cod} removido.").strip()
        if msg:
            flash(msg, "ok")
        db.commit()
        return redirect(url_for("admin_tabela", grupo=destino))
    grupos = carregar_grupos(db)
    originais = {r["codigo"] for r in db.execute("SELECT codigo FROM grupos WHERE original=1")}
    itens = carregar_itens(db)
    por_grupo = {g_: [i for i in itens if i["grupo"] == g_] for g_ in grupos}
    mapa = carregar_mapeamento(db)
    cats_por_item = {}
    for c, k in mapa.items():
        if k:
            cats_por_item.setdefault(k, []).append(CATEGORIAS_MAP[c]["label"])
    grupo_ativo = request.args.get("grupo") if request.args.get("grupo") in grupos else next(iter(grupos), "")
    return render_template("admin_tabela.html", por_grupo=por_grupo, cats_por_item=cats_por_item, GRUPOS=grupos,
                           originais=originais, CONTAGENS=CONTAGENS, grupo_ativo=grupo_ativo)


def _salvar_edicoes_tabela(db):
    """Grava nomes de grupos e campos dos itens enviados no formulário. Retorna o nº de alterações."""
    n = 0
    for cod, nome in carregar_grupos(db).items():
        novo = (request.form.get(f"grupo_nome__{cod}") or "").strip()
        if novo and novo != nome:
            db.execute("UPDATE grupos SET nome=? WHERE codigo=?", (novo, cod))
            n += 1
    # nova ordem dentro de cada grupo (reaproveita os números de ordem do próprio grupo)
    itens_todos = carregar_itens(db)
    for grp in carregar_grupos(db):
        do_grupo = [i for i in itens_todos if i["grupo"] == grp]
        try:
            pos = {i["key"]: int(request.form[f"pos__{i['key']}"]) for i in do_grupo}
        except (KeyError, ValueError):
            continue
        atual = [i["key"] for i in do_grupo]
        nova = sorted(atual, key=lambda k: pos[k])
        if nova != atual:
            slots = sorted(i["ordem"] for i in do_grupo)
            for k, o in zip(nova, slots):
                db.execute("UPDATE itens SET ordem=? WHERE key=?", (o, k))
            n += 1
    for it in itens_todos:
        k = it["key"]
        if f"valor__{k}" not in request.form:
            continue
        try:
            val = float((request.form.get(f"valor__{k}") or "0").replace(",", "."))
        except ValueError:
            val = it["valor"]
        codigo = (request.form.get(f"codigo__{k}") or "").strip() or it["codigo"] or k
        atividade = (request.form.get(f"atividade__{k}") or "").strip() or it["atividade"]
        contagem = request.form.get(f"contagem__{k}")
        contagem = contagem if contagem in CONTAGENS else (it["contagem"] or "registro")
        if (val, codigo, atividade, contagem) != (it["valor"], it["codigo"], it["atividade"], it["contagem"]):
            db.execute("UPDATE itens SET valor=?, codigo=?, atividade=?, contagem=? WHERE key=?",
                       (val, codigo, atividade, contagem, k))
            n += 1
    return n


def renumerar_grupo(db, grp):
    """Códigos seguem a ordem: G.1, G.2…; variantes consecutivas (G.N.a, G.N.b) mantêm as letras."""
    linhas = db.execute("SELECT key, codigo FROM itens WHERE grupo=? ORDER BY ordem, rowid", (grp,)).fetchall()
    blocos = []
    for r in linhas:
        v = regex_variante(r["codigo"], grp)
        base = f"v:{v}" if v else f"k:{r['key']}"  # prefixos evitam colisão entre chave interna e código
        if blocos and blocos[-1][0] == base:
            blocos[-1][1].append(r["key"])
        else:
            blocos.append((base, [r["key"]]))
    for i, (_, keys) in enumerate(blocos, 1):
        for j, k in enumerate(keys):
            cod = f"{grp}.{i}.{chr(97 + j)}" if len(keys) > 1 else f"{grp}.{i}"
            db.execute("UPDATE itens SET codigo=?, numero=? WHERE key=?", (cod, i, k))


def _adicionar_item(db, grp):
    codigos = {r["codigo"] for r in db.execute("SELECT codigo FROM itens WHERE grupo=?", (grp,))}
    n = len(codigos) + 1
    while f"{grp}.{n}" in codigos:
        n += 1
    ordem = (db.execute("SELECT MAX(ordem) m FROM itens").fetchone()["m"] or 0) + 1
    db.execute("INSERT INTO itens (key, codigo, grupo, numero, variante, atividade, contagem, valor_padrao, valor, ordem) "
               "VALUES (?,?,?,?,?,?,?,?,?,?)",
               (f"U{uuid.uuid4().hex[:10]}", f"{grp}.{n}", grp, n, "", "Nova atividade — edite o texto", "registro", 0, 0, ordem))


def _adicionar_grupo(db, nome):
    existentes = set(carregar_grupos(db))
    i = len(existentes) + 1
    while romano(i) in existentes:
        i += 1
    cod = romano(i)
    ordem = (db.execute("SELECT MAX(ordem) m FROM grupos").fetchone()["m"] or 0) + 1
    db.execute("INSERT INTO grupos (codigo, nome, ordem, original) VALUES (?,?,?,0)", (cod, nome, ordem))
    padrao = [x for x in (cfg("grupos", "", db) or "").split(",") if x]
    if cod not in padrao:
        padrao.append(cod)  # grupo novo entra na análise padrão
        db.execute("UPDATE config SET valor=? WHERE chave='grupos'", (",".join(padrao),))
    _adicionar_item(db, cod)
    return cod


@app.route("/admin/mapeamento", methods=["GET", "POST"])
@login_required
def admin_mapeamento():
    """Mapeamento Tabela → Lattes: cada item da tabela recebe os itens do Lattes que o alimentam.
    (Cada item do Lattes alimenta no máximo um item da tabela; grava-se categoria → item.)"""
    db = get_db()
    itens = carregar_itens(db)
    chaves = {i["key"] for i in itens}
    if request.method == "POST":
        destino = request.form.get("grupo") or None
        if request.form.get("acao") == "restaurar":
            for c in CATEGORIAS:
                db.execute("UPDATE mapeamento SET item_key=? WHERE categoria=?", (c[3], c[0]))
            flash("Mapeamento padrão restaurado.", "ok")
        else:
            n = 0
            atual = carregar_mapeamento(db)
            for c in CATEGORIAS:
                if f"map__{c[0]}" not in request.form:
                    continue
                v = request.form.get(f"map__{c[0]}") or None
                v = v if v in chaves else None
                if v != atual.get(c[0]):
                    db.execute("UPDATE mapeamento SET item_key=? WHERE categoria=?", (v, c[0]))
                    n += 1
            flash(f"Mapeamento salvo ({n} alteração(ões))." if n else "Nenhuma alteração no mapeamento.", "ok")
        db.commit()
        return redirect(url_for("admin_mapeamento", grupo=destino))
    grupos = carregar_grupos(db)
    mapa = carregar_mapeamento(db)
    cats = [dict(CATEGORIAS_MAP[c[0]], atual=(mapa.get(c[0]) if mapa.get(c[0]) in chaves else None)) for c in CATEGORIAS]
    por_item = {}
    for c in cats:
        if c["atual"]:
            por_item.setdefault(c["atual"], []).append(c)
    sem = [c for c in cats if not c["atual"]]
    por_grupo = {g_: [i for i in itens if i["grupo"] == g_] for g_ in grupos}
    ligacoes = {g_: sum(len(por_item.get(i["key"], [])) for i in por_grupo[g_]) for g_ in grupos}
    ativo = request.args.get("grupo")
    if ativo not in grupos and ativo != "__sem":
        ativo = next(iter(grupos), "__sem")
    return render_template("admin_mapeamento.html", cats=cats, por_item=por_item, sem=sem, por_grupo=por_grupo,
                           GRUPOS=grupos, ligacoes=ligacoes, grupo_ativo=ativo,
                           itens_js={i["key"]: {"codigo": i["codigo"], "grupo": i["grupo"]} for i in itens})


@app.route("/admin/config", methods=["GET", "POST"])
@login_required
def admin_config():
    db = get_db()

    def salvar(chave, valor):
        db.execute("INSERT INTO config (chave, valor) VALUES (?, ?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (chave, valor))

    if request.method == "POST":
        acao = request.form.get("acao")
        if acao == "analise":
            fl_novo = _monta_filtros(_mes_ano(request.form.get("interst_ini")),
                                     _mes_ano(request.form.get("interst_fim"), fim=True), [])
            salvar("interst_ini", fl_novo["ini"] or "")
            salvar("interst_fim", fl_novo["fim"] or "")
            salvar("grupos", ",".join(g for g in request.form.getlist("g") if g in G()))
            flash("Análise padrão salva.", "ok")
        elif acao == "logo":
            arq = request.files.get("logo")
            ext = (arq.filename.rsplit(".", 1)[-1].lower() if arq and "." in arq.filename else "")
            if not arq or ext not in LOGO_EXTS:
                flash("Envie a logo em PNG, SVG, JPG ou WEBP.", "erro")
            else:
                for e in LOGO_EXTS:
                    try:
                        os.remove(os.path.join(DATA_DIR, f"logo.{e}"))
                    except OSError:
                        pass
                destino = os.path.join(DATA_DIR, f"logo.{ext}")
                arq.save(destino)
                clara = preparar_logo(destino, ext)
                if request.form.get("logo_fundo") in ("auto", None, ""):
                    salvar("logo_fundo_auto", "sem" if clara else "selo")
                flash("Logo atualizada." + (" Logo clara detectada: exibida sem fundo sobre o vermelho." if clara else ""), "ok")
        elif acao == "logo_fundo":
            v = request.form.get("logo_fundo")
            salvar("logo_fundo", v if v in ("auto", "selo", "sem") else "auto")
            flash("Aparência da logo salva.", "ok")
        elif acao == "fotos":
            salvar("exibir_fotos", "1" if request.form.get("exibir_fotos") else "0")
            if request.form.get("limpar"):
                for f in os.listdir(FOTO_DIR) if os.path.isdir(FOTO_DIR) else []:
                    try:
                        os.remove(os.path.join(FOTO_DIR, f))
                    except OSError:
                        pass
                db.execute("UPDATE professores SET foto_tentativa=NULL")
            flash("Preferência de fotos salva.", "ok")
        elif acao == "remover_logo":
            for e in LOGO_EXTS:
                try:
                    os.remove(os.path.join(DATA_DIR, f"logo.{e}"))
                except OSError:
                    pass
            flash("Logo removida.", "ok")
        else:
            url = (request.form.get("elattes_url") or "https://elattes.ufpa.br").strip().rstrip("/")
            salvar("elattes_url", url)
            flash("Configuração salva.", "ok")
        db.commit()
        return redirect(url_for("admin_config"))
    return render_template("admin_config.html", elattes_url=cfg("elattes_url", "https://elattes.ufpa.br", db),
                           fl=filtros_padrao(db))


FOTO_RETENTAR_HORAS = 24
_foto_lock = threading.Lock()


@app.route("/professor/<pid>/foto")
def professor_foto(pid):
    """Miniatura da foto do Lattes (cache em disco). 404 se desativado ou indisponível."""
    if not re.fullmatch(r"\d{16}", pid) or cfg("exibir_fotos", "1") != "1":
        abort(404)
    destino = os.path.join(FOTO_DIR, f"{pid}.jpg")
    if os.path.exists(destino):
        return send_file(destino, mimetype="image/jpeg", max_age=86400)
    db = get_db()
    prof = db.execute("SELECT id, id_k, foto_tentativa FROM professores WHERE id=?", (pid,)).fetchone()
    if not prof:
        abort(404)
    # evita bater no CNPq a cada visualização quando não há foto
    if prof["foto_tentativa"]:
        try:
            ultima = dt.datetime.fromisoformat(prof["foto_tentativa"])
            if (dt.datetime.now() - ultima).total_seconds() < FOTO_RETENTAR_HORAS * 3600:
                abort(404)
        except ValueError:
            pass
    with _foto_lock:
        if os.path.exists(destino):
            return send_file(destino, mimetype="image/jpeg", max_age=86400)
        ok = False
        id_k = prof["id_k"]
        try:
            if not id_k:
                id_k = fotos.resolver_id_k(pid)
                if id_k:
                    db.execute("UPDATE professores SET id_k=? WHERE id=?", (id_k, pid))
            if id_k:
                ok = fotos.baixar_foto(id_k, destino)
        except Exception:  # noqa – rede/serviço indisponível
            ok = False
        if not ok:
            db.execute("UPDATE professores SET foto_tentativa=? WHERE id=?", (agora(), pid))
        db.commit()
    if not ok:
        abort(404)
    return send_file(destino, mimetype="image/jpeg", max_age=86400)


@app.route("/logo")
def logo():
    path, ext = logo_path()
    if not path:
        abort(404)
    return send_file(path, mimetype=LOGO_MIME[ext], max_age=300)


@app.route("/favicon.ico")
def favicon():
    path, ext = logo_path()
    if not path:
        return ("", 204)
    return send_file(path, mimetype=LOGO_MIME[ext], max_age=3600)


@app.route("/admin/exportar.csv")
@login_required
def admin_exportar():
    db = get_db()
    fl = ler_filtros()
    itens, mapa = carregar_itens(db), carregar_mapeamento(db)
    profs = db.execute("SELECT * FROM professores ORDER BY nome").fetchall()
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow([descreve_filtros(fl)])
    w.writerow(["id_lattes", "nome", "atualizacao_lattes", "importado_em", "status"]
               + [f"Grupo {g}{'' if g in fl['grupos'] else ' (fora da análise)'}" for g in G()] + ["Total bruto", "Grupo I considerado (máx. 50% do total)", "Total considerado"])
    for p in profs:
        _, pont, _ = _montar_pontuacao(p, fl, itens, mapa)
        w.writerow([p["id"], p["nome"], p["data_atualizacao_br"], fmt_dt(p["importado_em"]), status_atualizacao(p)]
                   + [f"{pont['totais_grupo'][g]:.1f}".replace(".", ",") for g in G()] + [f"{pont['total']:.1f}".replace(".", ",")]
                   + (lambda st: [f"{st['grupo_i_considerado']:.1f}".replace(".", ","), f"{st['total']:.1f}".replace(".", ",")])(situacao(pont, fl, db)))
    sufixo = f"_{fl['ini'] or 'inicio'}_a_{fl['fim'] or 'atual'}" if (fl["ini"] or fl["fim"]) else ""
    return app.response_class(out.getvalue().encode("utf-8-sig"), mimetype="text/csv",
                              headers={"Content-Disposition": f"attachment; filename=pontuacao_professores{sufixo}.csv"})


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False, threaded=True)
