"""Agregação Robô/IA F6 — nomes claros + tooltips do registro."""

from __future__ import annotations

import re
from typing import Any

from app.core.metrics_registry import get_metric, list_metrics
from app.core.states import MetricEnvelope, SourceRef
from app.core.timezone import TZ_NAME, agora, iso_bahia, janela_periodo
from app.sources import espelho, seed

_ENVIO_RE = re.compile(r"\b(ENVIO|enviou|send(ed)?|outbound)\b", re.IGNORECASE)


def _seed() -> dict[str, Any]:
    stamp = iso_bahia(agora())
    src = SourceRef(id="seed", label="Seed F6", last_update=stamp)
    return {
        "ocupadas": MetricEnvelope.ok(
            {"n": 2, "label_claro": "Conversas que o robô está olhando agora"},
            metric_id="robo.ocupadas",
            window="agora",
            source=src,
            is_seed=True,
        ).model_dump(),
        "envios": MetricEnvelope.ok(
            {"n": 186, "label_claro": "Mensagens que o robô enviou hoje"},
            metric_id="robo.envios",
            window="hoje",
            source=src,
            is_seed=True,
        ).model_dump(),
        "aguardando_poll": MetricEnvelope.ok(
            {"n": 5, "label_claro": "Fila real do robô (POLL aguardando)"},
            metric_id="robo.ocupadas",
            window="agora",
            source=src,
            is_seed=True,
        ).model_dump(),
        "catalogo": [
            {
                "id": m.id,
                "name": m.name,
                "definition": m.definition,
                "formula": m.formula,
                "source": m.source,
            }
            for m in list_metrics("robo")
        ],
    }


def montar_robo(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    filters = filters or {}
    periodo = str(filters.get("periodo") or "hoje")
    ini, fim, rotulo = janela_periodo(periodo)

    if seed.seed_habilitado():
        s = _seed()
        return {
            "ok": True,
            "phase": "F6",
            "timezone": TZ_NAME,
            "window": {"inicio": iso_bahia(ini), "fim": iso_bahia(fim), "label": rotulo},
            "is_seed": True,
            **s,
            "computed_at": iso_bahia(agora()),
        }

    src_log = SourceRef(id="live_log", label="live.log", last_update=None)
    poll = espelho.parse_poll_from_log()
    if poll:
        src_log.last_update = iso_bahia(agora())
        ocupadas = MetricEnvelope.ok(
            {
                "n": poll.get("ocupadas"),
                "label_claro": "Conversas que o robô está olhando agora",
                "linha": poll.get("line"),
            },
            metric_id="robo.ocupadas",
            window="agora",
            source=src_log,
        )
        aguardando = MetricEnvelope.ok(
            {
                "n": poll.get("aguardando"),
                "label_claro": "Clientes na fila do robô (POLL)",
                "linha": poll.get("line"),
            },
            metric_id="robo.ocupadas",
            window="agora",
            source=src_log,
        )
    else:
        log = espelho.tail_live_log(5)
        if log.state.value == "unavailable":
            ocupadas = MetricEnvelope.unavailable(
                "Log do robô indisponível — não inventar ocupadas=0",
                source=src_log,
                metric_id="robo.ocupadas",
            )
            aguardando = MetricEnvelope.unavailable(
                "POLL aguardando indisponível",
                source=src_log,
                metric_id="robo.ocupadas",
            )
        else:
            ocupadas = MetricEnvelope.empty(
                "Ainda não vi linha POLL no live.log",
                metric_id="robo.ocupadas",
                source=src_log,
            )
            aguardando = ocupadas

    # Envios: conta outbound no webhook no período
    src_q = SourceRef(id="webhook_queue", label="webhook queue.jsonl", last_update=None)
    if not espelho.WEBHOOK_QUEUE.is_file():
        # fallback: contar ENVIO no log
        env = espelho.tail_live_log(400)
        if env.state.value == "ok" and isinstance(env.value, list):
            n = sum(1 for r in env.value if _ENVIO_RE.search(str(r.get("line") or "")))
            src_log.last_update = iso_bahia(agora())
            envios = MetricEnvelope.ok(
                {"n": n, "label_claro": "Envios recentes vistos no log (amostra)", "amostra": True},
                metric_id="robo.envios",
                window=rotulo,
                source=src_log,
            )
        else:
            envios = MetricEnvelope.unavailable(
                "Não dá para contar envios do robô",
                source=src_q,
                metric_id="robo.envios",
            )
    else:
        n = 0
        for e in espelho.eventos_recentes(max_lines=8000):
            if not e.get("from_me"):
                continue
            ts = e.get("ts")
            if ts is None:
                continue
            if ini.timestamp() <= float(ts) < fim.timestamp():
                n += 1
        src_q.last_update = iso_bahia(agora())
        envios = MetricEnvelope.ok(
            {"n": n, "label_claro": "Mensagens enviadas (outbound) no período"},
            metric_id="robo.envios",
            window=rotulo,
            source=src_q,
        )

    catalogo = []
    for m in list_metrics("robo"):
        catalogo.append(
            {
                "id": m.id,
                "name": m.name,
                "definition": m.definition,
                "formula": m.formula,
                "source": m.source,
                "tooltip_ok": True,
            }
        )

    return {
        "ok": True,
        "phase": "F6",
        "timezone": TZ_NAME,
        "window": {"inicio": iso_bahia(ini), "fim": iso_bahia(fim), "label": rotulo},
        "is_seed": False,
        "ocupadas": ocupadas.model_dump(),
        "envios": envios.model_dump(),
        "aguardando_poll": aguardando.model_dump(),
        "catalogo": catalogo,
        "computed_at": iso_bahia(agora()),
    }


def drill_robo(metric_id: str, page: int, page_size: int) -> dict[str, Any]:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    m = get_metric(metric_id)
    rows = []
    if seed.seed_habilitado():
        s = _seed()
        if metric_id == "robo.envios":
            rows = [{"n": s["envios"]["value"]["n"], "label": s["envios"]["value"]["label_claro"]}]
        else:
            rows = [{"n": s["ocupadas"]["value"]["n"], "label": s["ocupadas"]["value"]["label_claro"]}]
    else:
        out = montar_robo({"periodo": "hoje"})
        key = "envios" if metric_id == "robo.envios" else "ocupadas"
        val = out.get(key, {}).get("value")
        rows = [val] if val else []
    if m:
        rows = [{"registro": m.model_dump(), "valor": r} for r in rows]
    total = len(rows)
    start = (page - 1) * page_size
    return {
        "total": total,
        "rows": rows[start : start + page_size],
        "state": MetricEnvelope.ok(rows, metric_id=metric_id, is_seed=seed.seed_habilitado()).model_dump(),
    }
