"""Gera ou troca a senha. O texto puro só vai para um arquivo do root.

Não imprime a senha. Uso: python -m app.definir_senha /root/painel-gxtv-senha.txt
"""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

from app.auth import gravar_senha
from app.config import cfg_de_ambiente


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    cfg = cfg_de_ambiente()
    destino = Path(args[0] if args else "/root/painel-gxtv-senha.txt")
    if destino.exists() and cfg.auth_file.exists() and "--nova" not in args:
        return 0
    senha = REDACTED)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(senha + "\n", encoding="utf-8")
    os.chmod(destino, 0o600)
    gravar_senha(cfg.auth_file, "gustavo", senha)
    del senha
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
