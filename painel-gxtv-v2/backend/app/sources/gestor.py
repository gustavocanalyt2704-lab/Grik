"""Cliente Gestor IPTV com cache em disco.

Autoridade de venda/renovação/vencimento/faturamento.
Se cair → indisponível + última atualização (nunca 0 inventado).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

from app.core.states import MetricEnvelope, SourceRef, gestor_indisponivel
from app.sources import credenciais
from app.core.timezone import TZ_NAME, agora, iso_bahia

GESTOR_BASE = os.environ.get("GESTOR_BASE", "https://gestor-iptv-1.emergent.host")
CACHE_PATH = Path(os.environ.get("GESTOR_CACHE_PATH", "/var/cache/painel-gxtv-v2/gestor.json"))
KPI_CACHE_PATH = Path(
    os.environ.get("GESTOR_KPI_CACHE_PATH", "/var/cache/painel-gxtv-v2/gestor_kpis.json")
)
CACHE_TTL_S = int(os.environ.get("GESTOR_CACHE_TTL_S", "120"))
STALE_AFTER_S = int(os.environ.get("GESTOR_STALE_AFTER_S", "900"))


def _ensure_dir(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


def _read_cache(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_cache(path: Path, payload: dict[str, Any]) -> None:
    _ensure_dir(path)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def _bearer() -> str:
    return credenciais.bearer()


async def _login(client: httpx.AsyncClient) -> str | None:
    email = credenciais.email()
    password = credenciais.password()
    if not (email and password):
        return None
    url = GESTOR_BASE.rstrip("/") + "/api/auth/login"
    r = await client.post(url, json={"email": email, "password": password})
    r.raise_for_status()
    data = r.json()
    return data.get("access_token") or data.get("token")


def _count_payload(payload: Any) -> int | None:
    if payload is None:
        return None
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, (int, float)):
        return int(payload)
    if isinstance(payload, dict):
        for key in ("total", "count", "n", "qty", "quantidade"):
            if isinstance(payload.get(key), (int, float)):
                return int(payload[key])
        for key in ("items", "data", "results", "customers", "rows", "expiring", "renewals"):
            val = payload.get(key)
            if isinstance(val, list):
                return len(val)
            if isinstance(val, dict):
                nested = _count_payload(val)
                if nested is not None:
                    return nested
        # some summaries nest totals
        for key in ("vencem_hoje", "vence_hoje", "renewals_today", "renovados_hoje", "faturamento"):
            if key in payload:
                nested = _count_payload(payload[key])
                if nested is not None:
                    return nested
    return None


def _money(payload: Any) -> float | None:
    if payload is None:
        return None
    if isinstance(payload, (int, float)):
        return float(payload)
    if isinstance(payload, dict):
        for key in (
            "faturamento",
            "revenue",
            "total_revenue",
            "amount",
            "valor",
            "total",
            "sum",
            "brl",
        ):
            v = payload.get(key)
            if isinstance(v, (int, float)):
                return float(v)
            if isinstance(v, dict):
                nested = _money(v)
                if nested is not None:
                    return nested
        for key in ("hoje", "today", "summary"):
            if key in payload:
                nested = _money(payload[key])
                if nested is not None:
                    return nested
    return None


def _envelope_from_cache(
    cached: dict[str, Any],
    *,
    metric_id: str,
    now: float,
) -> MetricEnvelope[dict]:
    age = now - float(cached.get("fetched_at", 0))
    src = SourceRef(
        id="gestor",
        label="Gestor IPTV (cache)",
        last_update=cached.get("last_update"),
        cache_ttl_s=CACHE_TTL_S,
    )
    kw = {"metric_id": metric_id, "window": "hoje", "source": src}
    data = cached.get("data") or {}
    if age > STALE_AFTER_S:
        return MetricEnvelope.stale(
            data,
            f"Cache Gestor atrasado ({int(age)}s) — timezone {TZ_NAME}",
            **kw,
        )
    return MetricEnvelope.ok(data, **kw)


async def fetch_gestor(path: str = "/api/lookup/health") -> MetricEnvelope[dict]:
    """Busca Gestor; em falha devolve última cache com estado unavailable/stale."""
    cached = _read_cache(CACHE_PATH)
    now = time.time()

    if cached and (now - float(cached.get("fetched_at", 0))) < CACHE_TTL_S:
        return _envelope_from_cache(cached, metric_id="comercial.gestor", now=now)

    url = GESTOR_BASE.rstrip("/") + path
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.get(url, headers={"Accept": "application/json"})
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        if cached and cached.get("data") is not None:
            return gestor_indisponivel(cached.get("data"), cached.get("last_update"))
        return MetricEnvelope.unavailable(
            f"Gestor indisponível ({type(exc).__name__}) — sem cache anterior",
            source=SourceRef(id="gestor", label="Gestor IPTV", last_update=None),
            metric_id="comercial.gestor",
        )

    stamp = iso_bahia(agora())
    blob = {"fetched_at": now, "last_update": stamp, "data": data, "path": path}
    _write_cache(CACHE_PATH, blob)
    return MetricEnvelope.ok(
        data,
        metric_id="comercial.gestor",
        window="hoje",
        source=SourceRef(id="gestor", label="Gestor IPTV", last_update=stamp, cache_ttl_s=CACHE_TTL_S),
    )


async def _auth_headers(client: httpx.AsyncClient) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    token = credenciais.bearer()
    if not token:
        token = (await _login(client)) or ""
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def fetch_kpis_comerciais() -> MetricEnvelope[dict]:
    """KPIs Gestor-first para Início/Comercial.

    Nunca inventa 0: sem Bearer/auth → unavailable (+ cache se houver).
    """
    cached = _read_cache(KPI_CACHE_PATH)
    now = time.time()
    if cached and (now - float(cached.get("fetched_at", 0))) < CACHE_TTL_S:
        return _envelope_from_cache(cached, metric_id="inicio.kpis_gestor", now=now)

    token_ready = credenciais.tem()
    if not token_ready:
        if cached and cached.get("data") is not None:
            env = gestor_indisponivel(cached.get("data"), cached.get("last_update"))
            env.metric_id = "inicio.kpis_gestor"
            env.message = credenciais.aviso()
            return env
        return MetricEnvelope.unavailable(
            credenciais.aviso() or "Gestor sem credencial",
            source=SourceRef(id="gestor", label="Gestor IPTV", last_update=None),
            metric_id="inicio.kpis_gestor",
        )

    base = GESTOR_BASE.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=18.0) as client:
            headers = await _auth_headers(client)
            if "Authorization" not in headers:
                raise RuntimeError("sem token Gestor")

            async def get(path: str) -> Any:
                r = await client.get(base + path, headers=headers)
                if r.status_code in (401, 403):
                    raise PermissionError(f"HTTP {r.status_code} {path}")
                r.raise_for_status()
                return r.json()

            today = await get("/api/expiring/today")
            renewals = await get("/api/expiring/renewals-today")
            today_summary: Any = None
            panels: Any = None
            for path, slot in (
                ("/api/manager/today-summary", "summary"),
                ("/api/expiring/panels-dashboard", "panels"),
            ):
                try:
                    payload = await get(path)
                    if slot == "summary":
                        today_summary = payload
                    else:
                        panels = payload
                except Exception:
                    pass
    except Exception as exc:
        if cached and cached.get("data") is not None:
            env = gestor_indisponivel(cached.get("data"), cached.get("last_update"))
            env.metric_id = "inicio.kpis_gestor"
            env.message = f"Gestor indisponível ({type(exc).__name__}) — cache preservado"
            return env
        return MetricEnvelope.unavailable(
            f"Gestor indisponível ({type(exc).__name__}) — sem cache anterior",
            source=SourceRef(id="gestor", label="Gestor IPTV", last_update=None),
            metric_id="inicio.kpis_gestor",
        )

    vencem = _count_payload(today)
    renov = _count_payload(renewals)
    faturamento = _money(today_summary) if today_summary is not None else _money(panels)
    # pendentes = vencem - renovados (quando ambos disponíveis)
    pendentes: int | None = None
    if vencem is not None and renov is not None:
        pendentes = max(0, vencem - renov)

    data = {
        "faturamento": faturamento,
        "renovacoes": renov,
        "vencem_hoje": vencem,
        "vencem_hoje_renovaram": renov,
        "vencem_hoje_pendentes": pendentes,
        "today_summary": today_summary,
        "panels_dashboard": panels,
        "fonte": "gestor:/api/expiring/*+/api/manager/today-summary",
        "whatsapp_nota": "Incluir 3619 e 0837 — autoridade Gestor, não inventar zero",
    }
    stamp = iso_bahia(agora())
    blob = {"fetched_at": now, "last_update": stamp, "data": data}
    _write_cache(KPI_CACHE_PATH, blob)
    return MetricEnvelope.ok(
        data,
        metric_id="inicio.kpis_gestor",
        window="hoje",
        source=SourceRef(id="gestor", label="Gestor IPTV", last_update=stamp, cache_ttl_s=CACHE_TTL_S),
    )


def _linha_venda(obj: dict[str, Any]) -> dict[str, Any] | None:
    tel = ""
    for key in ("telefone", "phone", "phoneNumber", "whatsapp", "celular"):
        if obj.get(key):
            tel = str(obj[key])
            break
    cliente = obj.get("cliente") if isinstance(obj.get("cliente"), dict) else {}
    if not tel:
        for key in ("telefone", "phone", "phoneNumber", "whatsapp", "celular"):
            if cliente.get(key):
                tel = str(cliente[key])
                break
    inst = obj.get("instancia") or obj.get("instance") or obj.get("numero") or obj.get("whatsapp_id") or ""
    valor = None
    for key in ("valor", "amount", "preco", "price", "faturamento"):
        if isinstance(obj.get(key), (int, float)):
            valor = float(obj[key])
            break
    if not tel and not inst and valor is None:
        return None
    return {"telefone": tel, "instancia": str(inst or ""), "valor": valor, "id": str(obj.get("id") or "")}


def coletar_linhas_venda(data: Any) -> list[dict[str, Any]] | None:
    """None quando o payload não traz lista. Lista vazia é dado real (zero vendas)."""
    if not isinstance(data, dict):
        return None
    blobs: list[Any] = []
    chaves = ("vendas", "sales", "renewals", "renovacoes", "vendas_hoje")
    for key in chaves:
        if key in data:
            blobs.append(data[key])
    summary = data.get("today_summary")
    if isinstance(summary, dict):
        for key in chaves:
            if key in summary:
                blobs.append(summary[key])
    panels = data.get("panels_dashboard")
    if isinstance(panels, dict):
        for key in chaves:
            if key in panels:
                blobs.append(panels[key])
    if not blobs:
        return None
    out: list[dict[str, Any]] = []
    for blob in blobs:
        rows: list[Any] = []
        if isinstance(blob, list):
            rows = blob
        elif isinstance(blob, dict):
            for key in ("items", "data", "results", "rows"):
                if isinstance(blob.get(key), list):
                    rows = blob[key]
                    break
        for item in rows:
            if isinstance(item, dict):
                linha = _linha_venda(item)
                if linha:
                    out.append(linha)
    return out


def extrair_kpi(env: MetricEnvelope[dict], key: str) -> MetricEnvelope[Any]:
    """Recorta um KPI do envelope Gestor sem inventar 0."""
    src = env.source
    mid_map = {
        "faturamento": "inicio.faturamento",
        "renovacoes": "inicio.renovacoes",
        "vencem_hoje": "inicio.vencem_hoje",
    }
    metric_id = mid_map.get(key, f"inicio.{key}")
    if env.state.value in ("unavailable", "error", "loading"):
        last = None
        if isinstance(env.value, dict) and key in env.value:
            last = env.value.get(key)
        return MetricEnvelope(
            state=env.state,
            value=last,
            message=env.message,
            source=src,
            metric_id=metric_id,
            window=env.window,
            is_seed=env.is_seed,
        )
    if not isinstance(env.value, dict):
        return MetricEnvelope.unavailable(
            "Gestor sem payload de KPI",
            source=src,
            metric_id=metric_id,
        )
    if key not in env.value or env.value.get(key) is None:
        return MetricEnvelope.unavailable(
            f"Gestor não trouxe {key} — não publicar 0",
            source=src,
            metric_id=metric_id,
            last_value=None,
        )
    if env.state.value == "stale":
        return MetricEnvelope.stale(
            env.value.get(key),
            env.message or "Cache Gestor atrasado",
            source=src,
            metric_id=metric_id,
            window=env.window,
            is_seed=env.is_seed,
        )
    return MetricEnvelope.ok(
        env.value.get(key),
        metric_id=metric_id,
        window=env.window,
        source=src,
        is_seed=env.is_seed,
    )
