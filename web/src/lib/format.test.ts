import { describe, expect, it } from "vitest";

import { errorKindFor } from "./api";
import {
  fileUrl,
  formatDeadline,
  formatFileSize,
  formatReservationDate,
  greeting,
  linkPhone,
  sourceName,
  splitChunkId,
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

describe("arquivos", () => {
  it("formata o tamanho em KB ou MB", () => {
    expect(formatFileSize(512)).toBe("512 KB");
    expect(formatFileSize(1834)).toBe("1,8 MB");
  });

  it("monta o endereço de abrir e de baixar", () => {
    expect(fileUrl("http://localhost:8000/", "/arquivos/cardapio.pdf")).toBe(
      "http://localhost:8000/arquivos/cardapio.pdf",
    );
    expect(fileUrl("http://localhost:8000", "/arquivos/cardapio.pdf", true)).toBe(
      "http://localhost:8000/arquivos/cardapio.pdf?download=1",
    );
  });
});

describe("linkPhone", () => {
  it("transforma o telefone da casa em link tel", () => {
    expect(linkPhone("Ligue para (51) 3030-4050.")).toBe("Ligue para [(51) 3030-4050](tel:+555130304050).");
  });

  it("não duplica um link que já existe", () => {
    const text = "[(51) 3030-4050](tel:+555130304050)";
    expect(linkPhone(text)).toBe(text);
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

  it("separa o chunk_id em arquivo e caminho legível", () => {
    expect(splitChunkId("faq.md#restricoes-alimentares>contaminacao-cruzada#0")).toEqual({
      source: "faq.md",
      path: "restricoes-alimentares › contaminacao-cruzada",
    });
    expect(splitChunkId("cardapio.md#sobremesas#1")).toEqual({ source: "cardapio.md", path: "sobremesas (parte 2)" });
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
