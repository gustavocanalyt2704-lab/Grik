"""Leitura do espelho/webhook local — NUNCA chama API DataCrazy de conversas."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.core.mapa_instancias import rotulo_mapeado
from app.core.states import MetricEnvelope, SourceRef
from app.core.timezone import TZ, agora, inicio_dia, iso_bahia, telefone_final

ESPELHO_DIR = Path(
    os.environ.get(
        "ESPELHO_DIR",
        "/opt/mnrobo/atendimento/ai/private/espelho",
    )
)
LIVE_LOG = Path(
    os.environ.get(
        "LIVE_LOG",
        "/opt/mnrobo/atendimento/ai/private/live.log",
    )
)
# Fila magra: evento msg_* sem campo instance. Nomes iguais ao CRM/DataCrazy.
_EVENTO_WHATSAPP = {
    "msg_3619": "3619",
    "msg_0837": "0837",
    "msg_1869": "1869",
    "msg_2884": "2884",
    "msg_3166": "3166",
    "msg_p1cob": "COBRANÇA P1",
    "msg_p2cob": "COBRANÇA P2",
    "msg_p4cob": "COBRANÇA P4",
    "msg_p5cob": "COBRANÇA P5",
    "msg_p6cob": "COBRANÇA P6",
    "msg_p1sup": "P1 SUPORTE",
    "msg_p2sup": "P2 SUPORTE",
    "msg_p4sup": "P4 SUPORTE",
    "msg_p5sup": "P5 SUPORTE",
    "msg_p6sup": "SUPORTE P6",
    "msg_rmkt": "ALPHA TECH RMKT",
    "msg_rmktofc": "ALPHA TEC RMKT OFC",
}

# fallback legado F1
_LIVE_FALLBACKS = [
    Path("/opt/mnrobo/ai/private/live.log"),
    Path("/opt/mnrobo/atendimento/ai/private/live.log"),
]
WEBHOOK_QUEUE = Path(
    os.environ.get(
        "WEBHOOK_QUEUE",
        "/opt/mnrobo/atendimento/webhook/queue.jsonl",
    )
)
ESPERANDO_MIN = int(os.environ.get("ESPERANDO_MIN", "15"))


def _resolve_live_log() -> Path | None:
    if LIVE_LOG.is_file():
        return LIVE_LOG
    for p in _LIVE_FALLBACKS:
        if p.is_file():
            return p
    return LIVE_LOG if LIVE_LOG.exists() else None


def _meta() -> dict[str, Any] | None:
    for name in ("meta.json", "saude.json", "status.json"):
        p = ESPELHO_DIR / name
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return None


def saude_espelho() -> MetricEnvelope[dict]:
    meta = _meta()
    src = SourceRef(id="espelho", label="Espelho webhook", last_update=None)
    queue_ok = WEBHOOK_QUEUE.is_file()
    live = _resolve_live_log()
    live_ok = bool(live and live.is_file())

    lag = None
    cobertura = None
    eventos_hoje = None
    msgs_com_texto = None
    last_update = None

    if meta:
        lag = meta.get("lag_s")
        cobertura = meta.get("cobertura")
        eventos_hoje = meta.get("eventos_hoje")
        msgs_com_texto = meta.get("msgs_com_texto")
        last_update = meta.get("last_update")

    # Deriva lag do mtime da fila se meta não tiver
    if lag is None and queue_ok:
        try:
            lag = max(0.0, time.time() - WEBHOOK_QUEUE.stat().st_mtime)
        except OSError:
            pass

    if last_update is None and queue_ok:
        try:
            last_update = iso_bahia(
                datetime.fromtimestamp(WEBHOOK_QUEUE.stat().st_mtime, tz=timezone.utc)
            )
        except OSError:
            pass

    src.last_update = last_update or iso_bahia(agora())

    if meta is None and not queue_ok and not ESPELHO_DIR.is_dir():
        return MetricEnvelope.unavailable(
            "Espelho indisponível — diretório/fila não encontrados",
            source=src,
            metric_id="inicio.saude_espelho",
        )

    value = {
        "lag_s": lag,
        "cobertura": cobertura,
        "eventos_hoje": eventos_hoje,
        "msgs_com_texto": msgs_com_texto,
        "queue_path": str(WEBHOOK_QUEUE),
        "queue_presente": queue_ok,
        "live_log_presente": live_ok,
        "live_log_path": str(live) if live else str(LIVE_LOG),
        "fonte": "espelho_local+webhook",
    }

    if meta is None and not queue_ok:
        return MetricEnvelope.empty(
            "Espelho sem metadados e sem fila webhook",
            metric_id="inicio.saude_espelho",
            source=src,
        )

    # lag alto → stale
    if isinstance(lag, (int, float)) and lag > 300:
        return MetricEnvelope.stale(
            value,
            f"Espelho atrasado ({int(lag)}s)",
            source=src,
            metric_id="inicio.saude_espelho",
            window="agora",
        )
    return MetricEnvelope.ok(value, metric_id="inicio.saude_espelho", source=src, window="agora")


def _parse_ts(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        v = float(raw)
        if v > 1e12:
            v /= 1000.0
        return v
    text = str(raw).strip()
    if not text:
        return None
    if text.isdigit():
        return _parse_ts(int(text))
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt.timestamp()
    except Exception:
        return None


def _iter_jsonl_tail(path: Path, max_lines: int = 2000) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        data = path.read_bytes()
    except OSError:
        return []
    lines = data.splitlines()[-max_lines:]
    out: list[dict[str, Any]] = []
    for raw in lines:
        try:
            text = raw.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            obj = json.loads(text)
            if isinstance(obj, dict):
                out.append(obj)
        except Exception:
            continue
    return out


def _normalize_event(ev: dict[str, Any]) -> dict[str, Any] | None:
    """Normaliza evento webhook magro ou completo → campos úteis do painel."""
    payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else ev
    contact = payload.get("contact") if isinstance(payload.get("contact"), dict) else {}
    phone = (
        payload.get("telefone")
        or payload.get("phone")
        or payload.get("phoneNumber")
        or contact.get("phoneNumber")
    )
    cid = (
        payload.get("conversa")
        or payload.get("conversation_id")
        or payload.get("conversationId")
        or payload.get("id")
    )
    ts = _parse_ts(
        payload.get("timestamp")
        or payload.get("timestamp_iso")
        or payload.get("createdAt")
        or payload.get("ts")
        or ev.get("ts")
        or ev.get("received_at")
    )
    from_me = payload.get("from_me")
    if from_me is None:
        direcao = str(payload.get("direcao") or payload.get("direction") or "").lower()
        from_me = direcao in ("out", "outbound", "saida", "sent")
    elif isinstance(from_me, str):
        from_me = from_me.strip().lower() in ("1", "true", "sim", "yes")
    text = str(payload.get("text") or payload.get("conteudo_texto") or payload.get("body") or "")
    nome = payload.get("nome") or payload.get("name") or contact.get("name") or ""
    instancia = payload.get("instancia") or payload.get("instance") or ""
    instance_id = (
        payload.get("instanceId")
        or payload.get("instance_id")
        or ev.get("instanceId")
        or ev.get("instance_id")
        or ""
    )
    instance_phone = (
        payload.get("instance_phone")
        or payload.get("wid")
        or payload.get("instancePhone")
        or ""
    )
    if isinstance(instancia, dict):
        instance_id = instance_id or instancia.get("id") or instancia.get("instanceId") or ""
        instance_phone = (
            instance_phone
            or instancia.get("phone")
            or instancia.get("phoneNumber")
            or instancia.get("wid")
            or ""
        )
        instancia = instancia.get("name") or instance_id or instance_phone or ""
    evento_bruto = str(payload.get("evento") or ev.get("evento") or "")
    mapeado = rotulo_mapeado(
        instancia,
        phone=instance_phone,
        evento=evento_bruto,
        instance_id=instance_id,
    )
    # Fila magra do robô: {"evento":"msg_p6cob","telefone","conversa"} — sem campo instance.
    if mapeado:
        instancia = mapeado
    elif not instancia or str(instancia).startswith("msg_"):
        instancia = _EVENTO_WHATSAPP.get(evento_bruto or str(instancia), instancia or evento_bruto)
    evento = payload.get("evento") or ev.get("evento") or "msg"
    if not cid and not phone:
        return None
    return {
        "conversation_id": str(cid or phone or ""),
        "phone": str(phone or ""),
        "phone_final": telefone_final(str(phone) if phone else None),
        "name": str(nome or ""),
        "from_me": bool(from_me),
        "text": text[:200],
        "ts": ts,
        "instance": str(instancia or ""),
        "instance_id": str(instance_id or ""),
        "instance_phone": str(instance_phone or ""),
        "evento": str(evento),
        "has_text": bool(text.strip()),
    }


def eventos_recentes(max_lines: int = 3000) -> list[dict[str, Any]]:
    rows = _iter_jsonl_tail(WEBHOOK_QUEUE, max_lines=max_lines)
    out: list[dict[str, Any]] = []
    for ev in rows:
        n = _normalize_event(ev)
        if n:
            out.append(n)
    return out


def entrada_ao_vivo(janela_s: int = 300, limit: int = 40) -> MetricEnvelope[list]:
    """Mensagens inbound recentes via webhook — sem GET DataCrazy."""
    src = SourceRef(id="webhook_queue", label="webhook queue.jsonl", last_update=None)
    if not WEBHOOK_QUEUE.is_file():
        return MetricEnvelope.unavailable(
            "Fila webhook indisponível",
            source=src,
            metric_id="inicio.entrada_viva",
        )
    now = time.time()
    eventos = eventos_recentes()
    inbound = [
        e
        for e in eventos
        if not e.get("from_me")
        and e.get("ts")
        and (now - float(e["ts"])) <= janela_s
    ]
    inbound.sort(key=lambda e: float(e.get("ts") or 0), reverse=True)
    rows = inbound[:limit]
    src.last_update = iso_bahia(agora())
    if not rows:
        # fila existe mas sem inbound recente → empty (não unavailable)
        return MetricEnvelope.empty(
            f"Nenhuma entrada nos últimos {janela_s // 60} min",
            metric_id="inicio.entrada_viva",
            source=src,
            window=f"{janela_s}s",
        )
    # strip internal ts for display but keep iso
    display = []
    for e in rows:
        display.append(
            {
                "t": iso_bahia(datetime.fromtimestamp(float(e["ts"]), tz=timezone.utc))
                if e.get("ts")
                else None,
                "phone_final": e.get("phone_final"),
                "name": e.get("name") or None,
                "text": e.get("text") or None,
                "instance": e.get("instance") or None,
                "conversation_id": e.get("conversation_id"),
                "evento": e.get("evento"),
            }
        )
    return MetricEnvelope.ok(
        display,
        metric_id="inicio.entrada_viva",
        source=src,
        window=f"{janela_s}s",
    )


def clientes_por_minuto(janela_s: int = 600) -> MetricEnvelope[float]:
    src = SourceRef(id="webhook_queue", label="webhook queue.jsonl", last_update=None)
    if not WEBHOOK_QUEUE.is_file():
        return MetricEnvelope.unavailable(
            "Fila webhook indisponível — clientes/min",
            source=src,
            metric_id="inicio.clientes_min",
        )
    now = time.time()
    eventos = eventos_recentes()
    # clientes únicos inbound na janela
    phones: set[str] = set()
    for e in eventos:
        if e.get("from_me"):
            continue
        ts = e.get("ts")
        if not ts or (now - float(ts)) > janela_s:
            continue
        key = e.get("phone") or e.get("conversation_id")
        if key:
            phones.add(str(key))
    rate = round(len(phones) / (janela_s / 60.0), 2)
    src.last_update = iso_bahia(agora())
    return MetricEnvelope.ok(
        rate,
        metric_id="inicio.clientes_min",
        source=src,
        window=f"{janela_s}s",
    )


def esperando_acima_de(minutos: int | None = None) -> MetricEnvelope[dict]:
    """Clientes com última fala inbound sem resposta há > N min (AGORA)."""
    minutos = minutos if minutos is not None else ESPERANDO_MIN
    src = SourceRef(id="webhook_queue", label="webhook queue.jsonl", last_update=None)
    if not WEBHOOK_QUEUE.is_file():
        return MetricEnvelope.unavailable(
            "Não dá para medir esperando — fila webhook ausente",
            source=src,
            metric_id="inicio.esperando_15min",
        )
    now = time.time()
    threshold = minutos * 60
    # estado por conversa: last_in / last_out
    state: dict[str, dict[str, Any]] = {}
    for e in eventos_recentes(max_lines=5000):
        cid = str(e.get("conversation_id") or "")
        if not cid:
            continue
        st = state.setdefault(
            cid,
            {
                "last_in": None,
                "last_out": None,
                "phone_final": e.get("phone_final"),
                "name": e.get("name"),
                "instance": e.get("instance"),
            },
        )
        ts = e.get("ts")
        if ts is None:
            continue
        if e.get("from_me"):
            if st["last_out"] is None or ts > st["last_out"]:
                st["last_out"] = ts
        else:
            if st["last_in"] is None or ts > st["last_in"]:
                st["last_in"] = ts
                st["phone_final"] = e.get("phone_final") or st["phone_final"]
                st["name"] = e.get("name") or st["name"]

    waiting: list[dict[str, Any]] = []
    for cid, st in state.items():
        last_in = st.get("last_in")
        last_out = st.get("last_out")
        if last_in is None:
            continue
        # cliente é o último a falar
        if last_out is not None and last_out >= last_in:
            continue
        age = now - float(last_in)
        if age < threshold:
            continue
        waiting.append(
            {
                "conversation_id": cid,
                "phone_final": st.get("phone_final") or "final —",
                "name": st.get("name") or None,
                "instance": st.get("instance") or None,
                "espera_min": round(age / 60.0, 1),
                "ultima_fala": iso_bahia(datetime.fromtimestamp(float(last_in), tz=timezone.utc)),
            }
        )
    waiting.sort(key=lambda r: float(r.get("espera_min") or 0), reverse=True)
    src.last_update = iso_bahia(agora())
    value = {"n": len(waiting), "minutos": minutos, "lista": waiting[:100]}
    return MetricEnvelope.ok(
        value,
        metric_id="inicio.esperando_15min",
        source=src,
        window="agora",
    )


def atendidos_hoje() -> MetricEnvelope[int]:
    """Conversas com pelo menos 1 outbound hoje (America/Bahia) via webhook."""
    src = SourceRef(id="webhook_queue", label="webhook queue.jsonl", last_update=None)
    if not WEBHOOK_QUEUE.is_file():
        return MetricEnvelope.unavailable(
            "Fila webhook indisponível — atendidos",
            source=src,
            metric_id="inicio.atendidos",
        )
    start = inicio_dia().timestamp()
    out_ids: set[str] = set()
    for e in eventos_recentes(max_lines=8000):
        if not e.get("from_me"):
            continue
        ts = e.get("ts")
        if ts is None or float(ts) < start:
            continue
        cid = str(e.get("conversation_id") or "")
        if cid:
            out_ids.add(cid)
    src.last_update = iso_bahia(agora())
    return MetricEnvelope.ok(
        len(out_ids),
        metric_id="inicio.atendidos",
        source=src,
        window="hoje",
    )


_POLL_RE = re.compile(
    r"POLL.*?ocupadas[=:]?\s*(\d+).*?(?:aguardando|waiting)[=:]?\s*(\d+)",
    re.IGNORECASE,
)


def parse_poll_from_log(n: int = 200) -> dict[str, Any] | None:
    path = _resolve_live_log()
    if not path or not path.is_file():
        return None
    try:
        data = path.read_bytes()
        lines = data.splitlines()[-n:]
    except OSError:
        return None
    last = None
    for raw in reversed(lines):
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            continue
        m = _POLL_RE.search(text)
        if m:
            last = {
                "ocupadas": int(m.group(1)),
                "aguardando": int(m.group(2)),
                "line": text[:300],
            }
            break
    return last


def tail_live_log(n: int = 40) -> MetricEnvelope[list]:
    src = SourceRef(id="live_log", label="live.log", last_update=None)
    path = _resolve_live_log()
    if not path or not path.is_file():
        return MetricEnvelope.unavailable(
            "Log operacional indisponível",
            source=src,
            metric_id="inicio.log_operacional",
        )
    try:
        data = path.read_bytes()
        lines = data.splitlines()[-n:]
        out = []
        for raw in lines:
            try:
                text = raw.decode("utf-8", errors="replace")
            except Exception:
                continue
            out.append({"t": None, "line": text[:500]})
        src.last_update = iso_bahia(agora())
        if not out:
            return MetricEnvelope.empty("Log vazio", metric_id="inicio.log_operacional", source=src)
        return MetricEnvelope.ok(out, metric_id="inicio.log_operacional", source=src)
    except OSError as exc:
        return MetricEnvelope.error(
            f"Erro lendo live.log: {exc}",
            metric_id="inicio.log_operacional",
            source=src,
        )


def follow_live_log(poll_s: float = 1.0) -> Iterator[str]:
    """Gera linhas novas do live.log (para SSE)."""
    path = _resolve_live_log()
    if not path or not path.is_file():
        yield json.dumps(
            {"state": "unavailable", "message": "live.log ausente", "line": None},
            ensure_ascii=False,
        )
        return
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            while True:
                line = fh.readline()
                if not line:
                    time.sleep(poll_s)
                    # heartbeat
                    yield json.dumps(
                        {"state": "ok", "heartbeat": True, "t": iso_bahia(agora())},
                        ensure_ascii=False,
                    )
                    continue
                try:
                    text = line.decode("utf-8", errors="replace").rstrip("\n")
                except Exception:
                    continue
                yield json.dumps(
                    {
                        "state": "ok",
                        "t": iso_bahia(agora()),
                        "line": text[:500],
                        "heartbeat": False,
                    },
                    ensure_ascii=False,
                )
    except OSError as exc:
        yield json.dumps(
            {"state": "error", "message": str(exc), "line": None},
            ensure_ascii=False,
        )


def mtime_espelho() -> float | None:
    try:
        return ESPELHO_DIR.stat().st_mtime
    except OSError:
        try:
            return WEBHOOK_QUEUE.stat().st_mtime
        except OSError:
            return None
