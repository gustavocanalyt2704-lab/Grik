#!/bin/bash
# Sobe o painel, entra e confere o ao vivo e cada bloco.
set -euo pipefail

systemctl start painel-gxtv
PORTA="8741"
if [[ -f /var/lib/painel-gxtv/porta ]]; then
  PORTA="$(tr -cd '0-9' < /var/lib/painel-gxtv/porta)"
fi
BASE="https://127.0.0.1:${PORTA}"

pronto=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsSk "$BASE/api/ping" >/dev/null 2>&1; then
    pronto=1
    break
  fi
  sleep 1
done
if [[ "$pronto" != 1 ]]; then
  echo "ERROR o painel não respondeu em $BASE" >&2
  exit 1
fi

/opt/painel-gxtv/venv/bin/python - "$BASE" << 'PY'
import json, pathlib, re, ssl, sys, urllib.request

base = sys.argv[1]
senha = pathlib.Path("/root/painel-gxtv-senha.txt").read_text(encoding="utf-8").strip()
ctx = ssl._create_unverified_context()
jar = {}

class GuardarCookie(urllib.request.BaseHandler):
    def http_response(self, request, response):
        cookie = response.headers.get("Set-Cookie", "")
        if "painel_sessao=" in cookie:
            jar["token"] = cookie.split("painel_sessao=", 1)[1].split(";", 1)[0]
        return response
    https_response = http_response

opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), GuardarCookie())
corpo = json.dumps({"usuario": "gustavo", "senha": senha}).encode()
opener.open(urllib.request.Request(base + "/api/entrar", data=corpo, headers={"Content-Type": "application/json"}), timeout=20).read()
if "token" not in jar:
    raise SystemExit("ERROR sem cookie de sessão")
cookie = {"Cookie": "painel_sessao=" + jar["token"]}
fluxo = opener.open(urllib.request.Request(base + "/api/stream", headers={**cookie, "Accept": "text/event-stream"}), timeout=20)
pedaco = fluxo.read(1200)
fluxo.close()
if b"snapshot" not in pedaco:
    raise SystemExit("ERROR sse sem snapshot")
estado = json.loads(opener.open(urllib.request.Request(base + "/api/estado", headers=cookie), timeout=30).read())["estado"]
for nome in ("dinheiro", "vendas", "clientes", "chats", "atendimento", "qualidade", "saude", "rotinas"):
    bloco = estado["blocos"][nome]
    if bloco["sem_dado"] and "sem dado" not in bloco["resumo"]:
        raise SystemExit(f"ERROR bloco {nome} sem explicação")
    if not bloco["sem_dado"] and not bloco["resumo"]:
        raise SystemExit(f"ERROR bloco {nome} vazio")
if re.search(r"(?<!\d)\d{10,13}(?!\d)", json.dumps(estado)):
    raise SystemExit("ERROR telefone completo no estado")

from datetime import datetime
from zoneinfo import ZoneInfo

momento = datetime.fromisoformat(estado["hora"])
fuso = ZoneInfo("America/Bahia")
if momento.tzinfo is None:
    momento = momento.replace(tzinfo=fuso)
dia = momento.astimezone(fuso).date().isoformat()
arquivo = pathlib.Path("/opt/mnrobo/contador_tg/cache") / f"{dia}.json"
try:
    oficial = json.loads(arquivo.read_text(encoding="utf-8"))
except OSError as exc:
    raise SystemExit(f"ERROR cache do dia ilegível: {exc}")
bloco = oficial.get("bloco") if isinstance(oficial, dict) else None
if not isinstance(bloco, dict) or bloco.get("mp_reais") is None:
    raise SystemExit("ERROR cache do /contagem sem bloco.mp_reais")
visto = estado["destaques"]["dinheiro"].get("v")
mp = float(bloco["mp_reais"])
if visto is None or abs(float(visto) - mp) > 0.009:
    raise SystemExit(f"ERROR dinheiro do painel {visto} != cache {mp}")
fora = bloco.get("mp_fora_reais")
if fora not in (None, 0) and abs(float(visto) - (mp + float(fora))) <= 0.009:
    raise SystemExit("ERROR dinheiro inclui movimentação própria")
gaveta = estado["gavetas"]["dinheiro"]
if bloco.get("renovado_n") is None or bloco.get("renovado_reais") is None:
    raise SystemExit("ERROR cache do /contagem sem renovação")
if gaveta.get("renov_qtd") != int(bloco["renovado_n"]) or abs(float(gaveta.get("renov_valor") or -1) - float(bloco["renovado_reais"])) > 0.009:
    raise SystemExit(f"ERROR renovação do painel {gaveta.get('renov_qtd')} {gaveta.get('renov_valor')} != cache {bloco.get('renovado_n')} {bloco.get('renovado_reais')}")
gerado = oficial.get("gerado_em")
if isinstance(gerado, str):
    try:
        instante = datetime.fromisoformat(gerado.replace("Z", "+00:00"))
        if instante.tzinfo is None:
            instante = instante.replace(tzinfo=fuso)
        if (momento - instante.astimezone(fuso)).total_seconds() > 600:
            frase = estado["destaques"]["dinheiro"].get("frase") or ""
            if "atualizado há" not in frase:
                raise SystemExit("ERROR cache velho sem o aviso de atualização")
    except ValueError:
        pass
print("OK login, sse e blocos")
PY
