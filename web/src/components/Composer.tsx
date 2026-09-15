"use client";

import { ArrowUp } from "lucide-react";
import { forwardRef, useImperativeHandle, useLayoutEffect, useRef, useState } from "react";

import { MAX_MESSAGE_CHARS } from "@/lib/api";

import styles from "./Composer.module.css";

export type ComposerHandle = { fill: (text: string) => void; focus: () => void };

type Props = {
  busy: boolean;
  onSend: (text: string) => void;
  /** "hero": grande, no centro da tela vazia. "dock": ancorado embaixo da conversa. */
  variant: "hero" | "dock";
  /** Erro vindo da API para o texto atual (ex.: mensagem longa demais após a limpeza). */
  error?: string | null;
  onEdit?: () => void;
  initialText?: string;
};

const WARN_AT = 1600;

/** O campo de mensagem é a peça principal da página. */
export const Composer = forwardRef<ComposerHandle, Props>(function Composer(
  { busy, onSend, variant, error, onEdit, initialText = "" },
  ref,
) {
  const [text, setText] = useState(initialText);
  const fieldRef = useRef<HTMLTextAreaElement>(null);

  useImperativeHandle(ref, () => ({
    fill: (value: string) => {
      setText(value);
      requestAnimationFrame(() => fieldRef.current?.focus());
    },
    focus: () => fieldRef.current?.focus(),
  }));

  useLayoutEffect(() => {
    const field = fieldRef.current;
    if (!field) return;
    const max = variant === "hero" ? 320 : 240;
    field.style.height = "auto";
    field.style.height = `${Math.min(field.scrollHeight, max)}px`;
    field.dataset.full = String(field.scrollHeight > max);
  }, [text, variant]);

  const trimmed = text.trim();
  const tooLong = text.length > MAX_MESSAGE_CHARS;
  const ready = trimmed.length > 0 && !tooLong && !busy;
  const invalid = tooLong || Boolean(error);

  function submit() {
    if (!ready) return;
    onSend(trimmed);
    setText("");
  }

  return (
    <form
      className={`${styles.composer} ${styles[variant]}`}
      data-invalid={invalid}
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <label htmlFor="mensagem" className="visually-hidden">
        Mensagem para o assistente
      </label>
      <textarea
        id="mensagem"
        ref={fieldRef}
        className={styles.input}
        rows={variant === "hero" ? 3 : 1}
        value={text}
        autoFocus={variant === "hero"}
        placeholder={
          variant === "hero" ? "Pergunte sobre o cardápio, ingredientes ou peça uma mesa" : "Responder ao assistente"
        }
        aria-describedby="mensagem-status"
        aria-invalid={invalid}
        onChange={(event) => {
          setText(event.target.value);
          onEdit?.();
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault();
            submit();
          }
        }}
      />
      <div className={styles.toolbar}>
        <p id="mensagem-status" className={styles.status} aria-live="polite">
          {error ? (
            <span className={styles.error}>{error}</span>
          ) : text.length >= WARN_AT ? (
            <span className={tooLong ? styles.error : undefined}>
              {text.length.toLocaleString("pt-BR")} de {MAX_MESSAGE_CHARS.toLocaleString("pt-BR")} caracteres
            </span>
          ) : null}
        </p>
        <button type="submit" className={styles.send} disabled={!ready} aria-label={busy ? "Aguardando resposta" : "Enviar mensagem"}>
          <ArrowUp size={18} strokeWidth={2.25} aria-hidden="true" />
        </button>
      </div>
    </form>
  );
});
