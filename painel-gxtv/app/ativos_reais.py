# -*- coding: utf-8 -*-
"""ATIVOS_REAIS_1210 — coletor de ativos reais por painel Sigma.

Roda como serviço separado (painel-gxtv-ativos). A cada ~10 min pagina
/customers?reseller=X&status=ACTIVE (20 por página, 1 GET a cada GAP s),
classifica e grava /var/lib/painel-gxtv/ativos_reais.json. O painel só lê
o arquivo (zero chamada ao Sigma na tela). 429/403 -> para a passada e
mantém o número anterior do painel. Nunca registra token/proxy.

Ativo real = status ACTIVE, vencimento (expires_at) no futuro, is_trial=NO,
e não é ativação de app MaxPlayer. Teste = is_trial=YES.
"""
import json, os, sys, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone

BASE = 'https://gerenciamento.sigmab.pro/api/integration/v1'
ROSTER = (('Painel01', 'P1'), ('painel2', 'P2'), ('painel3', 'P3'), ('Painel4', 'P4'),
          ('painel5', 'P5'), ('painel6', 'P6'), ('Alpha1', 'ALPHA'), ('Painelpromo', 'PROMO'),
          ('Jorge', 'JORGE'))
SAIDA = os.environ.get('ATIVOS_SAIDA', '/var/lib/painel-gxtv/ativos_reais.json')
GAP = float(os.environ.get('ATIVOS_GAP_S', '0.4'))  # FIX1710: era 2 s -> passada de ~1000 s com ciclo de 600 s
CICLO = float(os.environ.get('ATIVOS_CICLO_S', '600'))
PROXY_ARQ = '/etc/mnrobo-sigma-proxy.env'


class Barrado(Exception):
    pass


def _proxy():
    if os.path.exists('/etc/mnrobo/SIGMA_PROXY_OFF'):
        return ''
    p = (os.environ.get('SIGMA_PROXY') or '').strip()
    if p:
        return p
    try:
        for l in open(PROXY_ARQ, encoding='utf-8'):
            if l.startswith('SIGMA_PROXY='):
                return l.split('=', 1)[1].strip()
    except OSError:
        pass
    return ''


def get(path):
    tok = (os.environ.get('SIGMA_API_TOKEN') or '').strip()
    if not tok:
        raise RuntimeError('sem_token')
    req = lambda: urllib.request.Request(BASE + path, headers={'Authorization': 'Bearer ' + tok, 'Accept': 'application/json'})
    px = _proxy()
    try:
        if px:
            try:
                op = urllib.request.build_opener(urllib.request.ProxyHandler({'http': px, 'https': px}))
                with op.open(req(), timeout=25) as r:
                    return json.loads(r.read().decode('utf-8'))
            except urllib.error.HTTPError:
                raise
            except (urllib.error.URLError, OSError):
                pass
        with urllib.request.urlopen(req(), timeout=25) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise Barrado(str(e.code))
        raise RuntimeError('http_%s' % e.code)


def _ts(s):
    try:
        return datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except Exception:
        return None


def classificar(row, agora):
    if str(row.get('status') or '').upper() != 'ACTIVE':
        return None
    exp = _ts(row.get('expires_at'))
    if exp is None or exp <= agora:
        return 'vencido'
    if 'maxplayer' in (str(row.get('server') or '') + str(row.get('package') or '')).lower():
        return 'maxplayer'
    if str(row.get('is_trial') or '').upper() == 'YES':
        return 'teste'
    return 'real'


def contar(reseller, coletar=None):
    c = {'real': 0, 'teste': 0, 'maxplayer': 0, 'vencido': 0}
    pag, ult, vistos = 1, 1, set()
    while pag <= ult and pag <= 600:
        q = urllib.parse.urlencode({'reseller': reseller, 'status': 'ACTIVE', 'page': pag})
        corpo = get('/customers?' + q) or {}
        agora = datetime.now(timezone.utc)
        for row in corpo.get('data') or []:
            rid = row.get('id')
            if rid in vistos:
                continue
            vistos.add(rid)
            if coletar is not None:
                coletar.append(_enxuto(row))
            k = classificar(row, agora)
            if k:
                c[k] += 1
        ult = int((corpo.get('pagination') or {}).get('last_page') or 1)
        pag += 1
        time.sleep(GAP)
    c['sigma_total'] = len(vistos)
    # FIX1710: o Sigma tira do ACTIVE quem venceu (vira EXPIRED), então 'vencido' dava sempre 0.
    # 1 GET só: total de clientes EXPIRED do painel (venceram e não renovaram).
    try:
        q = urllib.parse.urlencode({'reseller': reseller, 'status': 'EXPIRED', 'page': 1})
        corpo = get('/customers?' + q) or {}
        c['vencido'] += int((corpo.get('pagination') or {}).get('total') or 0)
        time.sleep(GAP)
    except Barrado:
        raise
    except Exception as e:
        print('vencidos %s: %s' % (reseller, str(e)[:80]), flush=True)
    return c


