# -*- coding: utf-8 -*-
"""OCULTAR_JORGE_1110 — lista CENTRAL do que NÃO aparece no painel do Gustavo (só visão; o robô segue atendendo).
Pra reverter: esvaziar os conjuntos abaixo e reiniciar o painel-gxtv."""
PAINEIS_OCULTOS = {"jorge", "ryjdzvzdge"}      # painel/reseller Sigma (nome ou id, minúsculo)
INSTANCIAS_OCULTAS = {"jorge"}                 # instância WhatsApp (rótulo, minúsculo)
ATENDENTES_OCULTOS = {"jorge"}                 # nome de atendente atribuído


def _n(v) -> str:
    return " ".join(str(v or "").split()).casefold()


def instancia_oculta(v) -> bool:
    return _n(v) in INSTANCIAS_OCULTAS


def painel_oculto(*vals) -> bool:
    return any(_n(v) in PAINEIS_OCULTOS for v in vals if v)


def atendente_oculto(v) -> bool:
    return _n(v) in ATENDENTES_OCULTOS
