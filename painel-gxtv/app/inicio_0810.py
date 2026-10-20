"""Início 08/10: financeiro/renovações pelo ledger do fiscal, "quem atendeu" por número e o cartão
"Sem resposta" no lugar do "Esperando +15 min". Só acrescenta chaves ao estado montado."""

from __future__ import annotations

from app.financeiro_fiscal import FISCAL
from app.webhook_vivo import _ordem, rotulo

_AVISADO = False


def _br(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def completar(estado: dict, met: dict | None) -> None:
    if not isinstance(estado, dict):
        return
    destaques = estado.setdefault("destaques", {})
    fin = FISCAL.pacote()
    estado["financeiro"] = fin

    # Renovações: o mesmo ledger do financeiro (assim os dois números da tela batem).
    if fin.get("ok"):
        n, o = fin["n"], fin["ontem_n"]
        delta = None
        if o:
            dif = n - o
            delta = {"txt": f"{'+' if dif >= 0 else ''}{dif}", "bom": dif >= 0}
        destaques["renov"] = {
            "v": n, "ontem": o, "reais": fin["reais"],
            "frase": f"{_br(fin['reais'])} · ontem até agora: {o} ({_br(fin['ontem_reais'])})",
            "tom": "sem" if not o else ("ok" if n >= o else ("atencao" if n >= 0.7 * o else "ruim")),
            "delta": delta,
        }

    hoje = (met or {}).get("hoje") or {}
    por_num_met = hoje.get("por_numero") or {}
    sr = hoje.get("sem_resposta")
    if sr is None:
        destaques["sem_resposta"] = {"v": None, "tom": "sem", "frase": "calculando… a primeira leitura do dia leva uns 4 minutos"}
    else:
        destaques["sem_resposta"] = {
            "v": sr, "tom": "ok" if sr == 0 else ("atencao" if sr < 20 else "ruim"),
            "frase": "conversas de hoje em que o cliente pediu algo e não teve nenhuma resposta (robô nem equipe)",
        }

    numeros: dict[str, dict] = {}
    for bruto, d in por_num_met.items():
        k = rotulo("", bruto)
        alvo = numeros.setdefault(k, {"numero": k, "conversas": 0, "atendidas": 0, "sem_resposta": 0, "pessoas": {}})
        alvo["conversas"] += d.get("conversas", 0)
        alvo["atendidas"] += d.get("atendidas", 0)
        alvo["sem_resposta"] += d.get("sem_resposta", 0)
        for nome, c in (d.get("pessoas") or {}).items():
            alvo["pessoas"][nome] = alvo["pessoas"].get(nome, 0) + c
    # Conversas e mensagens do dia: registro do webhook (mais completo que o espelho)
    try:
        from app.webhook_vivo import VIVO

        wh = VIVO.hoje_por_numero()
    except Exception:
        wh = {}
    for k, w in wh.items():
        alvo = numeros.setdefault(k, {"numero": k, "conversas": 0, "atendidas": 0, "sem_resposta": 0, "pessoas": {}})
        alvo["conversas_wh"] = w["conversas"]
        alvo["recebidas_wh"] = w["recebidas"]
        alvo["enviadas_wh"] = w["enviadas"]
        alvo["robo_clientes"] = w.get("robo_clientes")
        alvo["robo_proativo"] = w.get("robo_proativo")
        alvo["atribuido"] = w.get("atribuido") or []
        alvo["sem_atendente"] = w.get("sem_atendente")
    for f in fin.get("por_numero") or []:
        alvo = numeros.setdefault(f["numero"], {"numero": f["numero"], "conversas": None, "atendidas": None, "sem_resposta": None, "pessoas": {}})
        alvo["renov_n"], alvo["renov_reais"] = f["n"], f["reais"]
    lista = []
    for k in sorted(numeros, key=_ordem):
        d = numeros[k]
        d.setdefault("renov_n", 0)
        d.setdefault("conversas_wh", None)
        d.setdefault("recebidas_wh", None)
        d.setdefault("enviadas_wh", None)
        d.setdefault("renov_reais", 0.0)
        # QUEM_WEBHOOK_0810: "quem atendeu" agora sai do registro do webhook (completo), em CLIENTES:
        # Robô = clientes que receberam resposta do robô; pessoas = atendente atribuído no DataCrazy.
        # O antigo (autor no espelho, parcial) fica em quem_espelho, só para conferência.
        d["quem_espelho"] = sorted(d.pop("pessoas").items(), key=lambda x: -x[1])
        d.setdefault("robo_clientes", None)
        d.setdefault("atribuido", [])
        d.setdefault("sem_atendente", None)
        d["quem"] = ([["Robô", d["robo_clientes"]]] if d["robo_clientes"] else []) + [list(x) for x in d["atribuido"]]
        lista.append(d)
    estado["por_numero"] = lista
    estado["por_numero_ok"] = bool(por_num_met)
    global _AVISADO
    if lista and not _AVISADO:
        _AVISADO = True
        import logging

        logging.getLogger("painel").warning(
            "início 08/10 pronto: renov %s / R$ %.2f | sem resposta %s | por número: %s", fin.get("n"), fin.get("reais") or 0, sr,
            "; ".join(f"{d['numero']}: conv {d['conversas']} conv_wh {d['conversas_wh']} sr {d['sem_resposta']} renov {d['renov_n']} quem {d['quem'][:4]} espelho {d['quem_espelho'][:3]}" for d in lista),
        )
