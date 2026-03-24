from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Deque, Dict, Optional, Tuple
import json
import zipfile

import requests


CRICSHEET_ARCHIVES: Dict[str, str] = {
    "ipl": "https://cricsheet.org/downloads/ipl_json.zip",
    "bbl": "https://cricsheet.org/downloads/bbl_json.zip",
    "psl": "https://cricsheet.org/downloads/psl_json.zip",
    "cpl": "https://cricsheet.org/downloads/cpl_json.zip",
    "sa20": "https://cricsheet.org/downloads/sa20_json.zip",
    "ilt20": "https://cricsheet.org/downloads/ilt20_json.zip",
    "wpl": "https://cricsheet.org/downloads/wpl_json.zip",
    "t20i": "https://cricsheet.org/downloads/t20s_json.zip",
    "odi": "https://cricsheet.org/downloads/odis_json.zip",
    "tests": "https://cricsheet.org/downloads/tests_json.zip",
}


@dataclass
class MatchProfileSuggestion:
    team_a_rating: float
    team_b_rating: float
    team_a_recent_win_pct: float
    team_b_recent_win_pct: float
    team_a_h2h_win_pct: float
    pitch_type: str
    pitch_summary: str
    source: str
    venue_avg_score: float = 160.0
    venue_chase_win_pct: float = 0.5
    venue_boundary_pct: float = 0.45


