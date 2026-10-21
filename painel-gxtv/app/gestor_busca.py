"""Busca o cliente no gestor. Sem chave. Não grava nada."""

from __future__ import annotations

from urllib.parse import quote

from app import rede
from app.mascarar import so_digitos

_CHAVES_SUMIR = {"password", "senha", "token", "secret", "access_token"}


def buscar(url_base: str, consulta: str) -> dict:
    consulta = (consulta or "").strip()
    if not consulta:
        return {"ok": False, "frase": "Digite o telefone ou o usuário."}
    tentativas = _consultas(consulta)
    ultimo = {"ok": False, "frase": "Não achei ninguém com isso."}
    for texto in tentativas:
        status, corpo, erro = rede.pedir("GET", f"{url_base}?query={quote(texto)}", None, None, timeout=10)
        if erro or status >= 400 or not isinstance(corpo, dict):
            ultimo = {"ok": False, "frase": "Não consegui consultar o cadastro agora."}
            continue
        lido = interpretar(corpo)
        if lido.get("varios"):
            return {"ok": False, "varios": True, "frase": "Achei mais de um cliente. Busque pelo usuário do Sigma."}
        if lido.get("ok"):
            return lido
        ultimo = lido
    return ultimo


def interpretar(corpo: dict) -> dict:
    matches = corpo.get("matches_count")
    customer = corpo.get("customer") or corpo.get("cliente")
    if isinstance(customer, list):
        if len(customer) > 1 or (isinstance(matches, int) and matches > 1):
            return {"ok": False, "varios": True, "frase": "Achei mais de um cliente. Busque pelo usuário do Sigma."}
        customer = customer[0] if customer else None
    if isinstance(matches, int) and matches > 1 and not isinstance(customer, dict):
        return {"ok": False, "varios": True, "frase": "Achei mais de um cliente. Busque pelo usuário do Sigma."}
    if not isinstance(customer, dict):
        if corpo.get("sigma_username") or corpo.get("username"):
            customer = corpo
        else:
            return {"ok": False, "frase": "Não achei ninguém com isso."}
    ficha = _ficha(customer)
    if not ficha.get("usuario") and not ficha.get("telefone"):
        return {"ok": False, "frase": "Não achei ninguém com isso."}
    ficha["ok"] = True
    ficha["frase"] = f"Achei {ficha['usuario'] or 'esse cliente'}."
    return ficha


def _ficha(customer: dict) -> dict:
    limpo = {k: v for k, v in customer.items() if str(k).casefold() not in _CHAVES_SUMIR}
    usuario = str(limpo.get("sigma_username") or limpo.get("username") or "").strip()
    telefone = str(limpo.get("whatsapp") or limpo.get("telefone") or limpo.get("phone") or "").strip()
    plano = str(limpo.get("pacote") or limpo.get("package") or limpo.get("plan") or "").strip()
    venc = limpo.get("venc") or limpo.get("expires_at") or limpo.get("expires_at_tz") or ""
    telas = limpo.get("telas")
    if telas is None:
        telas = limpo.get("connections")
    app = str(limpo.get("app") or "").strip()
    painel = str(limpo.get("panel_label") or limpo.get("panel_id") or limpo.get("server") or "").strip()
    trial = limpo.get("is_trial")
    if isinstance(trial, str):
        trial = trial.strip().casefold() in {"1", "true", "yes", "sim"}
    return {
        "usuario": usuario,
        "plano": plano,
        "vencimento": _data_curta(venc),
        "telas": telas,
        "app": app,
        "painel_sigma": painel,
        "teste": bool(trial),
        "telefone": telefone,
        "painel_sugerido": "promo" if "promo" in painel.casefold() else "principal",
    }


def _data_curta(valor) -> str:
    texto = str(valor or "").strip()
    if len(texto) >= 10 and texto[4] == "-" and texto[7] == "-":
        ano, mes, dia = texto[:10].split("-")
        return f"{dia}/{mes}/{ano}"
    return texto[:16]


def _consultas(consulta: str) -> list[str]:
    digitos = so_digitos(consulta)
    if not digitos or len(digitos) < 8 or any(c.isalpha() for c in consulta):
        return [consulta]
    saida = []

    def add(item: str):
        if item and item not in saida:
            saida.append(item)

    add(consulta)
    add(digitos)
    sem = digitos[2:] if digitos.startswith("55") and len(digitos) > 11 else digitos
    add(sem)
    if not sem.startswith("55"):
        add("55" + sem)
    if len(sem) == 10:
        com9 = sem[:2] + "9" + sem[2:]
        add(com9)
        add("55" + com9)
    elif len(sem) == 11 and sem[2] == "9":
        sem9 = sem[:2] + sem[3:]
        add(sem9)
        add("55" + sem9)
    return saida[:3]
