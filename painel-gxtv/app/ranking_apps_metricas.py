# -*- coding: utf-8 -*-
"""Bloco ISOLADO — placar ranking apps×aparelho no Painel GXTV.

Lê private/ranking_apps_placar.json (gerado pelo robô / ranking_apps.placar).
Zero GET DataCrazy. NÃO altera app/metricas.py.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

try:
    from app.tempo import TZ
except Exception:
    from datetime import timezone, timedelta as _td
    TZ = timezone(_td(hours=-3))

PRIV_CANDIDATOS = (
    os.environ.get('RANKING_APPS_PRIV'),
    os.environ.get('LOTE_ATENCAO_PRIV'),
    '/opt/mnrobo/atendimento/ai/private',
    '/workspace/atendimento/ai/private',
)


def _priv() -> Path:
    for p in PRIV_CANDIDATOS:
        if p and Path(p).is_dir():
            return Path(p)
    return Path('/opt/mnrobo/atendimento/ai/private')


def _ler_placar() -> dict | None:
    p = _priv() / 'ranking_apps_placar.json'
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


FICHAS_JSON = Path(os.environ.get(
    'RANKING_FICHAS_JSON',
    '/opt/mnrobo/atendimento/ai/private/ranking_fichas/ranking_fichas.json'))


def _ler_fichas() -> dict | None:
    """ORDEM1835: aba de apps lê o ranking das fichas (recálculo diário 03:17). Lido a cada request."""
    try:
        d = json.loads(FICHAS_JSON.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    aps = {}
    for k, v in (d.get('aparelhos') or {}).items():
        if not isinstance(v, dict):
            continue
        aps[k] = {
            'nome': v.get('nome') or k,
            'ordem': list(v.get('ordem_sugerida') or []),
            'fichas': v.get('fichas_usadas') or 0,
            'apps': [a for a in (v.get('apps') or []) if isinstance(a, dict)],
            # RANKING_VISUAL_0810: campos extras pra aba nova (só leitura do mesmo JSON)
            'ordem_robo': list(v.get('ordem_robo_base') or []),
            'amostra_baixa': list(v.get('amostra_baixa') or []),
            'fora_lista': list(v.get('fora_da_lista_do_robo_com_amostra') or []),
            'trocas': [t for t in (v.get('trocas') or []) if isinstance(t, dict)][:6],
        }
    return {'gerado_em': d.get('gerado_em'), 'fonte': d.get('fonte'),
            'min_n_ordem': d.get('min_n_ordem'), 'geral': d.get('geral') or {}, 'aparelhos': aps,
            # APPS1910: cards da aba nova (ordem = regras_0810.md, 7/30 dias). RANKING_APPS_VISUAL=antigo volta a aba velha.
            'cards': [c for c in (d.get('cards') or []) if isinstance(c, dict)],
            'regras_fonte': d.get('regras_fonte') or {},
            'visual': os.environ.get('RANKING_APPS_VISUAL', 'novo')}


def _ler_placar_fichas() -> dict | None:
    """FIX1710: bloco 'placar' do ranking_fichas.json (fichas com 'quando' nas últimas 4 h / 7 dias)."""
    try:
        d = json.loads(FICHAS_JSON.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    p = d.get('placar')
    if not isinstance(p, dict) or not p.get('linhas'):
        return None
    return {'ok': True, 'quando': p.get('quando'), 'fonte': 'fichas (ranking_fichas.json, a cada 10 min)',
            'min_casos': d.get('min_n_ordem', 10), 'exploracao': 0, 'linhas': p.get('linhas') or [], 'ordens': {}}


def _gerar() -> dict:
    """Tenta gerar via ranking_apps se estiver no PYTHONPATH do painel."""
    try:
        import sys
        for cand in (
            '/opt/mnrobo/atendimento/ai',
            '/workspace/atendimento/ai',
        ):
            if cand not in sys.path and Path(cand).is_dir():
                sys.path.insert(0, cand)
        import ranking_apps as RA
        os.environ.setdefault('RANKING_APPS_PRIV', str(_priv()))
        return RA.placar()
    except Exception as e:
        return {
            'ok': False,
            'erro': str(e)[:200],
            'linhas': [],
            'ordens': {},
            'quando': time.time(),
            'fonte': 'erro',
        }


def pacote(periodo: str = '4h') -> dict:
    """periodo: 4h | 7d | tudo — filtra exibição; dados já trazem ambos."""
    fichas = _ler_fichas()
    pf = _ler_placar_fichas()
    dados = _ler_placar()
    # FIX1710: o placar do robô (ranking_apps_placar.json) parou em 05/10 (o robô deixou de gravar eventos em 08/10).
    # Se estiver velho (> 2 h), o placar vem das fichas (recalculado a cada 10 min): 4 h e 7 dias reais.
    if pf and (not dados or time.time() - float(dados.get('quando') or 0) > 7200):
        dados = pf
    elif not dados or not dados.get('linhas'):
        dados = _gerar()
    linhas = list(dados.get('linhas') or [])
    if periodo == '4h':
        # destaca quem tem amostra 4h; mantém todos mas ordena por taxa_4h
        linhas = sorted(
            linhas,
            key=lambda r: (
                -(r.get('taxa_4h') if r.get('taxa_4h') is not None else -1),
                -(r.get('n_4h') or 0),
                r.get('aparelho') or '',
                r.get('app') or '',
            ),
        )
    elif periodo == '7d':
        linhas = sorted(
            linhas,
            key=lambda r: (
                -(r.get('taxa_7d') if r.get('taxa_7d') is not None else -1),
                -(r.get('n_7d') or 0),
                r.get('aparelho') or '',
                r.get('app') or '',
            ),
        )
    return {
        'ok': bool(dados.get('ok', True)),
        'periodo': periodo,
        'quando': dados.get('quando') or time.time(),
        'fonte': dados.get('fonte') or 'local',
        'min_casos': dados.get('min_casos', 10),
        'exploracao': dados.get('exploracao', 0.15),
        'linhas': linhas,
        'ordens': dados.get('ordens') or {},
        'erro': dados.get('erro'),
        'fichas': fichas,  # ORDEM1835: fonte principal da aba
    }
