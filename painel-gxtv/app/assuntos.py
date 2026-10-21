"""Assuntos, aplicativos e aparelhos por palavras — sem IA paga."""

from __future__ import annotations

import re
import unicodedata

_ATENDENTES = (
    ("robo", "Robô", "O", ("robo", "bot", "mnrobo", "assistant")),
    ("jorge", "Jorge", "O", ("jorge",)),
    ("camila", "Camila", "A", ("camila",)),
    ("guilherme", "Guilherme", "O", ("guilherme",)),
    ("gustavo", "Gustavo", "O", ("gustavo",)),
)

_ASSUNTOS = (
    ("instalacao", "Instalação", ("instalar", "instalacao", "instalaç", "baixar", "configurar o app", "codigo do app", "código do app")),
    ("travando", "Imagem travando", ("travando", "travou", "congela", "congelou", "buffering", "nao carrega", "não carrega", "tela preta", "sem imagem")),
    ("pagamento", "Pagamento", ("paguei", "pix", "comprovante", "pagamento")),
    ("renovacao", "Renovação", ("renov", "venceu", "vencimento", "mensalidade")),
    ("teste", "Teste", ("teste", "degustacao", "degustação")),
    ("senha", "Senha e acesso", ("senha", "login", "usuario", "usuário")),
    ("canais", "Canais e filmes", ("canal", "canais", "filme", "serie", "série", "lista m3u", "epg")),
)

_APPS = (
    ("XCIPTV", ("xciptv", "xc iptv")),
    ("Brasil IPTV", ("brasil iptv", "brasiliptv")),
    ("Max Player", ("max player", "maxplayer")),
    ("XP IPTV", ("xp iptv", "xpiptv")),
)

_APARELHOS = (
    ("Android TV", ("android tv", "androidtv", "google tv")),
    ("Smart TV Samsung", ("samsung",)),
    ("Smart TV LG", (" lg ", "lg webos", "webos")),
    ("Smart TV TCL", ("tcl",)),
    ("Smart TV Philco", ("philco",)),
    ("Smart TV AOC", (" aoc", "aoc ")),
    ("Smart TV Panasonic", ("panasonic",)),
    ("Smart TV Sony", ("sony", "bravia")),
    ("Smart TV Philips", ("philips",)),
    ("iPhone", ("iphone", "ios")),
    ("TV Box", ("tv box", "tvbox", "mxq")),
    ("Celular", ("celular", "smartphone")),
    ("Smart TV", ("smart tv", "smartv")),
)


def dobrar(texto) -> str:
    base = unicodedata.normalize("NFKD", str(texto or ""))
    base = "".join(c for c in base if not unicodedata.combining(c))
    return " " + base.casefold() + " "


def _tem(chave: str, texto, prefixo: bool = False) -> bool:
    bruto = dobrar(texto)
    alvo = dobrar(chave).strip()
    if f" {alvo} " in bruto:
        return True
    if prefixo and " " not in alvo and len(alvo) >= 4:
        return re.search(rf"(?<![a-z0-9]){re.escape(alvo)}", bruto) is not None
    return False


def atendente_de(nome, tipo) -> str | None:
    if any(_tem(chave, tipo) for chave in ("bot", "robo", "sistema", "assistant")):
        return "robo"
    for codigo, _nome, _artigo, chaves in _ATENDENTES:
        if any(_tem(chave, nome) or _tem(chave, tipo) for chave in chaves):
            return codigo
    return None


def nome_atendente(codigo: str) -> tuple[str, str]:
    for ident, nome, artigo, _chaves in _ATENDENTES:
        if ident == codigo:
            return nome, artigo
    return "Atendente", "O"


def ordem_atendentes() -> list[str]:
    return [codigo for codigo, *_resto in _ATENDENTES]


def assuntos_de(texto: str) -> list[str]:
    achados = []
    for codigo, _rotulo, chaves in _ASSUNTOS:
        if any(_tem(chave, texto, prefixo=True) for chave in chaves):
            achados.append(codigo)
    return achados


def rotulo_assunto(codigo: str) -> str:
    for ident, rotulo, _chaves in _ASSUNTOS:
        if ident == codigo:
            return rotulo
    return "Outro assunto"


def app_de(texto: str) -> str | None:
    for nome, chaves in _APPS:
        if any(_tem(chave, texto, prefixo=True) for chave in chaves):
            return nome
    return None


def aparelho_de(texto: str) -> str | None:
    for nome, chaves in _APARELHOS:
        if any(_tem(chave, texto, prefixo=True) for chave in chaves):
            return nome
    return None


def parece_codigo_interno(texto: str) -> bool:
    return bool(re.fullmatch(r"[a-z]{0,3}\d[a-z0-9]{3,}", dobrar(texto).strip()))
