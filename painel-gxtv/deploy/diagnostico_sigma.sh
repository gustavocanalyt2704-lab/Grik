#!/bin/bash
# Olha por que vendas novas e vencimento exato ficam sem dado,
# e quem (como root) voltou a gravar arquivo do contador.
# Só lê. Não reinicia nada. Não imprime senha nem chave.
set -u

redact() {
  sed -E \
    -e 's/([A-Za-z0-9_]*(TOKEN|PASSWORD|SECRET|DSN|KEY|SENHA)[A-Za-z0-9_]*=)[^[:space:]]+/\1***/Ig' \
    -e 's/(Bearer )[^[:space:]]+/\1***/Ig' \
    -e 's#(postgres(ql)?://[^:]+:)[^@]+@#\1***@#Ig'
}

echo "Diagnóstico do Sigma e do contador"
echo "Data desta máquina: $(date '+%Y-%m-%d %H:%M:%S %Z' 2>/dev/null || date)"
echo "Quem está rodando este script: $(id -un) (uid $(id -u))"
echo "Nada abaixo é senha. Se aparecer um valor longo no lugar de ***, pare e não encaminhe o arquivo."
echo

QUEBRA=()

marca() { QUEBRA+=("$1"); echo "  >> $1"; }

echo "== 1. Atalho do atendimento =="
if [[ -L /workspace/atendimento ]]; then
  echo "  /workspace/atendimento aponta para $(readlink -f /workspace/atendimento 2>/dev/null || readlink /workspace/atendimento)"
elif [[ -e /workspace/atendimento ]]; then
  echo "  /workspace/atendimento existe e NÃO é atalho"
else
  echo "  /workspace/atendimento não existe"
fi
echo

echo "== 2. Arquivos da lista do Sigma =="
ARQS=(
  /opt/mnrobo/contador_tg/cache/sigma_rows.ok.jsonl
  /opt/mnrobo/contador_tg/cache/sigma_rows.parcial.jsonl
  /opt/mnrobo/contador_tg/cache/sigma_estado.json
  /opt/mnrobo/contador_tg/cache/sigma_gate
  /opt/mnrobo/contador_tg/cache/sigma_disjuntor
  /opt/mnrobo/atendimento/ai/private/sigma_cache.json
  /workspace/atendimento/ai/private/sigma_cache.json
  /opt/mnrobo/atendimento/contador/painel_cache/sigma_users.json
  /workspace/atendimento/contador/painel_cache/sigma_users.json
)

le_mnrobo() {
  local f="$1"
  if ! id mnrobo >/dev/null 2>&1; then
    echo "usuário mnrobo não existe"
    return
  fi
  if [[ "$(id -u)" -eq 0 ]]; then
    if su -s /bin/sh mnrobo -c "test -r $(printf '%q' "$f")"; then
      echo "mnrobo CONSEGUE ler"
    else
      echo "mnrobo NÃO consegue ler"
      marca "o painel roda como mnrobo e não lê $f"
    fi
  else
    echo "não sou root, então não testei a leitura como mnrobo"
  fi
}

for f in "${ARQS[@]}"; do
  if [[ ! -e "$f" ]]; then
    echo "- AUSENTE  $f"
    continue
  fi
  if stat --printf '' "$f" >/dev/null 2>&1; then
    dono="$(stat -c '%U' "$f" 2>/dev/null || echo '?')"
    modo="$(stat -c '%a' "$f" 2>/dev/null || echo '?')"
    quando="$(stat -c '%y' "$f" 2>/dev/null || echo '?')"
    tamanho="$(stat -c '%s' "$f" 2>/dev/null || echo '?')"
  else
    dono="?"; modo="?"; quando="?"; tamanho="?"
  fi
  echo "- $f"
  echo "    dono=$dono modo=$modo tamanho=$tamanho alterado=$quando"
  echo "    $(le_mnrobo "$f")"
  if [[ "$dono" == "root" && "$modo" == "600" ]]; then
    marca "arquivo de root com permissão 600: $f"
  fi
done
echo

echo "== 3. O que esses arquivos contêm (só contagem e nomes de campo) =="
python3 - << 'PY' || echo "  python3 não conseguiu ler (sem permissão ou sem python3)"
import json, os, time
from pathlib import Path

