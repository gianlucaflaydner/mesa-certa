import type { Metadata, Viewport } from "next";
import { Inter_Tight, JetBrains_Mono } from "next/font/google";

import "./globals.css";

// Face de interface neutra e legível, no registro dos chats da categoria.
const sans = Inter_Tight({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

// Só para dados de verdade (ids de trace e chunk, argumentos das tools, código de reserva).
const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Mesa Certa | Assistente",
  description:
    "Converse com o assistente do Mesa Certa: cardápio, ingredientes, políticas da casa e reservas de mesa no Bom Fim, Porto Alegre.",
};

export const viewport: Viewport = {
  themeColor: "#FAF9F6",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

const DIRECTION_CONTRACT = `
THESIS: o chat é a página. Um agente com RAG em ação, no formato que ChatGPT e Claude consagraram, com o campo de mensagem como estrela. Recusa site de restaurante e painel técnico.
OWN-WORLD: fundo quente quase branco, superfícies brancas, bordas finas; um acento de brasa só em enviar, foco e estados ativos; Inter Tight na interface e JetBrains Mono só para dados.
STORY: o cliente pergunta ou reserva, vê o assistente pensando, lê a resposta com as fontes e recebe a reserva como cartão com código.
FIRST VIEWPORT: marca pequena no topo; no centro, saudação curta, o campo de mensagem grande e as sugestões logo abaixo dele.
FORM: padrão da categoria (canon), escolhido pelo usuário; referências ChatGPT e Claude; seed a5aeb468.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md
`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <template dangerouslySetInnerHTML={{ __html: `<!--${DIRECTION_CONTRACT}-->` }} />
        {children}
      </body>
    </html>
  );
}
