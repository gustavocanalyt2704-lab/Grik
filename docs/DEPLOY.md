# Publicar o painel na VPS

Os dois painéis continuam com os mesmos comandos e as mesmas portas.

- Painel da raiz: `uvicorn app.main:app --host 0.0.0.0 --port 8741` (com o certificado que o serviço já usa).
- Painel novo: `uvicorn app.main:app --host 0.0.0.0 --port 8742` (o mesmo, na pasta do v2).

O Caddy em `/etc/ponte-caddy/Caddyfile` é quem abre `https://mntv.tech`. Não coloque o IP da VPS no arquivo. Use o nome `mntv.tech`.

Não ligue `PAINEL_DEMO` nem `PAINEL_V2_SEED` na VPS. Isso é só para ver a tela com números de exemplo. Na VPS os números saem dos arquivos do robô e do Gestor.

Não apague `/var/lib/painel-gxtv` (senha, sessão, ativos). Não apague `/etc/painel-gxtv-v2.env`.

O script `painel-gxtv/deploy/rollback_painel.sh` **desinstala** o painel e apaga a pasta. Não use esse script para voltar uma versão. O volta atrás desta atualização está no fim deste texto.

## 1. Guardar o que está no ar

Na VPS, como root:

```bash
STAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p /var/backups/painel-gxtv/$STAMP
cp -a /opt/painel-gxtv /var/backups/painel-gxtv/$STAMP/painel-gxtv
cp -a /opt/painel-gxtv-v2 /var/backups/painel-gxtv/$STAMP/painel-gxtv-v2
cp -a /etc/ponte-caddy/Caddyfile /var/backups/painel-gxtv/$STAMP/Caddyfile
echo "$STAMP" > /var/backups/painel-gxtv/ULTIMO
```

Se `/opt/painel-gxtv-v2` ainda não existir, o `cp` dele falha. Siga assim mesmo para o painel da raiz e crie a pasta do v2 no passo 3.

## 2. Copiar o painel da raiz para /opt/painel-gxtv

No computador de onde sai o código (a pasta deste repositório):

```bash
rsync -a --delete \
  --exclude venv \
  --exclude __pycache__ \
  --exclude '*.pyc' \
  --exclude .git \
  painel-gxtv/ root@mntv.tech:/opt/painel-gxtv/
```

Na VPS:

```bash
cd /opt/painel-gxtv
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
chown -R mnrobo:mnrobo /opt/painel-gxtv
cp deploy/painel-gxtv.service /etc/systemd/system/painel-gxtv.service
systemctl daemon-reload
systemctl restart painel-gxtv
systemctl is-active painel-gxtv
curl -fsSk https://127.0.0.1:8741/api/ping
```

A resposta do ping tem que ter `"servico": "painel-gxtv"` e **não** pode ter `"demo": true`.

O serviço continua este comando (não troque a porta):

```text
/opt/painel-gxtv/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8741 --ssl-certfile /var/lib/painel-gxtv/cert.pem --ssl-keyfile /var/lib/painel-gxtv/key.pem
```

## 3. Copiar o painel novo para /opt/painel-gxtv-v2

No computador de origem, com a pasta `frontend/dist` já gerada (`npm ci && npm run build` dentro de `painel-gxtv-v2/frontend`):

```bash
rsync -a --delete \
  --exclude venv \
  --exclude node_modules \
  --exclude frontend/node_modules \
  --exclude __pycache__ \
  --exclude .git \
  painel-gxtv-v2/ root@mntv.tech:/opt/painel-gxtv-v2/
```

Na VPS:

```bash
cd /opt/painel-gxtv-v2
python3 -m venv venv
./venv/bin/pip install -r backend/requirements.txt
if [[ ! -f /etc/painel-gxtv-v2.env ]]; then
  cp deploy/painel-gxtv-v2.env.example /etc/painel-gxtv-v2.env
  chmod 600 /etc/painel-gxtv-v2.env
fi
# Não coloque senha neste arquivo se o login já usa
# /var/lib/painel-gxtv-v2/auth.json (cópia do hash do painel da raiz).
# Para copiar o hash uma vez, se o arquivo do v2 ainda não existe:
./venv/bin/python deploy/importar_auth_v1.py
cp deploy/painel-gxtv-v2.service /etc/systemd/system/painel-gxtv-v2.service
systemctl daemon-reload
systemctl enable painel-gxtv-v2
systemctl restart painel-gxtv-v2
systemctl is-active painel-gxtv-v2
curl -fsSk https://127.0.0.1:8742/api/v2/health
```

