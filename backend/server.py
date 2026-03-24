from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.core.predictor import CricketPredictor
from app.data.models import LiveMatchState, MatchContext
from app.services.historical_data import HistoricalProfilesService
from app.services.live_data import CricbuzzLiveService
from app.services.news_data import GoogleNewsRssService
from app.services.signals import NewsSignalService, WeatherSignalService
from app.services.weather_data import OpenMeteoWeatherService


class PreMatchRequest(BaseModel):
    tournament: str = "League"
    format_type: str = "T20"
    team_a: str
    team_b: str
    venue: str = "Unknown Venue"
    team_a_rating: float = 1600.0
    team_b_rating: float = 1600.0
    team_a_recent_win_pct: float = 0.5
    team_b_recent_win_pct: float = 0.5
    team_a_h2h_win_pct: float = 0.5
    toss_winner: str = "team_a"
    toss_decision: str = "bat"
    pitch_type: str = "balanced"
    weather_condition: str = "clear"
    humidity_pct: int = 60
    home_advantage: float = 0.0
    news_notes: str = ""
    venue_avg_score: float = 160.0
    venue_chase_win_pct: float = 0.5
    venue_boundary_pct: float = 0.45
    dew_factor: float = 0.0


class LiveStateRequest(BaseModel):
    batting_side: str
    overs_completed: float
    runs_scored: int
    wickets_lost: int
    max_overs: float
    target_runs: Optional[int] = None
    recent_run_rate: float = 0.0
    momentum_edge: float = 0.0


class LivePredictionRequest(BaseModel):
    context: PreMatchRequest
    live_state: LiveStateRequest
    prematch_team_a_probability: float = 0.5


class HistoricalSyncRequest(BaseModel):
    tournament_key: str = "ipl"
    max_matches: int = 1800
    force_download: bool = False


class HistoricalSuggestRequest(BaseModel):
    team_a: str
    team_b: str
    venue: str


class NewsRequest(BaseModel):
    query: str
    limit: int = 8


