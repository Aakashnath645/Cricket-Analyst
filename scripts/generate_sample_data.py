"""Generate training datasets from real Cricsheet match archives.

Running standalone:
    python -m scripts.generate_sample_data --from-cricsheet --tournament ipl
    python -m scripts.generate_sample_data --synthetic            # legacy fallback

The Cricsheet pathway parses downloaded JSON archives and produces:
  - historical_matches.csv  (pre-match rows with real outcomes)
  - live_states.csv         (ball-by-ball snapshots with chase outcomes)
"""
from __future__ import annotations

import argparse
import json
import zipfile
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.core.cricket_math import balls_to_overs_float
from app.data.models import MatchContext


# ═══════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════

CRICSHEET_ARCHIVES: Dict[str, str] = {
    "ipl": "https://cricsheet.org/downloads/ipl_json.zip",
    "bbl": "https://cricsheet.org/downloads/bbl_json.zip",
    "psl": "https://cricsheet.org/downloads/psl_json.zip",
    "cpl": "https://cricsheet.org/downloads/cpl_json.zip",
    "sa20": "https://cricsheet.org/downloads/sa20_json.zip",
    "ilt20": "https://cricsheet.org/downloads/ilt20_json.zip",
    "t20i": "https://cricsheet.org/downloads/t20s_json.zip",
    "odi": "https://cricsheet.org/downloads/odis_json.zip",
    "tests": "https://cricsheet.org/downloads/tests_json.zip",
}

PITCH_TYPES = ["batting_friendly", "balanced", "spin_friendly", "pace_friendly", "slow_low"]
WEATHER_TYPES = ["clear", "cloudy", "humid", "overcast", "rain_threat"]
FORMATS = ["T20", "ODI", "Test"]
TOURNAMENTS = ["IPL", "PSL", "BBL", "World Cup", "Champions Trophy", "County"]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def sigmoid(value: float) -> float:
    return 1.0 / (1.0 + np.exp(-value))


# ═══════════════════════════════════════════
# Real Cricsheet Data Pipeline
# ═══════════════════════════════════════════

@dataclass
class _TeamTracker:
    rating: float = 1500.0
    matches: int = 0
    wins: int = 0
    recent: Deque[int] = field(default_factory=lambda: deque(maxlen=12))

    @property
    def recent_win_pct(self) -> float:
        if not self.recent:
            return 0.5
        return sum(self.recent) / len(self.recent)


@dataclass
class _VenueTracker:
    matches: int = 0
    first_innings_totals: List[int] = field(default_factory=list)
    chase_wins: int = 0
    boundary_runs: int = 0
    total_runs: int = 0

    @property
    def avg_first_innings(self) -> float:
        if not self.first_innings_totals:
            return 160.0
        return sum(self.first_innings_totals) / len(self.first_innings_totals)

    @property
    def chase_win_pct(self) -> float:
        return self.chase_wins / max(self.matches, 1)

    @property
    def boundary_pct(self) -> float:
        return self.boundary_runs / max(self.total_runs, 1)

    @property
    def pitch_type(self) -> str:
        avg = self.avg_first_innings
        cwp = self.chase_win_pct
        if avg >= 178 and cwp >= 0.50:
            return "batting_friendly"
        if avg <= 150 and cwp < 0.45:
            return "slow_low"
        if avg <= 160 and cwp < 0.48:
            return "spin_friendly"
        if avg >= 170 and cwp < 0.44:
            return "pace_friendly"
        return "balanced"