O serviço continua este comando:

```text
/opt/painel-gxtv-v2/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8742 --ssl-certfile /var/lib/painel-gxtv/cert.pem --ssl-keyfile /var/lib/painel-gxtv/key.pem --workers 1
```

A pasta de trabalho do serviço é `/opt/painel-gxtv-v2/backend`. A tela pronta está em `/opt/painel-gxtv-v2/frontend/dist`.

Confira que `/etc/painel-gxtv-v2.env` **não** contém `PAINEL_V2_SEED=1` nem `PAINEL_V2_DEV_AUTH=1`.

## 4. Abrir mntv.tech no Caddy que já está rodando

O Caddy atual escuta 80 e 443 e não tem bloco para `mntv.tech`. Acrescente este bloco no fim de `/etc/ponte-caddy/Caddyfile`. Não apague os blocos do ponte e do webhook.

Os painéis falam HTTPS na porta local (o certificado que eles já usam). O Caddy fala HTTPS com o visitante e ignora o certificado local, porque é a própria máquina.

```caddy
mntv.tech, www.mntv.tech {
	encode gzip
	handle /api/v2* {
		reverse_proxy https://127.0.0.1:8742 {
			transport http {
				tls_insecure_skip_verify
			}
		}
	}
	handle /v2* {
		reverse_proxy https://127.0.0.1:8742 {
			transport http {
				tls_insecure_skip_verify
			}
		}
	}
	handle {
		reverse_proxy https://127.0.0.1:8741 {
			transport http {
				tls_insecure_skip_verify
			}
		}
	}
}
```

Grave e recarregue o Caddy que já está no ar (o processo que usa `/etc/ponte-caddy/Caddyfile`, não um serviço systemd chamado caddy):

```bash
caddy validate --config /etc/ponte-caddy/Caddyfile
caddy reload --config /etc/ponte-caddy/Caddyfile
```

Se o `reload` não achar o processo, reinicie do mesmo jeito que ele sobe hoje. Não instale outro Caddy na frente.

O certificado público de `mntv.tech` o próprio Caddy pede. Não precisa de certbot.

## 5. Conferir

```bash
curl -fsSk https://127.0.0.1:8741/api/ping
curl -fsSk https://127.0.0.1:8742/api/v2/health
curl -fsS https://mntv.tech/api/ping
curl -fsS https://mntv.tech/api/v2/health
```

No navegador:

- `https://mntv.tech/` abre o login do painel da raiz.
- `https://mntv.tech/v2/login` abre o login do painel novo.
- A aba Ações mostra os botões de teste, renovar, telas, pausar e soltar.
- Não aparece a faixa amarela de demonstração.

## 6. Voltar atrás

Troque `STAMP` pelo nome que ficou em `/var/backups/painel-gxtv/ULTIMO`.

```bash
STAMP=$(cat /var/backups/painel-gxtv/ULTIMO)
systemctl stop painel-gxtv painel-gxtv-v2
rm -rf /opt/painel-gxtv /opt/painel-gxtv-v2
cp -a /var/backups/painel-gxtv/$STAMP/painel-gxtv /opt/painel-gxtv
cp -a /var/backups/painel-gxtv/$STAMP/painel-gxtv-v2 /opt/painel-gxtv-v2
cp -a /var/backups/painel-gxtv/$STAMP/Caddyfile /etc/ponte-caddy/Caddyfile
chown -R mnrobo:mnrobo /opt/painel-gxtv
systemctl start painel-gxtv
systemctl start painel-gxtv-v2
caddy reload --config /etc/ponte-caddy/Caddyfile
```

Isso devolve o código e o Caddy. Senha, sessão e arquivos em `/var/lib` não foram mexidos.

Se o v2 não existia no backup, apague só `/opt/painel-gxtv-v2`, desligue o serviço (`systemctl disable --now painel-gxtv-v2`) e tire o bloco `mntv.tech` se ele também for novo. O painel da raiz volta com o `cp` acima.
