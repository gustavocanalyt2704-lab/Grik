"""Aviso no registro no máximo uma vez por hora para a mesma chave."""

from __future__ import annotations

import logging
import time

_log = logging.getLogger("painel")
_visto: dict[str, float] = {}


def avisar(chave: str, mensagem: str, *args, intervalo: float = 3600.0) -> None:
    agora = time.monotonic()
    if agora - _visto.get(chave, -1e9) < intervalo:
        return
    _visto[chave] = agora
    _log.warning(mensagem, *args)
