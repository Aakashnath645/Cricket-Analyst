import { useState } from "react";
import { apiGet, apiPost } from "./api";
import { WinDonut, TeamRadar, FactorsBar, ChaseGauge, MomentumChart } from "./Charts";

const DEFAULT_CONTEXT = {
  tournament: "IPL",
  formatType: "T20",
  teamA: "Mumbai Indians",
  teamB: "Chennai Super Kings",
  venue: "Wankhede Stadium",
  teamARating: 1600,
  teamBRating: 1570,
  teamARecentWinPct: 0.56,
  teamBRecentWinPct: 0.52,
  teamAH2hWinPct: 0.5,
  tossWinner: "team_a",
  tossDecision: "bat",
  pitchType: "balanced",
  weatherCondition: "clear",
  humidityPct: 60,
  homeAdvantage: 0,
  newsNotes: ""
};

const DEFAULT_LIVE_STATE = {
  battingSide: "team_a",
  overCount: 8,
  ballCount: 0,
  runsScored: 72,
  wicketsLost: 2,
  maxOvers: 20,
  targetRuns: 170,
  recentRunRate: 8.3,
  momentumEdge: 0.1
};

const TABS = [
  { key: "dataops", label: "Data Ops", icon: "📡" },
  { key: "match", label: "Match Setup", icon: "🏏" },
  { key: "live", label: "Live Prediction", icon: "⚡" },
];

function nowStamp() {
  return new Date().toLocaleTimeString();
}

function parseOvers(overs) {
  const whole = Math.floor(Number(overs || 0));
  let balls = Math.round((Number(overs || 0) - whole) * 10);
  if (balls > 5) {
    balls = 0;
  }
  return { overCount: whole, ballCount: balls };
}

function metric(value, fallback) {
  if (value === undefined || value === null) {
    return fallback;
  }
  return value;
}

