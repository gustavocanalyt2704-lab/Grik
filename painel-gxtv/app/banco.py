"""Uma conexão, só leitura, com tempo máximo de 15 segundos."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta

from app.assuntos import aparelho_de, app_de, assuntos_de, atendente_de, rotulo_assunto
from app.mascarar import mascarar_telefone
from app.tempo import TZ

_FECHADOS = {"resolvido", "resolvida", "fechado", "fechada", "encerrado", "encerrada", "finalizado", "finalizada"}


class Banco:
    def __init__(self, dsn: str | None, timeout_ms: int = 15000):
        self.dsn = dsn
        self.timeout_ms = max(1000, int(timeout_ms))
        self.conn = None
        self._trava = threading.Lock()
        self.motivo = None if dsn else "sem dado — não encontrei a configuração do banco"

    def fechar(self):
        with self._trava:
            self._fechar_sem_trava()

    def _fechar_sem_trava(self):
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    def _garantir(self) -> bool:
        """Abre a conexão se precisar. Quem chama já está com self._trava."""
        if not self.dsn:
            self.motivo = "sem dado — não encontrei a configuração do banco"
            return False
        if self.conn is not None and not getattr(self.conn, "closed", False):
            return True
        try:
            import psycopg
        except ImportError:
            self.motivo = "sem dado — o leitor do banco não está instalado"
            return False
        try:
            self.conn = psycopg.connect(
                self.dsn,
                autocommit=True,
                connect_timeout=8,
                application_name="painel-gxtv",
                options=f"-c statement_timeout={self.timeout_ms} -c TimeZone=America/Bahia",
            )
            self.conn.execute("SET TimeZone TO 'America/Bahia'")
            self.conn.execute(f"SET statement_timeout = {int(self.timeout_ms)}")
            self.conn.execute("SET default_transaction_read_only = on")
            self.motivo = None
            return True
        except Exception as exc:
            self._fechar_sem_trava()
            self.motivo = "sem dado — não consegui falar com o banco"
            try:
                from app.logonce import avisar
                avisar(
                    "banco-conexao",
                    "painel sem conexão com o espelho (%s)",
                    type(exc).__name__,
                    intervalo=300,
                )
            except Exception:
                pass
            return False

    def linhas(self, sql: str, params: dict | None = None):
        with self._trava:
            if not self._garantir():
                return None
            try:
                with self.conn.cursor() as cur:
                    cur.execute(sql, params or {})
                    if cur.description is None:
                        return []
                    colunas = [c.name for c in cur.description]
                    return [dict(zip(colunas, linha)) for linha in cur.fetchall()]
            except Exception as exc:
                # QueryCanceled deixa a conexão viva (autocommit). Fechar aqui
                # devolve a vaga do pooler e a próxima leitura não consegue outra.
                nome = type(exc).__name__
                try:
                    from app.logonce import avisar
                    cabeca = " ".join((sql or "").split())[:70]
                    avisar(
                        "banco-sql-" + cabeca[:40],
                        "consulta do painel falhou (%s): %s",
                        nome,
                        cabeca,
                        intervalo=300,
                    )
                except Exception:
                    pass
                if nome in {"OperationalError", "InterfaceError", "ConnectionTimeout"} or self.conn is None or getattr(self.conn, "closed", True):
                    self._fechar_sem_trava()
                return None

    def coletar(self, agora: datetime) -> dict:
        hoje = _inicio(agora)
        ontem = _inicio(agora, 1)
        corte = agora.astimezone(TZ) - timedelta(days=1)
        base = {"ok": False, "motivo": self.motivo}
        with self._trava:
            abriu = self._garantir()
            if not abriu:
                base["motivo"] = self.motivo
        if not abriu:
            return _vazio(base["motivo"])

        # received_at no webhook não tem índice utilizável daqui: a contagem
        # estoura o tempo e segura a conexão das métricas. Sem dado, de propósito.
        leads = None
        leads_horas = None
        testes = self.linhas(_SQL_TESTES, {"hoje": hoje})
        feedback = self.linhas(_SQL_FEEDBACK, {"hoje": hoje})
        duvidas = self.linhas(_SQL_DUVIDAS, {"hoje": hoje})
        travados = self.linhas(_SQL_TRAVADOS, {"hoje": hoje})
        erros = self.linhas(_SQL_ERROS, {"hoje": hoje})
        comprovantes = self.linhas(_SQL_COMPROVANTES)
        envios = self.linhas(_SQL_ENVIOS, {"hoje": hoje})
        avisos = self.linhas(_SQL_AVISOS, {"hoje": hoje})
        abertas = self.linhas(_SQL_ABERTAS)
        status = self.linhas(_SQL_STATUS, {"hoje": hoje})
        # Sem índice em mensagens.ts_origem: estas consultas varrem a tabela
        # inteira, estouram o tempo e derrubam a única conexão do painel.
        # A aba Métricas cobre atendimento e apps pelo espelho, em lotes.
        atendentes = None
        assuntos = None
        tem_instancia = bool(self.linhas(_SQL_TEM_INSTANCIA))
        candidatos = self.linhas(_SQL_ESPERA_INST if tem_instancia else _SQL_ESPERA)
        recentes = self.linhas(_SQL_RECENTES_INST if tem_instancia else _SQL_RECENTES)
        pares = None  # sem dado: varreria mensagens por ts_origem
        vence = None  # sem dado: o vencimento exibido vem do cadastro Sigma

        motivo = self.motivo
        saida = _vazio(motivo)
        saida["ok"] = any(item is not None for item in (leads, abertas, feedback, atendentes))
        if leads:
            saida["leads_hoje"] = int(leads[0]["hoje"] or 0)
            saida["leads_ontem"] = int(leads[0]["ontem"] or 0)
        if leads_horas is not None:
            horas = [0] * 24
            for linha in leads_horas:
                hora = int(linha["hora"])
                if 0 <= hora <= 23:
                    horas[hora] = int(linha["n"] or 0)
            saida["leads_horas"] = horas
        if testes is not None:
            saida["testes"] = int(testes[0]["n"] or 0)
        if feedback:
            linha = feedback[0]
            sem = int(linha["sem_classe"] or 0)
            enviados = int(linha["enviados"] or 0)
            saida["feedback"] = {
                "enviados": enviados,
                "responderam": int(linha["responderam"] or 0),
                "ok": int(linha["ok"] or 0),
                "ruim": int(linha["ruim"] or 0),
                "sem_classe": sem == enviados and enviados > 0,
            }
        if duvidas is not None:
            saida["duvidas"] = int(duvidas[0]["n"] or 0)
        if travados is not None:
            saida["travados"] = [{"motivo": linha["gatilho"] or "", "n": int(linha["n"] or 0)} for linha in travados]
        if erros is not None:
            saida["erros"] = [{"tipo": linha["tipo"] or "", "n": int(linha["n"] or 0)} for linha in erros]
        if comprovantes is not None:
            saida["comprovantes"] = int(comprovantes[0]["n"] or 0)
        if envios is not None:
            saida["envios"] = int(envios[0]["n"] or 0)
        if avisos is not None:
            saida["avisos"] = int(avisos[0]["n"] or 0)
        if abertas is not None:
            saida["abertas"] = int(abertas[0]["n"] or 0)
        if status is not None:
            fechados = 0
            conhecidos = False
            for linha in status:
                nome = str(linha["status_caso"] or "").strip().casefold()
                if nome in _FECHADOS:
                    conhecidos = True
                    fechados += int(linha["n"] or 0)
            if conhecidos:
                saida["resolvidas"] = fechados
            else:
                saida["resolvidas"] = None
                saida["resolvidas_motivo"] = "sem dado — as conversas não têm a marca de resolvida"
        if atendentes is not None:
            saida["atendentes"] = _por_atendente(atendentes)
        if assuntos is not None:
            saida["assuntos"], saida["apps"], saida["aparelhos"] = _assuntos(assuntos)
            if saida["apps"]:
                saida["origem_aparelho"] = "conversas de hoje"
        espera, lista = _espera(candidatos, self, agora)
        if candidatos is not None:
            saida["esperando"] = espera
            saida["esperando_lista"] = lista
        if recentes is not None:
            saida["recentes"] = _recentes(recentes, self, agora)
        if pares is not None:
            saida["tmr"], saida["resp_min"], saida["recv_min"] = _ritmo(pares, agora)
        if vence is not None:
            saida["vence_avisos"] = _vence(vence)
        return saida


def _whats(valor) -> str:
    if not valor:
        return "sem número"
    from app.metricas import _limpa_inst

    return _limpa_inst(valor) or "sem número"


def _vazio(motivo):
    return {
        "ok": False,
        "motivo": motivo,
        "leads_hoje": None,
        "leads_ontem": None,
        "leads_horas": None,
        "testes": None,
        "testes_horas": None,
        "feedback": None,
        "duvidas": None,
        "travados": None,
        "erros": None,
        "comprovantes": None,
        "envios": None,
        "avisos": None,
        "abertas": None,
        "resolvidas": None,
        "resolvidas_motivo": motivo,
        "atendentes": None,
        "assuntos": None,
        "apps": None,
        "aparelhos": None,
        "esperando": None,
        "esperando_lista": None,
        "recentes": None,
        "tmr": None,
        "resp_min": None,
        "recv_min": None,
        "vence_avisos": None,
    }


def _inicio(agora: datetime, dias: int = 0) -> datetime:
    local = agora.astimezone(TZ)
    dia = local.date() - timedelta(days=dias)
    return datetime(dia.year, dia.month, dia.day, tzinfo=TZ)


def _vence(linhas: list[dict]) -> dict:
    """Avisos automáticos de vencimento mandados hoje (modelos "P2 VENCE HOJE" etc.). Telefone só para casar com renovação."""
    saida = {"hoje": {}, "amanha": {}, "dois": {}}
    for linha in linhas:
        classe = linha.get("classe")
        if classe not in saida:
            continue
        saida[classe][linha["cid"]] = {"painel": str(linha.get("painel") or "").upper(), "telefone": linha.get("telefone")}
    return saida


def _por_atendente(linhas: list[dict]) -> dict:
    saida = {}
    for linha in linhas:
        if str(linha.get("autor_tipo") or "").casefold() == "sistema":
            continue  # aviso automático (modelo de cobrança), não é atendimento
        codigo = atendente_de(linha.get("autor_nome"), linha.get("autor_tipo"))
        if not codigo or str(linha.get("direcao") or "") != "saida":
            continue
        item = saida.setdefault(codigo, {"conversas": 0, "mensagens": 0, "conversas_ontem": 0, "mensagens_ontem": 0})
        if linha.get("dia") == "hoje":
            item["conversas"] += int(linha["conversas"] or 0)
            item["mensagens"] += int(linha["msgs"] or 0)
        else:
            item["conversas_ontem"] += int(linha["conversas"] or 0)
            item["mensagens_ontem"] += int(linha["msgs"] or 0)
    return saida


def _assuntos(linhas: list[dict]) -> tuple[dict, dict | None, dict | None]:
    assuntos: dict[str, int] = {}
    apps: dict[str, int] = {}
    aparelhos: dict[str, int] = {}
    for linha in linhas:
        texto = linha.get("trecho") or ""
        for codigo in assuntos_de(texto):
            assuntos[codigo] = assuntos.get(codigo, 0) + 1
        app = app_de(texto)
        if app:
            apps[app] = apps.get(app, 0) + 1
        aparelho = aparelho_de(texto)
        if aparelho:
            aparelhos[aparelho] = aparelhos.get(aparelho, 0) + 1
    return assuntos, (apps or None), (aparelhos or None)


def _ultimas(banco: Banco, cids: list) -> dict:
    if not cids:
        return {}
    saida = {}
    # Lotes pequenos: ANY grande em mensagens passa de 20s quando o banco está ocupado.
    for i in range(0, len(cids), 15):
        linhas = banco.linhas(_SQL_ULTIMA, {"cids": cids[i:i + 15]})
        if not linhas:
            continue
        for linha in linhas:
            saida[linha["cid"]] = linha
    return saida


def _espera(candidatos, banco: Banco, agora: datetime):
    if candidatos is None:
        return None, None
    ultimas = _ultimas(banco, [linha["cid"] for linha in candidatos])
    lista = []
    for linha in candidatos:
        ultima = ultimas.get(linha["cid"])
        if not ultima or str(ultima.get("direcao")) != "entrada":
            continue
        quando = ultima.get("ts_origem") or linha.get("ultima_msg_ts")
        if quando is None:
            continue
        if quando.tzinfo is None:
            quando = quando.replace(tzinfo=TZ)
        minutos = int((agora.astimezone(TZ) - quando.astimezone(TZ)).total_seconds() // 60)
        if minutos < 15:
            continue
        achados = assuntos_de(ultima.get("trecho") or "")
        lista.append({
            "cid": linha.get("cid"),
            "ph": mascarar_telefone(linha.get("telefone")) or "*----",
            "min": minutos,
            "atendente": None,
            "assunto": rotulo_assunto(achados[0]) if achados else "assunto não identificado",
            "whats": _whats(linha.get("instancia")),
        })
    lista.sort(key=lambda item: item["min"], reverse=True)
    return len(lista), lista[:8]


def _recentes(linhas, banco: Banco, agora: datetime):
    ultimas = _ultimas(banco, [linha["cid"] for linha in linhas])
    saida = []
    for linha in linhas:
        ultima = ultimas.get(linha["cid"]) or {}
        quando = linha.get("ultima_msg_ts")
        minutos = None
        if quando is not None:
            if quando.tzinfo is None:
                quando = quando.replace(tzinfo=TZ)
            minutos = int((agora.astimezone(TZ) - quando.astimezone(TZ)).total_seconds() // 60)
        direcao = str(ultima.get("direcao") or "")
        esperando = direcao == "entrada" and minutos is not None and minutos >= 1
        achados = assuntos_de(ultima.get("trecho") or "")
        from app.assuntos import nome_atendente

        codigo = atendente_de(ultima.get("autor_nome"), ultima.get("autor_tipo")) if direcao == "saida" else None
        if codigo:
            nome = nome_atendente(codigo)[0]
        elif direcao == "saida":
            nome = "Robô"
        else:
            nome = "Ainda sem resposta"
        assuntos = achados
        saida.append({
            "cid": linha.get("cid"),
            "ph": mascarar_telefone(linha.get("telefone")) or "*----",
            "atendente": nome,
            "assunto": rotulo_assunto(assuntos[0]) if assuntos else "assunto não identificado",
            "min": minutos if esperando else None,
            "esperando": esperando,
            "whats": _whats(linha.get("instancia")),
        })
        if len(saida) >= 8:
            break
    return saida


def _ritmo(linhas, agora: datetime):
    por_cid: dict = {}
    minutos_resp = {}
    minutos_recv = {}
    for linha in linhas:
        cid = linha["cid"]
        quando = linha.get("ts_origem")
        if quando is None:
            continue
        if quando.tzinfo is None:
            quando = quando.replace(tzinfo=TZ)
        quando = quando.astimezone(TZ)
        por_cid.setdefault(cid, []).append((quando, str(linha.get("direcao") or "")))
        chave = quando.replace(second=0, microsecond=0)
        if linha.get("direcao") == "entrada":
            minutos_recv[chave] = minutos_recv.get(chave, 0) + 1
        elif linha.get("direcao") == "saida":
            minutos_resp[chave] = minutos_resp.get(chave, 0) + 1
    esperas = []
    for eventos in por_cid.values():
        eventos.sort()
        aberto = None
        for quando, direcao in eventos:
            if direcao == "entrada" and aberto is None:
                aberto = quando
            elif direcao == "saida" and aberto is not None:
                esperas.append((quando - aberto).total_seconds())
                aberto = None
    tmr = round(sum(esperas) / len(esperas), 1) if len(esperas) >= 3 else None
    agora_m = agora.astimezone(TZ).replace(second=0, microsecond=0)
    resp, recv = [], []
    for i in range(29, -1, -1):
        chave = agora_m - timedelta(minutes=i)
        resp.append(minutos_resp.get(chave, 0))
        recv.append(minutos_recv.get(chave, 0))
    if not linhas:
        return tmr, None, None
    return tmr, resp, recv


_SQL_LEADS = """
SELECT
  count(DISTINCT conversa) FILTER (WHERE received_at >= %(hoje)s) AS hoje,
  count(DISTINCT conversa) FILTER (WHERE received_at >= %(ontem)s AND received_at < %(corte)s) AS ontem
