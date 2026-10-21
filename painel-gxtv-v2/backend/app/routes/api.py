"""Rotas /api/v2 — F1–F6 módulos + F7 cron externo."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.auth import (
    RequireUser,
    clear_session_cookie,
    diagnosticar_login,
    emitir_sessao,
    set_session_cookie,
)
from app.services.numeros import codigos_visiveis
from app.core.metrics_registry import FilterOptions, GlobalFilters, get_metric, registry_payload
from app.core.states import MetricEnvelope
from app.core.timezone import TZ_NAME, agora, iso_bahia, janela_periodo, telefone_final
from app.services import atendimento as atendimento_svc
from app.services import comercial as comercial_svc
from app.services import inicio as inicio_svc
from app.services import operacao as operacao_svc
from app.services import robo as robo_svc
from app.services import series as series_svc
from app.sources import espelho, gestor, seed

router = APIRouter(prefix="/api/v2")


class LoginBody(BaseModel):
    username: str
    password: str


class DrillQuery(BaseModel):
    metric_id: str
    page: int = 1
    page_size: int = 50
    filters: GlobalFilters = Field(default_factory=GlobalFilters)
    stage: str | None = None  # funil stage id


@router.get("/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "version": "v2-f7",
        "timezone": TZ_NAME,
        "now": iso_bahia(agora()),
        "phase": "F7",
    }


@router.post("/auth/login")
async def login(body: LoginBody, response: Response) -> dict[str, Any]:
    motivo = diagnosticar_login(body.username, body.password)
    if motivo:
        return {"ok": False, "motivo": motivo}
    token = emitir_sessao(body.username.strip())
    set_session_cookie(response, token)
    return {"ok": True, "username": body.username.strip(), "timezone": TZ_NAME}


@router.post("/auth/logout")
async def logout(response: Response) -> dict[str, Any]:
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/auth/me")
async def me(user: dict = RequireUser) -> dict[str, Any]:
    return {"ok": True, "user": user, "timezone": TZ_NAME}


@router.get("/registry")
async def registry(user: dict = RequireUser) -> dict[str, Any]:
    return {"ok": True, **registry_payload()}


@router.get("/registry/{metric_id}")
async def registry_one(metric_id: str, user: dict = RequireUser) -> dict[str, Any]:
    m = get_metric(metric_id)
    if not m:
        return {"ok": False, "motivo": "Métrica não encontrada no registro"}
    d = m.model_dump()
    d["last_update"] = d.get("last_update") or iso_bahia(agora())
    return {"ok": True, "metric": d}


@router.get("/filters/options")
async def filter_options(user: dict = RequireUser) -> dict[str, Any]:
    opts = FilterOptions()
    if seed.seed_habilitado():
        s = seed.seed_f1_shell()["filtros"]
        opts.numeros = s["numeros"]
        opts.atendentes = s["atendentes"]
        opts.apps = s["apps"]
        opts.aparelhos = s["aparelhos"]
    else:
        opts.numeros = [{"id": rotulo, "label": rotulo} for rotulo in codigos_visiveis()]
        opts.atendentes = [
            {"id": "Robô", "label": "Robô"},
            {"id": "Jorge", "label": "Jorge"},
            {"id": "Gustavo", "label": "Gustavo"},
            {"id": "Guilherme", "label": "Guilherme"},
        ]
    return {"ok": True, "options": opts.model_dump(), "timezone": TZ_NAME}


@router.get("/meta/shell")
async def shell(user: dict = RequireUser) -> dict[str, Any]:
    """Casca: módulos, estados, timezone, fontes."""
    ini, fim, rotulo = janela_periodo("hoje")
    saude = espelho.saude_espelho()
    log = espelho.tail_live_log(20)
    gest = await gestor.fetch_gestor()

    exemplares = None
    if seed.seed_habilitado():
        exemplares = seed.seed_f1_shell()["exemplos_estado"]

    return {
        "ok": True,
        "phase": "F7",
        "timezone": TZ_NAME,
        "window": {"inicio": iso_bahia(ini), "fim": iso_bahia(fim), "label": rotulo},
        "modules": [
            {"id": "inicio", "label": "Início", "phase": "F2", "ready": True},
            {"id": "atendimento", "label": "Atendimento", "phase": "F3", "ready": True},
            {"id": "comercial", "label": "Comercial", "phase": "F4", "ready": True},
            {"id": "operacao", "label": "Operação", "phase": "F5", "ready": True},
            {"id": "robo", "label": "Robô", "phase": "F6", "ready": True},
            {"id": "espelho", "label": "Espelho", "phase": "F2", "ready": True},
        ],
        "rules": {
            "no_datacrazy_chat_api": True,
            "gestor_authority": True,
            "gestor_down_never_zero": True,
            "phone_display": "final XXXX",
            "no_abandonado_label": True,
            "timezone": TZ_NAME,
        },
        "sources": {
            "espelho_saude": saude.model_dump(),
            "log_operacional": log.model_dump(),
            "gestor": gest.model_dump(),
        },
        "state_examples": exemplares,
        "phone_example": telefone_final("557799991234"),
        "user": user,
    }


@router.get("/meta/states")
async def states_demo(user: dict = RequireUser) -> dict[str, Any]:
    if not seed.seed_habilitado():
        return {
            "ok": True,
            "examples": {
                "loading": MetricEnvelope.loading().model_dump(),
                "empty": MetricEnvelope.empty("Sem dados neste período").model_dump(),
                "error": MetricEnvelope.error("erro de exemplo").model_dump(),
            },
        }
    return {"ok": True, "examples": seed.seed_f1_shell()["exemplos_estado"]}


@router.get("/inicio")
async def inicio(
    user: dict = RequireUser,
    periodo: str = Query("hoje"),
    numero: str | None = Query(None),
    atendente: str | None = Query(None),
    app: str | None = Query(None),
    aparelho: str | None = Query(None),
) -> dict[str, Any]:
    """F2 — KPIs compactos + entrada + log snapshot + saúde."""
    payload = await inicio_svc.montar_inicio(
        {
            "periodo": periodo,
            "numero": numero,
            "atendente": atendente,
            "app": app,
            "aparelho": aparelho,
        }
    )
    payload["graficos"] = series_svc.ao_vivo()
    return payload


@router.get("/inicio/log")
async def inicio_log(user: dict = RequireUser, n: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    if seed.seed_habilitado():
        return {"ok": True, **seed.seed_inicio()["log_operacional"]}
    env = espelho.tail_live_log(n)
    return {"ok": True, **env.model_dump()}


@router.get("/inicio/log/stream")
async def inicio_log_stream(user: dict = RequireUser) -> StreamingResponse:
    """SSE do live.log — ao vivo. Sem GET DataCrazy."""
    import json as _json

    async def event_gen() -> AsyncIterator[str]:
        if seed.seed_habilitado():
            for row in seed.seed_inicio()["log_operacional"].get("value") or []:
                yield (
                    "data: "
                    + _json.dumps(
                        {
                            "state": "ok",
                            "line": row.get("line"),
                            "t": row.get("t"),
                            "is_seed": True,
                            "heartbeat": False,
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )
                await asyncio.sleep(0.05)
            while True:
                yield (
                    "data: "
                    + _json.dumps(
                        {
                            "state": "ok",
                            "heartbeat": True,
                            "t": iso_bahia(agora()),
                            "is_seed": True,
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )
                await asyncio.sleep(2.0)
            return

        path = espelho._resolve_live_log()
        if not path or not path.is_file():
            yield (
                "data: "
                + _json.dumps(
                    {"state": "unavailable", "message": "live.log ausente", "heartbeat": False},
                    ensure_ascii=False,
                )
                + "\n\n"
            )
            return

        # Snapshot inicial + follow por posição
        try:
            size = path.stat().st_size
            pos = max(0, size - 16_384)
        except OSError as exc:
            yield (
                "data: "
                + _json.dumps(
                    {"state": "error", "message": str(exc), "heartbeat": False},
                    ensure_ascii=False,
                )
                + "\n\n"
            )
            return

        # envia últimas linhas
        env = espelho.tail_live_log(30)
        for row in env.value or []:
            if isinstance(row, dict) and row.get("line"):
                yield (
                    "data: "
                    + _json.dumps(
                        {
                            "state": "ok",
                            "line": row["line"],
                            "t": iso_bahia(agora()),
                            "heartbeat": False,
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )

        try:
            pos = path.stat().st_size
        except OSError:
            pos = 0

        while True:
            try:
                cur = path.stat().st_size
            except OSError as exc:
                yield (
                    "data: "
                    + _json.dumps(
                        {"state": "error", "message": str(exc), "heartbeat": False},
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )
                await asyncio.sleep(2.0)
                continue

            if cur < pos:
                # log rotacionou
                pos = 0

            if cur > pos:
                try:
                    with path.open("rb") as fh:
                        fh.seek(pos)
                        chunk = fh.read()
                        pos = fh.tell()
                except OSError as exc:
                    yield (
                        "data: "
                        + _json.dumps(
                            {"state": "error", "message": str(exc), "heartbeat": False},
                            ensure_ascii=False,
                        )
                        + "\n\n"
                    )
                    await asyncio.sleep(1.0)
                    continue
                for raw in chunk.splitlines():
                    try:
                        text = raw.decode("utf-8", errors="replace").rstrip("\n")
                    except Exception:
                        continue
                    if not text:
                        continue
                    yield (
                        "data: "
                        + _json.dumps(
                            {
                                "state": "ok",
                                "line": text[:500],
                                "t": iso_bahia(agora()),
                                "heartbeat": False,
                            },
                            ensure_ascii=False,
                        )
                        + "\n\n"
                    )
            else:
                yield (
                    "data: "
                    + _json.dumps(
                        {"state": "ok", "heartbeat": True, "t": iso_bahia(agora())},
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )
                await asyncio.sleep(1.0)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/inicio/entrada")
async def inicio_entrada(
    user: dict = RequireUser,
    janela_s: int = Query(300, ge=60, le=3600),
) -> dict[str, Any]:
    if seed.seed_habilitado():
        return {"ok": True, **seed.seed_inicio()["entrada_viva"]}
    env = espelho.entrada_ao_vivo(janela_s)
    return {"ok": True, **env.model_dump()}


def _filtros(
    periodo: str,
    numero: str | None,
    atendente: str | None,
    app: str | None,
    aparelho: str | None,
) -> dict[str, Any]:
    return {
        "periodo": periodo,
        "numero": numero,
        "atendente": atendente,
        "app": app,
        "aparelho": aparelho,
    }


@router.get("/atendimento")
async def atendimento(
    user: dict = RequireUser,
    periodo: str = Query("hoje"),
    numero: str | None = Query(None),
    atendente: str | None = Query(None),
    app: str | None = Query(None),
    aparelho: str | None = Query(None),
) -> dict[str, Any]:
    """F3 — funil clicável + tempos de resposta (média/mediana/P95/máx)."""
    return atendimento_svc.montar_atendimento(
        _filtros(periodo, numero, atendente, app, aparelho)
    )


@router.get("/comercial")
async def comercial(
    user: dict = RequireUser,
    periodo: str = Query("hoje"),
    numero: str | None = Query(None),
    atendente: str | None = Query(None),
    app: str | None = Query(None),
    aparelho: str | None = Query(None),
) -> dict[str, Any]:
    """F4 — Gestor-first vendas/vencem/WhatsApp (3619/0837) + funil de vendas."""
    payload = await comercial_svc.montar_comercial(
        _filtros(periodo, numero, atendente, app, aparelho)
    )
    try:
        from app.services import funil_comercial
        payload["funil_vendas"] = funil_comercial.montar(
            _filtros(periodo, numero, atendente, app, aparelho)
        )
    except Exception as exc:
        payload["funil_vendas"] = {
            "state": "unavailable",
            "value": None,
            "message": "Funil de vendas indisponível: %s" % exc,
            "metric_id": "comercial.funil_vendas",
        }
    payload["graficos"] = series_svc.ao_vivo()
    return payload


@router.get("/operacao")
async def operacao(
    user: dict = RequireUser,
    periodo: str = Query("hoje"),
    numero: str | None = Query(None),
    atendente: str | None = Query(None),
    app: str | None = Query(None),
    aparelho: str | None = Query(None),
) -> dict[str, Any]:
    """F5 — problemas × ontem/7d + correlações app×aparelho×hora."""
    return operacao_svc.montar_operacao(_filtros(periodo, numero, atendente, app, aparelho))


@router.get("/robo")
async def robo(
    user: dict = RequireUser,
    periodo: str = Query("hoje"),
    numero: str | None = Query(None),
    atendente: str | None = Query(None),
    app: str | None = Query(None),
    aparelho: str | None = Query(None),
) -> dict[str, Any]:
    """F6 — Robô/IA com nomes claros + tooltips do registro."""
    payload = robo_svc.montar_robo(_filtros(periodo, numero, atendente, app, aparelho))
    payload["graficos"] = series_svc.ao_vivo()
    return payload


@router.get("/espelho")
async def espelho_page(user: dict = RequireUser) -> dict[str, Any]:
    """F2 — saúde do espelho + lag + cobertura."""
    if seed.seed_habilitado():
        s = seed.seed_inicio()
        return {
            "ok": True,
            "phase": "F2",
            "timezone": TZ_NAME,
            "is_seed": True,
            "saude": s["saude_espelho"],
            "lag": MetricEnvelope.ok(
                (s["saude_espelho"]["value"] or {}).get("lag_s"),
                metric_id="espelho.lag",
                is_seed=True,
            ).model_dump(),
            "cobertura": MetricEnvelope.ok(
                (s["saude_espelho"]["value"] or {}).get("cobertura"),
                metric_id="espelho.cobertura",
                is_seed=True,
            ).model_dump(),
        }

    saude = espelho.saude_espelho()
    lag_v = None
    cob_v = None
    if isinstance(saude.value, dict):
        lag_v = saude.value.get("lag_s")
        cob_v = saude.value.get("cobertura")

    lag_env: MetricEnvelope
    cob_env: MetricEnvelope
    if saude.state.value == "unavailable":
        lag_env = MetricEnvelope.unavailable(
            saude.message or "Lag indisponível",
            source=saude.source,
            metric_id="espelho.lag",
        )
        cob_env = MetricEnvelope.unavailable(
            saude.message or "Cobertura indisponível",
            source=saude.source,
            metric_id="espelho.cobertura",
        )
    else:
        lag_env = (
            MetricEnvelope.ok(lag_v, metric_id="espelho.lag", source=saude.source, window="agora")
            if lag_v is not None
            else MetricEnvelope.empty("Lag ainda não medido", metric_id="espelho.lag", source=saude.source)
        )
        cob_env = (
            MetricEnvelope.ok(cob_v, metric_id="espelho.cobertura", source=saude.source, window="agora")
            if cob_v is not None
            else MetricEnvelope.empty(
                "Cobertura ainda não medida", metric_id="espelho.cobertura", source=saude.source
            )
        )

    return {
        "ok": True,
        "phase": "F2",
        "timezone": TZ_NAME,
        "is_seed": False,
        "saude": saude.model_dump(),
        "lag": lag_env.model_dump(),
        "cobertura": cob_env.model_dump(),
        "no_datacrazy": True,
    }


@router.post("/drilldown")
async def drilldown(body: DrillQuery, user: dict = RequireUser) -> dict[str, Any]:
    """Drill-down paginado — F2 preenche métricas do Início/Espelho."""
    m = get_metric(body.metric_id)
    if not m:
        return {"ok": False, "motivo": "Métrica fora do registro"}
    ini, fim, rotulo = janela_periodo(body.filters.periodo)

    if body.metric_id.startswith("inicio.") or body.metric_id.startswith("espelho."):
        payload = inicio_svc.drill_inicio(body.metric_id, body.page, body.page_size)
        return {
            "ok": True,
            "metric": m.model_dump(),
            "window": rotulo,
            "page": body.page,
            "page_size": body.page_size,
            "total": payload["total"],
            "rows": payload["rows"],
            "state": payload["state"],
            "filters": body.filters.model_dump(),
        }

    if body.metric_id.startswith("atendimento."):
        atendimento_svc.montar_atendimento(body.filters.model_dump())
        payload = atendimento_svc.drill_atendimento(
            body.metric_id, body.page, body.page_size, stage=body.stage
        )
        return {
            "ok": True,
            "metric": m.model_dump(),
            "window": rotulo,
            "page": body.page,
            "page_size": body.page_size,
            "total": payload["total"],
            "rows": payload["rows"],
            "state": payload["state"],
            "filters": body.filters.model_dump(),
            "stage": body.stage,
        }

    if body.metric_id.startswith("comercial."):
        payload = comercial_svc.drill_comercial(body.metric_id, body.page, body.page_size)
        return {
            "ok": True,
            "metric": m.model_dump(),
            "window": rotulo,
            "page": body.page,
            "page_size": body.page_size,
            "total": payload["total"],
            "rows": payload["rows"],
            "state": payload["state"],
            "filters": body.filters.model_dump(),
        }

    if body.metric_id.startswith("operacao."):
        operacao_svc.montar_operacao(body.filters.model_dump())
        payload = operacao_svc.drill_operacao(body.metric_id, body.page, body.page_size)
        return {
            "ok": True,
            "metric": m.model_dump(),
            "window": rotulo,
            "page": body.page,
            "page_size": body.page_size,
            "total": payload["total"],
            "rows": payload["rows"],
            "state": payload["state"],
            "filters": body.filters.model_dump(),
        }

    if body.metric_id.startswith("robo."):
        payload = robo_svc.drill_robo(body.metric_id, body.page, body.page_size)
        return {
            "ok": True,
            "metric": m.model_dump(),
            "window": rotulo,
            "page": body.page,
            "page_size": body.page_size,
            "total": payload["total"],
            "rows": payload["rows"],
            "state": payload["state"],
            "filters": body.filters.model_dump(),
        }

    return {
        "ok": True,
        "metric": m.model_dump(),
        "window": rotulo,
        "page": body.page,
        "page_size": body.page_size,
        "total": 0,
        "rows": [],
        "state": MetricEnvelope.empty(
            "Drill-down desta métrica entra na fase do módulo",
            metric_id=body.metric_id,
            window=rotulo,
        ).model_dump(),
        "filters": body.filters.model_dump(),
    }


@router.get("/sem-resposta")
async def sem_resposta(user: dict = RequireUser) -> dict[str, Any]:
    """Casos locais sem resposta do robô. Não chama DataCrazy."""
    path = "/opt/mnrobo/atendimento/revisoes/sem_resposta_atual.json"
    try:
        doc = json.loads(open(path, encoding="utf-8").read())
    except (OSError, ValueError):
        if seed.seed_habilitado():
            return {
                "ok": True,
                "is_seed": True,
                "total": 3,
                "causas": {"robô ocupado": 2, "número sem mapa": 1},
                "gerado_em": iso_bahia(agora()),
                "message": "Exemplo. O coletor real ainda não rodou neste computador.",
                "itens": [
                    {"sufixo": "9433", "instancia": "3619", "espera_min": 8, "motivo": "robô ocupado", "reprocessar": True, "numero_teste": False, "prova": "última fala do cliente sem resposta"},
                    {"sufixo": "1204", "instancia": "0837", "espera_min": 5, "motivo": "robô ocupado", "reprocessar": True, "numero_teste": False, "prova": "fila do robô acima do normal"},
                    {"sufixo": "7781", "instancia": "3166", "espera_min": 4, "motivo": "número sem mapa", "reprocessar": False, "numero_teste": True, "prova": "teste, sem Sigma"},
                ],
            }
        return {
            "ok": True,
            "total": 0,
            "causas": {},
            "itens": [],
            "gerado_em": None,
            "message": "Coletor ainda não rodou.",
        }
    return {"ok": True, **doc}
