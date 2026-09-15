---
name: Mesa Certa
description: Assistente do Mesa Certa. O chat é a página, no padrão que ChatGPT e Claude consagraram.
colors:
  bg: "#faf9f6"
  surface: "#ffffff"
  surface-2: "#f2efe9"
  surface-3: "#ebe7df"
  border: "#e5e1d9"
  border-strong: "#d3cdc2"
  text: "#1f1e1c"
  text-2: "#55524c"
  text-3: "#736f68"
  accent: "#c2461c"
  accent-hover: "#a63a15"
  accent-soft: "#f7e6dd"
  accent-text: "#9c3713"
  ok: "#2f6b4f"
  ok-soft: "#e3efe8"
  warn-soft: "#f6ecd9"
  warn-text: "#7a5410"
  danger-soft: "#f6e1dc"
  danger-text: "#9b2f1d"
typography:
  display:
    fontFamily: "Inter Tight, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "clamp(1.75rem, 3.6vw, 2.35rem)"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  data-display:
    fontFamily: "JetBrains Mono, ui-monospace, Cascadia Mono, Consolas, monospace"
    fontSize: "1.85rem"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "0.08em"
  title:
    fontFamily: "Inter Tight, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "0.98rem"
    fontWeight: 620
    lineHeight: 1.4
  body-lg:
    fontFamily: "Inter Tight, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.55
  body:
    fontFamily: "Inter Tight, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.65
  label:
    fontFamily: "Inter Tight, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "0.88rem"
    fontWeight: 520
    lineHeight: 1.4
  caption:
    fontFamily: "Inter Tight, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 400
    lineHeight: 1.45
  data:
    fontFamily: "JetBrains Mono, ui-monospace, Cascadia Mono, Consolas, monospace"
    fontSize: "0.74rem"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  s: "8px"
  m: "14px"
  l: "22px"
  pill: "999px"
spacing:
  pad: "1rem"
  thread-gap: "1.75rem"
  coluna: "48rem"
components:
  button-send:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    rounded: "{rounded.pill}"
    size: "2.25rem"
  button-send-hero:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    rounded: "{rounded.pill}"
    size: "2.5rem"
  button-send-hover:
    backgroundColor: "{colors.accent-hover}"
  button-send-disabled:
    backgroundColor: "{colors.surface-3}"
    textColor: "{colors.text-3}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.text-2}"
    typography: "{typography.label}"
    rounded: "{rounded.s}"
    padding: "0.45rem 0.7rem"
  button-ghost-hover:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.text}"
  button-outline:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-2}"
    rounded: "{rounded.s}"
    padding: "0.4rem 0.7rem"
  button-outline-hover:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.text}"
  composer-hero:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    typography: "{typography.body-lg}"
    rounded: "{rounded.l}"
    padding: "1.15rem 1.25rem 0.35rem"
    height: "6.5rem"
  composer-dock:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    typography: "{typography.body}"
    rounded: "{rounded.l}"
    padding: "0.85rem 0.5rem 0.85rem 1.1rem"
    height: "3.25rem"
  chip-suggestion:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-2}"
    rounded: "{rounded.pill}"
    padding: "0.45rem 0.8rem"
  chip-suggestion-hover:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.text}"
  chip-source:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-2}"
    rounded: "{rounded.s}"
    padding: "0.3rem 0.65rem"
  bubble-user:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.text}"
    typography: "{typography.body}"
    rounded: "{rounded.l}"
    padding: "0.7rem 1.05rem"
  card-reservation:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.m}"
    width: "34rem"
  card-reservation-header-criada:
    backgroundColor: "{colors.ok-soft}"
    textColor: "{colors.ok}"
    padding: "0.65rem 1rem"
  notice:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.m}"
    padding: "0.9rem 1rem 1rem"
  notice-atencao:
    backgroundColor: "{colors.warn-soft}"
    textColor: "{colors.warn-text}"
  notice-erro:
    backgroundColor: "{colors.danger-soft}"
    textColor: "{colors.danger-text}"
  badge-held:
    backgroundColor: "{colors.warn-soft}"
    textColor: "{colors.warn-text}"
    rounded: "{rounded.pill}"
    padding: "0.25rem 0.6rem"
