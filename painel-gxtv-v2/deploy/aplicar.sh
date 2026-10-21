#!/usr/bin/env bash
# Aplica Painel GXTV v2 em /opt/painel-gxtv-v2 + nginx /v2.
# NÃO reinicia mnrobo. NÃO troca a raiz do painel atual.
set -euo pipefail

SRC="${1:-}"
if [[ -z "$SRC" || ! -d "$SRC" ]]; then
  echo "uso: aplicar.sh /caminho/para/painel_gxtv_v2" >&2
  exit 2
fi

DEST=/opt/painel-gxtv-v2
STAMP=$(date +%Y%m%d_%H%M%S)
BAK="/var/backups/painel-gxtv-v2/${STAMP}"

echo "[v2] destino $DEST"
mkdir -p /var/backups/painel-gxtv-v2 /var/cache/painel-gxtv-v2
if [[ -d "$DEST" ]]; then
  mkdir -p "$BAK"
  cp -a "$DEST/." "$BAK/" || true
  echo "[v2] backup $BAK"
fi

mkdir -p "$DEST"
rsync -a --delete \
  --exclude node_modules \
  --exclude frontend/node_modules \
  --exclude .git \
  --exclude venv \
  --exclude frontend/dist \
  "$SRC/" "$DEST/"

# Python venv
if [[ ! -x "$DEST/venv/bin/python" ]]; then
  python3 -m venv "$DEST/venv"
fi
"$DEST/venv/bin/pip" install -q -r "$DEST/backend/requirements.txt"

# Front build (precisa node na VPS; se falhar, use dist pré-buildado do pack)
if [[ -d "$SRC/frontend/dist" ]]; then
  mkdir -p "$DEST/frontend/dist"
  rsync -a "$SRC/frontend/dist/" "$DEST/frontend/dist/"
elif command -v npm >/dev/null 2>&1; then
  (cd "$DEST/frontend" && npm ci && npm run build)
else
  echo "[v2] AVISO: sem dist/ e sem npm — UI ficará 503 até build" >&2
fi

# Env
if [[ ! -f /etc/painel-gxtv-v2.env ]]; then
  cp "$DEST/deploy/painel-gxtv-v2.env.example" /etc/painel-gxtv-v2.env
  chmod 600 /etc/painel-gxtv-v2.env
  echo "[v2] crie senha em /etc/painel-gxtv-v2.env (PAINEL_PASSWORD ou SHA256)"
fi

# Systemd
cp "$DEST/deploy/painel-gxtv-v2.service" /etc/systemd/system/painel-gxtv-v2.service
systemctl daemon-reload
systemctl enable painel-gxtv-v2
systemctl restart painel-gxtv-v2

# Nginx snippet — só se ainda não houver location /v2
NGINX_MAIN=""
for c in /etc/nginx/sites-enabled/* /etc/nginx/conf.d/*; do
  [[ -f "$c" ]] || continue
  if grep -q 'painel\|gxtv\|8787\|proxy_pass' "$c" 2>/dev/null; then
    NGINX_MAIN="$c"
    break
  fi
done

SNIP=/etc/nginx/snippets/painel-gxtv-v2.conf
mkdir -p /etc/nginx/snippets 2>/dev/null || true
if [[ -d /etc/nginx/snippets ]]; then
  cp "$DEST/deploy/nginx-v2.conf.snippet" "$SNIP" || true
fi
if [[ -n "$NGINX_MAIN" ]] && ! grep -q 'painel-gxtv-v2.conf' "$NGINX_MAIN"; then
  echo "[v2] adicione manualmente: include $SNIP;  em $NGINX_MAIN"
  echo "[v2] (não edito nginx automaticamente para não quebrar o painel atual)"
fi

# Login próprio: copia o hash do v1 uma vez. Não altera /var/lib/painel-gxtv/auth.json.
mkdir -p /var/lib/painel-gxtv-v2
if [[ ! -s /var/lib/painel-gxtv-v2/auth.json ]]; then
  "$DEST/venv/bin/python" "$DEST/deploy/importar_auth_v1.py" || echo "[v2] auth próprio ainda vazio — login avisa na tela"
fi
chmod 600 /var/lib/painel-gxtv-v2/auth.json 2>/dev/null || true

systemctl is-active painel-gxtv-v2
curl -skS -o /dev/null -w "health_tls:%{http_code}\n" https://127.0.0.1:8742/api/v2/health || true
curl -sS -o /dev/null -w "health_http:%{http_code}\n" http://127.0.0.1:8787/api/v2/health || true
echo "[v2] OK — UI em https://<host>:8742/v2 (TLS; login = mesmo gustavo do painel atual)"
echo "[v2] painel atual (:8741) intocado"
