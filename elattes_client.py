# -*- coding: utf-8 -*-
"""
Cliente do eLattes UFPA (https://elattes.ufpa.br/).

Fluxo observado no site:
  POST /download_cvs      {"ids_lattes": [...]}  -> {"job_id", "status_url", "download_file"}
  GET  /progress/<job>    -> {"status": "pending|running|done|error", "current", "total", "downloaded": [...], ...}
  GET  /download_file/<job> -> curriculos_baixados.zip  (contém <id>.zip -> <id>.xml, ISO-8859-1)
  POST /get_last_update   {"ids_lattes": [...]}  -> {"<id>": "DD/MM/AAAA HH:MM:SS"}
"""
import io
import time
import zipfile

import requests

BASE_URL = "https://elattes.ufpa.br"


class ELattesError(Exception):
    pass


class ELattesClient:
    def __init__(self, base_url=BASE_URL, timeout=60, poll_interval=1.5, max_wait=900):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_wait = max_wait
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Lattes-UFPA-Pontuacao/1.0", "Accept": "application/json, */*"})

    # ------------------------------------------------------------------
    def ultima_atualizacao(self, ids):
        """Retorna {id: 'DD/MM/AAAA HH:MM:SS'} para os IDs informados."""
        ids = [str(i).strip() for i in ids if str(i).strip()]
        if not ids:
            return {}
        r = self.session.post(f"{self.base_url}/get_last_update", json={"ids_lattes": ids}, timeout=self.timeout)
        if r.status_code != 200:
            raise ELattesError(f"get_last_update HTTP {r.status_code}: {r.text[:300]}")
        return r.json()

    def iniciar_download(self, ids):
        ids = [str(i).strip() for i in ids if str(i).strip()]
        r = self.session.post(f"{self.base_url}/download_cvs", json={"ids_lattes": ids}, timeout=self.timeout)
        try:
            data = r.json()
        except ValueError:
            raise ELattesError(f"download_cvs resposta inválida HTTP {r.status_code}: {r.text[:300]}")
        if r.status_code != 200 or "job_id" not in data:
            raise ELattesError(f"download_cvs HTTP {r.status_code}: {data}")
        return data["job_id"]

    def progresso(self, job_id):
        r = self.session.get(f"{self.base_url}/progress/{job_id}", timeout=self.timeout)
        if r.status_code != 200:
            raise ELattesError(f"progress HTTP {r.status_code}: {r.text[:300]}")
        return r.json()

    def baixar_zip(self, job_id):
        r = self.session.get(f"{self.base_url}/download_file/{job_id}", timeout=self.timeout * 5)
        if r.status_code != 200:
            raise ELattesError(f"download_file HTTP {r.status_code}: {r.text[:300]}")
        return r.content

    # ------------------------------------------------------------------
    def baixar_curriculos(self, ids, on_progress=None):
        """
        Executa o fluxo completo e devolve {id: xml_bytes}.
        on_progress(dict) é chamado a cada consulta de progresso.
        """
        job_id = self.iniciar_download(ids)
        inicio = time.time()
        while True:
            p = self.progresso(job_id)
            if on_progress:
                on_progress(p)
            if p.get("status") == "done":
                break
            if p.get("status") == "error":
                raise ELattesError(p.get("traceback") or p.get("message") or "Erro no eLattes")
            if time.time() - inicio > self.max_wait:
                raise ELattesError("Tempo máximo de espera do eLattes excedido")
            time.sleep(self.poll_interval)
        zip_bytes = self.baixar_zip(job_id)
        return extrair_xmls(zip_bytes)


def extrair_xmls(zip_bytes):
    """
    Extrai todos os XMLs de um zip (inclusive zips aninhados, como o do eLattes).
    Retorna {id_lattes_ou_nome: xml_bytes}.
    """
    out = {}

    def _walk(data, nome_origem):
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            if nome_origem.lower().endswith(".xml") or data.lstrip()[:5] == b"<?xml":
                out[_id_from_name(nome_origem, data)] = data
            return
        for info in zf.infolist():
            if info.is_dir():
                continue
            conteudo = zf.read(info)
            nome = info.filename.rsplit("/", 1)[-1]
            if nome.lower().endswith(".zip"):
                _walk(conteudo, nome)
            elif nome.lower().endswith(".xml"):
                out[_id_from_name(nome, conteudo)] = conteudo

    _walk(zip_bytes, "arquivo.zip")
    return out


def _id_from_name(nome, data):
    base = nome.rsplit(".", 1)[0]
    if base.isdigit() and len(base) == 16:
        return base
    # tenta extrair do próprio XML
    head = data[:2000].decode("latin-1", "ignore")
    import re
    m = re.search(r'NUMERO-IDENTIFICADOR="(\d{16})"', head)
    return m.group(1) if m else base
