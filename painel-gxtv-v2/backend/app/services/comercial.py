"""Agregação Comercial F4 — Gestor-first (vendas/renovações/vencem/WhatsApp)."""

from __future__ import annotations

from typing import Any

from app.core.states import MetricEnvelope, SourceRef
from app.core.timezone import TZ_NAME, agora, iso_bahia, janela_periodo
from app.services import numeros as numeros_svc
from app.sources import gestor, seed


def _seed() -> dict[str, Any]:
    stamp = iso_bahia(agora())
    src = SourceRef(id="seed", label="Seed F4", last_update=stamp)
    return {
        "vendas": MetricEnvelope.ok(
            {"total": 62, "valor": 4280.5, "por_whatsapp": {"3619": 38, "0837": 24}},
            metric_id="comercial.vendas",
            window="hoje",
            source=src,
            is_seed=True,
        ).model_dump(),
        "vencem_hoje": MetricEnvelope.ok(
            {"total": 112, "renovaram": 37, "pendentes": 75},
            metric_id="comercial.vencem_hoje",
            window="hoje",
            source=src,
            is_seed=True,
        ).model_dump(),
        "dist_whatsapp": MetricEnvelope.ok(
            {
                "items": [
                    {"id": "3619", "label": "WhatsApp 3619", "vendas": 38, "renovacoes": 21},
                    {"id": "0837", "label": "WhatsApp 0837", "vendas": 24, "renovacoes": 16},
                ]
            },
            metric_id="comercial.dist_whatsapp",
            window="hoje",
            source=src,
            is_seed=True,
        ).model_dump(),
        "nota_3619_0837": "Instâncias 3619 e 0837 entram no total Gestor — sem perda silenciosa.",
    }


