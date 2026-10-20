# Ideias por aba — painel GXTV

Texto para o Gustavo. Sem jargão. Cada ideia diz o que a pessoa vê na tela e por que fica mais fácil de ler no celular ou na TV da operação.

Há dois painéis:

- **Painel da raiz** (o de todo dia, porta 8741, endereço `https://mntv.tech/`).
- **Painel novo** (o paralelo, porta 8742, endereço `https://mntv.tech/v2`).

Os dois continuam no ar. Nada de número foi inventado: se a fonte não está na máquina, a tela diz **sem dado**.

## Mapa do que se repete

| O que aparece mais de uma vez | Onde | O que fazer |
| --- | --- | --- |
| Dinheiro de hoje, quantidade de pagamentos e comparação com ontem | Visão geral, aba Funil (que na verdade era um segundo painel de vendas) e aba Vendas | Um número grande na Visão geral. A lista de cada Pix fica só em Vendas. O Funil fica só com o caminho do cliente. |
| Funil (lead, teste, pagou) | Visão geral (um número), aba Funil, e no painel novo em Atendimento e Comercial | Visão geral mostra a conversão numa linha. O desenho do funil fica na aba Funil. No painel novo, Atendimento é o funil de conversa e Comercial é o funil de venda. Não são a mesma conta. |
| Mensagens por minuto e “quem escreveu” | Mensagens (Agora), Mensagens (Semana), bloco de pessoas atendidas, e no painel novo Início + Robô | Agora = o que está acontecendo neste minuto. Semana = o comparativo dos dias. Início do painel novo mostra o mesmo ritmo numa linha, sem repetir a tabela de cada WhatsApp. |
| Fila do robô, serviço fora do ar, envio | Visão geral, Saúde, e no painel novo Início, Robô e Espelho | Visão geral: está de pé ou não, e o medidor do teto de 240. Saúde: a lista de cada serviço e os erros. Robô: o que o robô está fazendo. Espelho: se o registro do webhook está atrasado. |
| Clientes ativos por painel | Ativos reais, e um resumo antigo escondido na visão geral | Só a aba Ativos reais conta P1, P2, P4, P5 e P6. P3 aparece apagado, com a palavra desligado. O painel novo não consulta o Sigma; ele avisa para olhar a aba da raiz. |
| Vendas 3619 e 0837 | Vendas da raiz e Comercial do painel novo | São a mesma venda vista de dois lugares. A raiz lê o livro local. O painel novo lê o Gestor. Se o Gestor cair, o painel novo diz indisponível e a hora da última atualização. Não publica zero. |
| Ranking de app | Apps na raiz e correlação de app na Operação do painel novo | Apps = qual app funciona em cada aparelho. Operação = em qual app o cliente reclamou. Não juntar os dois números. |
| Abas que saíram do menu (métricas gerais, lote de atenção, por conta, chats) | Ainda estão no código, escondidas | Continuam no programa para não perder histórico, mas não voltam para a barra. O que elas mostravam já aparece em Mensagens, Apps e Saúde. |

## O que esta versão já juntou

- A aba Funil deixou de repetir os cards de dinheiro, a lista dos últimos Pix e o gráfico de hora. Isso foi para Vendas e para a Visão geral.
- A Visão geral ganhou três gráficos ao vivo: vendas no dia, mensagens por minuto e o medidor de envio contra 240.
- A aba Mensagens escondeu o gráfico antigo de minuto (o de segundo a segundo continua) e mostra a linha dos últimos 60 minutos.
- Saúde ganhou o ritmo de envio e os alertas das últimas 12 horas.
- Ativos reais ganhou a barra por painel, com P3 desligado.
- A aba Ações voltou para o menu. Os botões continuam os mesmos: teste de 2 horas, renovar 30/60/90, liberar telas, pausar e soltar o robô.
- No celular, as abas ficam numa barra embaixo, com botão grande o bastante para o dedo.
- No painel novo, cada página ganhou um gráfico feito com os números que ela já buscava.

## Painel da raiz

### Visão geral

