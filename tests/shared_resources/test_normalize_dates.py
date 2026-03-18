"""Tests for shared-resources/scripts/normalize_dates.py"""

import normalize_dates as nd


# ─── normalize_year ───────────────────────────────────────────────────────────

def test_normalize_year_plain():
    assert nd.normalize_year("1925") == "1925"


def test_normalize_year_copyright():
    assert nd.normalize_year("©2021") == "2021"


def test_normalize_year_circa():
    assert nd.normalize_year("c.1985") == "1985"


def test_normalize_year_circa_no_dot():
    assert nd.normalize_year("c 1985") == "1985"


def test_normalize_year_bracketed():
    assert nd.normalize_year("[2003]") == "2003"


def test_normalize_year_in_sentence():
    assert nd.normalize_year("Published in May 2010 by Scribner") == "2010"


def test_normalize_year_none_input():
    assert nd.normalize_year(None) is None


def test_normalize_year_no_year():
    assert nd.normalize_year("no date given") is None


# ─── marc_008_date ────────────────────────────────────────────────────────────

def test_marc_008_date_valid():
    assert nd.marc_008_date("1925") == "1925"


def test_marc_008_date_none():
    assert nd.marc_008_date(None) == "    "


def test_marc_008_date_non_numeric():
    assert nd.marc_008_date("abcd") == "    "


# ─── format_pagination ────────────────────────────────────────────────────────

def test_format_pagination_bare_int():
    assert nd.format_pagination("250") == "250 pages"


def test_format_pagination_roman_plus_number():
    assert nd.format_pagination("xii, 250") == "xii, 250 pages"


def test_format_pagination_already_formatted():
    result = nd.format_pagination("300 pages")
    assert "page" in result.lower()
