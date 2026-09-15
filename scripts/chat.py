"""Chat com o agente no terminal, para teste manual com a API real do modelo.

Uso:
  python scripts/chat.py
  python scripts/chat.py --agora 2026-09-15T14:00:00-03:00 --debug
  python scripts/chat.py -m "Tem mesa pra 2 no sábado às 20h?"

Pré-requisitos: `make seed` e `make ingest`. Criação e cancelamento alteram o banco.
Digite "sair" ou Ctrl+C para encerrar.
"""

import argparse
from datetime import datetime

import anthropic

from mesa_certa.agent.factory import build_app, build_clock
from mesa_certa.agent.llm import ModelUnavailable
from mesa_certa.agent.loop import AgentLoop
from mesa_certa.agent.models import TurnResult
from mesa_certa.agent.session import Session
from mesa_certa.config import get_settings
from mesa_certa.observability.logging import configure_logging

_NO_CREDENTIALS = (
    "Credencial da API ausente ou inválida. Defina ANTHROPIC_API_KEY no .env "
    "ou faça login com `ant auth login`."
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--agora", help="fixa o relógio, em ISO 8601 com fuso")
    parser.add_argument("--debug", action="store_true", help="mostra tools, citações e tokens")
    parser.add_argument("-m", "--mensagem", action="append", help="mensagem única (repetível)")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging("WARNING")
    clock = build_clock(settings, datetime.fromisoformat(args.agora) if args.agora else None)
    app = build_app(settings, clock)
    session = app.sessions.create()

    try:
        if args.mensagem:
            for message in args.mensagem:
                print(f"> {message}")
                _turn(app.agent, session, message, args.debug)
            return
        while True:
            try:
                message = input("\nvocê> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if message.lower() in {"sair", "exit", "quit"}:
                break
            if message:
                _turn(app.agent, session, message, args.debug)
    finally:
        app.close()


def _turn(agent: AgentLoop, session: Session, message: str, debug: bool) -> None:
    try:
        result = agent.run_turn(session, message)
    except ModelUnavailable as exc:
        print(f"\n[modelo indisponível] {exc}")
        return
    except anthropic.AuthenticationError:
        raise SystemExit(_NO_CREDENTIALS) from None
    except TypeError as exc:
        # O SDK só percebe a falta de credencial na primeira chamada, como TypeError.
        if "authentication" not in str(exc):
            raise
        raise SystemExit(_NO_CREDENTIALS) from None
    print(f"\nassistente> {result.reply}")
    if debug:
        _print_debug(result)


def _print_debug(result: TurnResult) -> None:
    print(f"\n  trace {result.trace_id} | {result.iterations} iterações | {result.latency_ms} ms")
    for call in result.tool_calls:
        status = "ok" if call.ok else f"erro {call.error_code}"
        print(f"  tool {call.name}: {status} ({call.duration_ms} ms)")
    for citation in result.citations:
        print(f"  trecho {citation.chunk_id}")
    u = result.usage
    print(
        f"  tokens: entrada {u.input_tokens}, saída {u.output_tokens}, "
        f"cache lido {u.cache_read_input_tokens}"
    )
    if result.exhausted:
        print("  ESGOTOU o limite de iterações")


if __name__ == "__main__":
    main()
