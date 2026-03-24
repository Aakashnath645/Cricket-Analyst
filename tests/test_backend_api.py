from fastapi.testclient import TestClient

from backend.server import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_prematch_endpoint() -> None:
    payload = {
        "tournament": "IPL",
        "format_type": "T20",
        "team_a": "Mumbai Indians",
        "team_b": "Chennai Super Kings",
        "venue": "Mumbai",
        "team_a_rating": 1620,
        "team_b_rating": 1580,
        "team_a_recent_win_pct": 0.62,
        "team_b_recent_win_pct": 0.55,
        "team_a_h2h_win_pct": 0.52,
        "toss_winner": "team_a",
        "toss_decision": "bat",
        "pitch_type": "balanced",
        "weather_condition": "clear",
        "humidity_pct": 58,
        "home_advantage": 1.0,
        "news_notes": "Mumbai are confident and in-form."
    }
    response = client.post("/predict/prematch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert 0.0 <= data["teamAWinProbability"] <= 1.0
    assert 0.0 <= data["teamBWinProbability"] <= 1.0
    assert abs((data["teamAWinProbability"] + data["teamBWinProbability"]) - 1.0) < 1e-8
