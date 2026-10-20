"""Estados honestos de qualquer métrica/bloco do painel."""

from __future__ import annotations

from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from app.core.timezone import TZ_NAME, agora, iso_bahia

T = TypeVar("T")


class MetricState(str, Enum):
    LOADING = "loading"
    OK = "ok"
    EMPTY = "empty"
    ERROR = "error"
    STALE = "stale"  # atrasado — dado antigo além do SLA
    UNAVAILABLE = "unavailable"  # fonte caiu; NUNCA inventar 0


class SourceRef(BaseModel):
    id: str
    label: str
    last_update: str | None = None
    cache_ttl_s: int | None = None


class MetricEnvelope(BaseModel, Generic[T]):
    """Envelope padrão: todo número/bloco passa por aqui."""

    state: MetricState
    value: T | None = None
    message: str | None = None
    timezone: str = TZ_NAME
    window: str | None = None
    source: SourceRef | None = None
    metric_id: str | None = None
    computed_at: str = Field(default_factory=lambda: iso_bahia(agora()) or "")
    is_seed: bool = False  # True só em seed coerente marcado

    @classmethod
    def ok(
        cls,
        value: T,
        *,
        metric_id: str | None = None,
        window: str | None = None,
        source: SourceRef | None = None,
        is_seed: bool = False,
    ) -> "MetricEnvelope[T]":
        return cls(
            state=MetricState.OK,
            value=value,
            metric_id=metric_id,
            window=window,
            source=source,
            is_seed=is_seed,
        )

    @classmethod
    def empty(cls, message: str = "Sem dados neste período", **kw: Any) -> "MetricEnvelope[T]":
        return cls(state=MetricState.EMPTY, message=message, **kw)

    @classmethod
    def error(cls, message: str, **kw: Any) -> "MetricEnvelope[T]":
        return cls(state=MetricState.ERROR, message=message, **kw)

    @classmethod
    def stale(
        cls,
        value: T | None,
        message: str,
        *,
        source: SourceRef | None = None,
        **kw: Any,
    ) -> "MetricEnvelope[T]":
        return cls(
            state=MetricState.STALE,
            value=value,
            message=message,
            source=source,
            **kw,
        )

    @classmethod
    def unavailable(
        cls,
        message: str,
        *,
        last_value: T | None = None,
        source: SourceRef | None = None,
        **kw: Any,
    ) -> "MetricEnvelope[T]":
        """Fonte caiu: mostra última atualização, nunca 0 inventado."""
        return cls(
            state=MetricState.UNAVAILABLE,
            value=last_value,
            message=message,
            source=source,
            **kw,
        )

    @classmethod
    def loading(cls, message: str = "Carregando…") -> "MetricEnvelope[T]":
        return cls(state=MetricState.LOADING, message=message)


def gestor_indisponivel(last_payload: dict | None, last_update: str | None) -> MetricEnvelope[dict]:
    src = SourceRef(
        id="gestor",
        label="Gestor IPTV",
        last_update=last_update,
    )
    return MetricEnvelope.unavailable(
        "Gestor indisponível — mostrando última atualização conhecida",
        last_value=last_payload,
        source=src,
        metric_id="comercial.gestor",
    )
