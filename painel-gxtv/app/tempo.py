"""Relógio da operação: America/Bahia (mesmo fuso de São Paulo, UTC−3)."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Bahia")


def agora() -> datetime:
    return datetime.now(TZ)


def inicio_do_dia(momento: datetime, dias_atras: int = 0) -> datetime:
    local = momento.astimezone(TZ)
    dia = local.date() - timedelta(days=dias_atras)
    return datetime(dia.year, dia.month, dia.day, tzinfo=TZ)


def mesma_hora_ontem(momento: datetime) -> datetime:
    return momento.astimezone(TZ) - timedelta(days=1)
