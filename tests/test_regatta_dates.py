"""Tests for date parsing in scraper/parsers/metadata.py."""

from bs4 import BeautifulSoup
from scraper.parsers.metadata import extract


def _meta(date_text: str, datetime_attr: str):
    html = (
        f'<time itemprop="startDate" datetime="{datetime_attr}">'
        f"{date_text}</time>"
    )
    return extract(BeautifulSoup(html, "lxml"))


def test_same_month_range():
    m = _meta("March 6-8, 2026", "2026-03-06T10:00")
    assert (m.regatta_start, m.regatta_end) == ("2026-03-06", "2026-03-08")


def test_same_month_range_start_from_attr():
    m = _meta("March 6-8, 2026", "2026-03-06T15:30-05:00")
    assert m.regatta_start == "2026-03-06"


def test_cross_month_range():
    m = _meta("February 28 - March 1, 2026", "2026-02-28T10:00")
    assert (m.regatta_start, m.regatta_end) == ("2026-02-28", "2026-03-01")


def test_cross_month_january_february():
    m = _meta("January 31 - February 1, 2026", "2026-01-31T10:00")
    assert (m.regatta_start, m.regatta_end) == ("2026-01-31", "2026-02-01")


def test_single_day():
    m = _meta("March 6, 2026", "2026-03-06T10:00")
    assert (m.regatta_start, m.regatta_end) == ("2026-03-06", "2026-03-06")


def test_no_time_element():
    m = extract(BeautifulSoup("<div>No date here</div>", "lxml"))
    assert (m.regatta_start, m.regatta_end) == ("", "")


def test_datetime_attr_date_only():
    m = _meta("March 6-8, 2026", "2026-03-06")
    assert (m.regatta_start, m.regatta_end) == ("2026-03-06", "2026-03-08")


def test_end_before_start_not_possible():
    m = _meta("March 6-8, 2026", "2026-03-06T10:00")
    assert m.regatta_end >= m.regatta_start
