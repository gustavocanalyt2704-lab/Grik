#!/bin/bash
# Instala o Painel GXTV v6.
# --dry-run só mostra o que faria.
# Faz backup do painel atual. Não troca a senha se ela já existe.
# Não reinicia o robô, não mexe no bot e não para o aviso do Telegram.
set -euo pipefail

DRY=0
for arg in "$@"; do
  if [[ "$arg" == "--dry-run" ]]; then
    DRY=1
  fi
done

AQUI="$(cd "$(dirname "$0")" && pwd)"
TGZ="$AQUI/painel_v6.tgz"
DESTINO="/opt/painel-gxtv"
PORTA="${PAINEL_PORT:-8741}"
IP="179.236.239.192"
BKP_RAIZ="/var/backups/painel-gxtv"

if [[ "$DRY" == 1 ]]; then
  echo "dry-run: não vou alterar nada"
  if [[ -f "$TGZ" ]]; then
    echo "pacote encontrado: $TGZ"
  else
    echo "ATENÇÃO: não achei $TGZ — a instalação de verdade para sem esse arquivo"
  fi
  echo "1. conferir se o usuário mnrobo existe e se a porta ${PORTA} está livre"
  echo "2. backup de ${DESTINO} e da unidade painel-gxtv em ${BKP_RAIZ}/<data>/"
  echo "   o backup não inclui a senha nem a pasta /var/lib/painel-gxtv"
  echo "3. gravar o caminho do backup em ${BKP_RAIZ}/ULTIMO"
  echo "4. trocar o código em ${DESTINO} e instalar as bibliotecas"
  echo "5. manter a senha se /var/lib/painel-gxtv/auth.json já existe"
  echo "6. atualizar só o serviço painel-gxtv e reiniciar só ele"
  echo "não reinicia o robô"
  echo "não mexe no robô nem no telegram"
  exit 0
fi

if [[ ! -f "$TGZ" ]]; then
  echo "não achei $TGZ" >&2
  exit 1
fi
if ! id mnrobo >/dev/null 2>&1; then
  echo "o usuário mnrobo não existe nesta máquina" >&2
  exit 1
fi
if ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "(^|:)${PORTA}$"; then
  if ! systemctl is-active --quiet painel-gxtv; then
    echo "a porta ${PORTA} já está em uso" >&2
    exit 1
  fi
fi

SELO="$(date +%Y%m%d-%H%M%S)"
BKP="${BKP_RAIZ}/${SELO}"
install -d -o root -g root -m 700 "$BKP_RAIZ"
install -d -o root -g root -m 700 "$BKP"
if [[ -d "$DESTINO" ]]; then
  cp -a "$DESTINO" "$BKP/painel-gxtv"
fi
if [[ -f /etc/systemd/system/painel-gxtv.service ]]; then
  cp -a /etc/systemd/system/painel-gxtv.service "$BKP/painel-gxtv.service"
fi
echo "$BKP" > "${BKP_RAIZ}/ULTIMO"
chmod 600 "${BKP_RAIZ}/ULTIMO"
echo "backup em $BKP"

install -d -o mnrobo -g mnrobo -m 750 /var/lib/painel-gxtv
install -d -o root -g root -m 755 /usr/local/lib/painel-gxtv
rm -rf /tmp/painel-gxtv-descompacta
mkdir -p /tmp/painel-gxtv-descompacta
tar -xzf "$TGZ" -C /tmp/painel-gxtv-descompacta
rm -rf "$DESTINO"
mkdir -p "$DESTINO"
cp -a /tmp/painel-gxtv-descompacta/. "$DESTINO/"
rm -rf /tmp/painel-gxtv-descompacta
chown -R mnrobo:mnrobo "$DESTINO"

python3 -m venv "$DESTINO/venv"
"$DESTINO/venv/bin/pip" install --quiet -r "$DESTINO/requirements.txt"
chown -R mnrobo:mnrobo "$DESTINO"

if [[ ! -f /root/painel-gxtv-senha.txt || ! -f /var/lib/painel-gxtv/auth.json ]]; then
  (cd "$DESTINO" && PAINEL_AUTH_FILE=/var/lib/painel-gxtv/auth.json "$DESTINO/venv/bin/python" -m app.definir_senha /root/painel-gxtv-senha.txt)
  echo "senha nova gravada em /root/painel-gxtv-senha.txt"
else
  echo "a senha que já existia foi mantida"
fi
if [[ -f /var/lib/painel-gxtv/auth.json ]]; then
  chown mnrobo:mnrobo /var/lib/painel-gxtv/auth.json
  chmod 600 /var/lib/painel-gxtv/auth.json
fi
if [[ -f /root/painel-gxtv-senha.txt ]]; then
  chmod 600 /root/painel-gxtv-senha.txt
fi

if [[ ! -f /var/lib/painel-gxtv/cert.pem || ! -f /var/lib/painel-gxtv/key.pem ]]; then
  openssl req -x509 -newkey rsa:2048 \
    -keyout /var/lib/painel-gxtv/key.pem \
    -out /var/lib/painel-gxtv/cert.pem \
    -days 825 -nodes \
    -subj "/CN=${IP}" \
    -addext "subjectAltName=IP:${IP},IP:127.0.0.1"
fi
chown mnrobo:mnrobo /var/lib/painel-gxtv/cert.pem /var/lib/painel-gxtv/key.pem
chmod 600 /var/lib/painel-gxtv/key.pem
chmod 644 /var/lib/painel-gxtv/cert.pem

install -m 755 -o root -g root "$DESTINO/deploy/ler_rotinas.sh" /usr/local/lib/painel-gxtv/ler_rotinas.sh
cat > /etc/sudoers.d/painel-gxtv << 'EOF'
mnrobo ALL=(root) NOPASSWD: REDACTED
EOF
chmod 440 /etc/sudoers.d/painel-gxtv
visudo -cf /etc/sudoers.d/painel-gxtv >/dev/null

sed "s/8741/${PORTA}/g" "$DESTINO/deploy/painel-gxtv.service" > /etc/systemd/system/painel-gxtv.service
echo "$PORTA" > /var/lib/painel-gxtv/porta
chmod 644 /var/lib/painel-gxtv/porta /etc/systemd/system/painel-gxtv.service

if command -v ufw >/dev/null 2>&1 && ufw status | head -n 1 | grep -qi "Status: active"; then
  if ! ufw status | grep -q "${PORTA}/tcp"; then
    ufw allow "${PORTA}/tcp" comment 'painel-gxtv'
    echo "$PORTA" > /var/lib/painel-gxtv/ufw_porta
  fi
fi

systemctl daemon-reload
systemctl enable painel-gxtv >/dev/null
systemctl restart painel-gxtv
echo "painel no ar em https://${IP}:${PORTA}"
echo "para voltar atrás: bash ${DESTINO}/deploy/rollback_painel_v6.sh"