---

# Design System: Mesa Certa

## Overview

**Creative North Star: "A conversa em papel quente"**

O chat é a página. A interface segue o padrão que ChatGPT e Claude consagraram: coluna central única, marca pequena no topo, o campo de mensagem como o objeto mais importante da tela e a resposta do assistente em texto corrido, sem balão. O calor vem do fundo quase branco puxado para o creme e de uma única brasa que acende onde algo acontece: enviar, foco, o assistente pensando, a relevância de uma fonte.

A densidade é de leitura, não de painel. Tudo o que é dado técnico (código de reserva, ids de trace e de chunk, argumentos de tools) mora em JetBrains Mono e fica recolhido nos Bastidores, um painel lateral que só abre quando pedido. Superfícies são brancas sobre o fundo quente, separadas por bordas finas de 1px; sombra só existe em dois objetos que precisam flutuar (o campo de mensagem e o cartão de reserva) e no painel lateral.

A direção recusa site de restaurante (sem fotos, sem hero editorial, sem cardápio diagramado como identidade) e recusa painel técnico (sem grades de métricas na primeira vista). A primeira direção autoral, "Grelha de brasa", foi descartada pelo usuário por tirar o foco do chat; o que sobrevive dela é só a marca de chama sobre grelha, em traço.

**Key Characteristics:**
- Coluna central de 48rem; conversa rola atrás de degradês no topo e sob o campo ancorado.
- Um acento só (brasa), usado em pontos pequenos; nunca como área grande.
- Assistente sem balão, cliente em balão discreto de superfície tonal.
- Inter Tight para toda a interface; JetBrains Mono restrito a dado real.
- Bordas finas e superfícies brancas no lugar de sombras; três sombras nomeadas e só três.
- Movimento curto de saída (ease out forte), com redução total em `prefers-reduced-motion`.

## Colors

Neutros quentes de papel com uma brasa única de acento e três famílias de estado em tons suaves.

### Primary
- **Brasa** (accent): o botão de enviar, o anel de foco global, o cursor de digitação, os três pontos do "pensando", a marca de chama na barra e no avatar, e o preenchimento da barra de relevância dos chunks.
- **Brasa Funda** (accent-hover): hover do botão de enviar. Nada mais.
- **Brasa Rosada** (accent-soft): seleção de texto, o disco atrás da marca na saudação e o avatar aceso do assistente.
- **Brasa Escrita** (accent-text): texto e ícone sobre accent-soft e o estado ativo do botão "ver bastidores".

### Neutral
- **Papel Quente** (bg): fundo da página, do rodapé do cartão de reserva e do bloco de argumentos nos Bastidores. Também é a cor de destino do degradê sob o campo ancorado.
- **Branco de Superfície** (surface): campo de mensagem, cartões, chips, avisos, painel lateral.
- **Linho** (surface-2): balão do cliente, hover de botões fantasma e chips, selo "demo" na barra.
- **Linho Escuro** (surface-3): botão de enviar desabilitado e trilho da barra de relevância.
- **Borda** (border): toda borda de 1px em repouso e todo divisor interno.
- **Borda Firme** (border-strong): borda do campo em foco, hover de chip, contorno do botão de ação do aviso, sublinhado de links e thumb da barra de rolagem.
- **Tinta** (text): texto principal. **Tinta Média** (text-2): texto secundário, rótulos de botão, corpo de aviso. **Tinta Clara** (text-3): legendas, placeholders, metadados, marcadores de lista.

### Estados
- **Verde Confirmado** (ok, ok-soft): cabeçalho do cartão de reserva criada e selo "ok" de tool nos Bastidores.
- **Âmbar de Atenção** (warn-soft, warn-text): aviso de atenção e o selo de mensagem retida pela proteção contra injeção.
- **Vermelho de Erro** (danger-soft, danger-text): aviso de erro, status de reserva cancelada, falha de tool, borda do campo inválido.

