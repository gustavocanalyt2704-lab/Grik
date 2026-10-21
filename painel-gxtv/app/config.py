"""Caminhos reais da VPS. Segredo só pelo nome da variável, nunca o valor."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


@dataclass
class Cfg:
    auth_file: Path
    sessao_key: Path
    porta: int
    tls: bool
    cert: Path
    chave: Path
    coletar: bool
    externo: bool
    aviso_local: bool
    mp_jsonl: Path
    mp_cache: Path
    contador_dir: Path
    sigma_cache: Path
    sigma_users: Path
    acoes: Path
    ledger: Path
    live_log: Path
    backup: Path
    env_espelho: Path
    rotinas_nomes: Path
    motivos: Path
    intervalo: float = 4.0
    sigma_rows: Path = Path("/opt/mnrobo/contador_tg/cache/sigma_rows.ok.jsonl")
    sigma_parcial: Path = Path("/opt/mnrobo/contador_tg/cache/sigma_rows.parcial.jsonl")
    sigma_estado: Path = Path("/opt/mnrobo/contador_tg/cache/sigma_estado.json")
    registro: Path = Path("/var/lib/painel-gxtv/acoes.jsonl")
    lista_pausa: Path = Path("/opt/mnrobo/atendimento/ai/private/nao_responder_estrito.txt")
    planos: Path = RAIZ / "config" / "sigma_planos.json"
    paineis: Path = RAIZ / "config" / "paineis.json"
    gestor_url: str = "https://gestor-iptv-1.emergent.host/api/lookup/customer"


def cfg_de_ambiente() -> Cfg:
    def caminho(nome: str, padrao: str) -> Path:
        return Path(os.environ.get(nome, padrao))

    return Cfg(
        auth_file=caminho("PAINEL_AUTH_FILE", "/var/lib/painel-gxtv/auth.json"),
        sessao_key=caminho("PAINEL_SESSAO_KEY", "/var/lib/painel-gxtv/sessao.key"),
        porta=int(os.environ.get("PAINEL_PORT", "8741")),
        tls=os.environ.get("PAINEL_TLS", "1") != "0",
        cert=caminho("PAINEL_CERT", "/var/lib/painel-gxtv/cert.pem"),
        chave=caminho("PAINEL_CERT_KEY", "/var/lib/painel-gxtv/key.pem"),
        coletar=os.environ.get("PAINEL_COLETAR", "1") != "0",
        externo=os.environ.get("PAINEL_EXTERNO", "1") != "0",
        aviso_local=os.environ.get("PAINEL_AVISO_LOCAL", "0") == "1",
        mp_jsonl=caminho("PAINEL_MP_JSONL", "/opt/mp_alerta/pagamentos.jsonl"),
        mp_cache=caminho("PAINEL_MP_CACHE", "/opt/mnrobo/contador_tg/cache/mp_api.jsonl"),
        contador_dir=caminho("PAINEL_CONTADOR_DIR", "/opt/mnrobo/contador_tg"),
        sigma_cache=caminho("PAINEL_SIGMA_CACHE", "/opt/mnrobo/atendimento/ai/private/sigma_cache.json"),
        sigma_users=caminho("PAINEL_SIGMA_USERS", "/opt/mnrobo/atendimento/contador/painel_cache/sigma_users.json"),
        acoes=caminho("PAINEL_ACOES", "/workspace/atendimento/acoes/acoes.jsonl"),
        ledger=caminho("PAINEL_LEDGER", "/workspace/atendimento/acoes/renov_ledger.jsonl"),
        live_log=caminho("PAINEL_LIVE_LOG", "/opt/mnrobo/ai/private/live.log"),
        backup=caminho("PAINEL_BACKUP", ""),
        env_espelho=caminho("PAINEL_ENV_ESPELHO", "/etc/mnrobo-espelho2.env"),
        rotinas_nomes=caminho("PAINEL_ROTINA_NOMES", str(RAIZ / "config" / "rotinas_nomes.json")),
        motivos=caminho("PAINEL_MOTIVOS", str(RAIZ / "config" / "motivos.json")),
        sigma_rows=caminho("PAINEL_SIGMA_ROWS", "/opt/mnrobo/contador_tg/cache/sigma_rows.ok.jsonl"),
        sigma_parcial=caminho("PAINEL_SIGMA_PARCIAL", "/opt/mnrobo/contador_tg/cache/sigma_rows.parcial.jsonl"),
        sigma_estado=caminho("PAINEL_SIGMA_ESTADO", "/opt/mnrobo/contador_tg/cache/sigma_estado.json"),
        registro=caminho("PAINEL_REGISTRO", "/var/lib/painel-gxtv/acoes.jsonl"),
        lista_pausa=caminho("PAINEL_LISTA_PAUSA", "/opt/mnrobo/atendimento/ai/private/nao_responder_estrito.txt"),
        planos=caminho("PAINEL_PLANOS", str(RAIZ / "config" / "sigma_planos.json")),
        paineis=caminho("PAINEL_PAINEIS", str(RAIZ / "config" / "paineis.json")),
        gestor_url=os.environ.get("PAINEL_GESTOR_URL", "https://gestor-iptv-1.emergent.host/api/lookup/customer"),
    )
