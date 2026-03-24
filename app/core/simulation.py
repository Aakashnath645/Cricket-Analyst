from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.core.cricket_math import overs_to_balls
from app.data.models import LiveMatchState


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


@dataclass
class SimulationResult:
    win_probability: float
    projected_score: float


class LiveSimulator:
    def __init__(self, seed: int = 42) -> None:
        self.rng = np.random.default_rng(seed)
        self.run_values = np.array([0, 1, 2, 3, 4, 6], dtype=int)

    def estimate(self, state: LiveMatchState, iterations: int = 1200) -> SimulationResult:
        state.normalize()
        projected_score = self._project_final_score(state, samples=max(500, iterations // 2))

        if not state.target_runs:
            return SimulationResult(win_probability=0.0, projected_score=projected_score)

        wins = 0
        for _ in range(iterations):
            if self._simulate_single_chase(state):
                wins += 1
        return SimulationResult(win_probability=wins / iterations, projected_score=projected_score)

    def _simulate_single_chase(self, state: LiveMatchState) -> bool:
        balls_total = int(state.max_overs * 6)
        balls_bowled = min(overs_to_balls(state.overs_completed), balls_total)
        balls_remaining = max(balls_total - balls_bowled, 0)
        wickets = state.wickets_lost
        runs = state.runs_scored
        target = state.target_runs or 0

        for ball in range(balls_remaining):
            if runs >= target:
                return True
            if wickets >= 10:
                return False

            balls_left = balls_remaining - ball
            runs_required = max(target - runs, 0)
            required_rr = (runs_required * 6) / max(balls_left, 1)
            balls_faced = balls_bowled + ball
            current_rr = (runs * 6) / max(balls_faced, 1)

            wicket_prob, run_probs = self._ball_probabilities(
                wickets_lost=wickets,
                required_rr=required_rr,
                current_rr=current_rr,
            )

            if self.rng.random() < wicket_prob:
                wickets += 1
                continue

            runs += int(self.rng.choice(self.run_values, p=run_probs))

        return runs >= target

    def _project_final_score(self, state: LiveMatchState, samples: int) -> float:
        balls_total = int(state.max_overs * 6)
        balls_bowled = min(overs_to_balls(state.overs_completed), balls_total)
        balls_remaining = max(balls_total - balls_bowled, 0)

        totals = []
        for _ in range(samples):
            wickets = state.wickets_lost
            runs = state.runs_scored
            current_rr = (runs * 6) / max(balls_bowled, 1)
            target_rr = current_rr + 0.5

            for idx in range(balls_remaining):
                if wickets >= 10:
                    break
                wicket_prob, run_probs = self._ball_probabilities(
                    wickets_lost=wickets,
                    required_rr=target_rr,
                    current_rr=current_rr,
                )
                if self.rng.random() < wicket_prob:
                    wickets += 1
                else:
                    runs += int(self.rng.choice(self.run_values, p=run_probs))
                    balls_faced = balls_bowled + idx + 1
                    current_rr = (runs * 6) / max(balls_faced, 1)

            totals.append(runs)
        return float(np.mean(totals))

    @staticmethod
    def _ball_probabilities(
        wickets_lost: int,
        required_rr: float,
        current_rr: float,
    ) -> tuple[float, np.ndarray]:
        pressure = clamp((required_rr - current_rr) / 4.0, -0.8, 1.2)
        wickets_factor = wickets_lost / 10.0

        wicket_prob = clamp(0.020 + 0.008 * pressure + 0.010 * wickets_factor, 0.01, 0.12)
        base = np.array([0.33, 0.35, 0.13, 0.02, 0.12, 0.05], dtype=float)

        # Boundary intent goes up under pressure, with higher dismissal risk.
        base[4] += 0.05 * pressure
        base[5] += 0.04 * pressure
        base[0] -= 0.06 * pressure
        base[1] -= 0.03 * pressure

        # Conservative with wickets in hand depletion.
        if wickets_lost >= 7:
            base[0] += 0.05
            base[4] -= 0.03
            base[5] -= 0.03

        base = np.clip(base, 0.01, None)
        probs = base / base.sum()
        return wicket_prob, probs