export default function App() {
  const [context, setContext] = useState(DEFAULT_CONTEXT);
  const [liveState, setLiveState] = useState(DEFAULT_LIVE_STATE);
  const [historyPack, setHistoryPack] = useState("ipl");
  const [weatherLocation, setWeatherLocation] = useState("Mumbai");
  const [liveMatches, setLiveMatches] = useState([]);
  const [selectedMatchId, setSelectedMatchId] = useState("");
  const [news, setNews] = useState([]);
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("Ready");
  const [logs, setLogs] = useState([`${nowStamp()} App initialized`]);
  const [prematchProb, setPrematchProb] = useState(0.5);
  const [busy, setBusy] = useState(false);
  const [activeTab, setActiveTab] = useState("dataops");

  const pushLog = (line) => {
    setLogs((prev) => [...prev.slice(-200), `${nowStamp()} ${line}`]);
  };

  const updateContextField = (field, value) => {
    setContext((prev) => ({ ...prev, [field]: value }));
  };

  const updateLiveField = (field, value) => {
    setLiveState((prev) => ({ ...prev, [field]: value }));
  };

  const preMatchPayload = () => ({
    tournament: context.tournament,
    format_type: context.formatType,
    team_a: context.teamA,
    team_b: context.teamB,
    venue: context.venue,
    team_a_rating: Number(context.teamARating),
    team_b_rating: Number(context.teamBRating),
    team_a_recent_win_pct: Number(context.teamARecentWinPct),
    team_b_recent_win_pct: Number(context.teamBRecentWinPct),
    team_a_h2h_win_pct: Number(context.teamAH2hWinPct),
    toss_winner: context.tossWinner,
    toss_decision: context.tossDecision,
    pitch_type: context.pitchType,
    weather_condition: context.weatherCondition,
    humidity_pct: Number(context.humidityPct),
    home_advantage: Number(context.homeAdvantage),
    news_notes: context.newsNotes
  });

  const refreshLiveFeed = async () => {
    setBusy(true);
    setStatus("Refreshing live feed...");
    try {
      const data = await apiGet("/feeds/live?limit=40");
      const matches = data.matches || [];
      setLiveMatches(matches);
      setSelectedMatchId(matches[0]?.matchId || "");
      setStatus(`Live feed updated (${matches.length})`);
      pushLog(`Loaded ${matches.length} matches from live feed.`);
    } catch (error) {
      setStatus("Live feed failed");
      pushLog(`Live feed error: ${error.message}`);
    } finally {
      setBusy(false);
    }
  };

  const applySelectedMatch = () => {
    const match = liveMatches.find((item) => item.matchId === selectedMatchId);
    if (!match) {
      setStatus("Select a live match first");
      return;
    }

    setContext((prev) => ({
      ...prev,
      tournament: match.seriesName || prev.tournament,
      formatType:
        String(match.formatType || "").toUpperCase().startsWith("ODI")
          ? "ODI"
          : String(match.formatType || "").toUpperCase().startsWith("TEST")
            ? "Test"
            : "T20",
      teamA: match.team1 || prev.teamA,
      teamB: match.team2 || prev.teamB,
      venue: match.venue || prev.venue
    }));

    setWeatherLocation(match.city || match.venue || weatherLocation);

    if (match.team2Runs !== null && match.team2Runs !== undefined) {
      const parsed = parseOvers(match.team2Overs || 0);
      setLiveState((prev) => ({
        ...prev,
        battingSide: "team_b",
        overCount: parsed.overCount,
        ballCount: parsed.ballCount,
        runsScored: Number(match.team2Runs || 0),
        wicketsLost: Number(match.team2Wickets || 0),
        targetRuns: Number(match.team1Runs || 0) + 1
      }));
    } else if (match.team1Runs !== null && match.team1Runs !== undefined) {
      const parsed = parseOvers(match.team1Overs || 0);
      setLiveState((prev) => ({
        ...prev,
        battingSide: "team_a",
        overCount: parsed.overCount,
        ballCount: parsed.ballCount,
        runsScored: Number(match.team1Runs || 0),
        wicketsLost: Number(match.team1Wickets || 0),
        targetRuns: 0
      }));
    }

    setStatus("Live match applied");
    pushLog(
      `Applied ${match.team1} vs ${match.team2} (${match.shortStatus || match.state || "live"}).`
    );
  };

  const syncHistorical = async () => {
    setBusy(true);
    setStatus(`Syncing ${historyPack.toUpperCase()} historical pack...`);
    try {
      const data = await apiPost("/historical/sync", {
        tournament_key: historyPack,
        max_matches: 1800,
        force_download: false
      });
      setStatus("Historical sync done");
      pushLog(data.message || "Historical profiles synced.");
    } catch (error) {
      setStatus("Historical sync failed");
      pushLog(`Historical sync error: ${error.message}`);
    } finally {
      setBusy(false);
    }
  };

  const autofillProfiles = async () => {
    setBusy(true);
    setStatus("Applying historical profile suggestions...");
    try {
      const data = await apiPost("/historical/suggest", {
        team_a: context.teamA,
        team_b: context.teamB,
        venue: context.venue
      });
      setContext((prev) => ({
        ...prev,
        teamARating: data.teamARating,
        teamBRating: data.teamBRating,
        teamARecentWinPct: data.teamARecentWinPct,
        teamBRecentWinPct: data.teamBRecentWinPct,
        teamAH2hWinPct: data.teamAH2hWinPct,
        pitchType: data.pitchType
      }));
      setStatus("Historical profiles applied");
      pushLog(`${data.source || "local"} -> ${data.pitchSummary || "Profile updated."}`);
    } catch (error) {
      setStatus("Autofill failed");
      pushLog(`Autofill error: ${error.message}`);
    } finally {
      setBusy(false);
    }
  };

  const refreshWeather = async () => {
    const location = weatherLocation || context.venue;
    if (!location) {
      setStatus("Set a location first");
      return;
    }
    setBusy(true);
    setStatus(`Refreshing weather for ${location}...`);
    try {
      const data = await apiGet(`/signals/weather?location=${encodeURIComponent(location)}`);
      setContext((prev) => ({
        ...prev,
        weatherCondition: data.condition || prev.weatherCondition,
        humidityPct: data.humidityPct ?? prev.humidityPct
      }));
      setStatus("Weather updated");
      pushLog(
        `Weather ${data.locationName}: ${data.temperatureC}C, humidity ${data.humidityPct}%, rain ${data.rainProbabilityPct}%.`
      );
    } catch (error) {
      setStatus("Weather refresh failed");
      pushLog(`Weather error: ${error.message}`);
    } finally {
      setBusy(false);
    }
  };

  const refreshNews = async () => {
    const query = `${context.teamA} ${context.teamB} ${context.tournament} cricket`;
    setBusy(true);
    setStatus("Refreshing news...");
    try {
      const data = await apiPost("/signals/news", { query, limit: 10 });
      setNews(data.headlines || []);
      setContext((prev) => ({ ...prev, newsNotes: data.signalText || "" }));
      setStatus(`News updated (${(data.headlines || []).length})`);
      pushLog(`News refresh completed with ${(data.headlines || []).length} headlines.`);
    } catch (error) {
      setStatus("News refresh failed");
      pushLog(`News error: ${error.message}`);
    } finally {
      setBusy(false);
    }
  };

  const runPreMatchPrediction = async () => {
    setBusy(true);
    setStatus("Running pre-match model...");
    try {
      const data = await apiPost("/predict/prematch", preMatchPayload());
      setResult({ mode: "prematch", ...data });
      setPrematchProb(Number(data.teamAWinProbability || 0.5));
      setStatus("Pre-match prediction updated");
      pushLog(`Pre-match model: ${data.modelUsed}`);
    } catch (error) {
      setStatus("Pre-match prediction failed");
      pushLog(`Pre-match error: ${error.message}`);
    } finally {
      setBusy(false);
    }
  };

  const runLivePrediction = async () => {
    setBusy(true);
    setStatus("Running live model...");
    try {
      const oversCompleted = Number(liveState.overCount) + Number(liveState.ballCount) / 10;
      const data = await apiPost("/predict/live", {
        context: preMatchPayload(),
        live_state: {
          batting_side: liveState.battingSide,
          overs_completed: oversCompleted,
          runs_scored: Number(liveState.runsScored),
          wickets_lost: Number(liveState.wicketsLost),
          max_overs: Number(liveState.maxOvers),
          target_runs: Number(liveState.targetRuns) > 0 ? Number(liveState.targetRuns) : null,
          recent_run_rate: Number(liveState.recentRunRate),
          momentum_edge: Number(liveState.momentumEdge)
        },
        prematch_team_a_probability: Number(prematchProb)
      });
      setResult({ mode: "live", ...data });
      setStatus("Live prediction updated");
      pushLog(`Live model: ${data.modelUsed}`);
    } catch (error) {
      setStatus("Live prediction failed");
      pushLog(`Live prediction error: ${error.message}`);
    } finally {
      setBusy(false);
    }
  };

  // ── derived values ──
  const teamAProb = result ? (result.teamAWinProbability * 100).toFixed(1) : "50.0";
  const teamBProb = result ? (result.teamBWinProbability * 100).toFixed(1) : "50.0";
  const confidence = result ? (result.confidence * 100).toFixed(1) : "45.0";
  const teamAName = metric(result?.teamA, context.teamA);
  const teamBName = metric(result?.teamB, context.teamB);

  // ── tab content renderers ──
  const renderDataOps = () => (
    <>
      <div className="group">
        <div className="group-header">
          <div className="group-icon">📡</div>
          <h3>Live Feed</h3>
        </div>
        <div className="row">
          <button onClick={refreshLiveFeed}>Refresh Live Feed</button>
          <button onClick={applySelectedMatch}>Apply Match</button>
        </div>
        <select value={selectedMatchId} onChange={(e) => setSelectedMatchId(e.target.value)}>
          <option value="">Select live match</option>
          {liveMatches.map((item) => (
            <option key={item.matchId} value={item.matchId}>
              {item.displayLabel}
            </option>
          ))}
        </select>
      </div>

      <div className="group">
        <div className="group-header">
          <div className="group-icon">📊</div>
          <h3>Historical Data</h3>
        </div>
        <div className="row">
          <select value={historyPack} onChange={(e) => setHistoryPack(e.target.value)}>
            <option value="ipl">IPL</option>
            <option value="bbl">BBL</option>
            <option value="psl">PSL</option>
            <option value="cpl">CPL</option>
            <option value="sa20">SA20</option>
            <option value="ilt20">ILT20</option>
            <option value="wpl">WPL</option>
            <option value="t20i">T20I</option>
          </select>
          <button onClick={syncHistorical}>Sync</button>
          <button onClick={autofillProfiles}>Auto-Fill</button>
        </div>
      </div>

      <div className="group">
        <div className="group-header">
          <div className="group-icon">🌤</div>
          <h3>Weather & News</h3>
        </div>
        <div className="grid">
          <label>Weather Location
            <input value={weatherLocation} onChange={(e) => setWeatherLocation(e.target.value)} />
          </label>
        </div>
        <div className="row" style={{ marginTop: 10 }}>
          <button onClick={refreshWeather}>Refresh Weather</button>
          <button onClick={refreshNews}>Refresh News</button>
        </div>
      </div>
    </>
  );

  const renderMatchSetup = () => (
    <>
      <div className="group">
        <div className="group-header">
          <div className="group-icon">🏟</div>
          <h3>Match Context</h3>
        </div>
        <div className="grid">
          <label>Tournament
            <input value={context.tournament} onChange={(e) => updateContextField("tournament", e.target.value)} />
          </label>
          <label>Format
            <select value={context.formatType} onChange={(e) => updateContextField("formatType", e.target.value)}>
              <option>T20</option><option>ODI</option><option>Test</option>
            </select>
          </label>
          <label>Team A
            <input value={context.teamA} onChange={(e) => updateContextField("teamA", e.target.value)} />
          </label>
          <label>Team B
            <input value={context.teamB} onChange={(e) => updateContextField("teamB", e.target.value)} />
          </label>
          <label>Venue
            <input value={context.venue} onChange={(e) => updateContextField("venue", e.target.value)} />
          </label>
          <label>Home Edge
            <select value={context.homeAdvantage} onChange={(e) => updateContextField("homeAdvantage", Number(e.target.value))}>
              <option value={1}>Team A Home</option><option value={0}>Neutral</option><option value={-1}>Team B Home</option>
            </select>
          </label>
          <label>Toss Winner
            <select value={context.tossWinner} onChange={(e) => updateContextField("tossWinner", e.target.value)}>
              <option value="team_a">Team A</option><option value="team_b">Team B</option>
            </select>
          </label>
          <label>Toss Decision
            <select value={context.tossDecision} onChange={(e) => updateContextField("tossDecision", e.target.value)}>
              <option value="bat">Bat</option><option value="bowl">Bowl</option>
            </select>
          </label>
        </div>
      </div>

      <div className="group">
        <div className="group-header">
          <div className="group-icon">📈</div>
          <h3>Signals & Ratings</h3>
        </div>
        <div className="grid">
          <label>Team A Rating
            <input type="number" value={context.teamARating} onChange={(e) => updateContextField("teamARating", Number(e.target.value))} />
          </label>
          <label>Team B Rating
            <input type="number" value={context.teamBRating} onChange={(e) => updateContextField("teamBRating", Number(e.target.value))} />
          </label>
          <label>Team A Form
            <input type="number" min="0" max="1" step="0.01" value={context.teamARecentWinPct} onChange={(e) => updateContextField("teamARecentWinPct", Number(e.target.value))} />
          </label>
          <label>Team B Form
            <input type="number" min="0" max="1" step="0.01" value={context.teamBRecentWinPct} onChange={(e) => updateContextField("teamBRecentWinPct", Number(e.target.value))} />
          </label>
          <label>Team A H2H
            <input type="number" min="0" max="1" step="0.01" value={context.teamAH2hWinPct} onChange={(e) => updateContextField("teamAH2hWinPct", Number(e.target.value))} />
          </label>
          <label>Pitch
            <select value={context.pitchType} onChange={(e) => updateContextField("pitchType", e.target.value)}>
              <option>batting_friendly</option><option>balanced</option><option>spin_friendly</option><option>pace_friendly</option><option>slow_low</option>
            </select>
          </label>
          <label>Weather
            <select value={context.weatherCondition} onChange={(e) => updateContextField("weatherCondition", e.target.value)}>
              <option>clear</option><option>cloudy</option><option>humid</option><option>overcast</option><option>rain_threat</option>
            </select>
          </label>
          <label>Humidity %
            <input type="number" min="0" max="100" value={context.humidityPct} onChange={(e) => updateContextField("humidityPct", Number(e.target.value))} />
          </label>
        </div>
        <textarea
          rows={4}
          value={context.newsNotes}
          onChange={(e) => updateContextField("newsNotes", e.target.value)}
          placeholder="News signal text for sentiment scoring..."
          style={{ marginTop: 10 }}
        />
        <div className="row" style={{ marginTop: 10 }}>
          <button className="primary" onClick={runPreMatchPrediction}>▶ Run Pre-Match</button>
        </div>
      </div>
    </>
  );

  const renderLiveState = () => (
    <div className="group">
      <div className="group-header">
        <div className="group-icon">⚡</div>
        <h3>Live Match State</h3>
      </div>
      <div className="grid">
        <label>Batting Side
          <select value={liveState.battingSide} onChange={(e) => updateLiveField("battingSide", e.target.value)}>
            <option value="team_a">Team A</option><option value="team_b">Team B</option>
          </select>
        </label>
        <label>Max Overs
          <input type="number" value={liveState.maxOvers} onChange={(e) => updateLiveField("maxOvers", Number(e.target.value))} />
        </label>
        <label>Overs
          <input type="number" value={liveState.overCount} onChange={(e) => updateLiveField("overCount", Number(e.target.value))} />
        </label>
        <label>Balls
          <input type="number" min="0" max="5" value={liveState.ballCount} onChange={(e) => updateLiveField("ballCount", Number(e.target.value))} />
        </label>
        <label>Runs
          <input type="number" value={liveState.runsScored} onChange={(e) => updateLiveField("runsScored", Number(e.target.value))} />
        </label>
        <label>Wickets
          <input type="number" min="0" max="10" value={liveState.wicketsLost} onChange={(e) => updateLiveField("wicketsLost", Number(e.target.value))} />
        </label>
        <label>Target
          <input type="number" value={liveState.targetRuns} onChange={(e) => updateLiveField("targetRuns", Number(e.target.value))} />
        </label>
        <label>Recent RR
          <input type="number" step="0.1" value={liveState.recentRunRate} onChange={(e) => updateLiveField("recentRunRate", Number(e.target.value))} />
        </label>
        <label>Momentum
          <input type="number" min="-1" max="1" step="0.05" value={liveState.momentumEdge} onChange={(e) => updateLiveField("momentumEdge", Number(e.target.value))} />
        </label>
      </div>
      <div className="row" style={{ marginTop: 10 }}>
        <button className="primary" onClick={runLivePrediction}>⚡ Run Live Prediction</button>
      </div>
    </div>
  );

  return (
    <div className="app-shell">
      {/* ── Header ── */}
      <header className="hero">
        <div className="hero-left">
          <h1>CricAnalyst Pro</h1>
          <p>ML prediction engine · Live feeds · Weather & news signals</p>
        </div>
        <span className={`status-badge ${busy ? "busy" : ""}`}>{status}</span>
      </header>

      {/* ── Main Layout ── */}
      <main className="layout">
        {/* ── Left: Tabbed Controls ── */}
        <section className="panel form-panel">
          <div className="tabs">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                className={`tab-btn ${activeTab === tab.key ? "active" : ""}`}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.icon} {tab.label}
              </button>
            ))}
          </div>
          <div className="tab-content">
            {activeTab === "dataops" && renderDataOps()}
            {activeTab === "match" && renderMatchSetup()}
            {activeTab === "live" && renderLiveState()}
          </div>
        </section>

        {/* ── Right: Output ── */}
        <section className="panel output-panel">
          {/* Metrics Row */}
          <div className="metrics">
            <article className="metric-card team-a">
              <div className="metric-label">{teamAName} Win</div>
              <div className="metric-value">{teamAProb}%</div>
            </article>
            <article className="metric-card team-b">
              <div className="metric-label">{teamBName} Win</div>
              <div className="metric-value">{teamBProb}%</div>
            </article>
            <article className="metric-card confidence">
              <div className="metric-label">Confidence</div>
              <div className="metric-value">{confidence}%</div>
            </article>
          </div>

          {/* Probability Bar */}
          <div className="prob-bar-container">
            <div className="prob-bar-labels">
              <span className="prob-bar-team a">{teamAName} {teamAProb}%</span>
              <span className="prob-bar-team b">{teamBProb}% {teamBName}</span>
            </div>
            <div className="prob-bar-track">
              <div
                className="prob-bar-fill"
                style={{ "--prob-a": `${teamAProb}%` }}
              />
            </div>
          </div>

          {/* Charts Grid */}
          <div className="charts-grid">
            <WinDonut
              teamAProb={teamAProb}
              teamBProb={teamBProb}
              teamAName={teamAName}
              teamBName={teamBName}
            />
            <TeamRadar context={context} />
            {result?.keyFactors?.length > 0 && (
              <FactorsBar keyFactors={result.keyFactors} />
            )}
            {Number(liveState.targetRuns) > 0 && (
              <ChaseGauge liveState={liveState} />
            )}
          </div>

          {/* Momentum Chart (full width when visible) */}
          {Number(liveState.overCount) > 0 && (
            <MomentumChart liveState={liveState} />
          )}

          {/* Cards Stack */}
          <div className="stack">
            {/* Prediction Narrative */}
            <div className="card" style={{ flex: "0 1 auto" }}>
              <div className="card-header">
                <span className="card-icon">🎯</span>
                <h3>Prediction Narrative</h3>
              </div>
              <div className="card-body">
                {result ? (
                  <div className="result-body">
                    <p>{result.mode === "live" ? "Live" : "Pre-match"} model output is active.</p>
                    <ul className="key-factors">
                      {(result.keyFactors || []).map((factor, idx) => (
                        <li key={idx} className="factor-pill">{factor}</li>
                      ))}
                    </ul>
                    {result.projectedScore ? (
                      <div className="projected-score">
                        📊 Projected Score: {Number(result.projectedScore).toFixed(0)}
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <p className="empty-state">Run pre-match or live prediction to see model output.</p>
                )}
              </div>
            </div>

            {/* News */}
            <div className="card" style={{ flex: "0 1 auto" }}>
              <div className="card-header">
                <span className="card-icon">📰</span>
                <h3>News Headlines</h3>
              </div>
              <div className="card-body">
                {news.length === 0 ? (
                  <p className="empty-state">No headlines loaded yet.</p>
                ) : (
                  <ul className="news-list">
                    {news.map((item, idx) => (
                      <li key={`${item.link}-${idx}`}>
                        <a href={item.link} target="_blank" rel="noreferrer">
                          {item.title}
                        </a>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            {/* Activity Log */}
            <div className="card" style={{ flex: "1 1 0" }}>
              <div className="card-header">
                <span className="card-icon">📋</span>
                <h3>Activity Log</h3>
              </div>
              <div className="card-body">
                <pre className="log-console">{logs.join("\n")}</pre>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
