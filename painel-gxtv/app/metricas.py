"""Métricas do Contador antigo ("Painel de atendimento"), recalculadas do espelho.

O Contador antigo (atendimento/contador/painel.py) lia a API do DataCrazy (só as 20 últimas
mensagens por conversa). O espelho (espelho.mensagens) é a cópia completa dessas mesmas
conversas, então aqui as mesmas regras rodam sobre o espelho, com histórico inteiro.
Só leitura. Telefone nunca sai daqui: cada conversa vira um registro sem telefone.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
import threading
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from app.logonce import avisar
from app.tempo import TZ

_CONVS_ANTIGO = "/opt/mnrobo/atendimento/contador/painel_cache/convs.json"
_TESTES_SIGMA = "/opt/mnrobo/atendimento/ai/private/r639z_testes_sigma.json"

K = re.compile
# --- mesmas regras do painel.py antigo -------------------------------------------------
RE_VENDA = K(r'quanto (custa|e |é |fica|ta |tá )|qual (o |e o |é o )?(valor|preco)|\bprecos?\b|\bvalores\b|quero (assinar|contratar|comprar|adquirir)|'
             r'como (faco|faço|funciona) (pra|para) (ter|assinar|contratar|comprar)|\bteste gratis\b|tem teste|quero testar|liberar um teste|\bplanos\b|tabela')
RE_RENOV = K(r'renova|quero renovar|\bvenc(eu|ido|ida|e|imento)\b|\bpix\b|comprovante|paguei|\bpago\b|pagamento|chave pix|sim, quero renovar')
RE_CANCEL = K(r'cancel|nao quero mais|nao vou (mais )?(renovar|continuar)|estorn|reembols|devolu|devolve|dinheiro de volta|desist')
RE_REVERT = K(r'vou continuar|vou ficar|pode manter|deixa ativo|desisti de cancelar|nao precisa cancelar|quero continuar')
CATS = {
    'Login e dados': K(r'senha|usuario|login|\blogar\b|dados de acesso|\binvalid|incorret|nao (entra|aceita)|code|codigo'),
    'Instalação': K(r'instal|baixar|baixei|download|nao (acho|encontro) o app|loja de app|play ?store|app store|onde (acho|baixo)'),
    'Travamento': K(r'trava|travando|congel|buffer|carregando|lento|lentidao|caindo|\bcai\b|engasg|pausando'),
    'App com erro': K(r'\berro\b|nao abre|fecha sozinho|tela preta|nao (funciona|funcionou|carrega)|parou de funcionar|\bbug'),
    'Canais e conteúdo': K(r'\bcana(l|is)\b|filme|serie|futebol|jogo|sem sinal|fora do ar|nao (pega|passa)|lista'),
    'Pagamento': K(r'\bpix\b|paguei|comprovante|pagamento|boleto|cobran'),
}
DEVS = {
    'Samsung': K(r'samsung|tizen'), 'LG': K(r'\blg\b|webos'), 'Roku': K(r'roku'),
    'Android TV / TV Box': K(r'android tv|google tv|tv ?box|\bbox\b|mi box|xiaomi'), 'Fire Stick': K(r'fire ?stick|fire ?tv|amazon'),
    'Celular': K(r'celular|iphone|\bios\b|telefone'), 'TCL': K(r'\btcl\b'), 'Philco': K(r'philco'), 'AOC': K(r'\baoc\b'),
    'Semp': K(r'semp'), 'HQ': K(r'\bhq\b'), 'Computador': K(r'computador|notebook|\bpc\b'),
}
APPS = {
    'XCIPTV': K(r'xc ?iptv'), 'XP IPTV': K(r'xp ?iptv'), 'UTRA PLUS': K(r'\b[ou]?u?tra ?plus|\bultra ?plus|\butra\b'),
    'Brasil IPTV': K(r'brasil ?iptv'), 'Max Player': K(r'max ?player'), 'Fun Play': K(r'fun ?play'), 'IBO Player': K(r'\bibo\b|ibo ?player'),
    'IPTV Smarters': K(r'smarters'), 'Smart STB': K(r'smart ?stb|\bstb\b'), 'MN TECH': K(r'\bmn ?tech\b'), 'Flex Player': K(r'flex ?player'),
}
RE_ACK = K(r'^(ok|okay|okk+|blz|beleza|ta bom|ta|tá|certo|sim|show|top|valeu|vlw|obrigad\w*|obg|grat[oa]|ok obrigad\w*|tudo certo|combinado|'
           r'entendi|ah ta|ata|joia|perfeito|ok vou \w+|ta otimo|otimo|ok valeu|blz obrigad\w*)$')
SAUD = K(r'^(oi|ola|bom dia|boa tarde|boa noite|ok|blz|beleza|sim|nao|obrigad\w*|valeu|👍)\W*$')
RE_CURTA = K(r'^(sim|s|ss|isso|ok+|okay|okk+|obg\w*|obgd\w*|brigad\w*|obrigad\w*|foi|foi sim|deu|deu sim|sim deu|certo|blz|beleza|'
             r'ta bom|ta|show|top|valeu|vlw|joia|perfeito|combinado|entendi|ok obg\w*|ok obrigad\w*|sim obrigad\w*|ok valeu|blz obg\w*|'
             r'ta otimo|otimo|tudo certo|certinho|ok certo|show obrigad\w*|consegui|funcionou)( \w+)?$')
RE_EMOJI_OK = re.compile(r'^[\s👍🙏👌✅🙌😊😁🤝❤️♥️]+$')
RE_PASSO_FINAL = K(r'funcion|conseguiu|deu certo|renovad|confirmad|vencimento|usuario|senha|\bcode\b|codigo|pronto|liberad|ativad|ativei|'
                   r'tenta|reinici|segue|instal|baix|atualiz|sincroniz|qualquer (coisa|duvida)|estamos a disposicao|disponha')
RE_PASSO_NEG = K(r'infelizmente|nao (funciona|tem como|conseguimos|e possivel)|aguarde|vou verificar|vou conferir|ja (te )?retorno')
# instalação/credencial: mesmo critério do automacoes/feedback.py
RE_INST = K(r'instal|baix')
RE_CRED_U = K(r'usuari')
RE_CRED_S = K(r'\bsenha\b')

# app usado (histórico inteiro): só mensagem que cita UM app só; vale a menção mais recente
APP_HIST = (
    ('UTRA PLUS', K(r'\b(?:utra|ultra) ?plus\b|\butra\b')),
    ('XCIPTV', K(r'\bxc ?iptv\b')),
    ('Brasil IPTV', K(r'\bbrasil ?iptv\b')),
    ('Max Player', K(r'\bmax ?player\b')),
    ('MN TECH', K(r'\bmn ?tech\b')),
    ('Fun Play', K(r'\bfun ?play\b')),
    ('Flex Player', K(r'\bflex ?player\b')),
    ('XP IPTV', K(r'\bxp ?iptv\b')),
    ('IPTV Smarters', K(r'\bsmarters\b')),
    ('Smart STB', K(r'\bsmart ?stb\b')),
    ('IBO Player', K(r'\bibo ?(?:player|pro)\b|\biboplayer\b')),
)
DEV_HIST = (
    ('LG', K(r'\blg\b|webos')), ('Samsung', K(r'samsung|tizen')), ('Roku', K(r'\broku\b')),
    ('Fire Stick', K(r'fire ?stick|fire ?tv')), ('TV Box', K(r'tv ?box|mi box|\bmxq\b')), ('Android TV', K(r'android tv|google tv')),
    ('TCL', K(r'\btcl\b')), ('Philco', K(r'philco')), ('AOC', K(r'\baoc\b')), ('Semp', K(r'\bsemp\b')),
    ('Celular', K(r'\bcelular\b|iphone|smartphone')), ('Computador', K(r'computador|notebook')),
)
PREFILTRO = (r"utra|ultra ?plus|brasil ?iptv|xc ?iptv|max ?player|mn ?tech|fun ?play|flex ?player|xp ?iptv|smarters|smart ?stb|ibo ?player|ibo ?pro|iboplayer"
             r"|\ylg\y|webos|samsung|tizen|roku|fire ?stick|fire ?tv|tv ?box|mi box|mxq|android tv|google tv|\ytcl\y|philco|\yaoc\y|\ysemp\y|celular|iphone|smartphone|computador|notebook")

def _devolver_memoria():
    try:
        import ctypes

        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except (OSError, AttributeError):
        pass


# norm() e agradeceu(): cópia fiel de atendimento/contador/numeros.py (o painel não carrega código de fora).
_RE_NEG = re.compile(r'\bnao\s+(?:\w+\s+)?(?:funcion\w*|deu\s+certo|consegu\w*|pegou|pega|abriu|abre|deu|resolv\w*)')
_RE_OK = re.compile(r'obrigad|\bvaleu\b|\bvlw\b|funcionou|deu certo|\bconsegui\b|\bpegou\b|\babriu\b|\bja deu\b|perfeito|\bshow\b|\btop\b|resolvido|\bgrat[oa]\b')


def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', s.lower())


def agradeceu(texto):
    t = norm(texto)
    return bool(_RE_OK.search(_RE_NEG.sub(' ', t)))


def tel8(v):
    d = re.sub(r"\D", "", str(v or ""))
    return d[-8:] if len(d) >= 8 else ""


def precisa_resp(m):
    b = m["body"]
    if not b.strip():
        return bool(m["att"])
    t = re.sub(r'\s+', ' ', re.sub(r'[^\w ]+', ' ', norm(b))).strip()
    if not t:
        return False
    if len(t) <= 30 and RE_ACK.match(t):
        return False
    if '?' not in b and len(t) <= 60 and agradeceu(b):
        return False
    return True


def curta_ok(m):
    b = m["body"].strip()
    if not b:
        return False
    if RE_EMOJI_OK.match(b):
        return True
    t = re.sub(r'\s+', ' ', re.sub(r'[^\w ]+', ' ', norm(b))).strip()
    return bool(t) and len(t) <= 30 and bool(RE_CURTA.match(t))


def _limpa_inst(nome):
    # MAPA_INSTANCIAS_P6_1102 — telefone/id sem nome no DataCrazy (ex.: 5511936235903 = COBRANÇA P6)
    try:
        from app.mapa_instancias import rotulo_mapeado
        mapped = rotulo_mapeado(nome)
        if mapped:
            return mapped
    except Exception:
        pass
    s = re.sub(r"[^\w\s/+-]", " ", str(nome or ""), flags=re.UNICODE)
    s = re.sub(r"_", " ", s)
    s = " ".join(s.split()).upper()
    if not s:
        return None
    if re.fullmatch(r"\d{4}", s):
        return f"Final {s}"
    if re.fullmatch(r"\d{8,}", s):
        return f"Final {s[-4:]}"
    return s.replace("COBRANCA", "COBRANÇA")


def _inst_de(registro: dict) -> str | None:
    try:
        from app.mapa_instancias import rotulo_mapeado
        payload = registro.get("payload") if isinstance(registro.get("payload"), dict) else {}
        inst = (
            registro.get("instancia")
            or registro.get("instance")
            or registro.get("numero_whatsapp")
            or registro.get("whatsapp_instancia")
            or payload.get("instancia")
            or payload.get("instance")
        )
        mapped = rotulo_mapeado(
            inst,
            phone=registro.get("numero_whatsapp") or registro.get("instance_phone"),
            evento=registro.get("evento") or payload.get("evento"),
            instance_id=registro.get("instance_id") or registro.get("instanceId") or payload.get("instanceId"),
        )
        if mapped:
            return mapped
    except Exception:
        pass
    for chave in ("instancia", "numero_whatsapp", "whatsapp_instancia", "instance"):
        nome = _limpa_inst(registro.get(chave))
        if nome:
            return nome
    return None


_MARCAS_INST = (b'"instancia"', b'"numero_whatsapp"', b'"whatsapp_instancia"', b'"instance"')
_TAGS = {
    "ia_garante_escalado": "esc", "ia_escalar": "esc", "ia_router_venda_preco": "venda",
    "renovacao_pix": "pix", "audio_lead_teste": "teste",
}


class Instancias:
    """Lê o acoes.jsonl do robô aos poucos: conversa -> número (instância) e marcas do dia
    (robô pediu humano, pediu preço, renovação pelo Pix do robô). Também usa a lista do Contador antigo."""

    def __init__(self, acoes: Path):
        self.acoes = acoes
        self.mapa: dict[str, str] = {}
        self.marcas: dict[str, dict[str, set]] = {v: {} for v in set(_TAGS.values())}
        self.offset = 0
        self.inode = None
        self._antigo = False

    def marcado(self, tag: str, cid: str, dia: str) -> bool:
        return dia in self.marcas.get(tag, {}).get(cid, ())

    def atualizar(self):
        if not self._antigo:
            self._antigo = True
            try:
                for c in json.load(open(_CONVS_ANTIGO, encoding="utf-8")).get("convs") or []:
                    nome = _limpa_inst(c.get("instance"))
                    if nome and c.get("id"):
                        self.mapa.setdefault(c["id"], nome)
            except (OSError, ValueError):
                pass
        try:
            st = self.acoes.stat()
            if self.inode != (st.st_dev, st.st_ino) or st.st_size < self.offset:
                self.offset, self.inode = max(0, st.st_size - 60_000_000), (st.st_dev, st.st_ino)
            with self.acoes.open("rb") as f:
                f.seek(self.offset)
                if self.offset:
                    f.readline()
                for linha in f:
                    tem_inst = any(marca in linha for marca in _MARCAS_INST)
                    tag = None
                    if not tem_inst:
                        for chave in _TAGS:
                            if chave.encode() in linha:
                                tag = chave
                                break
                        if tag is None:
                            continue
                    try:
                        a = json.loads(linha)
                    except ValueError:
                        continue
                    cid = str(a.get("conversa") or "")
                    if not cid:
                        continue
                    nome = _inst_de(a)
                    if nome:
                        self.mapa[cid] = nome
                    marca = _TAGS.get(str(a.get("tipo") or ""))
                    if marca:
                        dia = str(a.get("ts") or "")[:10]
                        self.marcas[marca].setdefault(cid, set()).add(dia)
                self.offset = f.tell()
        except OSError as exc:
            avisar("inst-acoes", "sem acesso a %s: %s", self.acoes, exc)
        self._atualizar_webhook()  # MAPA_INSTANCIAS_P6_1102

    def _atualizar_webhook(self):
        """Fila magra: evento msg_p6cob / telefone da instância → mesmo rótulo do card."""
        fila = Path(os.environ.get("WEBHOOK_QUEUE") or "/opt/mnrobo/atendimento/webhook/queue.jsonl")
        if not fila.is_file():
            return
        try:
            from app.mapa_instancias import rotulo_mapeado
        except Exception:
            rotulo_mapeado = None
        try:
            st = fila.stat()
            off = getattr(self, "_wh_offset", None)
            inode = getattr(self, "_wh_inode", None)
            if inode != (st.st_dev, st.st_ino) or st.st_size < (off or 0):
                off, inode = max(0, st.st_size - 12_000_000), (st.st_dev, st.st_ino)
            with fila.open("rb") as f:
                f.seek(off or 0)
                if off:
                    f.readline()
                for linha in f:
                    if b'"conversa"' not in linha and b'"conversationId"' not in linha:
                        continue
                    try:
                        a = json.loads(linha)
                    except ValueError:
                        continue
                    payload = a.get("payload") if isinstance(a.get("payload"), dict) else a
                    cid = str(payload.get("conversa") or payload.get("conversationId") or a.get("conversa") or "")
                    if not cid:
                        continue
                    nome = _inst_de(payload) or _inst_de(a)
                    if not nome and rotulo_mapeado:
                        nome = rotulo_mapeado(
                            payload.get("instancia") or payload.get("instance"),
                            evento=payload.get("evento") or a.get("evento"),
                            instance_id=payload.get("instanceId") or payload.get("instance_id"),
                            phone=payload.get("instance_phone") or payload.get("wid"),
                        )
                    if nome:
                        self.mapa[cid] = nome
                self._wh_offset = f.tell()
                self._wh_inode = inode
        except OSError as exc:
            avisar("inst-webhook", "sem acesso a %s: %s", fila, exc)


def renov_do_dia(contador_cache: Path, dia: str) -> dict:
    """tel8 -> origem das renovações conferidas pelo /contagem nesse dia (telefone só para casar)."""
    try:
        doc = json.load(open(contador_cache / f"{dia}.json", encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    saida = {}
    for rec in ((doc.get("bloco") or {}).get("renovs") or {}).values():
        if isinstance(rec, dict) and tel8(rec.get("telefone")):
            saida[tel8(rec["telefone"])] = str(rec.get("origem") or "conferida")
    return saida


def _testes_hoje(inicio: datetime, fim: datetime) -> set:
    """Conversas com teste criado no Sigma pelo robô (r639z_testes_sigma.json: ts + cid)."""
    try:
        dado = json.load(open(_TESTES_SIGMA, encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    cids = set()
    for v in (dado.values() if isinstance(dado, dict) else []):
        if not isinstance(v, dict):
            continue
        try:
            quando = datetime.fromtimestamp(float(v.get("ts")), TZ)
        except (TypeError, ValueError):
            continue
        if inicio <= quando <= fim and v.get("cid"):
            cids.add(str(v["cid"]))
    return cids


# Não varre espelho.mensagens por ts_origem: essa coluna não tem índice sozinha
# (474 mil linhas) e o painel corta a consulta em 15s. Aí a aba ficava em
# "ainda calculando" / "sem dado" e, quando algo passava, não eram todos os chats.
# O dia sai de espelho.conversas.ultima_msg_ts. Quem continuou falando depois
# do fim da janela entra em lotes pelo índice (cid, ts_origem). Nunca chama a API DataCrazy.
_SQL_CIDS = """
SELECT cid FROM espelho.conversas
WHERE ultima_msg_ts >= %(ini)s AND ultima_msg_ts <= %(fim)s
"""
_SQL_EXISTE_DEPOIS = """
SELECT c.cid
FROM espelho.conversas c
WHERE c.ultima_msg_ts > %(fim)s
  AND EXISTS (
    SELECT 1 FROM espelho.mensagens m
    WHERE m.cid = c.cid
      AND m.ts_origem >= %(ini)s AND m.ts_origem <= %(fim)s
      AND coalesce(m.deletado, false) = false
      AND coalesce(m.interno, false) = false
  )
