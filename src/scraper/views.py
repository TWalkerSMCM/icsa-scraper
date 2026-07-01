"""
Flat, analysis-friendly row types produced by ``sailor_races`` and ``Dataset``.

Distinct from ``scraper.models`` (the nested API contract that mirrors the iOS
app): these are denormalized rows, one per (sailor·race) or (regatta·school),
made for looping, grouping, and dropping into a DataFrame.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SailorRaceFinish:
    """One sailor's result in one race — the RP↔finish join."""
    season: str
    regatta_slug: str
    sailor_slug: str
    sailor_name: str
    school_slug: str
    team_name: str
    division: str
    race_num: int
    place: int              # scored finish (penalized) the boat earned in this race
    boat_role: str          # "skipper" | "crew"
    # Regatta context — blank from a bare sailor_races() call; filled by Dataset.
    regatta_name: str = ""
    start_time: str = ""    # ISO 8601; use for chronological ordering (ELO)
    boat: str = ""
    participant: str = ""   # "coed" | "women"
    regatta_type: str = ""  # e.g. "Conference Championship" — maps to a grade


@dataclass
class Result:
    """One school's overall placing in one regatta."""
    season: str
    regatta_slug: str
    regatta_name: str
    scoring_type: str       # "divisional" | "combined" | "team"
    school_slug: str
    school: str
    team_name: str
    place: int
    total: int              # fleet points total; 0 for team racing
    is_final: bool
    start_time: str = ""


@dataclass
class Finish:
    """One team's finish in one fleet race."""
    season: str
    regatta_slug: str
    school_slug: str
    team_name: str
    division: str
    race_num: int
    place: int


@dataclass
class SharedRegatta:
    """A regatta-division two sailors both competed in (from their profiles)."""
    season: str
    slug: str
    regatta_name: str
    division: str
    place_a: int | None      # sailor A's finishing rank in this division
    place_b: int | None
    fleet_size: int | None


@dataclass
class RaceEncounter:
    """One race both sailors sailed head-to-head (same regatta·division·race)."""
    season: str
    regatta_slug: str
    division: str
    race_num: int
    place_a: int
    place_b: int


@dataclass
class HeadToHead:
    """Head-to-head comparison of two sailors by slug."""
    a: str
    b: str
    shared: list[SharedRegatta]     # regatta-division overlaps (cheap, from profiles)
    races: list[RaceEncounter]      # per-race encounters (empty unless races=True)

    @property
    def a_ahead(self) -> int:
        """Regatta-divisions where A finished ahead of B (both placed)."""
        return sum(1 for s in self.shared
                   if s.place_a is not None and s.place_b is not None and s.place_a < s.place_b)

    @property
    def b_ahead(self) -> int:
        return sum(1 for s in self.shared
                   if s.place_a is not None and s.place_b is not None and s.place_b < s.place_a)

    @property
    def a_race_wins(self) -> int:
        """Races where A beat B (lower place)."""
        return sum(1 for r in self.races if r.place_a < r.place_b)

    @property
    def b_race_wins(self) -> int:
        return sum(1 for r in self.races if r.place_b < r.place_a)
