import { PanelRight, SquarePen } from "lucide-react";

import { BrandMark } from "./BrandMark";
import styles from "./TopBar.module.css";

type Props = {
  canReset: boolean;
  onReset: () => void;
  debug: boolean;
  debugOpen: boolean;
  onToggleDebug: () => void;
};

export function TopBar({ canReset, onReset, debug, debugOpen, onToggleDebug }: Props) {
  return (
    <header className={styles.bar}>
      <div className={styles.brand}>
        <BrandMark size={22} className={styles.mark} />
        <span className={styles.name}>Mesa Certa</span>
        <span className={styles.badge}>Assistente</span>
      </div>
      <div className={styles.actions}>
        {debug ? (
          <button
            type="button"
            className={styles.button}
            onClick={onToggleDebug}
            aria-expanded={debugOpen}
            aria-controls="bastidores"
          >
            <PanelRight size={16} strokeWidth={1.75} aria-hidden="true" />
            <span>Bastidores</span>
          </button>
        ) : null}
        {canReset ? (
          <button type="button" className={styles.button} onClick={onReset}>
            <SquarePen size={16} strokeWidth={1.75} aria-hidden="true" />
            <span>Nova conversa</span>
          </button>
        ) : null}
      </div>
    </header>
  );
}
