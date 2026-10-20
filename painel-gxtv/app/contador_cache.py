"""Lê o cache do /contagem do Telegram sem inventar campo ausente."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from app.logonce import avisar
from app.tempo import TZ

_log = logging.getLogger("painel")

_CHAVES = {
    "dinheiro": ("dinheiro", "total_dia", "mp_hoje", "receita"),
    "testes": ("testes", "testes_2h", "teste"),
    "leads": ("leads", "leads_3619", "leads3619"),
    "funil": ("funil",),
    "feedback": ("feedback",),
    "vencimentos": ("vencimentos", "venc"),
    "avisos": ("avisos", "avisos_enviados"),
    "erros": ("erros", "erros_robo", "erros_do_robo"),
    "meta": ("meta", "meta_dia"),
}


def ler_diretorio(caminho: Path) -> dict | None:
    """Lê só os arquivos deste diretório. Não entra em subpastas."""
    try:
        if not caminho.is_dir():
            return None
        entradas = list(caminho.iterdir())
    except OSError as exc:
        avisar(f"acesso:{caminho}", "sem acesso a %s: %s", caminho, exc)
        return None
    melhor = None
    melhor_nota = 0
    melhor_mtime = -1.0
    for arquivo in entradas:
        try:
            if not arquivo.is_file():
                continue
            if arquivo.stat().st_size > 2_000_000:
                continue
            if arquivo.suffix.lower() not in {".json", ".txt", ""}:
                continue
            if "mp_api" in arquivo.name or "sigma" in arquivo.name:
                continue
            texto = arquivo.read_text(encoding="utf-8", errors="replace")
            mtime = arquivo.stat().st_mtime
        except OSError as exc:
            avisar(f"acesso:{arquivo}", "sem acesso a %s: %s", arquivo, exc)
            continue
        extraido = _extrair(texto)
        if not extraido:
            continue
        nota = len(extraido)
        if nota > melhor_nota or (nota == melhor_nota and mtime > melhor_mtime):
            melhor = extraido
            melhor_nota = nota
            melhor_mtime = mtime
    return melhor


def _extrair(texto: str) -> dict:
    texto = texto.strip()
    if not texto:
        return {}
    if texto[0] in "[{":
        try:
            return _de_json(json.loads(texto))
        except json.JSONDecodeError:
            pass
    return _de_texto(texto)


def _de_json(dado) -> dict:
    if isinstance(dado, list) and dado and isinstance(dado[0], dict):
        # jsonl curto de resumo: fica com o último objeto
        dado = dado[-1]
    if not isinstance(dado, dict):
        return {}
    plano = {}
    _achatar(dado, plano)
    saida = {}
    for destino, chaves in _CHAVES.items():
        for chave in chaves:
            if chave in plano:
                saida[destino] = plano[chave]
                break
    return saida


def _achatar(dado: dict, plano: dict, prefixo: str = ""):
    for chave, valor in dado.items():
        nome = str(chave).casefold()
        if isinstance(valor, dict) and nome in {"funil", "feedback", "vencimentos", "venc"}:
            plano[nome] = valor
            continue
        if isinstance(valor, dict):
            _achatar(valor, plano, nome)
            continue
        plano[nome] = valor


def _de_texto(texto: str) -> dict:
    import re

    saida = {}
    regras = (
        ("dinheiro", r"dinheiro[^\d\n]{0,24}R\$\s*([\d.]+(?:,\d{2})?)"),
        ("testes", r"testes?\s*[:\-]\s*(\d+)"),
        ("leads", r"leads?(?:\s*3619)?\s*[:\-]\s*(\d+)"),
        ("avisos", r"avisos?\s*(?:enviados?)?\s*[:\-]\s*(\d+)"),
        ("erros", r"erros?\s*(?:do\s*rob[oô])?\s*[:\-]\s*(\d+)"),
    )
    for destino, regra in regras:
        achou = re.search(regra, texto, re.I)
        if achou:
            saida[destino] = achou.group(1)
    return saida


def resumo_contagem(diretorio: Path, momento: datetime) -> dict | None:
    """Dinheiro e renovações do JSON do dia, já filtrados pelo coletor do /contagem.

    Abre só AAAA-MM-DD.json e o arquivo do dia anterior. Não lista a pasta.
    """
    try:
        dia = momento.astimezone(TZ).date()
    except (AttributeError, TypeError, ValueError, OSError):
        return None
    hoje = _ler_json_objeto(diretorio / f"{dia.isoformat()}.json")
    if hoje is None:
        return None
    bloco = hoje.get("bloco")
    if not isinstance(bloco, dict):
        avisar("cache-sem-bloco", "cache do dia sem bloco: %s", dia.isoformat())
        return None
    mp_reais = numero(bloco.get("mp_reais"))
    if mp_reais is None:
        avisar("cache-sem-mp", "cache do dia sem mp_reais: %s", dia.isoformat())
        return None
    ontem = _ler_json_objeto(diretorio / f"{(dia - timedelta(days=1)).isoformat()}.json")
    return {
        "mp_reais": round(float(mp_reais), 2),
        "mp_n": _como_int(numero(bloco.get("mp_n"))),
        "mp_fora_n": _como_int(numero(bloco.get("mp_fora_n"))),
        "mp_fora_reais": _arredondar(numero(bloco.get("mp_fora_reais"))),
        "mp_sem_n": _como_int(numero(bloco.get("mp_sem_n"))),
        "mp_sem_reais": _arredondar(numero(bloco.get("mp_sem_reais"))),
        "renovado_n": _como_int(numero(bloco.get("renovado_n"))),
        "renovado_reais": _arredondar(numero(bloco.get("renovado_reais"))),
        "aviso": _aviso_idade(hoje.get("gerado_em"), momento),
        "ontem_reais": _ontem_reais(hoje.get("ontem_corte"), ontem),
    }


def _ler_json_objeto(caminho: Path) -> dict | None:
    try:
        if not caminho.is_file():
            return None
        dado = json.loads(caminho.read_text(encoding="utf-8", errors="replace"))
    except OSError as exc:
        avisar(f"acesso:{caminho}", "sem acesso a %s: %s", caminho, exc)
        return None
    except json.JSONDecodeError:
        avisar(f"ilegivel:{caminho}", "cache ilegível: %s", caminho, intervalo=600)
        return None
    if not isinstance(dado, dict):
        return None
    return dado


def _aviso_idade(gerado, momento: datetime) -> str | None:
    instante = _instante(gerado)
    if instante is None:
        return None
    try:
        local = momento.astimezone(TZ)
    except (AttributeError, TypeError, ValueError):
        return None
    segundos = (local - instante).total_seconds()
    if segundos <= 10 * 60:
        return None
    return f"atualizado há {int(segundos // 60)} min"


def _ontem_reais(corte, ontem_doc: dict | None) -> float | None:
    """Ontem neste horário: o corte de hoje e, quando o corte é um horário, o arquivo de ontem."""
    direto = _mp_de_corte(corte)
    if direto is not None:
        return direto
    if not isinstance(ontem_doc, dict):
        return None
    bloco = ontem_doc.get("bloco")
    if not isinstance(bloco, dict):
        return None
    valor = _arredondar(numero(bloco.get("mp_reais")))
    if valor is None:
        return None
    instante = _instante_corte(corte)
    if instante is not None:
        referencia = _instante(ontem_doc.get("ate")) or _instante(ontem_doc.get("gerado_em"))
        if referencia is not None and abs((referencia - instante).total_seconds()) <= 90:
            return valor
        return None
    if ontem_doc.get("fechado") is False:
        return valor
    return None


def _mp_de_corte(corte) -> float | None:
    if corte is None or isinstance(corte, bool):
        return None
    if isinstance(corte, (int, float)):
        return round(float(corte), 2)
    if isinstance(corte, str):
        if _instante(corte) is not None:
            return None
        return _arredondar(numero(corte))
    if isinstance(corte, dict):
        bloco = corte.get("bloco") if isinstance(corte.get("bloco"), dict) else corte
        return _arredondar(numero(bloco.get("mp_reais")))
    return None


def _instante_corte(corte) -> datetime | None:
    if isinstance(corte, dict):
        return _instante(corte.get("ate") or corte.get("gerado_em"))
    return _instante(corte)


def _instante(valor) -> datetime | None:
    if valor is None or isinstance(valor, (bool, int, float)):
        return None
    texto = str(valor).strip().replace("Z", "+00:00")
    if not texto:
        return None
    try:
        momento = datetime.fromisoformat(texto)
    except ValueError:
        return None
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=TZ)
    return momento.astimezone(TZ)


def _arredondar(valor) -> float | None:
    if valor is None:
        return None
    return round(float(valor), 2)


def _como_int(valor) -> int | None:
    if valor is None:
        return None
    return int(round(float(valor)))


def numero(valor):
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return valor
    texto = str(valor).strip().replace("R$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# v5: o bloco inteiro do /contagem (todas as métricas do contador), sem telefone.

_CAMPOS_HOJE = (
    "mp_ok", "mp_n", "mp_reais", "mp_fora_n", "mp_fora_reais", "mp_sem_n", "mp_sem_reais",
    "renovado_n", "renovado_reais", "ledger_ok", "acoes_ok", "postgres_ok", "sigma_ok",
    "venda_nova", "vendas_novas", "vendas_paineis", "testes_criados", "testes_convertidos",
    "vence_hoje", "vence_amanha", "renov_painel_reais", "fiscal", "audio_n", "live_ok",
    "live_xl5z", "live_ini", "live_fim", "live_parcial", "venda_preco", "atendimento",
    "trava_conv_n", "trava_ev", "ia_resolvido", "resolvidos_painel", "esperando", "webhook",
    "funil_n", "funil_ev", "feedback_n", "fb_resp", "fb_ok", "fb_neg", "erro_real", "msgs_env",
    "erro_pct", "top_erro", "barrados", "dados_de",
)
_CAMPOS_ONTEM = (
    "renovado_n", "renovado_reais", "audio_n", "trava_conv_n", "feedback_n", "atendimento",
    "acoes_ok", "ledger_ok", "mp_ok", "mp_reais", "mp_n", "fim",
)


def _tel8(valor) -> str:
    import re

    digitos = re.sub(r"\D", "", str(valor or ""))
    return digitos[-8:] if len(digitos) >= 8 else ""


def ler_contagem(diretorio: Path, momento: datetime) -> dict | None:
    """Todas as métricas do JSON do dia do /contagem, mais o corte de ontem e os 7 dias."""
    try:
        dia = momento.astimezone(TZ).date()
    except (AttributeError, TypeError, ValueError):
        return None
    doc = _ler_json_objeto(diretorio / f"{dia.isoformat()}.json")
    if doc is None or not isinstance(doc.get("bloco"), dict):
        return None
    bloco = doc["bloco"]
    hoje = {chave: bloco.get(chave) for chave in _CAMPOS_HOJE}
    corte = doc.get("ontem_corte") if isinstance(doc.get("ontem_corte"), dict) else None
    ontem = {chave: corte.get(chave) for chave in _CAMPOS_ONTEM} if corte else None
    tels = set()
    renovs = bloco.get("renovs") if isinstance(bloco.get("renovs"), dict) else {}
    for rec in renovs.values():
        if isinstance(rec, dict) and _tel8(rec.get("telefone")):
            tels.add(_tel8(rec.get("telefone")))
    semana = []
    for atras in range(6, -1, -1):
        d = dia - timedelta(days=atras)
        outro = doc if atras == 0 else _ler_json_objeto(diretorio / f"{d.isoformat()}.json")
        b = (outro or {}).get("bloco") if isinstance((outro or {}).get("bloco"), dict) else None
        if not b:
            semana.append({"dia": d.isoformat(), "renovado_ok": False, "mp_ok": False})
            continue
        semana.append({
            "dia": d.isoformat(),
            "renovado_ok": bool(b.get("ledger_ok") or b.get("acoes_ok")),
            "renovado_n": b.get("renovado_n"),
            "renovado_reais": b.get("renovado_reais"),
            "mp_ok": bool(b.get("mp_ok")),
            "mp_n": b.get("mp_n"),
            "mp_reais": b.get("mp_reais"),
            "erro_pct": b.get("erro_pct"),
            "erro_real": b.get("erro_real"),
            "msgs_env": b.get("msgs_env"),
            "trava_conv_n": b.get("trava_conv_n"),
            "audio_n": b.get("audio_n"),
        })
    return {
        "gerado_em": doc.get("gerado_em"),
        "aviso": _aviso_idade(doc.get("gerado_em"), momento),
        "hoje": hoje,
        "ontem": ontem,
        "semana": semana,
        "_tel8_renovados": tels,
    }
