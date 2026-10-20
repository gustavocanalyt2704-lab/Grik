"""Lê a agenda ao vivo (timers e cron) e calcula o próximo horário.

A lista NÃO vem daqui. Este módulo só interpreta o texto que o sistema devolve
e troca o nome técnico pelo nome humano quando o mapa tem essa unidade.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta

from app.tempo import TZ

_LINHA_CRON = re.compile(r"^\s*(@\w+|\S+\s+\S+\s+\S+\s+\S+\s+\S+)\s+(.+)$")
_ATRIBUICAO = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _campo(expressao: str, minimo: int, maximo: int) -> set[int] | None:
    expressao = expressao.strip()
    if expressao == "*":
        return set(range(minimo, maximo + 1))
    saida: set[int] = set()
    for parte in expressao.split(","):
        passo = 1
        if "/" in parte:
            base, passo_txt = parte.split("/", 1)
            passo = int(passo_txt)
        else:
            base = parte
        if base in {"*", ""}:
            inicio, fim = minimo, maximo
        elif "-" in base:
            a, b = base.split("-", 1)
            inicio, fim = int(a), int(b)
        else:
            inicio = fim = int(base)
        if passo < 1:
            return None
        for valor in range(inicio, fim + 1, passo):
            if minimo <= valor <= maximo:
                saida.add(valor)
    return saida


def proxima_cron(expressao: str, agora: datetime, limite_minutos: int = 8 * 24 * 60) -> datetime | None:
    """Próxima execução de um cron de 5 campos, no fuso da operação."""
    local = agora.astimezone(TZ).replace(second=0, microsecond=0) + timedelta(minutes=1)
    apelidos = {
        "@hourly": "0 * * * *",
        "@daily": "0 0 * * *",
        "@midnight": "0 0 * * *",
        "@weekly": "0 0 * * 0",
        "@monthly": "0 0 1 * *",
        "@yearly": "0 0 1 1 *",
        "@annually": "0 0 1 1 *",
    }
    bruto = expressao.strip()
    if bruto.startswith("@"):
        if bruto == "@reboot":
            return None
        bruto = apelidos.get(bruto.split()[0], "")
    partes = bruto.split()
    if len(partes) < 5:
        return None
    try:
        minutos = _campo(partes[0], 0, 59)
        horas = _campo(partes[1], 0, 23)
        dias = _campo(partes[2], 1, 31)
        meses = _campo(partes[3], 1, 12)
        semanas = _campo(partes[4], 0, 7)
    except ValueError:
        return None
    if not all((minutos, horas, dias, meses, semanas)):
        return None
    semanas = {0 if d == 7 else d for d in semanas}
    dia_livre = partes[2] == "*"
    semana_livre = partes[4] == "*"
    cursor = local
    for _ in range(limite_minutos):
        if cursor.month not in meses or cursor.hour not in horas or cursor.minute not in minutos:
            cursor += timedelta(minutes=1)
            continue
        dow = (cursor.weekday() + 1) % 7  # cron: 0 = domingo
        casa_dia = cursor.day in dias
        casa_semana = dow in semanas
        if dia_livre and semana_livre:
            ok = True
        elif dia_livre:
            ok = casa_semana
        elif semana_livre:
            ok = casa_dia
        else:
            ok = casa_dia or casa_semana
        if ok:
            return cursor
        cursor += timedelta(minutes=1)
    return None


def _nome_humano(tecnico: str, comando: str, mapa: dict) -> tuple[str, bool]:
    unidades = mapa.get("unidades") or {}
    if tecnico in unidades:
        return unidades[tecnico], False
    for regra in mapa.get("cron") or []:
        trecho = str(regra.get("contem") or "").casefold()
        if trecho and trecho in comando.casefold():
            return str(regra["nome"]), False
    return tecnico, True


def _resultado(valor: str | None) -> str:
    bruto = (valor or "").strip().casefold()
    if bruto in {"success", "sucesso"}:
        return "ok"
    if bruto in {"", "n/a", "none", "desconhecido"}:
        return "sem_confirmacao"
    if bruto in {"failed", "failure", "exit-code", "signal", "timeout", "resources", "core-dump", "watchdog"}:
        return "falhou"
    return "sem_confirmacao"


def parse_timers(show_texto: str, resultados: dict[str, str], mapa: dict, agora: datetime) -> list[dict]:
    blocos = []
    atual = {}
    for linha in show_texto.splitlines():
        if not linha.strip():
            if atual.get("Id"):
                blocos.append(atual)
            atual = {}
            continue
        if "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        atual[chave.strip()] = valor.strip()
    if atual.get("Id"):
        blocos.append(atual)

    rotinas = []
    for bloco in blocos:
        unidade = bloco.get("Id") or ""
        if not unidade.endswith(".timer"):
            continue
        servico = (bloco.get("Triggers") or "").split()[0] if bloco.get("Triggers") else ""
        proxima = _usec(bloco.get("NextElapseUSecRealtime"))
        ultima = _usec(bloco.get("LastTriggerUSec"))
        nome, sem = _nome_humano(unidade, unidade, mapa)
        resultado = _resultado(resultados.get(servico) or resultados.get(unidade))
        rotinas.append(_item(nome, unidade, sem, proxima, ultima, resultado, "timer", agora))
    return rotinas


def parse_crontab(texto: str, usuario: str, mapa: dict, agora: datetime) -> list[dict]:
    rotinas = []
    for linha in texto.splitlines():
        bruto = linha.strip()
        if not bruto or bruto.startswith("#") or _ATRIBUICAO.match(bruto):
            continue
        casou = _LINHA_CRON.match(bruto)
        if not casou:
            continue
        agenda, comando = casou.group(1), casou.group(2).strip()
        if agenda.startswith("@"):
            expressao = agenda.split()[0]
            comando = bruto[len(agenda) :].strip() if " " in agenda else comando
            # @daily comando  — o grupo 2 já é o comando quando o regex pega @daily
            if agenda.startswith("@") and " " not in agenda:
                pass
            else:
                expressao = agenda
        else:
            expressao = agenda
        proxima = proxima_cron(expressao if not expressao.startswith("@") else expressao, agora)
        if expressao.startswith("@") and " " not in expressao:
            proxima = proxima_cron(expressao, agora)
        tecnico = f"cron {usuario}: {_curto(comando)}"
        nome, sem = _nome_humano(tecnico, comando, mapa)
        ident = hashlib.sha1(f"{usuario}:{bruto}".encode()).hexdigest()[:10]
        rotinas.append(
            _item(nome, tecnico, sem, proxima, None, "sem_confirmacao", "cron", agora, extra=ident)
        )
    return rotinas


def ordenar(rotinas: list[dict], agora: datetime) -> list[dict]:
    def chave(item):
        proxima = item.get("proxima_em")
        return (0 if proxima else 1, proxima or 10**18)

    saida = sorted(rotinas, key=chave)
    for item in saida:
        proxima = item.get("proxima_em")
        if proxima is None:
            item["perto"] = False
            continue
        falta = (datetime.fromtimestamp(proxima, TZ) - agora.astimezone(TZ)).total_seconds()
        item["perto"] = 0 <= falta <= 600
    return saida


def _item(nome, tecnico, sem, proxima, ultima, resultado, origem, agora, extra=""):
    def epoch(momento):
        if momento is None:
            return None
        if isinstance(momento, datetime):
            return int(momento.timestamp())
        return int(momento)

    ident = extra or tecnico
    return {
        "id": f"{origem}:{ident}",
        "nome": nome,
        "tecnico": tecnico,
        "sem_descricao": sem,
        "proxima_em": epoch(proxima),
        "ultima_em": epoch(ultima),
        "resultado": resultado,
        "origem": origem,
    }


def _usec(valor: str | None) -> datetime | None:
    if not valor or valor in {"0", "n/a", "none"}:
        return None
    texto = valor.strip()
    if texto.isdigit():
        numero = int(texto)
        if numero > 10**14:  # microssegundos
            numero = numero / 1_000_000
        elif numero > 10**11:  # milissegundos
            numero = numero / 1_000
        if numero <= 0:
            return None
        return datetime.fromtimestamp(numero, TZ)
    for fmt in ("%a %Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S %z"):
        try:
            return datetime.strptime(texto, fmt).astimezone(TZ)
        except ValueError:
            continue
    try:
        momento = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return None
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=TZ)
    return momento.astimezone(TZ)


def _curto(comando: str) -> str:
    comando = comando.strip()
    if len(comando) > 80:
        comando = comando[:77] + "…"
    return comando
