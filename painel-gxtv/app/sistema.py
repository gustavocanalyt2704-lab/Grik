"""Agenda e estado do robô, só com comandos de leitura."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

from app.rotinas_parse import ordenar, parse_crontab, parse_timers

_SCRIPT = "/usr/local/lib/painel-gxtv/ler_rotinas.sh"


def robo_ativo() -> bool | None:
    try:
        resultado = subprocess.run(
            ["systemctl", "is-active", "mnrobo"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    texto = (resultado.stdout or "").strip()
    if texto in {"active", "inactive", "failed", "activating", "deactivating"}:
        return texto == "active"
    return None


def ler_mapa(caminho: Path) -> dict:
    try:
        dado = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"unidades": {}, "cron": []}
    if not isinstance(dado, dict):
        return {"unidades": {}, "cron": []}
    return dado


def ler_motivos(caminho: Path) -> dict:
    try:
        dado = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(dado, dict):
        return {}
    return {str(chave).casefold(): str(valor) for chave, valor in dado.items()}


def ler_rotinas(mapa: dict, agora: datetime) -> tuple[list | None, str | None]:
    """Timers do systemd + tarefas de /etc/cron.d (lidas direto do arquivo, sem sudo e sem crontab -l)."""
    texto = _rodar_sem_root()
    if texto is None:
        return None, "sem dado — não consegui ler os agendamentos do servidor"
    partes = _partir(texto)
    resultados = _resultados(partes.get("RESULTS", ""))
    timers = parse_timers(partes.get("SHOW", ""), resultados, mapa, agora)
    crons = []
    for usuario, linhas in _cron_d().items():
        crons += parse_crontab("\n".join(linhas), usuario, mapa, agora)
    todas = ordenar(timers + crons, agora)
    for item in todas:
        tecnico = str(item.get("tecnico") or "")
        item["relevante"] = (not item.get("sem_descricao")) and ("mnrobo" in tecnico or tecnico.startswith("cron ") or "backup" in tecnico)
    todas.sort(key=lambda item: 0 if item["relevante"] else 1)
    return todas, None


def _cron_d(pasta: Path = Path("/etc/cron.d")) -> dict[str, list[str]]:
    """Cada linha de /etc/cron.d tem o usuário no 6º campo: tira ele e agrupa por usuário."""
    saida: dict[str, list[str]] = {}
    try:
        arquivos = sorted(p for p in pasta.iterdir() if p.is_file() and not p.name.startswith("."))
    except OSError:
        return saida
    for arq in arquivos:
        try:
            texto = arq.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for linha in texto.splitlines():
            bruto = linha.strip()
            if not bruto or bruto.startswith("#") or "=" in bruto.split()[0]:
                continue
            campos = bruto.split()
            if bruto.startswith("@"):
                if len(campos) < 3:
                    continue
                usuario, resto = campos[1], [campos[0]] + campos[2:]
            else:
                if len(campos) < 7:
                    continue
                usuario, resto = campos[5], campos[:5] + campos[6:]
            saida.setdefault(usuario, []).append(" ".join(resto))
    return saida


def _rodar_sem_root() -> str | None:
    timers = _rodar(["systemctl", "list-units", "--type=timer", "--all", "--no-legend", "--plain", "--no-pager"])
    if timers is None:
        return None
    ids = [linha.split()[0] for linha in timers.splitlines() if linha.strip().endswith(".timer")]
    show = ""
    if ids:
        show = _rodar(["systemctl", "show", *ids, "-p", "Id", "-p", "NextElapseUSecRealtime", "-p", "LastTriggerUSec", "-p", "Triggers", "--timestamp=us", "--no-pager"]) or ""
    return f"### SHOW\n{show}\n### RESULTS\n"


def _rodar(cmd: list[str]) -> str | None:
    try:
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if resultado.returncode != 0 and not resultado.stdout:
        return None
    return resultado.stdout


def _partir(texto: str) -> dict[str, str]:
    atual = ""
    partes: dict[str, list[str]] = {}
    for linha in texto.splitlines():
        if linha.startswith("### "):
            atual = linha[4:].strip()
            partes.setdefault(atual, [])
            continue
        if atual:
            partes[atual].append(linha)
    return {chave: "\n".join(linhas) for chave, linhas in partes.items()}


def _resultados(texto: str) -> dict[str, str]:
    saida = {}
    atual = {}
    blocos = []
    for linha in texto.splitlines() + [""]:
        if not linha.strip():
            if atual.get("Id"):
                blocos.append(atual)
            atual = {}
            continue
        if "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        atual[chave.strip()] = valor.strip()
    for bloco in blocos:
        if bloco.get("Id"):
            saida[bloco["Id"]] = bloco.get("Result", "")
    return saida
