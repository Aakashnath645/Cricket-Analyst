from __future__ import annotations

from typing import Dict, List

import numpy as np

from app.core.cricket_math import balls_to_overs_float, overs_to_balls
from app.data.models import LiveMatchState, MatchContext


PREMATCH_FEATURES: List[str] = [
    "rating_diff",
    "form_diff",
    "h2h_edge",
    "home_advantage",
    "toss_advantage",
    "pitch_batting_index",
    "pitch_spin_index",
    "pitch_pace_index",
    "weather_rain_risk",
    "news_edge",
    "venue_scoring_index",
    "venue_chase_tendency",
    "venue_boundary_index",
    "dew_factor",
    "format_t20",
    "format_odi",
    "format_test",
]

LIVE_FEATURES: List[str] = [
    "prematch_prob_for_batting",
    "overs_completed_ratio",
    "wickets_in_hand_ratio",
    "current_run_rate",
    "recent_run_rate",
    "momentum_edge",
    "required_run_rate",
    "rr_pressure",
    "runs_remaining_ratio",
    "balls_remaining_ratio",
    "target_defined",
    "venue_scoring_index",
    "venue_chase_tendency",
    "innings_phase",
    "format_t20",
    "format_odi",
    "format_test",
]


class FeatureEngineer:
    _pitch_map: Dict[str, Dict[str, float]] = {
        "batting_friendly": {"batting": 1.0, "spin": 0.2, "pace": 0.3},
        "balanced": {"batting": 0.0, "spin": 0.0, "pace": 0.0},
        "spin_friendly": {"batting": -0.3, "spin": 1.0, "pace": -0.4},
        "pace_friendly": {"batting": -0.2, "spin": -0.3, "pace": 1.0},
        "slow_low": {"batting": -0.5, "spin": 0.7, "pace": -0.5},
    }

    _weather_risk_map: Dict[str, float] = {
        "clear": 0.05,
        "cloudy": 0.10,
        "humid": 0.15,
        "overcast": 0.22,
        "rain_threat": 0.45,
    }

    def build_prematch_features(self, ctx: MatchContext) -> np.ndarray:
        ctx.normalize()
        pitch = self._pitch_map.get(ctx.pitch_type, self._pitch_map["balanced"])
        weather_risk = ctx.weather_rain_risk
        if weather_risk <= 0:
            weather_risk = self._weather_risk_map.get(ctx.weather_condition, 0.10)

        # Venue-derived features (normalized around typical T20 scores)
        venue_scoring_index = (ctx.venue_avg_score - 160.0) / 40.0  # centered at 160, scaled
        venue_chase_tendency = ctx.venue_chase_win_pct - 0.5  # centered at 50%
        venue_boundary_index = (ctx.venue_boundary_pct - 0.45) / 0.15  # centered at 45%

        features = {
            "rating_diff": (ctx.team_a_rating - ctx.team_b_rating) / 100.0,
            "form_diff": ctx.team_a_recent_win_pct - ctx.team_b_recent_win_pct,
            "h2h_edge": ctx.team_a_h2h_win_pct - 0.5,
            "home_advantage": ctx.home_advantage,
            "toss_advantage": self._calculate_toss_advantage(ctx),
            "pitch_batting_index": pitch["batting"],
            "pitch_spin_index": pitch["spin"],
            "pitch_pace_index": pitch["pace"],
            "weather_rain_risk": weather_risk,
            "news_edge": ctx.news_edge,
            "venue_scoring_index": venue_scoring_index,
            "venue_chase_tendency": venue_chase_tendency,
            "venue_boundary_index": venue_boundary_index,
            "dew_factor": ctx.dew_factor,
            **self._format_one_hot(ctx.format_type),
        }
        return np.array([features[key] for key in PREMATCH_FEATURES], dtype=float)

    def build_live_features(
        self,
        ctx: MatchContext,
        live: LiveMatchState,
        prematch_team_a_probability: float,
    ) -> np.ndarray:
        ctx.normalize()
        live.normalize()

        batting_is_team_a = live.batting_side.lower() in {"team_a", "a"}
        prematch_prob_for_batting = (
            prematch_team_a_probability if batting_is_team_a else 1.0 - prematch_team_a_probability
        )

        balls_total = int(live.max_overs * 6)
        balls_bowled = min(overs_to_balls(live.overs_completed), balls_total)
        balls_remaining = max(balls_total - balls_bowled, 0)
        overs_completed = balls_to_overs_float(balls_bowled)
        current_run_rate = (live.runs_scored * 6) / max(balls_bowled, 1)

        wickets_in_hand_ratio = (10 - live.wickets_lost) / 10.0
        overs_completed_ratio = balls_bowled / max(balls_total, 1)
        balls_remaining_ratio = balls_remaining / max(balls_total, 1)

        target_defined = 1.0 if live.target_runs else 0.0
        runs_remaining_ratio = 0.0
        required_run_rate = 0.0
        rr_pressure = 0.0

        if live.target_runs:
            runs_required = max(live.target_runs - live.runs_scored, 0)
            runs_remaining_ratio = runs_required / max(live.target_runs, 1)
            required_run_rate = (runs_required * 6) / max(balls_remaining, 1)
            rr_pressure = required_run_rate - current_run_rate

        # Venue features for live model
        venue_scoring_index = (ctx.venue_avg_score - 160.0) / 40.0
        venue_chase_tendency = ctx.venue_chase_win_pct - 0.5

        # Innings phase: 0=powerplay, 0.5=middle, 1.0=death
        innings_phase = overs_completed_ratio

        features = {
            "prematch_prob_for_batting": prematch_prob_for_batting,
            "overs_completed_ratio": overs_completed_ratio,
            "wickets_in_hand_ratio": wickets_in_hand_ratio,
            "current_run_rate": current_run_rate,
            "recent_run_rate": live.recent_run_rate or current_run_rate,
            "momentum_edge": live.momentum_edge,
            "required_run_rate": required_run_rate,
            "rr_pressure": rr_pressure,
            "runs_remaining_ratio": runs_remaining_ratio,
            "balls_remaining_ratio": balls_remaining_ratio,
            "target_defined": target_defined,
            "venue_scoring_index": venue_scoring_index,
            "venue_chase_tendency": venue_chase_tendency,
            "innings_phase": innings_phase,
            **self._format_one_hot(ctx.format_type),
        }
        return np.array([features[key] for key in LIVE_FEATURES], dtype=float)

    @staticmethod
    def _format_one_hot(format_type: str) -> Dict[str, float]:
        normalized = format_type.strip().upper()
        return {
            "format_t20": 1.0 if normalized == "T20" else 0.0,
            "format_odi": 1.0 if normalized == "ODI" else 0.0,
            "format_test": 1.0 if normalized == "TEST" else 0.0,
        }

    def _calculate_toss_advantage(self, ctx: MatchContext) -> float:
        winner_is_team_a = ctx.toss_winner.strip().lower() in {"team_a", "a"}
        winner_sign = 1.0 if winner_is_team_a else -1.0

        decision_bonus = 0.10 if ctx.toss_decision.lower() == "bat" else 0.12
        pitch_bonus = 0.0

        if ctx.pitch_type in {"spin_friendly", "slow_low"} and ctx.toss_decision.lower() == "bowl":
            pitch_bonus += 0.04
        if ctx.pitch_type == "batting_friendly" and ctx.toss_decision.lower() == "bat":
            pitch_bonus += 0.03
        if ctx.weather_condition in {"humid", "overcast"} and ctx.toss_decision.lower() == "bowl":
            pitch_bonus += 0.03

        # Dew factor: bowling second is harder with dew
        if ctx.dew_factor > 0.3 and ctx.toss_decision.lower() == "bat":
            pitch_bonus += ctx.dew_factor * 0.06

        return winner_sign * (decision_bonus + pitch_bonus)
