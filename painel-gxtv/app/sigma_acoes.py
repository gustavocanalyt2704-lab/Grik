"""Cria teste, renova e libera telas no Sigma. A chave fica no ambiente, nunca aqui."""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from urllib.parse import quote

from app import rede
from app.ler import ler_env

_ARQUIVOS_ENV = (
    Path("/etc/mnrobo.env"),
    Path("/etc/mnrobo-box.env"),
    Path("/etc/mnrobo-mp.env"),
)


def opcoes(cfg) -> dict:
    planos = _json(cfg.planos)
    paineis = []
    for chave, spec in _json(cfg.paineis).items():
        pronto, _ = resolver(cfg, chave)
        paineis.append({
            "id": chave,
            "nome": spec.get("nome") or chave,
            "telas": spec.get("telas_pagas") or 4,
            "pronto": pronto is not None,
        })
    return {
        "apps": list((planos.get("testes") or {}).keys()),
        "dias": [30, 60, 90],
        "paineis": paineis,
    }


def resolver(cfg, nome: str):
    paineis = _json(cfg.paineis)
    spec = paineis.get(nome or "")
    if not isinstance(spec, dict):
        return None, "Escolha o painel."
    token = _token(cfg, spec.get("token_env") or "")
    if not token:
        return None, f"{spec.get('nome') or 'Esse painel'} ainda não está configurado nesta máquina. Nada foi alterado."
    base = (os.environ.get(spec.get("base_env") or "") or "").strip() or (spec.get("base_padrao") or "").strip()
    if not base:
        principal = paineis.get("principal") or {}
        base = (os.environ.get("SIGMA_BASE") or principal.get("base_padrao") or "").strip()
    if not base:
        return None, "O endereço desse painel não está configurado. Nada foi alterado."
    user = (os.environ.get(spec.get("user_env") or "") or spec.get("user_padrao") or "").strip()
    server = (os.environ.get(spec.get("server_env") or "") or spec.get("server_padrao") or user).strip()
    return {
        "id": nome,
        "nome": spec.get("nome") or nome,
        "token": token,
        "base": base.rstrip("/"),
        "user": user,
        "server": server,
        "telas": int(spec.get("telas_pagas") or 4),
    }, None


def achar(painel: dict, usuario: str):
    url = f"{painel['base']}/customers?username={quote(usuario)}&per_page=20"
    status, corpo, erro = rede.pedir("GET", url, None, painel["token"])
    if erro or status >= 400:
        return None, _frase_http(status, erro)
    alvo = usuario.casefold()
    for item in _lista(corpo):
        nome = str(item.get("username") or item.get("sigma_username") or "").strip()
        if nome.casefold() == alvo:
            return item, None
    return None, f"Não achei o usuário {usuario} nesse painel. Nada foi alterado."


def renovar(cfg, painel_nome: str, usuario: str, dias: int) -> tuple[bool, str]:
    painel, erro = resolver(cfg, painel_nome)
    if erro:
        return False, erro
    if str(dias) not in {"30", "60", "90"}:
        return False, "Escolha 30, 60 ou 90 dias. Nada foi alterado."
    cliente, erro = achar(painel, usuario)
    if erro:
        return False, erro
    ident = str(cliente.get("id") or "").strip()
    if not ident:
        return False, "Achei o usuário, mas o Sigma não devolveu o código dele. Nada foi alterado."
    pacote = _pacote_pago(cfg, dias, str(cliente.get("package") or cliente.get("pacote") or ""))
    if not pacote:
        return False, "Não achei o plano desses dias. Nada foi alterado."
    status, _corpo, erro = rede.pedir(
        "POST", f"{painel['base']}/customers/{quote(ident)}/renew", {"packageId": pacote}, painel["token"]
    )
    if erro or status >= 400:
        return False, _frase_http(status, erro)
    return True, f"Renovei {usuario} por {dias} dias."


def liberar_telas(cfg, painel_nome: str, usuario: str) -> tuple[bool, str]:
    painel, erro = resolver(cfg, painel_nome)
    if erro:
        return False, erro
    cliente, erro = achar(painel, usuario)
    if erro:
        return False, erro
    ident = str(cliente.get("id") or "").strip()
    if not ident:
        return False, "Achei o usuário, mas o Sigma não devolveu o código dele. Nada foi alterado."
    meta = int(painel["telas"])
    atual = _telas(cliente)
    if atual is not None and atual >= meta:
        return True, f"{usuario} já tem {atual} telas."
    status, _corpo, erro = rede.pedir(
        "PUT", f"{painel['base']}/customers/{quote(ident)}", {"connections": meta}, painel["token"]
    )
    if erro or status >= 400:
        return False, _frase_http(status, erro)
    status, corpo, erro = rede.pedir("GET", f"{painel['base']}/customers/{quote(ident)}", None, painel["token"])
    if erro or status >= 400:
        return False, "Pedi as telas, mas não consegui conferir se o Sigma aceitou."
    ficou = _telas(_primeiro(corpo) or {})
    if ficou is None:
        return False, "Pedi as telas, mas o Sigma não confirmou o número."
    if ficou < meta:
        return False, f"Pedi {meta} telas para {usuario}, mas o cadastro continua com {ficou}."
    return True, f"{usuario} agora tem {ficou} telas."


