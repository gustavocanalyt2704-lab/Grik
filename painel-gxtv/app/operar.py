"""Ações do painel: confirma, executa uma vez e registra o resultado."""

from __future__ import annotations

from app.ficha import montar as montar_ficha
from app.mascarar import mascarar_telefone, so_digitos
from app.pausa_cliente import pausar, soltar
from app.protegidos import protegido
from app.registro import gravar
from app.sigma_acoes import criar_teste, liberar_telas, opcoes, renovar

_ACOES = {"teste", "renovar", "telas", "pausar", "soltar"}


def executar(cfg, usuario: str, pedido: dict, publico: dict | None = None) -> dict:
    acao = str((pedido or {}).get("acao") or "").strip()
    consulta = str((pedido or {}).get("q") or "").strip()
    if acao not in _ACOES:
        return {"ok": False, "frase": "Escolha o que fazer."}
    if not consulta:
        return {"ok": False, "frase": "Digite o telefone ou o usuário."}
    if protegido(consulta):
        return {"ok": False, "frase": "Esse número é protegido. Não mexi em nada."}

    ficha = montar_ficha(cfg, consulta, publico)
    if ficha.get("varios"):
        return {"ok": False, "frase": ficha.get("frase") or "Achei mais de um cliente. Busque pelo usuário do Sigma."}
    if ficha.get("protegido") or protegido(ficha.get("telefone")):
        return {"ok": False, "frase": "Esse número é protegido. Não mexi em nada."}
    if not ficha.get("ok") and acao in {"renovar", "telas"}:
        return {"ok": False, "frase": ficha.get("frase") or "Não achei esse cliente. Nada foi alterado."}

    painel = str(pedido.get("painel") or ficha.get("painel_sugerido") or "principal")
    dias = pedido.get("dias") or 30
    app = str(pedido.get("app") or ficha.get("app") or "").strip()
    nome = ficha.get("usuario") or mascarar_telefone(consulta) or "esse cliente"
    confirma = _pergunta(acao, nome, dias, app, painel, cfg)
    if not pedido.get("confirmar"):
        saida = {"ok": False, "precisa_confirmar": True, "frase": confirma, "ficha": _publica(ficha)}
        return saida

    ok, frase, frase_log = _fazer(cfg, acao, ficha, consulta, painel, dias, app, nome)
    if acao == "pausar" and ok:
        ficha["pausado"] = True
    if acao == "soltar" and ok:
        ficha["pausado"] = False
    gravar(cfg.registro, usuario, acao, _alvo(ficha, consulta), painel if acao in {"teste", "renovar", "telas"} else "", frase_log, ok)
    return {"ok": ok, "frase": frase, "ficha": _publica(ficha)}


def _fazer(cfg, acao, ficha, consulta, painel, dias, app, nome):
    if acao == "pausar":
        ok, frase = pausar(cfg.lista_pausa, ficha.get("telefone") or consulta)
        return ok, _trocar_nome(frase, nome), frase
    if acao == "soltar":
        ok, frase = soltar(cfg.lista_pausa, ficha.get("telefone") or consulta)
        return ok, _trocar_nome(frase, nome), frase
    usuario = ficha.get("usuario") or (consulta if any(c.isalpha() for c in consulta) else "")
    if acao == "teste":
        whats = so_digitos(ficha.get("telefone") or consulta)
        ok, tela, log = criar_teste(cfg, painel, app, whats)
        return ok, tela, log
    if not usuario:
        frase = "Não achei o usuário do Sigma. Nada foi alterado."
        return False, frase, frase
    if acao == "renovar":
        try:
            dias_n = int(dias)
        except (TypeError, ValueError):
            dias_n = 0
        ok, frase = renovar(cfg, painel, usuario, dias_n)
        return ok, frase, frase
    if acao == "telas":
        ok, frase = liberar_telas(cfg, painel, usuario)
        return ok, frase, frase
    frase = "Escolha o que fazer."
    return False, frase, frase


def _pergunta(acao, nome, dias, app, painel, cfg) -> str:
    if acao == "teste":
        qual = app or "o app escolhido"
        return f"Criar um teste de 2 horas no {qual} para {nome}?"
    if acao == "renovar":
        return f"Renovar {nome} por {dias} dias?"
    if acao == "telas":
        meta = _telas_painel(cfg, painel)
        return f"Liberar {meta} telas para {nome}?"
    if acao == "pausar":
        return f"Pausar o robô só para {nome}? Os outros clientes continuam sendo atendidos."
    return f"Soltar o robô para {nome}?"


def _telas_painel(cfg, painel: str) -> int:
    for item in opcoes(cfg).get("paineis") or []:
        if item.get("id") == painel:
            return int(item.get("telas") or 4)
    return 4


def _alvo(ficha, consulta) -> str:
    if ficha.get("usuario"):
        return str(ficha["usuario"])[:80]
    return mascarar_telefone(consulta) or "cliente"


def _publica(ficha: dict) -> dict:
    if not isinstance(ficha, dict):
        return {}
    return {
        "ok": bool(ficha.get("ok")),
        "usuario": ficha.get("usuario") or "",
        "plano": ficha.get("plano") or "",
        "vencimento": ficha.get("vencimento") or "",
        "telas": ficha.get("telas"),
        "app": ficha.get("app") or "",
        "linha": ficha.get("linha") or "sem número",
        "ultima": ficha.get("ultima") or "",
        "pausado": bool(ficha.get("pausado")),
        "protegido": bool(ficha.get("protegido")),
        "painel_sugerido": ficha.get("painel_sugerido") or "principal",
        "telefone": ficha.get("telefone") or "",
        "frase": ficha.get("frase") or "",
    }


def _trocar_nome(frase: str, nome: str) -> str:
    if "esse cliente" in frase and nome:
        return frase.replace("esse cliente", nome)
    return frase
