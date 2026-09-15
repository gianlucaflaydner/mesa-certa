"use client";

import { CalendarCheck, CalendarSearch, CalendarX, Check, Copy } from "lucide-react";
import { useState } from "react";

import type { Reservation } from "@/lib/api";
import { formatDeadline, formatReservationDate, zoneName } from "@/lib/format";

import styles from "./ReservationCard.module.css";

const HEADER = {
  criada: { title: "Reserva confirmada", icon: CalendarCheck },
  consultada: { title: "Reserva encontrada", icon: CalendarSearch },
  cancelada: { title: "Reserva cancelada", icon: CalendarX },
} as const;

/** Cartão da reserva. Só existe quando o sistema de reservas devolveu os dados neste turno. */
export function ReservationCard({ reservation: r }: { reservation: Reservation }) {
  const [copied, setCopied] = useState(false);
  const cancelled = r.tipo === "cancelada" || r.situacao === "CANCELADA";
  const { title, icon: Icon } = HEADER[r.tipo];

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(r.codigo);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  const facts: { label: string; value: string }[] = [];
  if (r.data) facts.push({ label: "Data", value: formatReservationDate(r.data, r.dia_semana) });
  if (r.horario) facts.push({ label: "Horário", value: r.horario });
  if (r.num_pessoas) {
    facts.push({ label: "Pessoas", value: `${r.num_pessoas} ${r.num_pessoas === 1 ? "pessoa" : "pessoas"}` });
  }
  const zone = zoneName(r.zona);
  if (zone) facts.push({ label: "Onde", value: zone });

  // Condições da reserva ficam no rodapé, em frase; os campos acima são só os dados da mesa.
  const conditions: string[] = [];
  if (r.tolerancia_minutos && !cancelled) conditions.push(`Tolerância de ${r.tolerancia_minutos} min de atraso.`);
  if (r.tipo === "cancelada") {
    conditions.push(
      r.dentro_da_janela_gratuita === false
        ? (r.aviso ?? "Cancelamento com menos de 4 horas de antecedência.")
        : "Cancelamento sem custo.",
    );
  } else if (r.cancelamento_sem_onus_ate && !cancelled) {
    conditions.push(`Cancelamento sem custo até ${formatDeadline(r.cancelamento_sem_onus_ate)}.`);
  } else if (r.situacao) {
    conditions.push(`Situação no sistema: ${r.situacao.toLowerCase()}.`);
  }
  const footer = conditions.length > 0 ? conditions.join(" ") : null;

  return (
    <section className={`${styles.card} ${cancelled ? styles.cancelled : styles[r.tipo]}`} aria-label={title}>
      <header className={styles.header}>
        <span className={styles.status}>
          <Icon size={16} strokeWidth={1.9} aria-hidden="true" />
          {title}
        </span>
        <span className={styles.origin}>Emitida pelo sistema de reservas</span>
      </header>

      <div className={styles.codeRow}>
        <div>
          <span className={styles.codeLabel}>Código</span>
          <p className={styles.code}>{r.codigo}</p>
        </div>
        {cancelled ? null : (
          <button type="button" className={styles.copy} onClick={copyCode}>
            {copied ? <Check size={15} strokeWidth={2} aria-hidden="true" /> : <Copy size={15} strokeWidth={1.75} aria-hidden="true" />}
            {copied ? "Copiado" : "Copiar"}
          </button>
        )}
      </div>

      {facts.length > 0 ? (
        <dl className={styles.facts}>
          {facts.map((f) => (
            <div key={f.label}>
              <dt>{f.label}</dt>
              <dd>{f.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {footer ? <p className={styles.footer}>{footer}</p> : null}
    </section>
  );
}
