"""Agregação Operação F5 — problemas × ontem/7d + correlações."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from app.core.states import MetricEnvelope, SourceRef
from app.core.timezone import TZ, TZ_NAME, agora, inicio_dia, iso_bahia, janela_periodo, hoje
from app.sources import espelho, seed

_PROBLEMA_RE = re.compile(
    r"(erro|falha|travou|travad|n[aã]o\s*abre|sem\s*sinal|buffer|problema|bug|offline|caiu)",
    re.IGNORECASE,
)
_APP_RE = re.compile(
    r"\b(max\s*player|ibo\s*player|brasil\s*iptv|ss\s*iptv|iptv\s*smarters|xc\s*iptv|lavie|downloader)\b",
    re.IGNORECASE,
)
_APARELHO_RE = re.compile(
    r"\b(samsung|lg|fire\s*stick|firestick|android|tv\s*box|iphone|xiaomi|roku|philips|tcl)\b",
    re.IGNORECASE,
)


def _seed() -> dict[str, Any]:
    stamp = iso_bahia(agora())
    src = SourceRef(id="seed", label="Seed F5", last_update=stamp)
    problemas = {
        "hoje": 14,
        "ontem": 11,
        "media_7d": 12.4,
        "delta_ontem": 3,
        "delta_media_7d": 1.6,
    }
    corr = {
        "por_app": [{"app": "Max Player", "n": 6}, {"app": "IBO Player", "n": 4}, {"app": "Brasil IPTV", "n": 3}],
        "por_aparelho": [{"aparelho": "Samsung", "n": 5}, {"aparelho": "Fire Stick", "n": 4}, {"aparelho": "LG", "n": 3}],
        "por_hora": [{"hora": h, "n": (h % 5) + 1} for h in range(8, 23)],
        "cruzamentos": [
            {"app": "Max Player", "aparelho": "Samsung", "hora": 20, "n": 3},
            {"app": "IBO Player", "aparelho": "Fire Stick", "hora": 19, "n": 2},
        ],
    }
    return {
        "problemas": MetricEnvelope.ok(problemas, metric_id="operacao.problemas", window="hoje", source=src, is_seed=True).model_dump(),
        "correlacoes": MetricEnvelope.ok(corr, metric_id="operacao.correlacoes", window="hoje", source=src, is_seed=True).model_dump(),
        "apps": MetricEnvelope.ok(corr["por_app"], metric_id="operacao.correlacoes", window="hoje", source=src, is_seed=True).model_dump(),
        "aparelhos": MetricEnvelope.ok(corr["por_aparelho"], metric_id="operacao.correlacoes", window="hoje", source=src, is_seed=True).model_dump(),
        "utra_lg": MetricEnvelope.ok(
            {
                "titulo": "UTRA na LG",
                "total": 0,
                "taxa_sucesso": None,
                "taxa_xc_account": None,
                "taxa_falha": None,
                "utra_ok": 0,
                "utra_xc_account": 0,
                "outro_erro": 0,
                "modelos_xc_account": [],
                "alerta_pendente": False,
                "min_n": 20,
                "limiar_falha": 0.5,
                "atualizado_em": stamp,
            },
            metric_id="operacao.utra_lg",
            window="hoje",
            source=src,
            is_seed=True,
        ).model_dump(),
    }


def _day_bounds(offset: int = 0) -> tuple[float, float]:
    d = hoje()
    from datetime import timedelta

    day = d - timedelta(days=offset)
    ini = inicio_dia(day).timestamp()
    fim = ini + 86400
    return ini, fim


def _scan_problemas() -> list[dict[str, Any]]:
    rows = []
    for e in espelho.eventos_recentes(max_lines=8000):
        if e.get("from_me"):
            continue
        text = str(e.get("text") or "")
        if not text or not _PROBLEMA_RE.search(text):
            continue
        ts = e.get("ts")
        if ts is None:
            continue
        app_m = _APP_RE.search(text)
        ap_m = _APARELHO_RE.search(text)
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc).astimezone(TZ)
        rows.append(
            {
                "conversation_id": e.get("conversation_id"),
                "phone_final": e.get("phone_final"),
                "text": text[:180],
                "ts": float(ts),
                "hora": dt.hour,
                "app": app_m.group(0).title() if app_m else None,
                "aparelho": ap_m.group(0).title() if ap_m else None,
                "instance": e.get("instance"),
            }
        )
    return rows


def montar_operacao(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    filters = filters or {}
    periodo = str(filters.get("periodo") or "hoje")
    ini, fim, rotulo = janela_periodo(periodo)

    if seed.seed_habilitado():
        s = _seed()
        return {
            "ok": True,
            "phase": "F5",
            "timezone": TZ_NAME,
            "window": {"inicio": iso_bahia(ini), "fim": iso_bahia(fim), "label": rotulo},
            "is_seed": True,
            **s,
            "computed_at": iso_bahia(agora()),
        }

    src = SourceRef(id="webhook_queue", label="webhook queue.jsonl", last_update=None)
    if not espelho.WEBHOOK_QUEUE.is_file():
        un = MetricEnvelope.unavailable(
            "Operação sem fila webhook — zero GET DataCrazy",
            source=src,
            metric_id="operacao.problemas",
        )
        return {
            "ok": True,
            "phase": "F5",
            "timezone": TZ_NAME,
            "window": {"inicio": iso_bahia(ini), "fim": iso_bahia(fim), "label": rotulo},
            "is_seed": False,
            "problemas": un.model_dump(),
            "correlacoes": MetricEnvelope.unavailable(
                "Correlações indisponíveis", source=src, metric_id="operacao.correlacoes"
            ).model_dump(),
            "apps": MetricEnvelope.unavailable("Apps indisponíveis", source=src).model_dump(),
            "aparelhos": MetricEnvelope.unavailable("Aparelhos indisponíveis", source=src).model_dump(),
            "utra_lg": MetricEnvelope.unavailable(
                "UTRA×LG sem fila", source=src, metric_id="operacao.utra_lg"
            ).model_dump(),
            "computed_at": iso_bahia(agora()),
        }

    rows = _scan_problemas()
    src.last_update = iso_bahia(agora())
    numero = filters.get("numero")
    if numero:
        rows = [r for r in rows if str(numero) in str(r.get("instance") or "")]

    hoje_ini, hoje_fim = _day_bounds(0)
    ontem_ini, ontem_fim = _day_bounds(1)

    def count_between(a: float, b: float) -> int:
        return sum(1 for r in rows if a <= r["ts"] < b)

    n_hoje = count_between(hoje_ini, hoje_fim)
    n_ontem = count_between(ontem_ini, ontem_fim)
    last7 = [count_between(*_day_bounds(i)) for i in range(0, 7)]
    media_7d = round(sum(last7) / 7.0, 1) if last7 else 0.0

    problemas = {
        "hoje": n_hoje,
        "ontem": n_ontem,
        "media_7d": media_7d,
        "delta_ontem": n_hoje - n_ontem,
        "delta_media_7d": round(n_hoje - media_7d, 1),
    }

    # Correlações no período selecionado
    in_period = [r for r in rows if ini.timestamp() <= r["ts"] < fim.timestamp()]
    if not in_period and periodo == "hoje":
        in_period = [r for r in rows if hoje_ini <= r["ts"] < hoje_fim]

    app_c: Counter[str] = Counter()
    ap_c: Counter[str] = Counter()
    hora_c: Counter[int] = Counter()
    cruz: Counter[tuple[str, str, int]] = Counter()
    for r in in_period:
        app = r.get("app") or "Não informado"
        ap = r.get("aparelho") or "Não informado"
        h = int(r.get("hora") or 0)
        app_c[app] += 1
        ap_c[ap] += 1
        hora_c[h] += 1
        cruz[(app, ap, h)] += 1

    corr = {
        "por_app": [{"app": k, "n": v} for k, v in app_c.most_common(12)],
        "por_aparelho": [{"aparelho": k, "n": v} for k, v in ap_c.most_common(12)],
        "por_hora": [{"hora": h, "n": hora_c[h]} for h in sorted(hora_c)],
        "cruzamentos": [
            {"app": a, "aparelho": p, "hora": h, "n": n}
            for (a, p, h), n in cruz.most_common(20)
        ],
    }

    montar_operacao._cache = {"rows": in_period, "all": rows}  # type: ignore[attr-defined]

    if not rows:
        prob_env = MetricEnvelope.empty(
            "Nenhum problema detectado no texto inbound recente",
            metric_id="operacao.problemas",
            source=src,
            window=rotulo,
        )
        corr_env = MetricEnvelope.empty("Sem correlações", metric_id="operacao.correlacoes", source=src, window=rotulo)
    else:
        prob_env = MetricEnvelope.ok(problemas, metric_id="operacao.problemas", window=rotulo, source=src)
        corr_env = MetricEnvelope.ok(corr, metric_id="operacao.correlacoes", window=rotulo, source=src)

    utra_env = _utra_lg_envelope(src, rotulo)

    return {
        "ok": True,
        "phase": "F5",
        "timezone": TZ_NAME,
        "window": {"inicio": iso_bahia(ini), "fim": iso_bahia(fim), "label": rotulo},
        "is_seed": False,
        "problemas": prob_env.model_dump(),
        "correlacoes": corr_env.model_dump(),
        "apps": MetricEnvelope.ok(corr["por_app"], metric_id="operacao.correlacoes", window=rotulo, source=src).model_dump()
        if corr["por_app"]
        else MetricEnvelope.empty("Sem apps nos textos", source=src).model_dump(),
        "aparelhos": MetricEnvelope.ok(corr["por_aparelho"], metric_id="operacao.correlacoes", window=rotulo, source=src).model_dump()
        if corr["por_aparelho"]
        else MetricEnvelope.empty("Sem aparelhos nos textos", source=src).model_dump(),
        "utra_lg": utra_env.model_dump(),
        "computed_at": iso_bahia(agora()),
    }


def _utra_lg_envelope(src: SourceRef, rotulo: str):
    """Taxa UTRA na LG — CSV do robô (utra_lg_metrica). Não muda ordem sozinho."""
    try:
        import sys
        from pathlib import Path

        for cand in (
            Path("/opt/mnrobo/atendimento/ai"),
            Path("/workspace/atendimento/ai"),
            Path(__file__).resolve().parents[4] / "atendimento" / "ai",
        ):
            if cand.is_dir() and str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
        import utra_lg_metrica as ULM  # type: ignore

        payload = ULM.painel_payload()
        return MetricEnvelope.ok(payload, metric_id="operacao.utra_lg", window=rotulo, source=src)
    except Exception as exc:
        return MetricEnvelope.unavailable(
            f"UTRA×LG indisponível: {exc}",
            source=src,
            metric_id="operacao.utra_lg",
        )


def drill_operacao(metric_id: str, page: int, page_size: int) -> dict[str, Any]:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    if seed.seed_habilitado():
        s = _seed()
        if metric_id == "operacao.correlacoes":
            rows = (s["correlacoes"]["value"] or {}).get("cruzamentos") or []
        else:
            rows = [{"hoje": 14, "ontem": 11, "media_7d": 12.4}]
        total = len(rows)
        start = (page - 1) * page_size
        return {
            "total": total,
            "rows": rows[start : start + page_size],
            "state": MetricEnvelope.ok(rows, metric_id=metric_id, is_seed=True).model_dump(),
        }
    cache = getattr(montar_operacao, "_cache", None) or {}
    rows = list(cache.get("rows") or [])
    total = len(rows)
    start = (page - 1) * page_size
    slice_rows = rows[start : start + page_size]
    return {
        "total": total,
        "rows": slice_rows,
        "state": (
            MetricEnvelope.ok(slice_rows, metric_id=metric_id)
            if slice_rows
            else MetricEnvelope.empty("Sem linhas", metric_id=metric_id)
        ).model_dump(),
    }
