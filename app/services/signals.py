from __future__ import annotations

from dataclasses import dataclass


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


@dataclass
class WeatherSignal:
    condition: str
    rain_risk: float
    swing_factor: float = 0.0
    dew_factor: float = 0.0
    heat_fatigue: float = 0.0


class WeatherSignalService:
    _condition_defaults = {
        "clear": 0.05,
        "cloudy": 0.10,
        "humid": 0.15,
        "overcast": 0.22,
        "rain_threat": 0.45,
    }

    # Swing/seam conditions
    _swing_map = {
        "clear": 0.05,
        "cloudy": 0.25,
        "humid": 0.35,
        "overcast": 0.55,
        "rain_threat": 0.40,
    }

    def estimate(
        self,
        condition: str,
        humidity_pct: int,
        temperature_c: float = 28.0,
        wind_speed_kmh: float = 10.0,
        is_day_night: bool = False,
    ) -> WeatherSignal:
        base = self._condition_defaults.get(condition, 0.10)
        humidity_factor = clamp((humidity_pct - 45) / 100.0, 0.0, 0.35)
        rain_risk = clamp(base + humidity_factor, 0.0, 0.95)

        # Swing factor: overcast + humid + wind = seam movement
        swing_base = self._swing_map.get(condition, 0.10)
        wind_bonus = clamp((wind_speed_kmh - 15) / 40.0, 0.0, 0.2)
        swing_factor = clamp(swing_base + humidity_factor * 0.5 + wind_bonus, 0.0, 1.0)

        # Dew factor: evening matches with humidity
        dew_factor = 0.0
        if is_day_night and humidity_pct > 55:
            dew_factor = clamp((humidity_pct - 55) / 40.0, 0.0, 0.8)

        # Heat fatigue: extreme temps affect performance
        heat_fatigue = 0.0
        if temperature_c > 38:
            heat_fatigue = clamp((temperature_c - 38) / 10.0, 0.0, 0.5)

        return WeatherSignal(
            condition=condition,
            rain_risk=rain_risk,
            swing_factor=swing_factor,
            dew_factor=dew_factor,
            heat_fatigue=heat_fatigue,
        )


class NewsSignalService:
    # Cricket-specific weighted phrase matching
    _positive_phrases = {
        # Player fitness & availability
        "fit": 1.0, "declared fit": 2.0, "passed fitness test": 2.0,
        "comeback": 1.5, "returns to squad": 2.0, "available": 1.0,
        # Form & momentum
        "in-form": 1.5, "confident": 1.0, "dominant": 1.5,
        "strong": 0.8, "momentum": 1.0, "winning streak": 2.0,
        "century": 1.2, "five-wicket": 1.5, "hat-trick": 2.0,
        # Tactical advantages
        "home conditions": 1.0, "familiar conditions": 0.8,
        "full-strength": 1.5, "unchanged squad": 1.0,
    }

    _negative_phrases = {
        # Player issues
        "injury": 1.5, "injured": 1.5, "ruled out": 2.5,
        "doubt": 1.0, "doubtful": 1.2, "hamstring": 1.5,
        "concussion": 2.0, "fracture": 2.0,
        # Form issues
        "out-of-form": 1.5, "poor form": 1.5, "struggling": 1.0,
        "fatigue": 1.0, "fatigued": 1.0, "workload": 0.8,
        # Squad disruption
        "suspension": 2.0, "banned": 2.0, "dropped": 1.5,
        "miss": 1.0, "misses": 1.0, "missing": 1.2,
        "unavailable": 1.5, "rested": 0.8,
        # Key player concerns
        "captain injured": 3.0, "key pacer out": 2.5,
        "star player": 0.5,  # neutral but signals importance
    }

    # Star player names — their availability swings predictions more
    _impact_players = {
        "kohli", "rohit", "bumrah", "jadeja", "ashwin",
        "smith", "cummins", "starc", "warner", "head",
        "babar", "shaheen", "rizwan", "root", "stokes",
        "rabada", "de kock", "williamson", "boult",
        "rashid khan", "buttler", "archer", "gill",
        "dhoni", "chahal", "pant", "hardik", "siraj",
        "suryakumar", "jaiswal", "nortje", "klaasen",
    }

    def estimate_edge(self, text: str, team_a: str, team_b: str) -> float:
        if not text.strip():
            return 0.0

        lower = text.lower()
        score_a = self._score_for_team(lower, team_a.lower())
        score_b = self._score_for_team(lower, team_b.lower())
        diff = score_a - score_b
        return clamp(diff / 6.0, -1.0, 1.0)

    def _score_for_team(self, text: str, team_name: str) -> float:
        windowed = text
        if team_name in text:
            center = text.find(team_name)
            start = max(center - 150, 0)
            end = min(center + 150, len(text))
            windowed = text[start:end]

        # Weighted phrase matching
        pos_score = sum(
            weight * windowed.count(phrase)
            for phrase, weight in self._positive_phrases.items()
            if phrase in windowed
        )
        neg_score = sum(
            weight * windowed.count(phrase)
            for phrase, weight in self._negative_phrases.items()
            if phrase in windowed
        )

        # Star player name mentions near negative keywords amplify the signal
        star_boost = 0.0
        for player in self._impact_players:
            if player in windowed:
                # Check if nearby text contains negative sentiment
                p_idx = windowed.find(player)
                nearby = windowed[max(p_idx - 40, 0):min(p_idx + 40, len(windowed))]
                neg_nearby = sum(1 for phrase in self._negative_phrases if phrase in nearby)
                pos_nearby = sum(1 for phrase in self._positive_phrases if phrase in nearby)
                star_boost += (pos_nearby - neg_nearby) * 0.8

        return float(pos_score - neg_score + star_boost)

    def summarize(self, edge: float) -> str:
        if edge > 0.2:
            return "Recent news flow supports Team A."
        if edge < -0.2:
            return "Recent news flow supports Team B."
        return "Recent news flow looks neutral."
