"""Timezone civil oficial do painel: America/Bahia (UTC-3, sem DST)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Bahia")
TZ_NAME = "America/Bahia"


def agora() -> datetime:
    return datetime.now(TZ)


def hoje() -> date:
    return agora().date()


def inicio_dia(d: date | None = None) -> datetime:
    d = d or hoje()
    return datetime(d.year, d.month, d.day, tzinfo=TZ)


def fim_dia(d: date | None = None) -> datetime:
    return inicio_dia(d) + timedelta(days=1)


def janela_periodo(periodo: str) -> tuple[datetime, datetime, str]:
    """Retorna (inicio, fim, rótulo) para filtros globais."""
    h = hoje()
    if periodo == "ontem":
        d = h - timedelta(days=1)
        return inicio_dia(d), fim_dia(d), d.isoformat()
    if periodo == "7d":
        ini = inicio_dia(h - timedelta(days=6))
        return ini, fim_dia(h), f"{ini.date().isoformat()}→{h.isoformat()}"
    if periodo == "30d":
        ini = inicio_dia(h - timedelta(days=29))
        return ini, fim_dia(h), f"{ini.date().isoformat()}→{h.isoformat()}"
    # YYYY-MM-DD explícito
    if len(periodo) == 10 and periodo[4] == "-":
        d = date.fromisoformat(periodo)
        return inicio_dia(d), fim_dia(d), d.isoformat()
    # padrão: hoje
    return inicio_dia(h), fim_dia(h), h.isoformat()


def iso_bahia(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ).isoformat()


def telefone_final(phone: str | None, digitos: int = 4) -> str:
    """Exibe telefone só pelo final — regra dura Gustavo."""
    if not phone:
        return "final —"
    digits = "".join(c for c in str(phone) if c.isdigit())
    if not digits:
        return "final —"
    return f"final {digits[-digitos:]}"
