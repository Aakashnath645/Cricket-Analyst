from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.predictor import CricketPredictor
from app.data.models import LiveMatchState, MatchContext, PredictionResult
from app.services.historical_data import HistoricalProfilesService
from app.services.live_data import CricbuzzLiveService, LiveMatch
from app.services.news_data import GoogleNewsRssService
from app.services.signals import NewsSignalService, WeatherSignalService
from app.services.weather_data import OpenMeteoWeatherService, WeatherSnapshot


@dataclass
class MetricCard:
    title: QLabel
    value: QLabel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CricAnalyst Pro Desktop")
        self.resize(1420, 860)

        self.predictor = CricketPredictor(model_dir="models")
        self.weather_signal_service = WeatherSignalService()
        self.news_signal_service = NewsSignalService()

        self.historical_service = HistoricalProfilesService(data_dir="data")
        self.live_feed_service = CricbuzzLiveService()
        self.weather_feed_service = OpenMeteoWeatherService()
        self.news_feed_service = GoogleNewsRssService()

        self._live_matches: List[LiveMatch] = []
        self._latest_weather: Optional[WeatherSnapshot] = None
        self._last_context: Optional[MatchContext] = None
        self._last_team_a_probability: float = 0.5

        self._apply_theme()
        self._build_ui()
        self._wire_events()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([510, 880])
        root_layout.addWidget(splitter)
        self.setCentralWidget(root)

    def _build_left_panel(self) -> QWidget:
        container = QFrame()
        container.setObjectName("leftPanel")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(10)

        content_layout.addWidget(self._build_data_ops_group())
        content_layout.addWidget(self._build_match_group())
        content_layout.addWidget(self._build_signal_group())
        content_layout.addWidget(self._build_live_state_group())
        content_layout.addStretch(1)

        scroll.setWidget(content)
        layout.addWidget(scroll)
        return container

    def _build_right_panel(self) -> QWidget:
        container = QFrame()
        container.setObjectName("rightPanel")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(16, 14, 16, 14)
        hero_layout.setSpacing(4)
        title = QLabel("Cricket Intelligence Workbench")
        title.setObjectName("heroTitle")
        subtitle = QLabel(
            "Desktop-first match analysis with historical form, live feeds, weather, pitch tendencies, and news sentiment."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("heroSubtitle")
        self.status_badge = QLabel("Ready")
        self.status_badge.setObjectName("statusBadge")
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        hero_layout.addWidget(self.status_badge, 0, Qt.AlignLeft)
        layout.addWidget(hero)

        cards = QFrame()
        cards_layout = QGridLayout(cards)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setHorizontalSpacing(10)
        cards_layout.setVerticalSpacing(10)

        self.metric_cards: Dict[str, MetricCard] = {}
        self.metric_cards["team_a"] = self._create_metric_card("Team A Win %", "50.0%")
        self.metric_cards["team_b"] = self._create_metric_card("Team B Win %", "50.0%")
        self.metric_cards["confidence"] = self._create_metric_card("Model Confidence", "45.0%")
        self.metric_cards["model"] = self._create_metric_card("Model", "heuristic")
        cards_layout.addWidget(self._card_widget(self.metric_cards["team_a"]), 0, 0)
        cards_layout.addWidget(self._card_widget(self.metric_cards["team_b"]), 0, 1)
        cards_layout.addWidget(self._card_widget(self.metric_cards["confidence"]), 1, 0)
        cards_layout.addWidget(self._card_widget(self.metric_cards["model"]), 1, 1)
        layout.addWidget(cards)

        self.analysis_output = QTextEdit()
        self.analysis_output.setReadOnly(True)
        self.analysis_output.setPlaceholderText("Prediction narrative, key factors, and scenario notes appear here.")
        self.analysis_output.setObjectName("analysisPane")

        self.feed_output = QTextEdit()
        self.feed_output.setReadOnly(True)
        self.feed_output.setPlaceholderText("Feed sync logs appear here.")
        self.feed_output.setObjectName("feedPane")

        self.news_links = QTextBrowser()
        self.news_links.setOpenExternalLinks(True)
        self.news_links.setObjectName("newsPane")
        self.news_links.setPlaceholderText("News headlines with links appear here after refresh.")

        bottom = QSplitter(Qt.Vertical)
        bottom.addWidget(self.analysis_output)
        bottom.addWidget(self.feed_output)
        bottom.addWidget(self.news_links)
        bottom.setSizes([280, 190, 150])
        layout.addWidget(bottom, 1)
        return container

    def _build_data_ops_group(self) -> QGroupBox:
        group = QGroupBox("Live Data & Sync")
        layout = QFormLayout(group)
        layout.setVerticalSpacing(8)

        self.live_match_combo = QComboBox()
        self.live_match_combo.addItem("No live feed loaded")

        self.refresh_live_btn = QPushButton("Refresh Live Feed")
        self.apply_live_btn = QPushButton("Apply Selected Match")

        self.history_tournament_combo = QComboBox()
        self.history_tournament_combo.addItems(["ipl", "bbl", "psl", "cpl", "sa20", "ilt20", "wpl", "t20i"])
        self.sync_history_btn = QPushButton("Sync Historical Data")

        self.weather_location_input = QLineEdit("Mumbai")
        self.refresh_weather_btn = QPushButton("Refresh Weather")
        self.refresh_news_btn = QPushButton("Refresh News")
        self.autofill_btn = QPushButton("Auto-Fill Match Profiles")

        live_buttons = QWidget()
        live_buttons_layout = QHBoxLayout(live_buttons)
        live_buttons_layout.setContentsMargins(0, 0, 0, 0)
        live_buttons_layout.setSpacing(6)
        live_buttons_layout.addWidget(self.refresh_live_btn)
        live_buttons_layout.addWidget(self.apply_live_btn)

        ops_buttons = QWidget()
        ops_buttons_layout = QHBoxLayout(ops_buttons)
        ops_buttons_layout.setContentsMargins(0, 0, 0, 0)
        ops_buttons_layout.setSpacing(6)
        ops_buttons_layout.addWidget(self.sync_history_btn)
        ops_buttons_layout.addWidget(self.autofill_btn)

        signal_buttons = QWidget()
        signal_buttons_layout = QHBoxLayout(signal_buttons)
        signal_buttons_layout.setContentsMargins(0, 0, 0, 0)
        signal_buttons_layout.setSpacing(6)
        signal_buttons_layout.addWidget(self.refresh_weather_btn)
        signal_buttons_layout.addWidget(self.refresh_news_btn)

        layout.addRow("Live matches", self.live_match_combo)
        layout.addRow("", live_buttons)
        layout.addRow("Cricsheet pack", self.history_tournament_combo)
        layout.addRow("", ops_buttons)
        layout.addRow("Weather location", self.weather_location_input)
        layout.addRow("", signal_buttons)
        return group

    def _build_match_group(self) -> QGroupBox:
        group = QGroupBox("Match Context")
        layout = QFormLayout(group)
        layout.setVerticalSpacing(8)

        self.tournament_input = QLineEdit("IPL")
        self.format_combo = QComboBox()
        self.format_combo.addItems(["T20", "ODI", "Test"])
        self.team_a_input = QLineEdit("Mumbai Indians")
        self.team_b_input = QLineEdit("Chennai Super Kings")
        self.venue_input = QLineEdit("Wankhede Stadium")

        self.toss_winner_combo = QComboBox()
        self.toss_winner_combo.addItems(["Team A", "Team B"])
        self.toss_decision_combo = QComboBox()
        self.toss_decision_combo.addItems(["bat", "bowl"])
        self.home_combo = QComboBox()
        self.home_combo.addItems(["Team A Home", "Neutral", "Team B Home"])

        layout.addRow("Tournament", self.tournament_input)
        layout.addRow("Format", self.format_combo)
        layout.addRow("Team A", self.team_a_input)
        layout.addRow("Team B", self.team_b_input)
        layout.addRow("Venue", self.venue_input)
        layout.addRow("Toss winner", self.toss_winner_combo)
        layout.addRow("Toss decision", self.toss_decision_combo)
        layout.addRow("Home edge", self.home_combo)
        return group

    def _build_signal_group(self) -> QGroupBox:
        group = QGroupBox("Signals (Historical + Weather + News)")
        layout = QFormLayout(group)
        layout.setVerticalSpacing(8)

        self.team_a_rating = QSpinBox()
        self.team_a_rating.setRange(900, 2500)
        self.team_a_rating.setValue(1600)
        self.team_b_rating = QSpinBox()
        self.team_b_rating.setRange(900, 2500)
        self.team_b_rating.setValue(1570)

        self.team_a_form = QDoubleSpinBox()
        self.team_a_form.setRange(0.0, 1.0)
        self.team_a_form.setSingleStep(0.01)
        self.team_a_form.setValue(0.56)
        self.team_b_form = QDoubleSpinBox()
        self.team_b_form.setRange(0.0, 1.0)
        self.team_b_form.setSingleStep(0.01)
        self.team_b_form.setValue(0.52)

        self.h2h_input = QDoubleSpinBox()
        self.h2h_input.setRange(0.0, 1.0)
        self.h2h_input.setSingleStep(0.01)
        self.h2h_input.setValue(0.50)

        self.pitch_combo = QComboBox()
        self.pitch_combo.addItems(
            ["batting_friendly", "balanced", "spin_friendly", "pace_friendly", "slow_low"]
        )
        self.weather_combo = QComboBox()
        self.weather_combo.addItems(["clear", "cloudy", "humid", "overcast", "rain_threat"])
        self.humidity_input = QSpinBox()
        self.humidity_input.setRange(10, 100)
        self.humidity_input.setValue(60)

        self.news_notes = QPlainTextEdit()
        self.news_notes.setFixedHeight(110)
        self.news_notes.setPlaceholderText(
            "News signal text appears here. You can edit it manually before prediction."
        )

        self.predict_pre_btn = QPushButton("Run Pre-Match Prediction")

        layout.addRow("Team A rating", self.team_a_rating)
        layout.addRow("Team B rating", self.team_b_rating)
        layout.addRow("Team A recent win %", self.team_a_form)
        layout.addRow("Team B recent win %", self.team_b_form)
        layout.addRow("Team A h2h win %", self.h2h_input)
        layout.addRow("Pitch profile", self.pitch_combo)
        layout.addRow("Weather condition", self.weather_combo)
        layout.addRow("Humidity %", self.humidity_input)
        layout.addRow("News signal notes", self.news_notes)
        layout.addRow("", self.predict_pre_btn)
        return group

    def _build_live_state_group(self) -> QGroupBox:
        group = QGroupBox("Live State")
        layout = QFormLayout(group)
        layout.setVerticalSpacing(8)

        self.live_batting_side = QComboBox()
        self.live_batting_side.addItems(["Team A", "Team B"])
        self.live_max_overs = QDoubleSpinBox()
        self.live_max_overs.setRange(5.0, 100.0)
        self.live_max_overs.setValue(20.0)

        self.live_over_count = QSpinBox()
        self.live_over_count.setRange(0, 100)
        self.live_over_count.setValue(8)
        self.live_ball_count = QSpinBox()
        self.live_ball_count.setRange(0, 5)
        self.live_ball_count.setValue(0)
        overs_widget = QWidget()
        overs_layout = QHBoxLayout(overs_widget)
        overs_layout.setContentsMargins(0, 0, 0, 0)
        overs_layout.setSpacing(6)
        overs_layout.addWidget(self.live_over_count)
        overs_layout.addWidget(QLabel("overs +"))
        overs_layout.addWidget(self.live_ball_count)
        overs_layout.addWidget(QLabel("balls"))
        overs_layout.addStretch(1)

        self.live_runs = QSpinBox()
        self.live_runs.setRange(0, 900)
        self.live_runs.setValue(72)
        self.live_wickets = QSpinBox()
        self.live_wickets.setRange(0, 10)
        self.live_wickets.setValue(2)
        self.live_target = QSpinBox()
        self.live_target.setRange(0, 900)
        self.live_target.setValue(170)
        self.live_recent_rr = QDoubleSpinBox()
        self.live_recent_rr.setRange(0.0, 20.0)
        self.live_recent_rr.setSingleStep(0.1)
        self.live_recent_rr.setValue(8.3)
        self.live_momentum = QDoubleSpinBox()
        self.live_momentum.setRange(-1.0, 1.0)
        self.live_momentum.setSingleStep(0.05)
        self.live_momentum.setValue(0.1)

        self.predict_live_btn = QPushButton("Run Live Prediction")

        layout.addRow("Batting side", self.live_batting_side)
        layout.addRow("Max overs", self.live_max_overs)
        layout.addRow("Overs completed", overs_widget)
        layout.addRow("Runs scored", self.live_runs)
        layout.addRow("Wickets lost", self.live_wickets)
        layout.addRow("Target (0 = first inns)", self.live_target)
        layout.addRow("Recent run rate", self.live_recent_rr)
        layout.addRow("Momentum edge", self.live_momentum)
        layout.addRow("", self.predict_live_btn)
        return group

    def _wire_events(self) -> None:
        self.refresh_live_btn.clicked.connect(self._on_refresh_live_feed)
        self.apply_live_btn.clicked.connect(self._on_apply_live_match)
        self.sync_history_btn.clicked.connect(self._on_sync_history)
        self.autofill_btn.clicked.connect(self._on_autofill_profiles)
        self.refresh_weather_btn.clicked.connect(self._on_refresh_weather)
        self.refresh_news_btn.clicked.connect(self._on_refresh_news)
        self.predict_pre_btn.clicked.connect(self._on_predict_pre_match)
        self.predict_live_btn.clicked.connect(self._on_predict_live)

    def _on_refresh_live_feed(self) -> None:
        self._set_status("Refreshing live feed...")
        try:
            self._live_matches = self.live_feed_service.fetch_matches(limit=40, include_completed=False)
        except Exception as exc:
            self._set_status("Live feed unavailable", is_error=True)
            self._append_feed_log(f"Live feed error: {exc}")
            return

        self.live_match_combo.clear()
        if not self._live_matches:
            self.live_match_combo.addItem("No active/preview matches found")
            self._set_status("No live matches found")
            return

        for match in self._live_matches:
            self.live_match_combo.addItem(match.display_label)
        self._set_status(f"Live feed updated ({len(self._live_matches)} matches)")
        self._append_feed_log(f"Loaded {len(self._live_matches)} matches from Cricbuzz live feed.")

    def _on_apply_live_match(self) -> None:
        if not self._live_matches:
            self._set_status("Load live feed first", is_error=True)
            return
        index = self.live_match_combo.currentIndex()
        if index < 0 or index >= len(self._live_matches):
            self._set_status("Select a valid match", is_error=True)
            return

        match = self._live_matches[index]
        self.team_a_input.setText(match.team1)
        self.team_b_input.setText(match.team2)
        self.venue_input.setText(match.venue)
        self.weather_location_input.setText(match.city or match.venue)
        self.tournament_input.setText(match.series_name)

        format_text = match.format_type.upper()
        if format_text.startswith("T20"):
            self.format_combo.setCurrentText("T20")
            self.live_max_overs.setValue(20.0)
        elif format_text.startswith("ODI"):
            self.format_combo.setCurrentText("ODI")
            self.live_max_overs.setValue(50.0)
        else:
            self.format_combo.setCurrentText("Test")
            self.live_max_overs.setValue(90.0)

        if match.team2_runs is not None:
            self.live_batting_side.setCurrentText("Team B")
            self.live_runs.setValue(int(match.team2_runs))
            self.live_wickets.setValue(int(match.team2_wickets or 0))
            self._set_overs_spinboxes(float(match.team2_overs or 0.0))
            if match.team1_runs is not None:
                self.live_target.setValue(int(match.team1_runs) + 1)
        elif match.team1_runs is not None:
            self.live_batting_side.setCurrentText("Team A")
            self.live_runs.setValue(int(match.team1_runs))
            self.live_wickets.setValue(int(match.team1_wickets or 0))
            self._set_overs_spinboxes(float(match.team1_overs or 0.0))
            self.live_target.setValue(0)

        self._append_feed_log(
            f"Applied match: {match.series_name} | {match.team1} {match.team1_score} vs "
            f"{match.team2} {match.team2_score}"
        )
        self._set_status("Live match context applied")

    def _on_sync_history(self) -> None:
        key = self.history_tournament_combo.currentText().strip().lower()
        self._set_status(f"Syncing Cricsheet {key.upper()} archive...")
        try:
            message = self.historical_service.sync_from_cricsheet(tournament_key=key, max_matches=1800)
            self._append_feed_log(message)
            self._set_status("Historical profiles synced")
        except Exception as exc:
            self._append_feed_log(f"Historical sync error: {exc}")
            self._set_status("Historical sync failed", is_error=True)

    def _on_autofill_profiles(self) -> None:
        team_a = self.team_a_input.text().strip()
        team_b = self.team_b_input.text().strip()
        venue = self.venue_input.text().strip()
        if not team_a or not team_b:
            self._set_status("Enter team names before auto-fill", is_error=True)
            return

        suggestion = self.historical_service.suggest_for_match(team_a=team_a, team_b=team_b, venue=venue)
        self.team_a_rating.setValue(int(round(suggestion.team_a_rating)))
        self.team_b_rating.setValue(int(round(suggestion.team_b_rating)))
        self.team_a_form.setValue(float(suggestion.team_a_recent_win_pct))
        self.team_b_form.setValue(float(suggestion.team_b_recent_win_pct))
        self.h2h_input.setValue(float(suggestion.team_a_h2h_win_pct))
        self.pitch_combo.setCurrentText(suggestion.pitch_type)

        self._append_feed_log(f"Profile source: {suggestion.source}")
        self._append_feed_log(suggestion.pitch_summary)
        self._set_status("Historical profiles applied")

    def _on_refresh_weather(self) -> None:
        location = self.weather_location_input.text().strip() or self.venue_input.text().strip()
        if not location:
            self._set_status("Enter a location for weather refresh", is_error=True)
            return
        self._set_status(f"Refreshing weather for {location}...")

        try:
            snapshot = self.weather_feed_service.fetch_current(location)
        except Exception as exc:
            self._append_feed_log(f"Weather API error: {exc}")
            self._set_status("Weather refresh failed", is_error=True)
            return

        if snapshot is None:
            self._set_status("Location not found for weather", is_error=True)
            return

        self._latest_weather = snapshot
        self.humidity_input.setValue(int(snapshot.humidity_pct))
        self.weather_location_input.setText(snapshot.location_name)
        self.weather_combo.setCurrentText(snapshot.condition)
        self._append_feed_log(
            f"Weather: {snapshot.location_name} | {snapshot.temperature_c:.1f}C, "
            f"humidity {snapshot.humidity_pct}%, rain risk {snapshot.rain_probability_pct}%."
        )
        self._set_status("Weather signal updated")

    def _on_refresh_news(self) -> None:
        query = f"{self.team_a_input.text()} {self.team_b_input.text()} {self.tournament_input.text()} cricket"
        self._set_status("Refreshing news feed...")
        try:
            headlines = self.news_feed_service.fetch(query=query, limit=10)
        except Exception as exc:
            self._append_feed_log(f"News feed error: {exc}")
            self._set_status("News refresh failed", is_error=True)
            return

        if not headlines:
            self.news_links.setPlainText("No headlines found for current query.")
            self._set_status("No recent headlines found")
            return

        self.news_links.clear()
        for item in headlines:
            self.news_links.append(f'<a href="{item.link}">{item.title}</a><br>')
        news_text = GoogleNewsRssService.to_signal_text(headlines)
        self.news_notes.setPlainText(news_text)
        self._append_feed_log(f"News headlines loaded: {len(headlines)}")
        self._set_status("News signal updated")

    def _on_predict_pre_match(self) -> None:
        context = self._build_context()
        result = self.predictor.predict_prematch(context)
        self._last_context = context
        self._last_team_a_probability = result.team_a_win_probability

        self._apply_prediction_to_cards(context.team_a, context.team_b, result)
        lines = [
            f"{context.team_a}: {result.team_a_win_probability:.1%}",
            f"{context.team_b}: {result.team_b_win_probability:.1%}",
            f"Confidence: {result.confidence:.1%}",
            f"Model: {result.model_used}",
            "",
            "Key Factors:",
        ]
        lines.extend(f"- {factor}" for factor in result.key_factors)
        lines.append("")
        lines.append(self.news_signal_service.summarize(context.news_edge))
        if self._latest_weather:
            lines.append(
                f"Weather live signal: {self._latest_weather.condition}, "
                f"{self._latest_weather.temperature_c:.1f}C, rain {self._latest_weather.rain_probability_pct}%."
            )
        self.analysis_output.setPlainText("\n".join(lines))
        self._set_status("Pre-match prediction updated")

    def _on_predict_live(self) -> None:
        context = self._last_context or self._build_context()
        overs_notation = self.live_over_count.value() + (self.live_ball_count.value() / 10.0)
        target_value = self.live_target.value()
        live_state = LiveMatchState(
            batting_side="team_a" if self.live_batting_side.currentText() == "Team A" else "team_b",
            overs_completed=overs_notation,
            runs_scored=self.live_runs.value(),
            wickets_lost=self.live_wickets.value(),
            max_overs=self.live_max_overs.value(),
            target_runs=target_value if target_value > 0 else None,
            recent_run_rate=self.live_recent_rr.value(),
            momentum_edge=self.live_momentum.value(),
        )

        result = self.predictor.predict_live(
            ctx=context,
            live=live_state,
            prematch_team_a_probability=self._last_team_a_probability,
        )
        simulation = self.predictor.simulator.estimate(live_state, iterations=900)
        self._apply_prediction_to_cards(context.team_a, context.team_b, result)

        lines = [
            f"{context.team_a}: {result.team_a_win_probability:.1%}",
            f"{context.team_b}: {result.team_b_win_probability:.1%}",
            f"Confidence: {result.confidence:.1%}",
            f"Model: {result.model_used}",
            f"Projected score from current state: {simulation.projected_score:.0f}",
            "",
            "Key Factors:",
        ]
        lines.extend(f"- {factor}" for factor in result.key_factors)
        self.analysis_output.setPlainText("\n".join(lines))
        self._set_status("Live prediction updated")

    def _build_context(self) -> MatchContext:
        weather_signal = self.weather_signal_service.estimate(
            condition=self.weather_combo.currentText(),
            humidity_pct=self.humidity_input.value(),
        )
        team_a = self.team_a_input.text().strip() or "Team A"
        team_b = self.team_b_input.text().strip() or "Team B"
        news_edge = self.news_signal_service.estimate_edge(
            self.news_notes.toPlainText(), team_a=team_a, team_b=team_b
        )
        home_advantage = {
            "Team A Home": 1.0,
            "Neutral": 0.0,
            "Team B Home": -1.0,
        }[self.home_combo.currentText()]

        toss_winner = "team_a" if self.toss_winner_combo.currentText() == "Team A" else "team_b"
        return MatchContext(
            tournament=self.tournament_input.text().strip() or "League",
            format_type=self.format_combo.currentText(),
            team_a=team_a,
            team_b=team_b,
            venue=self.venue_input.text().strip() or "Unknown Venue",
            team_a_rating=float(self.team_a_rating.value()),
            team_b_rating=float(self.team_b_rating.value()),
            team_a_recent_win_pct=self.team_a_form.value(),
            team_b_recent_win_pct=self.team_b_form.value(),
            team_a_h2h_win_pct=self.h2h_input.value(),
            toss_winner=toss_winner,
            toss_decision=self.toss_decision_combo.currentText(),
            pitch_type=self.pitch_combo.currentText(),
            weather_condition=weather_signal.condition,
            weather_rain_risk=weather_signal.rain_risk,
            home_advantage=home_advantage,
            news_edge=news_edge,
        )

    def _set_overs_spinboxes(self, overs: float) -> None:
        whole = int(overs)
        balls = int(round((overs - whole) * 10))
        if balls >= 6:
            whole += balls // 6
            balls = balls % 6
        self.live_over_count.setValue(whole)
        self.live_ball_count.setValue(max(0, min(balls, 5)))

    def _apply_prediction_to_cards(
        self,
        team_a_name: str,
        team_b_name: str,
        result: PredictionResult,
    ) -> None:
        self.metric_cards["team_a"].title.setText(f"{team_a_name} Win %")
        self.metric_cards["team_b"].title.setText(f"{team_b_name} Win %")
        self.metric_cards["team_a"].value.setText(f"{result.team_a_win_probability:.1%}")
        self.metric_cards["team_b"].value.setText(f"{result.team_b_win_probability:.1%}")
        self.metric_cards["confidence"].value.setText(f"{result.confidence:.1%}")
        self.metric_cards["model"].value.setText(result.model_used)

    def _set_status(self, text: str, is_error: bool = False) -> None:
        self.status_badge.setText(text)
        if is_error:
            self.status_badge.setProperty("status", "error")
        else:
            self.status_badge.setProperty("status", "ok")
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

    def _append_feed_log(self, line: str) -> None:
        current = self.feed_output.toPlainText().strip()
        next_text = f"{current}\n{line}" if current else line
        self.feed_output.setPlainText(next_text)
        self.feed_output.verticalScrollBar().setValue(self.feed_output.verticalScrollBar().maximum())

    def _create_metric_card(self, title: str, value: str) -> MetricCard:
        return MetricCard(title=QLabel(title), value=QLabel(value))

    def _card_widget(self, card: MetricCard) -> QWidget:
        frame = QFrame()
        frame.setObjectName("metricCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        card.title.setObjectName("metricTitle")
        card.value.setObjectName("metricValue")
        layout.addWidget(card.title)
        layout.addWidget(card.value)
        return frame

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            * {
                font-family: "Segoe UI Variable Text", "Bahnschrift", "Segoe UI", sans-serif;
                color: #1f2a37;
            }
            QMainWindow, QWidget {
                background: #eef2f7;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #d9e2ec;
                border-radius: 10px;
                margin-top: 12px;
                padding: 8px;
                font-weight: 700;
            }
            QGroupBox::title {
                left: 12px;
                top: -8px;
                padding: 0 4px;
                background: #eef2f7;
                color: #334e68;
            }
            #leftPanel, #rightPanel {
                background: transparent;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit, QTextBrowser {
                background: #ffffff;
                border: 1px solid #c6d2df;
                border-radius: 8px;
                padding: 6px;
                selection-background-color: #2f80ed;
            }
            QPushButton {
                background: #165dff;
                border: none;
                color: #ffffff;
                border-radius: 8px;
                padding: 7px 10px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #0f4bd4;
            }
            #heroCard {
                border-radius: 14px;
                background: qlineargradient(
                    spread:pad, x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0e4a7b, stop:1 #157f77
                );
            }
            #heroTitle {
                color: #ffffff;
                font-size: 24px;
                font-weight: 800;
            }
            #heroSubtitle {
                color: #d7e9ff;
                font-size: 13px;
            }
            #statusBadge {
                background: rgba(255, 255, 255, 0.2);
                color: #ffffff;
                border-radius: 12px;
                padding: 4px 10px;
                font-weight: 700;
            }
            #statusBadge[status="error"] {
                background: rgba(220, 53, 69, 0.85);
            }
            #statusBadge[status="ok"] {
                background: rgba(20, 160, 80, 0.85);
            }
            #metricCard {
                background: #ffffff;
                border: 1px solid #d3dde7;
                border-radius: 12px;
            }
            #metricTitle {
                color: #52606d;
                font-size: 12px;
                font-weight: 700;
            }
            #metricValue {
                color: #102a43;
                font-size: 22px;
                font-weight: 800;
            }
            #analysisPane, #feedPane, #newsPane {
                background: #ffffff;
                border: 1px solid #d3dde7;
                border-radius: 10px;
                padding: 8px;
            }
            """
        )