FROM espelho.webhook_eventos
WHERE evento = 'msg_3619' AND received_at >= %(ontem)s
"""

_SQL_LEADS_HORA = """
SELECT EXTRACT(HOUR FROM received_at AT TIME ZONE 'America/Bahia')::int AS hora,
       count(DISTINCT conversa) AS n
FROM espelho.webhook_eventos
WHERE evento = 'msg_3619' AND received_at >= %(hoje)s
GROUP BY 1
"""

_SQL_TESTES = """
SELECT count(*) AS n FROM automacoes.testes_2h WHERE atualizado_em >= %(hoje)s
"""

_SQL_FEEDBACK = """
SELECT
  count(*) AS enviados,
  count(*) FILTER (WHERE resposta IS NOT NULL AND btrim(resposta) <> '') AS responderam,
  count(*) FILTER (WHERE classe ILIKE '%%satis%%' OR classe ILIKE '%%positiv%%' OR classe ILIKE '%%bom%%') AS ok,
  count(*) FILTER (WHERE classe ILIKE '%%reclam%%' OR classe ILIKE '%%negativ%%' OR classe ILIKE '%%ruim%%') AS ruim,
  count(*) FILTER (WHERE classe IS NULL OR btrim(classe) = '') AS sem_classe
FROM automacoes.feedback
WHERE coalesce(enviado_em, criado_em) >= %(hoje)s
"""

_SQL_DUVIDAS = "SELECT count(*) AS n FROM automacoes.duvidas WHERE criado_em >= %(hoje)s"

_SQL_TRAVADOS = """
SELECT coalesce(gatilho, '') AS gatilho, count(*) AS n
FROM automacoes.travados
WHERE criado_em >= %(hoje)s
GROUP BY 1
ORDER BY 2 DESC
LIMIT 12
"""

_SQL_ERROS = """
SELECT coalesce(nullif(btrim(erro), ''), '') AS tipo, count(*) AS n
FROM public.erros_robo
WHERE quando >= %(hoje)s
GROUP BY 1
ORDER BY 2 DESC
LIMIT 12
"""

_SQL_COMPROVANTES = """
SELECT count(*) AS n FROM fiscal.casos_comprovante WHERE status IN ('aberto', 'alertado')
"""

_SQL_ENVIOS = """
SELECT count(*) AS n FROM automacoes.envios
WHERE coalesce(enviado, false) = true AND criado_em >= %(hoje)s
"""

_SQL_AVISOS = "SELECT count(*) AS n FROM automacoes.avisos_vencimento WHERE criado_em >= %(hoje)s"

_SQL_VENCE = """
SELECT DISTINCT m.cid, split_part(m.autor_nome, ' ', 1) AS painel,
  CASE WHEN m.autor_nome ILIKE '%%VENCE HOJE%%' THEN 'hoje'
       WHEN m.autor_nome ILIKE '%%VENCE AMANH%%' THEN 'amanha'
       WHEN m.autor_nome ILIKE '%%VENCE DOIS%%' THEN 'dois' END AS classe,
  c.telefone
