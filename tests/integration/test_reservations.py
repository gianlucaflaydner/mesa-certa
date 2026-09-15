import threading
from datetime import date, time

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from mesa_certa.db.models import DiningTable, Reservation
from mesa_certa.domain import codes
from mesa_certa.domain.availability import AvailabilityService
from mesa_certa.domain.date_resolver import FixedClock
from mesa_certa.domain.errors import (
    AlreadyCancelled,
    DayClosed,
    GroupTooLarge,
    NoAvailability,
    OutsideBookingWindow,
    ReservationNotFound,
)
from mesa_certa.domain.reservations import (
    CreateReservationCommand,
    ReservationDetails,
    ReservationService,
)
from mesa_certa.domain.rules import ReservationStatus, Zone
from tests.integration.conftest import at


def command(
    day: date, start: time, size: int = 2, name: str = "Cliente Teste"
) -> CreateReservationCommand:
    return CreateReservationCommand(
        name=name, phone="51999990000", party_size=size, date=day, time=start
    )


def count_reservations(factory: sessionmaker[Session]) -> int:
    with factory() as session:
        return session.scalar(select(func.count(Reservation.id))) or 0


def test_cria_reserva(reservations: ReservationService) -> None:
    details = reservations.create(command(date(2026, 9, 18), time(19, 0)))

    assert len(details.code) == 6
    assert set(details.code) <= set(codes.ALPHABET)
    assert details.status is ReservationStatus.CONFIRMADA
    assert details.zone is Zone.VARANDA
    assert details.table_labels == ("V1",)
    assert details.end_time == time(20, 30)
    assert details.free_cancellation_until == at(2026, 9, 18, 15)
    assert details.late_tolerance_minutes == 20

    found = reservations.get_by_code(details.code.lower())
    assert found == details


def test_consulta_codigo_inexistente(reservations: ReservationService) -> None:
    assert reservations.get_by_code("ZZZZZZ") is None


def test_consulta_reserva_do_seed(reservations: ReservationService) -> None:
    found = reservations.get_by_code("K7M2QP")

    assert found is not None
    assert found.customer_name == "Bruna Alves"
    assert (found.date, found.start_time, found.party_size) == (date(2026, 9, 26), time(20, 0), 2)
    assert found.zone is Zone.VARANDA


def test_grupo_de_7_ocupa_duas_mesas(reservations: ReservationService) -> None:
    details = reservations.create(command(date(2026, 9, 17), time(19, 0), size=7))

    assert details.table_labels == ("M1", "M2")
    assert details.end_time == time(21, 0)


def test_grupo_de_13_nao_cria(
    reservations: ReservationService, session_factory: sessionmaker[Session]
) -> None:
    with pytest.raises(GroupTooLarge):
        reservations.create(command(date(2026, 9, 17), time(19, 0), size=13))
    assert count_reservations(session_factory) == 13


def test_horario_lotado(
    reservations: ReservationService, session_factory: sessionmaker[Session]
) -> None:
    with pytest.raises(NoAvailability) as exc:
        reservations.create(command(date(2026, 9, 19), time(20, 0), size=6))
    assert exc.value.details == {"data": "2026-09-19", "horario": "20:00", "num_pessoas": 6}
    assert count_reservations(session_factory) == 13


def test_dia_fechado(reservations: ReservationService) -> None:
    with pytest.raises(DayClosed) as exc:
        reservations.create(command(date(2026, 9, 21), time(20, 0)))
    assert exc.value.details["proxima_data_aberta"] == "2026-09-22"


def test_limite_exato_de_60_minutos(
    session_factory: sessionmaker[Session], clock: FixedClock
) -> None:
    service = ReservationService(session_factory, clock)
    clock.instant = at(2026, 9, 16, 17, 0)
    service.create(command(date(2026, 9, 16), time(18, 0)))

    clock.instant = at(2026, 9, 16, 17, 1)
    with pytest.raises(OutsideBookingWindow):
        service.create(command(date(2026, 9, 16), time(18, 0)))


