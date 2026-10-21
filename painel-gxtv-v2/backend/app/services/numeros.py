"""Números de WhatsApp da tela Início.

A lista não é fixa. Sai da fila do webhook (a mesma conversa que o gráfico
"Por número de WhatsApp" do painel atual agrupa por r.n quando o cliente
escreveu). Nome vazio vira "sem número". Sem a fila, a lista fica vazia e
os campos ficam "sem dado" — nunca um 3619/0837 inventado.
"""

from __future__ import annotations

import json
import os
import re
import statistics
from pathlib import Path
from typing import Any

from app.core.mapa_instancias import rotulo_mapeado
from app.core.timezone import TZ_NAME, agora, iso_bahia, janela_periodo, telefone_final
from app.services.atendimento import (
    _build_conversation_state,
    _classify_stage,
    _response_gaps,
)
from app.sources import credenciais, espelho, gestor

SEM_NUMERO = "sem número"
_PREFIXO_CODIGO = r"(?:vendas|venda|loja|final|whatsapp|zap)"
# Gustavo 06/10 15:18: 3166 = número do irmão, fora da operação / não vai ao DataCrazy.
_OCULTOS_PAINEL = frozenset({"Final 3166", "3166"})
_LIXO_INSTANCIA = {
    "message sent",
    "message received",
    "sent",
    "received",
    "true",
    "false",
}


def _oculto_painel(rotulo: str) -> bool:
    r = str(rotulo or "").strip()
    if r in _OCULTOS_PAINEL:
        return True
    return bool(re.fullmatch(r"(?:Final\s+)?3166", r, re.IGNORECASE))
_CONTADOR_CACHE = Path(
    os.environ.get("PAINEL_CONTADOR_DIR", "/opt/mnrobo/contador_tg")
) / "cache"
_EMOJI = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U0000FE00-\U0000FE0F"
    "\U0000200D"
    "\U000020E3"
    "]+",
    flags=re.UNICODE,
)
_PIX_ENVIO = re.compile(r"pra pagar é só o pix|s[oó] o pix|pix\s*👇", re.IGNORECASE)
_PRECO = re.compile(
    r"quanto\s+(?:que\s+)?(?:custa|[eé]|fica|sai|t[aá]|cobra)|"
    r"qual(?:\s+[eé])?(?:\s+o|\s+a)?\s+(?:valor|pre[cç]o|tabela)|"
    r"(?:quero|queria|vou)\s+assinar|"
    r"tabela\s+(?:de\s+)?pre|"
    r"quais?\s+(?:s[aã]o\s+)?(?:os\s+)?(?:planos|valores|pre[cç]os)",
    re.IGNORECASE,
)
_PRECO_FALSO = re.compile(
    r"valor\s+d[oe]\s+(?:c[oó]digo|code|mac|usu[aá]rio|login|senha)|"
    r"quanto\s+tempo|por\s+quanto\s+tempo",
    re.IGNORECASE,
)
_GRUPOS = (
    ("vendas", "Vendas"),
    ("cobranca", "Cobrança"),
    ("suporte", "Suporte"),
    ("rmkt", "RMKT"),
    ("outros", "Outros"),
)
_NOTA = (
    'Conversas de clientes em cada número, na mesma fila do gráfico '
    '"Por número de WhatsApp". "sem número" = o robô ainda não gravou '
    "qual WhatsApp atendeu."
)


