# 30 requisitos do Gustavo — Painel GXTV v2

Checklist operacional. Fonte de implementação: registro de métricas + abas.

## Arquitetura e honestidade (1–8)

1. Central operacional profissional (não dashboard genérico de cartões soltos).
2. Abas: Início · Atendimento · Comercial · Operação · Robô · Espelho.
3. Leitura de conversas **só** via webhook/espelho — painel **nunca** consulta API DataCrazy de chat.
4. Gestor (`https://gestor-iptv-1.emergent.host`) = autoridade de venda/renovação/vencimento/faturamento (com cache).
5. Se Gestor cair → estado **indisponível + última atualização**, **nunca** publicar 0.
6. Timezone civil **America/Bahia** em todas as janelas e cron.
7. Telefone exibido só pelo final (`final 9433`).
8. Registro único de métricas (nome, definição, fonte, fórmula, timezone, janela, last update); tooltips/drill-down leem dele.

## UX e dados (9–16)

9. Estados honestos: loading · erro · vazio · atrasado · indisponível.
10. Filtros globais (período, número/WhatsApp, atendente, app, aparelho).
11. Funil clicável com drill-down paginado obrigatório.
12. Agregação no servidor/Supabase; SSE/Realtime só para ao vivo; resto cache curto.
13. Sem rótulo **"abandonado"** (usar termos operacionais claros).
14. Seed coerente só quando fonte real indisponível (marcado como seed/demo).
15. Versão nova em rota paralela `/v2` com mesmo login; raiz só após OK do Gustavo.
16. Deploy por fase sem derrubar o painel atual.

## Módulos (17–25)

17. **Início:** log operacional ao vivo + entrada ao vivo + saúde do espelho.
18. **Atendimento:** funil + tempo resposta média/mediana/P95/máx (agrupa msgs seguidas do mesmo lado).
19. **Comercial Gestor-first:** vendas (corrigir perda 3619/0837), vencem hoje (total/renovaram/pendentes), distribuição WhatsApp.
20. **Operação:** problemas vs ontem / média 7d; correlações app × aparelho × horário.
21. **Robô/IA:** nomes claros + tooltips (do registro).
22. **Espelho:** saúde, lag, cobertura webhook.
23. Relatório diário Telegram via cron VPS 23:55 Bahia.
24. Avisar Gustavo no Telegram a cada fase.
25. Não mexer em protegidos mnrobo; não reiniciar mnrobo no pico 17–21 Bahia sem ocupadas~0.

## Entrega técnica (26–30)

26. Stack front: React + Vite + TS + Tailwind (+ shadcn-like) + TanStack Query + ECharts.
27. Branch `cursor/*-d777`; commit/push; PR só se pedirem.
28. Sem SSH privado no git.
29. Drill-down em todo número clicável relevante.
30. Coordenador revisa e faz deploy; agente paralelo entrega pacote testável.
