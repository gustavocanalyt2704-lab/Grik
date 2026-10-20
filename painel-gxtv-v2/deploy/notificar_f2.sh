#!/usr/bin/env bash
# Notifica Gustavo no Telegram — F2 pronta (rodar na VPS após deploy).
set -euo pipefail
MSG='Painel GXTV v2 — F2 pronta
Início: KPIs Gestor-first + esperando>15min + clientes/min + entrada ao vivo + log SSE + saúde espelho.
Espelho: lag/cobertura. Zero GET DataCrazy. Gestor down ≠ 0.
URL https://179.236.239.192:8742/v2 (v1 :8741 intacto)'

if [[ -f /opt/mnrobo/ops/notify.py ]]; then
  python3 /opt/mnrobo/ops/notify.py --text "$MSG" || true
elif [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
  curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="$TELEGRAM_CHAT_ID" \
    --data-urlencode text="$MSG" >/dev/null || true
else
  echo "$MSG"
  echo "(sem notify.py / tokens — imprima acima)"
fi