def rotulo_instancia(
    raw: Any,
    *,
    phone: Any = None,
    evento: Any = None,
    instance_id: Any = None,
) -> str:
    """Limpa o nome da instância como o gráfico do painel atual mostra.

    Tira emoji e sobra de espaço. Código de 4 dígitos (3619, vendas-3619,
    loja-3166) vira "Final 3619". Nome vazio vira "sem número".
    Telefone/id/evento do mapa versionado (config/mapa_instancias.json)
    viram o rótulo cadastrado — 5511936235903 e msg_p6cob somam em COBRANÇA P6.
    """
    mapped = rotulo_mapeado(raw, phone=phone, evento=evento, instance_id=instance_id)
    if mapped:
        return mapped
    text = _EMOJI.sub(" ", str(raw or ""))
    text = "".join(ch if (ch.isalnum() or ch.isspace()) else " " for ch in text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return SEM_NUMERO
    baixo = text.casefold()
    if baixo in _LIXO_INSTANCIA:
        return SEM_NUMERO
    if baixo in {
        "sem número",
        "sem numero",
        "número não identificado",
        "numero não identificado",
        "numero nao identificado",
    }:
        return SEM_NUMERO
    m = re.fullmatch(rf"(?:{_PREFIXO_CODIGO}\s+)?(\d{{4}})", text, re.IGNORECASE)
    if m:
        return f"Final {m.group(1)}"
    return text


def grupo_de(rotulo: str) -> str:
    if rotulo == SEM_NUMERO:
        return "outros"
    u = rotulo.upper()
    if "RMKT" in u:
        return "rmkt"
    tem_sup = "SUPORTE" in u
    tem_cob = "COBRAN" in u
    if tem_sup and not tem_cob:
        return "suporte"
    if tem_cob and not tem_sup:
        return "cobranca"
    if tem_sup and tem_cob:
        return "cobranca" if u.find("COBRAN") < u.find("SUPORTE") else "suporte"
    if re.fullmatch(r"Final \d{4}", rotulo):
        return "vendas"
    return "outros"


def _bate_filtro(rotulo: str, pedido: str) -> bool:
    if not pedido:
        return True
    if pedido == rotulo:
        return True
    if rotulo == f"Final {pedido}":
        return True
    return False


def _digitos(raw: Any) -> str:
    return re.sub(r"\D", "", str(raw or ""))


def _campo(rotulo: str, valor: float | int | None = None, detalhe: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"rotulo": rotulo, "valor": valor}
    if detalhe:
        out["detalhe"] = detalhe
    return out


def sem_dado(detalhe: str | None = None) -> dict[str, Any]:
    return _campo("sem dado", None, detalhe)


def _fmt_tempo(seconds: float | None) -> str:
    if seconds is None:
        return "sem dado"
    if seconds < 60:
        return f"{int(round(seconds))}s"
    minutos = int(seconds // 60)
    resto = int(round(seconds % 60))
    return f"{minutos}m{resto:02d}s"


def _brl(valor: Any) -> str | None:
    if valor is None:
        return None
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return None
    texto = f"{n:,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _cliente_escreveu(st: dict[str, Any]) -> bool:
    return any(not msg.get("from_me") for msg in (st.get("msgs") or []))


def _pediu_preco(st: dict[str, Any]) -> bool:
    for msg in st.get("msgs") or []:
        if msg.get("from_me"):
            continue
        texto = str(msg.get("text") or "").strip()
        if not texto or _PRECO_FALSO.search(texto):
            continue
        if _PRECO.search(texto):
            return True
    return False


def rotulos_na_fila(max_lines: int = 40000) -> list[str]:
    """Rótulos vistos na fila, do maior volume de fala do cliente para o menor."""
    if not espelho.WEBHOOK_QUEUE.is_file():
        return []
    counts: dict[str, int] = {}
    for ev in espelho.eventos_recentes(max_lines=max_lines):
        if ev.get("from_me"):
            continue
        lab = rotulo_instancia(
            ev.get("instance"),
            phone=ev.get("instance_phone"),
            evento=ev.get("evento"),
            instance_id=ev.get("instance_id"),
        )
        if _oculto_painel(lab):
            continue
        counts[lab] = counts.get(lab, 0) + 1
    return [k for k, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].casefold()))]


def codigos_visiveis() -> list[str]:
    return rotulos_na_fila()


def _telefone_da_conversa(st: dict[str, Any]) -> str:
    for msg in st.get("msgs") or []:
        if msg.get("phone"):
            return str(msg["phone"])
    return ""


