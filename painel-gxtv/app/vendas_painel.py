# -*- coding: utf-8 -*-
"""VENDAS_1110 — aba Vendas: VENDA NOVA x RENOVAÇÃO por dia. Só arquivo local, zero API.

  VENDA NOVA  = marcador da rotina 'Avisar venda nova do anúncio' (vendas_avisadas.jsonl, espelhado do box
                a cada ~30s em /var/lib/painel-gxtv/vendas_avisadas.jsonl). Conta: dia=D, sem excluido,
                com avisado_em (mesmo critério do aviso: instância 3619/0837/JORGE, pago no dia, anúncio, sem rmkt).
  RENOVAÇÃO   = ledger do fiscal (/opt/mnrobo/atendimento/acoes/renov_ledger.jsonl, status=renovado),
                valor pelo 'reservado' / usados.jsonl (mesmas keys); tira o que já é venda nova (keys/telefone).
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from app.tempo import TZ
from app.ocultos import instancia_oculta
from app.webhook_vivo import _ordem, rotulo  # FIX1710: mesmo nome de instância do Funil/Mensagens

ARQ_AVISADAS = Path(os.environ.get("PAINEL_VENDAS_AVISADAS") or "/var/lib/painel-gxtv/vendas_avisadas.jsonl")
ARQ_LEDGER = Path(os.environ.get("PAINEL_FISCAL_LEDGER") or "/opt/mnrobo/atendimento/acoes/renov_ledger.jsonl")
ARQ_USADOS = Path(os.environ.get("PAINEL_FISCAL_USADOS") or "/opt/mnrobo/atendimento/fiscal_comprovante/usados.jsonl")
INST_VENDA = [i for i in ["3619", "0837", "1869", "2884", "MALU", "JORGE"] if not instancia_oculta(i)]  # FIX1710: + 2884, MALU

_trava = threading.Lock()
_cache: dict = {}


def _k(c) -> str:
    t = str(c or "").strip()
    for pre in ("SHA:", "ID:", "MP:", "sha:", "id:", "mp:"):
        if t.startswith(pre):
            t = t[len(pre):]
    return t.upper()


def _num(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


_arq_cache: dict = {}  # FIX1710: arquivo lido 1x por versão (mtime+tamanho)


def _linhas(p: Path):
    try:
        st = p.stat()
    except OSError:
        return []
    sig = (st.st_mtime_ns, st.st_size)
    c = _arq_cache.get(str(p))
    if c and c[0] == sig:
        return c[1]
    out = []
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            for ln in f:
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    continue
    except OSError:
        return []
    _arq_cache[str(p)] = (sig, out)
    return out


@lru_cache(maxsize=100_000)
def _dia(ts) -> str:
    """FIX1710: dia do registro em America/Bahia (00:00-23:59), aceita ts com ou sem fuso."""
    t = str(ts or "")
    try:
        d = datetime.fromisoformat(t.replace("Z", "+00:00"))
    except ValueError:
        return t[:10]
    if d.tzinfo is not None:
        d = d.astimezone(TZ)
    return d.date().isoformat()


def _rot(v) -> str:
    """FIX1710: rótulo único de instância (mesmo do Funil): '3619', 'MALU', 'P2 COBRANÇA'..."""
    t = str(v or "").strip()
    if not t or t in ("?", "—", "-", "None", "null"):
        return ""
    r = rotulo("", t)
    return "" if r in ("?", "") else r


def _hora(ts) -> str:
    try:
        d = datetime.fromisoformat(str(ts))
        if d.tzinfo is not None:
            d = d.astimezone(TZ)
        return d.strftime("%H:%M")
    except (TypeError, ValueError):
        return ""


_E2E = re.compile(r"^E[0-9A-Z]{8}(20\d{2})(\d{2})(\d{2})(\d{2})(\d{2})")
EXCL_DURO = {"rmkt", "pagamento_antigo", "sem_pagamento_confirmado", "outra_empresa", "tela_extra"}  # VN_ROTINA_1410


def _pix_hora(keys) -> str:
    """VN_ROTINA_1410: hora em que o Pix chegou, pelo E2E (UTC -> Bahia)."""
    from datetime import timezone
    for k in keys or []:
        m = _E2E.match(_k(k))
        if m:
            try:
                d = datetime(*map(int, m.groups()), tzinfo=timezone.utc).astimezone(TZ)
                return d.strftime("%H:%M")
            except ValueError:
                continue
    return ""


def _inst_renov(conv: str) -> str:
    if not conv:
        return "—"
    try:  # FIX1710: mesmo mapa conversa->número do Funil (registro do webhook inteiro)
        from app.painel_1110 import QUEUE
        QUEUE.ler()
        n = QUEUE.conv_inst.get(conv)
        if n:
            return n
    except Exception:
        pass
    try:
        from app.webhook_vivo import VIVO
        if not getattr(VIVO, "_vd_ok", False):
            VIVO.atualizar(); VIVO._vd_ok = True
        return VIVO.conv_num.get(conv) or "—"
    except Exception:
        return "—"


def _ts_item(ts, dia: str) -> str:
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        d = d.astimezone(TZ) if d.tzinfo is not None else d.replace(tzinfo=TZ)
        return d.isoformat(timespec="seconds")
    except (TypeError, ValueError):
        return f"{dia}T12:00:00-03:00"


def _apurar(dia: str) -> dict:
    novas, chaves_novas, tel_novas = [], set(), set()
    excl_tel = set()  # VN_TESTE_1210
    excl_keys, mp_keys = set(), set()  # VN_FIX_1410b
    for d in _linhas(ARQ_AVISADAS):
        if d.get("dia") == dia and d.get("excluido"):  # VN_FIX_1410b: qualquer exclusão do registro bloqueia
            excl_tel.add(str(d.get("telefone") or ""))
            excl_keys.update(_k(x) for x in [d.get("sha"), d.get("e2e")] + list(d.get("keys") or []) if x)  # VN_ROTINA_1410: renovacao_cliente_antigo/instância não bloqueiam venda_nova do fiscal
        if d.get("dia") != dia or d.get("excluido") or not d.get("avisado_em"):
            continue
        if instancia_oculta(d.get("numero")):
            continue  # OCULTAR_JORGE_1110
        tel = str(d.get("telefone") or "")
        inst = _rot(d.get("numero")) or _inst_renov(str(d.get("conv") or ""))  # FIX1710
        if instancia_oculta(inst):
            continue
        novas.append({"telefone": tel, "valor": _num(d.get("valor")) or 0.0, "tipo": "venda",
                      "instancia": inst, "hora": _hora(d.get("ts")),
                      "pago": _pix_hora([d.get("e2e")] + list(d.get("keys") or [])) or _hora(d.get("ts")),
                      "ts": _ts_item(d.get("ts"), dia), "conv": str(d.get("conv") or ""), "plano": d.get("plano")})
        tel_novas.add(tel)
        chaves_novas.update(_k(x) for x in (d.get("sha"), d.get("e2e")) if x)

    valor, vn_fiscal, usados_dia = {}, set(), []
    extra_k: dict = {}  # FIX1710: plano/msg_hora por key (p/ Visão geral/Funil usarem esta mesma lista)
    for u in _linhas(ARQ_USADOS):
        for k in list(u.get("keys") or []) + [u.get("sha"), u.get("e2e")]:
            if k:
                ek = extra_k.setdefault(_k(k), {})
                for c in ("plano", "msg_hora"):
                    if u.get(c):
                        ek[c] = u.get(c)
        if u.get("status") == "renovado" and _dia(u.get("ts")) == dia and u.get("keys"):
            usados_dia.append(u)  # VN_ROTINA_1410: renovações feitas pela rotina (vigia) só existem aqui
        if u.get("venda_nova") is True and u.get("status") == "renovado" and _dia(u.get("ts")) == dia:
            vn_fiscal.add(str(u.get("telefone") or ""))  # VN_TESTE_1210: lead que só tinha teste e pagou
        if u.get("mp_id") or u.get("mp_confirmado") is True or any(str(k).upper().startswith("MP") for k in (u.get("keys") or [])):
            mp_keys.update(_k(k) for k in (u.get("keys") or []) if k)  # VN_FIX_1410b: pagamento Mercado Pago
        v = _num(u.get("valor"))
        if v is not None:
            for k in u.get("keys") or []:
                valor.setdefault(_k(k), v)
    try:
        from app.webhook_vivo import VIVO
        VIVO.atualizar()
    except Exception:
        pass
    renov, vistas = [], set()
    ledger = list(_linhas(ARQ_LEDGER))
    cria = set()
    for x in ledger:
        if x.get("status") == "reservado_cria" and _dia(x.get("ts")) == dia:
            cria.update(_k(k) for k in (x.get("keys") or []) if k)
    extra = []
    for u in usados_dia:  # VN_ROTINA_1410: entra como se fosse linha do ledger (dedupe por keys)
        extra.append({"status": "renovado", "ts": u.get("ts"), "keys": u.get("keys"), "telefone": u.get("telefone"),
                      "conv": u.get("conv"), "valor": u.get("valor"), "_vn": u.get("venda_nova") is True, "_rotina": True})
    for x in ledger + extra:
        keys = [_k(k) for k in (x.get("keys") or []) if k]
        v = _num(x.get("valor"))
        if v is not None:
            for k in keys:
                valor[k] = v
        if x.get("status") != "renovado" or not keys or _dia(x.get("ts")) != dia:
            continue
        if any(k in vistas for k in keys):
            continue
        vistas.update(keys)
        tel = str(x.get("telefone") or "")
        if any(k in chaves_novas for k in keys) or (tel and tel in tel_novas):
            continue  # já contado como venda nova
        inst = _inst_renov(str(x.get("conv") or ""))
        ex = next((extra_k[k] for k in keys if k in extra_k), {})
        meta = {"ts": _ts_item(x.get("ts"), dia), "conv": str(x.get("conv") or ""), "plano": ex.get("plano"),
                "msg_hora": ex.get("msg_hora")}  # FIX1710
        e_venda = (x.get("_vn") or tel in vn_fiscal or any(k in cria for k in keys))
        e_mp = any(str(k).upper().startswith("MP") for k in (x.get("keys") or [])) or any(k in mp_keys for k in keys)
        e_cob = any(t in str(inst or "").upper() for t in ("COBRAN", "SUPORTE"))
        if any(k in excl_keys for k in keys) or e_mp or e_cob:
            e_venda = False  # VN_FIX_1410b: excluído no registro / Mercado Pago / painel COBRANÇA-SUPORTE
        if e_venda and tel not in excl_tel and not instancia_oculta(inst):  # VN_ROTINA_1410: qualquer instância
            # VN_TESTE_1210: fiscal marcou venda_nova (user do teste 2h) em instância de venda e a rotina
            # ainda não marcou/nem excluiu -> venda nova, não renovação.
            v0 = next((valor[k] for k in keys if k in valor), None) or 0.0
            novas.append({"telefone": tel, "valor": v0, "tipo": "venda", "instancia": inst,
                          "hora": _hora(x.get("ts")), "pago": _pix_hora(keys) or "—", **meta})
            tel_novas.add(tel); chaves_novas.update(keys)
            continue
        renov.append({"telefone": tel, "keys": keys, "tipo": "renovacao", "hora": _hora(x.get("ts")),
                      "instancia": inst, "pago": _pix_hora(keys) or "—", **meta})
    renov = [r for r in renov if not instancia_oculta(r["instancia"])]  # OCULTAR_JORGE_1110
    for r in renov:
        r["valor"] = next((valor[k] for k in r.pop("keys") if k in valor), None)

    por_inst = {i: {"n": 0, "reais": 0.0} for i in INST_VENDA}
    for n in novas:
        b = por_inst.setdefault(n["instancia"], {"n": 0, "reais": 0.0})
        b["n"] += 1
        b["reais"] = round(b["reais"] + n["valor"], 2)
    lista = sorted(novas + renov, key=lambda i: i["hora"], reverse=True)
    for i in lista:  # VN_ROTINA_1410: pix = hora do Pix; hora = renovado às
        i["pix"] = i.pop("pago", None) or "—"
    sv = lambda l: round(sum(i["valor"] or 0 for i in l), 2)
    erro = None if ARQ_AVISADAS.exists() else f"sem {ARQ_AVISADAS.name}"
    try:
        idade = int(time.time() - ARQ_AVISADAS.stat().st_mtime)
    except OSError:
        idade = None
    return {
        "ok": erro is None, "erro": erro, "dia": dia,
        "novas": {"n": len(novas), "reais": sv(novas)},
        "renovacoes": {"n": len(renov), "reais": sv(renov), "sem_valor": sum(1 for r in renov if r["valor"] is None)},
        "total": {"n": len(lista), "reais": sv(lista)},
        "por_instancia": [{"instancia": k, **v} for k, v in sorted(por_inst.items(), key=lambda x: _ordem(x[0]))],
        "lista": lista,
        "marcador_idade_s": idade,
        "gerado": datetime.now(TZ).strftime("%H:%M:%S"),
    }


def pacote(dia: str | None = None) -> dict:
    hoje = datetime.now(TZ).date().isoformat()
    try:
        dia = date.fromisoformat(str(dia)).isoformat() if dia else hoje
    except ValueError:
        dia = hoje
    with _trava:
        c = _cache.get(dia)
        if c and time.time() - c[0] < (5 if dia >= hoje else 120):  # FIX1710: dia fechado muda pouco
            return c[1]
        r = _apurar(dia)
        _cache.clear() if len(_cache) > 20 else None
        _cache[dia] = (time.time(), r)
        return r