def _parse_match_full(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse a Cricsheet JSON match into structured data."""
    info = payload.get("info", {})
    teams = info.get("teams", [])
    if not isinstance(teams, list) or len(teams) != 2:
        return None

    outcome = info.get("outcome", {})
    winner = outcome.get("winner")
    if winner not in teams:
        return None

    # Determine format
    match_type = str(info.get("match_type", "")).upper()
    if "T20" in match_type:
        format_type = "T20"
    elif "ODI" in match_type or "LIST" in match_type:
        format_type = "ODI"
    elif "TEST" in match_type:
        format_type = "Test"
    else:
        format_type = "T20"  # default for franchise leagues

    toss = info.get("toss", {})
    toss_winner_name = toss.get("winner", teams[0])
    toss_decision = str(toss.get("decision", "bat")).lower()

    venue = str(info.get("venue", info.get("city", "Unknown")))
    event = info.get("event", {})
    tournament = str(event.get("name", "League")) if isinstance(event, dict) else "League"

    # Parse innings
    innings_list = payload.get("innings", [])
    innings_data: List[Dict[str, Any]] = []

    for entry in innings_list:
        inn_obj = entry if isinstance(entry, dict) and "team" in entry else None
        if inn_obj is None and isinstance(entry, dict) and len(entry) == 1:
            val = next(iter(entry.values()))
            if isinstance(val, dict):
                inn_obj = val
        if inn_obj is None:
            continue

        team_name = inn_obj.get("team", "")
        overs = inn_obj.get("overs", [])
        deliveries_flat: List[Dict[str, Any]] = []
        total_runs = 0
        boundary_runs = 0

        if isinstance(overs, list):
            for over_obj in overs:
                for delivery in over_obj.get("deliveries", []):
                    d = delivery if isinstance(delivery, dict) and "runs" in delivery else {}
                    if not d and isinstance(delivery, dict) and len(delivery) == 1:
                        d = next(iter(delivery.values())) if isinstance(next(iter(delivery.values())), dict) else {}
                    runs_total = int(d.get("runs", {}).get("total", 0))
                    batter_runs = int(d.get("runs", {}).get("batter", 0))
                    is_wicket = bool(d.get("wickets"))
                    total_runs += runs_total
                    if batter_runs in (4, 6):
                        boundary_runs += batter_runs
                    deliveries_flat.append({
                        "runs_total": runs_total,
                        "batter_runs": batter_runs,
                        "is_wicket": is_wicket,
                    })

        innings_data.append({
            "team": team_name,
            "total_runs": total_runs,
            "boundary_runs": boundary_runs,
            "deliveries": deliveries_flat,
        })

    if len(innings_data) < 1:
        return None

    return {
        "team_a": teams[0],
        "team_b": teams[1],
        "winner": winner,
        "format_type": format_type,
        "venue": venue,
        "tournament": tournament,
        "toss_winner": toss_winner_name,
        "toss_decision": toss_decision,
        "innings": innings_data,
    }


def generate_from_cricsheet(
    data_dir: Path,
    tournament_key: str = "ipl",
    max_matches: int = 2000,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Build real training data from Cricsheet JSON archives.

    Returns (prematch_df, live_df).
    """
    raw_dir = data_dir / "raw"
    archive_path = raw_dir / f"{tournament_key}_json.zip"

    if not archive_path.exists():
        # Download the archive
        import requests
        print(f"Downloading {tournament_key.upper()} archive from Cricsheet...")
        url = CRICSHEET_ARCHIVES.get(tournament_key)
        if not url:
            raise ValueError(f"Unknown tournament key: {tournament_key}")
        raw_dir.mkdir(parents=True, exist_ok=True)
        with requests.get(url, timeout=60, stream=True) as resp:
            resp.raise_for_status()
            with archive_path.open("wb") as f:
                for chunk in resp.iter_content(1024 * 256):
                    if chunk:
                        f.write(chunk)
        print(f"Downloaded to {archive_path}")

    # Parse all matches from archive
    matches: List[Dict[str, Any]] = []
    with zipfile.ZipFile(archive_path) as zf:
        for name in sorted(zf.namelist()):  # sorted for chronological order
            if not name.lower().endswith(".json"):
                continue
            try:
                payload = json.loads(zf.read(name).decode("utf-8"))
            except Exception:
                continue
            parsed = _parse_match_full(payload)
            if parsed is not None:
                matches.append(parsed)
            if len(matches) >= max_matches:
                break

    print(f"Parsed {len(matches)} valid matches from {tournament_key.upper()}")

    # Build rolling stats
    team_trackers: Dict[str, _TeamTracker] = defaultdict(_TeamTracker)
    h2h_tracker: Dict[str, Dict[str, int]] = {}
    venue_trackers: Dict[str, _VenueTracker] = defaultdict(_VenueTracker)

    prematch_rows: List[Dict[str, Any]] = []
    live_rows: List[Dict[str, Any]] = []

    for match in matches:
        ta = match["team_a"]
        tb = match["team_b"]
        winner = match["winner"]
        venue = match["venue"]
        fmt = match["format_type"]
        innings = match["innings"]

        # ── Current stats BEFORE this match (for features) ──
        tracker_a = team_trackers[ta]
        tracker_b = team_trackers[tb]
        v_tracker = venue_trackers[venue]

        pair_key = "||".join(sorted([ta, tb]))
        h2h_entry = h2h_tracker.get(pair_key, {"matches": 0})

        h2h_matches = h2h_entry.get("matches", 0)
        h2h_a_wins = h2h_entry.get(ta, 0)
        h2h_pct = h2h_a_wins / max(h2h_matches, 1) if h2h_matches > 0 else 0.5

        toss_winner_name = match["toss_winner"]
        toss_winner_code = "team_a" if toss_winner_name == ta else "team_b"

        # Compute home advantage from venue history
        home_adv = 0.0
        if v_tracker.matches >= 5:
            # Rough heuristic: if this team plays more at this venue, they have home edge
            home_adv = 0.15 if tracker_a.matches > tracker_b.matches else -0.1

        # ── Build pre-match row ──
        prematch_row = {
            "tournament": match["tournament"],
            "format_type": fmt,
            "team_a": ta,
            "team_b": tb,
            "venue": venue,
            "team_a_rating": round(tracker_a.rating, 2),
            "team_b_rating": round(tracker_b.rating, 2),
            "team_a_recent_win_pct": round(tracker_a.recent_win_pct, 4),
            "team_b_recent_win_pct": round(tracker_b.recent_win_pct, 4),
            "team_a_h2h_win_pct": round(h2h_pct, 4),
            "toss_winner": toss_winner_code,
            "toss_decision": match["toss_decision"],
            "pitch_type": v_tracker.pitch_type if v_tracker.matches >= 3 else "balanced",
            "weather_condition": "clear",  # not available in Cricsheet
            "weather_rain_risk": 0.1,
            "home_advantage": round(home_adv, 4),
            "news_edge": 0.0,  # not available in Cricsheet
            "venue_avg_score": round(v_tracker.avg_first_innings, 2),
            "venue_chase_win_pct": round(v_tracker.chase_win_pct, 4),
            "venue_boundary_pct": round(v_tracker.boundary_pct, 4),
            "dew_factor": 0.0,
            "team_a_won": 1 if winner == ta else 0,
        }
        prematch_rows.append(prematch_row)

        # ── Build live snapshots from 2nd innings (chase) ──
        if len(innings) >= 2:
            first_total = innings[0]["total_runs"]
            second_innings = innings[1]
            batting_team = second_innings["team"]
            deliveries = second_innings["deliveries"]
            target = first_total + 1
            max_overs = 20.0 if fmt == "T20" else (50.0 if fmt == "ODI" else 90.0)

            batting_side = "team_a" if batting_team == ta else "team_b"
            batting_won = (winner == batting_team)

            # Pre-match probability estimate (simple Elo-based)
            elo_diff = tracker_a.rating - tracker_b.rating
            prematch_a_prob = sigmoid(elo_diff / 400.0)

            # Sample snapshots at regular over intervals
            runs_acc = 0
            wickets_acc = 0
            ball_count = 0
            recent_runs: Deque[int] = deque(maxlen=30)  # last 5 overs

            snapshot_overs = set()
            # Take snapshots every 2 overs in T20, every 5 in ODI, every 10 in Test
            interval = 2 if fmt == "T20" else (5 if fmt == "ODI" else 10)
            for i in range(interval, int(max_overs) + 1, interval):
                snapshot_overs.add(i)

            for delivery in deliveries:
                runs_acc += delivery["runs_total"]
                recent_runs.append(delivery["runs_total"])
                if delivery["is_wicket"]:
                    wickets_acc += 1
                ball_count += 1

                overs_completed = ball_count / 6.0

                if ball_count % 6 == 0 and (ball_count // 6) in snapshot_overs:
                    recent_rr = (sum(recent_runs) * 6) / max(len(recent_runs), 1)
                    current_rr = (runs_acc * 6) / max(ball_count, 1)
                    runs_remaining = max(target - runs_acc, 0)
                    balls_remaining = max(int(max_overs * 6) - ball_count, 1)
                    req_rr = (runs_remaining * 6) / balls_remaining

                    # Momentum edge: positive if batting team is ahead of par
                    par_score = (target / max_overs) * overs_completed
                    momentum = clamp((runs_acc - par_score) / 30.0, -1.0, 1.0)

                    live_row = {
                        "tournament": match["tournament"],
                        "format_type": fmt,
                        "team_a": ta,
                        "team_b": tb,
                        "venue": venue,
                        "team_a_rating": round(tracker_a.rating, 2),
                        "team_b_rating": round(tracker_b.rating, 2),
                        "team_a_recent_win_pct": round(tracker_a.recent_win_pct, 4),
                        "team_b_recent_win_pct": round(tracker_b.recent_win_pct, 4),
                        "team_a_h2h_win_pct": round(h2h_pct, 4),
                        "toss_winner": toss_winner_code,
                        "toss_decision": match["toss_decision"],
                        "pitch_type": v_tracker.pitch_type if v_tracker.matches >= 3 else "balanced",
                        "weather_condition": "clear",
                        "weather_rain_risk": 0.1,
                        "home_advantage": round(home_adv, 4),
                        "news_edge": 0.0,
                        "venue_avg_score": round(v_tracker.avg_first_innings, 2),
                        "venue_chase_win_pct": round(v_tracker.chase_win_pct, 4),
                        "venue_boundary_pct": round(v_tracker.boundary_pct, 4),
                        "dew_factor": 0.0,
                        "prematch_team_a_probability": round(prematch_a_prob, 4),
                        "batting_side": batting_side,
                        "overs_completed": round(overs_completed, 2),
                        "runs_scored": runs_acc,
                        "wickets_lost": wickets_acc,
                        "max_overs": max_overs,
                        "target_runs": target,
                        "recent_run_rate": round(recent_rr, 3),
                        "momentum_edge": round(momentum, 3),
                        "batting_side_wins": 1 if batting_won else 0,
                    }
                    live_rows.append(live_row)

        # ── UPDATE trackers AFTER this match ──
        # Elo update
        expected_a = 1.0 / (1.0 + 10 ** ((tracker_b.rating - tracker_a.rating) / 400.0))
        score_a = 1.0 if winner == ta else 0.0
        k = 20.0
        tracker_a.rating += k * (score_a - expected_a)
        tracker_b.rating += k * ((1.0 - score_a) - (1.0 - expected_a))

        for team, did_win in ((ta, winner == ta), (tb, winner == tb)):
            team_trackers[team].matches += 1
            team_trackers[team].wins += int(did_win)
            team_trackers[team].recent.append(1 if did_win else 0)

        # H2H update
        if pair_key not in h2h_tracker:
            h2h_tracker[pair_key] = {ta: 0, tb: 0, "matches": 0}
        if ta not in h2h_tracker[pair_key]:
            h2h_tracker[pair_key][ta] = 0
        if tb not in h2h_tracker[pair_key]:
            h2h_tracker[pair_key][tb] = 0
        h2h_tracker[pair_key]["matches"] += 1
        h2h_tracker[pair_key][winner] = h2h_tracker[pair_key].get(winner, 0) + 1

        # Venue update
        v_tracker.matches += 1
        if innings:
            first_total = innings[0]["total_runs"]
            first_boundary = innings[0]["boundary_runs"]
            v_tracker.first_innings_totals.append(first_total)
            v_tracker.boundary_runs += first_boundary
            v_tracker.total_runs += first_total
            if len(innings) >= 2:
                v_tracker.total_runs += innings[1]["total_runs"]
                v_tracker.boundary_runs += innings[1]["boundary_runs"]
                if winner == innings[1]["team"]:
                    v_tracker.chase_wins += 1

    prematch_df = pd.DataFrame(prematch_rows)
    live_df = pd.DataFrame(live_rows)

    print(f"Generated {len(prematch_df)} pre-match rows, {len(live_df)} live snapshot rows")
    return prematch_df, live_df


# ═══════════════════════════════════════════
# Legacy synthetic fallback (kept for testing)
# ═══════════════════════════════════════════

TEAM_POOL = [
    "India", "Australia", "England", "Pakistan", "South Africa",
    "New Zealand", "Sri Lanka", "West Indies", "Afghanistan", "Bangladesh",
    "Mumbai Indians", "Chennai Super Kings", "Royal Challengers Bengaluru",
    "Kolkata Knight Riders", "Rajasthan Royals", "Sunrisers Hyderabad",
]
VENUES = ["Mumbai", "Chennai", "Kolkata", "Bengaluru", "Ahmedabad",
          "Lahore", "Perth", "Lord's", "Auckland", "Johannesburg"]


def generate_prematch_rows(n_rows: int, seed: int) -> pd.DataFrame:
    """Legacy synthetic generator — kept as fallback."""
    rng = np.random.default_rng(seed)
    from app.core.feature_engineering import FeatureEngineer
    engineer = FeatureEngineer()
    rows: list[dict[str, object]] = []

    for _ in range(n_rows):
        team_a, team_b = rng.choice(TEAM_POOL, size=2, replace=False).tolist()
        format_type = rng.choice(FORMATS, p=[0.72, 0.20, 0.08]).item()
        pitch_type = rng.choice(PITCH_TYPES, p=[0.28, 0.32, 0.18, 0.16, 0.06]).item()
        weather = rng.choice(WEATHER_TYPES, p=[0.40, 0.24, 0.16, 0.12, 0.08]).item()

        ctx = MatchContext(
            tournament=rng.choice(TOURNAMENTS).item(),
            format_type=format_type,
            team_a=team_a, team_b=team_b,
            venue=rng.choice(VENUES).item(),
            team_a_rating=float(rng.normal(1560, 135)),
            team_b_rating=float(rng.normal(1545, 140)),
            team_a_recent_win_pct=clamp(float(rng.normal(0.56, 0.15)), 0.10, 0.95),
            team_b_recent_win_pct=clamp(float(rng.normal(0.54, 0.15)), 0.10, 0.95),
            team_a_h2h_win_pct=clamp(float(rng.normal(0.50, 0.18)), 0.02, 0.98),
            toss_winner=rng.choice(["team_a", "team_b"]).item(),
            toss_decision=rng.choice(["bat", "bowl"], p=[0.42, 0.58]).item(),
            pitch_type=pitch_type, weather_condition=weather,
            weather_rain_risk=0.0,
            home_advantage=float(rng.choice([1.0, 0.0, -1.0], p=[0.30, 0.46, 0.24])),
            news_edge=clamp(float(rng.normal(0.0, 0.30)), -1.0, 1.0),
        )

        x = engineer.build_prematch_features(ctx)
        score = (0.85 * x[0] + 2.10 * x[1] + 1.20 * x[2] + 0.75 * x[3]
                 + 0.75 * x[4] + 0.35 * x[5] + 0.12 * x[6] + 0.12 * x[7]
                 - 1.30 * x[8] + 0.95 * x[9] + float(rng.normal(0.0, 0.45)))
        p_a = sigmoid(score)
        team_a_won = int(rng.random() < p_a)

        rows.append({
            "tournament": ctx.tournament, "format_type": ctx.format_type,
            "team_a": ctx.team_a, "team_b": ctx.team_b, "venue": ctx.venue,
            "team_a_rating": round(ctx.team_a_rating, 2),
            "team_b_rating": round(ctx.team_b_rating, 2),
            "team_a_recent_win_pct": round(ctx.team_a_recent_win_pct, 4),
            "team_b_recent_win_pct": round(ctx.team_b_recent_win_pct, 4),
            "team_a_h2h_win_pct": round(ctx.team_a_h2h_win_pct, 4),
            "toss_winner": ctx.toss_winner, "toss_decision": ctx.toss_decision,
            "pitch_type": ctx.pitch_type, "weather_condition": ctx.weather_condition,
            "weather_rain_risk": round(ctx.weather_rain_risk, 4),
            "home_advantage": ctx.home_advantage,
            "news_edge": round(ctx.news_edge, 4),
            "venue_avg_score": 160.0, "venue_chase_win_pct": 0.5,
            "venue_boundary_pct": 0.45, "dew_factor": 0.0,
            "team_a_won": team_a_won,
        })
    return pd.DataFrame(rows)


def generate_live_rows(n_rows: int, seed: int) -> pd.DataFrame:
    """Legacy synthetic generator — kept as fallback."""
    rng = np.random.default_rng(seed + 101)
    from app.core.feature_engineering import FeatureEngineer
    engineer = FeatureEngineer()
    rows: list[dict[str, object]] = []
    overs_map = {"T20": 20.0, "ODI": 50.0, "Test": 90.0}

    for _ in range(n_rows):
        team_a, team_b = rng.choice(TEAM_POOL, size=2, replace=False).tolist()
        format_type = rng.choice(FORMATS, p=[0.74, 0.21, 0.05]).item()
        max_overs = overs_map[format_type]
        overs_completed = float(rng.uniform(1.0, max_overs - 0.6))

        ctx = MatchContext(
            tournament=rng.choice(TOURNAMENTS).item(),
            format_type=format_type,
            team_a=team_a, team_b=team_b,
            venue=rng.choice(VENUES).item(),
            team_a_rating=float(rng.normal(1560, 120)),
            team_b_rating=float(rng.normal(1540, 120)),
            team_a_recent_win_pct=clamp(float(rng.normal(0.56, 0.14)), 0.08, 0.95),
            team_b_recent_win_pct=clamp(float(rng.normal(0.55, 0.14)), 0.08, 0.95),
            team_a_h2h_win_pct=clamp(float(rng.normal(0.5, 0.16)), 0.02, 0.98),
            toss_winner=rng.choice(["team_a", "team_b"]).item(),
            toss_decision=rng.choice(["bat", "bowl"], p=[0.40, 0.60]).item(),
            pitch_type=rng.choice(PITCH_TYPES).item(),
            weather_condition=rng.choice(WEATHER_TYPES).item(),
            weather_rain_risk=0.0,
            home_advantage=float(rng.choice([1.0, 0.0, -1.0], p=[0.28, 0.45, 0.27])),
            news_edge=clamp(float(rng.normal(0.0, 0.25)), -1.0, 1.0),
        )

        prematch_prob_a = float(sigmoid(np.dot(engineer.build_prematch_features(ctx), np.array([
            0.70, 2.20, 1.30, 0.80, 0.75, 0.20, 0.10, 0.10, -1.20, 0.95, 0.03, 0.01, -0.02
        ]))))

        batting_side = rng.choice(["team_a", "team_b"]).item()
        base_rr = 6.8 if format_type == "T20" else (5.5 if format_type == "ODI" else 3.3)
        rr = clamp(float(rng.normal(base_rr, 1.6)), 1.8, 14.0)
        runs_scored = int(rr * overs_completed)
        wickets_lost = int(clamp(float(rng.normal(overs_completed / max_overs * 5.2, 1.8)), 0, 9))

        is_chase = bool(rng.random() < 0.88)
        target_runs = None
        if is_chase:
            if format_type == "T20":
                target_runs = int(clamp(float(rng.normal(170, 22)), 115, 240))
            elif format_type == "ODI":
                target_runs = int(clamp(float(rng.normal(285, 35)), 190, 430))
            else:
                target_runs = int(clamp(float(rng.normal(325, 45)), 220, 520))

        recent_rr = clamp(float(rng.normal(rr, 1.1)), 1.0, 16.0)
        momentum = clamp(float(rng.normal(0.0, 0.45)), -1.0, 1.0)

        live_x = engineer.build_live_features(
            ctx,
            __import__("app.data.models", fromlist=["LiveMatchState"]).LiveMatchState(
                batting_side=batting_side, overs_completed=overs_completed,
                runs_scored=runs_scored, wickets_lost=wickets_lost,
                max_overs=max_overs, target_runs=target_runs,
                recent_run_rate=recent_rr, momentum_edge=momentum,
            ),
            prematch_prob_a,
        )
        score = (2.35 * live_x[0] - 0.25 * live_x[1] + 1.55 * live_x[2]
                 + 0.18 * live_x[3] + 0.20 * live_x[4] + 0.60 * live_x[5]
                 - 0.25 * live_x[6] - 0.70 * live_x[7] - 1.20 * live_x[8]
                 - 0.60 * live_x[9] + 0.12 * live_x[10]
                 + float(rng.normal(0.0, 0.50)) - 1.25)
        batting_side_wins = int(rng.random() < sigmoid(score))

        rows.append({
            "tournament": ctx.tournament, "format_type": ctx.format_type,
            "team_a": ctx.team_a, "team_b": ctx.team_b, "venue": ctx.venue,
            "team_a_rating": round(ctx.team_a_rating, 2),
            "team_b_rating": round(ctx.team_b_rating, 2),
            "team_a_recent_win_pct": round(ctx.team_a_recent_win_pct, 4),
            "team_b_recent_win_pct": round(ctx.team_b_recent_win_pct, 4),
            "team_a_h2h_win_pct": round(ctx.team_a_h2h_win_pct, 4),
            "toss_winner": ctx.toss_winner, "toss_decision": ctx.toss_decision,
            "pitch_type": ctx.pitch_type, "weather_condition": ctx.weather_condition,
            "weather_rain_risk": round(ctx.weather_rain_risk, 4),
            "home_advantage": ctx.home_advantage,
            "news_edge": round(ctx.news_edge, 4),
            "venue_avg_score": 160.0, "venue_chase_win_pct": 0.5,
            "venue_boundary_pct": 0.45, "dew_factor": 0.0,
            "prematch_team_a_probability": round(prematch_prob_a, 4),
            "batting_side": batting_side,
            "overs_completed": round(overs_completed, 2),
            "runs_scored": runs_scored, "wickets_lost": wickets_lost,
            "max_overs": max_overs,
            "target_runs": target_runs if target_runs is not None else "",
            "recent_run_rate": round(recent_rr, 3),
            "momentum_edge": round(momentum, 3),
            "batting_side_wins": batting_side_wins,
        })
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate cricket datasets for training.")
    parser.add_argument("--from-cricsheet", action="store_true",
                        help="Use real Cricsheet data instead of synthetic")
    parser.add_argument("--tournament", type=str, default="ipl",
                        help="Cricsheet tournament key (ipl, t20i, odi, etc)")
    parser.add_argument("--max-matches", type=int, default=2000)
    parser.add_argument("--synthetic", action="store_true",
                        help="Use legacy synthetic generator")
    parser.add_argument("--prematch-rows", type=int, default=5000)
    parser.add_argument("--live-rows", type=int, default=9000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=str, default="data")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.from_cricsheet:
        prematch_df, live_df = generate_from_cricsheet(
            data_dir=out_dir,
            tournament_key=args.tournament,
            max_matches=args.max_matches,
        )
    else:
        prematch_df = generate_prematch_rows(args.prematch_rows, args.seed)
        live_df = generate_live_rows(args.live_rows, args.seed)

    prematch_path = out_dir / "historical_matches.csv"
    live_path = out_dir / "live_states.csv"
    prematch_df.to_csv(prematch_path, index=False)
    live_df.to_csv(live_path, index=False)

    print(f"Wrote {len(prematch_df)} rows to {prematch_path}")
    print(f"Wrote {len(live_df)} rows to {live_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
