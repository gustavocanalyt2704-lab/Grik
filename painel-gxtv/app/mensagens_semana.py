# -*- coding: utf-8 -*-
"""SEMANA_1110 — comparativo de mensagens por dia da semana (semana atual x anterior).

Mesmas fontes da aba Ao vivo (app/webhook_vivo.py), só leitura de arquivo local, zero API DataCrazy:
  RECEBIDAS  /opt/mnrobo/atendimento/webhook/queue.jsonl  (received_ts + payload.evento/instancia)
  ENVIADAS   /opt/mnrobo/atendimento/ai/private/fluxo_envio_outbox.jsonl  (ts + inst; ignora via que não saiu)
Instância = mesmo rótulo do Ao vivo (webhook_vivo.rotulo). Fuso America/Bahia; semana começa na segunda.
Lê o arquivo de forma incremental (offset) e guarda só contagens por dia×instância.
"""
from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta

from app.tempo import TZ
from app.webhook_vivo import ARQ_ENVIADO, ARQ_RECEBIDO, VIA_NAO_SAIU, _ordem, rotulo

DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


class _Contador:
    def __init__(self, caminho, lado):
        self.caminho, self.lado = caminho, lado
        self.offset, self.inode, self.resto = 0, None, b""
        self.cont = defaultdict(int)  # (dia_iso, inst) -> n
        self.primeiro = None
        self.ultimo = None
        self.erro = ""

    def _linha(self, ln):
        try:
            a = json.loads(ln)
        except ValueError:
            return
        if self.lado == "r":
            p = a.get("payload") if isinstance(a.get("payload"), dict) else {}
            if "teste" in str(a.get("path") or "") or "teste" in str(p.get("evento") or ""):
                return
            if str(p.get("evento") or "").lower() == "conversa_atribuida" or "canary" in str(p.get("instancia") or "").lower():
                return  # evento de atribuição / teste canário, não é mensagem
            try:
                q = float(a.get("received_ts"))
            except (TypeError, ValueError):
                return
            inst = rotulo(p.get("evento"), p.get("instancia"))
        else:
            try:
                q = datetime.fromisoformat(str(a.get("ts"))).replace(tzinfo=TZ).timestamp()
            except (TypeError, ValueError):
                return
            if str(a.get("via") or "") in VIA_NAO_SAIU:
                return
            inst = rotulo("", a.get("inst"))
        from app.ocultos import instancia_oculta
        if instancia_oculta(inst):
            return  # OCULTAR_JORGE_1110
        dia = datetime.fromtimestamp(q, TZ).date().isoformat()
        self.cont[(dia, inst)] += 1
        if self.primeiro is None or q < self.primeiro:
            self.primeiro = q
        if self.ultimo is None or q > self.ultimo:
            self.ultimo = q

    def ler(self):
        try:
            st = self.caminho.stat()
        except OSError as exc:
            self.erro = f"sem acesso: {exc.__class__.__name__}"
            return
        ino = (st.st_dev, st.st_ino)
        if ino != self.inode or st.st_size < self.offset:
            # arquivo novo/rotacionado: recomeça (contagens antigas do arquivo anterior ficam)
            self.inode, self.offset, self.resto = ino, 0, b""
            self.cont.clear()
            self.primeiro = self.ultimo = None
        if st.st_size == self.offset:
            return
        try:
            with self.caminho.open("rb") as f:
                f.seek(self.offset)
                while True:
                    bloco = f.read(4_000_000)
                    if not bloco:
                        break
                    self.offset += len(bloco)
                    linhas = (self.resto + bloco).split(b"\n")
                    self.resto = linhas.pop()
                    for ln in linhas:
                        if ln.strip():
                            self._linha(ln)
        except OSError as exc:
            self.erro = f"sem acesso: {exc.__class__.__name__}"
            return
        self.erro = ""


_trava = threading.Lock()
_REC = _Contador(ARQ_RECEBIDO, "r")
_ENV = _Contador(ARQ_ENVIADO, "e")
_ult = 0.0


def _iso(ts):
    return datetime.fromtimestamp(ts, TZ).isoformat(timespec="minutes") if ts else None


def pacote() -> dict:
    global _ult
    with _trava:
        if time.time() - _ult > 20:
            _REC.ler()
            _ENV.ler()
            _ult = time.time()
        hoje = datetime.now(TZ).date()
        seg_atual = hoje - timedelta(days=hoje.weekday())
        seg_ant = seg_atual - timedelta(days=7)
        datas = {"atual": [(seg_atual + timedelta(days=i)).isoformat() for i in range(7)],
                 "anterior": [(seg_ant + timedelta(days=i)).isoformat() for i in range(7)]}
        quer = set(datas["atual"]) | set(datas["anterior"])
        # dados[inst][dia_iso] = [rec, env]
        dados: dict = defaultdict(lambda: defaultdict(lambda: [0, 0]))
        for idx, c in ((0, _REC), (1, _ENV)):
            for (dia, inst), n in c.cont.items():
                if dia in quer:
                    dados[inst][dia][idx] += n

        def cobertura(c):
            if not c.primeiro:
                return None
            return datetime.fromtimestamp(c.primeiro, TZ).date().isoformat()

        return {
            "ok": True,
            "hoje": hoje.isoformat(),
            "dias": DIAS,
            "datas": datas,
            "instancias": sorted(dados.keys(), key=_ordem),
            "dados": {i: {d: v for d, v in m.items()} for i, m in dados.items()},
            "cobertura": {
                "recebidas_desde": cobertura(_REC), "enviadas_desde": cobertura(_ENV),
                "recebidas_primeiro": _iso(_REC.primeiro), "enviadas_primeiro": _iso(_ENV.primeiro),
                "recebidas_ultimo": _iso(_REC.ultimo), "enviadas_ultimo": _iso(_ENV.ultimo),
            },
            "fonte": {"recebido": str(ARQ_RECEBIDO), "enviado": str(ARQ_ENVIADO),
                      "erro_recebido": _REC.erro, "erro_enviado": _ENV.erro, "api_datacrazy": False},
        }