1. Deixar só cinco números grandes no topo: dinheiro de hoje, renovações, pessoas atendidas, quem espera mais de 15 minutos e quem vence hoje. O resto desce.
2. Pintar de verde o que está saudável, de amarelo o que pede olho e de vermelho o que está parado. A cor vale mais que o texto miúdo.
3. O gráfico de vendas do dia ocupa a largura da tela, com a hora atual marcada. Assim dá para ver se a tarde está melhor que a manhã sem abrir outra aba.
4. Ao lado, a linha de mensagens por minuto. Se ela dispara e a venda não sobe, o gargalo não é anúncio.
5. O medidor de envio mostra o número agora e a marca de 240. Perto do teto, o arco fica amarelo; em cima do teto, vermelho.
6. Os alertas das últimas 24 horas ficam numa lista curta, no máximo seis linhas. O sininho continua avisando o que é novo.
7. No celular, os cinco números viram uma coluna. Nada de tabela larga que obriga a rolar para o lado.
8. No modo TV, some o menu e os números crescem. A tela da parede não precisa de botão.
9. A faixa amarela “demonstração” só aparece quando o painel está com números de exemplo. Na VPS ela não liga.
10. Um toque no número de vendas abre a aba Vendas. Um toque na conversão abre o Funil. A visão geral não tenta ser as outras abas.

### Vendas

1. Três números no topo, sempre na mesma ordem: venda nova, renovação, total. O olho aprende o lugar.
2. O gráfico de pagamentos por hora fica em cima da tabela, não escondido no Funil.
3. O filtro Todas / Novas / Renovações vira botão grande, não texto pequeno.
4. A data fica com botão “Hoje” do lado, para não ter que abrir o calendário toda vez.
5. Cada linha da tabela mostra o final do telefone (final 9433), a hora do Pix, o valor e se foi nova ou renovação.
6. No celular, a tabela rola para o lado sem arrastar a página inteira, e o valor fica em negrito.
7. Venda nova e renovação usam duas cores fixas o mês inteiro, para não misturar com o verde de “serviço de pé”.
8. Se o marcador de venda nova parar, uma faixa avisa “o marcador está parado há X minutos” em vez de sumir com as vendas novas.
9. O total por WhatsApp (3619, 0837, 3166) fica numa linha, não num segundo painel.
10. Não repetir aqui o funil. Quem quer ver “quantos leads pagaram” vai na aba Funil.

### Funil

1. O desenho é uma escada: lead, teste, pagou, cadastro. A barra mais larga é o primeiro passo.
2. Em cada degrau, a frase “X% do passo anterior”, para ver onde a gente perde.
3. A frase “onde mais se perde gente” fica no título do gráfico, não numa nota de rodapé.
4. Uma linha só resume o dinheiro do período e a comparação com ontem. O detalhe de cada Pix não volta para cá.
5. A tabelinha por WhatsApp continua, porque o funil de 3619 não é o funil de 0837.
6. O passo “cadastro achado” fica marcado como provisório, do jeito que já era, para ninguém achar que o Gestor confirmou tudo.
7. Os botões Hoje, Ontem e 7 dias ficam no topo, com o mesmo desenho das outras abas.
8. No celular, a barra do funil ocupa a linha de baixo do nome, para o dedo não esconder o número.
9. Se o registro do webhook não estiver na máquina, a tela diz sem dado. Não desenha funil zerado.
10. A nota da fonte fica numa linha cinza no fim. Quem opera não precisa ler isso para decidir.

### Mensagens

1. A escolha Agora / Semana fica grudada no topo, com dois botões grandes.
2. Agora mostra a linha dos últimos 60 minutos (recebida e enviada) e, abaixo, o segundo a segundo dos últimos 2 minutos. O gráfico antigo de minuto saiu, porque era o mesmo número duas vezes.
3. Cada WhatsApp é um cartão: mensagens de hoje, clientes que escreveram, e há quanto tempo chegou a última.
4. “Pessoas atendidas hoje” fica numa faixa fina em cima, não como uma segunda página dentro da aba.
5. Semana compara esta semana com a passada em barras lado a lado. Dia futuro aparece como traço, não como zero.
6. Se um dia antigo não tem registro, a tela diz “sem registro”. Isso não é “zero mensagens”.
7. O filtro de WhatsApp na Semana são etiquetas que dá para ligar e desligar, com a opção Todas.
8. No celular, os cartões de WhatsApp empilham. O gráfico encolhe na largura sem cortar a legenda.
9. A atualização de Agora continua rápida. Semana pode esperar mais, porque o dia não muda a cada segundo.
10. Telefone de cliente não aparece inteiro nesta aba. O final basta para achar a conversa.

### Saúde