def chaves(obj, limite=12):
    if isinstance(obj, dict):
        return sorted(obj.keys())[:limite]
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        return sorted(obj[0].keys())[:limite]
    return []

def linhas_jsonl(path):
    n = 0
    primeira = None
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue
                n += 1
                if primeira is None:
                    try:
                        primeira = json.loads(linha)
                    except json.JSONDecodeError:
                        primeira = {"ilegivel": True}
                if n > 500000:
                    break
    except OSError as exc:
        print(f"  {path}: sem leitura ({exc.__class__.__name__})")
        return
    print(f"  {path}: {n} linhas; campos={chaves(primeira)}")

for p in (
    "/opt/mnrobo/contador_tg/cache/sigma_rows.ok.jsonl",
    "/opt/mnrobo/contador_tg/cache/sigma_rows.parcial.jsonl",
):
    if os.path.isfile(p):
        linhas_jsonl(p)

estado = "/opt/mnrobo/contador_tg/cache/sigma_estado.json"
if os.path.isfile(estado):
    try:
        doc = json.load(open(estado, encoding="utf-8"))
        print("  estado: pagina=%s ultima=%s completo=%s" % (
            doc.get("page"), doc.get("last_page"), doc.get("completo")))
        ok = "/opt/mnrobo/contador_tg/cache/sigma_rows.ok.jsonl"
        n = 0
        if os.path.isfile(ok):
            with open(ok, encoding="utf-8", errors="replace") as f:
                n = sum(1 for linha in f if linha.strip())
        if doc.get("completo") and n < 100:
            print("  PISTA: a lista está marcada como completa e tem poucas linhas (%s)." % n)
            print("  O coletor pode ter parado cedo numa página pequena. Isso é pista, não prova.")
    except (OSError, ValueError):
        print("  estado: ilegível ou sem permissão")

