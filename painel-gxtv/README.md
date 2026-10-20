# Painel GXTV

Painel da operação de IPTV. A tela mostra o dia em frases simples e, na aba Ações, busca um cliente, cria teste, renova, libera telas e pausa o robô para uma pessoa só.

O que mudou na tela, o que ficou de fora e como instalar na VPS estão no `LEIAME.md`.

## Rodar os testes

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest
```

## Ver aqui, sem a VPS

Sem os arquivos da VPS a tela mostra "sem dado" e o motivo, em vez de número inventado. Para subir localmente:

```bash
.venv/bin/python -m app.definir_senha /tmp/painel-senha.txt
PAINEL_TLS=0 PAINEL_COLETAR=1 .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8741
```
