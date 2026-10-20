"""Funil de vendas por número de WhatsApp (3619, 0837, 3166).

Lê o jsonl que o robô grava e, se existir, a fila do webhook.
Sem fonte: indisponível — não publica zero inventado.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from app.core.states import MetricEnvelope, SourceRef
from app.core.timezone import iso_bahia, agora

_FUNIL = None


def _modulo_funil():
    global _FUNIL
    if _FUNIL is not None:
        return _FUNIL
    candidatos = []
    env = os.environ.get("MNROBO_AI")
    if env:
        candidatos.append(Path(env) / "funil_venda.py")
    candidatos.append(Path("/opt/mnrobo/atendimento/ai/funil_venda.py"))
    aqui = Path(__file__).resolve()
    # backend/app/services -> repo
    candidatos.append(aqui.parents[4] / "atendimento" / "ai" / "funil_venda.py")
    for path in candidatos:
        if path.is_file():
            spec = importlib.util.spec_from_file_location("funil_venda", path)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                _FUNIL = mod
                return mod
    raise ImportError("funil_venda.py não encontrado")


def _ler_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    try:
        linhas = path.read_text(encoding="utf-8", errors="replace").splitlines()[-8000:]
    except OSError:
        return []
    for linha in linhas:
        linha = linha.strip()
        if not linha:
            continue
        try:
            obj = json.loads(linha)
        except ValueError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _eventos_webhook() -> list[dict[str, Any]]:
    try:
        from app.sources import espelho
    except Exception:
        return []
    if not espelho.WEBHOOK_QUEUE.is_file():
        return []
    vendas = ("3619", "0837", "3166")
    out = []
    for e in espelho.eventos_recentes(max_lines=8000):
        inst = str(e.get("instance") or "")
        if not any(p in inst for p in vendas):
            continue
        out.append({
            "ts": e.get("ts"),
            "instancia": inst,
            "cid": e.get("conversation_id"),
            "phone": e.get("phone") or "",
            "from_me": bool(e.get("from_me")),
            "text": e.get("text") or "",
            "tipo": "msg",
        })
    return out


def _sem_ao_vivo() -> dict[str, Any] | None:
    """Contador da fila ao vivo. Arquivo velho ou ausente não vira zero."""
    path = Path("/opt/mnrobo/atendimento/ai/private/funil_sem_resposta.json")
    if not path.is_file():
        return None
    try:
        dados = json.loads(path.read_text(encoding="utf-8"))
        ts = float(dados.get("ts") or 0)
    except (OSError, ValueError, TypeError):
        return None
    if time.time() - ts > 900:
        return None
    return dados if isinstance(dados, dict) else None


def coletar_eventos() -> tuple[list[dict[str, Any]], str]:
    mod = _modulo_funil()
    path = Path(mod.caminho_eventos())
    rows = _ler_jsonl(path)
    fonte = "funil_eventos.jsonl" if rows else ""
    hook = _eventos_webhook()
    if hook:
        rows = rows + hook
        fonte = (fonte + "+webhook").strip("+")
    return rows, fonte or "nenhuma"


def montar(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    src = SourceRef(id="funil_venda", label="Funil de vendas", last_update=iso_bahia(agora()))
    try:
        mod = _modulo_funil()
    except ImportError as exc:
        return MetricEnvelope.unavailable(
            str(exc),
            source=src,
            metric_id="comercial.funil_vendas",
        ).model_dump()
    eventos, fonte = coletar_eventos()
    numero = str((filters or {}).get("numero") or "")
    if numero:
        eventos = [e for e in eventos if numero in str(e.get("instancia") or "")]
    agregado = mod.agregar_eventos(eventos)
    ao_vivo = _sem_ao_vivo()
    if agregado is not None:
        if ao_vivo is None:
            agregado["sem_resposta_3min"] = None
            agregado["alerta"] = False
            for bloco in agregado.get("por_numero") or []:
                bloco["sem_resposta_3min"] = None
        else:
            por = ao_vivo.get("por_numero") or {}
            total = int(ao_vivo.get("sem_resposta_3min") or 0)
            agregado["sem_resposta_3min"] = total
            agregado["alerta"] = total > 0
            for bloco in agregado.get("por_numero") or []:
                bloco["sem_resposta_3min"] = int(por.get(bloco.get("id")) or 0)
    if agregado is None:
        return MetricEnvelope.unavailable(
            "Funil de vendas sem eventos — não publicar 0",
            source=src,
            metric_id="comercial.funil_vendas",
        ).model_dump()
    agregado["fonte"] = fonte
    agregado["mensagem_alerta"] = mod.mensagem_alerta(agregado)
    return MetricEnvelope.ok(
        agregado,
        metric_id="comercial.funil_vendas",
        window="hoje",
        source=src,
    ).model_dump()


def drill(page: int, page_size: int) -> dict[str, Any]:
    env = montar()
    valor = env.get("value") or {}
    rows = []
    for bloco in valor.get("por_numero") or []:
        rows.append({
            "id": bloco.get("id"),
            "taxa_ate_teste": bloco.get("taxa_ate_teste"),
            "tempo_medio_ate_teste_s": bloco.get("tempo_medio_ate_teste_s"),
            "sem_resposta_3min": bloco.get("sem_resposta_3min"),
            "etapas": bloco.get("etapas"),
        })
    total = len(rows)
    start = (page - 1) * page_size
    return {
        "total": total,
        "rows": rows[start:start + page_size],
        "state": env,
    }
