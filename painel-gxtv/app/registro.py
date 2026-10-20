"""Registro das ações feitas no painel. Sem senha e sem chave de acesso."""

from __future__ import annotations

import json
from pathlib import Path

from app.tempo import agora


def gravar(caminho: Path, usuario: str, acao: str, alvo: str, painel: str, frase: str, ok: bool) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    linha = {
        "ts": agora().isoformat(),
        "usuario": usuario or "",
        "acao": acao,
        "alvo": alvo,
        "painel": painel,
        "resultado": frase,
        "ok": bool(ok),
    }
    with caminho.open("a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(linha, ensure_ascii=False) + "\n")