class HistoricalProfilesService:
    def __init__(self, data_dir: str | Path = "data", timeout_seconds: int = 30) -> None:
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.profile_path = self.data_dir / "historical_profiles.json"
        self.timeout_seconds = timeout_seconds
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._profiles: Dict[str, Any] = self._load_profiles()

    def sync_from_cricsheet(
        self,
        tournament_key: str = "ipl",
        max_matches: int = 1800,
        force_download: bool = False,
    ) -> str:
        key = tournament_key.lower().strip()
        if key not in CRICSHEET_ARCHIVES:
            return f"Unsupported tournament key '{tournament_key}'."

        archive_path = self.raw_dir / f"{key}_json.zip"
        if force_download or (not archive_path.exists()):
            self._download_archive(CRICSHEET_ARCHIVES[key], archive_path)

        profiles = self._build_profiles_from_archive(archive_path, max_matches=max_matches)
        profiles["source"] = f"cricsheet:{key}"
        profiles["archive_path"] = str(archive_path)
        self._profiles = profiles
        self.profile_path.write_text(json.dumps(profiles, indent=2), encoding="utf-8")
        return (
            f"Synced {profiles.get('matches_processed', 0)} matches from {key.upper()} "
            f"into historical profiles."
        )

    def suggest_for_match(
        self,
        team_a: str,
        team_b: str,
        venue: str,
    ) -> MatchProfileSuggestion:
        team_profiles = self._profiles.get("team_profiles", {})
        venue_profiles = self._profiles.get("venue_profiles", {})
        h2h = self._profiles.get("h2h", {})

        team_a_name, team_a_profile = self._lookup_team_profile(team_a, team_profiles)
        team_b_name, team_b_profile = self._lookup_team_profile(team_b, team_profiles)

        rating_a = float(team_a_profile.get("rating", 1600.0))
        rating_b = float(team_b_profile.get("rating", 1600.0))
        recent_a = float(team_a_profile.get("recent_win_pct", 0.50))
        recent_b = float(team_b_profile.get("recent_win_pct", 0.50))

        key = "||".join(sorted([team_a_name, team_b_name]))
        h2h_stats = h2h.get(key, {})
        h2h_matches = int(h2h_stats.get("matches", 0))
        if h2h_matches > 0:
            team_a_h2h_wins = float(h2h_stats.get(team_a_name, 0))
            h2h_pct = team_a_h2h_wins / max(h2h_matches, 1)
        else:
            h2h_pct = 0.50

        venue_key, venue_profile = self._lookup_venue_profile(venue, venue_profiles)
        pitch_type = str(venue_profile.get("pitch_type", "balanced"))
        avg_first = float(venue_profile.get("avg_first_innings", 160.0))
        chase_win_pct = float(venue_profile.get("chase_win_pct", 0.50))
        venue_matches = int(venue_profile.get("matches", 0))

        summary = (
            f"{venue_key}: avg first innings {avg_first:.1f}, "
            f"chase win {chase_win_pct:.1%} ({venue_matches} matches)."
        )

        # Boundary percentage if available
        boundary_pct = float(venue_profile.get("boundary_pct", 0.45))

        return MatchProfileSuggestion(
            team_a_rating=rating_a,
            team_b_rating=rating_b,
            team_a_recent_win_pct=recent_a,
            team_b_recent_win_pct=recent_b,
            team_a_h2h_win_pct=h2h_pct,
            pitch_type=pitch_type,
            pitch_summary=summary,
            source=str(self._profiles.get("source", "local")),
            venue_avg_score=avg_first,
            venue_chase_win_pct=chase_win_pct,
            venue_boundary_pct=boundary_pct,
        )

    def _load_profiles(self) -> Dict[str, Any]:
        if self.profile_path.exists():
            try:
                return json.loads(self.profile_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return self._default_profiles()
        return self._default_profiles()

    @staticmethod
    def _default_profiles() -> Dict[str, Any]:
        return {
            "source": "default",
            "matches_processed": 0,
            "team_profiles": {},
            "h2h": {},
            "venue_profiles": {},
        }

    def _download_archive(self, url: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, timeout=self.timeout_seconds, stream=True) as response:
            response.raise_for_status()
            with destination.open("wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        file.write(chunk)

    def _build_profiles_from_archive(self, archive_path: Path, max_matches: int) -> Dict[str, Any]:
        team_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"matches": 0, "wins": 0, "rating": 1500.0, "recent": deque(maxlen=12)}
        )
        h2h: Dict[str, Dict[str, Any]] = {}
        venue_stats: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"matches": 0.0, "first_sum": 0.0, "chase_wins": 0.0}
        )
        processed = 0

        with zipfile.ZipFile(archive_path) as archive:
            for file_name in archive.namelist():
                if not file_name.lower().endswith(".json"):
                    continue
                try:
                    match_payload = json.loads(archive.read(file_name).decode("utf-8"))
                except Exception:
                    continue

                parsed = self._parse_match(match_payload)
                if parsed is None:
                    continue

                team_a, team_b, winner, venue, first_innings_runs, chase_won = parsed
                stats_a = team_stats[team_a]
                stats_b = team_stats[team_b]
                rating_a = float(stats_a["rating"])
                rating_b = float(stats_b["rating"])
                expected_a = 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))
                score_a = 1.0 if winner == team_a else 0.0
                k_factor = 18.0
                stats_a["rating"] = rating_a + k_factor * (score_a - expected_a)
                stats_b["rating"] = rating_b + k_factor * ((1.0 - score_a) - (1.0 - expected_a))

                for team, did_win in ((team_a, winner == team_a), (team_b, winner == team_b)):
                    team_stats[team]["matches"] += 1
                    team_stats[team]["wins"] += int(did_win)
                    recent: Deque[int] = team_stats[team]["recent"]
                    recent.append(1 if did_win else 0)

                pair_key = "||".join(sorted([team_a, team_b]))
                if pair_key not in h2h:
                    h2h[pair_key] = {team_a: 0, team_b: 0, "matches": 0}
                if team_a not in h2h[pair_key]:
                    h2h[pair_key][team_a] = 0
                if team_b not in h2h[pair_key]:
                    h2h[pair_key][team_b] = 0
                h2h[pair_key]["matches"] = int(h2h[pair_key].get("matches", 0)) + 1
                h2h[pair_key][winner] = int(h2h[pair_key].get(winner, 0)) + 1

                venue_entry = venue_stats[venue]
                venue_entry["matches"] += 1.0
                venue_entry["first_sum"] += float(first_innings_runs)
                if chase_won:
                    venue_entry["chase_wins"] += 1.0

                processed += 1
                if processed >= max_matches:
                    break

        team_profiles: Dict[str, Dict[str, float | int]] = {}
        for team_name, info in team_stats.items():
            recent_vals = list(info["recent"])
            recent_win_pct = sum(recent_vals) / len(recent_vals) if recent_vals else 0.5
            team_profiles[team_name] = {
                "rating": round(float(info["rating"]), 2),
                "matches": int(info["matches"]),
                "wins": int(info["wins"]),
                "recent_win_pct": round(recent_win_pct, 4),
            }

        venue_profiles: Dict[str, Dict[str, float | int | str]] = {}
        for venue_name, info in venue_stats.items():
            matches = max(float(info["matches"]), 1.0)
            avg_first = float(info["first_sum"]) / matches
            chase_win_pct = float(info["chase_wins"]) / matches
            venue_profiles[venue_name] = {
                "matches": int(matches),
                "avg_first_innings": round(avg_first, 2),
                "chase_win_pct": round(chase_win_pct, 4),
                "pitch_type": self._classify_pitch(avg_first, chase_win_pct),
            }

        return {
            "matches_processed": processed,
            "team_profiles": team_profiles,
            "h2h": h2h,
            "venue_profiles": venue_profiles,
        }

    def _parse_match(self, payload: Dict[str, Any]) -> Optional[Tuple[str, str, str, str, int, bool]]:
        info = payload.get("info", {})
        teams = info.get("teams", [])
        if not isinstance(teams, list) or len(teams) != 2:
            return None
        team_a = str(teams[0])
        team_b = str(teams[1])

        outcome = info.get("outcome", {})
        winner = outcome.get("winner")
        if winner not in (team_a, team_b):
            return None

        innings_payload = payload.get("innings", [])
        innings: list[Tuple[str, int]] = []
        for entry in innings_payload:
            parsed = self._extract_innings(entry)
            if parsed is not None:
                innings.append(parsed)
        if not innings:
            return None

        first_team, first_runs = innings[0]
        second_team = innings[1][0] if len(innings) > 1 else ""
        chase_won = bool(second_team and winner == second_team)

        venue = str(info.get("venue") or info.get("city") or "Unknown Venue")
        return team_a, team_b, str(winner), venue, int(first_runs), chase_won

    def _extract_innings(self, innings_entry: Any) -> Optional[Tuple[str, int]]:
        inning_obj: Dict[str, Any]
        if isinstance(innings_entry, dict) and "team" in innings_entry:
            inning_obj = innings_entry
        elif isinstance(innings_entry, dict) and len(innings_entry) == 1:
            value = next(iter(innings_entry.values()))
            if isinstance(value, dict):
                inning_obj = value
            else:
                return None
        else:
            return None

        team_name = inning_obj.get("team")
        if not team_name:
            return None

        total_runs = 0
        overs = inning_obj.get("overs")
        if isinstance(overs, list):
            for over in overs:
                for delivery in over.get("deliveries", []):
                    payload = self._normalize_delivery_payload(delivery)
                    total_runs += int(payload.get("runs", {}).get("total", 0))
        else:
            deliveries = inning_obj.get("deliveries", [])
            for delivery in deliveries:
                payload = self._normalize_delivery_payload(delivery)
                total_runs += int(payload.get("runs", {}).get("total", 0))

        return str(team_name), total_runs

    @staticmethod
    def _normalize_delivery_payload(delivery: Any) -> Dict[str, Any]:
        if isinstance(delivery, dict) and "runs" in delivery:
            return delivery
        if isinstance(delivery, dict) and len(delivery) == 1:
            value = next(iter(delivery.values()))
            if isinstance(value, dict):
                return value
        return {}

    @staticmethod
    def _classify_pitch(avg_first_innings: float, chase_win_pct: float) -> str:
        if avg_first_innings >= 178 and chase_win_pct >= 0.50:
            return "batting_friendly"
        if avg_first_innings <= 150 and chase_win_pct < 0.45:
            return "slow_low"
        if avg_first_innings <= 160 and chase_win_pct < 0.48:
            return "spin_friendly"
        if avg_first_innings >= 170 and chase_win_pct < 0.44:
            return "pace_friendly"
        return "balanced"

    @staticmethod
    def _lookup_team_profile(team_name: str, profiles: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        if team_name in profiles:
            return team_name, profiles[team_name]
        lowered = team_name.strip().lower()
        for candidate, profile in profiles.items():
            if candidate.lower() == lowered:
                return candidate, profile
        return team_name, {}

    @staticmethod
    def _lookup_venue_profile(venue: str, profiles: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        if venue in profiles:
            return venue, profiles[venue]
        lowered = venue.strip().lower()
        for candidate, profile in profiles.items():
            if candidate.lower() == lowered:
                return candidate, profile
        for candidate, profile in profiles.items():
            cand_lower = candidate.lower()
            if lowered and (lowered in cand_lower or cand_lower in lowered):
                return candidate, profile
        return venue or "Unknown Venue", {}

