"""Ficha do cliente para a tela de ações. Junta gestor, conversa recente e pausa."""

from __future__ import annotations

from app.gestor_busca import buscar
from app.mascarar import mascarar_telefone, so_digitos
from app.pausa_cliente import pausado
from app.protegidos import protegido


def montar(cfg, consulta: str, publico: dict | None = None) -> dict:
    consulta = (consulta or "").strip()
    if not consulta:
        return {"ok": False, "frase": "Digite o telefone ou o usuário."}
    if protegido(consulta):
        return {
            "ok": True,
            "protegido": True,
            "frase": "Esse número é protegido. Dá para ver, mas o painel não mexe nele.",
            "usuario": "",
            "telefone": mascarar_telefone(consulta) or "",
            "ultima": "Sem conversa recente no painel.",
            "linha": "sem número",
        }
    ficha = buscar(cfg.gestor_url, consulta)
    if not ficha.get("ok"):
        return ficha
    if protegido(ficha.get("telefone")):
        ficha["protegido"] = True
        ficha["frase"] = "Esse número é protegido. Dá para ver, mas o painel não mexe nele."
    else:
        ficha["protegido"] = False
    ficha["ultima"] = _ultima(publico, ficha.get("telefone"), consulta)
    ficha["linha"] = _linha(publico, ficha.get("telefone"), consulta)
    ficha["pausado"] = pausado(cfg.lista_pausa, ficha.get("telefone"))
    return ficha


def _ultima(publico, telefone, consulta) -> str:
    item = _achar(publico, telefone, consulta)
    if not item:
        return "Sem conversa recente no painel."
    assunto = item.get("assunto") or "assunto não identificado"
    quem = item.get("atendente") or "ninguém"
    if item.get("min") is not None and item.get("esperando"):
        return f"Última conversa: {assunto}, com {quem}, há {item['min']} min."
    return f"Última conversa: {assunto}, com {quem}."


def _linha(publico, telefone, consulta) -> str:
    item = _achar(publico, telefone, consulta)
    if item and item.get("whats") and item.get("whats") != "sem número":
        return str(item["whats"])
    return "sem número"


def _achar(publico, telefone, consulta) -> dict | None:
    if not isinstance(publico, dict):
        return None
    fim = _fim(telefone) or _fim(consulta)
    if not fim:
        return None
    listas = []
    chats = publico.get("chats") or {}
    atendimento = (publico.get("gavetas") or {}).get("atendimento") or {}
    listas.extend(chats.get("recentes") or [])
    listas.extend(atendimento.get("lista") or [])
    for item in listas:
        if not isinstance(item, dict):
            continue
        ph = so_digitos(item.get("ph"))
        if ph and ph[-4:] == fim:
            return item
    return None


def _fim(valor) -> str:
    digitos = so_digitos(valor)
    if len(digitos) < 4:
        return ""
    return digitos[-4:]