def test_limite_exato_de_60_dias(reservations: ReservationService, clock: FixedClock) -> None:
    clock.instant = at(2026, 9, 15, 12, 30)
    reservations.create(command(date(2026, 11, 14), time(12, 30)))

    with pytest.raises(OutsideBookingWindow):
        reservations.create(command(date(2026, 11, 14), time(13, 0)))


def test_colisao_de_codigo_tenta_de_novo(
    reservations: ReservationService, monkeypatch: pytest.MonkeyPatch
) -> None:
    sequence = iter(["K7M2QP", "W4X9HT", "ABCDEF"])
    monkeypatch.setattr(codes, "generate_code", lambda rng=None: next(sequence))

    details = reservations.create(command(date(2026, 9, 18), time(19, 0)))

    assert details.code == "ABCDEF"


def test_concorrencia_na_ultima_mesa(
    session_factory: sessionmaker[Session], clock: FixedClock
) -> None:
    service = ReservationService(session_factory, clock)
    day, start = date(2026, 9, 17), time(20, 0)
    for _ in range(3):
        service.create(command(day, start, size=6))
    assert AvailabilityService(session_factory, clock).check(day, 6, start).requested.available

    barrier = threading.Barrier(2)
    successes: list[ReservationDetails] = []
    failures: list[Exception] = []

    def attempt(name: str) -> None:
        barrier.wait()
        try:
            successes.append(service.create(command(day, start, size=6, name=name)))
        except Exception as exc:
            failures.append(exc)

    threads = [threading.Thread(target=attempt, args=(n,)) for n in ("Primeiro", "Segundo")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert len(successes) == 1
    assert len(failures) == 1
    assert isinstance(failures[0], NoAvailability)
    assert successes[0].table_labels == ("M4",)
    assert count_reservations(session_factory) == 17  # 13 do seed, 3 antes e 1 vencedora


def test_cancelamento_com_antecedencia(reservations: ReservationService) -> None:
    result = reservations.cancel("K7M2QP", "Mudou a data")

    assert result.status is ReservationStatus.CANCELADA
    assert result.within_free_window
    found = reservations.get_by_code("K7M2QP")
    assert found is not None
    assert found.status is ReservationStatus.CANCELADA
    assert found.cancellation_reason == "Mudou a data"
    assert found.cancelled_at == at(2026, 9, 15, 14)


@pytest.mark.parametrize(
    ("hour", "minute", "within"),
    [(15, 59, True), (16, 0, True), (16, 1, False)],
)
def test_cancelamento_perto_do_limite_de_4_horas(
    reservations: ReservationService, clock: FixedClock, hour: int, minute: int, within: bool
) -> None:
    clock.instant = at(2026, 9, 26, hour, minute)  # reserva às 20:00

    result = reservations.cancel("K7M2QP")

    assert result.within_free_window is within
    assert result.status is ReservationStatus.CANCELADA


def test_ja_cancelada(reservations: ReservationService) -> None:
    with pytest.raises(AlreadyCancelled) as exc:
        reservations.cancel("W4X9HT")
    assert exc.value.code == "JA_CANCELADA"


def test_cancelar_duas_vezes(reservations: ReservationService) -> None:
    reservations.cancel("K7M2QP")
    with pytest.raises(AlreadyCancelled):
        reservations.cancel("k7m2qp")


def test_cancelar_inexistente(reservations: ReservationService) -> None:
    with pytest.raises(ReservationNotFound):
        reservations.cancel("ZZZZZZ")


def test_cancelamento_libera_a_mesa(
    reservations: ReservationService,
    availability: AvailabilityService,
    session_factory: sessionmaker[Session],
) -> None:
    sat = date(2026, 9, 19)
    assert not availability.check(sat, 6, time(20, 0)).requested.available

    with session_factory() as session:
        code = session.scalars(
            select(Reservation.code)
            .join(Reservation.tables)
            .where(Reservation.reservation_date == "2026-09-19", DiningTable.label == "M3")
        ).one()
    reservations.cancel(code)

    result = availability.check(sat, 6, time(20, 0))
    assert result.requested.available
    assert result.requested.zone is Zone.MEZANINO
