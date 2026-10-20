"""Junta as fontes no ritmo seguro e guarda o estado do painel."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

_log = logging.getLogger("painel")

from app.contador_cache import ler_contagem, ler_diretorio, resumo_contagem
from app.ler import (
    Cauda,
    backup_de,
    cpu_percent,
    disco_percent,
    eventos_de_acoes,
    ler_lancamentos,
    ler_log,
    ler_pagamentos,
    ram_percent,
)
from app.mascarar import mascarar_telefone
from app.montar import montar
from app.sistema import ler_mapa, ler_motivos, ler_rotinas, robo_ativo
from app.tempo import TZ, agora, inicio_do_dia


class Nucleo:
    def __init__(self, cfg):
        self.cfg = cfg
        self.cauda_acoes = Cauda(cfg.acoes, primeira_janela=8_000_000)
        self.cauda_log = Cauda(cfg.live_log, primeira_janela=400_000)
        self.banco = None
        self.cpu_ant = None
        self.log_linhas: list[str] = []
        self.acoes: list[dict] = []
        self.sql = {}
        self.publico = None
        self._quando = {}
        self._cache = {}
        self._cpu_visto = None
        self.metricas = None  # preenchido pelo main (cálculo das métricas em segundo plano)
        self.sigma_extra: dict = {}

    def fechar(self):
        if self.banco is not None:
            self.banco.fechar()

    def rodada(self) -> dict:
        try:
            return self._rodada()
        except Exception as exc:
            _log.warning("rodada incompleta: %s", exc)
            if self.publico is None:
                self.publico = montar({"agora": agora()})
            return self.publico

    def _rodada(self) -> dict:
        momento = agora()
        self._silencioso("acoes", self._ler_acoes)
        self._silencioso("log", self._ler_log)
        pagamentos, motivo_pag = self._pegar(
            "pagamentos", 45,
            lambda: self._ou((None, "sem dados — não consegui ler os pagamentos"), lambda: ler_pagamentos(self.cfg.mp_jsonl, self.cfg.mp_cache)),
        )
        lancamentos = self._ou(None, lambda: ler_lancamentos(self.cfg.ledger, self.acoes))
        sigma, sigma_quando, sigma_motivo, sigma_extra = self._pegar(
            "sigma", 120,
            lambda: self._ou((None, None, "sem dados — não consegui ler o cadastro", {}), self._sigma),
        )
        contador = self._pegar("contador", 30, lambda: self._ou(None, lambda: ler_diretorio(self.cfg.contador_dir)))
        contagem = self._pegar(
            "contagem_dia", 30,
            lambda: self._ou(None, lambda: resumo_contagem(self.cfg.contador_dir / "cache", momento)),
        )
        backup, backup_motivo = self._pegar(
            "backup", 60,
            lambda: self._ou((None, "sem dados — não consegui ler o backup"), lambda: backup_de(self.cfg.backup)),
        )
        cpu, self.cpu_ant = cpu_percent(self.cpu_ant)
        if cpu is None:
            cpu = self._cpu_visto
        else:
            self._cpu_visto = cpu
        if self.cfg.externo:
            rotinas, rotinas_motivo = self._pegar(
                "rotinas", 300,
                lambda: self._ou((None, "sem dados — não consegui ler os agendamentos do servidor"), lambda: ler_rotinas(ler_mapa(self.cfg.rotinas_nomes), momento)),
            )
            robo = self._ou(None, robo_ativo)
        else:
            rotinas, rotinas_motivo = None, "sem dado — não consegui ler os agendamentos do servidor"
            robo = None
        completa = self._pegar("contagem_completa", 30, lambda: self._ou(None, lambda: ler_contagem(self.cfg.contador_dir / "cache", momento)))
        if self._venceu("sql", 30):
            self.sql = self._sql(momento)
        self._anotar_whats()
        eventos, testes_eventos, tabela_eventos = _eventos_hoje(self.acoes, momento)
        fontes = {
            "agora": momento,
            "pagamentos": pagamentos,
            "pagamentos_motivo": motivo_pag,
            "lancamentos": lancamentos,
            "sigma": sigma,
            "sigma_quando": sigma_quando,
            "sigma_motivo": sigma_motivo,
            "sigma_extra": sigma_extra or {},
            "sql": self.sql,
            "log": ler_log(self.log_linhas, momento),
            "cpu": cpu,
            "ram": ram_percent(),
            "disco": disco_percent(),
            "robo_ativo": robo,
            "backup_em": backup,
            "backup_motivo": backup_motivo,
            "rotinas": rotinas,
            "rotinas_motivo": rotinas_motivo,
            "contador": contador,
            "contagem": contagem,
            "motivos": ler_motivos(self.cfg.motivos),
            "eventos": eventos,
            "testes_eventos": testes_eventos,
            "tabela_eventos": tabela_eventos,
            "contagem_completa": completa,
            "metricas_hoje": self._resumo_metricas(),
        }
        self.publico = montar(fontes)
        try:
            from app.inicio_0810 import completar

            completar(self.publico, fontes.get("metricas_hoje"))
        except Exception as exc:  # noqa: BLE001
            _log.warning("início 08/10 incompleto: %s", exc)
        return self.publico

    def _resumo_metricas(self):
        m = self.metricas
        if m is None or m.hoje is None:
            return None
        from app.metricas import resumo

        guardado = self._cache.get("resumo_metricas")
        if guardado and guardado[0] == m.quando:
            return guardado[1]
        # A comparação por última mensagem deixa de fora quem voltou a falar hoje.
        # Não vira "a mais que ontem" no cartão. A aba mostra a lista e o aviso.
        ontem = None if (m.meta_ontem or {}).get("complemento") else resumo(m.hoje_anterior)
        valor = {"hoje": resumo(m.hoje), "ontem": ontem, "quando": m.quando}
        self._cache["resumo_metricas"] = (m.quando, valor)
        return valor

    def _sql(self, momento):
        dsn = os.environ.get("ESPELHO_PG_DSN") or None
        if self.banco is None or self.banco.dsn != dsn:
            if self.banco is not None:
                self.banco.fechar()
            from app.banco import Banco

            self.banco = Banco(dsn, timeout_ms=20000)
            if self.metricas is not None:
                self.metricas.banco = self.banco
        try:
            return self.banco.coletar(momento)
        except Exception:
            return {"ok": False, "motivo": "sem dado — não consegui falar com o banco"}

    def _ler_acoes(self):
        linhas = self.cauda_acoes.novas_linhas()
        if linhas is None and not self.acoes:
            return
        self.acoes.extend(eventos_de_acoes(linhas or []))
        if len(self.acoes) > 4000:
            self.acoes = self.acoes[-4000:]

    def _ler_log(self):
        linhas = self.cauda_log.novas_linhas()
        if not linhas:
            return
        self.log_linhas.extend(linhas)
        if len(self.log_linhas) > 800:
            self.log_linhas = self.log_linhas[-800:]

    def _sigma(self):
        from app.sigma_cadastro import ler_melhor

        return ler_melhor(self.cfg)

    def _anotar_whats(self):
        mapa = {}
        inst = getattr(self.metricas, "inst", None) if self.metricas is not None else None
        if inst is not None:
            mapa = inst.mapa
        for chave in ("recentes", "esperando_lista"):
            for item in (self.sql or {}).get(chave) or []:
                if not isinstance(item, dict):
                    continue
                cid = str(item.pop("cid", "") or "")
                if item.get("whats") and item.get("whats") != "sem número":
                    continue
                item["whats"] = mapa.get(cid) or "sem número"

    def _ou(self, padrao, func):
        try:
            return func()
        except OSError as exc:
            _log.warning("bloco sem acesso: %s", exc)
            return padrao

    def _silencioso(self, nome, func):
        try:
            func()
        except OSError as exc:
            _log.warning("bloco %s sem acesso: %s", nome, exc)

    def _pegar(self, nome: str, segundos: float, func):
        guardado = self._cache.get(nome)
        if guardado and time.monotonic() - guardado[0] < segundos:
            return guardado[1]
        valor = func()
        self._cache[nome] = (time.monotonic(), valor)
        return valor

    def _venceu(self, nome: str, segundos: float) -> bool:
        ultimo = self._quando.get(nome, 0)
        if time.monotonic() - ultimo < segundos:
            return False
        self._quando[nome] = time.monotonic()
        return True


def _eventos_hoje(acoes: list[dict], momento) -> tuple[list, int | None, int | None]:
    if not acoes:
        return [], None, None
    inicio = inicio_do_dia(momento)
    eventos = []
    testes = 0
    tabela = 0
    for item in acoes:
        quando = item.get("ts")
        if isinstance(quando, str):
            from app.ler import _quando

            instante = _quando(quando)
        else:
            instante = None
        if instante is not None and instante < inicio:
            continue
        tipo = str(item.get("tipo") or "").casefold()
        telefone = mascarar_telefone(item.get("telefone"))
        detalhe = f"cliente {telefone}" if telefone else "cliente sem telefone no registro"
        if "teste" in tipo:
            testes += 1
            eventos.append(_ev(item, "teste", "Teste de 2 horas criado", detalhe, "teste"))
        elif "tabela" in tipo or "preco" in tipo or "preço" in tipo:
            tabela += 1
        elif "trava" in tipo or "barrad" in tipo:
            eventos.append(_ev(item, "segura", "Mensagem segurada", detalhe, "atencao"))
        elif "duvida" in tipo or "telegram" in tipo:
            eventos.append(_ev(item, "duvida", "Dúvida encaminhada", detalhe, "conversa"))
        elif "lead" in tipo or "3619" in tipo:
            eventos.append(_ev(item, "lead", "Conversa nova no WhatsApp", detalhe, "conversa"))
    return eventos[-20:], testes, tabela


def _ev(item, sufixo, titulo, detalhe, tom) -> dict:
    ident = f"{sufixo}-{item.get('ts')}-{item.get('telefone') or ''}"
    return {"id": ident, "titulo": titulo, "detalhe": detalhe, "tom": tom, "valor": None, "em": item.get("ts") or ""}
