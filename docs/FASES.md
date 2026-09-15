# Especificação das fases | Mesa Certa

Documento de execução da v1. Detalha as fases F0 a F7 do [SDD §14](SDD.md#14-plano-de-implementação): o que entra em cada uma, em que arquivos, e o critério objetivo de pronto. PRD e SDD continuam sendo a fonte de verdade; este arquivo diz **como e em que ordem** chegar lá.

## Estado atual

| Item | Situação |
|---|---|
| PRD e SDD | versionados em `docs/` |
| Base de conhecimento | 4 documentos em `data/knowledge/`, revisados |
| Dataset de avaliação | `evals/dataset.yaml`, 36 casos, validado contra os cabeçalhos reais |
| Código | F0 a F3 concluídas: domínio, banco, seed, RAG e as 6 tools com registry |
| F4 | concluída: loop, sessão, trace e persona; cenário da US-08 validado com a API real |
| F4.1 | especificada (proteção contra injeção de instruções, SDD §8.5); não iniciada |

## Regras gerais

- Cada fase termina com o projeto executável e vira pelo menos um commit.
- Nenhuma fase começa sem a anterior estar pronta pelo critério dela.
- Nada de travessão em texto, comentário, commit ou documentação.
- Configuração só é lida em `config.py`. Relógio só é lido em `date_resolver.now()`.
- Mudança de contrato (schema de tool, formato do dataset, `chunk_id`) atualiza o SDD no mesmo commit.

## Decisões pendentes

| # | Decisão | Quando | Recomendação |
|---|---|---|---|
| D1 | Gerenciador de dependências: uv ou Poetry | início da F0 | **decidido na F0: uv** |
| D2 | Horários de funcionamento no system prompt | F4 | **decidido na F4: incluídos no prompt**, com instrução de não consultar disponibilidade na segunda |
| D3 | Reescrever travessões de PRD e SDD | qualquer momento | fazer antes da F7, junto com o README |
| D4 | Modelo Claude padrão em `MODEL_NAME` | F4 | **confirmado na F4: `claude-sonnet-5`**. Ele não aceita `temperature` (o SDK 1.x nem expõe o parâmetro), então `MODEL_TEMPERATURE` saiu e entrou `MODEL_EFFORT` (padrão `medium`, a calibrar na F6); `MODEL_MAX_TOKENS` foi para 16.000 por causa do thinking adaptativo |
| D6 | Limites de tamanho da P3 e da P4 (2.000 caracteres na mensagem, 120 no nome, 500 nas observações) | F4.1 | manter os valores do SDD §8.5 e revisar se algum caso real do dataset for cortado |
| D5 | Valor final do limiar de similaridade | F6 | definido pela varredura, não por palpite. Na F2, com e5, perguntas fora da base pontuaram cerca de 0,83 e a melhor resposta certa cerca de 0,90: o 0,72 atual não recusa nada, e a varredura precisa cobrir a faixa acima de 0,85 |

---

## F0. Fundação

**Objetivo.** Esqueleto do repositório com ferramentas de qualidade rodando, sem lógica de negócio.

**Entregas**

| Arquivo | Conteúdo |
|---|---|
| `pyproject.toml` | Python 3.12, dependências do SDD §1.2, grupos `dev` e `eval`, config de ruff, mypy (strict em `src/`) e pytest |
| `src/mesa_certa/` | pacotes vazios com `__init__.py`: `agent`, `tools`, `rag`, `domain`, `db`, `api`, `observability` |
| `src/mesa_certa/config.py` | `Settings` com pydantic-settings, todos os campos do SDD §12, cache via `get_settings()` |
| `.env.example` | cópia do SDD §12, trocando `MODEL_NAME` conforme D4 |
| `Makefile` | alvos `install`, `lint`, `format`, `typecheck`, `test`, `cov`, e stubs de `ingest`, `seed`, `eval`, `run-api`, `run-ui` |
| `tests/conftest.py` | fixture de `Settings` apontando para diretório temporário |
| `tests/unit/test_config.py` | carrega defaults e sobrescreve por variável de ambiente |
| `README.md` | nome, uma frase, links para PRD, SDD e este arquivo, seção "Como rodar" provisória |

**Pronto quando**
- `make lint`, `make typecheck` e `make test` passam em clone limpo.
- `Settings()` sobe sem `.env` (a chave da API só é exigida na F4).

---

## F1. Domínio e banco

**Objetivo.** Toda a regra de negócio de reservas funcionando e testada, sem nenhuma chamada a LLM.

**Entregas**

| Arquivo | Conteúdo |
|---|---|
| `db/models.py` | tabelas do SDD §5.1 em SQLAlchemy 2.x (`Mapped`), com as `CHECK` e `UNIQUE` |
| `db/session.py` | engine, `sessionmaker`, `PRAGMA foreign_keys=ON` |
| `migrations/` | Alembic com a migração inicial gerada dos modelos |
| `db/seed.py` | seed determinístico (ver abaixo) |
| `domain/errors.py` | `DomainError(code, message, details)` e as subclasses do SDD §5.8 |
| `domain/rules.py` | constantes do PRD §4.4 e validações puras de RN-01 a RN-04 |
| `domain/date_resolver.py` | funções do SDD §5.5, com `Clock` injetável |
| `domain/availability.py` | `AvailabilityService.check`, algoritmo do SDD §5.3 |
| `domain/reservations.py` | `create`, `get_by_code`, `cancel`, transação com `BEGIN IMMEDIATE` |
| `domain/menu.py` | `MenuService.list_for(date)` |
| `domain/codes.py` | gerador do código de reserva (SDD §5.7) |
| `scripts/reset_db.py` | apaga, migra e semeia; alvo `make seed` |

**Seed.** Data âncora fixa `2026-09-15`, `random.Random(42)`. Tem que cumprir exatamente as pré-condições do cabeçalho de `evals/dataset.yaml`:
- sábado 2026-09-19: mezanino M1 a M4 com reservas de 6 pessoas às 19:30
- `K7M2QP` confirmada (Bruna Alves, 2 pessoas, 2026-09-26 20:00, varanda) e `W4X9HT` cancelada
- pratos do dia de 2026-09-15 a 2026-09-28, nenhum em 2026-11-10
- 12 reservas no total, sem conflitar com os horários livres exigidos pelo dataset
- 3 fechamentos (25/12, 01/01 e uma manutenção fora da janela usada pelos casos)

**Decisões de implementação**
- Horários guardados como `HH:MM`; toda aritmética em minutos desde a meia-noite, com +1440 após a virada.
- Última reserva do serviço = fechamento menos 90 min. Jantar de sexta e sábado: último slot 22:30.
- Alocação (SDD §5.6): menor capacidade suficiente, desempate por menor `id`. Grupo de 7 a 12 usa duas mesas do mezanino `combinable`.
- `cancel` fora da janela de 4 h é aceito e devolve `within_free_window = False`.

**Testes**

| Arquivo | Cobre |
|---|---|
| `tests/unit/test_date_resolver.py` | parse ISO, rejeição de formatos, virada da meia-noite, janela 60 min e 60 dias nos limites exatos |
| `tests/unit/test_rules.py` | grupo 0, 1, 12, 13; segunda; fechamento; slot fora do serviço |
| `tests/unit/test_codes.py` | alfabeto sem `0 O 1 I`, tamanho 6, retry em colisão |
| `tests/integration/test_availability.py` | cenários do dataset (tool-001, 002, 004), alternativas ordenadas por proximidade, máximo 4 |
| `tests/integration/test_reservations.py` | criação, concorrência na última mesa (duas threads, uma vence), cancelamento a 3h59 e 4h01, `JA_CANCELADA` |
| `tests/integration/test_seed.py` | cada pré-condição do dataset verificada contra o banco semeado |

**Pronto quando**
- Todos os casos de borda do SDD §13 passam.
- Cobertura de `domain/` maior ou igual a 80%.
- `make seed` roda duas vezes e produz o mesmo banco.

---

## F2. Base de conhecimento e RAG

**Objetivo.** Ingestão idempotente e busca semântica com score e citação.

**Entregas**

| Arquivo | Conteúdo |
|---|---|
| `rag/chunker.py` | chunking estrutural do SDD §6.2 e regra de `chunk_id` |
| `rag/embedder.py` | `Embedder` sobre e5-small, `embed_query` com prefixo `query: `, `embed_passages` com `passage: `, vetores normalizados |
| `rag/store.py` | `PersistentClient`, collection com `hnsw:space = cosine` |
| `rag/ingest.py` | diff por `chunk_id` e `content_hash`; relatório criados, atualizados, removidos, inalterados |
| `rag/retriever.py` | `RetrievalResult` com limiar, `max_context_chars` e formatação de citação do SDD §6.5 |
| `scripts/ingest.py` | CLI; alvo `make ingest` |
| `scripts/search.py` | busca manual por linha de comando, imprime id, score e trecho |

**Decisão de escopo.** `scripts/generate_knowledge.py` do SDD fica fora: os documentos já existem e foram revisados. Registrar no SDD que a geração foi feita fora do repositório.

**Regras do chunker**
- Preâmbulo antes do primeiro `##` não vira chunk.
- Texto do chunk para embedding: `"{título} > {H2} > {H3}\n\n{conteúdo}"`.
- Divisão acima de 1.200 caracteres por parágrafo, com 1 de sobreposição; tabela nunca é partida.
- Chunk abaixo de 80 caracteres é fundido ao irmão seguinte e herda o `chunk_id` desse irmão.

**Testes**

| Arquivo | Cobre |
|---|---|
| `tests/unit/test_chunker.py` | slug com acento e pontuação, H2 sem H3, tabela íntegra, fusão, divisão |
| `tests/unit/test_embedder.py` | prefixos aplicados (mock do modelo) e um teste com modelo real marcado `slow` |
| `tests/unit/test_dataset_contract.py` | todo `chunks_esperados` existe no chunker real; campos e distribuição do dataset |
| `tests/integration/test_ingest.py` | segunda execução sem mudança faz zero escritas; editar um arquivo atualiza só os chunks dele |
| `tests/integration/test_retriever.py` | collection temporária com fixtures; limiar marca `below_threshold` |

**Pronto quando**
- `make ingest` duas vezes seguidas: a segunda reporta tudo inalterado.
- `scripts/search.py "opções sem glúten"` traz `cardapio.md#pratos-principais>opcoes-sem-gluten#0` no topo.
- Cobertura de `rag/` maior ou igual a 80%.

---

## F3. Tools

**Objetivo.** As 6 tools do SDD §7 expostas por um registry que nunca deixa exceção escapar.

**Entregas**

| Arquivo | Conteúdo |
|---|---|
| `tools/base.py` | `Tool` (nome, descrição, modelo Pydantic de entrada, handler), `ToolResult` com `to_json()` |
| `tools/registry.py` | `register`, `schemas`, `dispatch` conforme SDD §7.7 |
| `tools/knowledge.py` | `buscar_conhecimento` |
| `tools/availability.py` | `consultar_disponibilidade`, com `dia_semana` e `proxima_data_aberta` em dia fechado |
| `tools/reservations.py` | `criar_reserva`, `consultar_reserva`, `cancelar_reserva` |
| `tools/menu.py` | `listar_pratos_do_dia`, data padrão = hoje pelo `Clock` |
| `tools/__init__.py` | `build_registry(services, retriever)` |

**Regras**
- O `input_schema` enviado ao modelo é gerado do modelo Pydantic; o teste de contrato compara com o JSON do SDD.
- `num_pessoas` aceita até 20 na consulta e até 12 na criação (SDD §7.2).
- Erro de validação vira `ARGUMENTOS_INVALIDOS`; exceção inesperada vira `ERRO_INTERNO` sem stack trace no envelope.
- Resposta da tool nunca contém telefone ou e-mail completos do cliente, exceto o que o próprio cliente acabou de informar.

**Testes**
- `tests/contract/test_tool_schemas.py`: parametrizado sobre o registry, schema bate com o SDD.
- `tests/integration/test_tools.py`: caminho feliz e cada código de erro por tool, sobre banco semeado e retriever de fixture.

**Pronto quando**
- Todo código de erro do SDD §5.8 tem pelo menos um teste que o produz via `dispatch`.
- Nenhum teste consegue fazer `dispatch` levantar exceção.

---

## F4. Agente

**Objetivo.** Loop de tool calling próprio, com sessão, prompt e trace.

**Entregas**

| Arquivo | Conteúdo |
|---|---|
| `agent/models.py` | `TurnResult`, `Citation`, `ToolCallRecord`, `TokenUsage` |
| `agent/prompts.py` | `build_system_prompt(now)` a partir do SDD §8.2, com a decisão D2 aplicada |
| `agent/session.py` | `SessionStore` em memória, janela de 20 mensagens, TTL 60 min, poda que preserva pares `tool_use`/`tool_result` |
| `agent/loop.py` | `AgentLoop.run_turn` do SDD §8.1, cliente LLM injetável |
| `agent/llm.py` | `LLMClient` (protocolo), `AnthropicLLM` e `ModelUnavailable` |
| `agent/factory.py` | `build_app`: monta banco, tools, tracer, sessões e agente; reusado pela F5 |
| `observability/masking.py` | regras do SDD §10.2 e regex para texto livre |
| `observability/tracing.py` | `Tracer`, `Trace`, spans; grava JSONL diário em `TRACE_PATH` |
| `observability/logging.py` | structlog com processador de mascaramento |
| `scripts/chat.py` | chat no terminal para teste manual |

**Regras**
- Citações do `TurnResult` vêm dos `tool_result` de `buscar_conhecimento`, não do texto do modelo.
- Esgotar `MAX_ITERATIONS` devolve mensagem fixa com o telefone e marca `exhausted = true`.
- Erro da API do modelo propaga como exceção própria (`ModelUnavailable`), tratada na F5.

**Testes**
- `tests/unit/test_masking.py`: exemplos do SDD §10.2 e texto livre.
- `tests/unit/test_session.py`: poda da janela nunca deixa `tool_result` órfão.
- `tests/integration/test_agent_loop.py` com `FakeLLMClient` roteirizado: turno sem tool, com uma tool, com duas tools na mesma resposta, erro de tool, estouro de iterações.
- Trace gravado não contém telefone ou e-mail sem máscara.

**Pronto quando**
- Todos os cenários acima passam sem rede.
- `scripts/chat.py` com chave real conclui o cenário da US-08.

---

## F4.1. Proteção contra injeção de instruções

**Objetivo.** Defesa em camadas do SDD §8.5: o prompt reduz a chance de o modelo obedecer a instruções de terceiros, e o código garante que, se obedecer, nada indevido chega ao cliente nem ao banco.

**Entregas**

| Arquivo | Conteúdo |
|---|---|
| `agent/prompts.py` | P1: seção de hierarquia de autoridade (só o system prompt instrui; `tool_result` e `dados_informados_pelo_cliente` são dados; recusa simpática a vazamento de prompt e troca de papel) |
| `agent/sanitize.py` | P3: `clean_text(value, max_chars)` remove controle e largura zero; `MessageTooLong` acima do limite |
| `agent/loop.py` | aplica P3 no início de `run_turn` e P5 antes de `_finish` |
| `agent/guards.py` | P5: `check_reply(reply, turn_tool_results, session_tool_results) -> GuardOutcome` com as checagens (a) código e (b) confirmação sem tool; `SAFE_REPLY` com telefone |
| `tools/reservations.py` | P4: limites de `nome` e `observacoes` via Pydantic; `consultar_reserva` agrupa campos do cliente em `dados_informados_pelo_cliente` |
| `observability/injection.py` | P6: `looks_like_injection(text) -> bool` com a lista de padrões do SDD |
| `observability/tracing.py` | campos `suspeita_injecao` e `guard_violations` no `Trace` |
| `db/seed.py` | reserva `Q8R3TX` com observação maliciosa, sem conflitar com as pré-condições atuais |
| `evals/dataset.yaml` | casos adv-004 a adv-008 e a nova pré-condição no cabeçalho; distribuição passa a 41 casos |
| `tests/unit/test_dataset_contract.py` | distribuição atualizada |

**Regras**
- P5 nunca bloqueia resposta legítima: o código só é aceito se veio de `tool_result` da sessão, e o status "confirmada" é permitido após `consultar_reserva`.
- P6 só marca o trace. Nenhuma decisão de atendimento depende dela.
- A mensagem mascarada no trace é a mensagem já higienizada.
- Nada de lista de palavras proibidas na entrada: bloquear por palavra recusa clientes legítimos e é fácil de contornar.

**Testes**

| Arquivo | Cobre |
|---|---|
| `tests/unit/test_sanitize.py` | largura zero e controle removidos, quebra de linha preservada, limite exato e limite mais um |
| `tests/unit/test_guards.py` | código inventado trocado; código vindo de tool aceito; palavra comum em maiúsculas (ex.: "BRASIL") não tratada como código; "reserva confirmada" sem `criar_reserva` trocada; com `criar_reserva` ok aceita; "confirmada" após `consultar_reserva` aceita; cancelamento sem tool trocado |
| `tests/unit/test_injection.py` | padrões detectados, incluindo prefixo `SISTEMA:` só em início de linha; frases comuns de cliente não marcadas |
| `tests/integration/test_agent_loop.py` | modelo roteirizado que "obedece" à injeção (confirma sem tool, inventa código) tem a resposta trocada e `guard_violations` no trace; observação maliciosa chega ao modelo dentro de `dados_informados_pelo_cliente` |
| `tests/integration/test_tools.py` | nome acima de 120 e observação acima de 500 viram `ARGUMENTOS_INVALIDOS` |
| `tests/integration/test_seed.py` | pré-condição de `Q8R3TX` |

**Pronto quando**
- Todos os testes acima passam sem rede.
- `make chat` com chave real resiste aos 5 casos novos (adv-004 a adv-008) sem acionar a P5, ou seja, a defesa principal é o prompt e o código só confirma.
- Dataset com 41 casos e contrato verde.

---

## F5. Interface

**Objetivo.** API HTTP e UI de demonstração.

**Entregas**

| Arquivo | Conteúdo |
|---|---|
| `api/dto.py` | request e response do SDD §9.2 |
| `api/routes.py` | endpoints do SDD §9.1 |
| `api/main.py` | app FastAPI, montagem das dependências, handlers de erro do SDD §9.3 |
| `ui/app.py` | Streamlit consumindo `/chat`; barra lateral de debug com `DEBUG_UI=true` |

**Regras**
- `/admin/reindex` e `/reservations/{code}` só ficam ativos com `DEBUG_UI=true`.
- `/health` verifica banco, collection não vazia e presença da chave da API.

**Testes**
- `tests/integration/test_api.py` com `TestClient` e agente falso: sessão nova, sessão expirada (410), modelo indisponível (503).
- `tests/e2e/test_chat.py` marcado `e2e`, fora do `make test`.

**Pronto quando**
- US-01 a US-09 reproduzidas manualmente pela UI, com a barra de debug mostrando tools e chunks.

---

## F6. Avaliação

**Objetivo.** Relatório reproduzível com as métricas do PRD §9.1.

**Entregas**

| Arquivo | Conteúdo |
|---|---|
| `evals/metrics.py` | hit@1/3/5, MRR, latência p95, roteamento com `tools_alternativas`, citação, recusa, termos |
| `evals/runner.py` | por caso: re-seed, clock em `contexto_data`, executa turno com `build_app` e o trace; suite repetida para medir a variação do modelo (não há `temperature`) |
| `evals/report.py` | Markdown em `evals/results/AAAA-MM-DD-HHMM.md`, com comparação à execução anterior e casos que falharam |
| `Makefile` | `eval`, `eval-retrieval`, `eval-threshold-sweep` |

**Regras**
- `eval-retrieval` roda só o retriever, sem custo de API.
- Detecção de recusa: em `fora_da_base`, `encontrou_informacao = false` no trace e telefone na resposta; em `adversarial`, nenhum termo proibido e nenhuma tool fora do esperado.
- Comparação de termos sem caixa e sem acento, como no cabeçalho do dataset.

**Pronto quando**
- `make eval` gera relatório e bate os alvos: hit@3 ≥ 0,90, MRR ≥ 0,80, roteamento ≥ 0,85, citação 100%, recusa ≥ 0,90, violação de termos proibidos zero.
- Limiar fixado pela varredura (D5), com a curva salva para o README.
- Se um alvo não bater, o relatório registra o motivo antes de qualquer ajuste de prompt ou limiar.

---

## F7. Empacotamento

**Objetivo.** Qualquer pessoa sobe o projeto com um comando e entende a arquitetura em 3 minutos.

**Entregas**
- `Dockerfile` multi-stage com o modelo de embedding baixado no build.
- `docker-compose.yml` com API e UI; entrypoint roda migração, seed e ingestão se necessário.
- `docs/adr/001` a `006`, extraídos do SDD §3.
- `README.md` final: diagrama, como rodar, tabela de métricas do último relatório, curva do limiar, GIF do cenário composto.
- Travessões removidos de PRD e SDD (D3).

**Pronto quando**
- Clone limpo, `.env` com a chave e `docker compose up` entregam o sistema funcionando, sem passo manual.
- CI no GitHub Actions rodando `lint`, `typecheck`, `test` e `eval-retrieval`.
