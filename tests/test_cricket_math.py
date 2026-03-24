from app.core.cricket_math import overs_to_balls


def test_overs_to_balls_cricket_notation_and_feed_edge() -> None:
    assert overs_to_balls(8.3) == 51
    assert overs_to_balls(19.5) == 119
    assert overs_to_balls(19.6) == 120

