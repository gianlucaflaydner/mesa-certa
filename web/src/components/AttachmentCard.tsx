import { Download, ExternalLink, FileText } from "lucide-react";

import { API_URL, type Attachment } from "@/lib/api";
import { fileUrl, formatFileSize } from "@/lib/format";

import styles from "./AttachmentCard.module.css";

/** Arquivo entregue pelo assistente (hoje, o cardápio em PDF), para abrir ou baixar. */
export function AttachmentCard({ attachment: a }: { attachment: Attachment }) {
  return (
    <section className={styles.card} aria-label={`Arquivo: ${a.titulo}`}>
      <span className={styles.icon} aria-hidden="true">
        <FileText size={20} strokeWidth={1.75} />
      </span>
      <div className={styles.info}>
        <p className={styles.title}>{a.titulo}</p>
        <p className={styles.meta}>PDF · {formatFileSize(a.tamanho_kb)}</p>
      </div>
      <div className={styles.actions}>
        <a className={styles.action} href={fileUrl(API_URL, a.url)} target="_blank" rel="noreferrer">
          <ExternalLink size={15} strokeWidth={1.75} aria-hidden="true" />
          Abrir
        </a>
        <a className={`${styles.action} ${styles.primary}`} href={fileUrl(API_URL, a.url, true)} download={a.arquivo}>
          <Download size={15} strokeWidth={1.9} aria-hidden="true" />
          Baixar
        </a>
      </div>
    </section>
  );
}
