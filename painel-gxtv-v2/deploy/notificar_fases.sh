#!/usr/bin/env bash
# Notifica F3–F7 (após deploy). Uso: notificar_fases.sh F3
set -euo pipefail
FASE="${1:-F7}"
case "$FASE" in
  F3) MSG='Painel GXTV v2 — F3 Atendimento
Funil clicável + tempo resposta média/mediana/P95/máx (agrupa msgs seguidas).
Atual×7d. Zero DataCrazy. :8742/v2 (v1 intacto)' ;;
  F4) MSG='Painel GXTV v2 — F4 Comercial
Gestor-first: vendas + vencem hoje + WhatsApp 3619/0837. Gestor down ≠ 0.
:8742/v2' ;;
  F5) MSG='Painel GXTV v2 — F5 Operação
Problemas × ontem/média 7d + correlações app×aparelho×hora.
:8742/v2' ;;
  F6) MSG='Painel GXTV v2 — F6 Robô/IA
Nomes claros + tooltips do registro. POLL + envios.
:8742/v2' ;;
  F7|*) MSG='Painel GXTV v2 — F2→F7 empilhadas
Início SSE, Atendimento, Comercial Gestor-first, Operação, Robô, cron TG 23:55 Bahia.
URL https://179.236.239.192:8742/v2 · v1 :8741 intacto
Branch cursor/painel-gxtv-v2-f2-d777' ;;
esac

if [[ -f /opt/mnrobo/ops/notify.py ]]; then
  python3 /opt/mnrobo/ops/notify.py --text "$MSG" || true
else
  echo "$MSG"
fi