def _ler():
    try:
        return json.load(open(SAIDA, encoding='utf-8'))
    except Exception:
        return {}


def _gravar(doc):
    tmp = SAIDA + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as h:
        json.dump(doc, h, ensure_ascii=False)
    os.replace(tmp, SAIDA)


def passada():
    antigo = {p.get('canon'): p for p in (_ler().get('paineis') or [])}
    inicio = time.time()
    paineis, barrado = [], False
    linhas = {}
    for user, canon in ROSTER:
        item = None
        if not barrado:
            try:
                linhas[canon] = []
                c = contar(user, linhas[canon] if V2 else None)
                item = dict(canon=canon, username=user, ok=True, atualizado=time.time(), **c)
            except Barrado as e:
                barrado = True
                print('sigma barrou (%s) em %s; mantenho anteriores' % (e, canon), flush=True)
            except Exception as e:
                print('falha %s: %s' % (canon, str(e)[:120]), flush=True)
        if item is None:
            item = dict(antigo.get(canon) or {'canon': canon, 'username': user})
            item['ok'] = False
        paineis.append(item)
    tot = lambda k: sum(int(p.get(k) or 0) for p in paineis)
    if V2:
        try:
            v2 = classificar_v2({c: r for c, r in linhas.items() if any(p['canon'] == c and p.get('ok') for p in paineis)},
                                datetime.now(timezone.utc))
            for p in paineis:
                if p['canon'] in v2:
                    p['v2'] = v2[p['canon']]
                elif not p.get('ok'):
                    p['v2'] = (antigo.get(p['canon']) or {}).get('v2')
                p['outro'] = p['canon'] in OUTROS
            principais = [p for p in paineis if not p['outro'] and p.get('v2')]
            outros = [p for p in paineis if p['outro'] and p.get('v2')]
            t2 = lambda k, ps: sum(int(p['v2'].get(k) or 0) for p in ps)
            _gravar({'versao': 2, 'gerado': time.time(), 'duracao_s': round(time.time() - inicio), 'paineis': paineis,
                     'total_sigma': t2('sigma', principais), 'outros_sigma': t2('sigma', outros), 'total_reais': t2('real', principais), 'total_sem_pag_curto': t2('sem_pag_curto', principais),
                     'total_sem_pag_longo': t2('sem_pag_longo', principais), 'total_testes': t2('teste', principais),
                     'total_maxplayer': t2('maxplayer', principais), 'total_duplicados': t2('duplicado', principais),
                     'total_vencidos': sum(int(p.get('vencido') or 0) for p in paineis if not p['outro']),
                     'outros_reais': t2('real', outros), 'dias_curto': DIAS_CURTO, 'barrado': barrado, 'ciclo_s': CICLO})
            return barrado
        except Exception as e:
            print('v2 falhou, gravo modo antigo: %s' % str(e)[:160], flush=True)
    _gravar({'gerado': time.time(), 'duracao_s': round(time.time() - inicio),
             'paineis': paineis, 'total_reais': tot('real'), 'total_testes': tot('teste'),
             'total_maxplayer': tot('maxplayer'), 'total_vencidos': tot('vencido'), 'barrado': barrado, 'ciclo_s': CICLO})
    return barrado



# ===== ATIVOS_REAIS_V2_1910 =====
# Ativo real = ACTIVE no Sigma + vencimento futuro + não teste + pagou/renovou (ledger
# fiscal_comprovante/usados.jsonl ou acoes/renov_ledger.jsonl). Teste também = nota
# "Teste Nh criado pelo robô" sem pagamento. Dedup por telefone (vencimento mais distante).
# JORGE/ALPHA/PROMO ficam em "outros painéis", fora do total. ATIVOS_REAIS_V2=0 volta ao antigo.
import re as _re
V2 = os.environ.get('ATIVOS_REAIS_V2', '1').strip() != '0'
LEDGER_DIR = os.environ.get('ATIVOS_LEDGER_DIR', '/opt/mnrobo/atendimento/')
OUTROS = ('JORGE', 'ALPHA', 'PROMO')
DIAS_CURTO = 35
_RX_INT = _re.compile(r'IZABEL\s+RAMOS|JORGE\s+OT[AÁ]VIO|MN\s*MEDIA', _re.I)
_RX_ROBO = _re.compile(r'teste\s*\d+\s*h.{0,40}criado pelo rob', _re.I | _re.S)
_RX_PKT = _re.compile(r'TESTE|TRIAL', _re.I)
_dig = lambda s: _re.sub(r'\D', '', str(s or ''))