FROM espelho.mensagens m LEFT JOIN espelho.conversas c ON c.cid = m.cid
WHERE m.direcao = 'saida' AND m.autor_tipo = 'sistema' AND m.ts_origem >= %(hoje)s AND m.autor_nome ILIKE '%%VENCE%%'
"""

_SQL_ABERTAS = """
SELECT count(*) AS n FROM espelho.conversas WHERE ultima_msg_ts >= now() - interval '2 hours'
"""

_SQL_STATUS = """
SELECT coalesce(status_caso, '') AS status_caso, count(*) AS n
FROM espelho.conversas
WHERE ultima_msg_ts >= %(hoje)s
GROUP BY 1
"""

_SQL_ATENDENTES = """
SELECT
  CASE WHEN ts_origem >= %(hoje)s THEN 'hoje' ELSE 'ontem' END AS dia,
  coalesce(autor_nome, '') AS autor_nome,
  coalesce(autor_tipo, '') AS autor_tipo,
  direcao,
  count(*) AS msgs,
  count(DISTINCT cid) AS conversas
FROM espelho.mensagens
WHERE ts_origem >= %(ontem)s
  AND ts_origem <= %(agora)s
  AND (ts_origem >= %(hoje)s OR ts_origem < %(corte)s)
  AND coalesce(deletado, false) = false
  AND coalesce(interno, false) = false