### Named Rules
**The Brasa Pequena Rule.** O acento sólido só aparece em objetos pequenos (botão de enviar de 2.25rem a 2.5rem, pontos de 6px, trilho de 5px, marca de 28px, anel de foco de 2px). Área grande em brasa sólida não existe neste sistema; quando o acento precisa de área, usa accent-soft.

**The Estado Suave Rule.** Estados (ok, atenção, erro) se expressam como fundo suave com texto escuro da mesma família, e a borda do contêiner, quando tingida, usa a cor de texto a 16% ou 18% de opacidade. Nunca fundo saturado com texto branco.

## Typography

**Display Font:** Inter Tight (com system-ui, -apple-system, Segoe UI, sans-serif)
**Body Font:** Inter Tight (mesma pilha)
**Label/Mono Font:** JetBrains Mono (com ui-monospace, Cascadia Mono, Consolas, monospace)

**Character:** Uma grotesca neutra e compacta, no registro dos chats da categoria, que some atrás do conteúdo. A mono entra como marca de verdade: onde ela aparece, o texto é dado que veio do sistema.

### Hierarchy
- **Display** (600, clamp(1.75rem, 3.6vw, 2.35rem), 1.15, -0.02em): só a saudação do estado vazio, com `text-wrap: balance`.
- **Data Display** (JetBrains Mono 600, 1.85rem, 1.1, 0.08em): o código da reserva no cartão. Cancelada, vira text-3 com risco de 2px.
- **Title** (620, 0.98rem a 1rem): nome da marca na barra, título do painel Bastidores, títulos de aviso (600). Valores de fatos do cartão e das estatísticas usam 0.98rem em 560 a 580.
- **Body Large** (400, 1.0625rem a 1.125rem, 1.55): subtítulo da saudação (máximo 40ch) e o texto do campo de mensagem no estado vazio.
- **Body** (400, 1rem, 1.65 na resposta do assistente, 1.55 no balão e no corpo base): conversa. Negrito em 620.
- **Label** (500 a 560, 0.82rem a 0.9rem): botões fantasma e contornados, chips de sugestão (0.9rem, 500) e de fonte (0.82rem), status do cartão (0.9rem, 600).
- **Caption** (400, 0.74rem a 0.82rem, text-3): rótulos de fatos (0.76rem), metadados da resposta com números tabulares (0.78rem), aviso legal sob o campo (0.74rem), status do campo (0.8rem).
- **Data** (JetBrains Mono, 0.72rem a 0.82rem): id de trace, nome de tool (600), argumentos, ids de chunk em duas linhas (fonte em 600 e caminho em text-3).

### Named Rules
**The Mono É Dado Rule.** JetBrains Mono só aparece em valor que o sistema produziu: código de reserva, ids, nomes e argumentos de tools, trace. Rótulos, títulos e prosa ficam sempre em Inter Tight, mesmo dentro dos Bastidores.

**The Números Tabulares Rule.** Todo número que muda ou se compara (segundos pensando, milissegundos, scores, estatísticas, metadados) usa `font-variant-numeric: tabular-nums`.

## Layout

Uma tela em grade de três linhas (barra, conversa, campo) com altura de `100dvh`. A conversa ocupa uma coluna central de até 48rem com respiro lateral de 1rem; mensagens se empilham com 1.75rem entre si. O estado vazio usa coluna de 46rem centralizada vertical e horizontalmente: marca em disco, saudação, subtítulo, campo grande e as quatro sugestões logo abaixo, em uma linha só no desktop.

O campo ancorado fica na mesma coluna, com um degradê de 2rem do fundo transparente para bg por cima dele, e a lista rola por baixo. No topo, a lista entra por uma máscara de 1.75rem. A área do campo respeita `safe-area-inset-bottom`, e a barra respeita `safe-area-inset-top`.

A resposta do assistente é uma grade de avatar de 2rem e conteúdo, com 0.9rem de intervalo; o balão do cliente alinha à direita com largura máxima de min(85%, 36rem).

