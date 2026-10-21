"""Financeiro e renovações pelo LEDGER DO FISCAL (08/10). Só arquivo local; nunca chama a API do DataCrazy.

  /opt/mnrobo/atendimento/acoes/renov_ledger.jsonl
      status=renovado  -> uma renovação que o fiscal fechou no Sigma (ts, conv, keys do comprovante)
      status=reservado -> traz o valor do comprovante (mesmas keys)
  /opt/mnrobo/atendimento/fiscal_comprovante/usados.jsonl
      valor e plano (1m, 2m...) do mesmo comprovante, pelas keys
Uma renovação conta uma vez só (nenhuma key repetida). O número de WhatsApp vem da conversa
no registro do webhook (conversa -> evento msg_p2cob etc.). Telefone e usuário não saem daqui.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from app.tempo import TZ
from app.webhook_vivo import VIVO, _Cauda, _ordem

ARQ_LEDGER = Path(os.environ.get("PAINEL_FISCAL_LEDGER") or "/opt/mnrobo/atendimento/acoes/renov_ledger.jsonl")
ARQ_USADOS = Path(os.environ.get("PAINEL_FISCAL_USADOS") or "/opt/mnrobo/atendimento/fiscal_comprovante/usados.jsonl")
PLANOS = [14.90, 19.90, 27.90, 44.90, 79.90, 99.90, 109.90, 199.90]


def _k(chave) -> str:
    """'SHA:ce27…' (usados) e 'CE27…' (ledger) são o mesmo comprovante."""
    t = str(chave or "").strip()
    for pre in ("SHA:", "ID:", "sha:", "id:"):
        if t.startswith(pre):
            t = t[len(pre):]
    return t.upper()


def _num(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


class Fiscal:
    def __init__(self):
        self._trava = threading.Lock()
        self._led = _Cauda(ARQ_LEDGER)
        self._usa = _Cauda(ARQ_USADOS)
        self._valor: dict[str, float] = {}
        self._plano: dict[str, str] = {}
        self._vistas: set[str] = set()
        self._renovs: list[dict] = []  # {quando, conv, keys, valor}
        self._ultima = 0.0

    def _ler(self):
        for ln in self._usa.novas():
            try:
                u = json.loads(ln)
            except ValueError:
                continue
            v = _num(u.get("valor"))
            for k in [_k(x) for x in (u.get("keys") or []) if x]:
                if v is not None:
                    self._valor.setdefault(k, v)
                if u.get("plano"):
                    self._plano[k] = str(u["plano"])
        corte = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        for ln in self._led.novas():
            try:
                x = json.loads(ln)
            except ValueError:
                continue
            keys = [_k(k) for k in (x.get("keys") or []) if k]
            v = _num(x.get("valor"))
            if v is not None:
                for k in keys:
                    self._valor[k] = v
            if x.get("status") != "renovado" or not keys:
                continue
            if any(k in self._vistas for k in keys):
                continue
            self._vistas.update(keys)
            try:
                quando = datetime.fromisoformat(str(x.get("ts")))
            except (TypeError, ValueError):
                continue
            if quando.tzinfo is None:
                quando = quando.replace(tzinfo=TZ)
            if quando < corte:
                continue
            self._renovs.append({"quando": quando, "conv": str(x.get("conv") or ""), "keys": keys, "valor": v})
        self._renovs = [r for r in self._renovs if r["quando"] >= corte]

    def pacote(self) -> dict:
        with self._trava:
            if time.time() - self._ultima >= 4:
                self._ultima = time.time()
                self._ler()
            erro = self._led.erro or self._usa.erro
            agora = datetime.now(TZ)
            ini = agora.replace(hour=0, minute=0, second=0, microsecond=0)
            ini_ontem, corte_ontem = ini - timedelta(days=1), agora - timedelta(days=1)
            try:
                VIVO.atualizar()
            except Exception:
                pass
            hoje, ontem = [], []
            for r in self._renovs:
                valor = r["valor"]
                if valor is None:
                    valor = next((self._valor[k] for k in r["keys"] if k in self._valor), None)
                plano = next((self._plano[k] for k in r["keys"] if k in self._plano), None)
                item = {"quando": r["quando"], "valor": valor, "plano": plano,
                        "numero": VIVO.conv_num.get(r["conv"]) or "sem número"}
                if r["quando"] >= ini:
                    hoje.append(item)
                elif ini_ontem <= r["quando"] <= corte_ontem:
                    ontem.append(item)

        def soma(lista):
            return round(sum(i["valor"] or 0 for i in lista), 2)

        por_plano = []
        usados = set()
        for p in PLANOS:
            achou = [i for i in hoje if i["valor"] is not None and abs(i["valor"] - p) < 0.005]
            usados.update(id(i) for i in achou)
            por_plano.append({"valor_plano": p, "n": len(achou), "reais": soma(achou)})
        outros = [i for i in hoje if i["valor"] is not None and id(i) not in usados]
        valores_outros: dict[str, int] = {}
        for i in outros:
            chave = f"{i['valor']:.2f}"
            valores_outros[chave] = valores_outros.get(chave, 0) + 1
        por_numero: dict[str, dict] = {}
        for i in hoje:
            d = por_numero.setdefault(i["numero"], {"n": 0, "reais": 0.0})
            d["n"] += 1
            d["reais"] = round(d["reais"] + (i["valor"] or 0), 2)
        por_hora = [0.0] * 24
        for i in hoje:
            por_hora[i["quando"].hour] = round(por_hora[i["quando"].hour] + (i["valor"] or 0), 2)
        meses: dict[str, int] = {}
        for i in hoje:
            meses[i["plano"] or "sem plano"] = meses.get(i["plano"] or "sem plano", 0) + 1
        n, total = len(hoje), soma(hoje)
        return {
            "ok": not erro,
            "erro": erro or None,
            "fonte": f"{ARQ_LEDGER} + {ARQ_USADOS}",
            "n": n,
            "reais": total,
            "ticket": round(total / n, 2) if n else None,
            "sem_valor": sum(1 for i in hoje if i["valor"] is None),
            "ontem_n": len(ontem),
            "ontem_reais": soma(ontem),
            "por_plano": por_plano,
            "outros": {"n": len(outros), "reais": soma(outros),
                       "valores": sorted(valores_outros.items(), key=lambda x: -x[1])[:8]},
            "por_numero": [{"numero": k, **v} for k, v in sorted(por_numero.items(), key=lambda x: _ordem(x[0]))],
            "por_duracao": sorted(meses.items(), key=lambda x: -x[1]),
            "por_hora": por_hora,
            "ultimas": [{"hora": i["quando"].strftime("%H:%M"), "valor": i["valor"], "numero": i["numero"]}
                        for i in sorted(hoje, key=lambda i: i["quando"], reverse=True)[:6]],
        }


FISCAL = Fiscal()
