import { notFound } from "next/navigation";

import { ChatScreen } from "@/components/ChatScreen";

import { PREVIEWS } from "./fixtures";

/** Estados da interface com dados sintéticos, para revisão visual. Não existe em produção. */
export default async function Preview(props: PageProps<"/preview">) {
  if (process.env.NODE_ENV === "production") notFound();
  const { estado } = await props.searchParams;
  const preview = PREVIEWS[typeof estado === "string" ? estado : "conversa"];
  if (!preview) notFound();
  return <ChatScreen preview={preview} />;
}
