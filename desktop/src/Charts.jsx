import React, { useMemo } from "react";
import {
  PieChart, Pie, Cell,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  AreaChart, Area,
  ResponsiveContainer,
} from "recharts";

/* ── Palette ── */
const WIN_A  = "#00dcc8";
const WIN_B  = "#f97316";
const ACCENT = "#3b82f6";
const DIM    = "#556680";
const GLASS  = "rgba(20, 28, 50, 0.55)";
const BORDER = "rgba(80, 120, 180, 0.15)";
const INK    = "#e8edf4";
const MUTED  = "#8899b0";

/* ── Custom Tooltip ── */
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      {label && <div className="chart-tooltip-label">{label}</div>}
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color || INK }}>
          {p.name}: <strong>{typeof p.value === "number" ? p.value.toFixed(1) : p.value}</strong>
        </div>
      ))}
    </div>
  );
}

/* ════════════════════════════════════
   1. WIN PROBABILITY DONUT
   ════════════════════════════════════ */
export function WinDonut({ teamAProb, teamBProb, teamAName, teamBName }) {
  const data = [
    { name: teamAName, value: Number(teamAProb) },
    { name: teamBName, value: Number(teamBProb) },
  ];
  const colors = [WIN_A, WIN_B];

  return (
    <div className="chart-card">
      <div className="chart-title">Win Probability</div>
      <div className="chart-wrap donut-wrap">
        <ResponsiveContainer width="100%" height={130}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={38}
              outerRadius={58}
              paddingAngle={3}
              dataKey="value"
              stroke="none"
              animationDuration={800}
              animationEasing="ease-out"
            >
              {data.map((_, i) => (
                <Cell key={i} fill={colors[i]} />
              ))}
            </Pie>
            <Tooltip content={<ChartTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="donut-center">
          <span className="donut-vs">VS</span>
        </div>
      </div>
      <div className="donut-legend">
        <span style={{ color: WIN_A }}>● {teamAName} {teamAProb}%</span>
        <span style={{ color: WIN_B }}>● {teamBName} {teamBProb}%</span>
      </div>
    </div>
  );
}

/* ════════════════════════════════════
   2. TEAM COMPARISON RADAR
   ════════════════════════════════════ */
export function TeamRadar({ context }) {
  const data = useMemo(() => [
    {
      stat: "Rating",
      teamA: normalize(context.teamARating, 1000, 2200),
      teamB: normalize(context.teamBRating, 1000, 2200),
    },
    {
      stat: "Form",
      teamA: (context.teamARecentWinPct * 100),
      teamB: (context.teamBRecentWinPct * 100),
    },
    {
      stat: "H2H",
      teamA: (context.teamAH2hWinPct * 100),
      teamB: ((1 - context.teamAH2hWinPct) * 100),
    },
    {
      stat: "Home Edge",
      teamA: context.homeAdvantage >= 0 ? (context.homeAdvantage * 100) : 0,
      teamB: context.homeAdvantage < 0 ? (Math.abs(context.homeAdvantage) * 100) : 0,
    },
    {
      stat: "Toss",
      teamA: context.tossWinner === "team_a" ? 80 : 20,
      teamB: context.tossWinner === "team_b" ? 80 : 20,
    },
  ], [context]);

  return (
    <div className="chart-card">
      <div className="chart-title">Team Comparison</div>
      <div className="chart-wrap">
        <ResponsiveContainer width="100%" height={150}>
          <RadarChart data={data} cx="50%" cy="50%" outerRadius="65%">
            <PolarGrid stroke={BORDER} />
            <PolarAngleAxis
              dataKey="stat"
              tick={{ fill: MUTED, fontSize: 10, fontWeight: 600 }}
            />
            <PolarRadiusAxis
              domain={[0, 100]}
              tick={false}
              axisLine={false}
            />
            <Radar
              name={context.teamA}
              dataKey="teamA"
              stroke={WIN_A}
              fill={WIN_A}
              fillOpacity={0.15}
              strokeWidth={2}
              animationDuration={600}
            />
            <Radar
              name={context.teamB}
              dataKey="teamB"
              stroke={WIN_B}
              fill={WIN_B}
              fillOpacity={0.15}
              strokeWidth={2}
              animationDuration={600}
            />
            <Tooltip content={<ChartTooltip />} />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <div className="donut-legend">
        <span style={{ color: WIN_A }}>● {context.teamA}</span>
        <span style={{ color: WIN_B }}>● {context.teamB}</span>
      </div>
    </div>
  );
}

/* ════════════════════════════════════
   3. KEY FACTORS BAR CHART
   ════════════════════════════════════ */
export function FactorsBar({ keyFactors }) {
  if (!keyFactors?.length) return null;

  const data = keyFactors.map((f, i) => {
    // Parse contribution value if present, e.g. "rating_diff (+0.34)"
    const match = f.match(/\(([+-]?\d+\.?\d*)\)/);
    const value = match ? Math.abs(parseFloat(match[1])) : (keyFactors.length - i) * 0.3;
    const label = f.replace(/\s*\([^)]*\)/, "").trim();
    const isPositive = match ? parseFloat(match[1]) >= 0 : true;
    return { label, value, isPositive };
  });

  return (
    <div className="chart-card">
      <div className="chart-title">Key Prediction Factors</div>
      <div className="chart-wrap">
        <ResponsiveContainer width="100%" height={Math.max(100, data.length * 28)}>
          <BarChart data={data} layout="vertical" margin={{ left: 10, right: 16, top: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={BORDER} horizontal={false} />
            <XAxis type="number" tick={{ fill: MUTED, fontSize: 10 }} axisLine={false} />
            <YAxis
              type="category"
              dataKey="label"
              width={120}
              tick={{ fill: INK, fontSize: 11, fontWeight: 500 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<ChartTooltip />} />
            <Bar
              dataKey="value"
              name="Impact"
              radius={[0, 6, 6, 0]}
              animationDuration={700}
            >
              {data.map((entry, i) => (
                <Cell key={i} fill={entry.isPositive ? WIN_A : WIN_B} fillOpacity={0.85} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/* ════════════════════════════════════
   4. LIVE CHASE GAUGE
   ════════════════════════════════════ */
export function ChaseGauge({ liveState }) {
  const target = Number(liveState.targetRuns) || 0;
  const scored = Number(liveState.runsScored) || 0;
  const remaining = Math.max(target - scored, 0);
  const oversUsed = Number(liveState.overCount) + Number(liveState.ballCount) / 6;
  const oversTotal = Number(liveState.maxOvers) || 20;
  const oversLeft = Math.max(oversTotal - oversUsed, 0);
  const requiredRR = oversLeft > 0 ? (remaining * 6) / (oversLeft * 6) : 0;
  const currentRR = oversUsed > 0 ? scored / oversUsed : 0;

  if (target <= 0) return null;

  const progressPct = Math.min((scored / target) * 100, 100);

  const gaugeData = [
    { name: "Scored", value: scored },
    { name: "Remaining", value: remaining },
  ];

  return (
    <div className="chart-card">
      <div className="chart-title">Chase Progress</div>
      <div className="chart-wrap donut-wrap">
        <ResponsiveContainer width="100%" height={120}>
          <PieChart>
            <Pie
              data={gaugeData}
              cx="50%"
              cy="50%"
              startAngle={210}
              endAngle={-30}
              innerRadius={36}
              outerRadius={54}
              paddingAngle={2}
              dataKey="value"
              stroke="none"
              animationDuration={700}
            >
              <Cell fill={WIN_A} />
              <Cell fill="rgba(255,255,255,0.06)" />
            </Pie>
            <Tooltip content={<ChartTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="donut-center">
          <span className="donut-big">{scored}</span>
          <span className="donut-sub">/ {target}</span>
        </div>
      </div>
      <div className="chase-stats">
        <div className="chase-stat">
          <span className="chase-label">Current RR</span>
          <span className="chase-value" style={{ color: WIN_A }}>{currentRR.toFixed(1)}</span>
        </div>
        <div className="chase-stat">
          <span className="chase-label">Required RR</span>
          <span className="chase-value" style={{ color: requiredRR > currentRR * 1.3 ? WIN_B : ACCENT }}>{requiredRR.toFixed(1)}</span>
        </div>
        <div className="chase-stat">
          <span className="chase-label">Overs Left</span>
          <span className="chase-value">{oversLeft.toFixed(1)}</span>
        </div>
        <div className="chase-stat">
          <span className="chase-label">Wickets</span>
          <span className="chase-value">{10 - Number(liveState.wicketsLost)}/{10}</span>
        </div>
      </div>
    </div>
  );
}

/* ════════════════════════════════════
   5. INNINGS MOMENTUM AREA
   ════════════════════════════════════ */
export function MomentumChart({ liveState }) {
  const oversUsed = Number(liveState.overCount) + Number(liveState.ballCount) / 6;
  const maxOvers = Number(liveState.maxOvers) || 20;
  const scored = Number(liveState.runsScored) || 0;
  const target = Number(liveState.targetRuns) || 0;
  const recentRR = Number(liveState.recentRunRate) || 0;

  if (oversUsed <= 0) return null;

  // Build projected trajectory from current state
  const currentRR = scored / oversUsed;
  const points = [];

  for (let o = 0; o <= maxOvers; o++) {
    if (o <= oversUsed) {
      // Approximate actual progression (linear from 0 to current)
      const pct = o / oversUsed;
      points.push({
        over: o,
        runs: Math.round(scored * pct),
        projected: null,
        target: target > 0 ? Math.round((target / maxOvers) * o) : null,
      });
    } else {
      // Project forward using recent run rate
      const extraOvers = o - oversUsed;
      const projectedRuns = Math.round(scored + recentRR * extraOvers);
      points.push({
        over: o,
        runs: null,
        projected: projectedRuns,
        target: target > 0 ? Math.round((target / maxOvers) * o) : null,
      });
    }
  }

  return (
    <div className="chart-card">
      <div className="chart-title">Innings Momentum</div>
      <div className="chart-wrap">
        <ResponsiveContainer width="100%" height={130}>
          <AreaChart data={points} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
            <defs>
              <linearGradient id="gradA" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={WIN_A} stopOpacity={0.3} />
                <stop offset="100%" stopColor={WIN_A} stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="gradP" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={ACCENT} stopOpacity={0.2} />
                <stop offset="100%" stopColor={ACCENT} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
            <XAxis
              dataKey="over"
              tick={{ fill: MUTED, fontSize: 10 }}
              axisLine={{ stroke: BORDER }}
              label={{ value: "Overs", position: "insideBottomRight", fill: DIM, fontSize: 10, offset: -2 }}
            />
            <YAxis
              tick={{ fill: MUTED, fontSize: 10 }}
              axisLine={{ stroke: BORDER }}
              width={35}
            />
            <Tooltip content={<ChartTooltip />} />
            <Area
              type="monotone"
              dataKey="runs"
              name="Actual Runs"
              stroke={WIN_A}
              fill="url(#gradA)"
              strokeWidth={2}
              connectNulls={false}
              dot={false}
              animationDuration={600}
            />
            <Area
              type="monotone"
              dataKey="projected"
              name="Projected"
              stroke={ACCENT}
              fill="url(#gradP)"
              strokeWidth={2}
              strokeDasharray="6 3"
              connectNulls={false}
              dot={false}
              animationDuration={600}
            />
            {target > 0 && (
              <Area
                type="monotone"
                dataKey="target"
                name="Target Pace"
                stroke={WIN_B}
                fill="none"
                strokeWidth={1.5}
                strokeDasharray="4 4"
                connectNulls={false}
                dot={false}
                animationDuration={600}
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="donut-legend" style={{ marginTop: 6 }}>
        <span style={{ color: WIN_A }}>● Actual</span>
        <span style={{ color: ACCENT }}>● Projected</span>
        {target > 0 && <span style={{ color: WIN_B }}>● Target Pace</span>}
      </div>
    </div>
  );
}

/* ── Helpers ── */
function normalize(val, min, max) {
  return Math.min(100, Math.max(0, ((val - min) / (max - min)) * 100));
}
