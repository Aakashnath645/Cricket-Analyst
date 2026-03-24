from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


@dataclass
class MatchContext:
    tournament: str
    format_type: str
    team_a: str
    team_b: str
    venue: str
    team_a_rating: float
    team_b_rating: float
    team_a_recent_win_pct: float
    team_b_recent_win_pct: float
    team_a_h2h_win_pct: float
    toss_winner: str
    toss_decision: str
    pitch_type: str
    weather_condition: str
    weather_rain_risk: float = 0.1
    home_advantage: float = 0.0
    news_edge: float = 0.0
    # ── New features ──
    venue_avg_score: float = 160.0
    venue_chase_win_pct: float = 0.5
    venue_boundary_pct: float = 0.45
    dew_factor: float = 0.0

    def normalize(self) -> None:
        self.team_a_recent_win_pct = clamp(self.team_a_recent_win_pct, 0.0, 1.0)
        self.team_b_recent_win_pct = clamp(self.team_b_recent_win_pct, 0.0, 1.0)
        self.team_a_h2h_win_pct = clamp(self.team_a_h2h_win_pct, 0.0, 1.0)
        self.weather_rain_risk = clamp(self.weather_rain_risk, 0.0, 1.0)
        self.home_advantage = clamp(self.home_advantage, -1.0, 1.0)
        self.news_edge = clamp(self.news_edge, -1.0, 1.0)
        self.venue_avg_score = clamp(self.venue_avg_score, 80.0, 300.0)
        self.venue_chase_win_pct = clamp(self.venue_chase_win_pct, 0.0, 1.0)
        self.venue_boundary_pct = clamp(self.venue_boundary_pct, 0.0, 1.0)
        self.dew_factor = clamp(self.dew_factor, 0.0, 1.0)


@dataclass
class LiveMatchState:
    batting_side: str
    overs_completed: float
    runs_scored: int
    wickets_lost: int
    max_overs: float
    target_runs: Optional[int] = None
    recent_run_rate: float = 0.0
    momentum_edge: float = 0.0

    def normalize(self) -> None:
        self.overs_completed = clamp(self.overs_completed, 0.0, self.max_overs)
        self.wickets_lost = int(clamp(float(self.wickets_lost), 0.0, 10.0))
        self.runs_scored = max(self.runs_scored, 0)
        if self.target_runs is not None:
            self.target_runs = max(self.target_runs, 1)
        self.recent_run_rate = clamp(self.recent_run_rate, 0.0, 20.0)
        self.momentum_edge = clamp(self.momentum_edge, -1.0, 1.0)


@dataclass
class PredictionResult:
    team_a_win_probability: float
    team_b_win_probability: float
    confidence: float
    model_used: str
    key_factors: List[str] = field(default_factory=list)
