"""Séries para os gráficos ao vivo. Só reúne o que o painel já lê.

Não abre fonte nova. Se o arquivo não está na máquina, devolve sem dado — nunca zero inventado.
Com PAINEL_DEMO=1 a pré-visualização usa os exemplos de demo_dados.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from app.tempo import TZ, agora

CAP_ENVIO = 240


def _sem(motivo: str) -> dict:
    return {"sem_dado": True, "motivo": motivo}


def montar(nucleo=None) -> dict:
    if os.environ.get("PAINEL_DEMO") == "1":
        from app.demo_dados import graficos

        return graficos()
    return {
        "ok": True,
        "demo": False,
        "cap_envio_min": CAP_ENVIO,
        "vendas_hora": _vendas_hora(),
        "mensagens_min": _mensagens(),
        "funil": _funil(),
        "robo": _robo(),
        "ativos": _ativos(),
        "envio": _envio(nucleo),
    }


def _vendas_hora() -> dict:
    from app.painel_1110 import ARQ_LEDGER, ARQ_USADOS, vendas

    if not ARQ_LEDGER.exists() and not ARQ_USADOS.exists():
        return _sem("sem dado — o livro de vendas não está neste computador")
    try:
        v = vendas("hoje")
    except Exception:
        return _sem("sem dado — não deu para ler as vendas de hoje")
    barras = v.get("barras") or {}
    if not barras.get("rotulos"):
        return _sem("sem dado — as vendas de hoje não trouxeram o horário")
    return {
        "rotulos": barras.get("rotulos"),
        "n": barras.get("n"),
        "reais": barras.get("reais"),
        "hora_agora": barras.get("hora_agora"),
        "fonte": "mesmo apurado da aba Vendas",
    }


def _funil() -> dict:
    from app.painel_1110 import ARQ_QUEUE, vendas

    if not ARQ_QUEUE.exists():
        return _sem("sem dado — o registro do webhook não está neste computador")
    try:
        v = vendas("hoje")
        funil = v.get("funil") or {}
    except Exception:
        return _sem("sem dado — não deu para montar o funil")
    total = funil.get("total") or {}
    etapas = []
    for chave, nome in funil.get("etapas") or []:
        etapas.append({"nome": nome, "n": total.get(chave)})
    if not etapas:
        return _sem("sem dado — o funil veio vazio")
    return {
        "etapas": etapas,
        "vazamento": funil.get("maior_vazamento"),
        "fonte": "funil do lead",
    }


def _mensagens() -> dict:
    from app.webhook_vivo import ARQ_ENVIADO, ARQ_RECEBIDO, VIVO

    if not ARQ_RECEBIDO.exists() and not ARQ_ENVIADO.exists():
        return _sem("sem dado — o registro do webhook não está neste computador")
    try:
        pacote = VIVO.pacote()
    except Exception:
        return _sem("sem dado — não deu para ler as mensagens")
    serie = pacote.get("serie_60min") or []
    if not serie:
        return _sem("sem dado — ainda não há minuto fechado no registro")
    momento = agora()
    rotulos = [(momento - timedelta(minutes=len(serie) - 1 - i)).strftime("%H:%M") for i in range(len(serie))]
    return {
        "rotulos": rotulos,
        "recebidas": [p[0] for p in serie],
        "enviadas": [p[1] for p in serie],
        "fonte": "registro do webhook",
    }


def _robo() -> dict:
    from app.painel_1110 import alertas, saude

    try:
        s = saude()
    except Exception:
        return _sem("sem dado — não deu para ler a saúde dos serviços")
    servicos = [
        {"nome": item.get("rotulo") or item.get("nome"), "ok": item.get("estado") == "active"}
        for item in (s.get("servicos") or [])
    ]
    try:
        lista = (alertas().get("alertas") or [])
    except Exception:
        lista = []
    momento = agora()
    erros = [0] * 12
    rotulos = [f"{(momento - timedelta(hours=11 - i)).hour}h" for i in range(12)]
    inicio = momento - timedelta(hours=11)
    for item in lista:
        if item.get("nivel") not in ("ruim", "atencao"):
            continue
        try:
            quando = datetime.fromisoformat(str(item.get("ts")))
        except ValueError:
            continue
        if quando.tzinfo is None:
            quando = quando.replace(tzinfo=TZ)
        horas = int((quando - inicio).total_seconds() // 3600)
        if 0 <= horas < 12:
            erros[horas] += 1
    fiscal = s.get("fiscal") or {}
    robo = s.get("robo") or {}
    return {
        "servicos": servicos,
        "erros_hora": erros,
        "rotulos_hora": rotulos,
        "fila": _int(robo.get("pendentes")),
        "ocupadas": _int(robo.get("ocupadas")),
        "falhas_fiscal": fiscal.get("fast_wh_falhou"),
        "fonte": "saúde dos serviços + alertas das últimas horas",
    }


def _ativos() -> dict:
    import json

    caminho = "/var/lib/painel-gxtv/ativos_reais.json"
    try:
        with open(caminho, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return _sem("sem dado — a contagem de ativos ainda não está neste computador")
    queridos = ("P1", "P2", "P3", "P4", "P5", "P6")
    por = {}
    for painel in doc.get("paineis") or []:
        canon = str(painel.get("canon") or "")
        if canon not in queridos:
            continue
        v2 = painel.get("v2") or {}
        n = v2.get("sigma")
        if n is None:
            n = painel.get("real")
        por[canon] = n
    paineis = []
    for nome in queridos:
        if nome == "P3":
            paineis.append({"id": "P3", "n": None, "ativo": False, "nota": "desligado"})
            continue
        if nome not in por:
            paineis.append({"id": nome, "n": None, "ativo": True, "nota": "sem dado"})
        else:
            paineis.append({"id": nome, "n": por[nome], "ativo": True})
    return {"paineis": paineis, "fonte": "ativos reais"}


def _envio(nucleo) -> dict:
    agora_n = None
    if nucleo is not None and getattr(nucleo, "publico", None):
        gavetas = (nucleo.publico or {}).get("gavetas") or {}
        saude = gavetas.get("saude") or {}
        agora_n = saude.get("envios_min")
    if agora_n is None:
        return {
            "agora": None,
            "teto": CAP_ENVIO,
            "serie": None,
            "rotulos": None,
            **_sem("sem dado — o ritmo de envio não está no registro recente"),
        }
    return {
        "agora": agora_n,
        "teto": CAP_ENVIO,
        "serie": None,
        "rotulos": None,
        "fonte": "ritmo de envio do robô",
    }


def _int(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None
