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
import uuid

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template, request,
                   send_file, session, url_for)

import fotos
from genero import inferir_genero
from elattes_client import ELattesClient, ELattesError, extrair_xmls
from lattes_parser import PARSER_VERSAO, parse_lattes_xml
from scoring import CATEGORIAS, CATEGORIAS_MAP, CONTAGENS, GRUPOS, calcular_pontuacao, tabela_itens

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
    CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor TEXT);
    """)
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
                         ("grupos", ",".join(GRUPOS))):
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
app.jinja_env.globals["GRUPOS"] = GRUPOS
app.jinja_env.globals["status_atualizacao"] = status_atualizacao
app.jinja_env.globals["APP_NOME"] = APP_NOME
app.jinja_env.globals["APP_SUB"] = APP_SUB


def genero_de(prof):
    """Persona do avatar: escolha manual do admin ou palpite pelo primeiro nome."""
    try:
        manual = prof["genero_manual"]
    except (KeyError, IndexError):
        manual = None
    return manual if manual in ("M", "F", "N") else inferir_genero(prof["nome"])


app.jinja_env.globals["genero_de"] = genero_de
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


@app.context_processor
def _ctx():
    return {"tem_logo": logo_path()[0] is not None, "ANO_ATUAL": dt.date.today().year,
            "fotos_on": cfg("exibir_fotos", "1") == "1"}


# ---------------------------------------------------------------------------
# Filtros da análise (interstício + grupos)
# ---------------------------------------------------------------------------
def _ano(v):
    try:
        a = int(str(v).strip())
        return a if 1900 <= a <= 2100 else None
    except (TypeError, ValueError):
        return None


def filtros_padrao(con=None):
    gs = [g for g in (cfg("grupos", ",".join(GRUPOS), con) or "").split(",") if g in GRUPOS]
    return {"ini": _ano(cfg("interst_ini", "", con)), "fim": _ano(cfg("interst_fim", "", con)), "grupos": gs}


def ler_filtros():
    """Lê ?ini=&fim=&g=...&f=1 da URL; sem f=1 usa os padrões definidos na Configuração."""
    if request.args.get("f") != "1":
        return filtros_padrao()
    ini, fim = _ano(request.args.get("ini")), _ano(request.args.get("fim"))
    if ini and fim and ini > fim:
        ini, fim = fim, ini
    grupos = [g for g in request.args.getlist("g") if g in GRUPOS]
    return {"ini": ini, "fim": fim, "grupos": grupos}


def filtros_query(fl):
    q = {"f": "1", "ini": fl["ini"] or "", "fim": fl["fim"] or ""}
    parts = [f"{k}={v}" for k, v in q.items()] + [f"g={g}" for g in fl["grupos"]]
    return "&".join(parts)


def descreve_filtros(fl):
    if fl["ini"] and fl["fim"]:
        periodo = f"{fl['ini']}–{fl['fim']}"
    elif fl["ini"]:
        periodo = f"a partir de {fl['ini']}"
    elif fl["fim"]:
        periodo = f"até {fl['fim']}"
    else:
        periodo = "todo o currículo"
    if len(fl["grupos"]) == len(GRUPOS):
        gtxt = "todos os grupos"
    elif not fl["grupos"]:
        gtxt = "nenhum grupo"
    else:
        gtxt = "grupos " + ", ".join(fl["grupos"])
    return f"Interstício: {periodo} · {gtxt}"


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
            job["etapa"] = f"Baixando lote {i // LOTE + 1} de {(len(ids) + LOTE - 1) // LOTE} no eLattes"

            def on_progress(p, base=i):
                job["baixados"] = base + int(p.get("current") or 0)
                job["mensagem"] = f"eLattes: {p.get('status', '')} – {p.get('message') or ''} ({p.get('current', 0)}/{p.get('total', len(lote))})"

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
                    job["erros"].append({"id": pid, "erro": "XML não veio no zip do eLattes (ID inexistente ou falha no download)"})
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
    fl = filtros or {"ini": None, "fim": None, "grupos": list(GRUPOS)}
    pont = calcular_pontuacao(parsed["categorias"], itens_por_key, mapeamento,
                              ano_ini=fl["ini"], ano_fim=fl["fim"], grupos=fl["grupos"])
    return parsed, pont, itens


@app.route("/professor/<pid>")
def professor(pid):
    db = get_db()
    prof = db.execute("SELECT * FROM professores WHERE id=?", (pid,)).fetchone()
    if not prof:
        abort(404)
    fl = ler_filtros()
    parsed, pont, _ = _montar_pontuacao(prof, fl)
    pontos_cat = {l["categoria"]: l for l in pont["linhas"]}
    por_grupo = {g: [l for l in pont["linhas"] if l["grupo"] == g] for g in GRUPOS}
    grupo_ativo = request.args.get("grupo")
    if grupo_ativo not in GRUPOS:
        # primeiro grupo considerado que tenha pontos; senão o primeiro considerado; senão I
        grupo_ativo = next((g for g in fl["grupos"] if pont["totais_grupo"][g] > 0),
                           fl["grupos"][0] if fl["grupos"] else "I")
    return render_template("professor.html", prof=prof, cv=parsed, pont=pont, por_grupo=por_grupo, fl=fl,
                           fl_query=filtros_query(fl), pontos_cat=pontos_cat, status=status_atualizacao(prof),
                           aba=request.args.get("aba", "curriculo"), grupo_ativo=grupo_ativo)


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
        profs.append({**dict(p), "total": pont["total"], "totais_grupo": pont["totais_grupo"]})
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
        flash(f"Data de atualização verificada no eLattes para {len(ids)} professor(es).", "ok")
    except Exception as e:  # noqa
        flash(f"Falha ao consultar o eLattes: {e}", "erro")
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
        if request.form.get("acao") == "restaurar":
            for it in tabela_itens():
                db.execute("UPDATE itens SET codigo=?, atividade=?, contagem=?, valor=? WHERE key=?",
                           (it["codigo"], it["atividade"], it["contagem_padrao"], it["valor_padrao"], it["key"]))
            flash("Tabela restaurada para o Anexo I original (item, atividade, contagem e valor).", "ok")
        else:
            n = 0
            for it in carregar_itens(db):
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
            flash(f"{n} item(ns) alterado(s)." if n else "Nenhuma alteração.", "ok")
        db.commit()
        return redirect(url_for("admin_tabela", grupo=request.form.get("grupo") or None))
    itens = carregar_itens(db)
    por_grupo = {g: [i for i in itens if i["grupo"] == g] for g in GRUPOS}
    # categorias mapeadas para cada item (para mostrar o que o Lattes alimenta)
    mapa = carregar_mapeamento(db)
    cats_por_item = {}
    for c, k in mapa.items():
        if k:
            cats_por_item.setdefault(k, []).append(CATEGORIAS_MAP[c]["label"])
    grupo_ativo = request.args.get("grupo") if request.args.get("grupo") in GRUPOS else "I"
    return render_template("admin_tabela.html", por_grupo=por_grupo, cats_por_item=cats_por_item,
                           CONTAGENS=CONTAGENS, grupo_ativo=grupo_ativo)


@app.route("/admin/mapeamento", methods=["GET", "POST"])
@login_required
def admin_mapeamento():
    db = get_db()
    if request.method == "POST":
        if request.form.get("acao") == "restaurar":
            for c in CATEGORIAS:
                db.execute("UPDATE mapeamento SET item_key=? WHERE categoria=?", (c[3], c[0]))
            flash("Mapeamento padrão restaurado.", "ok")
        else:
            for c in CATEGORIAS:
                v = request.form.get(f"map__{c[0]}") or None
                db.execute("UPDATE mapeamento SET item_key=? WHERE categoria=?", (v, c[0]))
            flash("Mapeamento salvo.", "ok")
        db.commit()
        return redirect(url_for("admin_mapeamento"))
    itens = carregar_itens(db)
    mapa = carregar_mapeamento(db)
    cats = [dict(CATEGORIAS_MAP[c[0]], atual=mapa.get(c[0])) for c in CATEGORIAS]
    return render_template("admin_mapeamento.html", cats=cats, itens=itens)


@app.route("/admin/config", methods=["GET", "POST"])
@login_required
def admin_config():
    db = get_db()

    def salvar(chave, valor):
        db.execute("INSERT INTO config (chave, valor) VALUES (?, ?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (chave, valor))

    if request.method == "POST":
        acao = request.form.get("acao")
        if acao == "analise":
            ini, fim = _ano(request.form.get("interst_ini")), _ano(request.form.get("interst_fim"))
            if ini and fim and ini > fim:
                ini, fim = fim, ini
            salvar("interst_ini", str(ini or ""))
            salvar("interst_fim", str(fim or ""))
            salvar("grupos", ",".join(g for g in request.form.getlist("g") if g in GRUPOS))
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
                arq.save(os.path.join(DATA_DIR, f"logo.{ext}"))
                flash("Logo atualizada.", "ok")
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
               + [f"Grupo {g}{'' if g in fl['grupos'] else ' (fora da análise)'}" for g in GRUPOS] + ["Total considerado"])
    for p in profs:
        _, pont, _ = _montar_pontuacao(p, fl, itens, mapa)
        w.writerow([p["id"], p["nome"], p["data_atualizacao_br"], fmt_dt(p["importado_em"]), status_atualizacao(p)]
                   + [f"{pont['totais_grupo'][g]:.1f}".replace(".", ",") for g in GRUPOS] + [f"{pont['total']:.1f}".replace(".", ",")])
    sufixo = f"_{fl['ini'] or 'inicio'}-{fl['fim'] or 'atual'}" if (fl["ini"] or fl["fim"]) else ""
    return app.response_class(out.getvalue().encode("utf-8-sig"), mimetype="text/csv",
                              headers={"Content-Disposition": f"attachment; filename=pontuacao_professores{sufixo}.csv"})


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False, threaded=True)
