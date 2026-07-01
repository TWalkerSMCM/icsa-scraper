"""
Site-relative URL paths for scores.collegesailing.org.

Pure helpers so callers never hand-assemble path strings. Each returns a path
beginning with "/"; pair with ``scraper.Client`` (which prepends the base URL).
"""

from __future__ import annotations


def season(season: str) -> str:
    """Season index, e.g. ``/s26/``."""
    return f"/{season}/"


def regatta(season: str, slug: str) -> str:
    """Regatta overview page, e.g. ``/s26/hood-trophy/``."""
    return f"/{season}/{slug}/"


def full_scores(season: str, slug: str) -> str:
    """Combined full-scores page, e.g. ``/s26/hood-trophy/full-scores/``."""
    return f"/{season}/{slug}/full-scores/"


def division(season: str, slug: str, div: str) -> str:
    """One division's page, e.g. ``/s26/hood-trophy/A/``."""
    return f"/{season}/{slug}/{div}/"


def divisions(season: str, slug: str) -> str:
    """Combined-scoring summary page, e.g. ``/s26/hood-trophy/divisions/``."""
    return f"/{season}/{slug}/divisions/"


def all_races(season: str, slug: str) -> str:
    """Team-racing race list, e.g. ``/s26/hood-trophy/all/``."""
    return f"/{season}/{slug}/all/"


def rotations(season: str, slug: str) -> str:
    """Team-racing rotations/flights page, e.g. ``/s26/hood-trophy/rotations/``."""
    return f"/{season}/{slug}/rotations/"


def sailors(season: str, slug: str) -> str:
    """RP / sailors page, e.g. ``/s26/hood-trophy/sailors/``."""
    return f"/{season}/{slug}/sailors/"


def school(school_id: str, season: str) -> str:
    """A school's season page, e.g. ``/schools/navy/s26/`` (not regatta-scoped)."""
    return f"/schools/{school_id}/{season}/"


def sailor_profile(sailor_slug: str) -> str:
    """A sailor's public profile, e.g. ``/sailors/jane-doe/`` (cross-season)."""
    return f"/sailors/{sailor_slug}/"
