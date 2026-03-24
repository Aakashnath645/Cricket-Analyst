from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import joblib
import numpy as np

from app.core.feature_engineering import LIVE_FEATURES, PREMATCH_FEATURES, FeatureEngineer
from app.core.simulation import LiveSimulator
from app.data.models import LiveMatchState, MatchContext, PredictionResult


def sigmoid(value: float) -> float:
    return 1.0 / (1.0 + np.exp(-value))


class CricketPredictor:
    def __init__(self, model_dir: str | Path = "models") -> None:
        self.model_dir = Path(model_dir)
        self.features = FeatureEngineer()
        self.simulator = LiveSimulator()
        self.prematch_model = self._load_model("prematch_model.joblib")
        self.live_model = self._load_model("live_model.joblib")

    def predict_prematch(self, ctx: MatchContext) -> PredictionResult:
        x = self.features.build_prematch_features(ctx)
        if self.prematch_model is None:
            team_a_probability = self._heuristic_prematch(x)
            model_used = "heuristic_baseline"
            key_factors = self._heuristic_prematch_factors(x)
        else:
            try:
                team_a_probability = float(self.prematch_model.predict_proba([x])[0, 1])
                model_used = self._model_name(self.prematch_model, "prematch")
                key_factors = self._model_factors(
                    model=self.prematch_model,
                    features=PREMATCH_FEATURES,
                    values=x,
                )
            except Exception:
                team_a_probability = self._heuristic_prematch(x)
                model_used = "heuristic_fallback"
                key_factors = self._heuristic_prematch_factors(x)

        team_b_probability = 1.0 - team_a_probability
        confidence = self._confidence(team_a_probability)
        return PredictionResult(
            team_a_win_probability=team_a_probability,
            team_b_win_probability=team_b_probability,
            confidence=confidence,
            model_used=model_used,
            key_factors=key_factors,
        )

    def predict_live(
        self,
        ctx: MatchContext,
        live: LiveMatchState,
        prematch_team_a_probability: float,
    ) -> PredictionResult:
        x = self.features.build_live_features(ctx, live, prematch_team_a_probability)
        batting_is_team_a = live.batting_side.lower() in {"team_a", "a"}

        if self.live_model is None:
            batting_win_probability = self._heuristic_live(x)
            model_used = "heuristic_live"
            key_factors = self._heuristic_live_factors(x)
        else:
            try:
                batting_win_probability = float(self.live_model.predict_proba([x])[0, 1])
                model_used = self._model_name(self.live_model, "live")
                key_factors = self._model_factors(
                    model=self.live_model,
                    features=LIVE_FEATURES,
                    values=x,
                )
            except Exception:
                batting_win_probability = self._heuristic_live(x)
                model_used = "heuristic_live_fallback"
                key_factors = self._heuristic_live_factors(x)

        simulation_probability = None
        if live.target_runs:
            sim = self.simulator.estimate(live)
            simulation_probability = sim.win_probability
            match_phase = min(live.overs_completed / max(live.max_overs, 1.0), 1.0)
            # Late in the match, trust simulation more; early, trust model more
            model_weight = 0.70 - (0.30 * match_phase)
            sim_weight = 1.0 - model_weight
            batting_win_probability = (
                model_weight * batting_win_probability + sim_weight * simulation_probability
            )
            key_factors.append(f"Monte Carlo chase projection: {simulation_probability:.1%}")

        team_a_probability = batting_win_probability if batting_is_team_a else (1.0 - batting_win_probability)
        team_b_probability = 1.0 - team_a_probability

        if simulation_probability is not None:
            model_used = f"{model_used}+monte_carlo"

        return PredictionResult(
            team_a_win_probability=team_a_probability,
            team_b_win_probability=team_b_probability,
            confidence=self._confidence(team_a_probability),
            model_used=model_used,
            key_factors=key_factors[:5],
        )

    def _load_model(self, model_name: str) -> Optional[object]:
        path = self.model_dir / model_name
        if not path.exists():
            return None
        try:
            return joblib.load(path)
        except Exception:
            return None

    @staticmethod
    def _model_name(model: object, prefix: str) -> str:
        cls_name = type(model).__name__.lower()
        # Check calibrated wrapper first
        if "calibrated" in cls_name and hasattr(model, "estimator"):
            inner = type(model.estimator).__name__.lower()
            if "gradient" in inner:
                return f"{prefix}_calibrated_gradient_boosting"
            return f"{prefix}_calibrated_{inner}"
        if "gradient" in cls_name:
            return f"{prefix}_gradient_boosting"
        if "logistic" in cls_name:
            return f"{prefix}_logistic_regression"
        return f"{prefix}_{cls_name}"

    @staticmethod
    def _confidence(team_a_probability: float) -> float:
        return min(0.98, 0.45 + abs(team_a_probability - 0.5) * 1.1)

    @staticmethod
    def _heuristic_prematch(x: np.ndarray) -> float:
        weights = np.array(
            [
                0.75,   # rating_diff
                2.15,   # form_diff
                1.30,   # h2h_edge
                0.85,   # home_advantage
                0.70,   # toss_advantage
                0.18,   # pitch_batting_index
                0.07,   # pitch_spin_index
                0.07,   # pitch_pace_index
                -1.20,  # weather_rain_risk
                0.90,   # news_edge
                0.20,   # venue_scoring_index
                0.30,   # venue_chase_tendency
                0.10,   # venue_boundary_index
                0.15,   # dew_factor
                0.03,   # format_t20
                0.01,   # format_odi
                -0.02,  # format_test
            ],
            dtype=float,
        )
        return float(sigmoid(np.dot(x, weights)))

    @staticmethod
    def _heuristic_live(x: np.ndarray) -> float:
        weights = np.array(
            [
                2.40,   # prematch_prob_for_batting
                -0.25,  # overs_completed_ratio
                1.60,   # wickets_in_hand_ratio
                0.20,   # current_run_rate
                0.24,   # recent_run_rate
                0.60,   # momentum_edge
                -0.28,  # required_run_rate
                -0.65,  # rr_pressure
                -1.30,  # runs_remaining_ratio
                -0.65,  # balls_remaining_ratio
                0.10,   # target_defined
                0.15,   # venue_scoring_index
                0.25,   # venue_chase_tendency
                -0.10,  # innings_phase
                0.02,   # format_t20
                0.00,   # format_odi
                -0.02,  # format_test
            ],
            dtype=float,
        )
        center = np.dot(x, weights) - 1.25
        return float(sigmoid(center))

    @staticmethod
    def _heuristic_prematch_factors(values: np.ndarray) -> List[str]:
        factor_names = [
            "rating gap", "recent team form", "head-to-head trend",
            "home/venue edge", "toss impact", "pitch batting index",
            "pitch spin index", "pitch pace index", "weather risk",
            "news sentiment", "venue scoring", "venue chase tendency",
            "venue boundary %", "dew factor",
            "T20 format signal", "ODI format signal", "Test format signal",
        ]
        strengths = np.abs(values)
        top_idx = np.argsort(strengths)[::-1][:5]
        return [factor_names[i] for i in top_idx if i < len(factor_names)]

    @staticmethod
    def _heuristic_live_factors(values: np.ndarray) -> List[str]:
        factor_names = [
            "pre-match win prior", "innings phase", "wickets in hand",
            "current run rate", "recent run rate", "momentum signal",
            "required run rate", "RR pressure", "runs remaining ratio",
            "balls remaining ratio", "target context",
            "venue scoring", "venue chase tendency", "innings phase signal",
            "T20 format signal", "ODI format signal", "Test format signal",
        ]
        strengths = np.abs(values)
        top_idx = np.argsort(strengths)[::-1][:5]
        return [factor_names[i] for i in top_idx if i < len(factor_names)]

    @staticmethod
    def _model_factors(model: object, features: List[str], values: np.ndarray) -> List[str]:
        """Extract feature importance from the trained model."""
        # GradientBoosting has feature_importances_
        if hasattr(model, "feature_importances_"):
            importance = model.feature_importances_ * np.sign(values)
            top_idx = np.argsort(np.abs(importance))[::-1][:5]
            return [
                f"{features[i]} ({importance[i]:+.3f})"
                for i in top_idx if i < len(features)
            ]
        # CalibratedClassifierCV wraps inner model
        if hasattr(model, "estimator") and hasattr(model.estimator, "feature_importances_"):
            importance = model.estimator.feature_importances_ * np.sign(values)
            top_idx = np.argsort(np.abs(importance))[::-1][:5]
            return [
                f"{features[i]} ({importance[i]:+.3f})"
                for i in top_idx if i < len(features)
            ]
        # LogisticRegression has coef_
        if hasattr(model, "coef_"):
            contribution = model.coef_[0] * values
            top_idx = np.argsort(np.abs(contribution))[::-1][:5]
            return [
                f"{features[i]} ({contribution[i]:+.2f})"
                for i in top_idx if i < len(features)
            ]
        return []
