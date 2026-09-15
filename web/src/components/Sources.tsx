import { FileText } from "lucide-react";

import type { Citation } from "@/lib/api";
import { sourceName, uniqueCitations } from "@/lib/format";

import styles from "./Sources.module.css";

/** Fontes da resposta: de qual documento e seção da base veio cada informação. */
export function Sources({ citations }: { citations: Citation[] }) {
  const items = uniqueCitations(citations);
  if (items.length === 0) return null;

  return (
    <div className={styles.sources}>
      <span className={styles.heading}>{items.length === 1 ? "Fonte" : `${items.length} fontes`}</span>
      <ul className={styles.list}>
        {items.map((c) => (
          <li key={`${c.source}|${c.section}`} className={styles.chip} title={c.chunk_id}>
            <FileText size={14} strokeWidth={1.75} aria-hidden="true" />
            <span className={styles.doc}>{sourceName(c.source)}</span>
            <span className={styles.section}>{c.section}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
