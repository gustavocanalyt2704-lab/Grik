"""Séries para os gráficos do v2. Só agrupa o que o espelho já leu.

O teto de 240 envios por minuto é a regra da operação, não um número medido.
Se a fila do webhook não está na máquina, a resposta diz sem dado — não publica 0.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone

from app.core.timezone import TZ, agora
from app.sources import espelho, seed

CAP_ENVIO_MIN = 240
_ERRO = re.compile(r"erro|falhou|relig", re.IGNORECASE)


def ao_vivo() -> dict:
    if seed.seed_habilitado():
        return _seed()
    if not espelho.WEBHOOK_QUEUE.is_file():
        return {
            "ok": False,
            "sem_dado": True,
            "motivo": "sem dado — a fila do webhook não está neste computador",
            "cap_envio_min": CAP_ENVIO_MIN,
            "mensagens_min": {"sem_dado": True, "motivo": "sem dado — sem registro de mensagens"},
            "envio": {
                "agora": None,
                "teto": CAP_ENVIO_MIN,
                "sem_dado": True,
                "motivo": "sem dado — não há registro de envio",
            },
            "erros_min": {"sem_dado": True, "motivo": "sem dado — sem log para contar erro"},
            "vendas_hora": {"sem_dado": True, "motivo": "O Gestor não manda a venda hora a hora. O total continua no card."},
        }
    eventos = espelho.eventos_recentes(max_lines=8000)
    pacote = _de_eventos(eventos)
    log = _erros_log()
    if log and log["n"] and log["n"][0] > 0:
        pacote["erros_min"] = log
    pacote["vendas_hora"] = {
        "sem_dado": True,
        "motivo": "O Gestor não manda a venda hora a hora. O total continua no card.",
    }
    return pacote


def _seed() -> dict:
    momento = agora()
    rotulos = [(momento - timedelta(minutes=59 - i)).strftime("%H:%M") for i in range(60)]
    recebidas = [3 + (i % 5) for i in range(60)]
    enviadas = [5 + (i % 4) for i in range(60)]
    enviadas[-1] = 11
    vendas = [0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 4, 5, 7, 8, 9, 11, 8, 6, 4, 3, 2, 1]
    hora = momento.hour
    vendas = [n if i <= hora else 0 for i, n in enumerate(vendas)]
    return {
        "ok": True,
        "is_seed": True,
        "cap_envio_min": CAP_ENVIO_MIN,
        "mensagens_min": {
            "rotulos": rotulos,
            "recebidas": recebidas,
            "enviadas": enviadas,
            "fonte": "exemplo marcado como seed",
        },
        "envio": {
            "agora": 186,
            "teto": CAP_ENVIO_MIN,
            "serie": [*(120 + (i % 7) * 8 for i in range(59)), 186],
            "rotulos": rotulos,
            "fonte": "exemplo marcado como seed",
        },
        "erros_min": {
            "rotulos": [f"{(hora - 11 + i) % 24}h" for i in range(12)],
            "n": [0, 1, 0, 0, 2, 0, 1, 0, 0, 0, 1, 0],
            "fonte": "exemplo marcado como seed",
        },
        "vendas_hora": {
            "rotulos": [f"{i}h" for i in range(24)],
            "n": vendas,
            "fonte": "exemplo marcado como seed — o Gestor real não manda esta série",
        },
        "ativos": {
            "paineis": [
                {"id": "P1", "n": 820},
                {"id": "P2", "n": 640},
                {"id": "P3", "n": None, "nota": "desligado"},
                {"id": "P4", "n": 410},
                {"id": "P5", "n": 390},
                {"id": "P6", "n": 510},
            ],
            "fonte": "exemplo. O v2 não lê o Sigma; o número oficial de ativos está no painel da raiz.",
        },
    }


def _de_eventos(eventos: list[dict]) -> dict:
    now = time.time()
    minutos = 60
    inicio = now - minutos * 60
    recebidas = [0] * minutos
    enviadas = [0] * minutos
    erros = [0] * minutos
    ritmo = 0
    for evento in eventos:
        ts = evento.get("ts")
        if ts is None:
            continue
        ts = float(ts)
        if evento.get("from_me") and now - ts <= 60:
            ritmo += 1
        if ts < inicio or ts > now:
            continue
        indice = min(minutos - 1, int((ts - inicio) // 60))
        if evento.get("from_me"):
            enviadas[indice] += 1
        else:
            recebidas[indice] += 1
        if _ERRO.search(str(evento.get("text") or "")):
            erros[indice] += 1
    rotulos = [
        datetime.fromtimestamp(inicio + i * 60, tz=timezone.utc).astimezone(TZ).strftime("%H:%M")
        for i in range(minutos)
    ]
    return {
        "ok": True,
        "is_seed": False,
        "cap_envio_min": CAP_ENVIO_MIN,
        "mensagens_min": {
            "rotulos": rotulos,
            "recebidas": recebidas,
            "enviadas": enviadas,
            "fonte": "fila do webhook, últimos 60 minutos",
        },
        "envio": {
            "agora": ritmo,
            "teto": CAP_ENVIO_MIN,
            "serie": enviadas,
            "rotulos": rotulos,
            "fonte": "mensagens enviadas no webhook, por minuto. O número da direita é o último minuto.",
        },
        "erros_min": {
            "rotulos": rotulos,
            "n": erros,
            "fonte": "mensagens do webhook com palavra de erro",
        },
    }


def _erros_log() -> dict | None:
    env = espelho.tail_live_log(400)
    if env.state.value != "ok" or not isinstance(env.value, list):
        return None
    n = sum(1 for linha in env.value if _ERRO.search(str(linha.get("line") or "")))
    return {
        "rotulos": ["amostra"],
        "n": [n],
        "amostra": True,
        "fonte": "trecho recente do live.log",
    }
