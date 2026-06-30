"""
Canonical data models for ICSA scores.

These dataclasses define the API contract between the backend (DynamoDB) and the
iOS app (Models.swift Codable structs). Their shape must not change without a
coordinated iOS + backend migration.

Originally defined inline in parser.py; extracted here so that both the legacy
parser and the new techscore-based adapter can share the same types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


def make_pk(season: str, slug: str) -> str:
    """Build DynamoDB partition key from season and slug."""
    return f"{season}#{slug}"


# ---------------------------------------------------------------------------
# Fleet racing models
# ---------------------------------------------------------------------------

@dataclass
class RaceScore:
    """A single race finish for one division."""
    race_num: int
    points: int
    penalty: Optional[str] = None          # e.g. "DNF", "DSQ", "DNS", "BYE"
    penalty_formula: Optional[str] = None  # e.g. "Fleet + 1", "average in division"
    penalty_comment: Optional[str] = None  # free-text RC comment, e.g. "crew overboard"


@dataclass
class DivisionResult:
    total: int
    races: list[RaceScore] = field(default_factory=list)
    rank: Optional[int] = None  # per-division rank from /<season>/<slug>/<div>/ page
    tiebreaker: str = ""        # symbol, e.g. "*"
    tiebreaker_note: str = ""   # explanation, e.g. "Head-to-head tiebreaker"


@dataclass
class TeamResult:
    place: int
    school: str
    school_short: str
    school_slug: str        # URL slug, e.g. "navy" from /schools/navy/
    school_url: str
    team_name: str
    total: int
    divisions: dict[str, DivisionResult] = field(default_factory=dict)
    # 'A' and/or 'B' keys depending on regatta type
    tiebreaker: str = ""        # symbol shown when place is tiebroken, e.g. "†"
    tiebreaker_note: str = ""   # explanation, e.g. "Head-to-head tiebreaker"


@dataclass
class RegattaScores:
    name: str
    season: str
    slug: str
    scoring_type: str             # "divisional", "combined", or "team"
    races_sailed: dict[str, int]  # e.g. {"A": 12, "B": 12}
    host: str = ""
    regatta_start: str = ""       # "YYYY-MM-DD"
    regatta_end: str = ""         # "YYYY-MM-DD"
    is_final: bool = False        # True once the regatta is officially finalized
    teams: list[TeamResult] = field(default_factory=list)


@dataclass
class RegattaListEntry:
    name: str
    url: str                    # full URL
    slug: str                   # e.g. "victorian-urn"
    season: str                 # e.g. "f25"
    status: str                 # "in_progress", "recent", "upcoming"
    host: str = ""
    regatta_start: str = ""     # "YYYY-MM-DD"
    scoring_type: str = "divisional"  # "divisional" or "team"


# ---------------------------------------------------------------------------
# Team racing models
# ---------------------------------------------------------------------------

@dataclass
class TeamRaceMatch:
    """Result of one race between two teams."""
    race_num: int               # sequential race number within the regatta
    opponent: str               # school slug of opponent
    won: bool                   # True = win (ignored when sailed=False or tied=True)
    our_positions: list[int]    # e.g. [1, 2, 3]
    their_positions: list[int]
    sailed: bool = True         # False = race scheduled but not yet sailed
    tied: bool = False          # True = match ended in a tie
    flight: int = 0             # 1-based flight within the round; 0 if unknown


@dataclass
class TeamRaceRound:
    """All match results for a given round (e.g. 'Round 1')."""
    name: str                       # e.g. "Round 1"
    wins: int
    losses: int
    ties: int
    matches: list[TeamRaceMatch]    # ordered by race_num


@dataclass
class TeamRaceTeam:
    place: int
    school: str
    school_short: str
    school_slug: str        # URL slug, e.g. "navy" from /schools/navy/
    school_url: str
    team_name: str
    total_wins: int
    total_losses: int
    total_ties: int
    win_pct: float          # wins / (wins + losses + ties)
    rounds: list[TeamRaceRound]
    tiebreaker: str = ""        # symbol shown when place is tiebroken, e.g. "†"
    tiebreaker_note: str = ""   # explanation, e.g. "Head-to-head tiebreaker"


@dataclass
class TeamRegattaScores:
    name: str
    season: str
    slug: str
    scoring_type: str = "team"
    host: str = ""
    regatta_start: str = ""     # "YYYY-MM-DD"
    regatta_end: str = ""       # "YYYY-MM-DD"
    is_final: bool = False      # True once the regatta is officially finalized
    teams: list[TeamRaceTeam] = field(default_factory=list)
