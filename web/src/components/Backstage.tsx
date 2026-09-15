"use client";

import { X } from "lucide-react";
import { useEffect, useState } from "react";

import { ApiError, getTrace, type Trace } from "@/lib/api";
import { formatSeconds } from "@/lib/format";

import styles from "./Backstage.module.css";

type Props = {
  traceId: string | null;
  onClose: () => void;
  /** Só na pré-visualização: um trace pronto, sem chamar a API. */
  fixedTrace?: Trace;
};

type Result = { traceId: string; trace: Trace } | { traceId: string; error: string };

/**
 * Bastidores do turno (só com NEXT_PUBLIC_DEBUG_UI=true). Constelação fixa, lida sempre na mesma
 * ordem: ferramentas, trechos, verificação, sinal de injeção, consumo.
 */
export function Backstage({ traceId, onClose, fixedTrace }: Props) {
  const [result, setResult] = useState<Result | null>(null);

  useEffect(() => {
    if (fixedTrace || !traceId) return;
    const controller = new AbortController();
    getTrace(traceId, controller.signal)
      .then((trace) => setResult({ traceId, trace }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        const message =
          error instanceof ApiError && error.status === 404
            ? "Trace não encontrado. A API guarda só os turnos mais recentes e precisa de DEBUG_UI=true."
            : "Não foi possível carregar o trace deste turno.";
        setResult({ traceId, error: message });
      });
    return () => controller.abort();
  }, [traceId, fixedTrace]);

  // O estado de carga é derivado: vale o resultado que corresponde ao trace pedido agora.
  const current = result && result.traceId === traceId ? result : null;
  const trace = fixedTrace ?? (current && "trace" in current ? current.trace : null);
  const error = current && "error" in current ? current.error : null;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <aside id="bastidores" className={styles.panel} aria-label="Bastidores do turno">
      <header className={styles.head}>
        <h2 className={styles.title}>Bastidores do turno</h2>
        <button type="button" className={styles.close} onClick={onClose}>
          <X size={16} strokeWidth={1.75} aria-hidden="true" />
          Fechar
        </button>
      </header>

      {trace ? <TraceView trace={trace} /> : null}
      {!trace && error ? <p className={styles.note}>{error}</p> : null}
      {!trace && !error && traceId ? <p className={styles.note}>Carregando o trace…</p> : null}
      {!trace && !traceId ? <p className={styles.note}>Envie uma mensagem para ver o que o agente fez.</p> : null}
    </aside>
  );
}

function TraceView({ trace }: { trace: Trace }) {
  const tokensIn = trace.llm_calls.reduce((sum, c) => sum + c.input_tokens, 0);
  const tokensOut = trace.llm_calls.reduce((sum, c) => sum + c.output_tokens, 0);
  const cached = trace.llm_calls.reduce((sum, c) => sum + c.cache_read_input_tokens, 0);

  return (
    <div className={styles.body}>
      <p className={styles.traceId}>{trace.trace_id}</p>

      <section className={styles.section}>
        <h3 className={styles.heading}>Ferramentas</h3>
        {trace.tool_calls.length === 0 ? (
          <p className={styles.note}>Nenhuma ferramenta chamada neste turno.</p>
        ) : (
          <ol className={styles.list}>
            {trace.tool_calls.map((call, index) => (
              <li key={`${call.name}-${index}`} className={styles.tool}>
                <div className={styles.toolHead}>
                  <span className={styles.toolName}>{call.name}</span>
                  <span className={call.ok ? styles.ok : styles.fail}>
                    {call.ok ? "ok" : (call.error_code ?? "erro")}
                  </span>
                  <span className={styles.ms}>{call.duration_ms} ms</span>
                </div>
                <pre className={styles.args}>{JSON.stringify(call.args, null, 2)}</pre>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className={styles.section}>
        <h3 className={styles.heading}>Trechos recuperados</h3>
        {trace.retrievals.length === 0 ? (
          <p className={styles.note}>Sem busca na base de conhecimento.</p>
        ) : (
          trace.retrievals.map((retrieval, index) => (
            <div key={index} className={styles.retrieval}>
              <p className={styles.query}>“{retrieval.query}”</p>
              {retrieval.below_threshold ? (
                <p className={styles.fail}>Nenhum trecho atingiu o limiar: resposta deve recusar.</p>
              ) : (
                <ul className={styles.list}>
                  {retrieval.chunk_ids.map((chunk, i) => (
                    <li key={chunk} className={styles.chunk}>
                      <span className={styles.chunkId}>{chunk}</span>
                      <span className={styles.scoreTrack} aria-hidden="true">
                        <span className={styles.scoreFill} style={{ width: `${Math.round((retrieval.scores[i] ?? 0) * 100)}%` }} />
                      </span>
                      <span className={styles.score}>{(retrieval.scores[i] ?? 0).toFixed(2)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))
        )}
      </section>

      <section className={styles.section}>
        <h3 className={styles.heading}>Verificação da resposta</h3>
        {trace.guard_violations.length === 0 ? (
          <p className={styles.note}>Nenhuma troca: a resposta passou como o modelo escreveu.</p>
        ) : (
          <ul className={styles.list}>
            {trace.guard_violations.map((v) => (
              <li key={v} className={styles.fail}>
                {v}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={styles.section}>
        <h3 className={styles.heading}>Sinal de injeção</h3>
        <p className={trace.suspeita_injecao ? styles.fail : styles.note}>
          {trace.suspeita_injecao
            ? "Padrão suspeito na mensagem ou em dado de reserva. Só registrado, nada foi bloqueado."
            : "Nenhum padrão suspeito."}
        </p>
      </section>

      <section className={styles.section}>
        <h3 className={styles.heading}>Consumo</h3>
        <dl className={styles.stats}>
          <div>
            <dt>Tempo total</dt>
            <dd>{formatSeconds(trace.total_ms)}</dd>
          </div>
          <div>
            <dt>Chamadas ao modelo</dt>
            <dd>{trace.llm_calls.length}</dd>
          </div>
          <div>
            <dt>Tokens de entrada</dt>
            <dd>{tokensIn.toLocaleString("pt-BR")}</dd>
          </div>
          <div>
            <dt>Lidos do cache</dt>
            <dd>{cached.toLocaleString("pt-BR")}</dd>
          </div>
          <div>
            <dt>Tokens de saída</dt>
            <dd>{tokensOut.toLocaleString("pt-BR")}</dd>
          </div>
          <div>
            <dt>Limite estourado</dt>
            <dd>{trace.exhausted ? "sim" : "não"}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
