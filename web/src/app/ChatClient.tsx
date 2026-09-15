"use client";

import dynamic from "next/dynamic";

// Só no cliente: a conversa em andamento é lida do sessionStorage ao abrir a tela.
export const ChatClient = dynamic(
  () => import("@/components/ChatScreen").then((module) => module.ChatScreen),
  { ssr: false },
);