Responsivo, observado no build:
- **até 440px:** botões da barra perdem o rótulo e ficam só com ícone.
- **até 520px:** o estado vazio desce o bloco para a base da tela (perto do polegar), o avatar do assistente some e a resposta ocupa a largura toda, o balão vai a 90%, os fatos do cartão passam a duas colunas, as dicas de teclado e o selo "demo" somem.
- **até 640px:** Bastidores ocupa a tela inteira.
- **até 720px:** as sugestões podem quebrar em duas linhas, sem partir rótulos.
- **a partir de 1100px:** com Bastidores aberto, a conversa recua 27rem à direita em vez de ficar coberta.

## Elevation & Depth

Sistema híbrido e contido: a profundidade vem sobretudo de superfícies brancas sobre o papel quente e de bordas de 1px. Sombra existe em três lugares, todas difusas, de opacidade baixa e tingidas pela cor da tinta (31 30 28), nunca pretas puras.

### Shadow Vocabulary
- **Campo** (`box-shadow: 0 1px 2px rgb(31 30 28 / 0.04), 0 10px 30px -14px rgb(31 30 28 / 0.18)`): o campo de mensagem, nas duas formas. Em foco soma um halo de 4px de brasa a 8% (`0 0 0 4px rgb(194 70 28 / 0.08)`).
- **Cartão** (`box-shadow: 0 1px 2px rgb(31 30 28 / 0.04), 0 4px 14px -8px rgb(31 30 28 / 0.12)`): cartão de reserva.
- **Painel** (`box-shadow: -12px 0 32px -24px rgb(31 30 28 / 0.35)`): borda esquerda do painel Bastidores.

### Named Rules
**The Só Flutua Quem Age Rule.** Sombra é reservada ao campo de mensagem, ao cartão de reserva e ao painel lateral. Chips, avisos, balões e botões ficam planos, separados por borda ou por tom.

**The Degradê No Lugar do Corte Rule.** Onde conteúdo rolável encontra uma borda (topo da conversa, base sob o campo, limite de altura do campo), ele some num degradê em vez de ser cortado seco.

## Shapes

Quatro raios com papéis fixos. **Pill** (999px) para tudo que é circular ou selo: botão de enviar, chips de sugestão, avatar, disco da marca, selos de status, pontos, trilhos. **Grande** (22px) para as formas que carregam fala: o campo de mensagem e o balão do cliente. **Médio** (14px) para contêineres de conteúdo: cartão de reserva e avisos. **Pequeno** (8px) para controles retangulares e blocos de dado: botões fantasma e contornados, chips de fonte, bloco de argumentos.

Bordas são sempre de 1px. Divisores internos (cabeçalho e rodapé do cartão, seções dos Bastidores) usam a mesma borda. Contêineres com faixas internas cortam o conteúdo (`overflow: hidden`) para que o fundo da faixa siga o raio.

Iconografia em traço (lucide) com o mesmo peso visual da marca própria, que é uma chama sobre três barras de grelha desenhada em traço de 1.5.

## Components

### Buttons
Discretos, com uma única exceção que brilha.
- **Shape:** circular para enviar (999px); retangular suave para o resto (8px).
- **Enviar:** círculo de brasa com seta branca, 2.25rem no campo ancorado e 2.5rem no estado vazio. Hover escurece para accent-hover; ativo encolhe para 0.94; desabilitado vira surface-3 com seta text-3. Transições de 160ms.
- **Fantasma:** fundo transparente, texto text-2, peso 520; hover e estado expandido ganham surface-2 e texto text. Usado na barra ("Nova conversa", "Bastidores"), no fechar do painel e no "ver bastidores" da resposta, que ativo usa accent-text.
- **Contornado:** superfície branca com borda de 1px (border no botão copiar, border-strong na ação do aviso), hover para surface-2.
- **Focus:** anel global de 2px em brasa com 2px de afastamento, em qualquer elemento focável.

### Chips
- **Sugestão:** pílula branca com borda de 1px, ícone e rótulo em text-2 (0.9rem, 500), sem quebra interna do rótulo. Hover: surface-2, border-strong, texto text. Desabilitado a 55%.
- **Fonte:** retângulo de 8px, borda de 1px, ícone de documento em text-3, nome do documento em text (580) e seção truncada com reticências (quebra normal no mobile). Não é interativo.

