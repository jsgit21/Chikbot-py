"""Pure date math for the BOTW/SOTW cycle window. No network, no clock reads.

Cycle: starts Saturday 10:00 ET, ends the following Monday 00:00 ET (i.e. end
of Sunday). After a cycle ends, the next one starts on the *second* Saturday
after the end Monday (a mandatory week+weekend break between cycles).
"""

import datetime

from ..shared import tz

_SATURDAY = 5


def _next_weekday_on_or_after(d, weekday):
    days_ahead = (weekday - d.weekday()) % 7
    return d + datetime.timedelta(days=days_ahead)


def next_cycle_window(after, weeks_out=0):
    """Return (starts_at, ends_at) as naive datetimes in ET (server-local time)
    for the next cycle.

    `after` is the previous cycle's end (a date or datetime); the next cycle
    starts on the second Saturday after it, i.e. one full break week beyond
    the first available Saturday. `weeks_out` shifts the start further out by
    that many additional weeks (0 = the default second-Saturday start).
    """
    if isinstance(after, datetime.datetime):
        after_date = after.date()
    else:
        after_date = after

    first_saturday = _next_weekday_on_or_after(after_date + datetime.timedelta(days=1), _SATURDAY)
    start_date = first_saturday + datetime.timedelta(weeks=1 + weeks_out)

    starts_at = datetime.datetime(start_date.year, start_date.month, start_date.day, 10, 0)
    end_date = start_date + datetime.timedelta(days=2)
    ends_at = datetime.datetime(end_date.year, end_date.month, end_date.day, 0, 0)
    return starts_at, ends_at


def to_wom_iso(dt_et):
    """Convert a naive ET (server-local) datetime to the UTC ISO-8601 string WOM expects."""
    dt_utc = dt_et.replace(tzinfo=tz.ET).astimezone(datetime.timezone.utc)
    return dt_utc.strftime('%Y-%m-%dT%H:%M:%S.000Z')


def weeks_since_last_cycle(last_end, now):
    """Return the number of full weeks between a cycle's end and now."""
    if isinstance(last_end, datetime.datetime):
        last_end = last_end.date()
    if isinstance(now, datetime.datetime):
        now = now.date()
    return (now - last_end).days // 7
