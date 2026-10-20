# -*- coding: utf-8 -*-
"""Bloco ISOLADO de métricas do lote de atenção no Painel GXTV.

Lê só JSON local em atendimento/ai/private/lote_atencao_metricas/ — zero GET DataCrazy.
NÃO altera app/metricas.py (aba Métricas geral). Aplicar DEPOIS do conserto
bc-8d350dba-e67d-5751-9dfc-a4b44e6c73b4.

Drop-in: copiar para /opt/painel-gxtv/app/lote_atencao_metricas.py
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    from app.tempo import TZ
except Exception:
    from datetime import timezone, timedelta as _td
    TZ = timezone(_td(hours=-3))

PRIV_CANDIDATOS = (
    os.environ.get('LOTE_ATENCAO_PRIV'),
    '/opt/mnrobo/atendimento/ai/private',
    '/workspace/atendimento/ai/private',
)


def _priv() -> Path:
    for p in PRIV_CANDIDATOS:
        if p and Path(p).is_dir():
            return Path(p)
    return Path('/opt/mnrobo/atendimento/ai/private')


def _met_dir() -> Path:
    return _priv() / 'lote_atencao_metricas'


def _ler_dia(dia: str) -> dict | None:
    p = _met_dir() / ('%s.json' % dia)
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def _hoje() -> str:
    return datetime.now(TZ).strftime('%Y-%m-%d')


def pacote(periodo: str = 'hoje') -> dict:
    """hoje | ontem | 7d | YYYY-MM-DD — só disco local."""
    hoje = _hoje()
    if periodo == 'hoje':
        dia = hoje
    elif periodo == 'ontem':
        dia = (datetime.now(TZ).date() - timedelta(days=1)).strftime('%Y-%m-%d')
    elif periodo == '7d':
        dias = []
        base = datetime.now(TZ).date()
        for i in range(6, -1, -1):
            d = (base - timedelta(days=i)).strftime('%Y-%m-%d')
            dados = _ler_dia(d) or {
                'dia': d, 'chamados': 0, 'por_motivo': {}, 'respostas': 0,
                'taxa_resposta': 0, 'feedbacks': 0, 'feedback_tipos': {},
                'reabertos_ajuda': 0, 'lista_feedbacks': [], 'vs_anterior': {},
            }
            dias.append(dados)
        return {'ok': True, 'periodo': '7d', 'dias': dias, 'quando': time.time(), 'fonte': 'local'}
    else:
        dia = periodo
    dados = _ler_dia(dia)
    if dados is None:
        # tenta gerar via pacote lote_atencao.metricas se disponível no PYTHONPATH
        try:
            from lote_atencao import metricas as LM
            dados = LM.atualizar(dia=dia, priv=str(_priv()))
        except Exception:
            dados = {
                'dia': dia, 'chamados': 0, 'por_motivo': {}, 'respostas': 0,
                'taxa_resposta': 0, 'feedbacks': 0, 'feedback_tipos': {},
                'reabertos_ajuda': 0, 'lista_feedbacks': [], 'vs_anterior': {},
                'vazio': True,
            }
    return {'ok': True, 'periodo': periodo, 'dia': dia, 'dados': dados, 'quando': time.time(), 'fonte': 'local'}
