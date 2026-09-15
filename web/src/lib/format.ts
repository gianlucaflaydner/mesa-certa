import type { Citation } from "./api";

const SOURCE_NAMES: Record<string, string> = {
  "cardapio.md": "Cardápio",
  "politicas.md": "Políticas da casa",
  "faq.md": "Perguntas frequentes",
  "sobre.md": "Sobre a casa",
};

export function sourceName(source: string): string {
  return SOURCE_NAMES[source] ?? source.replace(/\.md$/, "");
}

/** Uma etiqueta por fonte e seção, na ordem em que apareceram. */
export function uniqueCitations(citations: Citation[]): Citation[] {
  const seen = new Set<string>();
  return citations.filter((c) => {
    const key = `${c.source}|${c.section}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/**
 * Tira do texto as linhas "Fonte: ..." que o modelo escreve no fim da resposta.
 * Só quando há citações estruturadas, que viram etiquetas; sem elas, o texto fica intacto.
 */
export function stripSourceLines(reply: string, hasCitations: boolean): string {
  if (!hasCitations) return reply;
  return reply
    .split("\n")
    .filter((line) => !/^\s*(\*\*|_)?fontes?:?(\*\*|_)?\s*:?/i.test(line))
    .join("\n")
    .trim();
}

const WEEKDAYS = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];

/** "2026-09-19" vira "sábado, 19/09". Sem Date com fuso: a data da reserva é local da casa. */
export function formatReservationDate(isoDate: string, weekday?: string | null): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate);
  if (!match) return isoDate;
  const [, year, month, day] = match;
  const name =
    weekday ?? WEEKDAYS[new Date(Number(year), Number(month) - 1, Number(day)).getDay()];
  return `${name}, ${day}/${month}`;
}

/** "2026-09-19T16:00:00-03:00" vira "sábado, 19/09 às 16:00", lendo a hora como está no texto. */
export function formatDeadline(isoDateTime: string): string {
  const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})/.exec(isoDateTime);
  if (!match) return isoDateTime;
  return `${formatReservationDate(match[1])} às ${match[2]}:${match[3]}`;
}

export function zoneName(zone: string | null | undefined): string | null {
  if (!zone) return null;
  return { salao: "Salão principal", varanda: "Varanda", mezanino: "Mezanino" }[zone] ?? zone;
}

export function greeting(hour: number): string {
  if (hour < 5 || hour >= 18) return "Boa noite";
  if (hour < 12) return "Bom dia";
  return "Boa tarde";
}

export function formatSeconds(ms: number): string {
  return `${(ms / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} s`;
}
