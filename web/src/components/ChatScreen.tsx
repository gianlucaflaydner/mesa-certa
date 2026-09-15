"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, DEBUG_UI, postChat, type ApiErrorKind, type ChatResponse, type Trace } from "@/lib/api";

import { Backstage } from "./Backstage";
import { Composer, type ComposerHandle } from "./Composer";
import { EmptyState } from "./EmptyState";
import { AssistantMessage, Thinking, UserMessage } from "./Messages";
import { Notice, type ThreadErrorKind } from "./Notice";
import { TopBar } from "./TopBar";
import styles from "./ChatScreen.module.css";

export type Entry =
  | { id: string; kind: "cliente"; text: string }
  | { id: string; kind: "casa"; response: ChatResponse }
  | { id: string; kind: "aviso"; error: ThreadErrorKind; traceId: string | null; text: string };

export type PreviewState = {
  entries: Entry[];
  pendingSince?: number;
  debugOpen?: boolean;
  trace?: Trace;
  draft?: string;
  draftError?: string;
};

const STORAGE_KEY = "mesa-certa:conversa";
const TOO_LONG = "Mensagem longa demais: envie até 2.000 caracteres ou divida o pedido.";

let counter = 0;
const newId = () => `${Date.now().toString(36)}-${(counter++).toString(36)}`;

type Stored = { sessionId: string | null; entries: Entry[] };

/** A conversa sobrevive a um recarregamento da aba; a sessão do servidor expira sozinha. */
function readStored(): Stored {
  const empty: Stored = { sessionId: null, entries: [] };
  if (typeof window === "undefined") return empty;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Stored) : empty;
  } catch {
    return empty;
  }
}

/**
 * Tela do chat. Na página principal é renderizada só no cliente (ver app/ChatClient),
 * porque o estado inicial vem do sessionStorage.
 */