def criar_teste(cfg, painel_nome: str, app: str, whatsapp: str) -> tuple[bool, str, str]:
    """Devolve ok, frase da tela (pode ter a senha) e frase do registro (sem senha)."""
    painel, erro = resolver(cfg, painel_nome)
    if erro:
        return False, erro, erro
    planos = (_json(cfg.planos).get("testes") or {})
    spec = planos.get(app)
    if not isinstance(spec, dict) or not spec.get("id"):
        return False, "Escolha o aplicativo do teste. Nada foi criado.", "Escolha o aplicativo do teste."
    if not painel["user"] or not painel["server"]:
        return False, "Esse painel ainda não tem o servidor configurado. Nada foi criado.", "Painel sem servidor."
    usuario = "gx" + secrets.token_hex(3)
    senha = f"{secrets.randbelow(900000) + 100000}"
    telas = int(spec.get("telas") or 1)
    corpo = {
        "userId": painel["user"],
        "serverId": painel["server"],
        "packageId": spec["id"],
        "username": usuario,
        "password": senha,
        "whatsapp": whatsapp or "",
        "connections": telas,
        "note": "teste 2h pelo painel",
    }
    status, resp, erro = rede.pedir("POST", f"{painel['base']}/customers", corpo, painel["token"])
    if erro or status >= 400:
        frase = _frase_http(status, erro).replace("Nada foi alterado.", "Nada foi criado.")
        return False, frase, frase
    criado = _primeiro(resp) or {}
    ident = str(criado.get("id") or "").strip()
    ficou = telas
    if ident:
        status, conf, erro = rede.pedir("GET", f"{painel['base']}/customers/{quote(ident)}", None, painel["token"])
        if not erro and status < 400:
            lido = _telas(_primeiro(conf) or {})
            if lido is not None:
                ficou = lido
    tela_txt = "1 tela" if ficou == 1 else f"{ficou} telas"
    tela = (
        f"Criei um teste de 2 horas no {app}. Usuário {usuario}, senha {senha}. "
        f"Ficou com {tela_txt}. Anote a senha agora — ela não fica salva no painel."
    )
    log = f"Criei um teste de 2 horas no {app}. Usuário {usuario}. Ficou com {tela_txt}."
    return True, tela, log


def _token(cfg, nome: str) -> str:
    if not nome:
        return ""
    valor = (os.environ.get(nome) or "").strip()
    if valor:
        return valor
    arquivos = list(_ARQUIVOS_ENV)
    if getattr(cfg, "env_espelho", None):
        arquivos.append(Path(cfg.env_espelho))
    for caminho in arquivos:
        achado = ler_env(caminho, nome)
        if achado:
            return achado.strip()
    return ""


def _pacote_pago(cfg, dias: int, plano_atual: str) -> str | None:
    tabela = (_json(cfg.planos).get("pagos") or {}).get(str(dias)) or {}
    if not isinstance(tabela, dict):
        return None
    texto = plano_atual.casefold()
    sem = "sem" in texto and ("18" in texto or "adult" in texto)
    return tabela.get("sem") if sem else tabela.get("com")


def _lista(corpo) -> list:
    if isinstance(corpo, list):
        return [item for item in corpo if isinstance(item, dict)]
    if isinstance(corpo, dict):
        for chave in ("data", "customers", "rows"):
            if isinstance(corpo.get(chave), list):
                return [item for item in corpo[chave] if isinstance(item, dict)]
        if corpo.get("id") or corpo.get("username"):
            return [corpo]
    return []


def _primeiro(corpo) -> dict | None:
    itens = _lista(corpo)
    return itens[0] if itens else None


def _telas(cliente: dict):
    for chave in ("connections", "telas", "max_connections"):
        valor = cliente.get(chave)
        if valor is None or valor == "":
            continue
        try:
            return int(valor)
        except (TypeError, ValueError):
            continue
    return None


def _frase_http(status: int, erro: str | None) -> str:
    if erro == "tempo":
        return "O Sigma não respondeu. Nada foi alterado."
    if erro == "sem_rede":
        return "Não consegui falar com o Sigma. Nada foi alterado."
    if status == 429:
        return "O Sigma pediu uma pausa. Tente de novo daqui a pouco. Nada foi alterado."
    if status in (401, 403):
        return "O Sigma não aceitou o acesso. Nada foi alterado."
    return "Não consegui fazer isso agora. Nada foi alterado."


def _json(caminho: Path) -> dict:
    try:
        dado = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dado if isinstance(dado, dict) else {}
