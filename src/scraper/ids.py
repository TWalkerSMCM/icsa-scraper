"""
Identity helpers: extract stable slugs from Techscore URLs and parse sailor
display names. Pure, no dependencies — the reconstruction layer that lets you
join parser output across pages and regattas.
"""

from __future__ import annotations

import re


def school_slug(url: str) -> str:
    """Extract a school slug from a school URL.

    Handles both ``/schools/{id}/{season}/`` and the bare ``/{id}/{season}/``
    form. Returns "" if the URL doesn't match.
    """
    m = re.search(r"/schools/([^/]+)/", url)
    if m:
        return m.group(1)
    m = re.match(r"^/([a-z0-9\-]{1,30})/[sfmw]\d{2}/$", url)
    return m.group(1) if m else ""


def sailor_slug(url: str) -> str:
    """Extract a sailor slug from ``/sailors/{slug}/``. Returns "" if no match.

    This slug is the stable cross-regatta identity for a sailor.
    """
    m = re.match(r"^/sailors/([^/]+)/$", url)
    return m.group(1) if m else ""


def split_sailor_name(full_name: str) -> tuple[str, str, int | None, bool]:
    """Parse a sailor display string from Techscore's ``Member::__toString()``.

    Formats::

        "{first} {last} '{YY}"   — registered student
        "{first} {last} '??"     — registered, unknown year
        "{first} {last} '{YY} *" — unregistered student
        "{first} {last}"         — coach / no year

    Returns ``(first_name, last_name, grad_year_or_None, is_registered)``.
    ``grad_year`` is the full 4-digit year (e.g. 2026 from "'26").
    """
    name = full_name.strip()

    registered = True
    if name.endswith(" *"):
        registered = False
        name = name[:-2].strip()

    grad_year: int | None = None
    m = re.search(r"\s+'(\d{2})$", name)
    if m:
        yy = int(m.group(1))
        # 00-49 → 2000-2049, 50-99 → 1950-1999
        grad_year = 2000 + yy if yy < 50 else 1900 + yy
        name = name[:m.start()].strip()
    else:
        # Strip " '??" (unknown year)
        name = re.sub(r"\s+'\?\?$", "", name).strip()

    parts = name.rsplit(" ", 1)
    if len(parts) == 2:
        return parts[0], parts[1], grad_year, registered
    return name, "", grad_year, registered


def expand_races(races_str: str, all_races: list[int]) -> list[int]:
    """Expand a race-range string like ``"1-3,5"`` to ``[1, 2, 3, 5]``.

    An empty/blank string means "all races" and returns ``all_races`` — this
    matches Techscore's RP convention where an omitted range = sailed everything.
    """
    if not races_str or not races_str.strip():
        return list(all_races)
    result: list[int] = []
    for part in races_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            result.extend(range(int(a), int(b) + 1))
        else:
            result.append(int(part))
    return result
