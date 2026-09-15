import { describe, expect, it } from "vitest";

import { errorKindFor } from "./api";
import {
  formatDeadline,
  formatReservationDate,
  greeting,
  sourceName,
  stripSourceLines,
  uniqueCitations,
  zoneName,
} from "./format";

describe("stripSourceLines", () => {
  const reply = "Temos três opções sem glúten.\n\nFonte: cardapio.md › Pratos principais";

  it("remove a linha de fonte quando há citações estruturadas", () => {
    expect(stripSourceLines(reply, true)).toBe("Temos três opções sem glúten.");
  });

  it("mantém o texto intacto sem citações", () => {
    expect(stripSourceLines(reply, false)).toBe(reply);
  });

  it("reconhece variações em negrito e plural", () => {
    expect(stripSourceLines("Ok.\n**Fontes:** faq.md", true)).toBe("Ok.");
  });

  it("não remove frases comuns que contêm a palavra", () => {
    const text = "A fonte de calor é a brasa de eucalipto.";
    expect(stripSourceLines(text, true)).toBe(text);
  });
});

describe("datas", () => {
  it("formata a data da reserva com o dia da semana", () => {
    expect(formatReservationDate("2026-09-19")).toBe("sábado, 19/09");
    expect(formatReservationDate("2026-09-19", "sábado")).toBe("sábado, 19/09");
  });

  it("formata o prazo de cancelamento sem converter fuso", () => {
    expect(formatDeadline("2026-09-19T16:00:00-03:00")).toBe("sábado, 19/09 às 16:00");
  });
});

describe("rótulos", () => {
  it("dá nome humano às fontes e zonas", () => {
    expect(sourceName("faq.md")).toBe("Perguntas frequentes");
    expect(sourceName("novo.md")).toBe("novo");
    expect(zoneName("varanda")).toBe("Varanda");
    expect(zoneName(null)).toBeNull();
  });

  it("deduplica citações pela fonte e seção", () => {
    const c = { source: "faq.md", section: "A › B", chunk_id: "x" };
    expect(uniqueCitations([c, { ...c, chunk_id: "y" }])).toHaveLength(1);
  });

  it("cumprimenta conforme a hora", () => {
    expect(greeting(9)).toBe("Bom dia");
    expect(greeting(14)).toBe("Boa tarde");
    expect(greeting(21)).toBe("Boa noite");
  });
});

describe("errorKindFor", () => {
  it("mapeia os status da API para mensagens", () => {
    expect(errorKindFor(410)).toBe("sessao_expirada");
    expect(errorKindFor(503)).toBe("indisponivel");
    expect(errorKindFor(422)).toBe("mensagem_longa");
    expect(errorKindFor(500)).toBe("interno");
  });
});
