"""Pausa o robô para um cliente só, na lista que o robô já consulta."""

from __future__ import annotations

from pathlib import Path

from app.mascarar import so_digitos
from app.protegidos import protegido

MARCA = "pausa pedida no painel"
_COMENTARIO = "deixa quieto — " + MARCA


def pausado(caminho: Path, telefone) -> bool:
    digitos = so_digitos(telefone)
    if len(digitos) < 8:
        return False
    for linha in _linhas(caminho):
        if MARCA in linha and _casa(linha, digitos):
            return True
    return False


def pausar(caminho: Path, telefone) -> tuple[bool, str]:
    if protegido(telefone):
        return False, "Esse número é protegido. Não pausei ninguém."
    digitos = so_digitos(telefone)
    if len(digitos) < 8:
        return False, "Não achei o WhatsApp desse cliente, então não pausei ninguém."
    if pausado(caminho, digitos):
        return True, "O robô já estava pausado para esse cliente. Os outros continuam normais."
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("a", encoding="utf-8") as arquivo:
        arquivo.write(f"{digitos} # {_COMENTARIO}\n")
    return True, "O robô não vai responder esse cliente. Os outros continuam normais."


def soltar(caminho: Path, telefone) -> tuple[bool, str]:
    if protegido(telefone):
        return False, "Esse número é protegido. Não mexi em nada."
    digitos = so_digitos(telefone)
    if len(digitos) < 8:
        return False, "Não achei o WhatsApp desse cliente, então não soltei ninguém."
    linhas = _linhas(caminho)
    ficou = []
    tirou = False
    for linha in linhas:
        if MARCA in linha and _casa(linha, digitos):
            tirou = True
            continue
        ficou.append(linha)
    if not tirou:
        return True, "Esse cliente não estava pausado pelo painel."
    texto = "\n".join(ficou)
    if texto:
        texto += "\n"
    with caminho.open("w", encoding="utf-8") as arquivo:
        arquivo.write(texto)
    return True, "O robô volta a responder esse cliente. As outras anotações continuam no lugar."


def _linhas(caminho: Path) -> list[str]:
    try:
        if not caminho.is_file():
            return []
        return caminho.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _casa(linha: str, digitos: str) -> bool:
    bruto = linha.split("#", 1)[0]
    deles = so_digitos(bruto)
    if len(deles) < 8:
        return False
    return deles[-8:] == digitos[-8:]
