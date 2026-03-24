from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Dict, List, Optional

import requests


@dataclass
class LiveMatch:
    match_id: str
    series_name: str
    match_desc: str
    format_type: str
    team1: str
    team2: str
    venue: str
    city: str
    status: str
    state: str
    short_status: str
    team1_score: str
    team2_score: str
    team1_runs: Optional[int] = None
    team2_runs: Optional[int] = None
    team1_wickets: Optional[int] = None
    team2_wickets: Optional[int] = None
    team1_overs: Optional[float] = None
    team2_overs: Optional[float] = None

    @property
    def display_label(self) -> str:
        return f"{self.team1} vs {self.team2} | {self.short_status or self.state}"


class CricbuzzLiveService:
    LIVE_SCORES_URL = "https://www.cricbuzz.com/cricket-match/live-scores"

    def __init__(self, timeout_seconds: int = 18) -> None:
        self.timeout_seconds = timeout_seconds
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        }

    def fetch_matches(self, limit: int = 24, include_completed: bool = False) -> List[LiveMatch]:
        html = requests.get(
            self.LIVE_SCORES_URL,
            headers=self.headers,
            timeout=self.timeout_seconds,
        ).text
        payload = self._extract_matches_payload(html)
        matches: List[LiveMatch] = []

        for entry in payload.get("matches", []):
            raw_match = entry.get("match", {})
            match_info = raw_match.get("matchInfo", {})
            state = str(match_info.get("state", "")).strip()
            if not include_completed and state.lower() == "complete":
                continue

            match_id = str(match_info.get("matchId", ""))
            format_type = str(match_info.get("matchFormat", "T20")).upper()
            team1 = str(match_info.get("team1", {}).get("teamName", "Team A"))
            team2 = str(match_info.get("team2", {}).get("teamName", "Team B"))
            venue_info = match_info.get("venueInfo", {})
            venue = str(venue_info.get("ground", "Unknown Venue"))
            city = str(venue_info.get("city", ""))

            score = raw_match.get("matchScore", {})
            team1_score = self._render_team_score(score.get("team1Score", {}))
            team2_score = self._render_team_score(score.get("team2Score", {}))
            team1_details = self._extract_primary_innings(score.get("team1Score", {}))
            team2_details = self._extract_primary_innings(score.get("team2Score", {}))

            matches.append(
                LiveMatch(
                    match_id=match_id,
                    series_name=str(match_info.get("seriesName", "Cricket Match")),
                    match_desc=str(match_info.get("matchDesc", "")),
                    format_type=format_type,
                    team1=team1,
                    team2=team2,
                    venue=venue,
                    city=city,
                    status=str(match_info.get("status", "")),
                    state=state,
                    short_status=str(match_info.get("shortStatus", "")),
                    team1_score=team1_score,
                    team2_score=team2_score,
                    team1_runs=team1_details.get("runs"),
                    team2_runs=team2_details.get("runs"),
                    team1_wickets=team1_details.get("wickets"),
                    team2_wickets=team2_details.get("wickets"),
                    team1_overs=team1_details.get("overs"),
                    team2_overs=team2_details.get("overs"),
                )
            )
            if len(matches) >= limit:
                break
        return matches

    def _extract_matches_payload(self, html: str) -> Dict[str, Any]:
        text = html.replace("\\\"", "\"").replace("\\n", "").replace("\\/", "/")
        marker = "\"matchesList\":{\"matches\":["
        idx = text.find(marker)
        if idx < 0:
            return {"matches": []}

        object_start = idx + len("\"matchesList\":")
        depth = 0
        in_string = False
        escaped = False
        end = None

        for pos, ch in enumerate(text[object_start:], start=object_start):
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == "\"":
                    in_string = False
            else:
                if ch == "\"":
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = pos + 1
                        break

        if end is None:
            return {"matches": []}

        snippet = text[object_start:end]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            return {"matches": []}

    @staticmethod
    def _render_team_score(team_score: Dict[str, Any]) -> str:
        innings = []
        for details in team_score.values():
            if not isinstance(details, dict):
                continue
            runs = details.get("runs")
            wickets = details.get("wickets")
            overs = details.get("overs")
            if runs is None:
                continue
            wicket_txt = wickets if wickets is not None else "-"
            overs_txt = f"{overs}" if overs is not None else "-"
            innings.append(f"{runs}/{wicket_txt} ({overs_txt})")
        return " & ".join(innings) if innings else "-"

    @staticmethod
    def _extract_primary_innings(team_score: Dict[str, Any]) -> Dict[str, Optional[float | int]]:
        if not team_score:
            return {"runs": None, "wickets": None, "overs": None}
        first_key = sorted(team_score.keys())[0]
        details = team_score.get(first_key, {})
        if not isinstance(details, dict):
            return {"runs": None, "wickets": None, "overs": None}
        runs = details.get("runs")
        wickets = details.get("wickets")
        overs = details.get("overs")
        return {
            "runs": int(runs) if runs is not None else None,
            "wickets": int(wickets) if wickets is not None else None,
            "overs": float(overs) if overs is not None else None,
        }

