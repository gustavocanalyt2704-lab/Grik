# MN Tecnologia — painel v2

Reestruturação completa do painel em rota paralela **`/v2`**. O painel atual na raiz permanece até o Gustavo aprovar a troca.

## Fases

| Fase | Escopo | Status pack |
|---|---|---|
| F1 | Design system, registro de métricas, fonte de verdade, TZ America/Bahia, estados loading/erro/vazio/atrasado/indisponível, filtros globais, auth gustavo | entregue |
| **F2** | Início + log ao vivo + entrada ao vivo + saúde do espelho | **este pack** |
| **F3** | Atendimento (funil + tempos) | **este pack** |
| **F4** | Comercial Gestor-first | **este pack** |
| **F5** | Operação | **este pack** |
| **F6** | Robô/IA + tooltips | **este pack** |
| **F7** | Relatório Telegram 23:55 Bahia | **este pack** |

## Regras duras

- Conversas: **só** webhook/espelho — zero GET DataCrazy de chat.
- Gestor = autoridade comercial; se cair → `unavailable` + last update, **nunca 0**.
- Telefone: `final 9433`.
- Sem rótulo "abandonado".
- Não reinicia mnrobo; não toca protegidos.

## Stack

- Front: React + Vite + TS + Tailwind + TanStack Query (+ ECharts nas fases de gráfico)
- Back: FastAPI em `127.0.0.1:8787`, nginx `/v2` + `/api/v2`

## Dev local

```bash
cd painel_gxtv_v2/backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
PAINEL_V2_DEV_AUTH=1 PAINEL_V2_SEED=1 uvicorn app.main:app --port 8787 --reload

cd ../frontend
npm install && npm run dev
# login: gustavo / dev
```

## Deploy VPS (coordenador)

```bash
# do workspace, com chave SSH:
scp -r painel_gxtv_v2 root@179.236.239.192:/tmp/painel_gxtv_v2
bin/vps 'bash /tmp/painel_gxtv_v2/deploy/aplicar.sh /tmp/painel_gxtv_v2'
# alinhar PAINEL_PASSWORD* com o painel atual em /etc/painel-gxtv-v2.env
# include nginx snippet + nginx -t && systemctl reload nginx
bin/vps 'bash /tmp/painel_gxtv_v2/deploy/notificar_f1.sh'
```

URL: `https://<host-do-painel>/v2`

## Testes

```bash
cd painel_gxtv_v2/backend && python3 -m unittest tests.test_f1_core tests.test_f2_inicio tests.test_f3_atendimento tests.test_f4_f7 -v
cd ../frontend && npm run build
```
