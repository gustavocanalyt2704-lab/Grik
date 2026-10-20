# Painel GXTV — o que mudou

Tela nova, em português, para o Gustavo resolver sem chamar ninguém.

## O que aparece na tela

A primeira tela mostra só cinco números grandes: dinheiro de hoje, renovações, atendidos, quem está esperando há mais de 15 minutos, e quem vence hoje. O resto do dia (gráficos, rotinas, o que acabou de acontecer) fica atrás de **Ver o resto do dia**.

Cada conversa tenta mostrar o WhatsApp que atendeu (3619, 0837, 3166…). Enquanto o robô não gravar isso, aparece **sem número**, pequeno e discreto.

A aba **Ações** busca um cliente pelo telefone ou pelo usuário e mostra a ficha: usuário, plano, vencimento, telas, app, última conversa e o WhatsApp. Dá para criar teste de 2 horas, renovar 30, 60 ou 90 dias, liberar as telas do plano e pausar ou soltar o robô **só para aquele cliente**. Toda ação pergunta antes ("Renovar fulano por 30 dias?") e depois diz em uma frase se deu certo.

Cliente pago no painel principal recebe 4 telas. Teste grátis fica com 1 tela; XCIPTV pode ficar com 4. A promo de 3 telas é o painel **Promo 3 telas**. Se ele ainda não estiver configurado na máquina, a tela avisa e não mexe em nada.

Números protegidos (*0424, *0555, *6098 e 5524988462124) podem ser vistos. O painel não renova, não cria teste e não pausa esses números.

## Vendas novas e vencimento

Antes, esses cartões só olhavam uma marca do resumo do dia. Se a marca vinha apagada, aparecia "sem dado", mesmo com a lista de clientes gravada ao lado. Agora o painel lê a lista, nesta ordem: lista completa, cadastro antigo, lista incompleta, cache por usuário. Se a lista está pela metade, o número aparece com o aviso de que pode subir.

O script `deploy/diagnostico_sigma.sh` só lê a máquina e diz onde quebra (arquivo ausente, sem permissão, pausa do Sigma, ou um processo de root gravando o contador). Não imprime senha. Rode na VPS e cole o texto de volta.

## Campo do WhatsApp

O painel lê, nesta ordem, o que já existir:

- no registro do robô `acoes.jsonl`, o campo **`instancia`**
- se esse campo ainda não vier, também aceita `numero_whatsapp`, `whatsapp_instancia` e `instance`
- se um dia a conversa no banco tiver a coluna `espelho.conversas.instancia`, o painel usa também

O outro trabalho (fazer o robô gravar a instância) continua do lado de lá. Aqui a tela já está pronta.

## O que ficou de fora

Ideia, ainda sem botão:

- **Pagamentos** — conferir ou lançar um Pix na mão
- **Serviços** — ligar ou desligar um serviço da máquina
- **Regras e textos** — mudar o que o robô fala
- **Anúncios** — mandar aviso para vários clientes

O painel não pausa ninguém sozinho. Pausar é sempre um botão, para um cliente só.

## Instalar

O pacote é `deploy/painel_v6.tgz`. Na VPS:

```bash
bash deploy/deploy_painel_v6.sh --dry-run
bash deploy/deploy_painel_v6.sh
```

O dry-run não muda nada. A instalação de verdade guarda uma cópia em `/var/backups/painel-gxtv/` e não troca a senha se ela já existe. Para desfazer: `bash deploy/rollback_painel_v6.sh`.

A chave do Sigma continua onde o robô já lê (`SIGMA_API_TOKEN` no ambiente da máquina). A da promo, quando existir, é `SIGMA_PROMO_TOKEN`. Nada disso entra no código nem no registro das ações.