1. Uma fileira de luzes no topo: Robô, Fiscal, Receptor, Vigia. Verde é de pé, vermelho é fora.
2. O medidor de envio contra 240 fica grande, porque é a única coisa que pede ação imediata (esperar a fila baixar).
3. A linha do ritmo mostra a última hora. A marca vermelha tracejada é o teto.
4. O gráfico de alertas das últimas 12 horas mostra se o problema é agora ou se já passou.
5. Os cards de saldo de IA, tempo do fiscal e comprovante parado continuam, em duas colunas no celular.
6. “Sem dado” no saldo de IA continua com a frase de onde gravar o valor. Não vira zero.
7. Serviço fora do ar há menos de um minuto não pinta a tela de vermelho. O painel já espera 60 segundos para não gritar num reinício normal.
8. A nota técnica das fontes vai para o fim, em letra menor.
9. No modo TV, as luzes e o medidor ocupam a tela. A lista longa de log não.
10. Se o systemctl não responder nesta máquina, a luz diz “desconhecido”, não “caiu”.

### Apps

1. O aviso “precisa de decisão” fica no topo, com no máximo três frases. O resto fica dentro do card do aparelho.
2. Cada aparelho é um card: Samsung, LG, Fire Stick. A ordem do robô é a ordem das linhas.
3. A porcentagem de “funcionou” usa verde, amarelo e vermelho, e cinza quando há menos de 10 casos. Cinza não decide troca de app.
4. O logo do app fica à esquerda do nome, do tamanho de um polegar, para achar Max, IBO e UTRA sem ler.
5. Os botões 7 dias e 30 dias ficam juntos do botão Atualizar, com área de toque alta.
6. “Melhor agora” destaca o app que está ganhando no período, sem esconder a ordem que o robô usa hoje.
7. App proibido que ainda aparece nas fichas ganha uma frase de aviso, não uma coluna extra.
8. A tabela larga do placar antigo fica fechada em “Detalhes”. Quem quer o visual antigo ainda tem o botão.
9. No celular, o card ocupa a tela inteira. A coluna de histórico desce para baixo do nome, em vez de sumir para fora da tela.
10. Esta aba não muda a ordem do robô. A frase “só leitura” continua visível, para ninguém achar que o toque já trocou o app.

### Ativos reais

1. O gráfico de barras é a primeira coisa: P1, P2, P4, P5, P6. P3 aparece apagado, com a palavra desligado, e não entra na soma.
2. Dois números grandes em seguida: ativos no Sigma (sem teste) e pagou/renovou com registro.
3. Cada painel continua com o cartão: Sigma, pagou/renovou, sem registro curto, sem registro longo, testes e vencidos.
4. Alpha, Promo e Jorge ficam numa seção “outros”, fora do total, como já era.
5. Se o Sigma barrou a última passada, a faixa diz isso e o número mostrado é o anterior. Não zera o painel.
6. A hora da última contagem fica no título. A contagem demora minutos; o painel não finge que é segundo a segundo.
7. No celular, os cartões viram uma coluna. O número grande não quebra no meio.
8. “Sem dado ainda” permanece quando o arquivo da contagem não existe. A primeira contagem leva um tempo e isso é normal.
9. Não repetir aqui o dinheiro do dia. Ativo é cliente com acesso, não é venda de hoje.
10. Um painel com número antigo (a coleta falhou) fica com o cartão mais apagado, para não parecer fresco.

### Ações

1. A aba voltou para o menu. No celular ela é o último botão da barra de baixo.
2. A busca é um campo grande e um botão Buscar do mesmo tamanho. Enter no teclado também busca.
3. A ficha do cliente abre em linhas claras: usuário, plano, vencimento, telas, app, WhatsApp e última conversa.
4. Os botões estão em três grupos, com rótulo: Teste, Renovar, Telas e robô. Continua existindo teste de 2 horas, renovar 30, 60 e 90, liberar telas, pausar o robô e soltar o robô.
5. Nada acontece no primeiro toque. A tela pede “Sim, pode fazer”. Cancelar desfaz.
6. Número protegido mostra a ficha e avisa que os botões não mexem nele.
7. O resultado aparece numa faixa verde ou vermelha, em frase, não em código.
8. No celular, cada botão ocupa a largura da tela e tem altura de dedo.
9. A demonstração confirma o clique e avisa que nada foi enviado ao Sigma. Na VPS o mesmo botão mexe de verdade, com a mesma confirmação.
10. Painel e app do teste continuam nos dois seletores. O texto do botão de telas muda conforme o painel (4 ou 3).

## Painel novo (/v2)

### Início

