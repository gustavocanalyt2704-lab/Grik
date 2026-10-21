"""Servidor do painel. Um processo, só leitura, atualização por SSE."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
import gzip
from pydantic import BaseModel

from app.auth import COOKIE, Auth
from app.banco import Banco
from app.config import cfg_de_ambiente
from app.metricas import Metricas
from app.nucleo import Nucleo
from app.tempo import agora

ESTATICOS = Path(__file__).resolve().parent / "static"
_PROIBIDO = ("enviar", "renovar", "pausar", "mensagem", "disparar")


class Entrada(BaseModel):
    usuario: str = ""
    senha: str = ""


class Acao(BaseModel):
    acao: str = ""
    q: str = ""
    dias: int = 30
    app: str = ""
    painel: str = "principal"
    confirmar: bool = False


def criar_app(cfg=None) -> FastAPI:
    cfg = cfg or cfg_de_ambiente()
    nucleo = Nucleo(cfg)
    auth = Auth(cfg.auth_file)
    filas: list[asyncio.Queue] = []
    # Uma conexão só: o pooler do espelho é modo sessão e a cota estoura
    # se o painel abre duas. Métricas e o restante esperam a vez nessa conexão.
    banco_painel = Banco(os.environ.get("ESPELHO_PG_DSN") or None, timeout_ms=20000)
    nucleo.banco = banco_painel
    metricas = Metricas(cfg, lambda: banco_painel)
    nucleo.metricas = metricas
    ultimo_envio = {"hash": None, "quando": 0.0}
    cache_metricas: dict = {}

    @asynccontextmanager
    async def vida(_app: FastAPI):
        tarefas = []
        if cfg.coletar:
            tarefas.append(asyncio.create_task(_ciclo()))
            tarefas.append(asyncio.create_task(_ciclo_metricas()))
        else:
            await asyncio.to_thread(nucleo.rodada)
        if os.environ.get("PAINEL_DEMO_CONVERSAS"):
            await asyncio.to_thread(metricas.rodar, agora())
            await asyncio.to_thread(nucleo.rodada)
        try:
            yield
        finally:
            for tarefa in tarefas:
                tarefa.cancel()
            nucleo.fechar()

    app = FastAPI(title="Painel GXTV", docs_url=None, redoc_url=None, openapi_url=None, lifespan=vida)

    @app.middleware("http")
    async def cabecalhos(request: Request, call_next):
        resposta = await call_next(request)
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        resposta.headers["Referrer-Policy"] = "no-referrer"
        resposta.headers["X-Frame-Options"] = "DENY"
        resposta.headers["Cache-Control"] = "no-store"
        return resposta

    app.state.cfg = cfg
    app.state.nucleo = nucleo
    app.state.auth = auth

    async def _ciclo():
        while True:
            try:
                await asyncio.to_thread(nucleo.rodada)
                await _avisar("snapshot")
            except Exception:
                pass
            await asyncio.sleep(cfg.intervalo)

    async def _ciclo_metricas():
        await asyncio.sleep(5)
        while True:
            try:
                await asyncio.to_thread(metricas.rodar, agora())
            except Exception as exc:  # noqa: BLE001
                import logging

                logging.getLogger("painel").warning("métricas incompletas: %s", exc)
            # Enquanto o dia ou a comparação não fecharam, tenta de novo logo.
            pausa = 20 if metricas.hoje is None or metricas.hoje_anterior is None else 120
            await asyncio.sleep(pausa)

    async def _avisar(tipo: str):
        """Manda o estado só quando algo mudou (ou a cada 20s). Fila cheia: sai o pacote mais velho."""
        estado_ = nucleo.publico or {}
        base = {k: v for k, v in estado_.items() if k != "hora"}
        saude = ((base.get("gavetas") or {}).get("saude") or {})
        if saude:
            base = dict(base)
            base["gavetas"] = dict(base["gavetas"])
            base["gavetas"]["saude"] = {k: v for k, v in saude.items() if k not in ("cpu", "ram")}
        marca = hashlib.sha256(json.dumps(base, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
        if marca == ultimo_envio["hash"] and time.monotonic() - ultimo_envio["quando"] < 20:
            return
        ultimo_envio["hash"], ultimo_envio["quando"] = marca, time.monotonic()
        pacote = json.dumps({"tipo": tipo, "aviso_local": cfg.aviso_local, "estado": estado_}, ensure_ascii=False)
        for fila in list(filas):
            if fila.full():
                try:
                    fila.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            fila.put_nowait(pacote)

    def _token(request: Request) -> str | None:
        return request.cookies.get(COOKIE)

    def _logado(request: Request) -> bool:
        return auth.valida(_token(request))

    def _demo() -> bool:
        return os.environ.get("PAINEL_DEMO") == "1"

    @app.get("/api/ping")
    async def ping():
        return {"ok": True, "servico": "painel-gxtv", "demo": _demo()}

    @app.get("/api/eu")
    async def eu(request: Request):
        if not _logado(request):
            return JSONResponse({"ok": False}, status_code=401)
        return {"ok": True, "usuario": auth.usuario}

    @app.post("/api/entrar")
    async def entrar(corpo: Entrada, request: Request):
        ip = request.client.host if request.client else "0"
        ok, mensagem, token = auth.entrar(corpo.usuario, corpo.senha, ip)
        if not ok:
            codigo = 429 if "Muitas" in mensagem else 401
            return JSONResponse({"ok": False, "mensagem": mensagem}, status_code=codigo)
        resposta = JSONResponse({"ok": True})
        resposta.set_cookie(
            COOKIE,
            token,
            httponly=True,
            secure=cfg.tls,
            samesite="strict",
            max_age=12 * 60 * 60,
            path="/",
        )
        return resposta

    @app.post("/api/sair")
    async def sair(request: Request):
        auth.sair(_token(request))
        resposta = JSONResponse({"ok": True})
        resposta.delete_cookie(COOKIE, path="/")
        return resposta

    @app.get("/api/estado")
    async def estado(request: Request):
        if not _logado(request):
            return JSONResponse({"ok": False}, status_code=401)
        if nucleo.publico is None:
            await asyncio.to_thread(nucleo.rodada)
        return {"ok": True, "hora": agora().isoformat(), "aviso_local": cfg.aviso_local, "estado": nucleo.publico}

    @app.get("/api/stream")
    async def stream(request: Request):
        if not _logado(request):
            return JSONResponse({"ok": False}, status_code=401)
        fila: asyncio.Queue = asyncio.Queue(maxsize=8)
        filas.append(fila)

        async def gerar():
            try:
                if nucleo.publico is None:
                    await asyncio.to_thread(nucleo.rodada)
                yield "retry: 4000\n\n"
                yield _sse({"tipo": "snapshot", "aviso_local": cfg.aviso_local, "estado": nucleo.publico})
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        pacote = await asyncio.wait_for(fila.get(), timeout=15)
                        yield f"event: snapshot\ndata: {pacote}\n\n"
                    except asyncio.TimeoutError:
                        yield _sse({"tipo": "ping", "hora": agora().isoformat()})
            finally:
                if fila in filas:
                    filas.remove(fila)

        return StreamingResponse(gerar(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/metricas")
    async def api_metricas(request: Request, periodo: str = "hoje"):
        if not _logado(request):
            return JSONResponse({"ok": False}, status_code=401)
        if periodo not in ("hoje", "ontem", "7d"):
            periodo = "hoje"
        chave = (periodo, metricas.quando)
        if chave not in cache_metricas:
            def preparar():
                corpo = json.dumps(metricas.pacote(periodo), ensure_ascii=False, separators=(",", ":"), default=str).encode()
                return gzip.compress(corpo, 6)
            for velha in [k for k in cache_metricas if k[1] != metricas.quando]:
                cache_metricas.pop(velha, None)
            cache_metricas[chave] = await asyncio.to_thread(preparar)
        comprimido = cache_metricas[chave]
        if "gzip" in (request.headers.get("accept-encoding") or ""):
            return Response(comprimido, media_type="application/json", headers={"Content-Encoding": "gzip", "Vary": "Accept-Encoding"})
        return Response(gzip.decompress(comprimido), media_type="application/json")

    @app.get("/api/lote-atencao-metricas")  # bloco isolado lote atenção (JSON local; depois bc-8d350dba)
    async def api_lote_atencao_metricas(request: Request, periodo: str = "hoje"):
        if not _logado(request):
            return JSONResponse({"ok": False}, status_code=401)
        if periodo not in ("hoje", "ontem", "7d") and len(periodo) != 10:
            periodo = "hoje"
        def _pacote():
            from app.lote_atencao_metricas import pacote as _p
            return _p(periodo)
        return JSONResponse(await asyncio.to_thread(_pacote))

    @app.get("/api/ranking-apps-metricas")  # placar taxa sucesso app×aparelho (JSON local)
    async def api_ranking_apps_metricas(request: Request, periodo: str = "4h"):
        if not _logado(request):
            return JSONResponse({"ok": False}, status_code=401)
        if periodo not in ("4h", "7d", "tudo"):
            periodo = "4h"
        if _demo():
            from app.demo_dados import ranking as ranking_demo

            return JSONResponse(ranking_demo())
        def _pacote():
            from app.ranking_apps_metricas import pacote as _p
            return _p(periodo)
        return JSONResponse(await asyncio.to_thread(_pacote))

    @app.get("/api/por-conta")  # POR_CONTA_1810
    async def api_por_conta(request: Request):
        if not _logado(request):
            return JSONResponse({"ok": False}, status_code=401)
        def _pacote():
            from app.por_conta import ligado, pacote as _p
            return _p() if ligado() else {"ok": False, "desligado": True}
        return JSONResponse(await asyncio.to_thread(_pacote))

    @app.get("/api/atendidos-hoje")  # ATENDIDOS_1410
    async def api_atendidos_hoje(request: Request):
        if not _logado(request):
            return JSONResponse({"ok": False}, status_code=401)
        if _demo():
            from app.demo_dados import atendidos as atendidos_demo

            return JSONResponse(atendidos_demo())
        def _pacote():
            from app.atendidos_hoje import pacote as _p
            return _p()
        return JSONResponse(await asyncio.to_thread(_pacote))

    @app.get("/api/mensagens-semana")  # SEMANA_1110: msgs por dia da semana, atual x anterior (arquivo local)
    async def api_mensagens_semana(request: Request):
        if not _logado(request):
            return JSONResponse({"ok": False}, status_code=401)
        if _demo():
            from app.demo_dados import semana as semana_demo

            return JSONResponse(semana_demo())
        def _pacote():
            from app.mensagens_semana import pacote as _p
            return _p()
        return JSONResponse(await asyncio.to_thread(_pacote))

    @app.get("/api/graficos")
    async def api_graficos(request: Request):
        """Séries ao vivo. Só junta leituras que o painel já faz."""
        if not _logado(request):
            return JSONResponse({"ok": False}, status_code=401)
        from app.graficos_ao_vivo import montar as montar_graficos

        return JSONResponse(await asyncio.to_thread(montar_graficos, nucleo))

    @app.get("/api/vendas")  # VENDAS_1110: venda nova x renovação por dia (arquivos locais)
    async def api_vendas(request: Request, dia: str = ""):
        if not _logado(request):
            return JSONResponse({"ok": False}, status_code=401)
        if _demo():
            from app.demo_dados import vendas_dia

            return JSONResponse(vendas_dia())
        def _pacote():
            from app.vendas_painel import pacote as _p
            return _p(dia or None)
        return JSONResponse(await asyncio.to_thread(_pacote))

    @app.get("/api/p11/vendas")  # PAINEL_1110: vendas do dia + funil (arquivos locais)
    async def api_p11_vendas(request: Request, periodo: str = "hoje"):
        if not _logado(request):
            return JSONResponse({"ok": False}, status_code=401)
        if _demo():
            from app.demo_dados import vendas_p11

            return JSONResponse(vendas_p11(periodo if periodo in ("hoje", "ontem", "7d") else "hoje"))
        from app.painel_1110 import vendas as _v
        return JSONResponse(await asyncio.to_thread(_v, periodo if periodo in ("hoje", "ontem", "7d") else "hoje"))

    @app.get("/api/p11/saude")  # PAINEL_1110: serviços, IA, fiscal, filas
    async def api_p11_saude(request: Request):
        if not _logado(request):
            return JSONResponse({"ok": False}, status_code=401)
        if _demo():
            from app.demo_dados import saude as saude_demo

            return JSONResponse(saude_demo())
        from app.painel_1110 import saude as _s
        return JSONResponse(await asyncio.to_thread(_s))

    @app.get("/api/p11/alertas")  # PAINEL_1110: sininho (venda nova, comprovante parado, erro grave)
    async def api_p11_alertas(request: Request):
        if not _logado(request):
            return JSONResponse({"ok": False}, status_code=401)
        if _demo():
            from app.demo_dados import alertas as alertas_demo

            return JSONResponse(alertas_demo())
        from app.painel_1110 import alertas as _a
        return JSONResponse(await asyncio.to_thread(_a))

    @app.get("/api/vivo")  # AO_VIVO_WEBHOOK_0810: registro do webhook (arquivo local; zero API DataCrazy)
    async def api_vivo(request: Request):
        if not _logado(request):
            return JSONResponse({"ok": False}, status_code=401)
        if _demo():
            from app.demo_dados import vivo as vivo_demo

            return JSONResponse(vivo_demo())
        from app.webhook_vivo import VIVO

        pacote = await asyncio.to_thread(VIVO.pacote)
        # QUEM_WEBHOOK_0810: "quem atendeu" já vem do registro do webhook dentro de pacote["numeros"]
        return JSONResponse(pacote)

    @app.get("/api/ativos-reais")  # ATIVOS_REAIS_1210: lê o arquivo do coletor (zero Sigma aqui)
    async def api_ativos_reais(request: Request):
        if not _logado(request):
            return JSONResponse({"ok": False}, status_code=401)
        if _demo():
            from app.demo_dados import ativos as ativos_demo

            return JSONResponse(ativos_demo())
        try:
            import json as _j
            d = _j.load(open("/var/lib/painel-gxtv/ativos_reais.json", encoding="utf-8"))
            d["ok"] = True
            return JSONResponse(d)
        except Exception:
            return JSONResponse({"ok": False})

    @app.get("/api/cliente")
    async def cliente(request: Request, q: str = ""):
        if not _logado(request):
            return JSONResponse({"ok": False}, status_code=401)
        if _demo():
            from app.demo_dados import cliente as cliente_demo

            return cliente_demo(q)
        from app.ficha import montar as montar_ficha
        from app.mascarar import sanitizar

        corpo = await asyncio.to_thread(montar_ficha, cfg, q, nucleo.publico)
        return sanitizar(corpo)

    @app.get("/api/opcoes")
    async def opcoes(request: Request):
        if not _logado(request):
            return JSONResponse({"ok": False}, status_code=401)
        from app.sigma_acoes import opcoes as opcoes_sigma

        return await asyncio.to_thread(opcoes_sigma, cfg)

    @app.post("/api/acao")
    async def acao(corpo: Acao, request: Request):
        if not _logado(request):
            return JSONResponse({"ok": False}, status_code=401)
        if os.environ.get("PAINEL_SEM_ACAO") == "1":
            return JSONResponse({"ok": False, "mensagem": "sem dado — esta cópia só lê métricas"}, status_code=403)
        if _demo():
            from app.demo_dados import acao as acao_demo

            return acao_demo(corpo.model_dump())
        from app.mascarar import sanitizar
        from app.operar import executar

        resultado = await asyncio.to_thread(
            executar,
            cfg,
            auth.usuario,
            corpo.model_dump(),
            nucleo.publico,
        )
        return sanitizar(resultado)

    @app.get("/")
    async def inicio():
        return FileResponse(ESTATICOS / "index.html", headers={"Cache-Control": "no-store"})

    app.mount("/static", StaticFiles(directory=ESTATICOS), name="static")
    return app


def _sse(dado: dict) -> str:
    return f"event: {dado['tipo']}\ndata: {json.dumps(dado, ensure_ascii=False)}\n\n"


app = criar_app()


def metodos_publicos() -> dict[str, set[str]]:
    """Usado pelo teste de somente leitura."""
    rotas = {}
    for rota in app.routes:
        metodos = getattr(rota, "methods", None)
        caminho = getattr(rota, "path", "")
        if metodos and caminho.startswith("/api"):
            rotas[caminho] = set(metodos) - {"HEAD", "OPTIONS"}
    return rotas
