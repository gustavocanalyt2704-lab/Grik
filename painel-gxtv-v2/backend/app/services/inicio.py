"""Agregação do módulo Início (F2)."""

from __future__ import annotations

from typing import Any

from app.core.states import MetricEnvelope
from app.core.timezone import TZ_NAME, agora, iso_bahia, janela_periodo
from app.services import numeros as numeros_svc
from app.services.numeros import rotulo_instancia
from app.sources import espelho, gestor, seed


async def montar_inicio(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    filters = filters or {}
    periodo = str(filters.get("periodo") or "hoje")
    ini, fim, rotulo = janela_periodo(periodo)

    if seed.seed_habilitado():
        s = seed.seed_inicio()
        bloco_numeros = await numeros_svc.montar_numeros(filters)
        return {
            "ok": True,
            "phase": "F2",
            "timezone": TZ_NAME,
            "window": {"inicio": iso_bahia(ini), "fim": iso_bahia(fim), "label": rotulo},
            "is_seed": True,
            "kpis": s["kpis"],
            "entrada_viva": s["entrada_viva"],
            "log_operacional": s["log_operacional"],
            "saude_espelho": s["saude_espelho"],
            "numeros": bloco_numeros,
            "computed_at": iso_bahia(agora()),
        }

    gest = await gestor.fetch_kpis_comerciais()
    bloco_numeros = await numeros_svc.montar_numeros(filters, gest=gest)
    fat = gestor.extrair_kpi(gest, "faturamento")
    renov = gestor.extrair_kpi(gest, "renovacoes")
    vencem_raw = gestor.extrair_kpi(gest, "vencem_hoje")

    # Envelope rico de vencem hoje (total/renovaram/pendentes)
    if gest.state.value in ("ok", "stale") and isinstance(gest.value, dict):
        vencem_val = {
            "total": gest.value.get("vencem_hoje"),
            "renovaram": gest.value.get("vencem_hoje_renovaram"),
            "pendentes": gest.value.get("vencem_hoje_pendentes"),
        }
        if vencem_raw.state.value == "stale":
            vencem = MetricEnvelope.stale(
                vencem_val,
                gest.message or "Cache Gestor atrasado",
                source=gest.source,
                metric_id="inicio.vencem_hoje",
                window="hoje",
            )
        else:
            vencem = MetricEnvelope.ok(
                vencem_val,
                metric_id="inicio.vencem_hoje",
                window="hoje",
                source=gest.source,
            )
    else:
        vencem = vencem_raw
        if isinstance(vencem.value, (int, float)):
            vencem = MetricEnvelope(
                state=vencem.state,
                value={"total": vencem.value, "renovaram": None, "pendentes": None},
                message=vencem.message,
                source=vencem.source,
                metric_id="inicio.vencem_hoje",
                window="hoje",
            )

    atendidos = espelho.atendidos_hoje()
    esperando = espelho.esperando_acima_de(15)
    clientes_min = espelho.clientes_por_minuto(600)
    entrada = espelho.entrada_ao_vivo(300, 40)
    log = espelho.tail_live_log(50)
    saude = espelho.saude_espelho()

    # filtro WhatsApp (numero) na entrada/espera quando informado
    numero = filters.get("numero")
    if numero and entrada.state.value == "ok" and isinstance(entrada.value, list):
        filtrados = [
            r
            for r in entrada.value
            if rotulo_instancia(r.get("instance")) == str(numero)
            or str(numero) in str(r.get("instance") or "")
        ]
        entrada = MetricEnvelope.ok(
            filtrados,
            metric_id="inicio.entrada_viva",
            window=entrada.window,
            source=entrada.source,
        ) if filtrados else MetricEnvelope.empty(
            f"Nenhuma entrada no WhatsApp {numero}",
            metric_id="inicio.entrada_viva",
            source=entrada.source,
            window=entrada.window,
        )

    return {
        "ok": True,
        "phase": "F2",
        "timezone": TZ_NAME,
        "window": {"inicio": iso_bahia(ini), "fim": iso_bahia(fim), "label": rotulo},
        "is_seed": False,
        "kpis": {
            "faturamento": fat.model_dump(),
            "renovacoes": renov.model_dump(),
            "vencem_hoje": vencem.model_dump(),
            "atendidos": atendidos.model_dump(),
            "esperando_15min": esperando.model_dump(),
            "clientes_min": clientes_min.model_dump(),
        },
        "entrada_viva": entrada.model_dump(),
        "log_operacional": log.model_dump(),
        "saude_espelho": saude.model_dump(),
        "poll": espelho.parse_poll_from_log(),
        "numeros": bloco_numeros,
        "computed_at": iso_bahia(agora()),
    }


def drill_inicio(metric_id: str, page: int, page_size: int) -> dict[str, Any]:
    """Linhas de drill-down para métricas do Início."""
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    rows: list[dict[str, Any]] = []
    total = 0
    state: MetricEnvelope | None = None

    if seed.seed_habilitado():
        s = seed.seed_inicio()
        if metric_id == "inicio.esperando_15min":
            lista = (s["kpis"]["esperando_15min"]["value"] or {}).get("lista") or []
            rows = lista
            state = MetricEnvelope.ok(lista, metric_id=metric_id, is_seed=True)
        elif metric_id == "inicio.entrada_viva":
            rows = s["entrada_viva"]["value"] or []
            state = MetricEnvelope.ok(rows, metric_id=metric_id, is_seed=True)
        elif metric_id == "inicio.log_operacional":
            rows = s["log_operacional"]["value"] or []
            state = MetricEnvelope.ok(rows, metric_id=metric_id, is_seed=True)
        else:
            rows = [{"metric_id": metric_id, "value": s["kpis"].get(metric_id.split(".", 1)[-1])}]
            state = MetricEnvelope.ok(rows, metric_id=metric_id, is_seed=True)
    else:
        if metric_id == "inicio.esperando_15min":
            env = espelho.esperando_acima_de(15)
            lista = (env.value or {}).get("lista") if isinstance(env.value, dict) else []
            rows = lista or []
            state = env
        elif metric_id == "inicio.entrada_viva":
            env = espelho.entrada_ao_vivo(300, 200)
            rows = env.value if isinstance(env.value, list) else []
            state = env
        elif metric_id == "inicio.log_operacional":
            env = espelho.tail_live_log(200)
            rows = env.value if isinstance(env.value, list) else []
            state = env
        elif metric_id in (
            "inicio.atendidos",
            "inicio.clientes_min",
            "inicio.saude_espelho",
        ):
            if metric_id == "inicio.atendidos":
                env = espelho.atendidos_hoje()
            elif metric_id == "inicio.clientes_min":
                env = espelho.clientes_por_minuto()
            else:
                env = espelho.saude_espelho()
            rows = [{"value": env.value, "message": env.message, "state": env.state.value}]
            state = env
        else:
            # Gestor KPIs — drill mostra envelope, sem inventar linhas
            rows = []
            state = MetricEnvelope.empty(
                "Drill Gestor detalhado sobe com F4 (listagens Bearer)",
                metric_id=metric_id,
            )

    total = len(rows)
    start = (page - 1) * page_size
    slice_rows = rows[start : start + page_size]
    return {
        "total": total,
        "rows": slice_rows,
        "state": (state or MetricEnvelope.empty("sem dados", metric_id=metric_id)).model_dump(),
    }
