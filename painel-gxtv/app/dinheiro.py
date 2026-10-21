"""Pagamento que entra no painel: só dinheiro recebido de cliente.

Ficam de fora a caixinha (investimento), o resgate e a transferência
entre contas da própria empresa (MN Media / titular).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta

from app.mascarar import mascarar_telefone
from app.tempo import TZ, inicio_do_dia

_CAIXA = re.compile(
    r"\b(caixinha|investimento|investimentos|resgate|rendimento|rendimentos|aplicacao)\b"
)
_TRANSF = re.compile(r"\b(transferencia|transferido|transferida)\b")
_CONTA_PROPRIA = re.compile(
    r"(mn\s*media|mn\s*midia|conta\s+propria|entre\s+contas|gustavo\s+lucas|gustavolucas)"
)
_STATUS_OK = {"", "ok", "aprovado", "aprovada", "renovado", "renovada", "pago", "paga", "sucesso"}
_STATUS_RUIM = {"bloqueado", "bloqueada", "erro", "falha", "cancelado", "cancelada", "recusado", "recusada"}


def _norm(valor) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.casefold()


def _texto_pagamento(pagamento: dict) -> str:
    pedacos = [
        pagamento.get("nome"),
        pagamento.get("descricao"),
        pagamento.get("metodo"),
        pagamento.get("tipo"),
        pagamento.get("operacao"),
        pagamento.get("origem"),
    ]
    return " ".join(_norm(p) for p in pedacos if p)


def motivo_exclusao(pagamento: dict) -> str | None:
    """Devolve o motivo humano se o lançamento NÃO for pagamento de cliente."""
    try:
        valor = float(pagamento.get("valor") or 0)
    except (TypeError, ValueError):
        return "valor ilegível"
    if valor <= 0:
        return "não é entrada de dinheiro"

    texto = _texto_pagamento(pagamento)
    if _CAIXA.search(texto):
        return "caixinha, investimento ou resgate"
    if re.search(r"mn\s*media|mn\s*midia", texto):
        return "conta da própria empresa"
    if _TRANSF.search(texto) and _CONTA_PROPRIA.search(texto):
        return "transferência entre contas da empresa"
    return None


def eh_pagamento_de_cliente(pagamento: dict) -> bool:
    return motivo_exclusao(pagamento) is None


def _quando(pagamento: dict) -> datetime | None:
    bruto = pagamento.get("data_aprovado") or pagamento.get("data_brt") or pagamento.get("registrado_em") or pagamento.get("ts")
    if not bruto:
        return None
    texto = str(bruto).strip().replace("Z", "+00:00")
    try:
        momento = datetime.fromisoformat(texto)
    except ValueError:
        return None
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=TZ)
    return momento.astimezone(TZ)


def _id(pagamento: dict) -> str:
    bruto = pagamento.get("id") or pagamento.get("payment_id") or pagamento.get("e2e")
    if bruto is None:
        return ""
    return str(bruto)


def _status_ok(registro: dict) -> bool:
    status = _norm(registro.get("status"))
    if status in _STATUS_RUIM:
        return False
    if status in _STATUS_OK:
        return True
    return False


def _venda_nova(registro: dict) -> bool:
    marca = registro.get("venda_nova")
    if isinstance(marca, str):
        return _norm(marca) in {"1", "true", "sim", "yes"}
    return bool(marca)


def classificar_dia(pagamentos: list[dict] | None, lancamentos: list[dict] | None, agora: datetime) -> dict:
    """Soma o dia e separa renovação de cliente novo quando o lançamento existe.

    pagamentos None = arquivo ausente (sem dado).
    lancamentos None = não há como separar renovação de cliente novo.
    """
    if pagamentos is None:
        return {
            "total": None,
            "qtd": None,
            "renov_valor": None,
            "renov_qtd": None,
            "novas_valor": None,
            "novas_qtd": None,
            "ticket": None,
            "ontem": None,
            "horas": None,
            "ontem_horas": None,
            "excluidos": None,
            "eventos": [],
            "sem_lista": True,
        }

    inicio_hoje = inicio_do_dia(agora)
    inicio_ontem = inicio_do_dia(agora, 1)
    corte_ontem = agora.astimezone(TZ) - timedelta(days=1)

    por_id: dict[str, dict] = {}
    por_e2e: dict[str, dict] = {}
    por_valor: list[dict] = []
    if lancamentos:
        for registro in lancamentos:
            if not _status_ok(registro):
                continue
            if registro.get("payment_id") not in (None, ""):
                por_id[str(registro["payment_id"])] = registro
            if registro.get("e2e"):
                por_e2e[str(registro["e2e"])] = registro
            por_valor.append(registro)

    usados: set[int] = set()
    vistos: set[str] = set()
    total = 0.0
    qtd = 0
    renov_valor = 0.0
    renov_qtd = 0
    novas_valor = 0.0
    novas_qtd = 0
    ontem = 0.0
    excluidos = 0
    horas = [0.0] * 24
    ontem_horas = [0.0] * 24
    eventos = []
    hora_atual = agora.astimezone(TZ).hour

    ordenados = []
    for pagamento in pagamentos:
        quando = _quando(pagamento)
        if quando is None or quando < inicio_ontem or quando > agora.astimezone(TZ) + timedelta(minutes=5):
            continue
        ident = _id(pagamento)
        if ident and ident in vistos:
            continue
        if ident:
            vistos.add(ident)
        ordenados.append((quando, pagamento, ident))
    ordenados.sort(key=lambda item: item[0])

    for quando, pagamento, ident in ordenados:
        if motivo_exclusao(pagamento):
            if quando >= inicio_hoje:
                excluidos += 1
            continue
        valor = float(pagamento["valor"])
        if quando >= inicio_hoje:
            total += valor
            qtd += 1
            horas[quando.hour] += valor
            classe, registro = _casar(pagamento, ident, quando, por_id, por_e2e, por_valor, usados)
            if lancamentos is not None and classe == "renov":
                renov_valor += valor
                renov_qtd += 1
            elif lancamentos is not None and classe == "nova":
                novas_valor += valor
                novas_qtd += 1
            else:
                classe = "pag" if lancamentos is not None else "pag"
            eventos.append(_evento(pagamento, ident, quando, valor, classe, registro if lancamentos is not None else None))
        elif inicio_ontem <= quando <= corte_ontem:
            ontem += valor
            ontem_horas[quando.hour] += valor

    def acumulado(serie, ate):
        saida = []
        soma = 0.0
        for hora, valor in enumerate(serie):
            if ate is not None and hora > ate:
                saida.append(None)
                continue
            soma += valor
            saida.append(round(soma, 2))
        return saida

    return {
        "total": round(total, 2),
        "qtd": qtd,
        "renov_valor": None if lancamentos is None else round(renov_valor, 2),
        "renov_qtd": None if lancamentos is None else renov_qtd,
        "novas_valor": None if lancamentos is None else round(novas_valor, 2),
        "novas_qtd": None if lancamentos is None else novas_qtd,
        "ticket": round(total / qtd, 2) if qtd else None,
        "ontem": round(ontem, 2),
        "horas": acumulado(horas, hora_atual),
        "ontem_horas": acumulado(ontem_horas, 23),
        "excluidos": excluidos,
        "eventos": eventos[-14:],
        "sem_lista": False,
    }


def _casar(pagamento, ident, quando, por_id, por_e2e, por_valor, usados):
    registro = None
    if ident and ident in por_id:
        registro = por_id[ident]
    elif pagamento.get("e2e") and str(pagamento["e2e"]) in por_e2e:
        registro = por_e2e[str(pagamento["e2e"])]
    else:
        melhor = None
        melhor_delta = timedelta(hours=6) + timedelta(seconds=1)
        for indice, candidato in enumerate(por_valor):
            if indice in usados:
                continue
            try:
                if abs(float(candidato.get("valor") or -1) - float(pagamento["valor"])) > 0.009:
                    continue
            except (TypeError, ValueError):
                continue
            momento = _quando(candidato) or _quando({"data_aprovado": candidato.get("ts")})
            if momento is None:
                continue
            delta = abs(momento - quando)
            if delta <= timedelta(hours=6) and delta < melhor_delta:
                melhor = indice
                melhor_delta = delta
        if melhor is not None:
            usados.add(melhor)
            registro = por_valor[melhor]
    if registro is None:
        return "pag", None
    if _venda_nova(registro):
        return "nova", registro
    return "renov", registro


def _evento(pagamento, ident, quando, valor, classe, registro) -> dict:
    titulos = {
        "renov": "Renovação aprovada ✅",
        "nova": "Cliente novo pagou 🎉",
        "pag": "Pagamento recebido ✅",
    }
    telefone = mascarar_telefone((registro or {}).get("telefone") or pagamento.get("telefone"))
    detalhe = f"cliente {telefone}" if telefone else "cliente sem telefone no aviso"
    painel = (registro or {}).get("painel")
    if painel and re.fullmatch(r"P\d{1,2}", str(painel).upper()):
        detalhe += f" · painel {str(painel).upper()}"
    return {
        "id": f"mp-{ident or quando.isoformat()}-{classe}",
        "titulo": titulos[classe],
        "detalhe": detalhe,
        "tom": "dinheiro" if classe != "nova" else "novo",
        "valor": round(valor, 2),
        "em": quando.isoformat(),
    }
