from datetime import datetime
from zoneinfo import ZoneInfo

from mesa_certa.agent.prompts import RULES_PROMPT, build_system_prompt

SP = ZoneInfo("America/Sao_Paulo")


def test_regras_em_bloco_cacheado_e_data_em_bloco_separado() -> None:
    blocos = build_system_prompt(datetime(2026, 9, 15, 14, 0, tzinfo=SP))

    assert blocos[0]["text"] == RULES_PROMPT
    assert blocos[0]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in blocos[1]
    assert "2026-09-15 14:00 (terça)" in blocos[1]["text"]


def test_bloco_de_regras_nao_muda_com_a_data() -> None:
    a = build_system_prompt(datetime(2026, 9, 15, 14, 0, tzinfo=SP))
    b = build_system_prompt(datetime(2026, 9, 19, 20, 30, tzinfo=SP))

    assert a[0] == b[0]
    assert a[1] != b[1]


def test_regras_carregam_as_decisoes_do_produto() -> None:
    assert "(51) 3030-4050" in RULES_PROMPT
    assert "Segunda-feira: fechado" in RULES_PROMPT
    assert "acima de 12 pessoas" in RULES_PROMPT
    assert "20 minutos" in RULES_PROMPT
    assert "encontrou_informacao = false" in RULES_PROMPT
    assert "Fonte: " in RULES_PROMPT


def test_prompt_sem_travessao() -> None:
    travessao, meia_risca = chr(0x2014), chr(0x2013)
    assert travessao not in RULES_PROMPT
    assert meia_risca not in RULES_PROMPT