def _indice_conversas(state: dict[str, dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Últimos 8 (e 4, se não colidir) dígitos → rótulo do WhatsApp."""
    por8: dict[str, str] = {}
    por4: dict[str, str] = {}
    colisao4: set[str] = set()
    for st in state.values():
        lab = rotulo_instancia(
            st.get("instance"),
            phone=st.get("instance_phone"),
            evento=st.get("evento"),
            instance_id=st.get("instance_id"),
        )
        if lab == SEM_NUMERO:
            continue
        tel = _digitos(_telefone_da_conversa(st))
        if len(tel) >= 8:
            por8[tel[-8:]] = lab
        if len(tel) >= 4:
            tail = tel[-4:]
            if tail in por4 and por4[tail] != lab:
                colisao4.add(tail)
            else:
                por4[tail] = lab
    for tail in colisao4:
        por4.pop(tail, None)
    return {"8": por8, "4": por4}


def _origem_da_venda(linha: dict[str, Any], indice: dict[str, Any]) -> tuple[str | None, str]:
    bruto = str(linha.get("instancia") or "").strip()
    inst = rotulo_instancia(bruto) if bruto else None
    if inst == SEM_NUMERO:
        inst = None
    tel = _digitos(linha.get("telefone"))
    match = None
    if len(tel) >= 8:
        match = indice["8"].get(tel[-8:])
    if match is None and len(tel) >= 4:
        match = indice["4"].get(tel[-4:])
    if match:
        return match, match
    return inst, "origem não identificada"


def linhas_com_origem(
    gest_value: Any,
    state: dict[str, dict[str, Any]],
) -> list[dict[str, Any]] | None:
    linhas = gestor.coletar_linhas_venda(gest_value)
    if linhas is None:
        return None
    indice = _indice_conversas(state)
    out = []
    for linha in linhas:
        numero, origem = _origem_da_venda(linha, indice)
        out.append(
            {
                "telefone_final": telefone_final(linha.get("telefone") or None),
                "valor": linha.get("valor"),
                "numero": numero,
                "origem": origem,
            }
        )
    return out


def _eventos_periodo(ini_ts: float, fim_ts: float) -> list[dict[str, Any]]:
    eventos = espelho.eventos_recentes(max_lines=40000)
    out = []
    for ev in eventos:
        ts = ev.get("ts")
        if ts is None:
            continue
        t = float(ts)
        if ini_ts <= t < fim_ts:
            out.append(ev)
    return out


def _caminhos_contagem() -> list[Path]:
    bruto = os.environ.get("CONTAGEM_COMPLETA") or os.environ.get("PAINEL_CONTAGEM_FILE") or ""
    caminhos = [Path(bruto)] if bruto else []
    caminhos.extend(
        [
            Path("/var/lib/painel-gxtv/contagem_completa.json"),
            Path("/opt/painel-gxtv/data/contagem_completa.json"),
            Path("/opt/painel-gxtv/var/contagem_completa.json"),
            Path("/opt/mnrobo/atendimento/ai/private/contagem_completa.json"),
        ]
    )
    return caminhos


def _contagem_do_cache_v1(pasta: Path | None = None) -> dict[str, Any] | None:
    """Mesmo JSON diário do /contagem do painel atual. Só lê, não grava."""
    pasta = pasta or Path(
        os.environ.get("PAINEL_CONTADOR_CACHE")
        or str(_CONTADOR_CACHE)
    )
    try:
        dia = agora().date().isoformat()
        doc = json.loads((pasta / f"{dia}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    bloco = doc.get("bloco")
    if not isinstance(bloco, dict):
        return None
    ontem = doc.get("ontem_corte")
    return {
        "gerado_em": doc.get("gerado_em"),
        "hoje": bloco,
        "ontem": ontem if isinstance(ontem, dict) else None,
    }


def _ler_contagem() -> dict[str, Any] | None:
    """Lê o resumo que o painel atual já gravou. Não escreve nele."""
    for caminho in _caminhos_contagem():
        try:
            if not caminho.is_file():
                continue
            data = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        if isinstance(data.get("hoje"), dict) or isinstance(data.get("bloco"), dict):
            if isinstance(data.get("bloco"), dict) and "hoje" not in data:
                return {
                    "gerado_em": data.get("gerado_em"),
                    "hoje": data.get("bloco"),
                    "ontem": data.get("ontem_corte") if isinstance(data.get("ontem_corte"), dict) else None,
                }
            return data
    return _contagem_do_cache_v1()


def _bloco_dia(contagem: dict[str, Any], periodo: str) -> dict[str, Any] | None:
    if periodo == "hoje":
        dia = contagem.get("hoje")
        return dia if isinstance(dia, dict) else None
    if periodo == "ontem":
        dia = contagem.get("ontem")
        return dia if isinstance(dia, dict) else None
    return None


def _resumo_lateral(
    *,
    fonte_conversas: bool,
    conversas: list[dict[str, Any]],
    viu_texto_cliente: bool,
    periodo: str,
) -> dict[str, Any]:
    if not fonte_conversas:
        pediram = sem_dado("sem a fila do webhook")
    elif not viu_texto_cliente:
        pediram = sem_dado("as mensagens do cliente chegaram sem texto")
    else:
        n = sum(1 for st in conversas if _pediu_preco(st))
        pediram = _campo(str(n), n, "pela conversa")

    contagem = _ler_contagem()
    dia = _bloco_dia(contagem, periodo) if contagem else None
    if periodo == "7d":
        pagamentos = sem_dado("o resumo de pagamentos que o painel atual guarda é do dia, não dos 7 dias")
        renovacoes = sem_dado("o resumo de renovações que o painel atual guarda é do dia, não dos 7 dias")
    elif dia is None:
        pagamentos = sem_dado("o resumo de pagamentos ainda não chegou")
        renovacoes = sem_dado("o resumo de renovações ainda não chegou")
    else:
        if dia.get("mp_ok") and dia.get("mp_n") is not None:
            reais = _brl(dia.get("mp_reais"))
            pagamentos = _campo(str(int(dia["mp_n"])), int(dia["mp_n"]), reais or "sem o valor em R$")
        else:
            pagamentos = sem_dado("o Mercado Pago ainda não chegou")
        if dia.get("renovado_n") is not None:
            reais_r = _brl(dia.get("renovado_reais"))
            renovacoes = _campo(
                str(int(dia["renovado_n"])),
                int(dia["renovado_n"]),
                reais_r or "sem o valor em R$",
            )
        else:
            renovacoes = sem_dado("o resumo de renovações ainda não chegou")
    return {
        "pediram_assinatura": pediram,
        "pagamentos": pagamentos,
        "renovacoes": renovacoes,
    }


def _card(
    rotulo: str,
    rows: list[dict[str, Any]],
    tempos: dict[str, float | None],
    pix: dict[str, int | None],
    vendas: dict[str, int | None],
) -> dict[str, Any]:
    n = len(rows)
    fin = sum(1 for r in rows if r.get("stage") == "resolvido")
    px = pix.get(rotulo)
    vd = vendas.get(rotulo)
    return {
        "id": rotulo,
        "grupo": grupo_de(rotulo),
        "conversas": _campo(str(n), n),
        "finalizadas": _campo(str(fin), fin),
        "abertas": _campo(str(n - fin), n - fin),
        "tempo_resposta": _campo(_fmt_tempo(tempos.get(rotulo)), tempos.get(rotulo)),
        "pix_enviados": sem_dado() if px is None else _campo(str(px), px),
        "vendas_dia": sem_dado() if vd is None else _campo(str(vd), vd),
    }


def _agrupar(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    por: dict[str, list[dict[str, Any]]] = {}
    for card in cards:
        por.setdefault(str(card.get("grupo") or "outros"), []).append(card)
    saida = []
    for gid, titulo in _GRUPOS:
        rows = por.get(gid) or []
        if not rows:
            continue
        rows.sort(key=lambda c: (-int(c["conversas"]["valor"] or 0), str(c["id"]).casefold()))
        nome = "Sem número" if gid == "outros" and all(c["id"] == SEM_NUMERO for c in rows) else titulo
        saida.append({"id": gid, "titulo": nome, "cards": rows})
    return saida


async def montar_numeros(
    filters: dict[str, Any] | None = None,
    gest: Any | None = None,
) -> dict[str, Any]:
    filters = filters or {}
    periodo = str(filters.get("periodo") or "hoje")
    ini, fim, rotulo = janela_periodo(periodo)
    if gest is None:
        gest = await gestor.fetch_kpis_comerciais()

    fonte_conversas = espelho.WEBHOOK_QUEUE.is_file()
    aviso = credenciais.aviso()
    if aviso is None and getattr(gest, "state", None) is not None and gest.state.value in (
        "unavailable",
        "error",
    ):
        aviso = gest.message or "Gestor indisponível. Vendas do dia ficam sem dado."

    state: dict[str, dict[str, Any]] = {}
    if fonte_conversas:
        events = _eventos_periodo(ini.timestamp(), fim.timestamp())
        state = _build_conversation_state(events)

    grupos: dict[str, list[dict[str, Any]]] = {}
    gaps_por: dict[str, list[float]] = {}
    textos_por: dict[str, list[str]] = {}
    conversas_cliente: list[dict[str, Any]] = []
    viu_texto = False
    now = agora().timestamp()
    pedido = str(filters.get("numero") or "")
    for cid, st in state.items():
        if not _cliente_escreveu(st):
            continue
        lab = rotulo_instancia(
            st.get("instance"),
            phone=st.get("instance_phone"),
            evento=st.get("evento"),
            instance_id=st.get("instance_id"),
        )
        if _oculto_painel(lab):
            continue
        if not _bate_filtro(lab, pedido):
            continue
        conversas_cliente.append(st)
        for msg in st.get("msgs") or []:
            if not msg.get("from_me") and str(msg.get("text") or "").strip():
                viu_texto = True
        stage = _classify_stage(st, now)
        grupos.setdefault(lab, []).append({"conversation_id": cid, "stage": stage})
        for gap in _response_gaps(st.get("msgs") or []):
            gaps_por.setdefault(lab, []).append(float(gap["gap_s"]))
        for msg in st.get("msgs") or []:
            if msg.get("from_me") and msg.get("text"):
                textos_por.setdefault(lab, []).append(str(msg.get("text")))

    tempos: dict[str, float | None] = {}
    pix: dict[str, int | None] = {}
    for lab, vals in gaps_por.items():
        tempos[lab] = round(statistics.median(vals), 1) if vals else None
    for lab in grupos:
        if lab not in tempos:
            tempos[lab] = None
        saidas = textos_por.get(lab) or []
        pix[lab] = None if not saidas else sum(1 for texto in saidas if _PIX_ENVIO.search(texto))

    gest_value = gest.value if isinstance(getattr(gest, "value", None), dict) else None
    linhas = linhas_com_origem(gest_value, state)
    gestor_ok = bool(credenciais.tem()) and gest.state.value not in ("unavailable", "error")
    vendas: dict[str, int | None] = {lab: (0 if gestor_ok else None) for lab in grupos}
    if linhas is not None and gestor_ok:
        for linha in linhas:
            if linha.get("origem") == "origem não identificada":
                continue
            num = linha.get("numero")
            if num in vendas:
                vendas[num] = int(vendas[num] or 0) + 1

    cards = [
        _card(lab, rows, tempos, pix, vendas)
        for lab, rows in grupos.items()
    ]
    cards.sort(key=lambda c: (-int(c["conversas"]["valor"] or 0), str(c["id"]).casefold()))
    nota = _NOTA if fonte_conversas else "Sem a fila do webhook, a lista de números fica sem dado."
    return {
        "timezone": TZ_NAME,
        "window": {"inicio": iso_bahia(ini), "fim": iso_bahia(fim), "label": rotulo},
        "aviso_gestor": aviso,
        "fonte_conversas": fonte_conversas,
        "fonte_gestor": gestor_ok,
        "nota": nota,
        "resumo": _resumo_lateral(
            fonte_conversas=fonte_conversas,
            conversas=conversas_cliente,
            viu_texto_cliente=viu_texto,
            periodo=periodo,
        ),
        "grupos": _agrupar(cards),
        "cards": cards,
        "vendas": linhas or [],
        "vendas_sem_lista": linhas is None,
        "computed_at": iso_bahia(agora()),
    }
