"""Login próprio do v2.

A senha do gustavo é a mesma do painel atual, mas o v2 não consulta o bcrypt
do v1 a cada request. No deploy (ou na subida) o hash é copiado uma vez para
/var/lib/painel-gxtv-v2/auth.json. O arquivo do v1 não é alterado.

Prioridade na verificação:
1) PAINEL_PASSWORD_SHA256 ou PAINEL_PASSWORD / PAINEL_V2_PASSWORD
2) Hash bcrypt do arquivo próprio do v2
3) PAINEL_V2_DEV_AUTH=1 e senha "dev" — só se não houver senha própria
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from pathlib import Path
from typing import Any

from fastapi import Cookie, Depends, HTTPException, Request, Response

SESSION_COOKIE = "mn_v2_session"
SESSION_TTL_S = 60 * 60 * 14  # 14h


def _secret() -> bytes:
    raw = os.environ.get("PAINEL_V2_SECRET") or os.environ.get("PAINEL_SECRET") or "dev-only-change-me"
    return raw.encode("utf-8")


def _credenciais() -> dict[str, str]:
    """Mapa usuário→senha. Mesmo login do painel atual (gustavo)."""
    user = os.environ.get("PAINEL_USER", "gustavo")
    pwd = os.environ.get("PAINEL_PASSWORD") or os.environ.get("PAINEL_V2_PASSWORD") or ""
    # Hash opcional: PAINEL_PASSWORD_SHA256
    return {"user": user, "password": pwd, "password_sha256": os.environ.get("PAINEL_PASSWORD_SHA256", "")}


def _bcrypt_ok(password: str, hashed: str) -> bool:
    """Mesmo hash do painel v1 (/var/lib/painel-gxtv/auth.json)."""
    try:
        import bcrypt  # type: ignore
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def v2_auth_path() -> Path:
    return Path(os.environ.get("PAINEL_V2_AUTH_FILE") or "/var/lib/painel-gxtv-v2/auth.json")


def v1_auth_path() -> Path:
    """Origem da cópia única. Não é lido no login."""
    return Path(
        os.environ.get("PAINEL_V1_AUTH_FILE")
        or "/var/lib/painel-gxtv/auth.json"
    )


def _ler_auth(path: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def importar_credencial_v1() -> bool:
    """Copia usuario+hash do v1 para o arquivo do v2, se o v2 ainda não tiver senha.

    Não escreve no auth.json do v1.
    """
    dest = v2_auth_path()
    atual = _ler_auth(dest) if dest.is_file() else None
    if atual and str(atual.get("hash") or "").startswith("$2"):
        return True
    src = _ler_auth(v1_auth_path())
    if not src:
        return False
    usuario = str(src.get("usuario") or src.get("user") or "gustavo")
    hashed = str(src.get("hash") or src.get("password_hash") or "")
    if not hashed.startswith("$2"):
        return False
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        payload = {"usuario": usuario, "hash": hashed, "origem": "importado_do_v1"}
        tmp = dest.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(dest)
    except OSError:
        return False
    return True


def _doc_v2() -> dict[str, Any] | None:
    path = v2_auth_path()
    if not path.is_file():
        return None
    return _ler_auth(path)


def diagnosticar_login(username: str, password: str) -> str | None:
    """None quando a senha confere. Texto curto quando não."""
    cred = _credenciais()
    nome = username.strip()
    doc = _doc_v2()
    usuario_arquivo = str((doc or {}).get("usuario") or cred["user"])
    if nome.casefold() != cred["user"].casefold() and nome.casefold() != usuario_arquivo.casefold():
        return "Usuário ou senha incorretos"

    if cred["password_sha256"]:
        dig = hashlib.sha256(password.encode("utf-8")).hexdigest()
        if hmac.compare_digest(dig, cred["password_sha256"]):
            return None
        return "Usuário ou senha incorretos"
    if cred["password"]:
        if hmac.compare_digest(password, cred["password"]):
            return None
        return "Usuário ou senha incorretos"

    hashed = str((doc or {}).get("hash") or "")
    if hashed.startswith("$2"):
        if _bcrypt_ok(password, hashed):
            return None
        return "Usuário ou senha incorretos"

    if os.environ.get("PAINEL_V2_DEV_AUTH") == "1" and password == "dev":
        return None
    return (
        "Login do v2 ainda sem senha própria. O deploy copia o hash do painel atual "
        "para /var/lib/painel-gxtv-v2/auth.json — esse arquivo não está aqui."
    )


def verificar_login(username: str, password: str) -> bool:
    return diagnosticar_login(username, password) is None


def _sign(payload: bytes) -> str:
    sig = hmac.new(_secret(), payload, hashlib.sha256).digest()
    return urlsafe_b64encode(payload).decode().rstrip("=") + "." + urlsafe_b64encode(sig).decode().rstrip("=")


def _unsign(token: str) -> dict[str, Any] | None:
    try:
        body_b64, sig_b64 = token.split(".", 1)
        pad = lambda s: s + "=" * (-len(s) % 4)
        body = urlsafe_b64decode(pad(body_b64))
        sig = urlsafe_b64decode(pad(sig_b64))
        expect = hmac.new(_secret(), body, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expect):
            return None
        data = json.loads(body.decode("utf-8"))
        if int(data.get("exp", 0)) < int(time.time()):
            return None
        return data
    except Exception:
        return None


def emitir_sessao(username: str) -> str:
    payload = {
        "u": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + SESSION_TTL_S,
        "v": 2,
    }
    return _sign(json.dumps(payload, separators=(",", ":")).encode("utf-8"))


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=os.environ.get("PAINEL_V2_SECURE_COOKIE", "0") == "1",
        max_age=SESSION_TTL_S,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


async def usuario_atual(
    request: Request,
    gxtv_v2_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    if gxtv_v2_session:
        data = _unsign(gxtv_v2_session)
        if data:
            return {"username": data["u"], "via": "v2"}

    # Compat: cookie do painel v1 (se o coordenador mapear o mesmo secret/validação)
    v1_name = os.environ.get("PAINEL_V1_SESSION_COOKIE", "session")
    v1 = request.cookies.get(v1_name)
    if v1 and os.environ.get("PAINEL_V1_TRUST_SESSION") == "1":
        # Modo trust: painel v1 já autenticou (nginx auth_request ou shared secret).
        return {"username": os.environ.get("PAINEL_USER", "gustavo"), "via": "v1"}

    raise HTTPException(status_code=401, detail="Faça login para continuar")


RequireUser = Depends(usuario_atual)
