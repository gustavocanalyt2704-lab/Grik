# -*- coding: utf-8 -*-
"""ATENDIDOS_1410 — "Pessoas atendidas hoje": telefones únicos que mandaram >=1 msg no dia (00:00 America/Bahia)
E tiveram resposta (robô: fluxo_envio_outbox na mesma conversa, via que saiu; humano: conversa com atendente atribuído).
Só arquivo local (mesmas fontes da aba Mensagens), zero API DataCrazy. Exclui 557791625576 e grupos."""
from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta

from app.tempo import TZ
from app.webhook_vivo import ARQ_ENVIADO, ARQ_RECEBIDO, VIA_NAO_SAIU, _ordem, rotulo

EXCLUIR = {"557791625576"}


class _Cauda:
    def __init__(self, caminho, fn):
        self.caminho, self.fn = caminho, fn
        self.offset, self.inode, self.resto = 0, None, b""

    def ler(self):
        try:
            st = self.caminho.stat()
        except OSError:
            return
        ino = (st.st_dev, st.st_ino)
        if ino != self.inode or st.st_size < self.offset:
            self.inode, self.offset, self.resto = ino, 0, b""
        if st.st_size == self.offset:
            return
        with self.caminho.open("rb") as f:
            f.seek(self.offset)
            while True:
                b = f.read(4_000_000)
                if not b:
                    break
                self.offset += len(b)
                ls = (self.resto + b).split(b"\n")
                self.resto = ls.pop()
                for ln in ls:
                    if ln.strip():
                        try:
                            self.fn(json.loads(ln))
                        except Exception:
                            pass


_conv = defaultdict(dict)      # dia -> conversa -> (tel, inst)
_resp = defaultdict(set)       # dia -> conversas respondidas
_trava = threading.Lock()
_ult = 0.0


def _rec(a):
    p = a.get("payload") if isinstance(a.get("payload"), dict) else {}
    ev = str(p.get("evento") or "")
    if "teste" in str(a.get("path") or "") or "teste" in ev or ev.lower() == "conversa_atribuida":
        return
    if "canary" in str(p.get("instancia") or "").lower():
        return
    tel = "".join(c for c in str(p.get("telefone") or "") if c.isdigit())
    braw = str(p.get("telefone") or "")
    if not tel or tel in EXCLUIR or "@g" in braw or "-" in braw or len(tel) > 13:
        return  # vazio, excluído ou grupo
    conv = str(p.get("conversa") or "")
    if not conv:
        return
    dia = datetime.fromtimestamp(float(a.get("received_ts")), TZ).date().isoformat()
    inst = rotulo(ev, p.get("instancia"))
    _conv[dia].setdefault(conv, (tel, inst))
    if str(p.get("atendente") or "").strip():
        _resp[dia].add(conv)


def _env(a):
    if str(a.get("via") or "") in VIA_NAO_SAIU:
        return
    cid = str(a.get("cid") or "")
    if not cid:
        return
    dia = datetime.fromisoformat(str(a.get("ts"))).date().isoformat()
    _resp[dia].add(cid)


_R = _Cauda(ARQ_RECEBIDO, _rec)
_E = _Cauda(ARQ_ENVIADO, _env)


def _conta(dia):
    from app.ocultos import instancia_oculta
    tels, por = set(), defaultdict(set)
    resp = _resp.get(dia, set())
    for conv, (tel, inst) in _conv.get(dia, {}).items():
        if conv in resp and not instancia_oculta(inst):
            tels.add(tel)
            por[inst].add(tel)
    return len(tels), {i: len(s) for i, s in por.items()}


def pacote() -> dict:
    global _ult
    with _trava:
        if time.time() - _ult > 10:
            _R.ler()
            _E.ler()
            _ult = time.time()
            lim = (datetime.now(TZ).date() - timedelta(days=3)).isoformat()
            for d in [d for d in list(_conv) + list(_resp) if d < lim]:
                _conv.pop(d, None)
                _resp.pop(d, None)
        hoje = datetime.now(TZ).date()
        ontem = (hoje - timedelta(days=1)).isoformat()
        th, ph = _conta(hoje.isoformat())
        to, po = _conta(ontem)
        return {"ok": True, "hoje": hoje.isoformat(), "total": th,
                "instancias": [{"inst": i, "n": ph[i], "ontem": po.get(i, 0)} for i in sorted(ph, key=_ordem)],
                "ontem": {"dia": ontem, "total": to},
                "atualizado": datetime.now(TZ).strftime("%H:%M:%S")}
