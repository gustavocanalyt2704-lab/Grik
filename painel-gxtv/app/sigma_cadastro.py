"""Lê a lista de clientes do Sigma que o coletor já gravou. Não chama o Sigma."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

from app.ler import _quando, ler_sigma_cru
from app.tempo import TZ, agora, inicio_do_dia

_MAXPLAYER = "maxplayer"


def ler_melhor(cfg, momento: datetime | None = None):
    """A lista mais útil que der para abrir, nesta ordem:

    lista completa do coletor, cadastro antigo, lista incompleta, cache por usuário.
    """
    momento = (momento or agora()).astimezone(TZ)
    vistos: set[str] = set()
    ordem = []

    def add(caminho: Path, incompleto: bool):
        try:
            chave = str(caminho.resolve()) if caminho.exists() else str(caminho)
        except OSError:
            chave = str(caminho)
        if chave in vistos:
            return
        vistos.add(chave)
        ordem.append((caminho, incompleto))

    add(cfg.sigma_rows, False)
    for extra in (
        cfg.sigma_cache,
        Path("/opt/mnrobo/atendimento/ai/private/sigma_cache.json"),
        Path("/workspace/atendimento/ai/private/sigma_cache.json"),
    ):
        add(extra, False)
    add(cfg.sigma_parcial, True)
    add(cfg.sigma_users, False)

    chave = (_assinatura([caminho for caminho, _ in ordem]), inicio_do_dia(momento))
    guardado = _MEMO.get("ultimo")
    if guardado and guardado[0] == chave:
        clientes, quando, base, incompleto = guardado[1]
        extra = dict(base)
        # Reavalia no dia: a lista pode ficar stale enquanto o memo ainda vale.
        extra["desatualizado"] = cadastro_desatualizado(extra, momento, quando)
        extra["frase"] = _frase(
            quando, momento, incompleto, desatualizado=extra["desatualizado"]
        )
        return clientes, quando, None, extra
    _MEMO.clear()

    motivo = _motivo_vazio(cfg)
    for caminho, incompleto in ordem:
        cru, quando, erro = ler_sigma_cru(caminho)
        if not cru:
            if erro and cru is None:
                motivo = erro
            continue
        extra = contar_hoje(cru, momento)
        extra["exato"] = True
        extra["incompleto"] = incompleto
        extra["desatualizado"] = cadastro_desatualizado(extra, momento, quando)
        from app.ler import _normalizar_cliente

        clientes = [_normalizar_cliente(item) for item in cru]
        del cru
        _MEMO["ultimo"] = (chave, (clientes, quando, dict(extra), incompleto))
        extra["frase"] = _frase(quando, momento, incompleto, desatualizado=extra["desatualizado"])
        return clientes, quando, None, extra
    return None, None, motivo, {}


# Último cadastro lido. A rodada pede de 120 em 120 s; o coletor só regrava o arquivo a cada 5 min.
_MEMO: dict = {}


def _assinatura(caminhos: list[Path]) -> tuple:
    sig = []
    for caminho in caminhos:
        try:
            st = caminho.stat()
            sig.append((str(caminho), st.st_mtime_ns, st.st_size))
        except OSError:
            sig.append((str(caminho), None, None))
    return tuple(sig)


def contar_hoje(rows: list[dict], momento: datetime) -> dict:
    """Venda nova e teste criado hoje, do mesmo jeito que o coletor separa."""
    inicio = inicio_do_dia(momento)
    fim = momento.astimezone(TZ)
    pagos = []
    testes = 0
    tem_created_hoje = False
    por_tel: dict[str, list] = {}
    for row in rows:
        if _maxplayer(row) or str(row.get("package") or "") == "ATIVAR MAXPLAYER":
            continue
        criado = _quando(row.get("created_at"))
        if criado and inicio <= criado <= fim:
            tem_created_hoje = True
        tel = _tel8(row)
        if tel:
            por_tel.setdefault(tel, []).append((criado, row))
        if _trial(row):
            if criado and inicio <= criado <= fim:
                testes += 1
            continue
        pagos.append((criado, row))

    vendas = 0
    for criado, row in pagos:
        if not criado or not (inicio <= criado <= fim):
            continue
        tel = _tel8(row)
        irmaos = [(c, r) for c, r in por_tel.get(tel, []) if tel and c and r is not row]
        antes = [r for c, r in irmaos if c < inicio]
        teste_antes = [r for c, r in irmaos if c and c <= criado and _trial(r)]
        if antes or _migrada(row) or teste_antes:
            continue
        vendas += 1
    return {
        "vendas_novas": vendas,
        "testes_criados": testes,
        "tem_created_hoje": tem_created_hoje,
    }


def cadastro_desatualizado(extra: dict, momento: datetime, quando: datetime | None = None) -> bool:
    """True quando a lista existe mas não tem created_at de hoje (coletor atrasado/congelado).

    Depois da 1h Bahia, 0 created_at no dia não é 'dia quieto' — é espelho velho.
    O coletor congela sigma_rows.ok.jsonl por até 6h (OK_MAX_S); nesse intervalo o painel
    não deve publicar vendas_novas/testes_criados=0 como verdade absoluta.
    """
    if not extra.get("exato"):
        return False
    if extra.get("tem_created_hoje"):
        return False
    local = momento.astimezone(TZ)
    if local.hour < 1:
        return False
    if quando is not None:
        idade = local - quando.astimezone(TZ)
        if idade < timedelta(minutes=20) and local.hour < 8:
            # lista acabou de fechar de madrugada; ainda pode ser cedo demais
            return False
    return True


def _motivo_vazio(cfg) -> str:
    caminho = cfg.contador_dir / "cache" / "sigma_disjuntor"
    try:
        if caminho.is_file():
            ate = float((caminho.read_text(encoding="utf-8") or "0").strip() or 0)
            if ate > datetime.now().timestamp():
                return "sem dado — o Sigma pediu uma pausa e a lista ainda não voltou"
    except (OSError, ValueError):
        pass
    return "sem dado — ainda carregando do painel Sigma"


def _frase(
    quando: datetime | None,
    momento: datetime,
    incompleto: bool,
    desatualizado: bool = False,
) -> str:
    if incompleto:
        return "Lista incompleta: o número pode subir quando o cadastro terminar de atualizar."
    if desatualizado:
        if quando is not None:
            hora = quando.astimezone(TZ).strftime("%H:%M")
            return (
                f"Cadastro Sigma desatualizado (lista de {hora}): "
                "ainda sem created_at de hoje — vendas novas e testes do Sigma não são confiáveis."
            )
        return (
            "Cadastro Sigma desatualizado: ainda sem created_at de hoje — "
            "vendas novas e testes do Sigma não são confiáveis."
        )
    if quando is not None and momento - quando.astimezone(TZ) > timedelta(hours=36):
        return f"Cadastro de {quando.astimezone(TZ).strftime('%d/%m')}. O número pode estar desatualizado."
    return "Li o cadastro direto, porque o resumo do dia ainda não marcou essa lista como pronta."


def _trial(row: dict) -> bool:
    valor = row.get("is_trial")
    if isinstance(valor, bool):
        return valor
    return str(valor or "").strip().casefold() in {"yes", "true", "1", "sim"}


def _tel8(row: dict) -> str:
    digitos = re.sub(r"\D", "", str(row.get("whatsapp") or ""))
    return digitos[-8:] if len(digitos) >= 8 else ""


def _maxplayer(row: dict) -> bool:
    texto = (str(row.get("server") or "") + str(row.get("package") or "")).casefold()
    return _MAXPLAYER in texto


def _migrada(row: dict) -> bool:
    if str(row.get("is_migrated") or "").upper() == "YES":
        return True
    nota = str(row.get("note") or "").casefold()
    return "antig" in nota or "migra" in nota