GROUP BY 1, 2, 3, 4
"""

_SQL_ASSUNTOS = """
SELECT left(conteudo_texto, 240) AS trecho
FROM espelho.mensagens
WHERE ts_origem >= %(hoje)s
  AND direcao = 'entrada'
  AND conteudo_texto IS NOT NULL
  AND coalesce(deletado, false) = false
  AND coalesce(interno, false) = false
ORDER BY ts_origem DESC
LIMIT 1500
"""

_SQL_TEM_INSTANCIA = """
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'espelho'
  AND table_name = 'conversas'
  AND column_name = 'instancia'
"""

_SQL_ESPERA = """
SELECT cid, telefone, ultima_msg_ts
FROM espelho.conversas
WHERE ultima_msg_ts >= now() - interval '12 hours'
  AND ultima_msg_ts <= now() - interval '15 minutes'
ORDER BY ultima_msg_ts ASC
LIMIT 80
"""

_SQL_ESPERA_INST = """
SELECT cid, telefone, ultima_msg_ts, instancia
FROM espelho.conversas
WHERE ultima_msg_ts >= now() - interval '12 hours'
  AND ultima_msg_ts <= now() - interval '15 minutes'
ORDER BY ultima_msg_ts ASC
LIMIT 80
"""

_SQL_RECENTES = """
SELECT cid, telefone, ultima_msg_ts
FROM espelho.conversas
WHERE ultima_msg_ts >= now() - interval '6 hours'
ORDER BY ultima_msg_ts DESC
LIMIT 12
"""

_SQL_RECENTES_INST = """
SELECT cid, telefone, ultima_msg_ts, instancia
FROM espelho.conversas
WHERE ultima_msg_ts >= now() - interval '6 hours'
ORDER BY ultima_msg_ts DESC
LIMIT 12
"""

_SQL_ULTIMA = """
SELECT DISTINCT ON (cid)
  cid, direcao, ts_origem, autor_nome, autor_tipo, left(conteudo_texto, 180) AS trecho
