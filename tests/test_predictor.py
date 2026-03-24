from app.core.predictor import CricketPredictor
from app.data.models import LiveMatchState, MatchContext


def sample_context() -> MatchContext:
    return MatchContext(
        tournament="IPL",
        format_type="T20",
        team_a="Mumbai Indians",
        team_b="Chennai Super Kings",
        venue="Mumbai",
        team_a_rating=1630,
        team_b_rating=1615,
        team_a_recent_win_pct=0.64,
        team_b_recent_win_pct=0.57,
        team_a_h2h_win_pct=0.51,
        toss_winner="team_a",
        toss_decision="bowl",
        pitch_type="batting_friendly",
        weather_condition="humid",
        weather_rain_risk=0.18,
        home_advantage=1.0,
        news_edge=0.2,
    )


def test_predictor_returns_valid_probabilities() -> None:
    predictor = CricketPredictor(model_dir="models")
    ctx = sample_context()
    pre = predictor.predict_prematch(ctx)
    assert 0.0 <= pre.team_a_win_probability <= 1.0
    assert abs(pre.team_a_win_probability + pre.team_b_win_probability - 1.0) < 1e-8


def test_live_predictor_returns_valid_probabilities() -> None:
    predictor = CricketPredictor(model_dir="models")
    ctx = sample_context()
    live = LiveMatchState(
        batting_side="team_a",
        overs_completed=11.4,
        runs_scored=104,
        wickets_lost=4,
        max_overs=20.0,
        target_runs=182,
        recent_run_rate=8.7,
        momentum_edge=0.15,
    )
    result = predictor.predict_live(ctx, live, prematch_team_a_probability=0.56)
    assert 0.0 <= result.team_a_win_probability <= 1.0
    assert abs(result.team_a_win_probability + result.team_b_win_probability - 1.0) < 1e-8

