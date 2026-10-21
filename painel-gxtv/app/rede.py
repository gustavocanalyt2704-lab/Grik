"""Chamada HTTP das ações. Segredo fica só no cabeçalho e não entra em log."""

from __future__ import annotations

import json
import urllib.error
import urllib.request


def pedir(metodo: str, url: str, corpo: dict | None, token: str | None, timeout: float = 12.0):
    """Devolve (status, json ou None, erro). erro é 'tempo', 'sem_rede' ou None."""
    dados = None
    if corpo is not None:
        dados = json.dumps(corpo).encode("utf-8")
    req = urllib.request.Request(url, data=dados, method=(metodo or "GET").upper())
    req.add_header("Accept", "application/json")
    if dados is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            bruto = resp.read(1_000_000)
            status = getattr(resp, "status", 200)
    except urllib.error.HTTPError as exc:
        try:
            bruto = exc.read(4000)
        except OSError:
            bruto = b""
        status = exc.code
    except TimeoutError:
        return 0, None, "tempo"
    except urllib.error.URLError as exc:
        motivo = str(getattr(exc, "reason", "") or "").casefold()
        if "timed out" in motivo or "timeout" in motivo:
            return 0, None, "tempo"
        return 0, None, "sem_rede"
    except OSError:
        return 0, None, "sem_rede"
    if not bruto:
        return status, None, None
    try:
        return status, json.loads(bruto.decode("utf-8", errors="replace")), None
    except (UnicodeError, json.JSONDecodeError, ValueError):
        return status, None, None
