import pytest

from mesa_certa.agent.guards import SAFE_REPLY, ToolOutcome, check_reply

CRIADA = ToolOutcome("criar_reserva", True, {"codigo": "K7M2QP"})
CONSULTA_CONFIRMADA = ToolOutcome("consultar_reserva", True, {"situacao": "CONFIRMADA"})
CONSULTA_CANCELADA = ToolOutcome("consultar_reserva", True, {"situacao": "CANCELADA"})
CANCELADA = ToolOutcome("cancelar_reserva", True, {"situacao": "CANCELADA"})
JA_CANCELADA = ToolOutcome("cancelar_reserva", False, None, "JA_CANCELADA")
DISPONIVEL = ToolOutcome("consultar_disponibilidade", True, {"disponivel": True})


def test_resposta_limpa_passa_intacta() -> None:
    reply = "Temos mesa às 20h. Posso reservar? Preciso do seu nome e telefone."

    outcome = check_reply(reply, [DISPONIVEL], "tem mesa?")

    assert outcome.reply == reply
    assert not outcome.replaced


def test_codigo_inventado_troca_a_resposta() -> None:
    outcome = check_reply("Pronto! Seu código é X7Y8Z9.", [], "reserva pra 2")

    assert outcome.reply == SAFE_REPLY
    assert outcome.violations == ["CODIGO_NAO_EMITIDO:X7Y8Z9"]


def test_codigo_vindo_de_tool_e_aceito() -> None:
    reply = "Reserva confirmada! Código K7M2QP, sábado às 20h, tolerância de 20 minutos."

    outcome = check_reply(reply, [CRIADA], '{"ok": true, "data": {"codigo": "K7M2QP"}}')

    assert not outcome.replaced


def test_codigo_digitado_pelo_cliente_e_aceito() -> None:
    reply = "Para cancelar a reserva K7M2QP, pode confirmar?"

    assert not check_reply(reply, [], "quero cancelar a K7M2QP").replaced


@pytest.mark.parametrize("reply", ["Bem-vindo ao BRASIL e ao MESA", "Veja o PRATOS do dia"])
def test_palavra_em_maiusculas_sem_digito_nao_e_codigo(reply: str) -> None:
    assert not check_reply(reply, [], "").replaced


def test_codigo_so_de_letras_perto_de_codigo_e_checado() -> None:
    outcome = check_reply("Seu código: ABCDEF", [], "")

    assert outcome.violations == ["CODIGO_NAO_EMITIDO:ABCDEF"]


@pytest.mark.parametrize(
    "reply",
    ["Sua reserva foi criada.", "Reservei a mesa para você.", "Reserva confirmada para sábado."],
)
def test_criacao_sem_tool_troca_a_resposta(reply: str) -> None:
    outcome = check_reply(reply, [DISPONIVEL], "")

    assert outcome.replaced
    assert outcome.reply == SAFE_REPLY


def test_criacao_com_tool_ok_e_aceita() -> None:
    assert not check_reply("Reserva confirmada para sábado.", [CRIADA], "").replaced


def test_criacao_com_tool_que_falhou_troca_a_resposta() -> None:
    falhou = ToolOutcome("criar_reserva", False, None, "SEM_DISPONIBILIDADE")

    assert check_reply("Reserva feita!", [falhou], "").violations == ["CRIACAO_SEM_TOOL"]


def test_status_confirmada_apos_consulta_e_aceito() -> None:
    reply = "Sua reserva está confirmada para sábado às 20h."

    assert not check_reply(reply, [CONSULTA_CONFIRMADA], "").replaced


def test_negacao_nao_conta_como_afirmacao() -> None:
    reply = "Ainda não reservei nada: a reserva não foi criada. Posso seguir?"

    assert not check_reply(reply, [DISPONIVEL], "").replaced


@pytest.mark.parametrize("reply", ["Cancelei sua reserva.", "Pronto, reserva cancelada."])
def test_cancelamento_sem_tool_troca_a_resposta(reply: str) -> None:
    assert check_reply(reply, [], "").violations == ["CANCELAMENTO_SEM_TOOL"]


@pytest.mark.parametrize("outcome", [CANCELADA, JA_CANCELADA, CONSULTA_CANCELADA])
def test_cancelamento_confirmado_por_tool_e_aceito(outcome: ToolOutcome) -> None:
    assert not check_reply("A reserva foi cancelada.", [outcome], "").replaced
