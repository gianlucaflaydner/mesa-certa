"use client";

import { CalendarDays, ClipboardList, UtensilsCrossed, WheatOff } from "lucide-react";
import { forwardRef, useSyncExternalStore } from "react";

import { greeting } from "@/lib/format";

import { BrandMark } from "./BrandMark";
import { Composer, type ComposerHandle } from "./Composer";
import { Phone } from "./Phone";
import styles from "./EmptyState.module.css";

const SUGGESTIONS = [
  { icon: CalendarDays, label: "Reservar mesa", message: "Quero reservar uma mesa para sábado à noite." },
  { icon: WheatOff, label: "Opções sem glúten", message: "Quais pratos são seguros para quem tem intolerância a glúten?" },
  { icon: ClipboardList, label: "Política de cancelamento", message: "Até quando posso cancelar uma reserva sem custo?" },
  { icon: UtensilsCrossed, label: "Prato do dia", message: "Qual é o prato do dia hoje?" },
];

const noSubscription = () => () => {};
const currentHour = () => new Date().getHours();
const noHourOnServer = () => null;

type Props = {
  busy: boolean;
  onSend: (message: string) => void;
  composerError?: string | null;
  onEdit?: () => void;
  initialText?: string;
};

export const EmptyState = forwardRef<ComposerHandle, Props>(function EmptyState(
  { busy, onSend, composerError, onEdit, initialText },
  ref,
) {
  // A hora é do navegador; no HTML do servidor a saudação é neutra, para não divergir.
  const hour = useSyncExternalStore(noSubscription, currentHour, noHourOnServer);
  const hello = hour === null ? "Olá" : greeting(hour);

  return (
    <section className={styles.empty} aria-labelledby="boas-vindas">
      <div className={styles.head}>
        <span className={styles.mark}>
          <BrandMark size={30} />
        </span>
        <h1 id="boas-vindas" className={styles.title}>
          {hello}. Em que posso ajudar?
        </h1>
        <p className={styles.lede}>
          Tiro dúvidas sobre o cardápio e as políticas da casa e cuido da sua reserva no Mesa Certa.
        </p>
      </div>

      <Composer
        ref={ref}
        variant="hero"
        busy={busy}
        onSend={onSend}
        error={composerError}
        onEdit={onEdit}
        initialText={initialText}
      />

      <ul className={styles.suggestions} aria-label="Sugestões">
        {SUGGESTIONS.map(({ icon: Icon, label, message }) => (
          <li key={label}>
            <button type="button" className={styles.chip} onClick={() => onSend(message)} disabled={busy} title={message}>
              <Icon size={16} strokeWidth={1.75} aria-hidden="true" />
              {label}
            </button>
          </li>
        ))}
      </ul>

      <p className={styles.footnote}>
        Respostas com base na base de conhecimento da casa, sempre com a fonte. Prefere falar com a equipe? <Phone />
      </p>
    </section>
  );
});
