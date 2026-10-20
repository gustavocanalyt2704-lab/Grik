"""Credencial do Gestor lida do que já existe. Não grava segredo e não inventa token."""

from __future__ import annotations

import os
from pathlib import Path

CHAVES = ("GESTOR_BEARER", "GESTOR_TOKEN", "GESTOR_EMAIL", "GESTOR_PASSWORD", "GESTOR_SENHA")

# Só leitura. O arquivo do v1 entra na lista porque a credencial pode já estar lá;
# este módulo não escreve em nenhum deles.
_ARQUIVOS = (
    "/etc/painel-gxtv-v2.env",
    "/etc/painel-gxtv.env",
    "/etc/mnrobo-box.env",
    "/opt/mnrobo/.env",
    "/opt/mnrobo/atendimento/.env",
    "/opt/painel-gxtv/.env",
    "/opt/painel-gxtv/gestor.env",
)

AVISO_SEM_CREDENCIAL = (
    "Gestor sem credencial. Procurei GESTOR_BEARER (ou GESTOR_EMAIL + GESTOR_PASSWORD) "
    "no ambiente e nos arquivos de config que o painel já usa. Sem isso as vendas ficam "
    "como sem dado — o restante da tela continua."
)


def _ler_arquivo(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, raw = line.partition("=")
        key = key.strip()
        if key not in CHAVES:
            continue
        val = raw.strip().strip('"').strip("'")
        if val:
            out[key] = val
    return out


def _mapa() -> dict[str, str]:
    found: dict[str, str] = {}
    extra = (os.environ.get("GESTOR_ENV_FILE") or "").strip()
    paths = ([extra] if extra else []) + list(_ARQUIVOS)
    for raw in paths:
        if not raw:
            continue
        found.update(_ler_arquivo(Path(raw)))
    for key in CHAVES:
        env = (os.environ.get(key) or "").strip()
        if env:
            found[key] = env
    if not found.get("GESTOR_BEARER") and found.get("GESTOR_TOKEN"):
        found["GESTOR_BEARER"] = found["GESTOR_TOKEN"]
    if not found.get("GESTOR_PASSWORD") and found.get("GESTOR_SENHA"):
        found["GESTOR_PASSWORD"] = found["GESTOR_SENHA"]
    return found


def bearer() -> str:
    return _mapa().get("GESTOR_BEARER", "")


def email() -> str:
    return _mapa().get("GESTOR_EMAIL", "")


def password() -> str:
    return _mapa().get("GESTOR_PASSWORD", "")


def tem() -> bool:
    m = _mapa()
    if m.get("GESTOR_BEARER"):
        return True
    return bool(m.get("GESTOR_EMAIL") and m.get("GESTOR_PASSWORD"))


def aviso() -> str | None:
    if tem():
        return None
    return AVISO_SEM_CREDENCIAL
