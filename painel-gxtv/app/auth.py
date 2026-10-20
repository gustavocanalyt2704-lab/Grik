"""Login com bcrypt e cookie de sessão. Bloqueio só depois de 50 erros em 1 minuto, e dura 1 minuto.

As sessões ficam gravadas (só o resumo sha256 do cookie) para sobreviver a um reinício do painel."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from pathlib import Path

import bcrypt

COOKIE = "painel_sessao"
MAX_TENTATIVAS = 50
BLOQUEIO_S = 60
SESSAO_S = 12 * 60 * 60


class Auth:
    def __init__(self, auth_file: Path):
        self.auth_file = auth_file
        self._falhas: dict[str, list[float]] = {}
        self._bloqueado_ate: dict[str, float] = {}
        self.sessoes: dict[str, float] = {}
        self.usuario, self._hash = self._ler()
        self.arquivo_sessoes = auth_file.parent / "sessoes.json" if str(auth_file) != "/dev/null" else None
        self._gravado = 0.0
        self._carregar_sessoes()

    @staticmethod
    def _chave(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def _carregar_sessoes(self):
        if not self.arquivo_sessoes:
            return
        try:
            dado = json.loads(self.arquivo_sessoes.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        agora = time.time()
        self.sessoes = {k: float(v) for k, v in dado.items() if isinstance(v, (int, float)) and v > agora}

    def _gravar_sessoes(self, ja: bool = False):
        if not self.arquivo_sessoes:
            return
        agora = time.time()
        if not ja and agora - self._gravado < 60:
            return
        self._gravado = agora
        self.sessoes = {k: v for k, v in self.sessoes.items() if v > agora}
        try:
            tmp = self.arquivo_sessoes.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.sessoes), encoding="utf-8")
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.arquivo_sessoes)
        except OSError:
            pass

    def _ler(self) -> tuple[str, bytes]:
        dado = json.loads(self.auth_file.read_text(encoding="utf-8"))
        return str(dado["usuario"]), str(dado["hash"]).encode()

    def entrar(self, usuario: str, senha: str, ip: str) -> tuple[bool, str, str | None]:
        chave = f"{ip}|{(usuario or '').casefold()}"
        agora = time.time()
        if self._bloqueado_ate.get(chave, 0) > agora:
            return False, "Muitas tentativas seguidas. Tente de novo em alguns minutos.", None
        # PAINEL_DEMO=1 só existe na pré-visualização. Na VPS essa variável fica desligada.
        if os.environ.get("PAINEL_DEMO") == "1" and (usuario or "").casefold() == "gustavo" and (senha or "") == "demo":
            token = secrets.token_urlsafe(32)
            self.sessoes[self._chave(token)] = agora + SESSAO_S
            self._gravar_sessoes(ja=True)
            return True, "", token
        ok_usuario = secrets.compare_digest((usuario or "").casefold(), self.usuario.casefold())
        ok_senha = bcrypt.checkpw((senha or "").encode(), self._hash)
        if not (ok_usuario and ok_senha):
            janela = [t for t in self._falhas.get(chave, []) if agora - t < BLOQUEIO_S]
            janela.append(agora)
            self._falhas[chave] = janela
            if len(janela) >= MAX_TENTATIVAS:
                self._bloqueado_ate[chave] = agora + BLOQUEIO_S
                return False, "Muitas tentativas seguidas. Tente de novo em alguns minutos.", None
            return False, "Usuário ou senha incorretos.", None
        self._falhas.pop(chave, None)
        self._bloqueado_ate.pop(chave, None)
        token = secrets.token_urlsafe(32)
        self.sessoes[self._chave(token)] = agora + SESSAO_S
        self._gravar_sessoes(ja=True)
        return True, "", token

    def valida(self, token: str | None) -> bool:
        if not token:
            return False
        chave = self._chave(token)
        expira = self.sessoes.get(chave)
        if not expira:
            return False
        if expira < time.time():
            self.sessoes.pop(chave, None)
            return False
        self.sessoes[chave] = time.time() + SESSAO_S
        self._gravar_sessoes()
        return True

    def sair(self, token: str | None):
        if token:
            self.sessoes.pop(self._chave(token), None)
            self._gravar_sessoes(ja=True)


def gravar_senha(auth_file: Path, usuario: str, senha: str, rounds: int = 12):
    auth_file.parent.mkdir(parents=True, exist_ok=True)
    digest = bcrypt.hashpw(senha.encode(), bcrypt.gensalt(rounds=rounds)).decode()
    auth_file.write_text(json.dumps({"usuario": usuario, "hash": digest}), encoding="utf-8")
    try:
        auth_file.chmod(0o600)
    except OSError:
        pass
