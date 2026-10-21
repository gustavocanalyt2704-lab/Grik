# Painel GXTV

Dois painéis da operação da MN Tech (GXTV), em português.

- `painel-gxtv/` é o painel da raiz. FastAPI na porta 8741. O Caddy manda `https://mntv.tech/` para ele.
- `painel-gxtv-v2/` é o painel novo. FastAPI na porta 8742, tela em `/v2`. O Caddy manda `/v2` e `/api/v2` para ele.

Como copiar para a VPS e como voltar atrás: [docs/DEPLOY.md](docs/DEPLOY.md).

O que se repete entre as abas e dez ideias de leitura para cada uma: [docs/IDEIAS_POR_ABA.md](docs/IDEIAS_POR_ABA.md).

`PAINEL_DEMO=1` (raiz) e `PAINEL_V2_SEED=1` (novo) só servem para ver a tela com números de exemplo. Na VPS os dois ficam desligados.
