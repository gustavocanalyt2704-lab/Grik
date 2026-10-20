#!/usr/bin/env python3
"""Relatório diário Telegram — cron 23:55 America/Bahia (F7).

Uso (VPS):
  /opt/painel-gxtv-v2/venv/bin/python /opt/painel-gxtv-v2/backend/scripts/relatorio_diario_tg.py

Não reinicia mnrobo. Só lê fontes locais + Gestor (cache) e notifica.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.timezone import TZ_NAME, agora, iso_bahia  # noqa: E402
from app.services import atendimento as atendimento_svc  # noqa: E402
from app.services import comercial as comercial_svc  # noqa: E402
from app.services import inicio as inicio_svc  # noqa: E402
from app.services import operacao as operacao_svc  # noqa: E402
from app.services import robo as robo_svc  # noqa: E402


def _v(env: dict | None, default: str = "—") -> str:
    if not env:
        return default
    state = env.get("state")
    if state in ("unavailable", "error", "empty", "loading"):
        msg = env.get("message") or state
        last = (env.get("source") or {}).get("last_update")
        if state == "unavailable" and env.get("value") is not None:
            return f"indisponível (cache) · {last or '?'}"
        return f"{state}: {msg}" if msg else str(state)
    val = env.get("value")
    if isinstance(val, dict):
        if "n" in val:
            return str(val["n"])
        if "total" in val:
            return str(val["total"])
        if "valor" in val and val.get("valor") is not None:
            return f"R$ {val['valor']}"
    if isinstance(val, float):
        return f"{val:.2f}"
    if val is None:
        return default
    return str(val)


async def montar_texto() -> str:
    ini = await inicio_svc.montar_inicio({"periodo": "hoje"})
    at = atendimento_svc.montar_atendimento({"periodo": "hoje"})
    com = await comercial_svc.montar_comercial({"periodo": "hoje"})
    op = operacao_svc.montar_operacao({"periodo": "hoje"})
    rb = robo_svc.montar_robo({"periodo": "hoje"})

    k = ini.get("kpis") or {}
    agora_s = iso_bahia(agora())
    lines = [
        "MN Tecnologia — relatório diário",
        f"TZ {TZ_NAME} · {agora_s}",
        "",
        "Comercial (Gestor)",
        f"· Faturamento: {_v(k.get('faturamento'))}",
        f"· Renovações: {_v(k.get('renovacoes'))}",
        f"· Vencem hoje: {_v(k.get('vencem_hoje'))}",
        f"· Vendas (aba): {_v(com.get('vendas'))}",
        "",
        "Atendimento",
        f"· Atendidos: {_v(k.get('atendidos'))}",
        f"· Esperando >15min (agora): {_v(k.get('esperando_15min'))}",
        f"· T. resposta média: {_v((at.get('tempos') or {}).get('media'))}s",
        "",
        "Operação / Robô",
        f"· Problemas hoje: {_v(op.get('problemas'))}",
        f"· Ocupadas (POLL): {_v(rb.get('ocupadas'))}",
        f"· Envios robô: {_v(rb.get('envios'))}",
        "",
        "Espelho",
        f"· Saúde: {_v(ini.get('saude_espelho'))}",
        "",
        "Painel: https://179.236.239.192:8742/v2",
    ]
    return "\n".join(lines)


def enviar_telegram(texto: str) -> bool:
    # 1) notify.py mnrobo
    notify = Path(os.environ.get("MNROBO_NOTIFY", "/opt/mnrobo/ops/notify.py"))
    if notify.is_file():
        import subprocess

        r = subprocess.run(
            [sys.executable, str(notify), "--text", texto],
            capture_output=True,
            text=True,
        )
        return r.returncode == 0

    token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TG_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("TG_CHAT_ID")
    if token and chat:
        import urllib.parse
        import urllib.request

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": chat, "text": texto}).encode()
        try:
            urllib.request.urlopen(url, data=data, timeout=30)
            return True
        except Exception as exc:
            print("telegram falhou:", exc, file=sys.stderr)
            return False

    print(texto)
    return False


def main() -> int:
    texto = asyncio.run(montar_texto())
    dry = os.environ.get("DRY_RUN", "0") == "1"
    if dry:
        print(texto)
        return 0
    ok = enviar_telegram(texto)
    print("ok" if ok else "enviado_stdout_ou_falha")
    if not ok:
        print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
