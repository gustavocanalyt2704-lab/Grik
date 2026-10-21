# -*- coding: utf-8 -*-
"""Mapa versionado instância/telefone → rótulo do painel.

Fonte: config/mapa_instancias.json (mesmo arquivo no git e na VPS).
Quando o DataCrazy não manda nome, o webhook ainda traz o id da instância
ou o número. Este módulo devolve o rótulo do card (ex.: COBRANÇA P6) para
v1 e v2 somarem na mesma linha.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

_CACHE: dict | None = None
_CACHE_PATH: Path | None = None
_CACHE_MTIME: float | None = None


def _caminhos() -> list[Path]:
    out: list[Path] = []
    env = os.environ.get("MAPA_INSTANCIAS") or ""
    if env.strip():
        out.append(Path(env.strip()))
    here = Path(__file__).resolve()
    out.append(here.with_name("mapa_instancias.json"))
    for parent in here.parents:
        out.append(parent / "config" / "mapa_instancias.json")
    out.extend(
        [
            Path("/opt/mnrobo/config/mapa_instancias.json"),
            Path("/opt/painel-gxtv/config/mapa_instancias.json"),
            Path("/opt/painel-gxtv-v2/config/mapa_instancias.json"),
            Path("/opt/painel-gxtv-v2/backend/app/data/mapa_instancias.json"),
        ]
    )
    visto: set[str] = set()
    uniq: list[Path] = []
    for p in out:
        chave = str(p)
        if chave in visto:
            continue
        visto.add(chave)
        uniq.append(p)
    return uniq


def caminho_mapa() -> Path | None:
    for p in _caminhos():
        if p.is_file():
            return p
    return None


def _carregar(forcar: bool = False) -> dict:
    global _CACHE, _CACHE_PATH, _CACHE_MTIME
    path = caminho_mapa()
    if path is None:
        _CACHE, _CACHE_PATH, _CACHE_MTIME = {"indices": {}}, None, None
        return _CACHE
    mtime = path.stat().st_mtime
    if (
        not forcar
        and _CACHE is not None
        and _CACHE_PATH == path
        and _CACHE_MTIME == mtime
    ):
        return _CACHE
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = {"entradas": []}
    _CACHE = _indexar(doc if isinstance(doc, dict) else {"entradas": []})
    _CACHE_PATH = path
    _CACHE_MTIME = mtime
    return _CACHE


def _digitos(raw) -> str:
    return re.sub(r"\D", "", str(raw or ""))


def _chaves_tel(tel: str) -> list[str]:
    d = _digitos(tel)
    if not d:
        return []
    out = [d]
    if d.startswith("55") and len(d) > 11:
        out.append(d[2:])
    elif len(d) >= 10:
        out.append("55" + d)
    return out


def _indexar(doc: dict) -> dict:
    por: dict[str, str] = {}
    meta: dict[str, dict] = {}
    for ent in doc.get("entradas") or []:
        if not isinstance(ent, dict):
            continue
        rotulo = str(ent.get("rotulo") or "").strip()
        if not rotulo:
            continue
        meta[rotulo] = ent
        for tel in ent.get("telefones") or []:
            for chave in _chaves_tel(tel):
                por[chave] = rotulo
        for iid in ent.get("ids") or []:
            s = str(iid or "").strip()
            if s:
                por[s] = rotulo
                por[s.casefold()] = rotulo
        for ev in ent.get("eventos") or []:
            s = str(ev or "").strip()
            if s:
                por[s] = rotulo
                por[s.casefold()] = rotulo
        for nome in ent.get("nomes_brutos") or []:
            s = str(nome or "").strip()
            if s:
                por[s] = rotulo
                por[s.casefold()] = rotulo
    return {"doc": doc, "por": por, "meta": meta}


def invalidar_cache() -> None:
    global _CACHE, _CACHE_PATH, _CACHE_MTIME
    _CACHE = None
    _CACHE_PATH = None
    _CACHE_MTIME = None


def rotulo_mapeado(raw=None, *, phone=None, evento=None, instance_id=None) -> str | None:
    """Devolve o rótulo do card se raw/phone/evento/id estiver no mapa. Senão None."""
    idx = _carregar().get("por") or {}
    if not idx:
        return None
    candidatos = []
    for valor in (instance_id, evento, raw, phone):
        if valor is None:
            continue
        if isinstance(valor, dict):
            candidatos.extend(
                [
                    valor.get("id"),
                    valor.get("instanceId"),
                    valor.get("name"),
                    valor.get("phone"),
                    valor.get("phoneNumber"),
                    valor.get("wid"),
                ]
            )
        else:
            candidatos.append(valor)
    vistos: set[str] = set()
    for cand in candidatos:
        texto = str(cand or "").strip()
        if not texto or texto in vistos:
            continue
        vistos.add(texto)
        if texto in idx:
            return idx[texto]
        baixo = texto.casefold()
        if baixo in idx:
            return idx[baixo]
        for chave in _chaves_tel(texto):
            if chave in idx:
                return idx[chave]
    return None


def grupo_mapeado(rotulo: str) -> str | None:
    ent = (_carregar().get("meta") or {}).get(rotulo) or {}
    g = str(ent.get("grupo") or "").strip()
    return g or None


def painel_mapeado(raw=None, *, phone=None, evento=None, instance_id=None) -> str | None:
    rotulo = rotulo_mapeado(raw, phone=phone, evento=evento, instance_id=instance_id)
    if not rotulo:
        return None
    ent = (_carregar().get("meta") or {}).get(rotulo) or {}
    pn = str(ent.get("painel") or "").strip()
    return pn or None
