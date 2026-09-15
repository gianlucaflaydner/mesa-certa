from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from mesa_certa.agent.session import Session, SessionExpired, SessionStore
from mesa_certa.domain.date_resolver import FixedClock

AGORA = datetime(2026, 9, 15, 14, tzinfo=ZoneInfo("America/Sao_Paulo"))


def _turno_com_tool(session: Session, n: int) -> None:
    session.append_user(f"pergunta {n}")
    session.append_assistant(
        [{"type": "tool_use", "id": f"toolu_{n}", "name": "eco", "input": {"texto": str(n)}}]
    )
    session.append_tool_results(
        [{"type": "tool_result", "tool_use_id": f"toolu_{n}", "content": "{}"}]
    )
    session.append_assistant([{"type": "text", "text": f"resposta {n}"}])


def _pares_integros(messages: list[dict[str, Any]]) -> bool:
    pedidos: set[str] = set()
    for message in messages:
        for block in message["content"] if isinstance(message["content"], list) else []:
            if block["type"] == "tool_use":
                pedidos.add(block["id"])
            if block["type"] == "tool_result" and block["tool_use_id"] not in pedidos:
                return False
    return True


def test_historico_preserva_ordem_e_formato() -> None:
    session = Session(id="s", last_activity=AGORA)
    _turno_com_tool(session, 1)

    messages = session.to_api_messages()

    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    assert messages[0]["content"] == "pergunta 1"


@pytest.mark.parametrize("max_messages", [3, 4, 5, 6, 7, 20])
def test_poda_nunca_deixa_tool_result_orfao(max_messages: int) -> None:
    session = Session(id="s", last_activity=AGORA, max_messages=max_messages)

    for n in range(1, 8):
        _turno_com_tool(session, n)
        messages = session.to_api_messages()
        assert _pares_integros(messages)
        assert messages[0]["role"] == "user"
        assert isinstance(messages[0]["content"], str)


def test_poda_descarta_turnos_antigos_e_mantem_o_atual() -> None:
    session = Session(id="s", last_activity=AGORA, max_messages=5)
    for n in range(1, 4):
        _turno_com_tool(session, n)

    session.append_user("pergunta nova")
    messages = session.to_api_messages()

    assert messages[-1]["content"] == "pergunta nova"
    assert "pergunta 1" not in [m["content"] for m in messages]
    assert len(messages) <= 5


def test_to_api_messages_devolve_copia() -> None:
    session = Session(id="s", last_activity=AGORA)
    session.append_user("oi")

    session.to_api_messages().clear()

    assert len(session.messages) == 1


def test_store_cria_e_recupera_sessao() -> None:
    store = SessionStore(FixedClock(AGORA), ttl_minutes=60, max_messages=10)

    session = store.create()

    assert store.get(session.id) is session
    assert store.get_or_create(session.id) is session
    assert store.get_or_create(None) is not session
    assert session.max_messages == 10


def test_sessao_inexistente_e_tratada_como_expirada() -> None:
    store = SessionStore(FixedClock(AGORA))

    with pytest.raises(SessionExpired):
        store.get("nao-existe")


def test_ttl_expira_por_inatividade_e_uso_renova() -> None:
    clock = FixedClock(AGORA)
    store = SessionStore(clock, ttl_minutes=60)
    session = store.create()

    clock.instant = AGORA + timedelta(minutes=59)
    store.get(session.id)
    clock.instant = AGORA + timedelta(minutes=118)
    assert store.get(session.id) is session

    clock.instant = AGORA + timedelta(minutes=179)
    with pytest.raises(SessionExpired):
        store.get(session.id)
    with pytest.raises(SessionExpired):
        store.get(session.id)


def test_purge_remove_so_as_expiradas() -> None:
    clock = FixedClock(AGORA)
    store = SessionStore(clock, ttl_minutes=60)
    antiga = store.create()
    clock.instant = AGORA + timedelta(minutes=30)
    recente = store.create()

    clock.instant = AGORA + timedelta(minutes=61)

    assert store.purge_expired() == 1
    assert store.get(recente.id) is recente
    with pytest.raises(SessionExpired):
        store.get(antiga.id)
