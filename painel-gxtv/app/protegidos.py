"""Números que o painel não altera: *0424, *0555, *6098 e 5524988462124."""

from __future__ import annotations

from app.mascarar import so_digitos

_EXATO = "5524988462124"
_SUFIXOS = {"0424", "0555", "6098"}


def protegido(valor) -> bool:
    digitos = so_digitos(valor)
    if not digitos:
        return False
    if digitos == _EXATO or digitos.endswith(_EXATO):
        return True
    if len(digitos) >= 8 and digitos[-4:] in _SUFIXOS:
        return True
    return False
