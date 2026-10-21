"""Números de exemplo para pré-visualização. Só entra com PAINEL_DEMO=1.

Não é fonte de produção. Cada pacote traz demo=True para a tela avisar o Gustavo.
Os valores batem entre as abas (o mesmo dia, os mesmos painéis, o mesmo ritmo).
"""

from __future__ import annotations

from datetime import timedelta

from app.tempo import agora


CAP_ENVIO = 240


def _hora() -> int:
    return agora().hour


def _curva(hora: int) -> list[int]:
    """Pagamentos por hora, com o pico da tarde que a operação já conhece."""
    base = [0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 4, 5, 7, 8, 9, 11, 10, 8, 6, 4, 2, 1]
    return [n if i <= hora else 0 for i, n in enumerate(base)]


def _reais(ns: list[int]) -> list[float]:
    ticket = [0, 0, 0, 0, 0, 0, 30, 35, 40, 45, 40, 50, 35, 40, 45, 50, 40, 55, 45, 40, 35, 30, 40, 30]
    return [round(n * ticket[i], 2) for i, n in enumerate(ns)]


def _resumo(ns: list[int], rs: list[float]) -> dict:
    n = sum(ns)
    reais = round(sum(rs), 2)
    novas = max(1, n // 3) if n else 0
    return {
        "n": n,
        "reais": reais,
        "novas": novas,
        "novas_reais": round(reais * 0.38, 2),
        "ticket": round(reais / n, 2) if n else None,
    }


def vendas_p11(periodo: str = "hoje") -> dict:
    momento = agora()
    hora = momento.hour if periodo == "hoje" else 23
    ns = _curva(hora if periodo != "7d" else 23)
    if periodo == "7d":
        rotulos = [(momento - timedelta(days=6 - i)).strftime("%d/%m") for i in range(7)]
        n = [18, 22, 15, 27, 19, 24, sum(ns)]
        reais = [round(x * 42, 2) for x in n]
        barras = {"tipo": "dia", "rotulos": rotulos, "n": n, "reais": reais}
        res = _resumo(n, reais)
    else:
        reais = _reais(ns)
        barras = {
            "tipo": "hora",
            "rotulos": [f"{i}h" for i in range(24)],
            "n": ns,
            "reais": reais,
            "n_dia_anterior": [max(0, n - (1 if i % 2 == 0 else 0)) for i, n in enumerate(_curva(23))],
            "hora_agora": hora if periodo == "hoje" else 24,
        }
        res = _resumo(ns, reais)
    ontem = {"n": max(0, res["n"] - 4), "reais": round(res["reais"] * 0.86, 2), "novas": max(0, res["novas"] - 1)}
    funil = {
        "periodo": periodo,
        "total": {"leads": 86, "teste": 41, "pagou": 19, "cadastro": 14, "cadastro_sem_dado": 2},
        "etapas": [
            ("leads", "Lead chegou"),
            ("teste", "Ganhou teste"),
            ("pagou", "Pagou"),
            ("cadastro", "Cadastro achado"),
        ],
        "por_numero": [
            {"numero": "3619", "leads": 48, "teste": 24, "pagou": 11, "cadastro": 8},
            {"numero": "0837", "leads": 27, "teste": 12, "pagou": 6, "cadastro": 4},
            {"numero": "3166", "leads": 11, "teste": 5, "pagou": 2, "cadastro": 2},
        ],
        "maior_vazamento": "Lead chegou → Ganhou teste",
        "taxa_vazamento": 0.477,
        "erro": None,
        "nota": "Exemplo de demonstração. Na VPS o funil sai do webhook e do ledger.",
    }
    return {
        "ok": True,
        "demo": True,
        "periodo": periodo if periodo in ("hoje", "ontem", "7d") else "hoje",
        "agora": momento.isoformat(timespec="minutes"),
        "resumo": res,
        "comparacao": {
            "ontem": ontem,
            "semana_passada": {"n": max(0, res["n"] - 7), "reais": round(res["reais"] * 0.74, 2), "novas": 4},
            "media_7d": {"n": round(res["n"] * 0.9, 1), "reais": round(res["reais"] * 0.9, 2)},
            "ontem_dia_todo": {"n": ontem["n"] + 6, "reais": round(ontem["reais"] + 240, 2), "novas": ontem["novas"] + 2},
            "anteontem": {"n": 21, "reais": 890.0, "novas": 6},
            "7d_anteriores": {"n": 140, "reais": 6120.0, "novas": 40},
        },
        "por_numero": [
            {"numero": "3619", "n": 11, "reais": 520.0, "novas": 4, "ticket": 47.27},
            {"numero": "0837", "n": 6, "reais": 280.0, "novas": 2, "ticket": 46.67},
            {"numero": "3166", "n": 2, "reais": 90.0, "novas": 1, "ticket": 45.0},
        ],
        "barras": barras,
        "planos": [("30 dias", 12), ("60 dias", 5), ("90 dias", 2)],
        "ultimas": [
            {"hora": "18:12", "valor": 40.0, "numero": "3619", "nova": True, "plano": "30 dias"},
            {"hora": "17:48", "valor": 70.0, "numero": "0837", "nova": False, "plano": "60 dias"},
            {"hora": "17:05", "valor": 40.0, "numero": "3619", "nova": False, "plano": "30 dias"},
        ],
        "sem_valor": 0,
        "funil": funil,
        "fonte": "demonstração — não é o ledger da VPS",
    }


def vendas_dia() -> dict:
    momento = agora()
    return {
        "ok": True,
        "demo": True,
        "erro": None,
        "dia": momento.date().isoformat(),
        "novas": {"n": 7, "reais": 310.0},
        "renovacoes": {"n": 12, "reais": 580.0, "sem_valor": 0},
        "total": {"n": 19, "reais": 890.0},
        "por_instancia": [
            {"instancia": "3619", "n": 4, "reais": 180.0},
            {"instancia": "0837", "n": 2, "reais": 90.0},
            {"instancia": "3166", "n": 1, "reais": 40.0},
        ],
        "lista": [
            {"pix": "18:10", "hora": "18:12", "telefone": "final 9433", "valor": 40.0, "tipo": "venda", "instancia": "3619"},
            {"pix": "17:40", "hora": "17:48", "telefone": "final 1204", "valor": 70.0, "tipo": "renovacao", "instancia": "0837"},
            {"pix": "17:01", "hora": "17:05", "telefone": "final 7781", "valor": 40.0, "tipo": "renovacao", "instancia": "3619"},
            {"pix": "16:22", "hora": "16:30", "telefone": "final 3344", "valor": 40.0, "tipo": "venda", "instancia": "3166"},
            {"pix": "15:10", "hora": "15:18", "telefone": "final 5566", "valor": 100.0, "tipo": "renovacao", "instancia": "0837"},
        ],
        "marcador_idade_s": 40,
        "gerado": momento.strftime("%H:%M:%S"),
    }


def saude() -> dict:
    momento = agora()
    return {
        "ok": True,
        "demo": True,
        "agora": momento.isoformat(timespec="seconds"),
        "servicos": [
            {"nome": "mnrobo", "rotulo": "Robô (WhatsApp)", "estado": "active"},
            {"nome": "mnrobo-fiscal", "rotulo": "Fiscal de comprovante", "estado": "active"},
            {"nome": "vigia_comprovante", "rotulo": "Vigia de comprovante (cron 5 min)", "estado": "active", "detalhe": "última rodada há 3 min"},
            {"nome": "mnrobo-receiver", "rotulo": "Receptor de webhook", "estado": "active", "detalhe": "último webhook há 1 min"},
            {"nome": "mnbox-vigia", "rotulo": "Vigia do túnel", "estado": "active"},
        ],
        "todos_ok": True,
        "ia": {
            "hoje_usd": 4.8,
            "hoje_chamadas": 320,
            "ontem_usd": 5.1,
            "media_7d_usd": 4.6,
            "modelos_hoje": [("gpt", 4.8)],
            "fonte": "demonstração",
            "saldo": {"restante_usd": 62.4, "carregado_usd": 100, "em": "2026-10-01T12:00", "dias_restantes": 13.5},
        },
        "fiscal": {
            "fast_wh_mediana_s": 6,
            "fast_wh_media_s": 8,
            "fast_wh_ok": 40,
            "fast_wh_falhou": 2,
            "renov_mediana_min": 3.5,
            "renov_n": 12,
            "ciclo": {"hora": momento.strftime("%H:%M"), "seg": 9},
            "fila_alerta": None,
            "manual_hoje": 1,
            "parados_hoje": 1,
        },
        "robo": {"hora": momento.strftime("%H:%M"), "pendentes": "4", "aguardando": "3", "fila": "7", "ocupadas": "2"},
    }


def alertas() -> dict:
    momento = agora()
    ts = momento.isoformat(timespec="seconds")
    return {
        "ok": True,
        "demo": True,
        "agora": ts,
        "alertas": [
            {
                "id": "demo-venda",
                "ts": ts,
                "tipo": "venda",
                "nivel": "bom",
                "titulo": "Venda nova R$ 40,00",
                "detalhe": "3619 · plano 30 dias · final 9433",
            },
            {
                "id": "demo-parado",
                "ts": (momento - timedelta(minutes=12)).isoformat(timespec="seconds"),
                "tipo": "parado",
                "nivel": "atencao",
                "titulo": "Comprovante parado há 12 min",
                "detalhe": "0837 · final 1204",
            },
        ],
    }


def vivo() -> dict:
    momento = agora()
    serie = []
    for i in range(120):
        rece = 1 if i % 5 == 0 else 0
        envi = 1 if i % 4 == 0 else 0
        serie.append([rece, envi])
    minutos = []
    for i in range(60):
        minutos.append([4 + (i % 5), 6 + (i % 4)])
    return {
        "ok": True,
        "demo": True,
        "hora": momento.isoformat(timespec="seconds"),
        "fonte": {"recebido": "demo", "enviado": "demo", "erro_recebido": None, "erro_enviado": None, "api_datacrazy": False},
        "geral": {
            "msg_s_1": 1,
            "rec_s_1": 0,
            "env_s_1": 1,
            "msg_s_10": 0.8,
            "msg_s_60": 0.35,
            "rec_s_60": 0.14,
            "env_s_60": 0.21,
            "msg_min_15": 18.4,
            "rec_min_15": 8.2,
            "env_min_15": 10.2,
            "msg_min_hoje": 16.0,
            "rec_hoje": 2410,
            "env_hoje": 3180,
            "nao_saiu_hoje": 12,
            "pico_s_60": 3,
        },
        "serie_120s": serie,
        "serie_60min": minutos,
        "numeros": [
            {
                "numero": "3619",
                "rec_hoje": 980,
                "env_hoje": 1240,
                "nao_saiu_hoje": 4,
                "rec_s_60": 0.08,
                "env_s_60": 0.11,
                "rec_min_15": 4.1,
                "env_min_15": 5.2,
                "rec_10s": 1,
                "env_10s": 2,
                "rec_1s": 0,
                "env_1s": 1,
                "rec_tipos": {"texto": 20, "foto": 4, "audio": 2},
                "env_tipos": {"texto": 30},
                "clientes_hoje": 86,
                "ult_rec_ha_s": 8,
                "ult_env_ha_s": 3,
            },
            {
                "numero": "0837",
                "rec_hoje": 640,
                "env_hoje": 810,
                "nao_saiu_hoje": 3,
                "rec_s_60": 0.04,
                "env_s_60": 0.06,
                "rec_min_15": 2.4,
                "env_min_15": 3.1,
                "rec_10s": 0,
                "env_10s": 1,
                "rec_1s": 0,
                "env_1s": 0,
                "rec_tipos": {"texto": 12, "audio": 3},
                "env_tipos": {"texto": 16},
                "clientes_hoje": 54,
                "ult_rec_ha_s": 20,
                "ult_env_ha_s": 11,
            },
        ],
    }


def ativos() -> dict:
    momento = agora()
    paineis = [
        {"canon": "P1", "ok": True, "outro": False, "vencido": 40, "v2": {"sigma": 820, "real": 760, "sem_pag_curto": 40, "sem_pag_longo": 20, "teste": 18}},
        {"canon": "P2", "ok": True, "outro": False, "vencido": 28, "v2": {"sigma": 640, "real": 590, "sem_pag_curto": 30, "sem_pag_longo": 20, "teste": 12}},
        {"canon": "P3", "ok": False, "outro": False, "vencido": None, "desligado": True, "v2": {"sigma": None, "real": None, "sem_pag_curto": None, "sem_pag_longo": None, "teste": None}},
        {"canon": "P4", "ok": True, "outro": False, "vencido": 18, "v2": {"sigma": 410, "real": 380, "sem_pag_curto": 18, "sem_pag_longo": 12, "teste": 9}},
        {"canon": "P5", "ok": True, "outro": False, "vencido": 15, "v2": {"sigma": 390, "real": 360, "sem_pag_curto": 16, "sem_pag_longo": 14, "teste": 7}},
        {"canon": "P6", "ok": True, "outro": False, "vencido": 22, "v2": {"sigma": 510, "real": 470, "sem_pag_curto": 24, "sem_pag_longo": 16, "teste": 11}},
        {"canon": "ALPHA", "ok": True, "outro": True, "vencido": 4, "v2": {"sigma": 80, "real": 70, "sem_pag_curto": 6, "sem_pag_longo": 4, "teste": 2}},
        {"canon": "PROMO", "ok": True, "outro": True, "vencido": 6, "v2": {"sigma": 120, "real": 100, "sem_pag_curto": 10, "sem_pag_longo": 10, "teste": 5}},
    ]
    return {
        "ok": True,
        "demo": True,
        "versao": 2,
        "gerado": int(momento.timestamp()),
        "dias_curto": 35,
        "total_sigma": 2770,
        "total_reais": 2560,
        "total_testes": 57,
        "total_sem_pag_curto": 128,
        "total_sem_pag_longo": 82,
        "paineis": paineis,
        "barrado": False,
    }


def semana() -> dict:
    momento = agora()
    hoje = momento.date()
    segunda = hoje - timedelta(days=hoje.weekday())
    atual = [(segunda + timedelta(days=i)).isoformat() for i in range(7)]
    anterior = [(segunda - timedelta(days=7 - i)).isoformat() for i in range(7)]
    instancias = ["3619", "0837", "3166"]
    dados: dict[str, dict] = {}
    for inst, peso in (("3619", 1.0), ("0837", 0.6), ("3166", 0.25)):
        dados[inst] = {}
        for i, dia in enumerate(anterior + atual):
            rec = int((80 + i * 7) * peso)
            env = int(rec * 1.25)
            dados[inst][dia] = [rec, env]
    return {
        "ok": True,
        "demo": True,
        "hoje": hoje.isoformat(),
        "dias": ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"],
        "datas": {"atual": atual, "anterior": anterior},
        "instancias": instancias,
        "dados": dados,
        "cobertura": {
            "recebidas_desde": anterior[0],
            "enviadas_desde": anterior[0],
            "recebidas_primeiro": anterior[0] + "T00:00",
            "enviadas_primeiro": anterior[0] + "T00:00",
        },
    }


def atendidos() -> dict:
    momento = agora()
    return {
        "ok": True,
        "demo": True,
        "total": 214,
        "ontem": {"total": 198},
        "atualizado": momento.strftime("%H:%M"),
        "instancias": [
            {"inst": "3619", "n": 96, "ontem": 88},
            {"inst": "0837", "n": 74, "ontem": 70},
            {"inst": "3166", "n": 44, "ontem": 40},
        ],
    }


def ranking() -> dict:
    def app(ok7, n7, ok30, n30, hist_ok, hist_n, visto7=0):
        return {
            "ok_7d": ok7,
            "n_7d": n7,
            "ok_30d": ok30,
            "n_30d": n30,
            "hist_ok": hist_ok,
            "hist_n": hist_n,
            "visto_7d": visto7 or n7,
            "visto_30d": n30,
        }

    cards = [
        {
            "nome": "Samsung",
            "fichas_7d": 42,
            "fichas_30d": 160,
            "ordem": ["max", "brasil", "ibo"],
            "apps": {
                "max": app(28, 34, 90, 120, 210, 280),
                "brasil": app(8, 18, 40, 70, 90, 160),
                "ibo": app(6, 12, 22, 40, 40, 80),
            },
            "proibidos": [],
        },
        {
            "nome": "LG",
            "fichas_7d": 30,
            "fichas_30d": 110,
            "ordem": ["utra", "brasil", "max"],
            "apps": {
                "utra": app(11, 22, 40, 80, 70, 150),
                "brasil": app(14, 18, 48, 60, 80, 100),
                "max": app(4, 8, 12, 20, 20, 40),
            },
            "proibidos": [{"app": "xciptv", "nome": "XCIPTV", "desde": "01/10", "fichas_desde": 6}],
        },
        {
            "nome": "Fire Stick",
            "fichas_7d": 24,
            "fichas_30d": 90,
            "ordem": ["ibo", "max", "downloader"],
            "apps": {
                "ibo": app(16, 20, 50, 64, 90, 120),
                "max": app(6, 10, 18, 30, 30, 50),
                "downloader": app(2, 4, 8, 14, 12, 22),
            },
            "proibidos": [],
        },
    ]
    return {
        "ok": True,
        "demo": True,
        "periodo": "7d",
        "quando": agora().timestamp(),
        "fonte": "demonstração",
        "min_casos": 10,
        "linhas": [],
        "ordens": {},
        "fichas": {
            "visual": "novo",
            "gerado_em": agora().isoformat(timespec="minutes"),
            "min_n_ordem": 10,
            "geral": {"lidas": 360, "com_app": 340, "sem_aparelho": 12, "varios_aparelhos": 4, "app_sem_aparelho_claro": 6},
            "regras_fonte": {"arquivo": "regras (exemplo)", "mtime": "2026-10-18"},
            "cards": cards,
            "aparelhos": {},
        },
    }


def cliente(q: str) -> dict:
    return {
        "ok": True,
        "demo": True,
        "frase": f"Achei um exemplo para {q or 'este cliente'}. Nada aqui mexe no Sigma.",
        "usuario": "cliente.exemplo",
        "plano": "30 dias",
        "vencimento": "20/11/2026",
        "telas": 1,
        "app": "Max Player",
        "linha": "3619",
        "ultima": "Pediu o teste hoje de manhã.",
        "protegido": False,
        "pausado": False,
        "painel_sugerido": "principal",
    }


def acao(corpo: dict) -> dict:
    nomes = {
        "teste": "criar o teste de 2 horas",
        "renovar": f"renovar {corpo.get('dias') or 30} dias",
        "telas": "liberar as telas",
        "pausar": "pausar o robô só para este cliente",
        "soltar": "soltar o robô para este cliente",
    }
    frase_acao = nomes.get(str(corpo.get("acao") or ""), "fazer esta ação")
    ficha = cliente(str(corpo.get("q") or ""))
    if not corpo.get("confirmar"):
        return {
            "ok": False,
            "demo": True,
            "precisa_confirmar": True,
            "frase": f"Demonstração: confirmar para {frase_acao}? Na VPS isso mexe no cliente de verdade. Aqui não mexe.",
            "ficha": ficha,
        }
    return {
        "ok": True,
        "demo": True,
        "frase": f"Demonstração: {frase_acao} não foi enviado. O botão está no lugar e a confirmação funcionou.",
        "ficha": ficha,
    }


def graficos() -> dict:
    v = vendas_p11("hoje")
    barras = v["barras"]
    vivo_p = vivo()
    minutos = vivo_p["serie_60min"]
    momento = agora()
    rotulos_min = []
    for i in range(59, -1, -1):
        t = momento - timedelta(minutes=i)
        rotulos_min.append(t.strftime("%H:%M"))
    envio_serie = [120 + (i % 7) * 8 for i in range(60)]
    envio_serie[-1] = 186
    erros = [0, 1, 0, 0, 2, 0, 1, 0, 0, 0, 1, 0]
    return {
        "ok": True,
        "demo": True,
        "cap_envio_min": CAP_ENVIO,
        "vendas_hora": {
            "rotulos": barras["rotulos"],
            "n": barras["n"],
            "reais": barras["reais"],
            "hora_agora": barras.get("hora_agora"),
            "fonte": "mesmo apurado da aba Vendas",
        },
        "mensagens_min": {
            "rotulos": rotulos_min,
            "recebidas": [p[0] for p in minutos],
            "enviadas": [p[1] for p in minutos],
            "fonte": "registro do webhook",
        },
        "funil": {
            "etapas": [
                {"nome": "Lead chegou", "n": 86},
                {"nome": "Ganhou teste", "n": 41},
                {"nome": "Pagou", "n": 19},
                {"nome": "Cadastro achado", "n": 14},
            ],
            "vazamento": "Lead chegou → Ganhou teste",
            "fonte": "funil do lead",
        },
        "robo": {
            "servicos": [
                {"nome": "Robô", "ok": True},
                {"nome": "Fiscal", "ok": True},
                {"nome": "Receptor", "ok": True},
                {"nome": "Vigia", "ok": True},
            ],
            "erros_hora": erros,
            "rotulos_hora": [f"{(momento.hour - 11 + i) % 24}h" for i in range(12)],
            "fila": 4,
            "ocupadas": 2,
            "falhas_fiscal": 2,
            "fonte": "saúde dos serviços + alertas",
        },
        "ativos": {
            "paineis": [
                {"id": "P1", "n": 820, "ativo": True},
                {"id": "P2", "n": 640, "ativo": True},
                {"id": "P3", "n": None, "ativo": False, "nota": "desligado"},
                {"id": "P4", "n": 410, "ativo": True},
                {"id": "P5", "n": 390, "ativo": True},
                {"id": "P6", "n": 510, "ativo": True},
            ],
            "fonte": "ativos reais",
        },
        "envio": {
            "agora": 186,
            "teto": CAP_ENVIO,
            "serie": envio_serie,
            "rotulos": rotulos_min,
            "fonte": "ritmo de envio do robô",
        },
    }
