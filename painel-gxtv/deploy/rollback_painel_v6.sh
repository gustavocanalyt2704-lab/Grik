#!/bin/bash
# Volta o painel para o backup feito pelo deploy_painel_v6.sh.
# Não apaga nada se não achar backup. Não mexe no robô.
set -euo pipefail

ULTIMO="/var/backups/painel-gxtv/ULTIMO"
if [[ ! -f "$ULTIMO" ]]; then
  echo "não achei backup para voltar. Não apaguei nada." >&2
  exit 1
fi
BKP="$(tr -d '[:space:]' < "$ULTIMO")"
if [[ ! -d "$BKP/painel-gxtv" ]]; then
  echo "backup incompleto em ${BKP}. Não apaguei nada." >&2
  exit 1
fi

systemctl stop painel-gxtv >/dev/null 2>&1 || true
rm -rf /opt/painel-gxtv
cp -a "$BKP/painel-gxtv" /opt/painel-gxtv
if [[ -f "$BKP/painel-gxtv.service" ]]; then
  cp -a "$BKP/painel-gxtv.service" /etc/systemd/system/painel-gxtv.service
fi
systemctl daemon-reload
systemctl enable painel-gxtv >/dev/null 2>&1 || true
systemctl start painel-gxtv
echo "voltei o painel para o backup $BKP"
echo "a senha em /var/lib/painel-gxtv não foi mexida"
