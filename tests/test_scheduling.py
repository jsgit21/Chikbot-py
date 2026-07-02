"""Tests for scheduling.py: pure date math, no network, no clock reads."""
import datetime

from cogs.wise_old_man.competitions import scheduling


def test_next_cycle_window_matches_confirmed_example():
    # Real cycle from the PRD: ended Mon 6/22/2026 -> next starts Sat 7/04/2026.
    after = datetime.date(2026, 6, 22)
    starts_at, ends_at = scheduling.next_cycle_window(after)

    assert starts_at == datetime.datetime(2026, 7, 4, 14, 0)  # 10:00 ET (EDT, UTC-4)
    assert ends_at == datetime.datetime(2026, 7, 6, 4, 0)     # 00:00 ET (EDT, UTC-4)


def test_next_cycle_window_is_second_saturday_after_end():
    after = datetime.date(2026, 6, 22)  # a Monday
    starts_at, _ = scheduling.next_cycle_window(after)

    first_saturday_after = datetime.date(2026, 6, 27)
    second_saturday_after = datetime.date(2026, 7, 4)
    assert starts_at.date() != first_saturday_after
    assert starts_at.date() == second_saturday_after


def test_next_cycle_window_weeks_out_shifts_start():
    after = datetime.date(2026, 6, 22)
    default_start, _ = scheduling.next_cycle_window(after, weeks_out=0)
    shifted_start, _ = scheduling.next_cycle_window(after, weeks_out=2)

    assert (shifted_start - default_start).days == 14


def test_next_cycle_window_spans_dst_fall_back():
    # US DST ends Sun 11/1/2026. A cycle starting Sat 10/31 (still EDT,
    # UTC-4) and ending Mon 11/2 (already EST, UTC-5) picks up the extra
    # hour: 39 UTC hours between 10:00 ET Saturday and 00:00 ET Monday,
    # not the usual 38.
    after = datetime.date(2026, 10, 19)
    starts_at, ends_at = scheduling.next_cycle_window(after)

    assert starts_at == datetime.datetime(2026, 10, 31, 14, 0)  # EDT, UTC-4
    assert ends_at == datetime.datetime(2026, 11, 2, 5, 0)      # EST, UTC-5
    assert (ends_at - starts_at) == datetime.timedelta(hours=39)


def test_to_wom_iso_format():
    dt = datetime.datetime(2026, 7, 4, 14, 0, 0)
    assert scheduling.to_wom_iso(dt) == '2026-07-04T14:00:00.000Z'


def test_weeks_since_last_cycle():
    last_end = datetime.date(2026, 6, 22)
    now = datetime.date(2026, 7, 6)
    assert scheduling.weeks_since_last_cycle(last_end, now) == 2


def test_weeks_since_last_cycle_less_than_a_week():
    last_end = datetime.date(2026, 6, 22)
    now = datetime.date(2026, 6, 25)
    assert scheduling.weeks_since_last_cycle(last_end, now) == 0