export function ChatScreen({ preview }: { preview?: PreviewState }) {
  const [initial] = useState<Stored>(() =>
    preview ? { sessionId: null, entries: preview.entries } : readStored(),
  );
  const [entries, setEntries] = useState<Entry[]>(initial.entries);
  const [sessionId, setSessionId] = useState<string | null>(initial.sessionId);
  const [pendingSince, setPendingSince] = useState<number | null>(() => {
    const since = preview?.pendingSince;
    if (since === undefined) return null;
    // Na pré-visualização, valor negativo é relativo ao momento em que a tela abriu.
    return since < 0 ? Date.now() + since : since;
  });
  const [debugOpen, setDebugOpen] = useState(preview?.debugOpen ?? false);
  const [inspected, setInspected] = useState<string | null>(null);
  const [composerError, setComposerError] = useState<string | null>(preview?.draftError ?? null);

  const composer = useRef<ComposerHandle>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const controller = useRef<AbortController | null>(null);
  const busy = pendingSince !== null;
  const showDebug = DEBUG_UI || Boolean(preview?.trace);

  useEffect(() => {
    if (preview) return;
    try {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ sessionId, entries } satisfies Stored));
    } catch {
      // Armazenamento cheio ou bloqueado: a conversa segue só na memória.
    }
  }, [entries, sessionId, preview]);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    endRef.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "end" });
  }, [entries, pendingSince]);

  const lastReply = [...entries].reverse().find((e) => e.kind === "casa");
  const traceForPanel = inspected ?? (lastReply?.kind === "casa" ? lastReply.response.trace_id : null);

  const run = useCallback(async (text: string, options: { appendCustomer: boolean; session: string | null }) => {
    const customerId = newId();
    if (options.appendCustomer) {
      setEntries((prev) => [...prev, { id: customerId, kind: "cliente", text }]);
    }
    setComposerError(null);
    setPendingSince(Date.now());
    controller.current = new AbortController();
    try {
      const response = await postChat(text, options.session, controller.current.signal);
      setSessionId(response.session_id);
      setInspected(null);
      setEntries((prev) => [...prev, { id: newId(), kind: "casa", response }]);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      const kind: ApiErrorKind = error instanceof ApiError ? error.kind : "rede";
      if (kind === "mensagem_longa") {
        // O problema é o texto: ele volta para o campo, onde a correção acontece.
        setEntries((prev) => prev.filter((e) => e.id !== customerId));
        setComposerError(TOO_LONG);
        composer.current?.fill(text);
        return;
      }
      if (kind === "sessao_expirada") setSessionId(null);
      const traceId = error instanceof ApiError ? error.traceId : null;
      setEntries((prev) => [...prev, { id: newId(), kind: "aviso", error: kind, traceId, text }]);
    } finally {
      setPendingSince(null);
      controller.current = null;
    }
  }, []);

  const send = useCallback(
    (text: string) => {
      if (busy) return;
      void run(text, { appendCustomer: true, session: sessionId });
    },
    [busy, run, sessionId],
  );

  const reset = useCallback(() => {
    controller.current?.abort();
    setEntries([]);
    setSessionId(null);
    setPendingSince(null);
    setInspected(null);
    setComposerError(null);
  }, []);

  function recover(entry: Extract<Entry, { kind: "aviso" }>) {
    if (entry.error === "sessao_expirada") {
      setEntries([]);
      setSessionId(null);
      void run(entry.text, { appendCustomer: true, session: null });
      return;
    }
    setEntries((prev) => prev.filter((e) => e.id !== entry.id));
    void run(entry.text, { appendCustomer: false, session: sessionId });
  }

  const empty = entries.length === 0 && !busy;
  const clearError = () => setComposerError(null);

  return (
    <div className={`${styles.screen} ${debugOpen ? styles.withPanel : ""}`}>
      <TopBar
        canReset={entries.length > 0}
        onReset={reset}
        debug={showDebug}
        debugOpen={debugOpen}
        onToggleDebug={() => setDebugOpen((open) => !open)}
      />

      {empty ? (
        <main className={styles.emptyMain}>
          <EmptyState
            ref={composer}
            busy={busy}
            onSend={send}
            composerError={composerError}
            onEdit={clearError}
            initialText={preview?.draft}
          />
        </main>
      ) : (
        <>
          <main className={styles.thread}>
            <div role="log" aria-live="polite" aria-relevant="additions" aria-label="Conversa" className={styles.log}>
              {entries.map((entry) => {
                if (entry.kind === "cliente") return <UserMessage key={entry.id} text={entry.text} />;
                if (entry.kind === "casa") {
                  return (
                    <AssistantMessage
                      key={entry.id}
                      response={entry.response}
                      onInspect={
                        showDebug
                          ? (traceId) => {
                              setInspected(traceId);
                              setDebugOpen(true);
                            }
                          : undefined
                      }
                      inspected={debugOpen && traceForPanel === entry.response.trace_id}
                    />
                  );
                }
                return (
                  <Notice
                    key={entry.id}
                    kind={entry.error}
                    traceId={entry.traceId}
                    onAction={() => recover(entry)}
                    disabled={busy}
                  />
                );
              })}
              {busy && pendingSince !== null ? <Thinking since={pendingSince} /> : null}
              <div ref={endRef} />
            </div>
          </main>

          <div className={styles.dock}>
            <Composer
              ref={composer}
              variant="dock"
              busy={busy}
              onSend={send}
              error={composerError}
              onEdit={clearError}
              initialText={preview?.draft}
            />
            <p className={styles.disclaimer}>
              Informações do cardápio e das políticas vêm da base da casa. Reservas só valem com código emitido pelo
              sistema.
            </p>
          </div>
        </>
      )}

      {showDebug && debugOpen ? (
        <Backstage traceId={traceForPanel} onClose={() => setDebugOpen(false)} fixedTrace={preview?.trace} />
      ) : null}
    </div>
  );
}
