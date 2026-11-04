# -*- coding: utf-8 -*-
"""
Foto do professor a partir do serviço oficial do CNPq.

O serviço de fotos usa o identificador interno do CNPq (formato K0000000A0), não o ID Lattes
de 16 dígitos. Esse identificador é obtido lendo apenas o redirecionamento de
http://lattes.cnpq.br/<ID16> (o currículo em si não é aberto). A foto é baixada uma vez,
reduzida e guardada em DATA_DIR/fotos/<ID16>.jpg.
"""
import io
import os
import re
from urllib.parse import urljoin

import requests

LATTES_BASE = os.environ.get("LATTES_BASE", "http://lattes.cnpq.br")
FOTO_URL = os.environ.get("FOTO_URL", "https://servicosweb.cnpq.br/wspessoa/servletrecuperafoto?tipo=1&id={id_k}")
RE_ID_K = re.compile(r"\b(K\d{7}[A-Z0-9]\d)\b")
TAMANHO = 320  # lado máximo da miniatura, em px

_session = requests.Session()
_session.headers.update({"User-Agent": "Progressao-Automatizada-UFPA/1.0"})


def resolver_id_k(id16, timeout=15):
    """Lê o(s) redirecionamento(s) de lattes.cnpq.br/<id16> e extrai o identificador K."""
    url = f"{LATTES_BASE.rstrip('/')}/{id16}"
    for _ in range(5):
        r = _session.get(url, allow_redirects=False, timeout=timeout)
        loc = r.headers.get("Location", "")
        m = RE_ID_K.search(loc)
        if m:
            return m.group(1)
        if r.is_redirect and loc:
            url = urljoin(url, loc)
            continue
        m = RE_ID_K.search(r.text[:20000]) if r.status_code == 200 else None
        return m.group(1) if m else None
    return None


def baixar_foto(id_k, destino, timeout=20):
    """Baixa a foto, valida, reduz e salva como JPEG. Retorna True se salvou."""
    from PIL import Image, ImageOps

    r = _session.get(FOTO_URL.format(id_k=id_k), timeout=timeout)
    if r.status_code != 200 or len(r.content) < 200:
        return False
    try:
        im = Image.open(io.BytesIO(r.content))
        im = ImageOps.exif_transpose(im).convert("RGB")
    except Exception:  # noqa – não é uma imagem (professor sem foto, erro do serviço)
        return False
    if min(im.size) < 16:
        return False
    # recorte quadrado centralizado, um pouco acima do centro (rosto)
    w, h = im.size
    lado = min(w, h)
    left = (w - lado) // 2
    top = max(0, min(h - lado, int((h - lado) * 0.35)))
    im = im.crop((left, top, left + lado, top + lado)).resize((TAMANHO, TAMANHO), Image.LANCZOS)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    tmp = destino + ".tmp"
    im.save(tmp, "JPEG", quality=85, optimize=True)
    os.replace(tmp, destino)
    return True
