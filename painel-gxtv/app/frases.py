"""Frases curtas, em português simples."""

from __future__ import annotations


def inteiro(valor: float | int) -> str:
    return f"{int(round(valor)):,}".replace(",", ".")


def reais(valor: float, centavos: bool = False) -> str:
    if centavos:
        texto = f"{valor:,.2f}"
        texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
        return "R$ " + texto
    return "R$ " + inteiro(valor)


def comparacao(hoje, ontem, dinheiro: bool = False) -> str | None:
    if hoje is None or ontem is None:
        return None
    diff = hoje - ontem
    if dinheiro:
        if abs(diff) < 0.5:
            return "igual a ontem neste horário"
        if diff > 0:
            return f"{reais(diff)} a mais que ontem neste horário"
        return f"{reais(abs(diff))} a menos que ontem neste horário"
    diff = int(round(diff))
    if diff == 0:
        return "igual a ontem neste horário"
    n = inteiro(abs(diff))
    if diff > 0:
        return f"{n} a mais que ontem neste horário"
    return f"{n} a menos que ontem neste horário"


def seta(hoje, ontem, inverso: bool = False) -> dict | None:
    if hoje is None or ontem is None:
        return None
    if ontem == 0:
        if hoje == 0:
            return {"txt": "igual", "dir": "flat"}
        return None
    delta = (hoje - ontem) / abs(ontem) * 100
    if abs(delta) < 0.5:
        return {"txt": "0%", "dir": "flat"}
    bom = delta > 0
    if inverso:
        bom = not bom
    sentido = "up" if delta > 0 else "down"
    return {
        "txt": f"{'▲' if delta > 0 else '▼'} {inteiro(abs(delta))}%",
        "dir": sentido,
        "bom": bom,
    }


def juntar(frase: str, comparacao_txt: str | None) -> str:
    if not comparacao_txt:
        return frase
    if frase.endswith("."):
        frase = frase[:-1]
    return f"{frase} ({comparacao_txt})"


def duracao(segundos) -> str | None:
    if segundos is None:
        return None
    segundos = int(round(segundos))
    if segundos < 60:
        return f"{segundos} s"
    return f"{segundos // 60} min {segundos % 60:02d} s"


def falta(segundos: float | None) -> str:
    if segundos is None:
        return "sem horário marcado"
    if segundos < 5:
        return "agora"
    segundos = int(segundos)
    if segundos < 60:
        return f"falta {segundos}s"
    minutos = segundos // 60
    if minutos < 60:
        return f"falta {minutos}min"
    horas, minutos = divmod(minutos, 60)
    if horas < 48:
        return f"falta {horas}h {minutos:02d}min"
    dias, horas = divmod(horas, 24)
    return f"falta {dias}d {horas}h"
