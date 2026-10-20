"""Agregação Atendimento (F3): funil + tempos de resposta."""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any

from app.core.states import MetricEnvelope, SourceRef
from app.core.timezone import TZ_NAME, agora, iso_bahia, janela_periodo, telefone_final
from app.sources import espelho, seed

# Estágios operacionais — SEM rótulo "abandonado"
FUNIL_STAGES = (
    ("novo", "Novo"),
    ("em_atendimento", "Em atendimento"),
    ("aguardando", "Aguardando cliente"),
    ("resolvido", "Resolvido"),
)


def _seed_atendimento() -> dict[str, Any]:
    stamp = iso_bahia(agora())
    src = SourceRef(id="seed", label="Seed F3", last_update=stamp)
    funil = {
        "stages": [
            {"id": "novo", "label": "Novo", "n": 18},
            {"id": "em_atendimento", "label": "Em atendimento", "n": 42},
            {"id": "aguardando", "label": "Aguardando cliente", "n": 27},
            {"id": "resolvido", "label": "Resolvido", "n": 156},
        ],
        "total": 243,
    }
    gaps = [12, 18, 25, 40, 55, 90, 120, 180, 240, 400]
    tempos = {
        "media": round(statistics.mean(gaps), 1),
        "mediana": statistics.median(gaps),
        "p95": sorted(gaps)[max(0, int(len(gaps) * 0.95) - 1)],
        "max": max(gaps),
        "n": len(gaps),
        "unidade": "s",
    }
    return {
        "is_seed": True,
        "funil": MetricEnvelope.ok(funil, metric_id="atendimento.funil", window="hoje", source=src, is_seed=True).model_dump(),
        "tempos": {
            "media": MetricEnvelope.ok(tempos["media"], metric_id="atendimento.t_resposta_media", window="hoje", source=src, is_seed=True).model_dump(),
            "mediana": MetricEnvelope.ok(tempos["mediana"], metric_id="atendimento.t_resposta_mediana", window="hoje", source=src, is_seed=True).model_dump(),
            "p95": MetricEnvelope.ok(tempos["p95"], metric_id="atendimento.t_resposta_p95", window="hoje", source=src, is_seed=True).model_dump(),
            "max": MetricEnvelope.ok(tempos["max"], metric_id="atendimento.t_resposta_max", window="hoje", source=src, is_seed=True).model_dump(),
            "resumo": tempos,
        },
        "atual_vs_historico": {
            "atual": tempos,
            "historico_7d": {"media": 88.0, "mediana": 52.0, "p95": 310.0, "max": 520.0, "n": 980},
        },
        "drill_funil": {
            "novo": [
                {"conversation_id": "s1", "phone_final": "final 9433", "stage": "novo", "espera_min": 2.1},
                {"conversation_id": "s2", "phone_final": "final 1204", "stage": "novo", "espera_min": 0.5},
            ],
            "em_atendimento": [
                {"conversation_id": "s3", "phone_final": "final 7781", "stage": "em_atendimento", "atendente": "Robô"},
            ],
            "aguardando": [
                {"conversation_id": "s4", "phone_final": "final 3344", "stage": "aguardando"},
            ],
            "resolvido": [
                {"conversation_id": "s5", "phone_final": "final 5566", "stage": "resolvido"},
            ],
        },
        "gaps_sample": [
            {"conversation_id": "s3", "phone_final": "final 7781", "gap_s": g, "ts": stamp}
            for g in gaps
        ],
    }


def _events_in_window(ini_ts: float, fim_ts: float) -> list[dict[str, Any]]:
    eventos = espelho.eventos_recentes(max_lines=8000)
    out = []
    for e in eventos:
        ts = e.get("ts")
        if ts is None:
            continue
        t = float(ts)
        if ini_ts <= t < fim_ts:
            out.append(e)
    return out