def _tel(s):
    d = _dig(s)
    return d[-8:] if len(d) >= 8 else ''


def ledgers():
    pagou, paytel, interno, inttel, u2t = set(), set(), set(), set(), {}
    def linhas(p):
        try:
            for l in open(LEDGER_DIR + p, encoding='utf-8'):
                try:
                    yield json.loads(l)
                except Exception:
                    continue
        except OSError:
            return
    for x in linhas('fiscal_comprovante/usados.jsonl'):
        u, t = str(x.get('usuario') or ''), _tel(x.get('telefone'))
        if u and t:
            u2t.setdefault(u, t)
        if _RX_INT.search(str(x.get('nome') or '')):
            interno.add(u); inttel.add(t); continue
        if str(x.get('status', '')).startswith(('renov', 'ok', 'usado', 'conf')) or x.get('valor'):
            pagou.add(u); paytel.add(t)
    for x in linhas('acoes/renov_ledger.jsonl'):
        u, t = str(x.get('usuario') or ''), _tel(x.get('telefone'))
        if u and t:
            u2t.setdefault(u, t)
        if x.get('status') == 'renovado':
            pagou.add(u); paytel.add(t)
    for s in (pagou, paytel, interno, inttel):
        s.discard('')
    return pagou, paytel, interno, inttel, u2t


def _enxuto(r):
    # só o necessário (nunca guarda senha/m3u)
    return {k: r.get(k) for k in ('id', 'username', 'status', 'expires_at', 'server', 'package', 'is_trial', 'note')}


def classificar_v2(rows_por_canon, agora):
    pagou, paytel, interno, inttel, u2t = ledgers()
    cont = {c: dict(sigma=0, real=0, sem_pag_curto=0, sem_pag_longo=0, teste=0, maxplayer=0, interno=0, duplicado=0, sigma_total=len(rs))
            for c, rs in rows_por_canon.items()}
    cand = []
    for canon, rs in rows_por_canon.items():
        c = cont[canon]
        for r in rs:
            k = classificar(r, agora)
            if k in ('maxplayer', 'teste'):
                c[k] += 1
            if k != 'real':
                continue
            u = str(r.get('username') or '')
            nota = str(r.get('note') or '')
            t = u2t.get(u) or _tel((_re.search(r'\d{10,13}', nota) or [''])[0])
            if u in interno or (t and t in inttel):
                c['interno'] += 1; continue
            pago = u in pagou or bool(t and t in paytel)
            if not pago and (_RX_ROBO.search(nota) or _RX_PKT.search(str(r.get('package') or ''))):
                c['teste'] += 1; continue
            cand.append((canon, u, t, _ts(r.get('expires_at')), pago))
    # dedup por telefone (sem telefone: por username) dentro de cada grupo; fica o vencimento mais distante
    melhor = {}
    for it in cand:
        canon, u, t, exp, pago = it
        chave = ('o' if canon in OUTROS else 'p', ('t' + t) if t else ('u' + u))
        a = melhor.get(chave)
        if a is None or exp > a[3]:
            if a is not None:
                cont[a[0]]['duplicado'] += 1
            melhor[chave] = it
        else:
            cont[canon]['duplicado'] += 1
    for canon, u, t, exp, pago in melhor.values():
        c = cont[canon]
        c['sigma'] += 1
        if pago:
            c['real'] += 1
        elif (exp - agora).days <= DIAS_CURTO:
            c['sem_pag_curto'] += 1
        else:
            c['sem_pag_longo'] += 1
    return cont


def main():
    while True:
        t0 = time.time()
        try:
            barrado = passada()
        except Exception as e:
            print('passada falhou: %s' % str(e)[:160], flush=True)
            barrado = True
        espera = CICLO - (time.time() - t0)
        time.sleep(max(60 if not barrado else 900, espera))  # FIX1710: ciclo ~10 min de verdade


if __name__ == '__main__':
    if '--uma' in sys.argv:
        passada()
    else:
        main()
