// Contrato com a API FastAPI (docs/SDD.md §9). Os tipos espelham src/mesa_certa/api/dto.py.

export type Citation = { source: string; section: string; chunk_id: string };

export type ToolCall = {
  name: string;
  ok: boolean;
  duration_ms: number;
  error_code: string | null;
};

export type Reservation = {
  tipo: "criada" | "consultada" | "cancelada";
  codigo: string;
  data?: string | null;
  dia_semana?: string | null;
  horario?: string | null;
  num_pessoas?: number | null;
  zona?: string | null;
  tolerancia_minutos?: number | null;
  cancelamento_sem_onus_ate?: string | null;
  situacao?: string | null;
  dentro_da_janela_gratuita?: boolean | null;
  aviso?: string | null;
};

export type ChatResponse = {
  session_id: string;
  trace_id: string;
  reply: string;
  citations: Citation[];
  tool_calls: ToolCall[];
  latency_ms: number;
  iterations: number;
  exhausted: boolean;
  guard_violations: string[];
  reservation: Reservation | null;
};

export type TraceToolCall = {
  name: string;
  args: unknown;
  ok: boolean;
  error_code: string | null;
  duration_ms: number;
};

export type TraceRetrieval = {
  query: string;
  chunk_ids: string[];
  scores: number[];
  below_threshold: boolean;
};

export type Trace = {
  trace_id: string;
  iterations: number;
  exhausted: boolean;
  suspeita_injecao: boolean;
  guard_violations: string[];
  total_ms: number;
  tool_calls: TraceToolCall[];
  retrievals: TraceRetrieval[];
  llm_calls: {
    iteration: number;
    input_tokens: number;
    output_tokens: number;
    cache_read_input_tokens: number;
    duration_ms: number;
  }[];
};

export type ApiErrorKind =
  | "sessao_expirada"
  | "indisponivel"
  | "mensagem_longa"
  | "interno"
  | "rede";

export class ApiError extends Error {
  constructor(
    readonly kind: ApiErrorKind,
    readonly status: number | null,
    readonly traceId: string | null = null,
  ) {
    super(kind);
    this.name = "ApiError";
  }
}

export const MAX_MESSAGE_CHARS = 2000;

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

export const DEBUG_UI = process.env.NEXT_PUBLIC_DEBUG_UI === "true";

export function errorKindFor(status: number): ApiErrorKind {
  if (status === 410) return "sessao_expirada";
  if (status === 422) return "mensagem_longa";
  if (status === 503 || status === 502 || status === 504) return "indisponivel";
  return "interno";
}

async function request<T>(path: string, init: RequestInit, baseUrl: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("rede", null);
  }
  if (response.ok) return (await response.json()) as T;

  let traceId: string | null = null;
  try {
    const body = (await response.json()) as { trace_id?: string };
    traceId = body.trace_id ?? null;
  } catch {
    // Corpo sem JSON: o status já basta para escolher a mensagem.
  }
  throw new ApiError(errorKindFor(response.status), response.status, traceId);
}

export function postChat(
  message: string,
  sessionId: string | null,
  signal?: AbortSignal,
  baseUrl = API_URL,
): Promise<ChatResponse> {
  return request<ChatResponse>(
    "/chat",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId }),
      signal,
    },
    baseUrl,
  );
}

export function getTrace(traceId: string, signal?: AbortSignal, baseUrl = API_URL): Promise<Trace> {
  return request<Trace>(`/traces/${encodeURIComponent(traceId)}`, { signal }, baseUrl);
}
