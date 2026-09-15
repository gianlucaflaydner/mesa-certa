import { CloudOff, Hourglass, TriangleAlert, WifiOff, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import type { ApiErrorKind } from "@/lib/api";

import { Phone } from "./Phone";
import styles from "./Notice.module.css";

/** Erros exibidos na conversa. "mensagem_longa" aparece no próprio campo de mensagem. */
export type ThreadErrorKind = Exclude<ApiErrorKind, "mensagem_longa">;

const COPY: Record<ThreadErrorKind, { icon: LucideIcon; title: string; body: ReactNode; action: string; tone: string }> = {
  sessao_expirada: {
    icon: Hourglass,
    tone: "neutro",
    title: "Sua conversa expirou",
    body: "Ela ficou parada por mais de uma hora e o atendimento a encerrou. Comece uma nova para continuar.",
    action: "Começar nova conversa com esta mensagem",
  },
  indisponivel: {
    icon: CloudOff,
    tone: "atencao",
    title: "O assistente está indisponível agora",
    body: (
      <>
        Tente de novo em instantes ou ligue para <Phone />.
      </>
    ),
    action: "Tentar de novo",
  },
  rede: {
    icon: WifiOff,
    tone: "atencao",
    title: "Sem conexão",
    body: (
      <>
        Confira sua internet e tente de novo. Se preferir, ligue para <Phone />.
      </>
    ),
    action: "Tentar de novo",
  },
  interno: {
    icon: TriangleAlert,
    tone: "erro",
    title: "Algo deu errado do nosso lado",
    body: (
      <>
        A mensagem não foi processada. Tente de novo ou ligue para <Phone />.
      </>
    ),
    action: "Tentar de novo",
  },
};

type Props = { kind: ThreadErrorKind; traceId: string | null; onAction: () => void; disabled?: boolean };

export function Notice({ kind, traceId, onAction, disabled }: Props) {
  const { icon: Icon, title, body, action, tone } = COPY[kind];
  return (
    <div className={`${styles.notice} ${styles[tone]}`} role="alert">
      <Icon className={styles.icon} size={18} strokeWidth={1.9} aria-hidden="true" />
      <div className={styles.content}>
        <p className={styles.title}>{title}</p>
        <p className={styles.body}>{body}</p>
        {traceId ? (
          <p className={styles.trace}>
            Código para a equipe: <code>{traceId}</code>
          </p>
        ) : null}
        <button type="button" className={styles.action} onClick={onAction} disabled={disabled}>
          {action}
        </button>
      </div>
    </div>
  );
}
