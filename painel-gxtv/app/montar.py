"""Monta o estado que o navegador vê. Não lê arquivo e não inventa número."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.assuntos import nome_atendente, ordem_atendentes, parece_codigo_interno, rotulo_assunto
from app.contador_cache import numero
from app.dinheiro import classificar_dia
from app.frases import comparacao, duracao, inteiro, juntar, reais, seta
from app.mascarar import sanitizar
from app.tempo import TZ

_FECHADOS = {"resolvido", "resolvida", "fechado", "fechada", "encerrado", "encerrada", "finalizado", "finalizada"}
_ATIVOS = {"active", "ativo", "ativa", "enabled", "ok"}


def montar(fontes: dict) -> dict:
    agora: datetime = fontes["agora"].astimezone(TZ)
    dinheiro = classificar_dia(fontes.get("pagamentos"), fontes.get("lancamentos"), agora)
    dinheiro_motivo = _aplicar_contagem(dinheiro, fontes.get("contagem"))

    if fontes.get("sigma") is None:
        sigma = _sigma(None, None, agora)
        sigma["motivo"] = fontes.get("sigma_motivo") or "sem dado — ainda carregando do painel Sigma"
    else:
        sigma = _sigma(fontes.get("sigma") or [], fontes.get("sigma_quando"), agora)

    sql = fontes.get("sql") or {}
    log = fontes.get("log") or {}
    contador = fontes.get("contador")
    vendas = _vendas(sql, contador, dinheiro, fontes.get("testes_eventos"), fontes.get("tabela_eventos"))
    chats = _chats(sql, contador, fontes.get("motivos") or {})
    clientes = _clientes(sigma, contador)
    _completar_apps(chats, clientes)
    atendimento = _atendimento(sql, log)
    completa = fontes.get("contagem_completa")
    met = fontes.get("metricas_hoje")
    esp_cont = ((completa or {}).get("hoje") or {}).get("esperando")
    if isinstance(esp_cont, int) and not (completa or {}).get("aviso"):
        # mesmo número da linha "Esperando +15 min" do /contagem (atualiza a cada 5 min)
        atendimento["esperando_painel"] = atendimento.get("esperando")
        atendimento["esperando"] = esp_cont
        atendimento["fila_frase"] = (atendimento.get("fila_frase") or "") + " O número grande é o mesmo do resumo do Telegram (/contagem, atualiza a cada 5 min); a lista abaixo é a leitura ao vivo do painel."
    qualidade = _qualidade(sql, contador, chats)
    saude = _saude(fontes, agora)
    calor = _calor(vendas, dinheiro)
    linha = _linha(dinheiro, fontes.get("eventos") or [])
    rotinas = fontes.get("rotinas")
    frase, tom = _frase_topo(saude, atendimento, dinheiro_motivo)

    _pessoas_reais(chats, met)
    extra = fontes.get("sigma_extra") or {}
    vencem = _vencem_card(sigma, clientes, sql.get("vence_avisos"), completa, extra)
    destaques = {
        "dinheiro": _destaque_dinheiro(dinheiro, dinheiro_motivo),
        "previsao": _previsao(dinheiro, dinheiro_motivo, agora),
        "renov": _destaque_renov(completa),
        "atendidos": _destaque_atendidos(met, saude),
        "espera": _destaque_espera(atendimento),
        "robo": _destaque_robo(saude, chats),
        "vencem": vencem if vencem else _destaque_vencem(clientes),
    }
    estado = {
        "hora": agora.isoformat(),
        "frase": frase,
        "tom": tom,
        "destaques": destaques,
        "calor": calor,
        "linha": linha[:8],
        "rotinas": rotinas or [],
        "rotinas_motivo": None if rotinas is not None else (fontes.get("rotinas_motivo") or "sem dado — não consegui ler os agendamentos do servidor"),
        "chats": chats,
        "resumo_contador": _aplicar_sigma_painel(_resumo_contador(completa), extra),
        "gavetas": {
            "dinheiro": _gaveta_dinheiro(dinheiro, dinheiro_motivo, linha),
            "vendas": vendas,
            "clientes": clientes,
            "atendimento": atendimento,
            "qualidade": qualidade,
            "saude": saude,
        },
        "blocos": {},
    }
    estado["blocos"] = {
        "dinheiro": _bloco(dinheiro_motivo is None, destaques["dinheiro"]["frase"]),
        "vendas": _bloco(not vendas["sem_dado"], vendas["resumo"]),
        "clientes": _bloco(not clientes["sem_dado"], clientes["resumo"]),
        "chats": _bloco(not chats["sem_dado"], chats["resumo"]),
        "atendimento": _bloco(not atendimento["sem_dado"], atendimento["resumo"]),
        "qualidade": _bloco(not qualidade["sem_dado"], qualidade["resumo"]),
        "saude": _bloco(not saude["sem_dado"], saude["resumo"]),
        "rotinas": _bloco(rotinas is not None, "agenda lida" if rotinas is not None else estado["rotinas_motivo"]),
    }
    return sanitizar(estado)


def _pessoas_reais(chats: dict, met) -> None:
    """Quem atendeu: contado conversa por conversa (o aviso automático de cobrança não conta como robô)."""
    if not met or not met.get("hoje"):
        return
    hoje = met["hoje"]["pessoas"]
    ontem = (met.get("ontem") or {}).get("pessoas") or {}
    pessoas = []
    for nome in sorted(hoje, key=lambda n: (n != "Robô", -hoje[n]["conversas"])):
        d = hoje[nome]
        o = (ontem.get(nome) or {}).get("conversas")
        verbo = "atendeu" if nome == "Robô" else "falou em"
        artigo = "O" if nome in ("Robô", "Jorge", "Gustavo", "Guilherme") else "A"
        nucleo = f"{artigo} {nome} {verbo} {inteiro(d['conversas'])} {'conversa' if d['conversas'] == 1 else 'conversas'} hoje e mandou {inteiro(d['mensagens'])} {'mensagem' if d['mensagens'] == 1 else 'mensagens'}"
        pessoas.append({"id": nome.casefold(), "nome": nome, "conversas": d["conversas"], "mensagens": d["mensagens"], "ontem": o,
                        "frase": juntar(nucleo, comparacao(d["conversas"], o)), "delta": seta(d["conversas"], o)})
    chats["pessoas"] = pessoas
    robo = hoje.get("Robô")
    if robo:
        chats["robo_conversas"] = robo["conversas"]
        chats["robo_ontem"] = (ontem.get("Robô") or {}).get("conversas")
        chats["robo_motivo"] = None
        chats["resumo"] = f"O robô atendeu {inteiro(robo['conversas'])} conversas hoje"


def _previsao(dinheiro: dict, motivo, agora: datetime) -> dict:
    """Estimativa: o que já entrou + o ritmo real das últimas 3 horas até a meia-noite."""
    base = {"v": None, "frase": "sem dado — ainda não dá para estimar o fim do dia", "ritmo": None, "horas": None}
    if motivo or dinheiro.get("total") is None:
        return base
    acum = dinheiro.get("horas") or []
    h = agora.hour
    if len(acum) < 24 or acum[h] is None:
        return base
    por_hora = []
    anterior = 0.0
    for i in range(24):
        v = acum[i]
        if v is None:
            por_hora.append(None)
            continue
        por_hora.append(round(v - anterior, 2))
        anterior = v
    ini = max(0, h - 2)
    passadas = (h - ini) + agora.minute / 60
    if passadas < 0.5:
        return base | {"horas": por_hora}
    soma = sum(v or 0 for v in por_hora[ini:h + 1])
    ritmo = soma / passadas
    restante = max(0.0, 24 - (h + agora.minute / 60))
    estimado = dinheiro["total"] + ritmo * restante
    arred = int(round(estimado / 10.0) * 10)
    return {
        "v": arred,
        "ritmo": round(ritmo, 2),
        "restante_h": round(restante, 1),
        "horas": por_hora,
        "frase": f"No ritmo atual você fecha o dia com cerca de {reais(arred)}",
        "nota": f"É uma estimativa: soma o que já entrou com o ritmo das últimas 3 horas ({reais(ritmo)} por hora) até a meia-noite. Pode mudar.",
    }


def _destaque_renov(completa) -> dict:
    d = _destaque_renov_orig(completa)
    try:  # POR_CONTA_1810: renovado sem duplicados e com valor real do MP
        from app.por_conta import ligado, pacote
        if ligado() and d.get("v") is not None:
            p = pacote()
            d["v"], d["reais"] = p["renovado_n"], p["renovado_reais"]
            o = d.get("ontem")
            frase = reais(p["renovado_reais"], centavos=True) + " (sem duplicados)"
            d["frase"] = f"{frase} · ontem até agora: {inteiro(o)}" if o is not None else frase
            d["delta"] = seta(d["v"], o)
    except Exception:
        pass
    return d


def _destaque_renov_orig(completa) -> dict:
    hoje = (completa or {}).get("hoje") or {}
    ontem = (completa or {}).get("ontem") or {}
    n = hoje.get("renovado_n")
    if n is None or not (hoje.get("ledger_ok") or hoje.get("acoes_ok")):
        return {"v": None, "frase": "sem dado — o resumo ainda não trouxe as renovações", "tom": "sem"}
    o = ontem.get("renovado_n") if (ontem.get("ledger_ok") or ontem.get("acoes_ok")) else None
    valor = hoje.get("renovado_reais")
    frase = reais(valor, centavos=True) if valor is not None else ""
    if o is not None:
        frase = f"{frase} · ontem até agora: {inteiro(o)}" if frase else f"ontem até agora: {inteiro(o)}"
    tom = "sem" if o is None else ("ok" if n >= o else ("atencao" if n >= 0.7 * o else "ruim"))
    return {"v": n, "ontem": o, "reais": valor, "frase": frase, "tom": tom, "delta": seta(n, o)}


def _destaque_atendidos(met, saude) -> dict:
    if not met or not met.get("hoje"):
        return {"v": None, "frase": "calculando… a primeira leitura do dia leva uns 4 minutos", "tom": "sem"}
    h = met["hoje"]
    o = (met.get("ontem") or {}).get("atendidos")
    partes = [f"{p} {inteiro(d['conversas'])}" for p, d in sorted(h["pessoas"].items(), key=lambda x: -x[1]["conversas"])]
    frase = juntar(f"{inteiro(h['atendidos'])} clientes atendidos hoje", comparacao(h["atendidos"], o) if o is not None else None)
    tom = "ruim" if saude.get("robo") is False else "ok"
    return {"v": h["atendidos"], "ontem": o, "frase": frase, "quem": partes, "tom": tom, "delta": seta(h["atendidos"], o),
            "robo_parado": saude.get("robo") is False}


def _vencem_avisos(avisos, completa) -> dict | None:
    """Sem o cadastro do Sigma, o melhor retrato atual é: quantos receberam hoje o aviso automático de vencimento."""
    if not avisos:
        return None
    from app.contador_cache import _tel8

    hoje = avisos.get("hoje") or {}
    renovados = (completa or {}).get("_tel8_renovados") or set()
    ja = sum(1 for d in hoje.values() if _tel8(d.get("telefone")) in renovados)
    por_painel: dict[str, int] = {}
    for d in hoje.values():
        por_painel[d["painel"] or "?"] = por_painel.get(d["painel"] or "?", 0) + 1
    n = len(hoje)
    frase = f"{inteiro(n)} {'cliente recebeu' if n == 1 else 'clientes receberam'} hoje o aviso \"vence hoje\""
    if n:
        frase += f" · {inteiro(ja)} já {'renovou' if ja == 1 else 'renovaram'}"
    return {
        "v": n, "ja_renovaram": ja, "amanha": len(avisos.get("amanha") or {}), "dois_dias": len(avisos.get("dois") or {}),
        "por_painel": dict(sorted(por_painel.items())), "frase": frase, "tom": "ok" if n == 0 else "atencao", "aviso": None,
        "fonte": "Sem o cadastro, contei quem recebeu o aviso de vencimento hoje.",
    }


_NOMES_ERRO = {
    "midia_texto_barrado": "Foto ou áudio barrado", "ia_resgate": "Robô precisou de resgate", "ia_turno_garante": "Garantia de resposta",
    "pergunta_repetida": "Pergunta repetida", "dados_repetidos_sem_bloco": "Dados repetidos", "trava_resolvido": "Já estava resolvido",
}


def _nome_erro(cod: str) -> str:
    cod = str(cod or "").replace("Barrado pela trava: ", "")
    return _NOMES_ERRO.get(cod, cod.replace("_", " ").capitalize())


def _resumo_contador(completa) -> dict | None:
    """O bloco do /contagem em pedaços para virar cartão e gráfico (nada de telefone)."""
    if not completa or not completa.get("hoje"):
        return None
    h = completa["hoje"]
    o = completa.get("ontem") or {}
    at = h.get("atendimento") if isinstance(h.get("atendimento"), dict) else {}
    fiscal = h.get("fiscal") if isinstance(h.get("fiscal"), dict) else {}
    web = h.get("webhook") if isinstance(h.get("webhook"), dict) else {}
    return {
        "gerado_em": completa.get("gerado_em"),
        "aviso": completa.get("aviso"),
        "sigma_ok": bool(h.get("sigma_ok")),
        "mp": {"n": h.get("mp_n"), "reais": h.get("mp_reais"), "fora_n": h.get("mp_fora_n"), "fora_reais": h.get("mp_fora_reais"),
               "sem_n": h.get("mp_sem_n"), "sem_reais": h.get("mp_sem_reais"), "ok": bool(h.get("mp_ok")),
               "ontem_n": o.get("mp_n") if o.get("mp_ok") else None,
               "ontem_reais": o.get("mp_reais") if o.get("mp_ok") else None,
               "ontem_ok": bool(o.get("mp_ok"))},
        "renov": {"n": h.get("renovado_n"), "reais": h.get("renovado_reais"), "ontem_n": o.get("renovado_n"), "ontem_reais": o.get("renovado_reais"),
                  "por_painel": fiscal.get("por_painel"), "alertado": fiscal.get("alertado"), "duplicado": fiscal.get("duplicado")},
        "vendas": {"venda_nova": h.get("venda_nova"), "vendas_novas": h.get("vendas_novas"), "testes_criados": h.get("testes_criados"),
                   "testes_convertidos": h.get("testes_convertidos"), "venda_preco": h.get("venda_preco"), "audio": h.get("audio_n"),
                   "audio_ontem": o.get("audio_n"), "live_xl5z": h.get("live_xl5z"), "funil_n": h.get("funil_n"),
                   "vendas_novas_ontem": o.get("vendas_novas") if o.get("sigma_ok") else None,
                   "testes_ontem": o.get("testes_criados") if o.get("sigma_ok") else None},
        "atendimento": {"robo": (at.get("robo") or {}), "humanos": {k.replace("Atendente ", "").replace(" Gerente", ""): v for k, v in (at.get("humanos") or {}).items()},
                        "esperando": h.get("esperando"), "webhook_tel": web.get("telefones"), "webhook_ev": web.get("eventos")},
        "avisos": (at.get("avisos") or {}),
        "qualidade": {"feedback": h.get("feedback_n"), "responderam": h.get("fb_resp"), "satisfeitos": h.get("fb_ok"), "reclamaram": h.get("fb_neg"),
                      "erro_real": h.get("erro_real"), "msgs_env": h.get("msgs_env"), "erro_pct": h.get("erro_pct"),
                      "erros": [{"nome": _nome_erro(a), "n": b} for a, b in (h.get("top_erro") or [])],
                      "barrados": [{"nome": _nome_erro(a), "n": b} for a, b in (h.get("barrados") or [])],
                      "trava_conv": h.get("trava_conv_n"), "trava_conv_ontem": o.get("trava_conv_n"), "trava_ev": h.get("trava_ev"), "ia_resolvido": h.get("ia_resolvido")},
        "semana": completa.get("semana") or [],
    }


def _bloco(tem_dado: bool, resumo: str) -> dict:
    if tem_dado:
        return {"sem_dado": False, "resumo": resumo}
    texto = resumo if resumo and "sem dado" in resumo else f"sem dado — {resumo or 'ainda não chegou'}"
    return {"sem_dado": True, "resumo": texto}


def _aplicar_contagem(dinheiro: dict, contagem) -> str | None:
    """O número grande é o bloco do /contagem. A soma da lista ao vivo não entra aqui."""
    if not isinstance(contagem, dict) or contagem.get("mp_reais") is None:
        dinheiro["total"] = None
        dinheiro["qtd"] = None
        dinheiro["ticket"] = None
        dinheiro["ontem"] = None
        dinheiro["renov_qtd"] = None
        dinheiro["renov_valor"] = None
        if isinstance(contagem, dict) and contagem.get("motivo"):
            return contagem["motivo"]
        return "sem dado — o resumo de hoje ainda não chegou"
    total = round(float(contagem["mp_reais"]), 2)
    qtd = contagem.get("mp_n")
    qtd = int(qtd) if qtd is not None else None
    dinheiro["total"] = total
    dinheiro["qtd"] = qtd
    dinheiro["ticket"] = round(total / qtd, 2) if qtd else None
    ontem = contagem.get("ontem_reais")
    dinheiro["ontem"] = None if ontem is None else round(float(ontem), 2)
    qtd_renov = contagem.get("renovado_n")
    valor_renov = contagem.get("renovado_reais")
    if qtd_renov is None or valor_renov is None:
        dinheiro["renov_qtd"] = None
        dinheiro["renov_valor"] = None
    else:
        dinheiro["renov_qtd"] = int(qtd_renov)
        dinheiro["renov_valor"] = round(float(valor_renov), 2)
    fora = contagem.get("mp_fora_n")
    if fora is not None:
        dinheiro["excluidos"] = int(fora)
    dinheiro["aviso"] = contagem.get("aviso")
    return None


def _destaque_dinheiro(dinheiro: dict, motivo: str | None) -> dict:
    if motivo or dinheiro.get("total") is None:
        texto = motivo or "sem dado — o resumo de hoje ainda não chegou"
        return {"v": None, "ontem": None, "frase": texto, "motivo": texto, "delta": None, "meta": None}
    comp = comparacao(dinheiro["total"], dinheiro["ontem"], dinheiro=True)
    qtd = dinheiro.get("qtd")
    base = f"{reais(dinheiro['total'], centavos=True)} em {inteiro(qtd)} {'pagamento' if qtd == 1 else 'pagamentos'} de clientes" if qtd else f"{reais(dinheiro['total'], centavos=True)} entrou hoje de clientes"
    frase = juntar(base, comp)
    aviso = dinheiro.get("aviso")
    if aviso:
        frase = f"{frase} · {aviso}"
    return {
        "v": dinheiro["total"],
        "ontem": dinheiro["ontem"],
        "frase": frase,
        "motivo": None,
        "delta": seta(dinheiro["total"], dinheiro["ontem"]),
        "meta": None,
        "qtd": dinheiro["qtd"],
    }


def _destaque_espera(atendimento: dict) -> dict:
    valor = atendimento["esperando"]
    if valor is None:
        motivo = atendimento["esperando_motivo"]
        return {"v": None, "frase": motivo, "motivo": motivo, "tom": "sem"}
    if valor == 0:
        return {"v": 0, "frase": "Ninguém esperando resposta agora", "motivo": None, "tom": "ok"}
    frase = f"{inteiro(valor)} {'cliente esperando resposta' if valor == 1 else 'clientes esperando resposta'} há mais de 15 minutos"
    return {"v": valor, "frase": frase, "motivo": None, "tom": "ruim" if valor >= 4 else "atencao"}


def _destaque_robo(saude: dict, chats: dict) -> dict:
    ligado = saude["robo"]
    conversas = chats["robo_conversas"]
    ontem = chats["robo_ontem"]
    if ligado is False:
        return {
            "ligado": False,
            "v": conversas,
            "ontem": ontem,
            "frase": "O robô está parado",
            "motivo": None if conversas is not None else chats["robo_motivo"],
            "tom": "ruim",
            "delta": seta(conversas, ontem) if conversas is not None else None,
        }
    if ligado is None and conversas is None:
        motivo = saude["robo_motivo"] or chats["robo_motivo"]
        return {"ligado": None, "v": None, "ontem": None, "frase": motivo, "motivo": motivo, "tom": "sem", "delta": None}
    if conversas is None:
        frase = "O robô está ligado" if ligado else (saude["robo_motivo"] or "sem dado — não deu para ver o robô")
        return {
            "ligado": ligado,
            "v": None,
            "ontem": None,
            "frase": frase if ligado else frase,
            "motivo": chats["robo_motivo"],
            "tom": "ok" if ligado else "sem",
            "delta": None,
        }
    comp = comparacao(conversas, ontem)
    frase = juntar(f"O robô atendeu {inteiro(conversas)} {'conversa' if conversas == 1 else 'conversas'} hoje", comp)
    return {
        "ligado": True if ligado is None else ligado,
        "v": conversas,
        "ontem": ontem,
        "frase": frase,
        "motivo": None,
        "tom": "ok",
        "delta": seta(conversas, ontem),
    }


def _vencem_card(sigma, clientes, avisos, completa, extra) -> dict:
    if extra.get("exato") and sigma.get("vence_hoje") is not None:
        card = _destaque_vencem(clientes)
        card["exato"] = True
        card["amanha"] = sigma.get("vence_amanha")
        card["fonte"] = "Vencem hoje de verdade, pelo cadastro."
        if extra.get("incompleto"):
            card["aviso"] = "Lista incompleta: o número pode subir."
        elif clientes.get("aviso"):
            card["aviso"] = clientes.get("aviso")
        return card
    avisos_card = _vencem_avisos(avisos, completa)
    return avisos_card if avisos_card else _destaque_vencem(clientes)


def _aplicar_sigma_painel(resumo, extra) -> dict | None:
    """Encaixa vendas/testes do cadastro Sigma no resumo do /contagem.

    Se o espelho sigma_rows não tem created_at de hoje (coletor congelado),
    não publica 0 como verdade: marca desatualizado e zera a confiança dos
    cards (UI cai no fallback do robô / traço).
    """
    if not isinstance(resumo, dict):
        return resumo
    extra = extra or {}
    desatualizado = bool(extra.get("desatualizado"))

    if not extra.get("exato") and not resumo.get("sigma_ok"):
        resumo["sigma_frase"] = "sem dado — o cadastro do Sigma ainda não chegou"
        return resumo

    if desatualizado:
        vendas = resumo.get("vendas") if isinstance(resumo.get("vendas"), dict) else {}
        # Não inventar número de vendas novas (MP ≠ venda nova Sigma).
        vendas["vendas_novas"] = None
        vendas["venda_nova"] = None
        # Testes: UI usa A.ts (r639z) quando testes_criados é null / stale.
        vendas["testes_criados"] = None
        vendas["testes_fonte"] = "robo"
        vendas["vendas_hint"] = "cadastro Sigma desatualizado"
        resumo["vendas"] = vendas
        resumo["sigma_ok"] = True
        resumo["sigma_cadastro_desatualizado"] = True
        resumo["sigma_frase"] = extra.get("frase") or (
            "Cadastro Sigma desatualizado — sem created_at de hoje."
        )
        return resumo

    if resumo.get("sigma_ok"):
        resumo["sigma_cadastro_desatualizado"] = False
        return resumo

    if not extra.get("exato"):
        return resumo

    vendas = resumo.get("vendas") if isinstance(resumo.get("vendas"), dict) else {}
    vendas["vendas_novas"] = extra.get("vendas_novas")
    vendas["venda_nova"] = extra.get("vendas_novas")
    vendas["testes_criados"] = extra.get("testes_criados")
    vendas.pop("testes_fonte", None)
    vendas.pop("vendas_hint", None)
    resumo["vendas"] = vendas
    resumo["sigma_ok"] = True
    resumo["sigma_cadastro_desatualizado"] = False
    resumo["sigma_frase"] = extra.get("frase") or "Li o cadastro direto."
    return resumo


def _destaque_vencem(clientes: dict) -> dict:
    valor = clientes["vence_hoje"]
    if valor is None:
        return {"v": None, "frase": clientes["motivo"], "motivo": clientes["motivo"], "tom": "sem", "aviso": None}
    aviso = clientes.get("aviso")
    frase = f"{inteiro(valor)} {'cliente vence hoje' if valor == 1 else 'clientes vencem hoje'}"
    tom = "ok" if valor == 0 else "atencao"
    return {"v": valor, "frase": frase, "motivo": None, "tom": tom, "aviso": aviso}


def _frase_topo(saude, atendimento, dinheiro_motivo) -> tuple[str, str]:
    if saude["robo"] is False:
        return "Atenção: o robô está parado", "ruim"
    espera = atendimento["esperando"]
    if espera is not None and espera >= 4:
        return f"Atenção: {inteiro(espera)} clientes esperando resposta", "ruim"
    if espera is not None and espera >= 1:
        texto = "1 cliente esperando resposta" if espera == 1 else f"{inteiro(espera)} clientes esperando resposta"
        return f"Atenção: {texto}", "atencao"
    if saude["disco"] is not None and saude["disco"] >= 92:
        return "Atenção: o disco está quase cheio", "ruim"
    if saude["cpu"] is not None and saude["cpu"] >= 85:
        return "Atenção: o computador está sobrecarregado", "ruim"
    if saude["disco"] is not None and saude["disco"] >= 80:
        return "Atenção: o disco está enchendo", "atencao"
    if dinheiro_motivo:
        return "Atenção: o resumo de hoje ainda não chegou", "atencao"
    return "Hoje está tudo normal", "ok"


def _sigma(clientes, quando: datetime | None, agora: datetime) -> dict:
    vazio = {
        "ativos": None,
        "vence_hoje": None,
        "vence_amanha": None,
        "vencidos": None,
        "paineis": None,
        "apps": None,
        "aparelhos": None,
        "aviso": None,
        "motivo": None,
    }
    if clientes is None:
        return vazio
    hoje = agora.date()
    amanha = hoje + timedelta(days=1)
    ativos = vence_hoje = vence_amanha = vencidos = 0
    paineis: dict[str, int] = {}
    apps: dict[str, int] = {}
    aparelhos: dict[str, int] = {}
    for cliente in clientes:
        if cliente.get("trial") or cliente.get("oculto"):  # OCULTAR_JORGE_1110
            continue
        status = str(cliente.get("status") or "").strip().casefold()
        vence = cliente.get("vence")
        ativo = status in _ATIVOS and (vence is None or vence >= hoje)
        vencido = vence is not None and vence < hoje
        if ativo:
            ativos += 1
        if vence == hoje:
            vence_hoje += 1
        elif vence == amanha:
            vence_amanha += 1
        if vencido:
            vencidos += 1
        if ativo or vence == hoje:
            painel = cliente.get("painel")
            if painel:
                paineis[painel] = paineis.get(painel, 0) + 1
            app = cliente.get("app")
            if app:
                apps[app] = apps.get(app, 0) + 1
            aparelho = cliente.get("aparelho")
            if aparelho:
                aparelhos[aparelho] = aparelhos.get(aparelho, 0) + 1
    aviso = None
    if quando is not None and agora - quando.astimezone(TZ) > timedelta(hours=36):
        aviso = f"o cadastro é de {quando.astimezone(TZ).strftime('%d/%m')} e pode estar desatualizado"
    return {
        "ativos": ativos,
        "vence_hoje": vence_hoje,
        "vence_amanha": vence_amanha,
        "vencidos": vencidos,
        "paineis": paineis,
        "apps": apps or None,
        "aparelhos": aparelhos or None,
        "aviso": aviso,
        "motivo": None,
    }


def _completar_apps(chats: dict, clientes: dict) -> None:
    if not chats.get("apps") and clientes.get("apps"):
        chats["apps"] = _mapa_itens(clientes["apps"])
        chats["apps_motivo"] = None
        chats["origem_apps"] = "cadastro dos clientes"
    elif chats.get("apps"):
        chats["origem_apps"] = "conversas de hoje"
    if not chats.get("aparelhos") and clientes.get("aparelhos"):
        chats["aparelhos"] = _mapa_itens(clientes["aparelhos"])
        chats["aparelhos_motivo"] = None
        chats["origem_aparelho"] = "cadastro dos clientes"
    elif chats.get("aparelhos") and not chats.get("origem_aparelho"):
        chats["origem_aparelho"] = "conversas de hoje"


def _como_lista(mapa):
    if mapa is None:
        return None
    if isinstance(mapa, list):
        return mapa or None
    return _mapa_itens(mapa) or None


def _mapa_itens(mapa: dict) -> list:
    itens = [{"nome": nome, "n": int(qtd)} for nome, qtd in mapa.items()]
    itens.sort(key=lambda item: item["n"], reverse=True)
    return itens


def _clientes(sigma: dict, contador) -> dict:
    venc_cache = (contador or {}).get("vencimentos") if isinstance((contador or {}).get("vencimentos"), dict) else None
    if sigma["ativos"] is None and venc_cache:
        sigma = {
            **sigma,
            "ativos": None,
            "vence_hoje": _int_chave(venc_cache, "hoje", "vence_hoje"),
            "vence_amanha": _int_chave(venc_cache, "amanha", "amanhã"),
            "vencidos": _int_chave(venc_cache, "vencidos"),
            "motivo": None if _int_chave(venc_cache, "hoje", "vence_hoje") is not None else sigma["motivo"],
            "aviso": "vencimentos vieram do resumo do Telegram",
        }
    sem = sigma["ativos"] is None and sigma["vence_hoje"] is None
    if sigma["ativos"] is not None:
        resumo = f"{inteiro(sigma['ativos'])} clientes ativos"
    elif sigma["vence_hoje"] is not None:
        resumo = f"{inteiro(sigma['vence_hoje'])} vencem hoje"
    else:
        resumo = sigma["motivo"] or "sem dado — ainda carregando do painel Sigma"
    return {
        "ativos": sigma["ativos"],
        "vence_hoje": sigma["vence_hoje"],
        "vence_amanha": sigma["vence_amanha"],
        "vencidos": sigma["vencidos"],
        "paineis": sigma["paineis"],
        "apps": sigma["apps"],
        "aparelhos": sigma["aparelhos"],
        "aviso": sigma["aviso"],
        "motivo": None if not sem else (sigma["motivo"] or "sem dado — ainda carregando do painel Sigma"),
        "origem_apps": "cadastro dos clientes" if sigma["apps"] else None,
        "resumo": resumo,
        "sem_dado": sem,
    }


def _vendas(sql, contador, dinheiro, testes_eventos, tabela_eventos) -> dict:
    funil_cache = _funil_cache(contador)
    leads = sql.get("leads_hoje")
    leads_ontem = sql.get("leads_ontem")
    testes = sql.get("testes")
    if testes is None:
        testes = testes_eventos
    tabela = tabela_eventos
    pagou = dinheiro["novas_qtd"]
    origem = None
    if funil_cache:
        leads = funil_cache["chegou"]
        testes = funil_cache["teste"]
        tabela = funil_cache["precos"]
        pagou = funil_cache["pagou"]
        leads_ontem = None
        origem = "resumo do Telegram"
    conv = None
    if leads not in (None, 0) and pagou is not None:
        conv = round(pagou / leads * 100, 1)
    elif leads == 0 and pagou is not None:
        conv = 0
    horas = sql.get("leads_horas")
    testes_horas = sql.get("testes_horas")
    sem = all(v is None for v in (leads, testes, tabela, pagou))
    if leads is not None:
        comp = comparacao(leads, leads_ontem)
        resumo = juntar(f"{inteiro(leads)} {'pessoa nova chamou' if leads == 1 else 'pessoas novas chamaram'} no WhatsApp hoje", comp)
    elif sem:
        resumo = "sem dado — ainda não deu para ver as conversas novas de hoje"
    else:
        resumo = "Vendas de hoje, com o que já deu para ler"
    return {
        "leads": leads,
        "leads_ontem": leads_ontem,
        "testes": testes,
        "tabela": tabela,
        "pagou": pagou,
        "conversao": conv,
        "leads_horas": horas,
        "testes_horas": testes_horas,
        "origem": origem,
        "resumo": resumo,
        "frase_leads": resumo if leads is not None else "sem dado — as conversas novas de hoje ainda não chegaram",
        "frase_testes": _frase_contagem(testes, "teste de 2 horas criado hoje", "testes de 2 horas criados hoje", "sem dado — nenhum registro de teste chegou"),
        "frase_pagou": _frase_contagem(pagou, "cliente novo pagou", "clientes novos pagaram", "sem dado — não deu para separar o cliente novo da renovação"),
        "sem_dado": sem,
        "delta_leads": seta(leads, leads_ontem),
    }


def _chats(sql, contador, motivos: dict) -> dict:
    brutos = sql.get("atendentes")
    pessoas = []
    robo_conversas = robo_ontem = None
    robo_motivo = "sem dado — não deu para separar quem atendeu cada conversa"
    if brutos:
        robo_motivo = None
        for codigo in ordem_atendentes():
            dados = brutos.get(codigo) or {}
            nome, artigo = nome_atendente(codigo)
            conversas = dados.get("conversas")
            mensagens = dados.get("mensagens")
            ontem = dados.get("conversas_ontem")
            if codigo == "robo":
                robo_conversas = conversas
                robo_ontem = ontem
            if conversas is None and mensagens is None:
                frase = f"sem dado — não achei {artigo.lower()} {nome} nas conversas de hoje"
                pessoas.append({"id": codigo, "nome": nome, "conversas": None, "mensagens": None, "frase": frase})
                continue
            comp = comparacao(conversas, ontem)
            nucleo = f"{artigo} {nome} {'atendeu' if codigo == 'robo' else 'falou em'} {inteiro(conversas or 0)} {'conversa' if (conversas or 0) == 1 else 'conversas'} hoje"
            if mensagens is not None:
                nucleo += f" e mandou {inteiro(mensagens)} {'mensagem' if mensagens == 1 else 'mensagens'}"
            pessoas.append({
                "id": codigo,
                "nome": nome,
                "conversas": conversas,
                "mensagens": mensagens,
                "ontem": ontem,
                "frase": juntar(nucleo, comp),
                "delta": seta(conversas, ontem),
            })
    else:
        for codigo in ordem_atendentes():
            nome, artigo = nome_atendente(codigo)
            pessoas.append({
                "id": codigo,
                "nome": nome,
                "conversas": None,
                "mensagens": None,
                "frase": f"sem dado — não achei {artigo.lower()} {nome} nas conversas de hoje",
            })

    assuntos = _rotular_mapa(sql.get("assuntos"), rotulo_assunto)
    travados = _agrupar_motivos(sql.get("travados"), motivos)
    erros = _agrupar_erros(sql.get("erros"))
    recentes = sql.get("recentes")
    telegram = _linhas_telegram(contador)
    tem_pessoa = any(p.get("conversas") is not None for p in pessoas)
    sem = not tem_pessoa and recentes is None and not telegram
    if robo_conversas is not None:
        resumo = f"O robô atendeu {inteiro(robo_conversas)} conversas hoje"
    elif recentes is not None:
        resumo = f"{inteiro(len(recentes))} conversas recentes na tela"
    elif telegram:
        resumo = "O resumo do Telegram chegou"
    else:
        resumo = "sem dado — as conversas de hoje ainda não chegaram"
    return {
        "pessoas": pessoas,
        "robo_conversas": robo_conversas,
        "robo_ontem": robo_ontem,
        "robo_motivo": robo_motivo if robo_conversas is None else None,
        "assuntos": assuntos,
        "assuntos_motivo": None if assuntos is not None else "sem dado — ainda não li as mensagens de hoje",
        "apps": _como_lista(sql.get("apps")),
        "aparelhos": _como_lista(sql.get("aparelhos")),
        "apps_motivo": None if sql.get("apps") else "sem dado — não achei o aplicativo nas conversas nem no cadastro",
        "aparelhos_motivo": None if sql.get("aparelhos") else "sem dado — não achei o aparelho nas conversas nem no cadastro",
        "origem_aparelho": sql.get("origem_aparelho"),
        "recentes": recentes,
        "recentes_motivo": None if recentes is not None else "sem dado — a lista de conversas ainda não chegou",
        "travados": travados,
        "erros": erros,
        "telegram": telegram,
        "telegram_motivo": None if telegram else "sem dado — o resumo do Telegram ainda não está salvo no servidor",
        "resumo": resumo,
        "sem_dado": sem,
    }


def _atendimento(sql, log) -> dict:
    esperando = sql.get("esperando")
    espera_motivo = None if esperando is not None else "sem dado — não deu para ver quem está esperando"
    abertas = sql.get("abertas")
    abertas_motivo = None if abertas is not None else "sem dado — não deu para contar as conversas abertas"
    resolvidas = sql.get("resolvidas")
    if resolvidas is None:
        resolvidas_motivo = sql.get("resolvidas_motivo") or "sem dado — as conversas não têm a marca de resolvida"
    else:
        resolvidas_motivo = None
    fila = log.get("fila") if log.get("fresco") else None
    ocup = log.get("em_atendimento") if log.get("fresco") else None
    tmr = sql.get("tmr")
    resp = sql.get("resp_min")
    recv = sql.get("recv_min")
    sem = esperando is None and abertas is None
    if esperando is not None:
        resumo = "Ninguém esperando" if esperando == 0 else f"{inteiro(esperando)} esperando há mais de 15 minutos"
    elif abertas is not None:
        resumo = f"{inteiro(abertas)} conversas com mensagem nas últimas 2 horas"
    else:
        resumo = espera_motivo
    return {
        "esperando": esperando,
        "esperando_motivo": espera_motivo,
        "lista": sql.get("esperando_lista") or [],
        "abertas": abertas,
        "abertas_motivo": abertas_motivo,
        "abertas_frase": _frase_contagem(abertas, "conversa com mensagem nas últimas 2 horas", "conversas com mensagem nas últimas 2 horas", abertas_motivo),
        "resolvidas": resolvidas,
        "resolvidas_motivo": resolvidas_motivo,
        "resolvidas_frase": _frase_contagem(resolvidas, "conversa resolvida hoje", "conversas resolvidas hoje", resolvidas_motivo),
        "fila": fila,
        "fila_frase": _frase_contagem(fila, "conversa na fila", "conversas na fila", "sem dado — a fila não está visível agora"),
        "em_atendimento": ocup,
        "em_atendimento_frase": _frase_contagem(ocup, "conversa que o robô está olhando agora", "conversas que o robô está olhando agora", "sem dado — não deu para ver quantas o robô está olhando"),
        "tmr": tmr,
        "tmr_txt": duracao(tmr) if tmr is not None else None,
        "tmr_motivo": None if tmr is not None else "sem dado — o tempo médio ainda não deu para calcular",
        "resp_min": resp,
        "recv_min": recv,
        "resp_agora": resp[-1] if resp else None,
        "resumo": resumo,
        "sem_dado": sem,
    }


def _qualidade(sql, contador, chats) -> dict:
    fb = sql.get("feedback")
    cache = (contador or {}).get("feedback") if isinstance((contador or {}).get("feedback"), dict) else None
    enviados = responderam = ok = ruim = None
    motivo_nota = None
    if cache:
        enviados = _int_chave(cache, "enviados")
        responderam = _int_chave(cache, "responderam")
        ok = _int_chave(cache, "satisfeitos", "satisfeito")
        ruim = _int_chave(cache, "reclamaram", "reclamou")
        motivo_nota = "veio do resumo do Telegram"
    elif fb:
        enviados = fb.get("enviados")
        responderam = fb.get("responderam")
        if fb.get("sem_classe"):
            ok = ruim = None
            motivo_nota = "sem dado — as respostas ainda não foram classificadas"
        else:
            ok = fb.get("ok")
            ruim = fb.get("ruim")
    duvidas = sql.get("duvidas")
    if duvidas is None and contador and numero((contador or {}).get("escaladas")) is not None:
        duvidas = int(numero(contador["escaladas"]))
    travados_total = None
    if chats["travados"] is not None:
        travados_total = sum(item["n"] for item in chats["travados"])
    sem = enviados is None and duvidas is None and travados_total is None
    if ok is not None and ruim is not None:
        resumo = f"{inteiro(ok)} ficaram satisfeitos e {inteiro(ruim)} reclamaram"
    elif enviados is not None:
        resumo = f"{inteiro(enviados)} pedidos de opinião enviados hoje"
    elif sem:
        resumo = "sem dado — ainda não deu para ler a qualidade de hoje"
    else:
        resumo = "Qualidade de hoje, com o que já deu para ler"
    return {
        "enviados": enviados,
        "responderam": responderam,
        "satisfeitos": ok,
        "reclamaram": ruim,
        "nota_motivo": motivo_nota,
        "duvidas": duvidas,
        "duvidas_frase": _frase_contagem(duvidas, "dúvida precisou de você hoje", "dúvidas precisaram de você hoje", "sem dado — não deu para ler as dúvidas"),
        "seguradas": travados_total,
        "seguradas_frase": _frase_contagem(travados_total, "mensagem foi segurada hoje", "mensagens foram seguradas hoje", "sem dado — não deu para ler as mensagens seguradas"),
        "motivos": chats["travados"],
        "erros": chats["erros"],
        "resumo": resumo,
        "sem_dado": sem,
    }


def _saude(fontes, agora) -> dict:
    cpu = fontes.get("cpu")
    ram = fontes.get("ram")
    disco = fontes.get("disco")
    robo = fontes.get("robo_ativo")
    backup = fontes.get("backup_em")
    calma = (fontes.get("log") or {}).get("calma")
    lento = (fontes.get("log") or {}).get("banco_lento")
    envios = (fontes.get("log") or {}).get("envios_min")
    fresco = (fontes.get("log") or {}).get("fresco")
    if not fresco:
        calma = lento = envios = None
    backup_txt = None
    backup_horas = None
    backup_tom = "sem"
    if backup is not None:
        delta = agora - backup.astimezone(TZ)
        backup_horas = delta.total_seconds() / 3600
        quando = backup.astimezone(TZ).strftime("%d/%m %H:%M")
        backup_txt = f"último arquivo em {quando} (há {inteiro(backup_horas)} h)"
        backup_tom = "ruim" if backup_horas >= 50 else "atencao" if backup_horas >= 26 else "ok"
    sem = cpu is None and robo is None
    if robo is True:
        resumo = "O robô está ligado"
    elif robo is False:
        resumo = "O robô está parado"
    elif cpu is not None:
        resumo = f"Computador em {inteiro(cpu)}% de uso"
    else:
        resumo = "sem dado — não consegui ver a saúde do servidor"
    return {
        "cpu": cpu,
        "ram": ram,
        "disco": disco,
        "robo": robo,
        "robo_motivo": None if robo is not None else "sem dado — não consegui ver se o robô está ligado",
        "envios_min": envios,
        "envios_frase": None if envios is None else f"cerca de {inteiro(envios)} mensagens por minuto",
        "envios_motivo": None if envios is not None else "sem dado — o ritmo de envio não está no registro recente",
        "calma": calma,
        "calma_frase": None if calma is None else ("O WhatsApp não pediu calma no último minuto" if calma == 0 else f"O WhatsApp pediu calma {inteiro(calma)} {'vez' if calma == 1 else 'vezes'} no último minuto"),
        "calma_motivo": None if calma is not None else "sem dado — não vi o aviso de limite do WhatsApp",
        "lento": lento,
        "lento_frase": None if lento is None else ("O banco respondeu no ritmo normal" if lento == 0 else f"O banco demorou a responder {inteiro(lento)} {'vez' if lento == 1 else 'vezes'} nos registros recentes"),
        "lento_motivo": None if lento is not None else "sem dado — não vi demora do banco nos registros recentes",
        "backup_txt": backup_txt,
        "backup_horas": backup_horas,
        "backup_tom": backup_tom,
        "backup_motivo": None if backup is not None else (fontes.get("backup_motivo") or "sem dado — não achei um backup automático"),
        "resumo": resumo,
        "sem_dado": sem,
    }


def _calor(vendas, dinheiro) -> dict:
    horas = vendas.get("leads_horas")
    titulo = "Quando chegam as conversas novas"
    if not horas or all(v in (None, 0) for v in horas):
        brutas = dinheiro.get("horas")
        if brutas:
            horas = []
            anterior = 0
            for valor in brutas:
                if valor is None:
                    horas.append(0)
                else:
                    horas.append(max(0, round(valor - anterior)))
                    anterior = valor
            titulo = "Quando o dinheiro entra"
        else:
            horas = None
    if horas is None:
        return {"horas": None, "frase": "sem dado — ainda não dá para ver o movimento do dia", "motivo": "sem dado — ainda não dá para ver o movimento do dia", "titulo": titulo}
    pico = max(range(len(horas)), key=lambda i: horas[i] or 0)
    if not any(horas):
        frase = "Ainda quase não houve movimento hoje"
    else:
        frase = f"O movimento mais forte foi às {pico:02d}h"
    return {"horas": horas, "frase": frase, "motivo": None, "titulo": titulo, "pico": pico}


def _linha(dinheiro, extras) -> list:
    eventos = list(dinheiro.get("eventos") or []) + list(extras or [])
    eventos.sort(key=lambda item: item.get("em") or "", reverse=True)
    vistos = set()
    saida = []
    for evento in eventos:
        ident = evento.get("id")
        if ident in vistos:
            continue
        vistos.add(ident)
        saida.append(evento)
        if len(saida) >= 14:
            break
    return saida


def _gaveta_dinheiro(dinheiro, motivo, linha) -> dict:
    if motivo:
        return {"motivo": motivo, "eventos": [], "excluidos": None}
    sem_separa = dinheiro["renov_valor"] is None
    return {
        "motivo": None,
        "total": dinheiro["total"],
        "qtd": dinheiro["qtd"],
        "ticket": dinheiro["ticket"],
        "ticket_frase": None if dinheiro["ticket"] is None else f"em média {reais(dinheiro['ticket'], centavos=True)} por pagamento",
        "renov_valor": dinheiro["renov_valor"],
        "renov_qtd": dinheiro["renov_qtd"],
        "renov_frase": (
            "Nenhuma renovação marcada à parte. O valor do dia já está na soma."
            if dinheiro["renov_qtd"] == 0 and dinheiro["qtd"]
            else _frase_reais(dinheiro["renov_valor"], dinheiro["renov_qtd"], "renovação", "renovações", "sem dado — o resumo de hoje ainda não trouxe as renovações", True)
        ),
        "novas_valor": dinheiro["novas_valor"],
        "novas_qtd": dinheiro["novas_qtd"],
        "novas_frase": _frase_reais(dinheiro["novas_valor"], dinheiro["novas_qtd"], "cliente novo", "clientes novos", "sem dado — não deu para separar o cliente novo da renovação"),
        "horas": dinheiro["horas"],
        "ontem_horas": dinheiro["ontem_horas"],
        "excluidos": dinheiro["excluidos"],
        "nota": "Não entra aqui o dinheiro da caixinha, o resgate nem a transferência entre contas da empresa.",
        "eventos": linha,
        "sem_separa": sem_separa,
    }


def _frase_reais(valor, qtd, um, varios, motivo, centavos=False):
    if valor is None or qtd is None:
        return motivo
    miolo = f"{reais(valor, centavos=centavos)} em {inteiro(qtd or 0)} {um if (qtd or 0) == 1 else varios}"
    return miolo


def _frase_contagem(valor, um, varios, motivo):
    if valor is None:
        return motivo
    n = int(round(valor))
    return f"{inteiro(n)} {um if n == 1 else varios}"


def _funil_cache(contador) -> dict | None:
    if not contador:
        return None
    funil = contador.get("funil")
    if isinstance(funil, dict):
        chegou = _int_chave(funil, "lead", "leads", "chegou")
        teste = _int_chave(funil, "teste", "testes")
        precos = _int_chave(funil, "tabela", "precos", "preços")
        pagou = _int_chave(funil, "pagou", "pago")
    elif isinstance(funil, list) and len(funil) >= 4:
        chegou, teste, precos, pagou = (int(numero(x)) if numero(x) is not None else None for x in funil[:4])
    else:
        return None
    if all(v is None for v in (chegou, teste, precos, pagou)):
        return None
    return {"chegou": chegou, "teste": teste, "precos": precos, "pagou": pagou}


def _int_chave(mapa: dict, *chaves):
    for chave in chaves:
        if chave in mapa and numero(mapa[chave]) is not None:
            return int(round(numero(mapa[chave])))
    return None


def _rotular_mapa(mapa, rotulo) -> list | None:
    if mapa is None:
        return None
    itens = [{"id": chave, "nome": rotulo(chave), "n": int(valor)} for chave, valor in mapa.items() if valor]
    itens.sort(key=lambda item: item["n"], reverse=True)
    return itens


def _agrupar_motivos(linhas, mapa_motivos) -> list | None:
    if linhas is None:
        return None
    grupos: dict[str, int] = {}
    for linha in linhas:
        bruto = str(linha.get("motivo") or linha.get("gatilho") or "").strip()
        nome = mapa_motivos.get(bruto.casefold())
        if not nome:
            nome = "sem descrição" if not bruto or parece_codigo_interno(bruto) else bruto[:48]
            if any(pedaço in bruto.casefold() for pedaço in ("r639", "sombra")):
                nome = "sem descrição"
        grupos[nome] = grupos.get(nome, 0) + int(linha.get("n") or 0)
    saida = [{"nome": nome, "n": n} for nome, n in grupos.items() if n]
    saida.sort(key=lambda item: item["n"], reverse=True)
    return saida


def _agrupar_erros(linhas) -> list | None:
    if linhas is None:
        return None
    grupos: dict[str, int] = {}
    for linha in linhas:
        bruto = str(linha.get("tipo") or "").strip()
        if not bruto or parece_codigo_interno(bruto) or "r639" in bruto.casefold():
            nome = "sem descrição"
        elif len(bruto) > 60:
            nome = bruto[:57].rsplit(" ", 1)[0] + "…"
        else:
            nome = bruto
        grupos[nome] = grupos.get(nome, 0) + int(linha.get("n") or 0)
    saida = [{"nome": nome, "n": n} for nome, n in grupos.items() if n]
    saida.sort(key=lambda item: item["n"], reverse=True)
    return saida[:6]


def _linhas_telegram(contador) -> list | None:
    if not contador:
        return None
    linhas = []
    dinheiro = numero(contador.get("dinheiro"))
    if dinheiro is not None:
        linhas.append(f"Dinheiro no resumo: {reais(float(dinheiro))}.")
    testes = numero(contador.get("testes"))
    if testes is not None:
        linhas.append(f"Testes no resumo: {inteiro(testes)}.")
    leads = numero(contador.get("leads"))
    if leads is not None:
        linhas.append(f"Conversas novas no resumo: {inteiro(leads)}.")
    funil = _funil_cache(contador)
    if funil:
        pedacos = []
        for chave, rotulo in (("chegou", "chegou"), ("teste", "teste"), ("precos", "preços"), ("pagou", "pagou")):
            if funil[chave] is not None:
                pedacos.append(f"{rotulo} {inteiro(funil[chave])}")
        if pedacos:
            linhas.append("Caminho do cliente no resumo: " + ", ".join(pedacos) + ".")
    fb = contador.get("feedback") if isinstance(contador.get("feedback"), dict) else None
    if fb:
        partes = []
        for chave, rotulo in (("enviados", "enviados"), ("responderam", "responderam"), ("satisfeitos", "satisfeitos"), ("reclamaram", "reclamaram")):
            n = _int_chave(fb, chave)
            if n is not None:
                partes.append(f"{inteiro(n)} {rotulo}")
        if partes:
            linhas.append("Opiniões no resumo: " + ", ".join(partes) + ".")
    venc = contador.get("vencimentos") if isinstance(contador.get("vencimentos"), dict) else None
    if venc:
        partes = []
        for chave, rotulo in (("hoje", "hoje"), ("amanha", "amanhã"), ("vencidos", "vencidos")):
            n = _int_chave(venc, chave)
            if n is not None:
                partes.append(f"{inteiro(n)} {rotulo}")
        if partes:
            linhas.append("Vencimentos no resumo: " + ", ".join(partes) + ".")
    avisos = numero(contador.get("avisos"))
    if avisos is not None:
        linhas.append(f"Avisos enviados no resumo: {inteiro(avisos)}.")
    erros = numero(contador.get("erros"))
    if erros is not None:
        linhas.append(f"Erros do robô no resumo: {inteiro(erros)}.")
    return linhas or None