async def montar_comercial(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    filters = filters or {}
    periodo = str(filters.get("periodo") or "hoje")
    ini, fim, rotulo = janela_periodo(periodo)

    if seed.seed_habilitado():
        s = _seed()
        bloco = await numeros_svc.montar_numeros(filters)
        return {
            "ok": True,
            "phase": "F4",
            "timezone": TZ_NAME,
            "window": {"inicio": iso_bahia(ini), "fim": iso_bahia(fim), "label": rotulo},
            "is_seed": True,
            **s,
            "aviso_gestor": bloco.get("aviso_gestor"),
            "vendas_linhas": bloco.get("vendas") or [],
            "vendas_sem_lista": bool(bloco.get("vendas_sem_lista")),
            "numeros": bloco,
            "computed_at": iso_bahia(agora()),
        }

    gest = await gestor.fetch_kpis_comerciais()
    bloco = await numeros_svc.montar_numeros(filters, gest=gest)
    src = gest.source or SourceRef(id="gestor", label="Gestor IPTV", last_update=None)

    if gest.state.value in ("unavailable", "error"):
        vendas = MetricEnvelope(
            state=gest.state,
            value=gest.value.get("faturamento") if isinstance(gest.value, dict) else None,
            message=gest.message or "Gestor indisponível — não publicar 0",
            source=src,
            metric_id="comercial.vendas",
            window=rotulo,
        )
        # Prefer structured last cache
        if isinstance(gest.value, dict):
            vendas = MetricEnvelope(
                state=gest.state,
                value={
                    "total": gest.value.get("renovacoes"),
                    "valor": gest.value.get("faturamento"),
                    "por_whatsapp": None,
                    "hint": "cache preservado — inclui 3619/0837 quando Gestor reportar",
                },
                message=gest.message,
                source=src,
                metric_id="comercial.vendas",
                window=rotulo,
            )
        vencem = MetricEnvelope(
            state=gest.state,
            value={
                "total": gest.value.get("vencem_hoje") if isinstance(gest.value, dict) else None,
                "renovaram": gest.value.get("vencem_hoje_renovaram") if isinstance(gest.value, dict) else None,
                "pendentes": gest.value.get("vencem_hoje_pendentes") if isinstance(gest.value, dict) else None,
            }
            if isinstance(gest.value, dict)
            else None,
            message=gest.message,
            source=src,
            metric_id="comercial.vencem_hoje",
            window=rotulo,
        )
        dist = MetricEnvelope.unavailable(
            "Distribuição WhatsApp exige Gestor online (3619/0837)",
            source=src,
            metric_id="comercial.dist_whatsapp",
        )
        return {
            "ok": True,
            "phase": "F4",
            "timezone": TZ_NAME,
            "window": {"inicio": iso_bahia(ini), "fim": iso_bahia(fim), "label": rotulo},
            "is_seed": False,
            "vendas": vendas.model_dump(),
            "vencem_hoje": vencem.model_dump(),
            "dist_whatsapp": dist.model_dump(),
            "nota_3619_0837": "Sem credencial do Gestor: vendas ficam sem dado — nunca 0 inventado.",
            "aviso_gestor": bloco.get("aviso_gestor"),
            "vendas_linhas": bloco.get("vendas") or [],
            "vendas_sem_lista": bool(bloco.get("vendas_sem_lista")),
            "numeros": bloco,
            "computed_at": iso_bahia(agora()),
        }

    data = gest.value if isinstance(gest.value, dict) else {}
    summary = data.get("today_summary") if isinstance(data.get("today_summary"), dict) else {}
    panels = data.get("panels_dashboard") if isinstance(data.get("panels_dashboard"), dict) else {}

    # Tenta extrair breakdown WhatsApp do summary/panels sem inventar
    por_wa = None
    for blob in (summary, panels, data):
        if not isinstance(blob, dict):
            continue
        for key in ("por_whatsapp", "whatsapp", "instances", "by_instance"):
            if isinstance(blob.get(key), dict):
                por_wa = blob[key]
                break
        if por_wa:
            break

    # filtro numero
    numero = filters.get("numero")
    valor = data.get("faturamento")
    renov = data.get("renovacoes")
    if numero and isinstance(por_wa, dict) and str(numero) in por_wa:
        # se breakdown existir, recorta
        slice_wa = por_wa.get(str(numero))
        if isinstance(slice_wa, dict):
            valor = slice_wa.get("faturamento", slice_wa.get("valor", valor))
            renov = slice_wa.get("vendas", slice_wa.get("renovacoes", renov))
        elif isinstance(slice_wa, (int, float)):
            renov = int(slice_wa)

    vendas_val = {
        "total": renov,
        "valor": valor,
        "por_whatsapp": por_wa,
        "inclui_3619_0837": True,
    }

    def _env(val: Any, mid: str) -> MetricEnvelope:
        if gest.state.value == "stale":
            return MetricEnvelope.stale(
                val, gest.message or "Cache Gestor atrasado", source=src, metric_id=mid, window=rotulo
            )
        if val is None or (isinstance(val, dict) and all(v is None for v in val.values() if v != True)):
            # for vendas dict, allow partial
            if isinstance(val, dict) and (val.get("valor") is not None or val.get("total") is not None):
                return MetricEnvelope.ok(val, metric_id=mid, window=rotulo, source=src)
            return MetricEnvelope.unavailable(
                "Gestor não trouxe este campo — não publicar 0",
                source=src,
                metric_id=mid,
            )
        return MetricEnvelope.ok(val, metric_id=mid, window=rotulo, source=src)

    vencem_val = {
        "total": data.get("vencem_hoje"),
        "renovaram": data.get("vencem_hoje_renovaram"),
        "pendentes": data.get("vencem_hoje_pendentes"),
    }

    if por_wa and isinstance(por_wa, dict):
        items = []
        for wid in ("3619", "0837"):
            raw = por_wa.get(wid)
            if isinstance(raw, dict):
                items.append(
                    {
                        "id": wid,
                        "label": f"WhatsApp {wid}",
                        "vendas": raw.get("vendas", raw.get("total")),
                        "renovacoes": raw.get("renovacoes"),
                        "valor": raw.get("valor", raw.get("faturamento")),
                    }
                )
            elif isinstance(raw, (int, float)):
                items.append({"id": wid, "label": f"WhatsApp {wid}", "vendas": int(raw)})
            else:
                items.append(
                    {
                        "id": wid,
                        "label": f"WhatsApp {wid}",
                        "vendas": None,
                        "nota": "Gestor sem breakdown — total agregado preservado",
                    }
                )
        # outros
        for k, raw in por_wa.items():
            if str(k) in ("3619", "0837"):
                continue
            if isinstance(raw, dict):
                items.append({"id": str(k), "label": f"WhatsApp {k}", **{kk: raw.get(kk) for kk in ("vendas", "renovacoes", "valor")}})
            elif isinstance(raw, (int, float)):
                items.append({"id": str(k), "label": f"WhatsApp {k}", "vendas": int(raw)})
        dist_env = _env({"items": items}, "comercial.dist_whatsapp")
    else:
        # Sem breakdown: mostra slots 3619/0837 como parte do total (não zero)
        dist_env = MetricEnvelope.ok(
            {
                "items": [
                    {
                        "id": "3619",
                        "label": "WhatsApp 3619",
                        "vendas": None,
                        "nota": "Incluído no total Gestor — breakdown não veio no payload",
                    },
                    {
                        "id": "0837",
                        "label": "WhatsApp 0837",
                        "vendas": None,
                        "nota": "Incluído no total Gestor — breakdown não veio no payload",
                    },
                ],
                "total_gestor": renov,
                "aviso": "Sem perda silenciosa: totais vêm do Gestor; detalhe por número quando API enviar.",
            },
            metric_id="comercial.dist_whatsapp",
            window=rotulo,
            source=src,
        )

    return {
        "ok": True,
        "phase": "F4",
        "timezone": TZ_NAME,
        "window": {"inicio": iso_bahia(ini), "fim": iso_bahia(fim), "label": rotulo},
        "is_seed": False,
        "vendas": _env(vendas_val, "comercial.vendas").model_dump(),
        "vencem_hoje": _env(vencem_val, "comercial.vencem_hoje").model_dump(),
        "dist_whatsapp": dist_env.model_dump(),
        "nota_3619_0837": "Venda do Gestor sem conversa no webhook fica como origem não identificada.",
        "aviso_gestor": bloco.get("aviso_gestor"),
        "vendas_linhas": bloco.get("vendas") or [],
        "vendas_sem_lista": bool(bloco.get("vendas_sem_lista")),
        "numeros": bloco,
        "computed_at": iso_bahia(agora()),
    }


def drill_comercial(metric_id: str, page: int, page_size: int) -> dict[str, Any]:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    if metric_id == "comercial.funil_vendas":
        from app.services import funil_comercial
        return funil_comercial.drill(page, page_size)
    if seed.seed_habilitado():
        s = _seed()
        if metric_id == "comercial.dist_whatsapp":
            rows = (s["dist_whatsapp"]["value"] or {}).get("items") or []
        elif metric_id == "comercial.vencem_hoje":
            v = s["vencem_hoje"]["value"] or {}
            rows = [
                {"tipo": "total", "n": v.get("total")},
                {"tipo": "renovaram", "n": v.get("renovaram")},
                {"tipo": "pendentes", "n": v.get("pendentes")},
            ]
        else:
            rows = [s["vendas"]["value"]]
        total = len(rows)
        start = (page - 1) * page_size
        return {
            "total": total,
            "rows": rows[start : start + page_size],
            "state": MetricEnvelope.ok(rows, metric_id=metric_id, is_seed=True).model_dump(),
        }
    return {
        "total": 0,
        "rows": [],
        "state": MetricEnvelope.empty(
            "Drill Gestor detalhado depende de listagens Bearer (expiring/*)",
            metric_id=metric_id,
        ).model_dump(),
    }
