#!/bin/bash
# Somente leitura: timers, resultado da última execução e crontabs.
set -u
echo '### SHOW'
ids=()
while read -r unidade _; do
  case "$unidade" in
    *.timer) ids+=("$unidade") ;;
  esac
done < <(systemctl list-units --type=timer --all --no-legend --plain --no-pager 2>/dev/null || true)
if ((${#ids[@]})); then
  systemctl show "${ids[@]}" -p Id -p NextElapseUSecRealtime -p LastTriggerUSec -p Triggers --timestamp=us --no-pager 2>/dev/null || true
fi
echo
echo '### RESULTS'
servicos=()
if ((${#ids[@]})); then
  while read -r linha; do
    case "$linha" in
      Triggers=*.service*) servicos+=("${linha#Triggers=}") ;;
    esac
  done < <(systemctl show "${ids[@]}" -p Triggers --no-pager 2>/dev/null || true)
fi
if ((${#servicos[@]})); then
  systemctl show "${servicos[@]}" -p Id -p Result --no-pager 2>/dev/null || true
fi
echo
echo '### CRON_ROOT'
crontab -l 2>/dev/null || true
echo
echo '### CRON_MNROBO'
crontab -u mnrobo -l 2>/dev/null || true
echo
