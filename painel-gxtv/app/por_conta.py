"""POR_CONTA_1810: 'Recebido por conta hoje' e 'Renovado' corrigido. Só leitura de arquivos locais.

Fontes (somente leitura):
  /opt/mnrobo/contador_tg/cache/mp_api.jsonl  -> Pix da conta MP de suporte (2891), já com a flag 'proprio'
  /opt/mnrobo/atendimento/fiscal_comprovante/usados.jsonl -> renovações (status=renovado) e chaves do comprovante
Desligar: criar /var/lib/painel-gxtv/por_conta_off  (ou PAINEL_POR_CONTA=0 no ambiente) -> painel volta ao antigo.
Contas próprias: /opt/painel-gxtv/config/contas_proprias.json {"payer_ids": [...], "payment_ids": [...]}.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from app.tempo import TZ

ARQ_MP = Path(os.environ.get("PAINEL_MP_API") or "/opt/mnrobo/contador_tg/cache/mp_api.jsonl")
ARQ_USADOS = Path(os.environ.get("PAINEL_FISCAL_USADOS") or "/opt/mnrobo/atendimento/fiscal_comprovante/usados.jsonl")
ARQ_PROPRIAS = Path(__file__).resolve().parent.parent / "config" / "contas_proprias.json"
DESLIGA = Path("/var/lib/painel-gxtv/por_conta_off")
JANELA = timedelta(minutes=30)


def ligado() -> bool:
    return os.environ.get("PAINEL_POR_CONTA", "1") != "0" and not DESLIGA.exists()


def _ts(v):
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return (t if t.tzinfo else t.replace(tzinfo=TZ)).astimezone(TZ)


def _num(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _k(x):
    t = str(x or "").strip().upper()
    for p in ("SHA:", "ID:"):
        if t.startswith(p):
            t = t[len(p):]
    return t


def _jsonl(p: Path):
    try:
        with p.open(encoding="utf-8", errors="replace") as f:
            for ln in f:
                try:
                    yield json.loads(ln)
                except ValueError:
                    continue
    except OSError:
        return


def _proprias():
    try:
        d = json.loads(ARQ_PROPRIAS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    return {str(x) for x in d.get("payer_ids") or []}, {str(x) for x in d.get("payment_ids") or []}


def pacote(agora: datetime | None = None) -> dict:
    agora = (agora or datetime.now(TZ)).astimezone(TZ)
    ini = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    payers_prop, pays_prop = _proprias()

    # 1) MP suporte (API)
    mp, fora = {}, []
    for p in _jsonl(ARQ_MP):
        t = _ts(p.get("data_aprovado"))
        v = _num(p.get("valor"))
        if t is None or v is None or t < ini or t > agora + timedelta(minutes=5):
            continue
        pid = str(p.get("id") or "")
        mot = p.get("proprio")
        if not mot and (pid in pays_prop or str(p.get("payer_id") or "") in payers_prop):
            mot = "conta do próprio Gustavo"
        if mot:
            fora.append({"id": pid, "valor": v, "hora": t.strftime("%H:%M"), "motivo": mot})
            continue
        mp[pid] = {"id": pid, "valor": v, "quando": t}

    # 2) renovações do fiscal (status=renovado), sem duplicar
    regs = []
    for u in _jsonl(ARQ_USADOS):
        if u.get("status") != "renovado":
            continue
        t = _ts(u.get("ts"))
        if t is None or t < ini:
            continue
        regs.append({"t": t, "usuario": str(u.get("usuario") or ""), "tel": str(u.get("telefone") or ""),
                     "valor": _num(u.get("valor")), "plano": u.get("plano"), "mp": str(u.get("mp_id") or ""),
                     "arq": str(u.get("arquivo") or ""), "keys": [_k(k) for k in (u.get("keys") or [])]})
    regs.sort(key=lambda r: r["t"])
    renovs: list[dict] = []
    por_mp: dict[str, dict] = {}
    for r in regs:
        if r["mp"]:
            # mesmo pagamento MP = uma renovação; vale o último cliente casado (correção do fiscal)
            if r["mp"] in por_mp:
                por_mp[r["mp"]].update(usuario=r["usuario"], tel=r["tel"], plano=r["plano"] or por_mp[r["mp"]]["plano"])
                continue
            por_mp[r["mp"]] = r
            renovs.append(r)
            continue
        dup = next((x for x in renovs if x["usuario"] == r["usuario"] and abs(x["t"] - r["t"]) <= JANELA
                    and (not r["valor"] or not x["valor"] or (r["arq"] and r["arq"] == x["arq"]) or set(r["keys"]) & set(x["keys"]))), None)
        if dup:
            if r["valor"] and not dup["valor"]:
                dup["valor"] = r["valor"]
            if r["plano"] and not dup["plano"]:
                dup["plano"] = r["plano"]
            continue
        if not r["valor"] and any(x["usuario"] == r["usuario"] for x in renovs):
            continue
        renovs.append(r)
    # casa renovação sem id MP com Pix MP livre de mesmo valor (±30 min)
    usados_mp = {r["mp"] for r in renovs if r["mp"]}
    for r in renovs:
        if r["mp"] or not r["valor"]:
            continue
        cand = [p for p in mp.values() if p["id"] not in usados_mp and abs(p["valor"] - r["valor"]) < 0.005
                and abs(p["quando"] - r["t"]) <= JANELA]
        if cand:
            p = min(cand, key=lambda p: abs(p["quando"] - r["t"]))
            r["mp"] = p["id"]
            usados_mp.add(p["id"])
    # valor real do MP manda; classifica a conta
    contas = {"mp": [], "cs": [], "outras": []}
    for r in renovs:
        if r["mp"] in mp:
            r["valor"] = mp[r["mp"]]["valor"]
            r["conta"] = "mp"
        elif r["mp"]:
            r["conta"] = "mp_outro_dia"
        elif any(k.startswith("CS") for k in r["keys"]):
            r["conta"] = "cs"
        else:
            r["conta"] = "outras"
        if r["conta"] in ("cs", "outras"):
            contas[r["conta"]].append(r)

    def soma(xs):
        return round(sum(x["valor"] or 0 for x in xs), 2)

    mp_lista = list(mp.values())
    tabela = [
        {"conta": "Mercado Pago suporte (2891)", "fonte": "API do MP", "n": len(mp_lista), "reais": soma(mp_lista)},
        {"conta": "CS (Conta Simples)", "fonte": "comprovantes do fiscal (chave CS)", "n": len(contas["cs"]), "reais": soma(contas["cs"])},
        {"conta": "Outras (Dock/PagBank/Inter)", "fonte": "comprovantes do fiscal sem id MP e sem chave CS; o comprovante não diz a conta",
         "n": len(contas["outras"]), "reais": soma(contas["outras"])},
    ]
    return {
        "ok": True,
        "atualizado": agora.strftime("%H:%M"),
        "contas": tabela,
        "total_n": sum(c["n"] for c in tabela),
        "total_reais": round(sum(c["reais"] for c in tabela), 2),
        "fora": fora,
        "renovado_n": len(renovs),
        "renovado_reais": soma(renovs),
        "renovacoes": [{"hora": r["t"].strftime("%H:%M"), "usuario": r["usuario"], "valor": r["valor"],
                        "plano": r["plano"], "conta": r["conta"], "mp_id": r["mp"] or None} for r in renovs],
    }
