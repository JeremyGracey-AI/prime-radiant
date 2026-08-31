"""Season-week encoding, flusion convention: the flu season starts at CDC epiweek 31.

season_week 1 = epiweek 31; the new calendar year continues the count (epiweek w in
Jan-Jul maps to 22 + w). Christmas lands in epiweek 52 = season week 22, giving
delta_xmas = season_week - 22 as a signed distance to the seasonal peak anchor.
"""

from datetime import date

from epiweeks import Week

_SEASON_START_EPIWEEK = 31
_XMAS_SEASON_WEEK = 22


def season_week(day: date) -> int:
    week = Week.fromdate(day, system="cdc").week
    if week >= _SEASON_START_EPIWEEK:
        return week - _SEASON_START_EPIWEEK + 1
    return week + _XMAS_SEASON_WEEK


def delta_xmas(week: int) -> int:
    return week - _XMAS_SEASON_WEEK
