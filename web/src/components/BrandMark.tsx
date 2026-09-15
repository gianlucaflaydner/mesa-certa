type Props = { size?: number; lit?: boolean; className?: string };

/** Três barras de grelha com a chama por cima, desenhadas no mesmo traço. `lit` acende a chama. */
export function BrandMark({ size = 28, lit = false, className }: Props) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M16 3.5c-.9 2.6-3.9 4.4-3.9 7.9a3.9 3.9 0 0 0 7.8 0c0-1.6-.8-2.8-1.7-3.9-.2 1.3-.9 2.1-1.8 2.4.6-2.1.4-4.4-.4-6.4Z"
        stroke="currentColor"
        fill={lit ? "currentColor" : "none"}
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M4 19.5h24M4 24h24M4 28.5h24" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" />
      <path d="M8 17.5v12.5M24 17.5v12.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" />
    </svg>
  );
}