1. O título do dia (Hoje, Ontem, 7 dias) fica grande, com os três botões logo abaixo.
2. A lista de WhatsApp, do maior volume para o menor, continua sendo o miolo. Os grupos Vendas, Cobrança, Suporte e RMKT não se misturam.
3. Os seis números (faturamento, renovações, vencem hoje, atendidos, esperando, clientes por minuto) ficam numa faixa, não repetidos dentro de cada linha.
4. O gráfico de mensagens por minuto usa a fila do webhook. Não busca conversa na API do DataCrazy.
5. O gráfico de envio contra 240 fica ao lado. A linha vermelha é o teto.
6. A barra de ativos por painel, quando é exemplo, deixa claro que o número oficial está na aba Ativos reais da raiz. O painel novo não consulta o Sigma.
7. Entrada ao vivo, log e saúde do espelho ficam em três colunas no computador e uma coluna no celular.
8. Telefone só como “final 9433”.
9. Se o Gestor estiver fora, a faixa diz indisponível e a hora da última leitura. O faturamento não vira R$ 0.
10. Quem está esperando mais de 15 minutos aparece numa caixa própria, curta, para não se perder no meio do log.

### Atendimento

1. O funil vira gráfico de barras: novo, em atendimento, aguardando cliente, resolvido.
2. Cada estágio continua clicável. O toque abre a lista daquelas conversas.
3. Os tempos média, mediana, P95 e máximo ficam em quatro cartões, na mesma ordem sempre.
4. A comparação com os 7 dias anteriores fica ao lado, não numa segunda página.
5. Não usar a palavra “abandonado”. O nome do estágio já diz o que está acontecendo.
6. Atualiza sozinho a cada 45 segundos, como já fazia.
7. No celular, os quatro estágios empilham em dois e dois, com número grande.
8. Se a fila do webhook não estiver na máquina, o gráfico diz sem dado.
9. A fonte (“webhook, não DataCrazy”) fica numa linha sob o título.
10. Exemplo de demonstração leva a palavra seed no subtítulo, para não parecer o dia real.

### Sem resposta

1. Se não há ninguém esperando, uma frase só: nenhum cliente esperando. Sem gráfico vazio ao lado.
2. Quando há casos, o gráfico mostra o motivo (robô ocupado, número sem mapa) antes da tabela.
3. A tabela traz final do telefone, WhatsApp, minutos de espera, motivo e a prova.
4. Caso de teste, sem Sigma, fica marcado na linha. Não entra como cliente pagante.
5. Atualiza a cada 60 segundos.
6. No celular, a tabela rola para o lado e o final do telefone fica fixo à esquerda se couber; se não couber, cada caso vira um cartão.
7. A hora da coleta aparece no subtítulo (“atualizado às …”).
8. Não chama o DataCrazy. Se o coletor ainda não rodou, a frase é “coletor ainda não rodou”, não zero.
9. Motivo e “pode reprocessar ou não” ficam na mesma linha, para não abrir outro painel.
10. Esta página não repete o “esperando 15 minutos” do Início. Aqui o corte é 3 minutos sem resposta do robô.

### Comercial

1. O título deixa claro: a venda nasce no Gestor.
2. O gráfico de vendas por hora só aparece quando existe série. Se o Gestor não manda a hora, a tela diz isso e o total continua no cartão. Não inventa a curva.
3. O gráfico por WhatsApp mostra 3619 e 0837 juntos, para não “perder” nenhuma das duas instâncias.
4. Vencem hoje continua com total, renovaram e pendentes. Pendente não é zero quando o Gestor está fora.
5. A lista de vendas mostra o final do telefone e o valor.
6. O funil de venda (lead, aparelho, app, teste, funcionou, pago) fica abaixo, separado do funil de atendimento.
7. O aviso de “sem resposta há mais de 3 minutos” nesta página é o mesmo alarme, não uma segunda contagem escondida.
8. Atualiza a cada 60 segundos.
9. No celular, os dois gráficos empilham. A tabela de vendas rola na horizontal.
10. Faixa do Gestor no topo quando ele está indisponível, com a hora do último dado bom.

### Operação

1. Quatro números no topo: problemas hoje, ontem, média de 7 dias e a diferença. A diferença positiva em tom de alerta, não em verde de venda.
2. O gráfico por hora mostra em que hora do dia (Bahia) o cliente reclama.
3. O gráfico por app mostra Max, IBO, Brasil e os outros que apareceram no texto. Isso não é o ranking de “qual app funciona”.
4. O bloco UTRA na LG continua separado, com sucesso, XC Account e falha. Ele só registra. Não troca a ordem do robô sozinho.
5. A frase do alerta (“se passar de metade com pelo menos 20 casos, avisa o Gustavo”) fica junto do número, não no manual.
6. Atualiza a cada 60 segundos.
7. No celular, os quatro números viram grade de dois.
8. Sem fila de webhook, a página diz indisponível. Não publica “zero problemas”.
9. Cruzamento app × aparelho × hora fica numa lista curta debaixo dos gráficos, só os maiores.
10. Filtro de WhatsApp do topo da página também vale aqui, para ver um número só.

