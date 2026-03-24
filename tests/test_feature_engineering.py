from app.core.cricket_math import overs_to_balls
from app.core.feature_engineering import LIVE_FEATURES, PREMATCH_FEATURES, FeatureEngineer
from app.data.models import LiveMatchState, MatchContext


def test_prematch_feature_vector_length() -> None:
    engineer = FeatureEngineer()
    ctx = MatchContext(
        tournament="IPL",
        format_type="T20",
        team_a="Team A",
        team_b="Team B",
        venue="Mumbai",
        team_a_rating=1620,
        team_b_rating=1560,
        team_a_recent_win_pct=0.65,
        team_b_recent_win_pct=0.58,
        team_a_h2h_win_pct=0.54,
        toss_winner="team_a",
        toss_decision="bowl",
        pitch_type="balanced",
        weather_condition="humid",
        weather_rain_risk=0.0,
        home_advantage=1.0,
        news_edge=0.1,
    )
    x = engineer.build_prematch_features(ctx)
    assert len(x) == len(PREMATCH_FEATURES)
    assert x[0] > 0


def test_live_feature_vector_length() -> None:
    engineer = FeatureEngineer()
    ctx = MatchContext(
        tournament="IPL",
        format_type="T20",
        team_a="Team A",
        team_b="Team B",
        venue="Mumbai",
        team_a_rating=1620,
        team_b_rating=1560,
        team_a_recent_win_pct=0.65,
        team_b_recent_win_pct=0.58,
        team_a_h2h_win_pct=0.54,
        toss_winner="team_a",
        toss_decision="bowl",
        pitch_type="balanced",
        weather_condition="humid",
        weather_rain_risk=0.0,
        home_advantage=1.0,
        news_edge=0.1,
    )
    live = LiveMatchState(
        batting_side="team_a",
        overs_completed=9.2,
        runs_scored=84,
        wickets_lost=3,
        max_overs=20.0,
        target_runs=176,
        recent_run_rate=8.8,
        momentum_edge=0.2,
    )
    x = engineer.build_live_features(ctx, live, prematch_team_a_probability=0.58)
    assert len(x) == len(LIVE_FEATURES)
    assert 0.0 <= x[0] <= 1.0


def test_overs_notation_is_parsed_as_base_six() -> None:
    assert overs_to_balls(8.3) == 51
    assert overs_to_balls(19.5) == 119
    assert overs_to_balls(8.5) == 53  # cricket notation: 8 overs + 5 balls
