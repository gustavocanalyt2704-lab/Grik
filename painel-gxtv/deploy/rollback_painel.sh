#!/bin/bash
# Tira o painel do ar e apaga o que ele instalou.
# Não mexe no robô, no Telegram nem nos dados que ele só lia.
set -euo pipefail

systemctl disable --now painel-gxtv >/dev/null 2>&1 || true
rm -f /etc/systemd/system/painel-gxtv.service
systemctl daemon-reload

if [[ -f /var/lib/painel-gxtv/ufw_porta ]] && command -v ufw >/dev/null 2>&1; then
  porta="$(tr -cd '0-9' < /var/lib/painel-gxtv/ufw_porta)"
  if [[ -n "$porta" ]]; then
    ufw delete allow "${porta}/tcp" >/dev/null 2>&1 || true
  fi
fi

rm -f /etc/sudoers.d/painel-gxtv
rm -f /usr/local/lib/painel-gxtv/ler_rotinas.sh
rmdir /usr/local/lib/painel-gxtv 2>/dev/null || true
rm -rf /opt/painel-gxtv
rm -rf /var/lib/painel-gxtv
echo "painel removido. A senha, se ainda existir, continua em /root/painel-gxtv-senha.txt"
