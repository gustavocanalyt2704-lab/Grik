"""Ao vivo pelo REGISTRO DO WEBHOOK (08/10). Só lê arquivo local; nunca chama a API do DataCrazy.

Duas fontes, cada uma é um lado do webhook:
  RECEBIDO  /opt/mnrobo/atendimento/webhook/queue.jsonl
            o DataCrazy chama o nosso receptor a cada mensagem do CLIENTE (evento msg_3619, msg_p2cob...).
  ENVIADO   /opt/mnrobo/atendimento/ai/private/fluxo_envio_outbox.jsonl
            o robô chama o webhook fixo de cada número no DataCrazy para mandar a resposta
            (1 linha por envio fechado: número, tipo texto/mídia, via=webhook/reenvio_ok/falha...).
Lê só o pedaço novo dos arquivos (offset), no máximo 1x por segundo, e só quando alguém olha a tela.
Telefone, nome e texto não saem daqui.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from app.tempo import TZ

ARQ_RECEBIDO = Path(os.environ.get("PAINEL_WEBHOOK_QUEUE") or "/opt/mnrobo/atendimento/webhook/queue.jsonl")
ARQ_ENVIADO = Path(os.environ.get("PAINEL_FLUXO_OUTBOX") or "/opt/mnrobo/atendimento/ai/private/fluxo_envio_outbox.jsonl")

# via do fluxo_envio que NÃO saiu para o cliente
VIA_NAO_SAIU = {
    "falha_webhook_final", "falha_sem_fallback", "sem_mapa", "rest_sem_mapa", "janela_24h", "sem_fluxo_midia",
    "audio_bloqueado", "rest_bloqueado", "descartado_cliente_novo", "descartado_fila_cheia",
}
TIPOS_REC = {"IMAGE": "foto", "AUDIO": "audio", "VIDEO": "video", "FILE": "arquivo", "DOCUMENT": "arquivo"}
ORDEM_FIXA = ["3619", "0837", "1869", "2884", "MALU"]  # FIX1710: + MALU (mesma ordem em todas as abas)
JANELA_S = 3600  # guarda 1 h segundo a segundo

# ENVLOG_1910: o outbox só ganha linha quando o item FECHA (conferência); muitos aceitos (http 2xx) ficam
# pendentes e nunca fecham -> o painel subcontava (~1/3). Agora "enviado" = cada POST aceito no log
# "HH:MM:SS FLUXO envio inst=... http=2xx" (robô + ondas + fiscal). O outbox segue só p/ não-saiu e conversas.
LOGS_ENVIO = [x for x in (os.environ.get("PAINEL_LOGS_ENVIO") or
    "/opt/mnrobo/atendimento/ai/private/live.log,/opt/mnrobo/atendimento/ai/private/*onda*.log,"
    "/opt/mnrobo/atendimento/fiscal_comprovante/fiscal.log").split(",") if x.strip()]
RX_ENVIO = re.compile(rb"^(\d\d):(\d\d):(\d\d) FLUXO envio inst=(.+?) tel=\S* cid=\S* tipo=(\S+) tent=\d+ http=(\d+)")


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def rotulo(evento: str = "", inst: str = "") -> str:
    """msg_p2cob / ' 💙 COBRANÇA P2 💙 ' / 'COBRANÇA P2' -> 'P2 COBRANÇA'. Mesma chave dos dois lados."""
    ev = str(evento or "").strip().lower()
    m = re.fullmatch(r"msg_p(\d)(cob|sup)", ev)
    if m:
        return f"P{m.group(1)} " + ("COBRANÇA" if m.group(2) == "cob" else "SUPORTE")
    m = re.fullmatch(r"msg_(\d{4})", ev)
    if m:
        return m.group(1)
    if ev == "msg_rmkt":
        return "RMKT"
    bruto = re.sub(r"[^0-9A-Za-zÀ-ÿ ]+", " ", str(inst or ""))
    bruto = re.sub(r"\s+", " ", bruto).strip().upper()
    if not bruto:
        return "?" if not ev else ev.replace("msg_", "").upper()
    plano = _sem_acento(bruto)
    m = re.search(r"\bP\s?(\d)\b", plano)
    if m and "COBRAN" in plano:
        return f"P{m.group(1)} COBRANÇA"
    if m and "SUPORT" in plano:
        return f"P{m.group(1)} SUPORTE"
    if "RMKT" in plano:
        return "RMKT"
    m = re.fullmatch(r"(?:FINAL )?(\d{4})", plano)
    if m:
        return m.group(1)
    if plano == "SEM NUMERO":
        return "sem número"
    return bruto[:24]


def _ordem(r: str):
    if r in ORDEM_FIXA:
        return (0, ORDEM_FIXA.index(r), r)
    m = re.match(r"P(\d) (COBRANÇA|SUPORTE)", r)
    if m:
        return (1, int(m.group(1)) * 2 + (0 if m.group(2) == "COBRANÇA" else 1), r)
    if r == "RMKT":
        return (2, 0, r)
    return (3, 0, r)


class _Cauda:
    """Lê só as linhas novas de um jsonl (aguenta rotação/truncamento)."""

    def __init__(self, caminho: Path):
        self.caminho = caminho
        self.offset = 0
        self.inode = None
        self.resto = b""
        self.erro = ""

    def novas(self, inicio_bytes: int | None = None):
        try:
            st = self.caminho.stat()
        except OSError as exc:
            self.erro = f"sem acesso: {exc.__class__.__name__}"
            return []
        ino = (st.st_dev, st.st_ino)
        if ino != self.inode or st.st_size < self.offset:
            self.inode, self.resto = ino, b""
            self.offset = 0 if inicio_bytes is None else max(0, st.st_size - inicio_bytes)
        if st.st_size == self.offset:
            return []
        try:
            with self.caminho.open("rb") as f:
                f.seek(self.offset)
                bloco = f.read(st.st_size - self.offset)
        except OSError as exc:
            self.erro = f"sem acesso: {exc.__class__.__name__}"
            return []
        self.erro = ""
        self.offset += len(bloco)
        dado = self.resto + bloco
        linhas = dado.split(b"\n")
        self.resto = linhas.pop()
        return linhas


def _novo_num():
    return {"rec": 0, "env": 0, "nao_saiu": 0, "rec_tipos": defaultdict(int), "env_tipos": defaultdict(int),
            "ult_rec": 0.0, "ult_env": 0.0, "convs": set(), "robo_convs": set(), "atrib": {}}


def _quem(n: dict) -> dict:
    """QUEM_WEBHOOK_0810 — tudo em CLIENTES (conversas distintas de hoje), pelo registro do webhook:
    robo_clientes = conversas que escreveram hoje e receberam pelo menos 1 mensagem do robô (fluxo_envio_outbox, saiu);
    robo_proativo = conversas que só receberam mensagem do robô (aviso/lote), sem ter escrito hoje;
    atribuido     = conversas cujo atendente atribuído no DataCrazy era essa pessoa (campo atendente do webhook);
    sem_atendente = conversas que escreveram hoje sem atendente atribuído.
    O webhook não registra mensagem escrita por humano; por isso o humano aqui é o ATRIBUÍDO, não quem digitou."""
    nomes: dict[str, int] = {}
    sem = 0
    for at in n["atrib"].values():
        if not at:
            sem += 1
            continue
        for x in at.split(","):
            x = " ".join(x.replace("Atendente ", "").replace("Gerente", "").split())
            from app.ocultos import atendente_oculto
            if x and not atendente_oculto(x):  # OCULTAR_JORGE_1110
                nomes[x] = nomes.get(x, 0) + 1
    # robô: só quem ESCREVEU hoje e recebeu resposta (tira os avisos proativos para quem não falou)
    return {"robo_clientes": len(n["robo_convs"] & n["convs"]), "robo_proativo": len(n["robo_convs"] - n["convs"]), "atribuido": sorted(nomes.items(), key=lambda x: -x[1]), "sem_atendente": sem}


class WebhookVivo:
    def __init__(self):
        self._trava = threading.Lock()
        self._rec = _Cauda(ARQ_RECEBIDO)
        self._env = _Cauda(ARQ_ENVIADO)
        self._ultima_leitura = 0.0
        self._dia = None
        self._zerar_dia(datetime.now(TZ).date())
        # segundo (int epoch) -> {"r": {num: n}, "e": {num: n}}
        self._seg: dict[int, dict] = {}
        self._primeira = True
        self.conv_num: dict[str, str] = {}  # conversa -> número (para o financeiro por número)
        self._logs: dict[str, _Cauda] = {}  # ENVLOG_1910

    def _zerar_dia(self, dia):
        self._dia = dia
        self._nums: dict[str, dict] = defaultdict(_novo_num)
        self._tot = {"rec": 0, "env": 0, "nao_saiu": 0}
        self._min_dia: dict[int, list] = defaultdict(lambda: [0, 0])  # minuto do dia -> [rec, env]
        self._ini_dia = datetime.combine(dia, datetime.min.time(), TZ).timestamp()

    # ---------------- leitura ----------------
    def _conta(self, lado: str, num: str, quando: float, tipo: str, saiu: bool = True, conversa: str = "", atendente: str = ""):
        from app.ocultos import instancia_oculta
        if instancia_oculta(num):
            return  # OCULTAR_JORGE_1110
        dia = datetime.fromtimestamp(quando, TZ).date()
        if dia != self._dia:
            if dia < self._dia:
                return  # linha de ontem (só na 1ª leitura)
            self._zerar_dia(dia)
        n = self._nums[num]
        if lado == "r":
            n["rec"] += 1
            n["rec_tipos"][tipo] += 1
            if conversa:
                n["convs"].add(conversa)
                # QUEM_WEBHOOK_0810: atendente atribuído à conversa (o último que o DataCrazy mandou hoje)
                if atendente:
                    n["atrib"][conversa] = atendente
                else:
                    n["atrib"].setdefault(conversa, "")
            n["ult_rec"] = max(n["ult_rec"], quando)
            self._tot["rec"] += 1
        elif saiu:
            n["env"] += 1
            n["env_tipos"][tipo] += 1
            if conversa:
                n["robo_convs"].add(conversa)
            n["ult_env"] = max(n["ult_env"], quando)
            self._tot["env"] += 1
        else:
            n["nao_saiu"] += 1
            self._tot["nao_saiu"] += 1
            return
        mi = int((quando - self._ini_dia) // 60)
        self._min_dia[mi][0 if lado == "r" else 1] += 1
        s = int(quando)
        if s >= time.time() - JANELA_S - 5:
            caixa = self._seg.setdefault(s, {"r": defaultdict(int), "e": defaultdict(int)})
            caixa[lado][num] += 1

    def _ler_recebidos(self, linhas):
        for ln in linhas:
            if not ln.strip():
                continue
            try:
                a = json.loads(ln)
            except ValueError:
                continue
            p = a.get("payload") if isinstance(a.get("payload"), dict) else {}
            try:
                quando = float(a.get("received_ts"))
            except (TypeError, ValueError):
                continue
            anexos = p.get("anexos") if isinstance(p.get("anexos"), list) else []
            t0 = (anexos[0].get("type") if anexos and isinstance(anexos[0], dict) else "") or ""
            tipo = TIPOS_REC.get(str(t0).upper(), "outro") if anexos else "texto"
            num = rotulo(p.get("evento"), p.get("instancia"))
            if p.get("conversa"):
                self.conv_num[str(p["conversa"])] = num
            at = str(p.get("atendente") or "").strip()
            if "{{" in at:
                at = ""
            self._conta("r", num, quando, tipo, conversa=str(p.get("conversa") or ""), atendente=at)

    def _ler_enviados(self, linhas):
        for ln in linhas:
            if not ln.strip():
                continue
            try:
                a = json.loads(ln)
            except ValueError:
                continue
            try:
                quando = datetime.fromisoformat(str(a.get("ts"))).replace(tzinfo=TZ).timestamp()
            except (TypeError, ValueError):
                continue
            via = str(a.get("via") or "")
            tipo = "foto" if str(a.get("tipo") or "") == "midia" else "texto"
            num_e = rotulo("", a.get("inst"))
            if a.get("cid") and num_e not in ("?", ""):
                self.conv_num.setdefault(str(a["cid"]), num_e)  # FIX1710: número pela saída do robô se o webhook faltar
            if via in VIA_NAO_SAIU:
                self._conta("e", num_e, quando, tipo, saiu=False, conversa=str(a.get("cid") or ""))
            elif a.get("cid") and datetime.fromtimestamp(quando, TZ).date() == self._dia:
                self._nums[num_e]["robo_convs"].add(str(a["cid"]))  # ENVLOG_1910: contagem vem do log

    def _ler_logs_envio(self, ini):
        """ENVLOG_1910: conta cada POST aceito (http 2xx) do fluxo_envio pelo horário do log (sem data na linha)."""
        import glob
        for padrao in LOGS_ENVIO:
            for cam in glob.glob(padrao):
                if ".bak" in cam:
                    continue
                c = self._logs.get(cam)
                novo = c is None
                if novo:
                    c = self._logs[cam] = _Cauda(Path(cam))
                try:
                    mt = os.stat(cam).st_mtime
                except OSError:
                    continue
                linhas = c.novas(ini if (novo and ini) else (16_000_000 if novo else None))
                if not linhas:
                    continue
                dia = datetime.fromtimestamp(mt, TZ).date()
                if dia != self._dia:
                    continue
                # data por linha: do fim para trás, volta 1 dia quando a hora "sobe" (virada de meia-noite)
                achados, ant, dia_ok = [], None, True
                for ln in reversed(linhas):
                    m = RX_ENVIO.match(ln)
                    if not m:
                        continue
                    hms = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
                    if ant is not None and hms > ant + 600:
                        dia_ok = False
                    if not dia_ok:
                        break
                    ant = hms
                    if not m.group(6).startswith(b"2"):
                        continue
                    achados.append((hms, m.group(4).decode("utf-8", "ignore"), m.group(5).decode()))
                agora = time.time()
                for hms, inst, tp in reversed(achados):
                    quando = self._ini_dia + hms
                    if quando > agora + 120:
                        continue  # é de ontem
                    self._conta("e", rotulo("", inst), quando, "foto" if tp == "midia" else "texto")

    def atualizar(self):
        with self._trava:
            agora = time.time()
            if agora - self._ultima_leitura < 0.8:
                return
            self._ultima_leitura = agora
            if datetime.now(TZ).date() != self._dia:
                self._zerar_dia(datetime.now(TZ).date())
            # 1ª vez: lê o dia inteiro (fila de vários dias: só os últimos ~16 MB bastam p/ 1 dia).
            ini = 16_000_000 if self._primeira else None
            self._ler_recebidos(self._rec.novas(ini))
            self._ler_enviados(self._env.novas(ini))
            self._ler_logs_envio(80_000_000 if self._primeira else None)
            self._primeira = False
            corte = int(agora) - JANELA_S
            for s in [s for s in self._seg if s < corte]:
                del self._seg[s]

    def hoje_por_numero(self) -> dict:
        """INICIO_0810: {número: {"conversas": clientes distintos que escreveram hoje, "recebidas": msgs, "enviadas": msgs}}"""
        self.atualizar()
        with self._trava:
            return {k: {"conversas": len(v["convs"]), "recebidas": v["rec"], "enviadas": v["env"], **_quem(v)} for k, v in self._nums.items()}

    # ---------------- pacote para a tela ----------------
    def _soma(self, de: int, ate: int):
        r = defaultdict(int)
        e = defaultdict(int)
        for s in range(de, ate):
            c = self._seg.get(s)
            if c:
                for k, v in c["r"].items():
                    r[k] += v
                for k, v in c["e"].items():
                    e[k] += v
        return r, e

    def pacote(self) -> dict:
        self.atualizar()
        with self._trava:
            agora = time.time()
            s_agora = int(agora)
            # O registro grava com 1 s de atraso; o "último segundo" é o que já fechou.
            r1, e1 = self._soma(s_agora - 1, s_agora)
            r10, e10 = self._soma(s_agora - 10, s_agora)
            r60, e60 = self._soma(s_agora - 60, s_agora)
            r15, e15 = self._soma(s_agora - 900, s_agora)
            serie = []
            for s in range(s_agora - 120, s_agora):
                c = self._seg.get(s)
                serie.append([sum(c["r"].values()), sum(c["e"].values())] if c else [0, 0])
            min_hoje = max(1.0, (agora - self._ini_dia) / 60)
            mi_agora = int((agora - self._ini_dia) // 60)
            min_serie = [self._min_dia.get(m, [0, 0]) for m in range(max(0, mi_agora - 59), mi_agora + 1)]

            def tx(d, seg):
                return round(sum(d.values()) / seg, 3)

            numeros = []
            nomes = set(self._nums) | set(r15) | set(e15)
            for nome in sorted(nomes, key=_ordem):
                n = self._nums.get(nome) or _novo_num()
                numeros.append({
                    "numero": nome,
                    "rec_hoje": n["rec"], "env_hoje": n["env"], "nao_saiu_hoje": n["nao_saiu"],
                    "rec_s_60": round(r60.get(nome, 0) / 60, 3), "env_s_60": round(e60.get(nome, 0) / 60, 3),
                    "rec_min_15": round(r15.get(nome, 0) / 15, 2), "env_min_15": round(e15.get(nome, 0) / 15, 2),
                    "rec_10s": r10.get(nome, 0), "env_10s": e10.get(nome, 0),
                    "rec_1s": r1.get(nome, 0), "env_1s": e1.get(nome, 0),
                    "rec_tipos": dict(n["rec_tipos"]), "env_tipos": dict(n["env_tipos"]),
                    "clientes_hoje": len(n["convs"]), **_quem(n),
                    "ult_rec_ha_s": round(agora - n["ult_rec"]) if n["ult_rec"] else None,
                    "ult_env_ha_s": round(agora - n["ult_env"]) if n["ult_env"] else None,
                })
            tot_r, tot_e = self._tot["rec"], self._tot["env"]
            return {
                "ok": True,
                "hora": datetime.fromtimestamp(agora, TZ).isoformat(timespec="seconds"),
                "fonte": {
                    "recebido": str(ARQ_RECEBIDO), "enviado": str(ARQ_ENVIADO),
                    "erro_recebido": self._rec.erro, "erro_enviado": self._env.erro,
                    "api_datacrazy": False,
                },
                "geral": {
                    "msg_s_1": sum(r1.values()) + sum(e1.values()),
                    "rec_s_1": sum(r1.values()), "env_s_1": sum(e1.values()),
                    "msg_s_10": round((sum(r10.values()) + sum(e10.values())) / 10, 2),
                    "msg_s_60": round((sum(r60.values()) + sum(e60.values())) / 60, 3),
                    "rec_s_60": tx(r60, 60), "env_s_60": tx(e60, 60),
                    "msg_min_15": round((sum(r15.values()) + sum(e15.values())) / 15, 1),
                    "rec_min_15": round(sum(r15.values()) / 15, 1), "env_min_15": round(sum(e15.values()) / 15, 1),
                    "msg_min_hoje": round((tot_r + tot_e) / min_hoje, 1),
                    "rec_hoje": tot_r, "env_hoje": tot_e, "nao_saiu_hoje": self._tot["nao_saiu"],
                    "pico_s_60": max((a + b for a, b in serie[-60:]), default=0),
                },
                "serie_120s": serie,
                "serie_60min": min_serie,
                "numeros": numeros,
            }


VIVO = WebhookVivo()
