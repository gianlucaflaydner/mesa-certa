# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Next.js (App Router, TypeScript) em `web/`, no mesmo repositório, consumindo a API FastAPI existente (`src/mesa_certa/api/`). Os dois sobem juntos no Docker Compose. Substitui o Streamlit previsto no SDD §9.4.

## Users

Cliente do restaurante Mesa Certa, em primeiro lugar. Exemplos das personas do PRD: quem quer reservar mesa para sábado no intervalo do trabalho, pelo celular, sem preencher formulário; e quem tem restrição alimentar (celíaco, por exemplo) e precisa de informação confiável antes de reservar para um grupo.

Público secundário, e razão de ser do projeto: avaliador técnico (recrutador, tech lead) que abre o portfólio para ver um agente com RAG funcionando. É atendido pelo painel de bastidores, ligado por configuração (`DEBUG_UI`), e pelas fontes visíveis em cada resposta.

## Product Purpose

Um único ponto de atendimento em conversa que resolve a dúvida informativa (cardápio, alérgenos, políticas, horários) e a ação transacional (consultar disponibilidade, criar, consultar e cancelar reserva), sem o cliente saber de qual sistema vem a resposta. Sucesso: o cliente reserva ou tira a dúvida numa conversa curta, com informação que a casa sustenta.

## Positioning

O assistente não inventa. Toda informação sobre prato, alérgeno ou política vem da base da casa e é citada; toda disponibilidade e toda confirmação de reserva vêm do sistema de reservas, com código. Quando não sabe, diz que não sabe e passa o telefone. Isso é verificado em código, não só prometido.

## Operating Context

- Conversa em português do Brasil, com sessão que mantém o histórico enquanto o cliente conversa.
- Uso típico no celular, em momentos curtos.
- Respostas podem trazer: citação de fonte ("Fonte: cardapio.md › Seção"), confirmação de reserva (código de 6 caracteres, data, horário, número de pessoas, tolerância de 20 minutos), alternativas de horário quando lotado, e recusas educadas para assuntos fora do restaurante.
- Estados de erro reais da API: sessão expirada (410), modelo indisponível (503), falha interna (500), mensagem longa demais (422, limite de 2.000 caracteres).

## Capabilities and Constraints

- Backend: `POST /chat` devolve `reply`, `citations` (source, section, chunk_id), `tool_calls` (name, ok, duration_ms, error_code), `latency_ms`, `guard_violations`. `GET /traces/{id}` (só em modo debug) devolve argumentos das tools mascarados, chunks recuperados com score e `suspeita_injecao`.
- A resposta chega inteira, sem streaming, e leva alguns segundos (alvo p95 de 4 a 8 s).
- O assistente não faz delivery, não altera reserva existente, não emite vale-presente, não dá desconto e não organiza evento privado (grupos acima de 12 vão para o telefone).
- Sem autenticação, conta de usuário ou pagamento na v1.
- Restaurante fictício: nenhuma foto real do salão, dos pratos ou da equipe existe.
- Em aberto: domínio e hospedagem do front-end.

## Brand Commitments

- Nome: Mesa Certa. Descritor: "Cozinha brasileira contemporânea, fogo e fermentação". Bom Fim, Porto Alegre.
- Contato público: (51) 3030-4050, contato@mesacerta.com.br, Rua Fernandes Vieira, 812.
- Voz do assistente (confirmada): amigável e proativo, respeitoso e simpático, respostas curtas, sem emojis, sem travessão.
- O cardápio diagramado em `docs/Cardápio Mesa Certa.pdf` é **referência, não identidade obrigatória**: a interface pode ter linguagem visual própria.
- **Padrão de interface (decisão do usuário, 2026-09-15):** o chat é o protagonista da página, no formato consagrado por ChatGPT e Claude: coluna central, campo de mensagem como elemento principal, sugestões junto ao campo, resposta do assistente em texto corrido e mensagem do cliente em balão discreto. A primeira direção ("Grelha de brasa") foi descartada por tirar o foco do chat. O projeto é portfólio de um agente com RAG: a conversa, as fontes e os bastidores são a vitrine, não a identidade do restaurante.

## Evidence on Hand

- Base de conhecimento real do projeto: `data/knowledge/` (cardápio com preços e alérgenos, políticas, FAQ, sobre).
- Cardápio diagramado de referência: `docs/Cardápio Mesa Certa.pdf` (6 páginas, inclui marca de chama em traço).
- Não existem: fotografias, depoimentos, avaliações, prêmios verificáveis além do texto fictício de `sobre.md`, nem métricas de uso. Não fabricar.

## Product Principles

1. **Verdade antes de fluidez.** Nunca afirmar disponibilidade, reserva ou informação de prato sem a fonte ter respondido.
2. **Mostrar de onde vem.** Citação e confirmação são parte da resposta, não rodapé técnico.
3. **Resolver em poucas trocas.** Antecipar o próximo passo útil, sem agir sem confirmação.
4. **O cliente vem primeiro; a engenharia fica disponível.** O painel de debug existe, mas não disputa espaço com o atendimento.

## Accessibility & Inclusion

Público com restrições alimentares depende de a informação de alérgeno ser legível e inequívoca. Sem outro requisito específico confirmado; seguir WCAG 2.2 AA como piso.
