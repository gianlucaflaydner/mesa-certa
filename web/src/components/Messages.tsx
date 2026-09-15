"use client";

import { ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";

import type { ChatResponse } from "@/lib/api";
import { linkPhone, stripSourceLines } from "@/lib/format";

import { AttachmentCard } from "./AttachmentCard";
import { BrandMark } from "./BrandMark";
import { ReservationCard } from "./ReservationCard";
import { Sources } from "./Sources";
import styles from "./Messages.module.css";

export function UserMessage({ text }: { text: string }) {
  return (
    <article className={styles.user} aria-label="Você">
      <p className={styles.bubble}>{text}</p>
    </article>
  );
}

function Avatar({ lit = false }: { lit?: boolean }) {
  return (
    <span className={`${styles.avatar} ${lit ? styles.avatarLit : ""}`} aria-hidden="true">
      <BrandMark size={18} lit={lit} />
    </span>
  );
}

type AssistantProps = {
  response: ChatResponse;
  onInspect?: (traceId: string) => void;
  inspected?: boolean;
};

export function AssistantMessage({ response, onInspect, inspected }: AssistantProps) {
  const text = linkPhone(stripSourceLines(response.reply, response.citations.length > 0));
  // Contida: a verificação trocou a resposta ou o turno estourou o limite de iterações.
  const held = response.guard_violations.length > 0 || response.exhausted;

  return (
    <article className={styles.assistant} aria-label="Mesa Certa">
      <Avatar />
      <div className={styles.content}>
        {held ? (
          <p className={styles.held}>
            <ShieldAlert size={15} strokeWidth={1.75} aria-hidden="true" />
            Resposta segura: o sistema não confirmou o que foi pedido.
          </p>
        ) : null}
        <div className={styles.text}>
          <ReactMarkdown
            disallowedElements={["img", "script", "iframe"]}
            components={{
              a: ({ href, children }) =>
                href?.startsWith("tel:") ? (
                  <a href={href} className={styles.phone}>
                    {children}
                  </a>
                ) : (
                  <a href={href} target="_blank" rel="noreferrer">
                    {children}
                  </a>
                ),
            }}
          >
            {text}
          </ReactMarkdown>
        </div>
        {response.reservation ? <ReservationCard reservation={response.reservation} /> : null}
        {(response.attachments ?? []).map((attachment) => (
          <AttachmentCard key={attachment.url} attachment={attachment} />
        ))}
        <Sources citations={response.citations} />
        {onInspect ? (
          <div className={styles.actions}>
            <button
              type="button"
              className={`${styles.inspect} ${inspected ? styles.inspected : ""}`}
              onClick={() => onInspect(response.trace_id)}
              aria-pressed={inspected}
            >
              Ver bastidores
            </button>
            <span className={styles.meta}>
              {response.tool_calls.length} {response.tool_calls.length === 1 ? "ferramenta" : "ferramentas"} ·{" "}
              {(response.latency_ms / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} s
            </span>
          </div>
        ) : null}
      </div>
    </article>
  );
}

/** O assistente está trabalhando. A resposta leva alguns segundos e o contador diz quantos. */
export function Thinking({ since }: { since: number }) {
  const [elapsed, setElapsed] = useState(() => Math.max(0, Date.now() - since));

  useEffect(() => {
    const timer = window.setInterval(() => setElapsed(Math.max(0, Date.now() - since)), 500);
    return () => window.clearInterval(timer);
  }, [since]);

  const seconds = Math.floor(elapsed / 1000);

  return (
    <article className={styles.assistant} aria-label="Mesa Certa está respondendo">
      <Avatar lit />
      <div className={styles.thinking} role="status">
        <span className={styles.dots} aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
        <span>
          {seconds < 9 ? "Consultando a casa" : "Quase lá"}
          <span className={styles.seconds} suppressHydrationWarning>
            {" "}
            · {seconds} s
          </span>
        </span>
      </div>
    </article>
  );
}