FROM espelho.mensagens
WHERE cid = ANY(%(cids)s)
  AND coalesce(deletado, false) = false
  AND coalesce(interno, false) = false
ORDER BY cid, ts_origem DESC
"""

_SQL_PARES = """
SELECT cid, direcao, ts_origem
FROM espelho.mensagens
WHERE ts_origem >= now() - interval '45 minutes'
  AND coalesce(deletado, false) = false
  AND coalesce(interno, false) = false
ORDER BY ts_origem DESC
LIMIT 2500
"""


CONSULTAS = [
    _SQL_LEADS,
    _SQL_LEADS_HORA,
    _SQL_TESTES,
    _SQL_FEEDBACK,
    _SQL_DUVIDAS,
    _SQL_TRAVADOS,
    _SQL_ERROS,
    _SQL_COMPROVANTES,
    _SQL_ENVIOS,
    _SQL_AVISOS,
    _SQL_ABERTAS,
    _SQL_STATUS,
    _SQL_ATENDENTES,
    _SQL_ASSUNTOS,
    _SQL_TEM_INSTANCIA,
    _SQL_ESPERA,
    _SQL_ESPERA_INST,
    _SQL_RECENTES,
    _SQL_RECENTES_INST,
    _SQL_ULTIMA,
    _SQL_PARES,
]