def _classify_stage(st: dict[str, Any], now: float) -> str:
    """Classifica conversa em estágio operacional (sem abandonado)."""
    last_in = st.get("last_in")
    last_out = st.get("last_out")
    first_seen = st.get("first_seen")
    if last_in is None and last_out is None:
        return "novo"
    # resolvido: última atividade outbound e silêncio do cliente > 30 min
    if last_out is not None and (last_in is None or last_out >= last_in):
        age_out = now - float(last_out)
        if age_out > 30 * 60:
            return "resolvido"
        # outbound recente esperando cliente
        return "aguardando"
    # cliente falou por último
    if last_in is not None and (last_out is None or last_in > last_out):
        # se nunca houve outbound e fala recente → novo
        if last_out is None and first_seen and (now - float(first_seen)) < 15 * 60:
            return "novo"
        return "em_atendimento"
    return "em_atendimento"


def _build_conversation_state(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    for e in sorted(events, key=lambda x: float(x.get("ts") or 0)):
        cid = str(e.get("conversation_id") or "")
        if not cid:
            continue
        st = state.setdefault(
            cid,
            {
                "last_in": None,
                "last_out": None,
                "first_seen": e.get("ts"),
                "phone_final": e.get("phone_final"),
                "name": e.get("name"),
                "instance": e.get("instance"),
                "instance_id": e.get("instance_id"),
                "instance_phone": e.get("instance_phone"),
                "evento": e.get("evento"),
                "msgs": [],
            },
        )
        ts = e.get("ts")
        if ts is None:
            continue
        st["msgs"].append(e)
        inst_novo = str(e.get("instance") or "").strip()
        atual = str(st.get("instance") or "").strip()
        baixo_atual = atual.casefold().replace(".", " ")
        lixo = {
            "",
            "message sent",
            "message received",
            "sent",
            "received",
            "true",
            "false",
        }
        if inst_novo and (baixo_atual in lixo or not atual):
            st["instance"] = inst_novo
        if e.get("instance_id"):
            st["instance_id"] = e.get("instance_id")
        if e.get("instance_phone"):
            st["instance_phone"] = e.get("instance_phone")
        if e.get("evento") and (
            not st.get("evento")
            or str(st.get("evento")).casefold().replace(".", " ") in lixo
        ):
            st["evento"] = e.get("evento")
        if st["first_seen"] is None or float(ts) < float(st["first_seen"]):
            st["first_seen"] = ts
        if e.get("from_me"):
            if st["last_out"] is None or ts > st["last_out"]:
                st["last_out"] = ts
        else:
            if st["last_in"] is None or ts > st["last_in"]:
                st["last_in"] = ts
                st["phone_final"] = e.get("phone_final") or st["phone_final"]
                st["name"] = e.get("name") or st["name"]
    return state


def _response_gaps(msgs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Agrupa msgs seguidas do mesmo lado; gap = 1ª resposta - última msg do bloco cliente."""
    if not msgs:
        return []
    ordered = sorted(msgs, key=lambda m: float(m.get("ts") or 0))
    # comprimir blocos
    blocks: list[dict[str, Any]] = []
    for m in ordered:
        side = "out" if m.get("from_me") else "in"
        ts = float(m.get("ts") or 0)
        if not blocks or blocks[-1]["side"] != side:
            blocks.append({"side": side, "start": ts, "end": ts, "n": 1})
        else:
            blocks[-1]["end"] = ts
            blocks[-1]["n"] += 1

    gaps: list[dict[str, Any]] = []
    for i, b in enumerate(blocks):
        if b["side"] != "in":
            continue
        # próxima resposta outbound
        nxt = None
        for j in range(i + 1, len(blocks)):
            if blocks[j]["side"] == "out":
                nxt = blocks[j]
                break
        if not nxt:
            continue
        gap = nxt["start"] - b["end"]
        if gap < 0:
            continue
        gaps.append({"gap_s": round(gap, 1), "from_block_end": b["end"], "to_reply": nxt["start"]})
    return gaps


def _percentile(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _tempos_from_gaps(gap_rows: list[dict[str, Any]]) -> dict[str, Any]:
    vals = [float(g["gap_s"]) for g in gap_rows if g.get("gap_s") is not None]
    if not vals:
        return {"media": None, "mediana": None, "p95": None, "max": None, "n": 0, "unidade": "s"}
    vals_sorted = sorted(vals)
    return {
        "media": round(statistics.mean(vals), 1),
        "mediana": round(statistics.median(vals), 1),
        "p95": round(_percentile(vals_sorted, 0.95) or 0, 1),
        "max": round(max(vals), 1),
        "n": len(vals),
        "unidade": "s",
    }


def montar_atendimento(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    filters = filters or {}
    periodo = str(filters.get("periodo") or "hoje")
    ini, fim, rotulo = janela_periodo(periodo)

    if seed.seed_habilitado():
        s = _seed_atendimento()
        return {
            "ok": True,
            "phase": "F3",
            "timezone": TZ_NAME,
            "window": {"inicio": iso_bahia(ini), "fim": iso_bahia(fim), "label": rotulo},
            "is_seed": True,
            "funil": s["funil"],
            "tempos": s["tempos"],
            "atual_vs_historico": s["atual_vs_historico"],
            "computed_at": iso_bahia(agora()),
        }

    if not espelho.WEBHOOK_QUEUE.is_file():
        unavail = MetricEnvelope.unavailable(
            "Fila webhook indisponível — atendimento sem GET DataCrazy",
            source=SourceRef(id="webhook_queue", label="webhook queue.jsonl", last_update=None),
            metric_id="atendimento.funil",
        )
        empty_t = MetricEnvelope.unavailable(
            "Sem fonte para tempos de resposta",
            source=unavail.source,
            metric_id="atendimento.t_resposta_media",
        )
        return {
            "ok": True,
            "phase": "F3",
            "timezone": TZ_NAME,
            "window": {"inicio": iso_bahia(ini), "fim": iso_bahia(fim), "label": rotulo},
            "is_seed": False,
            "funil": unavail.model_dump(),
            "tempos": {
                "media": empty_t.model_dump(),
                "mediana": {**empty_t.model_dump(), "metric_id": "atendimento.t_resposta_mediana"},
                "p95": {**empty_t.model_dump(), "metric_id": "atendimento.t_resposta_p95"},
                "max": {**empty_t.model_dump(), "metric_id": "atendimento.t_resposta_max"},
                "resumo": {"media": None, "mediana": None, "p95": None, "max": None, "n": 0},
            },
            "atual_vs_historico": {"atual": None, "historico_7d": None},
            "computed_at": iso_bahia(agora()),
        }

    now = agora().timestamp()
    events = _events_in_window(ini.timestamp(), fim.timestamp())
    # também usa eventos recentes fora da janela civil se período=hoje e fila curta
    if not events and periodo == "hoje":
        events = espelho.eventos_recentes(max_lines=8000)

    state = _build_conversation_state(events)
    numero = filters.get("numero")
    if numero:
        state = {
            k: v
            for k, v in state.items()
            if str(numero) in str(v.get("instance") or "")
        }

    buckets: dict[str, list[dict[str, Any]]] = {sid: [] for sid, _ in FUNIL_STAGES}
    all_gaps: list[dict[str, Any]] = []
    for cid, st in state.items():
        stage = _classify_stage(st, now)
        row = {
            "conversation_id": cid,
            "phone_final": st.get("phone_final") or telefone_final(None),
            "name": st.get("name"),
            "instance": st.get("instance"),
            "stage": stage,
        }
        buckets.setdefault(stage, []).append(row)
        for g in _response_gaps(st.get("msgs") or []):
            all_gaps.append(
                {
                    **g,
                    "conversation_id": cid,
                    "phone_final": row["phone_final"],
                    "instance": st.get("instance"),
                }
            )

    stages = [
        {"id": sid, "label": label, "n": len(buckets.get(sid, []))}
        for sid, label in FUNIL_STAGES
    ]
    total = sum(s["n"] for s in stages)
    src = SourceRef(id="webhook_queue", label="webhook queue.jsonl", last_update=iso_bahia(agora()))
    funil_env = (
        MetricEnvelope.ok(
            {"stages": stages, "total": total},
            metric_id="atendimento.funil",
            window=rotulo,
            source=src,
        )
        if total > 0
        else MetricEnvelope.empty(
            "Nenhuma conversa no período (webhook)",
            metric_id="atendimento.funil",
            window=rotulo,
            source=src,
        )
    )

    tempos = _tempos_from_gaps(all_gaps)
    if tempos["n"] == 0:
        t_media = MetricEnvelope.empty("Sem gaps de resposta no período", metric_id="atendimento.t_resposta_media", source=src, window=rotulo)
        t_med = MetricEnvelope.empty("Sem gaps de resposta no período", metric_id="atendimento.t_resposta_mediana", source=src, window=rotulo)
        t_p95 = MetricEnvelope.empty("Sem gaps de resposta no período", metric_id="atendimento.t_resposta_p95", source=src, window=rotulo)
        t_max = MetricEnvelope.empty("Sem gaps de resposta no período", metric_id="atendimento.t_resposta_max", source=src, window=rotulo)
    else:
        t_media = MetricEnvelope.ok(tempos["media"], metric_id="atendimento.t_resposta_media", window=rotulo, source=src)
        t_med = MetricEnvelope.ok(tempos["mediana"], metric_id="atendimento.t_resposta_mediana", window=rotulo, source=src)
        t_p95 = MetricEnvelope.ok(tempos["p95"], metric_id="atendimento.t_resposta_p95", window=rotulo, source=src)
        t_max = MetricEnvelope.ok(tempos["max"], metric_id="atendimento.t_resposta_max", window=rotulo, source=src)

    # histórico 7d (mesma fonte, janela maior)
    ini7, fim7, _ = janela_periodo("7d")
    ev7 = _events_in_window(ini7.timestamp(), fim7.timestamp())
    st7 = _build_conversation_state(ev7)
    gaps7: list[dict[str, Any]] = []
    for st in st7.values():
        gaps7.extend(_response_gaps(st.get("msgs") or []))
    hist = _tempos_from_gaps(gaps7)

    # stash for drilldown
    montar_atendimento._cache = {  # type: ignore[attr-defined]
        "buckets": buckets,
        "gaps": all_gaps,
        "rotulo": rotulo,
    }

    return {
        "ok": True,
        "phase": "F3",
        "timezone": TZ_NAME,
        "window": {"inicio": iso_bahia(ini), "fim": iso_bahia(fim), "label": rotulo},
        "is_seed": False,
        "funil": funil_env.model_dump(),
        "tempos": {
            "media": t_media.model_dump(),
            "mediana": t_med.model_dump(),
            "p95": t_p95.model_dump(),
            "max": t_max.model_dump(),
            "resumo": tempos,
        },
        "atual_vs_historico": {"atual": tempos, "historico_7d": hist},
        "computed_at": iso_bahia(agora()),
    }


def drill_atendimento(metric_id: str, page: int, page_size: int, stage: str | None = None) -> dict[str, Any]:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)

    if seed.seed_habilitado():
        s = _seed_atendimento()
        if metric_id == "atendimento.funil":
            sid = stage or "novo"
            rows = s["drill_funil"].get(sid) or []
        else:
            rows = s["gaps_sample"]
        total = len(rows)
        start = (page - 1) * page_size
        return {
            "total": total,
            "rows": rows[start : start + page_size],
            "state": MetricEnvelope.ok(rows, metric_id=metric_id, is_seed=True).model_dump(),
        }

    cache = getattr(montar_atendimento, "_cache", None)
    if not cache:
        # rebuild lightly
        montar_atendimento({"periodo": "hoje"})
        cache = getattr(montar_atendimento, "_cache", {"buckets": {}, "gaps": []})

    if metric_id == "atendimento.funil":
        sid = stage or "em_atendimento"
        rows = list((cache.get("buckets") or {}).get(sid) or [])
    else:
        rows = list(cache.get("gaps") or [])
        rows.sort(key=lambda r: float(r.get("gap_s") or 0), reverse=True)

    total = len(rows)
    start = (page - 1) * page_size
    slice_rows = rows[start : start + page_size]
    state = (
        MetricEnvelope.ok(slice_rows, metric_id=metric_id)
        if slice_rows
        else MetricEnvelope.empty("Sem linhas", metric_id=metric_id)
    )
    return {"total": total, "rows": slice_rows, "state": state.model_dump()}