### Cards / Containers
- **Cartão de reserva:** 14px, superfície branca, borda de 1px, sombra de cartão, largura máxima de 34rem. Cabeçalho com status e ícone (reserva criada ganha fundo ok-soft e texto ok; cancelada, texto danger-text; consultada, texto normal). Linha do código em mono grande com botão copiar (oculto quando cancelada). Fatos em quatro colunas (duas no mobile) com rótulo caption e valor 560. Rodapé em bg com as condições, 0.84rem text-2.
- **Aviso:** 14px, grade de ícone e texto, padding 0.9rem 1rem 1rem. Neutro em branco; atenção e erro com fundo suave, borda tingida e ícone na cor de texto da família. Id de trace em mono quando houver.

### Inputs / Fields
- **Campo de mensagem (estrela da tela):** superfície branca, 22px, borda de 1px, sombra de campo. No estado vazio é alto (6.5rem, texto 1.125rem, 5rem e 1.0625rem no mobile) com barra inferior de status e botão. Ancorado, vira uma linha só com o botão à direita e o status só aparece quando há o que dizer.
- **Focus:** borda passa a border-strong e soma halo de brasa a 8%; o contorno do textarea é suprimido porque o contêiner carrega o foco. Cursor em brasa.
- **Limite de altura:** o texto rola e a base some num degradê de máscara.
- **Inválido:** borda em danger-text e mensagem de status em danger-text, peso 550.

### Navigation
- **Barra do topo:** sem fundo nem borda, altura mínima de 3.5rem. À esquerda a marca de chama em brasa, o nome em 1rem/620 e o selo "demo" em pílula surface-2. À direita, botões fantasma com ícone e rótulo, que perdem o rótulo abaixo de 440px.

### Resposta do assistente
Sem balão: avatar circular de 2rem com a marca em brasa (aceso com accent-soft enquanto pensa), texto corrido em body 1.65, listas com marcador text-3, telefone auto-linkado sem quebra. Abaixo, fontes, cartão de reserva quando houver, e uma linha de ações com "ver bastidores" e metadados tabulares. Entra com subida de 6px e fade em 320ms. O estado "pensando" mostra três pontos de brasa pulsando (1.2s, defasados em 0.15s) e os segundos decorridos.

### Bastidores
Painel lateral fixo de 27rem que entra deslizando 16px em 240ms. Seções separadas por borda: tools com nome em mono, selo ok e milissegundos; argumentos em bloco mono sobre bg; recuperações com a consulta em texto e cada chunk como fonte e caminho em mono, trilho de relevância de 5px com preenchimento em brasa e score tabular; estatísticas em duas colunas.

## Do's and Don'ts

### Do:
- **Do** manter o campo de mensagem como o maior e mais elevado objeto da tela, com raio de 22px e a sombra de campo.
- **Do** usar brasa sólida só em objetos pequenos (enviar, foco, pontos, trilho, marca) e accent-soft quando o acento precisar de área.
- **Do** colocar todo dado gerado pelo sistema em JetBrains Mono e todo o resto em Inter Tight.
- **Do** separar superfícies com borda de 1px em border antes de pensar em sombra.
- **Do** expressar estados como fundo suave com texto escuro da mesma família.
- **Do** fazer conteúdo rolável sumir em degradê nas bordas.
- **Do** usar `--ease-saida` com durações entre 160ms e 320ms, e respeitar `prefers-reduced-motion`.

### Don't:
- **Don't** colocar a resposta do assistente dentro de balão; o balão é só do cliente.
- **Don't** pintar áreas grandes (cabeçalhos, faixas, cartões) em brasa sólida.
- **Don't** usar JetBrains Mono em rótulos, títulos ou prosa.
- **Don't** criar sombras novas além das três nomeadas, nem sombras duras deslocadas.
- **Don't** usar fotos de salão, pratos ou equipe; o restaurante é fictício e nenhuma existe.
- **Don't** usar sobretítulos (eyebrows) em caixa alta sobre títulos ou seções.
- **Don't** transformar a primeira vista em site de restaurante ou em painel de métricas; os Bastidores ficam recolhidos até serem pedidos.
