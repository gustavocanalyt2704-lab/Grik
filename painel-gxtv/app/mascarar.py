"""Telefones saem do servidor só mascarados: * e os 4 últimos dígitos."""

from __future__ import annotations

import re

_DIGITOS = re.compile(r"\d")
_LONGO = re.compile(r"(?<!\d)(\d{8,})(?!\d)")


def so_digitos(valor) -> str:
    return "".join(_DIGITOS.findall(str(valor or "")))


def mascarar_telefone(valor) -> str | None:
    digitos = so_digitos(valor)
    if len(digitos) < 4:
        return None
    return "*" + digitos[-4:]


def limpar_texto(texto: str) -> str:
    """Troca um telefone grudado numa frase. Não mexe em horário nem em valor."""
    if not texto:
        return texto

    def trocar(m: re.Match) -> str:
        return mascarar_telefone(m.group(1)) or "****"

    return _LONGO.sub(trocar, str(texto))


_CHAVES_TELEFONE = {"telefone", "phone", "whatsapp", "fone", "celular"}
_CHAVES_PROIBIDAS = {
    "password",
    "senha",
    "token",
    "dsn",
    "authorization",
    "access_token",
    "secret",
    "conteudo_texto",
    "texto",
    "mensagem",
    "payload",
}


def sanitizar(valor):
    """Corta segredo e telefone completo antes de qualquer resposta."""
    if isinstance(valor, dict):
        limpo = {}
        for chave, item in valor.items():
            nome = str(chave).casefold()
            if nome in _CHAVES_PROIBIDAS or nome.endswith("_token") or nome.endswith("_dsn"):
                continue
            if nome in _CHAVES_TELEFONE:
                limpo[chave] = mascarar_telefone(item)
                continue
            limpo[chave] = sanitizar(item)
        return limpo
    if isinstance(valor, list):
        return [sanitizar(item) for item in valor]
    if isinstance(valor, str):
        return limpar_texto(valor)
    return valor
