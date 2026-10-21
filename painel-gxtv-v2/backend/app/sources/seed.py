"""Seed coerente — só quando fontes reais indisponíveis e PAINEL_V2_SEED=1.

Sempre marcado is_seed=True. Nunca se passa por dado real do Gestor/espelho.
"""

from __future__ import annotations

import os
from typing import Any

from app.core.states import MetricEnvelope, SourceRef
from app.core.timezone import agora, iso_bahia


def seed_habilitado() -> bool:
    return os.environ.get("PAINEL_V2_SEED", "0") == "1"


def seed_f1_shell() -> dict[str, Any]:
    """Dados de demonstração da casca F1 (filtros + estados)."""
    stamp = iso_bahia(agora())
    return {
        "is_seed": True,
        "generated_at": stamp,
        "filtros": {
            "numeros": [
                {"id": "3619", "label": "WhatsApp 3619"},
                {"id": "0837", "label": "WhatsApp 0837"},
            ],
            "atendentes": [
                {"id": "Robô", "label": "Robô"},
                {"id": "Jorge", "label": "Jorge"},
                {"id": "Gustavo", "label": "Gustavo"},
            ],
            "apps": [
                {"id": "Max Player", "label": "Max Player"},
                {"id": "IBO Player", "label": "IBO Player"},
                {"id": "Brasil IPTV", "label": "Brasil IPTV"},
            ],
            "aparelhos": [
                {"id": "Samsung", "label": "Samsung"},
                {"id": "LG", "label": "LG"},
                {"id": "Fire Stick", "label": "Fire Stick"},
            ],
        },
        "exemplos_estado": {
            "ok": MetricEnvelope.ok(
                {"n": 12},
                metric_id="inicio.entrada_viva",
                window="hoje",
                source=SourceRef(id="seed", label="Seed F1", last_update=stamp),
                is_seed=True,
            ).model_dump(),
            "empty": MetricEnvelope.empty(
                "Nenhuma entrada neste filtro",
                metric_id="inicio.entrada_viva",
                is_seed=True,
            ).model_dump(),
            "error": MetricEnvelope.error(
                "Falha ao agregar (exemplo)",
                metric_id="operacao.problemas",
                is_seed=True,
            ).model_dump(),
            "stale": MetricEnvelope.stale(
                {"n": 7},
                "Dado atrasado — última sync há 22 min",
                metric_id="comercial.vendas",
                source=SourceRef(id="gestor", label="Gestor (cache)", last_update=stamp),
                is_seed=True,
            ).model_dump(),
            "unavailable": MetricEnvelope.unavailable(
                "Gestor indisponível — última atualização conhecida",
                last_value={"vendas": None, "hint": "não é zero"},
                source=SourceRef(id="gestor", label="Gestor IPTV", last_update=stamp),
                metric_id="comercial.vendas",
                is_seed=True,
            ).model_dump(),
        },
    }


def seed_inicio() -> dict[str, Any]:
    """KPIs + feeds do Início (F2) — só com PAINEL_V2_SEED=1."""
    stamp = iso_bahia(agora())
    src = SourceRef(id="seed", label="Seed F2", last_update=stamp)
    return {
        "is_seed": True,
        "generated_at": stamp,
        "kpis": {
            "faturamento": MetricEnvelope.ok(
                4280.5, metric_id="inicio.faturamento", window="hoje", source=src, is_seed=True
            ).model_dump(),
            "renovacoes": MetricEnvelope.ok(
                37, metric_id="inicio.renovacoes", window="hoje", source=src, is_seed=True
            ).model_dump(),
            "vencem_hoje": MetricEnvelope.ok(
                {
                    "total": 112,
                    "renovaram": 37,
                    "pendentes": 75,
                },
                metric_id="inicio.vencem_hoje",
                window="hoje",
                source=src,
                is_seed=True,
            ).model_dump(),
            "atendidos": MetricEnvelope.ok(
                214, metric_id="inicio.atendidos", window="hoje", source=src, is_seed=True
            ).model_dump(),
            "esperando_15min": MetricEnvelope.ok(
                {
                    "n": 3,
                    "minutos": 15,
                    "lista": [
                        {
                            "conversation_id": "seed-1",
                            "phone_final": "final 9433",
                            "name": "Cliente A",
                            "espera_min": 22.5,
                            "instance": "3619",
                        },
                        {
                            "conversation_id": "seed-2",
                            "phone_final": "final 1204",
                            "name": "Cliente B",
                            "espera_min": 18.0,
                            "instance": "0837",
                        },
                        {
                            "conversation_id": "seed-3",
                            "phone_final": "final 7781",
                            "name": None,
                            "espera_min": 16.2,
                            "instance": "3619",
                        },
                    ],
                },
                metric_id="inicio.esperando_15min",
                window="agora",
                source=src,
                is_seed=True,
            ).model_dump(),
            "clientes_min": MetricEnvelope.ok(
                1.4, metric_id="inicio.clientes_min", window="10min", source=src, is_seed=True
            ).model_dump(),
        },
        "entrada_viva": MetricEnvelope.ok(
            [
                {
                    "t": stamp,
                    "phone_final": "final 9433",
                    "name": "Cliente A",
                    "text": "Oi, o app não abre",
                    "instance": "3619",
                    "conversation_id": "seed-1",
                    "evento": "msg",
                },
                {
                    "t": stamp,
                    "phone_final": "final 1204",
                    "name": "Cliente B",
                    "text": "Quero renovar",
                    "instance": "0837",
                    "conversation_id": "seed-2",
                    "evento": "msg",
                },
            ],
            metric_id="inicio.entrada_viva",
            window="5min",
            source=src,
            is_seed=True,
        ).model_dump(),
        "log_operacional": MetricEnvelope.ok(
            [
                {"t": stamp, "line": "POLL ocupadas=2 aguardando=3"},
                {"t": stamp, "line": "ENVIO ok cid=seed-9 instancia=3619"},
                {"t": stamp, "line": "ALERTA espera>15min n=3"},
            ],
            metric_id="inicio.log_operacional",
            source=src,
            is_seed=True,
        ).model_dump(),
        "saude_espelho": MetricEnvelope.ok(
            {
                "lag_s": 4.2,
                "cobertura": 0.91,
                "eventos_hoje": 1480,
                "msgs_com_texto": 1340,
                "queue_presente": True,
                "live_log_presente": True,
                "fonte": "seed",
            },
            metric_id="inicio.saude_espelho",
            window="agora",
            source=src,
            is_seed=True,
        ).model_dump(),
    }
