"""Leitura de arquivos que já existem na VPS. Nunca escreve neles."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from app.assuntos import aparelho_de, app_de
from app.logonce import avisar
from app.tempo import TZ, agora, inicio_do_dia

_ATIVOS = {"active", "ativo", "ativa", "enabled", "ok"}
_log = logging.getLogger("painel")


def ler_env(caminho: Path, nome: str) -> str | None:
    try:
        if not caminho.is_file():
            return None
        texto = caminho.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        avisar(f"acesso:{caminho}", "sem acesso a %s: %s", caminho, exc)
        return None
    prefixo = f"{nome}="
    for linha in texto.splitlines():
        bruto = linha.strip()
        if bruto.startswith("export "):
            bruto = bruto[len("export ") :].strip()
        if not bruto.startswith(prefixo):
            continue
        valor = bruto[len(prefixo) :].strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "'\"":
            valor = valor[1:-1]
        return valor or None
    return None


def ler_jsonl(caminho: Path, max_bytes: int = 30_000_000) -> list[dict] | None:
    try:
        if not caminho.is_file():
            return None
        tamanho = caminho.stat().st_size
        with caminho.open("rb") as arquivo:
            if tamanho > max_bytes:
                arquivo.seek(tamanho - max_bytes)
                arquivo.readline()
            bruto = arquivo.read().decode("utf-8", errors="replace")
    except OSError as exc:
        avisar(f"acesso:{caminho}", "sem acesso a %s: %s", caminho, exc)
        return None
    saida = []
    for linha in bruto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            item = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            saida.append(item)
    return saida


def ler_pagamentos(_principal: Path, reserva: Path) -> tuple[list[dict] | None, str | None]:
    """Lista ao vivo: só o cache mp_api.jsonl. Linha com a chave proprio fica de fora.

    O total do dia não sai desta lista. Ele vem do JSON diário do /contagem.
    """
    itens = ler_jsonl(reserva)
    if itens is None:
        return None, "sem dado — o resumo do Mercado Pago ainda não gravou os pagamentos"
    return [item for item in itens if "proprio" not in item], None


def ler_lancamentos(ledger: Path, acoes: list[dict] | None) -> list[dict] | None:
    linhas = ler_jsonl(ledger, max_bytes=20_000_000)
    eventos = []
    if linhas:
        eventos.extend(linhas)
    if acoes:
        for evento in acoes:
            tipo = str(evento.get("tipo") or evento.get("evento") or evento.get("acao") or "").casefold()
            if "renov" in tipo or "pix" in tipo or "venda_nova" in evento:
                eventos.append(evento)
    if linhas is None and not acoes:
        return None
    return eventos


class Cauda:
    """Lê só o que chegou desde a última vez. Na primeira abertura, pega um trecho do fim."""

    def __init__(self, caminho: Path, primeira_janela: int = 8_000_000):
        self.caminho = caminho
        self.primeira_janela = primeira_janela
        self.offset = None
        self.inode = None

    def novas_linhas(self) -> list[str] | None:
        try:
            if not self.caminho.is_file():
                self.offset = None
                return None
            stat = self.caminho.stat()
        except OSError as exc:
            avisar(f"acesso:{self.caminho}", "sem acesso a %s: %s", self.caminho, exc)
            return None
        inode = (stat.st_dev, stat.st_ino)
        try:
            arquivo_bin = self.caminho.open("rb")
        except OSError as exc:
            avisar(f"acesso:{self.caminho}", "sem acesso a %s: %s", self.caminho, exc)
            return None
        with arquivo_bin:
            if self.offset is None or inode != self.inode or stat.st_size < (self.offset or 0):
                inicio = max(0, stat.st_size - self.primeira_janela)
                arquivo_bin.seek(inicio)
                if inicio:
                    arquivo_bin.readline()
                self.inode = inode
            else:
                arquivo_bin.seek(self.offset)
            bruto = arquivo_bin.read()
            self.offset = arquivo_bin.tell()
            self.inode = inode
        texto = bruto.decode("utf-8", errors="replace")
        return [linha for linha in texto.splitlines() if linha.strip()]


def eventos_de_acoes(linhas: list[str] | None, agora_em: datetime | None = None) -> list[dict]:
    if not linhas:
        return []
    momento = agora_em or agora()
    limite = inicio_do_dia(momento, 1)
    saida = []
    for linha in linhas:
        try:
            item = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        quando = _quando(item.get("ts") or item.get("data") or item.get("em"))
        if quando is not None and quando < limite:
            continue
        tipo = str(item.get("tipo") or item.get("evento") or item.get("acao") or "")
        saida.append({
            "tipo": tipo,
            "ts": quando.isoformat() if quando else item.get("ts"),
            "telefone": item.get("telefone"),
            "valor": item.get("valor"),
            "venda_nova": item.get("venda_nova"),
            "status": item.get("status") or item.get("resultado"),
            "payment_id": item.get("payment_id") or item.get("id_pagamento"),
            "e2e": item.get("e2e"),
            "motivo": item.get("motivo"),
            "painel": item.get("painel"),
        })
    return saida


def resumir_sigma(caminho: Path) -> tuple[list[dict] | None, datetime | None, str | None]:
    cru, quando, motivo = ler_sigma_cru(caminho)
    if cru is None:
        return None, quando, motivo
    return [_normalizar_cliente(item) for item in cru if isinstance(item, dict)], quando, None


# Só o que contar_hoje e _normalizar_cliente leem. A linha inteira do Sigma não cabe no MemoryMax do painel.
CAMPOS_SIGMA = (
    "status", "estado", "expires_at_tz", "expires_at", "vencimento", "server", "painel", "server_id",
    "package", "pacote", "app", "note", "nota", "observacao", "is_trial", "created_at", "whatsapp", "is_migrated",
)


def _enxugar(item: dict) -> dict:
    return {chave: item[chave] for chave in CAMPOS_SIGMA if chave in item}


def _jsonl_em_fluxo(caminho: Path) -> list[dict] | None:
    """JSONL com dois valores ou mais, linha a linha e já enxuto.

    None quando o arquivo é um JSON só: aí vale o caminho antigo (json.loads do texto todo).
    """
    saida: list[dict] = []
    valores = 0
    with caminho.open("rb") as arquivo:
        for bruta in arquivo:
            linha = bruta.strip()
            if not linha:
                continue
            try:
                item = json.loads(linha.decode("utf-8", errors="replace"))
            except ValueError:
                if valores == 0:
                    return None
                continue
            valores += 1
            if isinstance(item, list):
                saida.extend(_enxugar(x) for x in item if isinstance(x, dict))
            elif isinstance(item, dict):
                saida.append(_enxugar(item))
    if valores < 2:
        return None
    return saida


def ler_sigma_cru(caminho: Path) -> tuple[list[dict] | None, datetime | None, str | None]:
    """Linhas do cadastro, só com CAMPOS_SIGMA. Aceita JSON, JSONL e o mapa {usuário: {rows}}."""
    try:
        if not caminho.is_file():
            return None, None, "sem dado — ainda carregando do painel Sigma"
        stat = caminho.stat()
        clientes = _jsonl_em_fluxo(caminho)
        texto = caminho.read_text(encoding="utf-8", errors="replace") if clientes is None else None
    except OSError as exc:
        avisar(f"acesso:{caminho}", "sem acesso a %s: %s", caminho, exc)
        return None, None, "sem dados — não consegui ler o cadastro"
    if clientes is None:
        bruto = interpretar_sigma(texto)
        if bruto is None:
            return None, None, "sem dado — o cadastro do painel Sigma está ilegível"
        clientes = [_enxugar(item) for item in _lista_sigma(bruto) if isinstance(item, dict)]
    return clientes, datetime.fromtimestamp(stat.st_mtime, TZ), None


def interpretar_sigma(texto: str):
    bruto = (texto or "").strip()
    if not bruto:
        return []
    try:
        return json.loads(bruto)
    except json.JSONDecodeError:
        pass
    linhas = []
    alguma = False
    for linha in bruto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            item = json.loads(linha)
        except json.JSONDecodeError:
            continue
        alguma = True
        if isinstance(item, list):
            linhas.extend(item)
        elif isinstance(item, dict):
            linhas.append(item)
    if not alguma:
        return None
    return linhas


def _lista_sigma(bruto) -> list:
    if isinstance(bruto, list):
        return bruto
    if isinstance(bruto, dict):
        for chave in ("rows", "customers", "clientes", "data", "items", "usuarios"):
            if isinstance(bruto.get(chave), list):
                return bruto[chave]
        achatados = []
        parece_users = False
        for valor in bruto.values():
            if isinstance(valor, dict) and isinstance(valor.get("rows"), list):
                parece_users = True
                achatados.extend(item for item in valor["rows"] if isinstance(item, dict))
        if parece_users:
            return achatados
        if bruto.get("status") or bruto.get("expires_at") or bruto.get("expires_at_tz") or bruto.get("username"):
            return [bruto]
        valores = [v for v in bruto.values() if isinstance(v, dict)]
        if valores and any(v.get("status") or v.get("expires_at_tz") or v.get("username") for v in valores[:5]):
            return valores
    return []


def _normalizar_cliente(item: dict) -> dict:
    status = item.get("status") or item.get("estado") or ""
    vence = _data(item.get("expires_at_tz") or item.get("expires_at") or item.get("vencimento"))
    painel = _painel(item.get("server") or item.get("painel"), item.get("server_id"))
    texto = " ".join(str(item.get(chave) or "") for chave in ("package", "pacote", "app", "note", "nota", "observacao"))
    trial = item.get("is_trial")
    if isinstance(trial, str):
        trial = trial.strip().casefold() in {"1", "true", "sim", "yes"}
    return {
        "status": str(status).strip().casefold(),
        "vence": vence,
        "painel": painel,
        "app": app_de(texto),
        "aparelho": aparelho_de(texto),
        "trial": bool(trial),
        "oculto": __import__("app.ocultos", fromlist=["x"]).painel_oculto(  # OCULTAR_JORGE_1110
            painel, item.get("server"), item.get("server_id"), item.get("reseller"), item.get("reseller_id"),
            item.get("owner"), item.get("owner_id"), item.get("user_id"), item.get("revenda")),
    }


def _painel(server, server_id) -> str | None:
    bruto = str(server or server_id or "").strip()
    if not bruto:
        return None
    achou = re.search(r"\bp\s*([0-9]{1,2})\b", bruto, re.I) or re.search(r"painel\s*([0-9]{1,2})", bruto, re.I)
    if achou:
        return f"P{achou.group(1)}"
    if re.fullmatch(r"[0-9a-f]{8,}", bruto, re.I) or len(bruto) > 24:
        return None
    return bruto


def ler_log(linhas: list[str] | None, momento: datetime | None = None) -> dict:
    agora_em = momento or agora()
    vazio = {"fila": None, "em_atendimento": None, "envios_min": None, "calma": None, "banco_lento": None, "fresco": False}
    if not linhas:
        return vazio
    ultima_poll = None
    ultima_calma = None
    lentos = 0
    for linha in linhas:
        quando = _hora_log(linha, agora_em)
        if quando is not None and agora_em - quando > timedelta(minutes=20):
            continue
        poll = re.search(r"\bPOLL\b.*?\bfila=(\d+).*?\bocupadas=(\d+).*?\(([\d.]+)/min\)", linha)
        if poll:
            ultima_poll = poll
        calma = re.search(r"\bDCRATE\b.*?429_60s=(\d+)", linha)
        if calma:
            ultima_calma = int(calma.group(1))
        if re.search(r"timeout|timeoutexception|tempo esgotado", linha, re.I):
            lentos += 1
    if ultima_poll is None and ultima_calma is None and lentos == 0:
        return vazio
    return {
        "fila": int(ultima_poll.group(1)) if ultima_poll else None,
        "em_atendimento": int(ultima_poll.group(2)) if ultima_poll else None,
        "envios_min": float(ultima_poll.group(3)) if ultima_poll else None,
        "calma": ultima_calma,
        "banco_lento": lentos,
        "fresco": True,
    }


_BACKUP_PULAR = ("backup_restart", "/backup_", "deploy_contador")


def backup_de(caminho: Path | None) -> tuple[datetime | None, str | None]:
    """Data do último arquivo de backup. Pastas de backup manual/deploy são puladas sem ler."""
    texto = str(caminho or "").strip()
    if not texto or texto == "." or any(p in texto for p in _BACKUP_PULAR):
        if caminho is not None and any(p in texto for p in _BACKUP_PULAR):
            avisar(f"acesso:{caminho}", "sem acesso a %s: pasta de backup ignorada", caminho)
        return None, "sem dados — este servidor não tem backup automático que o painel acompanhe"
    try:
        if not caminho.is_file():
            return None, "sem dado — não achei um backup automático"
        return datetime.fromtimestamp(caminho.stat().st_mtime, TZ), None
    except OSError as exc:
        avisar(f"acesso:{caminho}", "sem acesso a %s: %s", caminho, exc)
        return None, "sem dados — não consegui ler o backup"


def cpu_percent(anterior: tuple[int, int] | None) -> tuple[float | None, tuple[int, int] | None]:
    try:
        linha = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0]
    except OSError:
        return None, anterior
    partes = [int(p) for p in linha.split()[1:]]
    total = sum(partes)
    ocioso = partes[3] + (partes[4] if len(partes) > 4 else 0)
    if not anterior or total <= anterior[0]:
        return None, (total, ocioso)
    dt = total - anterior[0]
    di = ocioso - anterior[1]
    if dt <= 0:
        return None, (total, ocioso)
    return round((1 - di / dt) * 100, 1), (total, ocioso)


def ram_percent() -> float | None:
    try:
        texto = Path("/proc/meminfo").read_text(encoding="utf-8")
    except OSError:
        return None
    dados = {}
    for linha in texto.splitlines():
        if ":" not in linha:
            continue
        chave, _, valor = linha.partition(":")
        dados[chave] = int(valor.strip().split()[0])
    total = dados.get("MemTotal") or 0
    if not total:
        return None
    livre = dados.get("MemAvailable", dados.get("MemFree", 0))
    return round((1 - livre / total) * 100, 1)


def disco_percent(caminho: str = "/") -> float | None:
    try:
        stat = os.statvfs(caminho)
    except OSError:
        return None
    total = stat.f_blocks * stat.f_frsize
    if not total:
        return None
    livre = stat.f_bavail * stat.f_frsize
    return round((1 - livre / total) * 100, 1)


def _quando(valor) -> datetime | None:
    if not valor:
        return None
    texto = str(valor).strip().replace("Z", "+00:00")
    try:
        momento = datetime.fromisoformat(texto)
    except ValueError:
        return None
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=TZ)
    return momento.astimezone(TZ)


def _data(valor):
    momento = _quando(valor)
    if momento is None:
        texto = str(valor or "")[:10]
        try:
            return datetime.strptime(texto, "%Y-%m-%d").date()
        except ValueError:
            return None
    return momento.astimezone(TZ).date()


def _hora_log(linha: str, agora_em: datetime) -> datetime | None:
    achou = re.match(r"(\d{2}):(\d{2}):(\d{2})", linha.strip())
    if not achou:
        return None
    hora, minuto, segundo = (int(achou.group(i)) for i in (1, 2, 3))
    base = agora_em.astimezone(TZ).replace(hour=hora, minute=minuto, second=segundo, microsecond=0)
    if base - agora_em > timedelta(hours=2):
        base -= timedelta(days=1)
    return base
