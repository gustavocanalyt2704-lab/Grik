#!/usr/bin/env python3
"""Copia o hash bcrypt do painel atual para o arquivo próprio do v2.

Não altera /var/lib/painel-gxtv/auth.json.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.auth import importar_credencial_v1, v2_auth_path  # noqa: E402


def main() -> int:
    ok = importar_credencial_v1()
    print(f"[v2] auth próprio {v2_auth_path()} {'pronto' if ok else 'ainda vazio'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
