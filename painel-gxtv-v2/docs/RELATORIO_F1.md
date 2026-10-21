# Relatório F1 — Painel GXTV v2

**Branch:** `cursor/painel-gxtv-v2-f1-d777`  
**Pack:** `/workspace/painel_gxtv_v2`  
**Quando:** 05/10/2026 (America/Bahia)

## O que subiu (código)

Pacote completo F1, deployável em paralelo na VPS:

- Design system (IBM Plex + Source Serif, fundo atmosférico verde-óleo, tokens CSS)
- Registro único de **17 métricas** (nome, definição, fonte, fórmula, TZ, janela, last update)
- Envelope de estados: `loading | ok | empty | error | stale | unavailable`
- Gestor: cache + `unavailable` com last update (**nunca 0 inventado**)
- Timezone `America/Bahia`; telefone `final XXXX`
- Filtros globais (período, WhatsApp, atendente, app, aparelho)
- Auth usuário `gustavo` (mesmo login; env `/etc/painel-gxtv-v2.env`)
- SPA em `/v2` + API `/api/v2` (serviço `painel-gxtv-v2` porta 8787)
- Nav das abas Início/Atendimento/Comercial/Operação/Robô/Espelho/Registro (conteúdo F2–F6 placeholder)
- Scripts: `deploy/aplicar.sh`, nginx snippet, systemd unit, `notificar_f1.sh`
- Testes: 9/9 OK; build front OK; smoke local health/login/registry/shell/UI 200

## URL /v2

Após o coordenador aplicar na VPS + include nginx:

`https://<host-atual-do-painel>/v2`

(Login: `gustavo` + senha do painel atual, configurada em `/etc/painel-gxtv-v2.env`.)

## O que falta (este agente / ambiente)

1. **SSH da VPS ausente neste cloud agent** — chave `~/.ssh/mnrobo_vps` / secret `MNROBO_VPS_KEY` não disponível. Deploy real em `/opt/painel-gxtv-v2`, nginx reload e Telegram **pendentes do coordenador**.
2. Fases **F2–F7** (conteúdo real Início/Atendimento/Comercial/Operação/Robô + cron 23:55).
3. Alinhar senha/hash com o auth do painel v1; opcional `PAINEL_V1_TRUST_SESSION=1`.
4. Confirmar path real do espelho/meta na VPS (`ESPELHO_DIR`).
5. Endpoints Gestor concretos (path `/api/dashboard` é placeholder — ajustar ao API real do emergent.host).

## Riscos

- Nginx: `aplicar.sh` **não** edita o vhost automaticamente (evita derrubar o painel atual) — include manual do snippet.
- Sem senha em env + sem `PAINEL_V2_DEV_AUTH`, login falha (correto).
- Gestor path/API pode diferir → estado `unavailable` até calibrar (honesto).
- Seed só com `PAINEL_V2_SEED=1` (não ligar em produção sem querer).
- Memória: unit com `MemoryMax=512M` (independente do v1).

## Como o coordenador aplica

```bash
scp -r painel_gxtv_v2 root@179.236.239.192:/tmp/painel_gxtv_v2
bin/vps 'bash /tmp/painel_gxtv_v2/deploy/aplicar.sh /tmp/painel_gxtv_v2'
# copiar senha do painel atual → /etc/painel-gxtv-v2.env
# include /etc/nginx/snippets/painel-gxtv-v2.conf no vhost; nginx -t && reload
bin/vps 'bash /tmp/painel_gxtv_v2/deploy/notificar_f1.sh'
```

Painel atual (`painel-gxtv` na raiz) permanece intocado.
