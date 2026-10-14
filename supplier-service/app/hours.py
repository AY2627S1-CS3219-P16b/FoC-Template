"""Operating days and the "is it open now?" rule.

A supplier has one daily time range and the weekdays it trades. A closing time
before the opening time means trading past midnight, and that late part of the
shift belongs to the day it started: Supersnacks open 18:00 to 02:00 on Friday
is still open at 01:00 on Saturday even if it does not trade on Saturday.
"""

from datetime import datetime, time, timedelta, timezone

DAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")

# Every supplier is on campus. Singapore has kept UTC+8 with no daylight saving
# since 1982, so a fixed offset avoids depending on the container's tz database.
CAMPUS_TIMEZONE = timezone(timedelta(hours=8))

OPEN_ALL_DAY = (time(0, 0), time(23, 59))

# Shorthand accepted in the seed CSV, alongside ranges such as MON-FRI and
# lists such as MON,WED,FRI.
DAY_ALIASES = {"DAILY": DAYS, "WEEKDAYS": DAYS[:5], "WEEKENDS": DAYS[5:]}


def normalize_days(values: list[str]) -> list[str]:
    """Upper-case, de-duplicated, in week order; at least one day."""
    days = set()
    for value in values:
        day = value.strip().upper()
        if day not in DAYS:
            raise ValueError(f"unknown day {value!r}; use {', '.join(DAYS)}")
        days.add(day)
    if not days:
        raise ValueError("choose at least one operating day")
    return [day for day in DAYS if day in days]


def parse_days(text: str) -> list[str]:
    """Read CSV shorthand: DAILY, WEEKDAYS, MON-FRI, or MON,WED,FRI."""
    days = []
    for part in text.split(","):
        part = part.strip().upper()
        if part in DAY_ALIASES:
            days.extend(DAY_ALIASES[part])
        elif "-" in part:
            start, end = (day.strip() for day in part.split("-", 1))
            if start not in DAYS or end not in DAYS or DAYS.index(start) > DAYS.index(end):
                raise ValueError(f"invalid day range {part!r}; write it like MON-FRI")
            days.extend(DAYS[DAYS.index(start):DAYS.index(end) + 1])
        elif part:
            days.append(part)
    return normalize_days(days)


def is_open(opening: time, closing: time, days: list[str], now: datetime | None = None) -> bool:
    """Whether a supplier with these hours is trading at `now` (campus time)."""
    now = (now or datetime.now(CAMPUS_TIMEZONE)).astimezone(CAMPUS_TIMEZONE)
    today = DAYS[now.weekday()]
    yesterday = DAYS[(now.weekday() - 1) % 7]
    current = now.time().replace(tzinfo=None)

    if (opening, closing) == OPEN_ALL_DAY:
        return today in days
    if opening <= closing:
        return today in days and opening <= current < closing
    # Past midnight: the evening part of today's shift, or the early-morning
    # tail of yesterday's.
    return (today in days and current >= opening) or (yesterday in days and current < closing)