app = FastAPI(title="CricAnalyst API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

predictor = CricketPredictor(model_dir="models")
weather_signal_service = WeatherSignalService()
news_signal_service = NewsSignalService()
live_feed_service = CricbuzzLiveService()
historical_service = HistoricalProfilesService(data_dir="data")
weather_feed_service = OpenMeteoWeatherService()
news_feed_service = GoogleNewsRssService()


def _build_context(request: PreMatchRequest) -> MatchContext:
    weather_signal = weather_signal_service.estimate(
        condition=request.weather_condition,
        humidity_pct=request.humidity_pct,
    )
    news_edge = news_signal_service.estimate_edge(
        text=request.news_notes,
        team_a=request.team_a,
        team_b=request.team_b,
    )
    return MatchContext(
        tournament=request.tournament,
        format_type=request.format_type,
        team_a=request.team_a,
        team_b=request.team_b,
        venue=request.venue,
        team_a_rating=request.team_a_rating,
        team_b_rating=request.team_b_rating,
        team_a_recent_win_pct=request.team_a_recent_win_pct,
        team_b_recent_win_pct=request.team_b_recent_win_pct,
        team_a_h2h_win_pct=request.team_a_h2h_win_pct,
        toss_winner=request.toss_winner,
        toss_decision=request.toss_decision,
        pitch_type=request.pitch_type,
        weather_condition=weather_signal.condition,
        weather_rain_risk=weather_signal.rain_risk,
        home_advantage=request.home_advantage,
        news_edge=news_edge,
        venue_avg_score=request.venue_avg_score,
        venue_chase_win_pct=request.venue_chase_win_pct,
        venue_boundary_pct=request.venue_boundary_pct,
        dew_factor=request.dew_factor,
    )


def _build_live_state(request: LiveStateRequest) -> LiveMatchState:
    return LiveMatchState(
        batting_side=request.batting_side,
        overs_completed=request.overs_completed,
        runs_scored=request.runs_scored,
        wickets_lost=request.wickets_lost,
        max_overs=request.max_overs,
        target_runs=request.target_runs,
        recent_run_rate=request.recent_run_rate,
        momentum_edge=request.momentum_edge,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/predict/prematch")
def predict_prematch(request: PreMatchRequest) -> dict[str, Any]:
    context = _build_context(request)
    result = predictor.predict_prematch(context)
    return {
        "teamA": context.team_a,
        "teamB": context.team_b,
        "teamAWinProbability": result.team_a_win_probability,
        "teamBWinProbability": result.team_b_win_probability,
        "confidence": result.confidence,
        "modelUsed": result.model_used,
        "keyFactors": result.key_factors,
    }


@app.post("/predict/live")
def predict_live(request: LivePredictionRequest) -> dict[str, Any]:
    context = _build_context(request.context)
    live_state = _build_live_state(request.live_state)
    result = predictor.predict_live(
        ctx=context,
        live=live_state,
        prematch_team_a_probability=request.prematch_team_a_probability,
    )
    simulation = predictor.simulator.estimate(live_state, iterations=900)
    return {
        "teamA": context.team_a,
        "teamB": context.team_b,
        "teamAWinProbability": result.team_a_win_probability,
        "teamBWinProbability": result.team_b_win_probability,
        "confidence": result.confidence,
        "modelUsed": result.model_used,
        "keyFactors": result.key_factors,
        "projectedScore": simulation.projected_score,
    }


@app.get("/feeds/live")
def get_live_matches(limit: int = 24, include_completed: bool = False) -> dict[str, Any]:
    try:
        matches = live_feed_service.fetch_matches(limit=limit, include_completed=include_completed)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Live feed error: {exc}") from exc
    return {
        "matches": [
            {
                "matchId": match.match_id,
                "seriesName": match.series_name,
                "matchDesc": match.match_desc,
                "formatType": match.format_type,
                "team1": match.team1,
                "team2": match.team2,
                "venue": match.venue,
                "city": match.city,
                "status": match.status,
                "state": match.state,
                "shortStatus": match.short_status,
                "team1Score": match.team1_score,
                "team2Score": match.team2_score,
                "team1Runs": match.team1_runs,
                "team2Runs": match.team2_runs,
                "team1Wickets": match.team1_wickets,
                "team2Wickets": match.team2_wickets,
                "team1Overs": match.team1_overs,
                "team2Overs": match.team2_overs,
                "displayLabel": match.display_label,
            }
            for match in matches
        ]
    }


@app.get("/signals/weather")
def get_weather(location: str) -> dict[str, Any]:
    try:
        snapshot = weather_feed_service.fetch_current(location_query=location)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Weather feed error: {exc}") from exc
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Location not found")
    return {
        "locationName": snapshot.location_name,
        "temperatureC": snapshot.temperature_c,
        "humidityPct": snapshot.humidity_pct,
        "rainProbabilityPct": snapshot.rain_probability_pct,
        "windSpeedKmh": snapshot.wind_speed_kmh,
        "weatherCode": snapshot.weather_code,
        "condition": snapshot.condition,
    }


@app.post("/signals/news")
def get_news(request: NewsRequest) -> dict[str, Any]:
    try:
        headlines = news_feed_service.fetch(query=request.query, limit=request.limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"News feed error: {exc}") from exc
    return {
        "headlines": [
            {
                "title": item.title,
                "link": item.link,
                "published": item.published,
            }
            for item in headlines
        ],
        "signalText": GoogleNewsRssService.to_signal_text(headlines),
    }


@app.post("/historical/sync")
def sync_historical(request: HistoricalSyncRequest) -> dict[str, str]:
    try:
        message = historical_service.sync_from_cricsheet(
            tournament_key=request.tournament_key,
            max_matches=request.max_matches,
            force_download=request.force_download,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Historical sync error: {exc}") from exc
    return {"message": message}


@app.post("/historical/suggest")
def suggest_historical(request: HistoricalSuggestRequest) -> dict[str, Any]:
    suggestion = historical_service.suggest_for_match(
        team_a=request.team_a,
        team_b=request.team_b,
        venue=request.venue,
    )
    return {
        "teamARating": suggestion.team_a_rating,
        "teamBRating": suggestion.team_b_rating,
        "teamARecentWinPct": suggestion.team_a_recent_win_pct,
        "teamBRecentWinPct": suggestion.team_b_recent_win_pct,
        "teamAH2hWinPct": suggestion.team_a_h2h_win_pct,
        "pitchType": suggestion.pitch_type,
        "pitchSummary": suggestion.pitch_summary,
        "source": suggestion.source,
        "venueAvgScore": suggestion.venue_avg_score,
        "venueChaseWinPct": suggestion.venue_chase_win_pct,
        "venueBoundaryPct": suggestion.venue_boundary_pct,
    }
