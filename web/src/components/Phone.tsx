import styles from "./Phone.module.css";

export const PHONE = "(51) 3030-4050";

/** Telefone da casa: sempre clicável e nunca partido no hífen. */
export function Phone() {
  return (
    <a href="tel:+555130304050" className={styles.phone}>
      {PHONE}
    </a>
  );
}
