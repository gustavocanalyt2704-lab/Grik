# -*- coding: utf-8 -*-
"""PAINEL_1110 — Visão geral / Vendas+Funil / Saúde / Alertas do Painel GXTV.

Só leitura de arquivos locais (e um GET sem login no Gestor para o passo "cadastro" do funil, com cache).
Nunca chama a API do DataCrazy, nunca envia nada, não escreve nos arquivos do robô.

Fontes:
  vendas   /opt/mnrobo/atendimento/acoes/renov_ledger.jsonl (status renovado, valor no reservado)
           /opt/mnrobo/atendimento/fiscal_comprovante/usados.jsonl (valor, plano, venda_nova, msg_hora)
  número   /opt/mnrobo/atendimento/webhook/queue.jsonl (conversa -> evento msg_3619/msg_0837...)
  funil    lead = 1ª msg "Olá! Posso ter mais informações" (queue.jsonl); teste = funil_eventos.jsonl etapa=teste;
           pagou = renovado no ledger da mesma conversa; cadastro = Gestor (gestor-iptv-1.emergent.host) acha o telefone
  saúde    systemctl is-active; vigia/vigia.log (cron 5 min); ai/private/ia_uso.jsonl (gasto IA);
           fiscal.log (FAST_WH, ciclo); fiscal_comprovante/manual.txt; vigia/comprovante_parado.jsonl;
           ai/private/live.log (última linha POLL); saldo IA opcional em /var/lib/painel-gxtv/ia_saldo.json
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from app.tempo import TZ
from app.webhook_vivo import _ordem, rotulo

A = Path("/opt/mnrobo/atendimento")
ARQ_LEDGER = A / "acoes/renov_ledger.jsonl"
ARQ_USADOS = A / "fiscal_comprovante/usados.jsonl"
ARQ_QUEUE = A / "webhook/queue.jsonl"
ARQ_FUNIL = A / "ai/private/funil_eventos.jsonl"
ARQ_IA = A / "ai/private/ia_uso.jsonl"
ARQ_LIVE = A / "ai/private/live.log"
ARQ_ALERTAS_VIGIA = A / "ai/private/alertas.log"
ARQ_FISCAL_LOG = A / "fiscal_comprovante/fiscal.log"
ARQ_MANUAL = A / "fiscal_comprovante/manual.txt"
ARQ_PARADO = A / "vigia/comprovante_parado.jsonl"
ARQ_VIGIA_LOG = A / "vigia/vigia.log"
ARQ_SALDO = Path(os.environ.get("PAINEL_IA_SALDO") or "/var/lib/painel-gxtv/ia_saldo.json")
GESTOR = "https://gestor-iptv-1.emergent.host/api/lookup/customer"
LEAD_TXT = "posso ter mais informa"
TESTE_GUSTAVO = "557791625576"
SERVICOS = [("mnrobo", "Robô (WhatsApp)"), ("mnrobo-fiscal", "Fiscal de comprovante"),
            ("mnrobo-receiver", "Receptor de webhook"), ("mnbox-vigia", "Vigia do túnel")]

_trava = threading.RLock()


def _agora():
    return datetime.now(TZ)


def _dt(v):
    try:
        d = datetime.fromisoformat(str(v))
    except (TypeError, ValueError):
        return None
    return d.replace(tzinfo=TZ) if d.tzinfo is None else d.astimezone(TZ)


def _k(chave) -> str:
    t = str(chave or "").strip()
    for pre in ("SHA:", "ID:", "sha:", "id:"):
        if t.startswith(pre):
            t = t[len(pre):]
    return t.upper()


def _f(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _jl(p: Path):
    try:
        with p.open("rb") as fh:
            for ln in fh:
                try:
                    yield json.loads(ln)
                except ValueError:
                    pass
    except OSError:
        return


def _cauda_txt(p: Path, n=300_000) -> list[str]:
    try:
        with p.open("rb") as fh:
            fh.seek(0, 2)
            t = fh.tell()
            fh.seek(max(0, t - n))
            return fh.read().decode("utf-8", "ignore").splitlines()[1:]
    except OSError:
        return []


def _fim(p: Path):
    try:
        return p.stat().st_mtime
    except OSError:
        return None


# ---------------------------------------------------------------- conversa -> número / leads (queue.jsonl, incremental)
class _Queue:
    def __init__(self):
        self.offset, self.inode, self.resto = 0, None, b""
        self.conv_inst: dict[str, str] = {}
        self.leads: dict[str, dict] = {}  # cid -> {ts, inst, tel}
        self.ult = 0.0
        self.erro = ""
        self._lk = threading.Lock()  # FIX1710: Vendas e Funil leem juntos

    def ler(self):
        with self._lk:
            self._ler()

    def _ler(self):
        if time.time() - self.ult < 20:
            return
        self.ult = time.time()
        try:
            st = ARQ_QUEUE.stat()
        except OSError as exc:
            self.erro = f"sem acesso: {exc.__class__.__name__}"
            return
        ino = (st.st_dev, st.st_ino)
        if ino != self.inode or st.st_size < self.offset:
            self.inode, self.offset, self.resto = ino, 0, b""
        if st.st_size == self.offset:
            return
        try:
            with ARQ_QUEUE.open("rb") as fh:
                fh.seek(self.offset)
                while True:
                    bloco = fh.read(4_000_000)
                    if not bloco:
                        break
                    self.offset += len(bloco)
                    linhas = (self.resto + bloco).split(b"\n")
                    self.resto = linhas.pop()
                    for ln in linhas:
                        if b'"conversa"' in ln:
                            self._linha(ln)
        except OSError as exc:
            self.erro = f"sem acesso: {exc.__class__.__name__}"
            return
        self.erro = ""

    def _linha(self, ln: bytes):
        try:
            a = json.loads(ln)
        except ValueError:
            return
        p = a.get("payload") if isinstance(a.get("payload"), dict) else {}
        cid = str(p.get("conversa") or "")
        ev = str(p.get("evento") or "")
        if not cid or "teste" in ev or "canary" in str(p.get("instancia") or "").lower():
            return
        if ev.lower() == "conversa_atribuida":
            return
        inst = rotulo(ev, p.get("instancia"))
        if inst:
            self.conv_inst.setdefault(cid, inst)
        if cid not in self.leads and LEAD_TXT in str(p.get("texto") or "").lower():
            tel = re.sub(r"\D", "", str(p.get("telefone") or ""))
            if tel == TESTE_GUSTAVO:
                return
            try:
                ts = float(a.get("received_ts"))
            except (TypeError, ValueError):
                return
            self.leads[cid] = {"ts": ts, "inst": inst or "sem número", "tel": tel}


QUEUE = _Queue()


# ---------------------------------------------------------------- vendas (ledger + usados)
_vendas_cache = {"t": 0.0, "lista": [], "erro": ""}


def _vendas() -> list[dict]:
    """FIX1710: MESMA lista da aba Vendas (vendas_painel: ledger + usados + marcador de venda nova),
    dia America/Bahia 00:00-23:59, últimos 16 dias. Assim Visão geral, Vendas e Funil batem."""
    if time.time() - _vendas_cache["t"] < 15:
        return _vendas_cache["lista"]
    from app import vendas_painel as VP
    hoje = _agora().date()
    lista = []
    for d in range(16, -1, -1):
        dia = (hoje - timedelta(days=d)).isoformat()
        try:
            pk = VP.pacote(dia)
        except Exception:  # noqa: BLE001
            continue
        for i in pk.get("lista") or []:
            q = _dt(i.get("ts"))
            if not q:
                continue
            inst = i.get("instancia")
            lista.append({"quando": q, "valor": i.get("valor"), "plano": i.get("plano"), "nova": i.get("tipo") == "venda",
                          "conv": str(i.get("conv") or ""), "tel": str(i.get("telefone") or ""),
                          "msg_hora": i.get("msg_hora"), "inst": inst if inst and inst != "—" else None})
    lista.sort(key=lambda r: r["quando"])
    _vendas_cache.update(t=time.time(), lista=lista, erro="" if ARQ_LEDGER.exists() else "ledger não encontrado")
    return lista


def _num_venda(r) -> str:
    return r.get("inst") or _numero(r["conv"])


def _numero(conv: str) -> str:
    n = QUEUE.conv_inst.get(conv)
    if n:
        return n
    try:
        from app.webhook_vivo import VIVO
        return VIVO.conv_num.get(conv) or "sem número"
    except Exception:
        return "sem número"


def _resumo(lista):
    n = len(lista)
    reais = round(sum(r["valor"] or 0 for r in lista), 2)
    return {"n": n, "reais": reais, "ticket": round(reais / n, 2) if n else None,
            "novas": sum(1 for r in lista if r["nova"]), "novas_reais": round(sum(r["valor"] or 0 for r in lista if r["nova"]), 2)}


def _janela(ini, fim):
    return [r for r in _vendas() if ini <= r["quando"] < fim]


_res_cache: dict = {}  # FIX1710: periodo -> (t, pacote); 7 dias custava ~7 s por pedido


def vendas(periodo: str = "hoje") -> dict:
    with _trava:
        c = _res_cache.get(periodo)
        if c and time.time() - c[0] < (10 if periodo == "hoje" else 60):
            return c[1]
        r = _vendas_calc(periodo)
        _res_cache[periodo] = (time.time(), r)
        return r


def _vendas_calc(periodo: str = "hoje") -> dict:
    if True:
        QUEUE.ler()
        agora = _agora()
        h0 = agora.replace(hour=0, minute=0, second=0, microsecond=0)
        dt_agora = agora - h0
        if periodo == "ontem":
            ini, fim = h0 - timedelta(days=1), h0
        elif periodo == "7d":
            ini, fim = h0 - timedelta(days=6), agora + timedelta(seconds=1)
        else:
            periodo, ini, fim = "hoje", h0, agora + timedelta(seconds=1)
        sel = _janela(ini, fim)
        res = _resumo(sel)

        # comparação no mesmo ponto do dia (só faz sentido para hoje)
        comp = {}
        if periodo == "hoje":
            o = _resumo(_janela(h0 - timedelta(days=1), h0 - timedelta(days=1) + dt_agora))
            s = _resumo(_janela(h0 - timedelta(days=7), h0 - timedelta(days=7) + dt_agora))
            dias = [_resumo(_janela(h0 - timedelta(days=d), h0 - timedelta(days=d) + dt_agora)) for d in range(1, 8)]
            comp = {
                "ontem": o, "semana_passada": s,
                "media_7d": {"n": round(sum(d["n"] for d in dias) / 7, 1), "reais": round(sum(d["reais"] for d in dias) / 7, 2)},
                "ontem_dia_todo": _resumo(_janela(h0 - timedelta(days=1), h0)),
            }
        elif periodo == "ontem":
            comp = {"anteontem": _resumo(_janela(h0 - timedelta(days=2), h0 - timedelta(days=1))),
                    "semana_passada": _resumo(_janela(h0 - timedelta(days=8), h0 - timedelta(days=7)))}
        else:
            comp = {"7d_anteriores": _resumo(_janela(h0 - timedelta(days=13), h0 - timedelta(days=6)))}

        por_num: dict[str, list] = defaultdict(list)
        for r in sel:
            por_num[_num_venda(r)].append(r)
        numeros = [{"numero": k, **_resumo(v)} for k, v in sorted(por_num.items(), key=lambda x: _ordem(x[0]))]

        # por hora (hoje/ontem) ou por dia (7d)
        if periodo == "7d":
            eixo = [(h0 - timedelta(days=6 - i)) for i in range(7)]
            serie = [_resumo([r for r in sel if r["quando"].date() == d.date()]) for d in eixo]
            barras = {"tipo": "dia", "rotulos": [d.strftime("%d/%m") for d in eixo],
                      "n": [x["n"] for x in serie], "reais": [x["reais"] for x in serie]}
        else:
            n = [0] * 24
            rs = [0.0] * 24
            for r in sel:
                n[r["quando"].hour] += 1
                rs[r["quando"].hour] = round(rs[r["quando"].hour] + (r["valor"] or 0), 2)
            ref = _janela(ini - timedelta(days=1), ini)
            nref = [0] * 24
            for r in ref:
                nref[r["quando"].hour] += 1
            barras = {"tipo": "hora", "rotulos": [f"{i}h" for i in range(24)], "n": n, "reais": rs,
                      "n_dia_anterior": nref, "hora_agora": agora.hour if periodo == "hoje" else 24}

        planos: dict[str, int] = defaultdict(int)
        for r in sel:
            planos[r["plano"] or "sem plano"] += 1
        ultimas = [{"hora": r["quando"].strftime("%d/%m %H:%M" if periodo == "7d" else "%H:%M"), "valor": r["valor"],
                    "numero": _num_venda(r), "nova": r["nova"], "plano": r["plano"]}
                   for r in sorted(sel, key=lambda r: r["quando"], reverse=True)[:8]]
        return {"ok": True, "periodo": periodo, "agora": agora.isoformat(timespec="minutes"), "resumo": res,
                "comparacao": comp, "por_numero": numeros, "barras": barras,
                "planos": sorted(planos.items(), key=lambda x: -x[1]), "ultimas": ultimas,
                "sem_valor": sum(1 for r in sel if r["valor"] is None),
                "funil": funil(periodo),
                "fonte": "mesma apuração da aba Vendas (renov_ledger + usados + marcador de venda nova), dia 00:00-23:59 America/Bahia"}


# ---------------------------------------------------------------- funil
_gestor_cache: dict[str, tuple[float, bool | None]] = {}


def _gestor_achou(tel: str):
    """True/False/None (None = não deu pra consultar). Cache: achou = sempre; não achou = 30 min."""
    tel = re.sub(r"\D", "", tel or "")
    if not tel:
        return None
    c = _gestor_cache.get(tel)
    if c and (c[1] is True or time.time() - c[0] < 1800):
        return c[1]
    res = None
    for q in [tel] + ([tel[2:]] if tel.startswith("55") else []):
        try:
            with urllib.request.urlopen(GESTOR + "?" + urllib.parse.urlencode({"query": q}), timeout=6) as r:
                j = json.loads(r.read().decode("utf-8", "ignore") or "{}")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                res = False
                continue
            res = None
            break
        except Exception:
            res = None
            break
        if int(j.get("matches_count") or 0) >= 1:
            res = True
            break
        res = False
    _gestor_cache[tel] = (time.time(), res)
    return res


_gestor_fila: set = set()
_gestor_thr = {"t": None}


def _gestor_bg():
    while True:
        try:
            tel = _gestor_fila.pop()
        except KeyError:
            time.sleep(5)
            continue
        try:
            _gestor_achou(tel)
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.3)


def _gestor_sem_esperar(tel: str):
    """FIX1710: só lê o cache; o que falta é consultado numa thread (a tela não espera o Gestor)."""
    tel = re.sub(r"\D", "", tel or "")
    if not tel:
        return None
    c = _gestor_cache.get(tel)
    if c and (c[1] is True or time.time() - c[0] < 1800):
        return c[1]
    _gestor_fila.add(tel)
    if _gestor_thr["t"] is None or not _gestor_thr["t"].is_alive():
        _gestor_thr["t"] = threading.Thread(target=_gestor_bg, daemon=True, name="gestor-funil")
        _gestor_thr["t"].start()
    return c[1] if c else None


def _testes() -> dict[str, float]:
    t: dict[str, float] = {}
    for d in _jl(ARQ_FUNIL):
        if d.get("etapa") != "teste":
            continue
        try:
            ts = float(d.get("ts"))
        except (TypeError, ValueError):
            continue
        cid = str(d.get("cid") or "")
        if cid and (cid not in t or ts < t[cid]):
            t[cid] = ts
    return t


def funil(periodo: str = "hoje") -> dict:
    agora = _agora()
    h0 = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    ini, fim = {"ontem": (h0 - timedelta(days=1), h0), "7d": (h0 - timedelta(days=6), agora)}.get(periodo, (h0, agora))
    a, b = ini.timestamp(), fim.timestamp() + 1
    leads = {c: v for c, v in QUEUE.leads.items() if a <= v["ts"] < b}
    testes = _testes()
    pag: dict[str, dict] = {}
    for r in _vendas():
        if r["conv"] and r["conv"] not in pag:
            pag[r["conv"]] = r
    por_inst: dict[str, dict] = defaultdict(lambda: {"leads": 0, "teste": 0, "pagou": 0, "cadastro": 0, "cadastro_sem_dado": 0})
    total = por_inst["__total"]
    consultas = 0
    for cid, l in leads.items():
        alvos = (por_inst[l["inst"]], total)
        for x in alvos:
            x["leads"] += 1
        if cid in testes and testes[cid] >= l["ts"] - 60:
            for x in alvos:
                x["teste"] += 1
        p = pag.get(cid)
        if p and p["quando"].timestamp() >= l["ts"] - 60:
            for x in alvos:
                x["pagou"] += 1
            tel = p["tel"] or l["tel"]
            achou = _gestor_sem_esperar(tel)  # FIX1710
            for x in alvos:
                if achou is True:
                    x["cadastro"] += 1
                elif achou is None:
                    x["cadastro_sem_dado"] += 1
    total = por_inst.pop("__total")
    etapas = [("leads", "Lead chegou"), ("teste", "Ganhou teste"), ("pagou", "Pagou"), ("cadastro", "Cadastro achado")]
    vaza = None
    pior = 1.1
    for i in range(1, 3):  # cadastro fica fora: fonte provisória
        de, para = total[etapas[i - 1][0]], total[etapas[i][0]]
        if de >= 3:
            taxa = para / de
            if taxa < pior:
                pior, vaza = taxa, f"{etapas[i - 1][1]} → {etapas[i][1]}"
    return {"periodo": periodo, "total": total, "etapas": etapas,
            "por_numero": [{"numero": k, **v} for k, v in sorted(por_inst.items(), key=lambda x: _ordem(x[0]))],
            "maior_vazamento": vaza, "taxa_vazamento": None if vaza is None else round(pior, 3),
            "erro": QUEUE.erro or None,
            "nota": ("Lead = conversa que abriu com \"Olá! Posso ter mais informações\" (anúncio). Teste = robô levou ao teste "
                     "(funil_eventos.jsonl). Pagou = comprovante renovado pelo fiscal na mesma conversa. Cadastro = o telefone "
                     "aparece no Gestor (provisório: o formulário funcional-test.emergent.host ainda não grava um registro que o painel leia).")}


# ---------------------------------------------------------------- saúde
def _servico(nome):
    try:
        r = subprocess.run(["systemctl", "is-active", nome], capture_output=True, text=True, timeout=3)
        return r.stdout.strip() or "desconhecido"
    except Exception:
        return "desconhecido"


_ia_cache = {"offset": 0, "ino": None, "dias": defaultdict(lambda: {"usd": 0.0, "n": 0}), "mods": defaultdict(lambda: defaultdict(float)), "eventos": []}


def _ia():
    c = _ia_cache
    try:
        st = ARQ_IA.stat()
    except OSError:
        return None
    ino = (st.st_dev, st.st_ino)
    if ino != c["ino"] or st.st_size < c["offset"]:
        c.update(ino=ino, offset=0, dias=defaultdict(lambda: {"usd": 0.0, "n": 0}), mods=defaultdict(lambda: defaultdict(float)), eventos=[])
    if st.st_size > c["offset"]:
        with ARQ_IA.open("rb") as fh:
            fh.seek(c["offset"])
            dado = fh.read(st.st_size - c["offset"])
        corte = dado.rfind(b"\n") + 1
        c["offset"] += corte
        for ln in dado[:corte].split(b"\n"):
            try:
                d = json.loads(ln)
            except ValueError:
                continue
            dia = str(d.get("t") or "")[:10]
            usd = float(d.get("usd") or 0)
            c["dias"][dia]["usd"] += usd
            c["dias"][dia]["n"] += 1
            c["mods"][dia][str(d.get("mod") or "?")] += usd  # FIX1710: por dia (antes acumulava desde o start)
            c["eventos"].append((str(d.get("t") or ""), usd))
        c["eventos"] = c["eventos"][-200000:]
    agora = _agora()
    dia = lambda k: c["dias"].get((agora.date() - timedelta(days=k)).isoformat(), {"usd": 0.0, "n": 0})
    hoje = dia(0)
    sete = sum(dia(k)["usd"] for k in range(1, 8)) / 7
    saldo = None
    try:
        s = json.loads(ARQ_SALDO.read_text())
        base, em = float(s.get("saldo_usd")), str(s.get("em") or "")
        gasto = sum(u for t, u in c["eventos"] if t >= em)
        restante = base - gasto
        saldo = {"restante_usd": round(restante, 2), "carregado_usd": base, "em": em,
                 "dias_restantes": round(restante / sete, 1) if sete > 0 else None}
    except Exception:
        saldo = None
    return {"hoje_usd": round(hoje["usd"], 2), "hoje_chamadas": hoje["n"], "ontem_usd": round(dia(1)["usd"], 2),
            "media_7d_usd": round(sete, 2), "modelos_hoje": sorted(((k, round(v, 2)) for k, v in c["mods"].get(agora.date().isoformat(), {}).items()), key=lambda x: -x[1])[:4],
            "fonte": "ia_uso.jsonl (custo por chamada; dia America/Bahia)",
            "saldo": saldo}


def _fiscal():
    agora = _agora()
    linhas = _cauda_txt(ARQ_FISCAL_LOG, 600_000)
    hh = agora.strftime("%H:%M:%S")
    lim = (agora - timedelta(hours=2)).strftime("%H:%M:%S")
    oks, falhas, ciclo, fila_alerta = [], 0, None, None
    for l in linhas:
        t = l[:8]
        recente = (lim <= t <= hh) if lim < hh else (t >= lim or t <= hh)
        m = re.search(r" FAST_WH webhook \S+ \S+ (ok|falhou) (\d+)s", l)
        if m and recente:
            if m.group(1) == "ok":
                oks.append(int(m.group(2)))
            else:
                falhas += 1
        m = re.search(r" ciclo ok em (\d+)s", l)
        if m:
            ciclo = {"hora": t[:5], "seg": int(m.group(1))}
        if " FILA_ALERTA " in l and recente and t >= (agora - timedelta(minutes=30)).strftime("%H:%M:%S"):
            fila_alerta = l[:200]
    oks.sort()
    # comprovante (msg do cliente) -> renovado, hoje
    h0 = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    esperas = []
    for r in _vendas():
        if r["quando"] < h0 or not r["msg_hora"]:
            continue
        try:
            mh = datetime.strptime(f"{agora.year} {r['msg_hora']}", "%Y %d/%m %H:%M").replace(tzinfo=TZ)
        except ValueError:
            continue
        m = (r["quando"] - mh).total_seconds() / 60
        if 0 <= m < 24 * 60:
            esperas.append(m)
    esperas.sort()
    dm = agora.strftime("%d/%m")
    manual = 0
    try:
        with ARQ_MANUAL.open(errors="ignore") as fh:
            manual = sum(1 for l in fh if l.startswith(dm))
    except OSError:
        pass
    hoje = agora.date().isoformat()
    parados = [p for p in _jl(ARQ_PARADO) if str(p.get("alerta_ts") or "").startswith(hoje)]
    # PARADOS_2010: agrupa por cliente e tira quem ja foi renovado depois do comprovante
    _cli = {}
    for p in parados:
        _t = "".join(ch for ch in str(p.get("telefone") or "") if ch.isdigit())[-8:]
        _c = str(p.get("conversa") or "")
        _ch = _t or _c
        _q = str(p.get("quando") or p.get("alerta_ts") or "")
        if _ch not in _cli or _q < _cli[_ch][2]:
            _cli[_ch] = (_t, _c, _q)
    _ren_t, _ren_c = {}, {}
    for u in _jl(ARQ_USADOS):
        if u.get("status") != "renovado":
            continue
        _ts = str(u.get("ts") or "")
        _t = "".join(ch for ch in str(u.get("telefone") or "") if ch.isdigit())[-8:]
        if _t:
            _ren_t[_t] = max(_ren_t.get(_t, ""), _ts)
        if u.get("conv"):
            _ren_c[str(u["conv"])] = max(_ren_c.get(str(u["conv"]), ""), _ts)
    def _menos30(q):  # tolerancia: o robo as vezes anota o comprovante minutos depois da renovacao
        try:
            return (datetime.fromisoformat(q[:19]) - timedelta(minutes=30)).isoformat()[:16]
        except Exception:
            return q[:16]
    abertos = [k for k, (_t, _c, _q) in _cli.items()
               if not ((_t and _ren_t.get(_t, "") >= _menos30(_q)) or (_c and _ren_c.get(_c, "") >= _menos30(_q)))]
    return {
        "fast_wh_mediana_s": oks[len(oks) // 2] if oks else None,
        "fast_wh_media_s": round(sum(oks) / len(oks)) if oks else None,
        "fast_wh_ok": len(oks), "fast_wh_falhou": falhas,
        "renov_mediana_min": round(esperas[len(esperas) // 2], 1) if esperas else None,
        "renov_n": len(esperas),
        "ciclo": ciclo, "fila_alerta": fila_alerta,
        "manual_hoje": manual, "parados_hoje": len(abertos), "abertos_agora": len(abertos), "alertas_hoje": len(parados), "clientes_alerta_hoje": len(_cli),
    }


def _robo_poll():
    for l in reversed(_cauda_txt(ARQ_LIVE, 200_000)):
        if " POLL pendentes=" in l:
            g = lambda k: (re.search(k + r"=(\d+)", l) or [None, None])[1]
            return {"hora": l[:5], "pendentes": g("pendentes"), "aguardando": g("aguardando"), "fila": g("fila"), "ocupadas": g("ocupadas")}
    return None


_saude_cache = {"t": 0.0, "v": None}


def saude() -> dict:
    with _trava:
        if _saude_cache["v"] and time.time() - _saude_cache["t"] < 10:
            return _saude_cache["v"]
        servs = [{"nome": n, "rotulo": r, "estado": _servico(n)} for n, r in SERVICOS]
        mt = _fim(ARQ_VIGIA_LOG)
        idade = None if mt is None else int(time.time() - mt)
        ult = (_cauda_txt(ARQ_VIGIA_LOG, 2000) or [""])[-1][:120]
        servs.insert(2, {"nome": "vigia_comprovante", "rotulo": "Vigia de comprovante (cron 5 min)",
                         "estado": "active" if idade is not None and idade < 11 * 60 else "parado",
                         "detalhe": f"última rodada há {idade // 60 if idade is not None else '?'} min · {ult}"})
        mq = _fim(ARQ_QUEUE)  # FIX1710: receptor "active" mas sem receber nada = problema
        for s_ in servs:
            if s_["nome"] == "mnrobo-receiver" and mq is not None:
                iq = int(time.time() - mq)
                s_["detalhe"] = f"último webhook do DataCrazy há {iq // 60} min ({datetime.fromtimestamp(mq, TZ).strftime('%d/%m %H:%M')})"
                if s_["estado"] == "active" and iq > 3600:
                    s_["estado"] = "sem dados"
        try:
            ia = _ia()
        except Exception as exc:  # noqa: BLE001
            ia = {"erro": exc.__class__.__name__}
        v = {"ok": True, "agora": _agora().isoformat(timespec="seconds"), "servicos": servs,
             "todos_ok": all(s["estado"] == "active" for s in servs),
             "ia": ia, "fiscal": _fiscal(), "robo": _robo_poll()}
        _saude_cache.update(t=time.time(), v=v)
        return v


# ---------------------------------------------------------------- alertas
_FORA_DESDE: dict = {}
def alertas() -> dict:
    with _trava:
        QUEUE.ler()
        agora = _agora()
        desde = agora - timedelta(hours=24)
        out = []
        for r in _vendas():
            if r["nova"] and r["quando"] >= desde:
                v = "sem valor" if r["valor"] is None else "R$ " + f"{r['valor']:.2f}".replace(".", ",")
                out.append({"id": "venda:" + r["quando"].isoformat() + r["conv"][-6:], "ts": r["quando"].isoformat(timespec="seconds"),
                            "tipo": "venda", "nivel": "bom", "titulo": f"Venda nova {v}",
                            "detalhe": f"{_num_venda(r)} · plano {r['plano'] or '?'} · final {r['tel'][-4:]}"})
        for p in _jl(ARQ_PARADO):
            q = _dt(p.get("alerta_ts"))
            if q and q >= desde:
                out.append({"id": "parado:" + str(p.get("alerta_ts")) + str(p.get("conversa") or "")[-6:], "ts": q.isoformat(timespec="seconds"),
                            "tipo": "parado", "nivel": "atencao",
                            "titulo": f"Comprovante parado há {p.get('minutos_parado', '?')} min",
                            "detalhe": f"{_numero(str(p.get('conversa') or ''))} · {p.get('fonte')} · final {str(p.get('telefone') or '')[-4:]} · {str(p.get('motivo') or '')[:110]}"})
        for l in _cauda_txt(ARQ_ALERTAS_VIGIA, 20_000):
            q = _dt(l[:19].replace(" ", "T"))
            if q and q >= desde and "RELIGANDO" in l:
                out.append({"id": "religa:" + l[:19], "ts": q.isoformat(timespec="seconds"), "tipo": "erro", "nivel": "ruim",
                            "titulo": "Robô travou e o vigia religou", "detalhe": l[20:180]})
        s = saude()
        for sv in s["servicos"]:  # ALERTA60_1910: só alerta se ficar fora do ar > 60 s (restart normal não conta)
            if sv["estado"] == "active":
                _FORA_DESDE.pop(sv["nome"], None)
                continue
            if time.time() - _FORA_DESDE.setdefault(sv["nome"], time.time()) < 60:
                continue
            if sv["estado"] != "active":
                out.append({"id": f"svc:{sv['nome']}:{agora.strftime('%Y%m%d%H')}", "ts": agora.isoformat(timespec="seconds"),
                            "tipo": "erro", "nivel": "ruim", "titulo": f"{sv['rotulo']} fora do ar",
                            "detalhe": f"estado: {sv['estado']}" + (f" · {sv.get('detalhe')}" if sv.get("detalhe") else "")})
        fa = (s.get("fiscal") or {}).get("fila_alerta")
        if fa:
            out.append({"id": "fila:" + agora.strftime("%Y%m%d") + fa[:5], "ts": agora.replace(hour=int(fa[:2]), minute=int(fa[3:5]), second=0, microsecond=0).isoformat(timespec="seconds"),
                        "tipo": "erro", "nivel": "atencao", "titulo": "Fiscal lento (ciclo demorou)", "detalhe": fa[9:120]})
        out.sort(key=lambda x: x["ts"], reverse=True)
        return {"ok": True, "agora": agora.isoformat(timespec="seconds"), "alertas": out[:60]}
