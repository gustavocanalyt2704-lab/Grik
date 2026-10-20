#!/usr/bin/env bash
# Avisar Gustavo no Telegram — rodar NA VPS após deploy F1.
set -euo pipefail
set -a
# shellcheck disable=SC1091
source /etc/mnrobo-box.env
set +a
MSG="${1:-Painel GXTV v2 F1 no ar em /v2 — design system, registro de métricas, filtros, estados honestos. Raiz do painel atual intacta.}"
python3 /workspace/telegram/notify.py "$MSG" 2>/dev/null \
  || python3 /opt/mnrobo/telegram/notify.py "$MSG" 2>/dev/null \
  || python3 - <<'PY'
import os, urllib.request, urllib.parse
token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TG_BOT_TOKEN")
chat = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("TG_CHAT_ID") or os.environ.get("GUSTAVO_CHAT_ID")
msg = os.environ.get("MSG") or "Painel GXTV v2 F1 (/v2) pronto p/ revisão."
if not token or not chat:
    raise SystemExit("sem TELEGRAM_* no env")
data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=20)
print("telegram ok")
PY