disj = "/opt/mnrobo/contador_tg/cache/sigma_disjuntor"
if os.path.isfile(disj):
    try:
        ate = float(open(disj, encoding="utf-8").read().strip() or 0)
        falta = int(ate - time.time())
        if falta > 0:
            print("  pausa do Sigma: ainda faltam cerca de %s minutos" % max(1, falta // 60))
        else:
            print("  pausa do Sigma: arquivo existe, mas o horário já passou")
    except (OSError, ValueError):
        print("  pausa do Sigma: arquivo existe e não deu para ler o horário")

hoje = time.strftime("%Y-%m-%d")
dia = f"/opt/mnrobo/contador_tg/cache/{hoje}.json"
if os.path.isfile(dia):
    try:
        bloco = json.load(open(dia, encoding="utf-8")).get("bloco") or {}
        print("  resumo de hoje: sigma_ok=%s vendas_novas=%s testes_criados=%s" % (
            bool(bloco.get("sigma_ok")), bloco.get("vendas_novas"), bloco.get("testes_criados")))
        if not bloco.get("sigma_ok"):
            print("  o resumo do dia NÃO marcou a lista como pronta (é isso que deixava o cartão em 'sem dado')")
    except (OSError, ValueError):
        print("  resumo de hoje: ilegível ou sem permissão")
else:
    print(f"  resumo de hoje ausente: {dia}")
PY
echo

echo "== 4. A chave de acesso existe? (o valor não é mostrado) =="
for f in /etc/mnrobo.env /etc/mnrobo-box.env /etc/mnrobo-mp.env /etc/mnrobo-espelho2.env; do
  if [[ ! -e "$f" ]]; then
    echo "  ausente: $f"
    continue
  fi
  if [[ ! -r "$f" ]]; then
    echo "  sem permissão de leitura: $f"
    continue
  fi
  if grep -Eq '^[[:space:]]*(export[[:space:]]+)?SIGMA_API_TOKEN=.+' "$f"; then
    echo "  SIGMA_API_TOKEN presente em $f (valor escondido)"
  else
    echo "  SIGMA_API_TOKEN AUSENTE em $f"
  fi
  if grep -Eq '^[[:space:]]*(export[[:space:]]+)?SIGMA_PROMO_TOKEN=.+' "$f"; then
    echo "  SIGMA_PROMO_TOKEN presente em $f (valor escondido)"
  else
    echo "  SIGMA_PROMO_TOKEN ausente em $f"
  fi
done
echo "  não usei 'systemctl show Environment' porque isso imprimiria a chave"
echo

echo "== 5. Arquivos do contador gravados por root nos últimos 14 dias =="
DIRS=(/opt/mnrobo/contador_tg /opt/mnrobo/atendimento/contador /workspace/atendimento/contador)
achou=0
for d in "${DIRS[@]}"; do
  [[ -d "$d" ]] || continue
  while IFS= read -r linha; do
    [[ -n "$linha" ]] || continue
    echo "  $linha"
    achou=1
  done < <(find "$d" -user root -mtime -14 -printf '%TY-%Tm-%Td %TH:%TM %u %m %s %p\n' 2>/dev/null | head -n 80)
done
if [[ "$achou" == 0 ]]; then
  echo "  nenhum arquivo de root modificado nesse prazo (ou sem permissão para listar)"
else
  marca "tem arquivo do contador com dono root modificado recentemente"
fi
echo

echo "== 6. Timers do sistema =="
if command -v systemctl >/dev/null 2>&1; then
  systemctl list-timers --all --no-pager 2>/dev/null | redact || echo "  systemctl list-timers falhou"
else
  echo "  sem systemctl"
fi
echo

echo "== 7. Crontab de root e /etc/cron =="
if [[ "$(id -u)" -eq 0 ]]; then
  crontab -l 2>/dev/null | redact || echo "  crontab de root vazia"
else
  sudo -n crontab -l 2>/dev/null | redact || echo "  não deu para ler a crontab de root sem senha"
fi
grep -R -n -i -E 'contador|sigma_rows|mnrobo-contador' /etc/crontab /etc/cron.d /etc/cron.daily /etc/cron.hourly /etc/cron.weekly 2>/dev/null | redact || echo "  nada em /etc/cron citando o contador"
echo

echo "== 8. Serviços e scripts que citam o contador =="
if command -v systemctl >/dev/null 2>&1; then
  systemctl list-units --all --no-pager --plain 2>/dev/null | grep -Ei 'contador|mnbox-vigia|mnbox-telegram|mnrobo|painel-gxtv' || echo "  nenhum unit com esses nomes na lista"
  echo
  for u in mnrobo-contador mnrobo-contador.timer mnbox-vigia mnbox-telegram painel-gxtv; do
    echo "-- $u --"
    if systemctl cat "$u" >/dev/null 2>&1; then
      systemctl cat "$u" 2>/dev/null | grep -E '^(#|\[|User=|Group=|ExecStart=|EnvironmentFile=|Description=)' || true
      echo "  ativo: $(systemctl is-active "$u" 2>/dev/null || echo '?')"
    else
      echo "  não achei essa unidade"
    fi
  done
fi
echo "  arquivos cujo nome ou caminho cita o contador (só o caminho):"
grep -R -l -i -E 'contador_tg|mnrobo-contador' /etc/systemd/system /lib/systemd/system /usr/lib/systemd/system /usr/local/bin /usr/local/lib /opt/mnrobo 2>/dev/null | head -n 40 || true
echo

echo "== Onde parece quebrar =="
ok="/opt/mnrobo/contador_tg/cache/sigma_rows.ok.jsonl"
parc="/opt/mnrobo/contador_tg/cache/sigma_rows.parcial.jsonl"
if [[ ! -s "$ok" && -s "$parc" ]]; then
  marca "a lista completa não existe, mas a lista incompleta sim — a passada do Sigma não terminou"
fi
if [[ ! -s "$ok" && ! -s "$parc" && ! -s /opt/mnrobo/atendimento/ai/private/sigma_cache.json && ! -s /workspace/atendimento/ai/private/sigma_cache.json ]]; then
  marca "não achei nenhuma lista de clientes do Sigma com conteúdo"
fi
if [[ ${#QUEBRA[@]} -eq 0 ]]; then
  echo "  não marquei uma causa única. Leia as seções acima: dono, permissão, pausa e se a lista tem linhas."
else
  printf '  - %s\n' "${QUEBRA[@]}"
fi
echo
echo "Fim. Pode colar este texto de volta. Ele não deve conter senha."