"""
_LOTE = 12
_SQL_CIDS_NOVOS = """
SELECT cid FROM espelho.conversas
WHERE ultima_msg_ts > %(desde)s AND ultima_msg_ts <= %(fim)s
"""
_SQL_JANELA = """
SELECT m.cid, m.direcao, coalesce(m.autor_tipo, '') AS autor_tipo, coalesce(m.autor_nome, '') AS autor_nome, m.ts_origem,
       left(coalesce(m.conteudo_texto, ''), 400) AS body, (m.midia IS NOT NULL) AS att, left(coalesce(m.midia_texto, ''), 200) AS ic
FROM espelho.mensagens m
WHERE m.cid = ANY(%(cids)s)
  AND m.ts_origem >= %(antes)s AND m.ts_origem <= %(fim)s
  AND coalesce(m.deletado, false) = false AND coalesce(m.interno, false) = false
ORDER BY m.cid, m.ts_origem
"""
_SQL_CONVS = "SELECT cid, telefone, conv_criada_em FROM espelho.conversas WHERE cid = ANY(%(cids)s)"
def _em_lotes(cids, tamanho, fn):
    """fn(lote) devolve uma lista, ou None se a leitura daquele lote falhou.

    Um lote que estoura o tempo é refeito menor. O que ainda falhar fica de fora
    e é contado — o resto do dia não é descartado.
    """
    saida = []
    falhas = 0
    i = 0
    passo = max(1, tamanho)
    while i < len(cids):
        fatia = cids[i:i + passo]
        parte = fn(fatia)
        if parte is None:
            if passo > 1:
                passo = max(1, passo // 2)
                continue
            parte = fn(fatia)
            if parte is None:
                falhas += len(fatia)
                i += len(fatia)
                passo = max(1, tamanho)
                continue
        saida.extend(parte)
        i += len(fatia)
        passo = max(1, tamanho)
    return saida, falhas


def _ids_da_janela(banco, D: datetime, A: datetime, agora: datetime | None = None):
    """Todos os cids com mensagem na janela. None se a lista do dia não veio."""
    agora = agora or datetime.now(TZ)
    lista = banco.linhas(_SQL_CIDS, {"ini": D, "fim": A})
    if lista is None:
        return None, {"falhas": 1, "complemento": None}
    ids = [r["cid"] for r in lista]
    if A >= agora - timedelta(minutes=3):
        return ids, {"falhas": 0, "complemento": None}
    # Não procura quem continuou falando depois do fim da janela.
    # Essa consulta (EXISTS em mensagens) não usa índice sozinho, estoura o tempo
    # e trava a conexão. A comparação fica com quem teve a última mensagem no horário.
    return ids, {
        "falhas": 0,
        "complemento": "comparação sem quem falou nesse horário e voltou a falar depois",
    }


def _who(m):
    if m["direcao"] == "entrada":
        return "cli"
    tipo = m["autor_tipo"]
    # ROBO_WEBHOOK_0810: desde 08/10 00:42 o robô manda pelo fluxo do DataCrazy e a mensagem chega no
    # espelho como autor_tipo=sistema "IA GXTV — retorno (webhook) ...". É o robô, não aviso automático.
    if tipo == "sistema" and str(m.get("autor_nome") or "").startswith("IA GXTV"):
        return "b:Robô"
    if tipo == "sistema":
        return "template"
    if tipo == "equipe":
        nome = " ".join((m["autor_nome"] or "").replace("Atendente ", "").replace("Gerente", "").split())
        return "h:" + (nome or "Equipe")
    return "b:Robô"


def _ultimo_unico(linhas, regras, tipos_ok=None):
    melhor = None
    for ln in linhas:
        if tipos_ok and ln["autor_tipo"] not in tipos_ok and ln["direcao"] != "entrada":
            continue
        texto = norm(ln["body"])
        achados = {nome for nome, rx in regras if rx.search(texto)}
        if len(achados) != 1:
            continue
        if melhor is None or ln["ts_origem"] >= melhor[0]:
            melhor = (ln["ts_origem"], achados.pop())
    return melhor[1] if melhor else None


def calcular_janela(banco, D: datetime, A: datetime, inst: Instancias, extras: dict, agora: datetime | None = None):
    """Registros por conversa na janela [D, A].

    Devolve (lista, meta). lista is None só quando a lista de conversas do dia
    não veio. meta['falhas'] é quantas conversas ficaram de fora por tempo.
    extras: tel8_renov{tel8: origem}.
    """
    todos, meta_ids = _ids_da_janela(banco, D, A, agora)
    if todos is None:
        return None, {"falhas": 1, "cids": 0, "complemento": None}
    saida, falhas = _em_lotes(todos, _LOTE, lambda lote: _janela_lote(banco, lote, D, A, inst, extras))
    return saida, {
        "falhas": falhas + int(meta_ids.get("falhas") or 0),
        "cids": len(todos),
        "complemento": meta_ids.get("complemento"),
    }


def calcular_janela_cids(banco, cids, D: datetime, A: datetime, inst: Instancias, extras: dict):
    """Recalcula só estes cids (atualização, sem varrer o dia inteiro de novo)."""
    saida, falhas = _em_lotes(list(cids), _LOTE, lambda lote: _janela_lote(banco, lote, D, A, inst, extras))
    return saida, {"falhas": falhas, "cids": len(list(cids)), "complemento": None}


def _sem_cid(regs):
    """O cid não sai na API. O id curto já é um resumo sem telefone."""
    if not regs:
        return regs
    limpo = []
    for r in regs:
        if "_cid" not in r:
            limpo.append(r)
            continue
        x = dict(r)
        x.pop("_cid", None)
        limpo.append(x)
    return limpo


def _janela_lote(banco, lote, D, A, inst, extras):
    linhas = banco.linhas(_SQL_JANELA, {"cids": lote, "fim": A, "antes": D - timedelta(hours=24)})
    if linhas is None:
        return None
    por = {}
    for ln in linhas:
        por.setdefault(ln["cid"], []).append(ln)
    del linhas
    info = {r["cid"]: r for r in (banco.linhas(_SQL_CONVS, {"cids": lote}) or [])}
    testados = _testes_hoje(D, A)
    renov = extras.get("tel8_renov") or {}
    saida = []
    for cid, todas in por.items():
        for m in todas:
            m["body"] = m["body"] or ""
            m["ic"] = m["ic"] or ""
            m["t"] = m["ts_origem"].astimezone(TZ)
            m["rec"] = m["direcao"] == "entrada"
            m["_who"] = _who(m)
        w = [m for m in todas if D <= m["t"] <= A]
        if not w:
            continue
        inb = [m for m in w if m["rec"]]
        out = [m for m in w if not m["rec"] and m["_who"] != "template"]
        tpl = [m for m in w if not m["rec"] and m["_who"] == "template"]
        c = info.get(cid) or {}
        t8 = tel8(c.get("telefone"))
        criada = c.get("conv_criada_em")
        r = {"_cid": cid, "id": hashlib.sha1(cid.encode()).hexdigest()[:8], "d": w[0]["t"].date().isoformat(),
             "n": inst.mapa.get(cid) or "sem número", "rc": bool(inb),
             "nv": bool(criada and criada.astimezone(TZ) >= D), "mc": len(inb), "ma": len(out), "mt": len(tpl)}
        txt = lambda m: norm(m["body"] + " " + m["ic"])  # noqa: E731
        nec = [m for m in inb if precisa_resp(m)]
        r["ne"] = bool(nec)
        resp = None
        r["sr"] = False
        r["t1"] = None
        r["fr"] = None
        if nec:
            t0 = nec[0]["t"]
            resp = next((m for m in w if not m["rec"] and m["_who"] != "template" and m["t"] >= t0), None)
            if resp is None:
                r["sr"] = True
            else:
                r["t1"] = int((resp["t"] - t0).total_seconds())
                r["fr"] = resp["_who"][2:]
        entre, fila = [], []
        esperando, nblk = None, 0
        for m in w:
            if m["rec"]:
                if esperando is None and precisa_resp(m):
                    esperando = m["t"]
            elif m["_who"] != "template" and esperando is not None:
                fila.append([int(esperando.timestamp() // 60), int(m["t"].timestamp() // 60)])
                if nblk > 0:
                    entre.append(int((m["t"] - esperando).total_seconds()))
                nblk += 1
                esperando = None
        r["ig"] = False
        if esperando is not None:
            # quem ficou sem retorno sai da conta da fila depois de 2 h (já aparece como "sem resposta")
            fim_fila = min(A, esperando + timedelta(hours=2))
            fila.append([int(esperando.timestamp() // 60), int(fim_fila.timestamp() // 60)])
            r["ig"] = (A - esperando).total_seconds() > 1800
        r["en"] = entre[:12]
        r["fq"] = fila[:12]
        ok = None
        for m in inb:
            if agradeceu(m["body"]) and any(not x["rec"] and x["_who"] != "template" and x["t"] < m["t"] for x in w):
                ok = m
                break
        r["re"] = 0
        r["rs"] = None
        if ok:
            r["re"] = 1
            ant = [x for x in nec if x["t"] < ok["t"]]
            if ant:
                r["rs"] = int((ok["t"] - ant[0]["t"]).total_seconds())
        elif (t8 and t8 in renov) or inst.marcado("pix", cid, w[0]["t"].date().isoformat()):
            r["re"] = 2
        elif inb:
            k = max(i for i, m in enumerate(w) if m["rec"])
            if curta_ok(w[k]):
                antes = [x for x in w[:k] if not x["rec"] and x["_who"] != "template"]
                if antes and RE_PASSO_FINAL.search(txt(antes[-1])) and not RE_PASSO_NEG.search(txt(antes[-1])):
                    r["re"] = 3
        r["ab"] = bool(not r["re"] and nec and w and not w[-1]["rec"] and resp is not None and (A - w[-1]["t"]).total_seconds() >= 3600)
        # transferências
        seq = [m["_who"] for m in out]
        hs = [s for s in seq if s.startswith("h:")]
        r["rh"] = any(seq[k].startswith("b:") and seq[k + 1].startswith("h:") for k in range(len(seq) - 1))
        r["hh"] = len(set(hs)) >= 2
        dia_w = r["d"]
        r["es"] = inst.marcado("esc", cid, dia_w)
        r["at"] = dict(Counter(s[2:] for s in seq))
        # vendas / renovação / cancelamento
        tt = " ".join(txt(m) for m in inb)
        r["vi"] = bool((RE_VENDA.search(tt) and not RE_RENOV.search(tt)) or inst.marcado("venda", cid, dia_w))
        r["vc"] = None  # venda nova concluída: depende do Sigma (sem dado hoje)
        r["rp"] = bool(RE_RENOV.search(tt) or any(m["att"] and re.search(r'comprovante|pix|pagamento|transfer', norm(m["ic"])) for m in inb))
        r["rv"] = renov.get(t8) if t8 else None
        if r["rv"] is None and inst.marcado("pix", cid, dia_w):
            r["rv"] = "pix"
        cn = 0
        tc = next((m["t"] for m in inb if RE_CANCEL.search(txt(m))), None)
        if tc is not None:
            cn = 1
            if (t8 and t8 in renov) or inst.marcado("pix", cid, w[0]["t"].date().isoformat()) or any(RE_REVERT.search(txt(m)) and m["t"] >= tc for m in inb):
                cn = 2
        r["cn"] = cn
        # problemas, aparelho, app (regra antiga: só o que o cliente escreveu no período)
        cs = Counter()
        ds, aps = set(), set()
        for m in inb:
            t_ = txt(m)
            for k2, rx in CATS.items():
                if rx.search(t_):
                    cs[k2] += 1
            for k2, rx in DEVS.items():
                if rx.search(t_):
                    ds.add(k2)
            for k2, rx in APPS.items():
                if rx.search(t_):
                    aps.add(k2)
        r["pb"] = sorted(cs)
        r["rep"] = sorted(k2 for k2, v in cs.items() if v >= 3)
        r["dv"] = sorted(ds)
        r["ap"] = sorted(aps)
        # app e aparelho: última menção de um só, nas mensagens já lidas (o dia e as 24 h anteriores).
        # O histórico inteiro da conversa exigiria varrer o texto sem índice e estourava o tempo.
        r["app"] = _ultimo_unico(todas, APP_HIST, {"robo", "equipe", ""})
        r["dev"] = _ultimo_unico(todas, DEV_HIST, {"robo", "equipe", ""})
        # instalação guiada / login enviado hoje (critério do automacoes/feedback.py)
        inst_app = None
        cred = False
        for m in out:
            t_ = m["body"]
            if RE_CRED_U.search(norm(t_)) and RE_CRED_S.search(norm(t_)):
                cred = True
            if RE_INST.search(norm(t_)):
                achado = {nome for nome, rx in APP_HIST if rx.search(norm(t_))}
                if len(achado) == 1:
                    inst_app = achado.pop()
        r["ins"] = inst_app
        r["cr"] = cred
        r["ts"] = cid in testados or inst.marcado("teste", cid, dia_w)
        r["h0"] = w[0]["t"].hour
        r["hs"] = sorted({m["t"].hour for m in inb})
        # reabertura em 24h: cliente agradeceu e voltou com o mesmo assunto em até 24h
        reab = False
        evento = False
        for j, m in enumerate(todas):
            if not (m["rec"] and agradeceu(m["body"])) or not (D <= m["t"] <= A):
                continue
            antes_c = {k2 for x in todas[:j] if x["rec"] and (m["t"] - x["t"]).total_seconds() <= 86400 for k2, rx in CATS.items() if rx.search(txt(x))}
            if not antes_c:
                continue
            evento = True
            for x in todas[j + 1:]:
                if x["rec"] and 1800 <= (x["t"] - m["t"]).total_seconds() <= 86400 and not SAUD.match(norm(x["body"]).strip()):
                    if any(rx.search(txt(x)) for k2, rx in CATS.items() if k2 in antes_c):
                        reab = True
                        break
        r["ev"] = evento
        r["rb"] = reab
        saida.append(r)
    return saida


class Metricas:
    """Calcula em segundo plano. Dias fechados ficam guardados; hoje é refeito a cada 2 minutos."""

    def __init__(self, cfg, banco_factory):
        self.cfg = cfg
        self.banco_factory = banco_factory
        self.banco = None
        self.inst = Instancias(cfg.acoes)
        self.dias: dict[str, list] = {}
        self.hoje: list | None = None
        self.hoje_anterior: list | None = None
        self.meta: dict = {}
        self.meta_ontem: dict = {}
        self._dia = None
        self._cheio_em = None
        self._marca = None
        self._ontem_em = None
        self._hoje_cru = None
        self.quando = None
        self.motivo = "ainda calculando — a primeira leitura do dia leva uns 4 minutos"
        self._trava = threading.Lock()

    def rodar(self, agora: datetime):
        demo = os.environ.get("PAINEL_DEMO_CONVERSAS") or ""
        if demo and Path(demo).is_file():
            self._carregar_demo(agora, Path(demo))
            return
        with self._trava:
            if self.banco is None:
                self.banco = self.banco_factory()
            self.inst.atualizar()
            cache = self.cfg.contador_dir / "cache"
            local = agora.astimezone(TZ)
            ini = local.replace(hour=0, minute=0, second=0, microsecond=0)
            t0 = time.monotonic()
            cheio = (
                self.hoje is None
                or self._dia != ini.date()
                or self._cheio_em is None
                or local - self._cheio_em >= timedelta(minutes=20)
            )
            extras_hoje = {"tel8_renov": renov_do_dia(cache, ini.date().isoformat())}
            ontem_velho = self._ontem_em is None or local - self._ontem_em >= timedelta(minutes=20)
            dia_faltando = None
            for atras in range(1, 7):
                chave = (ini - timedelta(days=atras)).date().isoformat()
                if chave not in self.dias:
                    dia_faltando = ini - timedelta(days=atras)
                    break
            if cheio:
                hoje, meta = calcular_janela(self.banco, ini, local, self.inst, extras_hoje, agora=local)
                if hoje is None:
                    if self.hoje is None:
                        self.motivo = "sem dado — não consegui ler as conversas no banco"
                    return
                self._hoje_cru = hoje
                self.hoje = _sem_cid(hoje)
                self.meta = meta
                self._dia = ini.date()
                self._cheio_em = local
                self._marca = local - timedelta(minutes=2)
                self.quando = local
                self.motivo = None
            elif ontem_velho and self.hoje is not None:
                ontem_ini = ini - timedelta(days=1)
                corte, meta_c = calcular_janela(
                    self.banco, ontem_ini, local - timedelta(days=1), self.inst,
                    {"tel8_renov": renov_do_dia(cache, ontem_ini.date().isoformat())},
                    agora=local,
                )
                if corte is not None:
                    self.hoje_anterior = _sem_cid(corte)
                    self.meta_ontem = meta_c
                    self._ontem_em = local
                    self.quando = local
            elif dia_faltando is not None:
                d0 = dia_faltando
                chave = d0.date().isoformat()
                fim = d0 + timedelta(days=1) - timedelta(seconds=1)
                reg, _meta_d = calcular_janela(
                    self.banco, d0, fim, self.inst,
                    {"tel8_renov": renov_do_dia(cache, chave)},
                    agora=local,
                )
                if reg is not None:
                    self.dias[chave] = _sem_cid(reg)
                    self.quando = local
                for antiga in list(self.dias):
                    if antiga < (ini - timedelta(days=7)).date().isoformat():
                        self.dias.pop(antiga, None)
            else:
                novos = self.banco.linhas(_SQL_CIDS_NOVOS, {"desde": self._marca, "fim": local})
                if novos is not None:
                    cids = [r["cid"] for r in novos]
                    parte, meta_p = calcular_janela_cids(self.banco, cids, ini, local, self.inst, extras_hoje)
                    if parte is not None:
                        por = {r.get("_cid"): r for r in (self._hoje_cru or [])}
                        for r in parte:
                            por[r.get("_cid")] = r
                        self._hoje_cru = [r for r in por.values() if r]
                        self.hoje = _sem_cid(self._hoje_cru)
                        if meta_p.get("falhas"):
                            self.meta = {**self.meta, "falhas": (self.meta.get("falhas") or 0) + meta_p["falhas"]}
                        self._marca = local - timedelta(minutes=2)
                        self.quando = local
                        self.motivo = None
            _devolver_memoria()
            atendidos = sum(1 for r in (self.hoje or []) if r["rc"] or r["ma"])
            avisar(
                "metricas-ok",
                "métricas %s em %.1fs (%d conversas hoje, %d atendidas, %d de fora)",
                "cheias" if cheio else "atualizadas",
                time.monotonic() - t0, len(self.hoje or []), atendidos, (self.meta or {}).get("falhas") or 0,
                intervalo=600,
            )

    def _carregar_demo(self, agora: datetime, caminho: Path):
        """Só liga se PAINEL_DEMO_CONVERSAS apontar um arquivo. A VPS não define isso."""
        try:
            dado = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.motivo = "sem dado — o exemplo de conversas não abriu"
            return
        hoje = dado.get("hoje") if isinstance(dado, dict) else dado
        if not isinstance(hoje, list):
            self.motivo = "sem dado — o exemplo de conversas não abriu"
            return
        local = agora.astimezone(TZ)
        self.hoje = hoje
        self.hoje_anterior = dado.get("ontem") if isinstance(dado, dict) else None
        self.meta = {"falhas": 0, "cids": len(hoje), "complemento": None}
        self.quando = local
        self.motivo = None
        self.inst.atualizar()

    def pacote(self, periodo: str) -> dict:
        if self.hoje is None:
            return {"ok": False, "motivo": self.motivo}
        if periodo == "ontem":
            ontem = (self.quando - timedelta(days=1)).date().isoformat()
            ante = (self.quando - timedelta(days=2)).date().isoformat()
            atual, antes = self.dias.get(ontem), self.dias.get(ante)
            rotulo, rot_antes = "ontem, dia inteiro", "anteontem inteiro"
        elif periodo == "7d":
            atual = [r for k in sorted(self.dias) for r in self.dias[k]] + self.hoje
            antes = None
            rotulo, rot_antes = "últimos 7 dias", None
        else:
            atual, antes = self.hoje, self.hoje_anterior
            rotulo, rot_antes = "hoje até agora", "ontem até este horário"
        aviso = _aviso_cobertura(self.meta)
        if periodo == "hoje" and self.hoje_anterior is None:
            aviso = _juntar_aviso(aviso, "comparação com ontem: sem dado")
        elif periodo == "hoje":
            aviso = _juntar_aviso(aviso, _aviso_cobertura(self.meta_ontem))
        if periodo == "7d" and len(self.dias) < 6:
            aviso = _juntar_aviso(aviso, "os dias anteriores ainda estão sendo contados")
        return {"ok": True, "periodo": periodo, "rotulo": rotulo, "rotulo_antes": rot_antes,
                "calculado_em": self.quando.isoformat(), "conversas": _sem_cid(atual or []),
                "anteriores": _sem_cid(antes) if antes else antes,
                "dias": sorted(set(self.dias) | {self.quando.date().isoformat()}),
                "aviso": aviso}


def _juntar_aviso(atual, extra):
    if not extra:
        return atual
    if not atual:
        return extra
    return f"{atual} · {extra}"


def _aviso_cobertura(meta) -> str | None:
    if not meta:
        return None
    partes = []
    if meta.get("falhas"):
        partes.append("sem dado completo — parte das conversas não entrou porque a leitura do banco estourou o tempo")
    comp = meta.get("complemento")
    if comp:
        partes.append(comp)
    return " · ".join(partes) or None


def resumo(regs: list | None) -> dict | None:
    """Poucos números para a tela inicial (quem atendeu, quantos foram atendidos)."""
    if regs is None:
        return None
    atendidos = [r for r in regs if r["rc"] or r["ma"]]
    pessoas: dict[str, dict] = {}
    for r in regs:
        for nome, n in (r.get("at") or {}).items():
            p = pessoas.setdefault(nome, {"conversas": 0, "mensagens": 0})
            p["conversas"] += 1
            p["mensagens"] += n
    # QUEM_ATENDEU_POR_NUMERO_0810: mesmo cálculo de "pessoas", separado pelo número de WhatsApp da conversa
    por_numero: dict[str, dict] = {}
    for r in regs:
        d = por_numero.setdefault(r.get("n") or "sem número", {"conversas": 0, "atendidas": 0, "sem_resposta": 0, "pessoas": {}})
        d["conversas"] += 1
        if r["rc"] or r["ma"]:
            d["atendidas"] += 1
        if r["sr"]:
            d["sem_resposta"] += 1
        for nome in (r.get("at") or {}):
            d["pessoas"][nome] = d["pessoas"].get(nome, 0) + 1
    return {
        "por_numero": por_numero,
        "atendidos": len(atendidos),
        "escreveram": sum(1 for r in regs if r["rc"]),
        "so_aviso": sum(1 for r in regs if not r["rc"] and not r["ma"] and r["mt"]),
        "pessoas": pessoas,
        "sem_resposta": sum(1 for r in regs if r["sr"]),
    }