### Robô

1. Três cartões com nome de gente: conversas que o robô está olhando, fila, mensagens enviadas. Sem sigla solta.
2. O gráfico de envio por minuto com a linha do teto 240 é o centro da página.
3. O gráfico de erros usa o log que o painel já lê. Se o log não está na máquina, diz sem dado.
4. Cada número tem o texto de ajuda do registro (o que é, de onde vem, como se conta).
5. O catálogo de métricas fica em cartões, não numa tabela que foge da tela.
6. Atualiza a cada 20 segundos, porque fila muda rápido.
7. No celular, os três cartões empilham e o gráfico ocupa a largura.
8. Exemplo de demonstração diz seed. Não parece o robô real.
9. Não mostrar “ocupadas = 0” quando o log não abriu. Mostrar indisponível.
10. Esta página não repete a luz de “serviço de pé” da Saúde da raiz. Aqui o assunto é o que o robô está fazendo agora.

### Espelho

1. Três leituras: atraso (lag), cobertura e o pacote de saúde. Cobertura em porcentagem, não em decimal 0,91.
2. O pacote de saúde vira uma grade de rótulos (atraso, eventos de hoje, fila presente) em vez de um bloco de código.
3. Atualiza a cada 20 segundos.
4. Deixa escrito que não há chamada de conversa ao DataCrazy.
5. Se a fila não existe, lag e cobertura dizem indisponível, com a hora se houver cache.
6. No celular, os três blocos empilham.
7. Não repetir aqui a lista de mensagens do Início. Espelho é a saúde do cano, não o conteúdo.
8. Número de exemplo leva a marca seed.
9. O botão de detalhe continua abrindo o drill-down de onde o número saiu.
10. Uma frase no rodapé: se o espelho atrasar, o Início também atrasou. Não são duas panes.

### Registro

1. No celular, cada métrica é um cartão: nome, o que significa, fonte e fórmula. A tabela larga fica só no computador.
2. Os filtros de módulo (início, atendimento, comercial…) são botões com altura de toque.
3. O botão deixa de se chamar “drill-down” na cara do Gustavo. No celular ele diz “ver de onde vem”.
4. A definição em português aparece antes da fórmula.
5. A busca visual por módulo evita uma lista de dezenas de linhas misturadas.
6. O fuso America/Bahia aparece uma vez no topo, não em cada linha.
7. Métrica sem linhas ainda explica o motivo, em frase, não numa janela vazia.
8. Não duplicar aqui os gráficos. Registro é o dicionário. O número ao vivo está na aba dele.
9. Ordenar por módulo, na ordem do menu, para achar sem ler o código do identificador.
10. Fonte “Gestor” e fonte “webhook” com duas cores leves, para não misturar venda com conversa.

### Entrar

1. A tela de entrar ocupa o centro, com o nome MN Tecnologia e a palavra Entrar grande.
2. Usuário e senha com campo alto. O teclado do celular não cobre o botão.
3. Erro de senha em frase curta, em vermelho, debaixo dos campos. Sem código.
4. O mesmo usuário do painel da raiz. A senha não fica escrita em arquivo do site.
5. No painel novo, a sessão é própria. Sair numa aba não precisa derrubar a outra, mas o botão Sair fica sempre à mão.
6. Fundo claro, igual ao resto do painel novo, para não parecer outro produto.
7. Botão Entrar na largura do cartão, no celular e no computador.
8. Se o servidor não responder, a frase é “não consegui falar com o servidor”, não uma página em branco.
9. Não guardar a senha na tela depois que entrou.
10. A demonstração local aceita a senha de teste só quando alguém liga isso de propósito. Na VPS essa porta fica fechada.

## O que não entra em gráfico

- Não criar número quando o arquivo não está na VPS.
- Não consultar a API de conversa do DataCrazy. Conversa só pelo registro do webhook.
- Não publicar 0 no lugar de “o Gestor está fora”.
- Não mostrar telefone completo. O final basta.
- O teto de 240 mensagens por minuto é a regra da operação. O gráfico mede o ritmo real e desenha essa marca. Ele não aumenta o teto.
