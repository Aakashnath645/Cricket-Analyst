"""Train cricket prediction models on real or synthetic data.

Usage:
    # Train on real Cricsheet data (recommended)
    python -m scripts.train_model --from-cricsheet --tournament ipl

    # Train on existing CSVs
    python -m scripts.train_model --data-dir data --model-dir models

    # Force regenerate synthetic data (legacy)
    python -m scripts.train_model --force-generate --prematch-rows 6000 --live-rows 10000
"""
from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split

from app.core.feature_engineering import LIVE_FEATURES, PREMATCH_FEATURES, FeatureEngineer
from app.data.models import LiveMatchState, MatchContext
from scripts.generate_sample_data import generate_from_cricsheet, generate_live_rows, generate_prematch_rows


def _build_prematch_arrays(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    engineer = FeatureEngineer()
    feature_rows = []
    labels = []

    for row in df.to_dict(orient="records"):
        ctx = MatchContext(
            tournament=str(row["tournament"]),
            format_type=str(row["format_type"]),
            team_a=str(row["team_a"]),
            team_b=str(row["team_b"]),
            venue=str(row["venue"]),
            team_a_rating=float(row["team_a_rating"]),
            team_b_rating=float(row["team_b_rating"]),
            team_a_recent_win_pct=float(row["team_a_recent_win_pct"]),
            team_b_recent_win_pct=float(row["team_b_recent_win_pct"]),
            team_a_h2h_win_pct=float(row["team_a_h2h_win_pct"]),
            toss_winner=str(row["toss_winner"]),
            toss_decision=str(row["toss_decision"]),
            pitch_type=str(row["pitch_type"]),
            weather_condition=str(row["weather_condition"]),
            weather_rain_risk=float(row.get("weather_rain_risk", 0.1)),
            home_advantage=float(row["home_advantage"]),
            news_edge=float(row.get("news_edge", 0.0)),
            venue_avg_score=float(row.get("venue_avg_score", 160.0)),
            venue_chase_win_pct=float(row.get("venue_chase_win_pct", 0.5)),
            venue_boundary_pct=float(row.get("venue_boundary_pct", 0.45)),
            dew_factor=float(row.get("dew_factor", 0.0)),
        )
        feature_rows.append(engineer.build_prematch_features(ctx))
        labels.append(int(row["team_a_won"]))

    return np.array(feature_rows), np.array(labels)


def _build_live_arrays(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    engineer = FeatureEngineer()
    feature_rows = []
    labels = []

    for row in df.to_dict(orient="records"):
        ctx = MatchContext(
            tournament=str(row["tournament"]),
            format_type=str(row["format_type"]),
            team_a=str(row["team_a"]),
            team_b=str(row["team_b"]),
            venue=str(row["venue"]),
            team_a_rating=float(row["team_a_rating"]),
            team_b_rating=float(row["team_b_rating"]),
            team_a_recent_win_pct=float(row["team_a_recent_win_pct"]),
            team_b_recent_win_pct=float(row["team_b_recent_win_pct"]),
            team_a_h2h_win_pct=float(row["team_a_h2h_win_pct"]),
            toss_winner=str(row["toss_winner"]),
            toss_decision=str(row["toss_decision"]),
            pitch_type=str(row["pitch_type"]),
            weather_condition=str(row["weather_condition"]),
            weather_rain_risk=float(row.get("weather_rain_risk", 0.1)),
            home_advantage=float(row["home_advantage"]),
            news_edge=float(row.get("news_edge", 0.0)),
            venue_avg_score=float(row.get("venue_avg_score", 160.0)),
            venue_chase_win_pct=float(row.get("venue_chase_win_pct", 0.5)),
            venue_boundary_pct=float(row.get("venue_boundary_pct", 0.45)),
            dew_factor=float(row.get("dew_factor", 0.0)),
        )

        target_val = row.get("target_runs", "")
        target_runs = None
        if target_val != "" and not pd.isna(target_val):
            target_runs = int(target_val)

        live = LiveMatchState(
            batting_side=str(row["batting_side"]),
            overs_completed=float(row["overs_completed"]),
            runs_scored=int(row["runs_scored"]),
            wickets_lost=int(row["wickets_lost"]),
            max_overs=float(row["max_overs"]),
            target_runs=target_runs,
            recent_run_rate=float(row["recent_run_rate"]),
            momentum_edge=float(row["momentum_edge"]),
        )

        feature_rows.append(
            engineer.build_live_features(
                ctx=ctx,
                live=live,
                prematch_team_a_probability=float(row["prematch_team_a_probability"]),
            )
        )
        labels.append(int(row["batting_side_wins"]))

    return np.array(feature_rows), np.array(labels)


def _train_model(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    model_name: str,
) -> tuple[object, dict[str, float]]:
    """Train a GradientBoosting model with calibration and cross-validation."""

    print(f"\n{'='*50}")
    print(f"Training: {model_name}")
    print(f"  Samples: {len(y)} | Features: {X.shape[1]}")
    print(f"  Class balance: {y.mean():.1%} positive")
    print(f"{'='*50}")

    # Holdout split for final evaluation
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y,
    )

    # Train GradientBoosting
    gb = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.85,
        min_samples_leaf=8,
        min_samples_split=12,
        max_features="sqrt",
        random_state=42,
    )
    gb.fit(X_train, y_train)

    # Calibrate probabilities
    calibrated = CalibratedClassifierCV(gb, cv=5, method="isotonic")
    calibrated.fit(X_train, y_train)

    # Evaluate on holdout
    prob = calibrated.predict_proba(X_test)[:, 1]
    pred = calibrated.predict(X_test)

    metrics = {
        "accuracy": float(accuracy_score(y_test, pred)),
        "roc_auc": float(roc_auc_score(y_test, prob)),
        "brier": float(brier_score_loss(y_test, prob)),
        "log_loss": float(log_loss(y_test, prob)),
    }

    # Cross-validation metrics
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_probs = cross_val_predict(gb, X, y, cv=cv, method="predict_proba")[:, 1]
    cv_preds = (cv_probs >= 0.5).astype(int)
    metrics["cv_accuracy"] = float(accuracy_score(y, cv_preds))
    metrics["cv_roc_auc"] = float(roc_auc_score(y, cv_probs))
    metrics["cv_brier"] = float(brier_score_loss(y, cv_probs))

    print(f"\n  Holdout metrics:")
    for key in ["accuracy", "roc_auc", "brier", "log_loss"]:
        print(f"    {key}: {metrics[key]:.4f}")
    print(f"\n  5-fold CV metrics:")
    for key in ["cv_accuracy", "cv_roc_auc", "cv_brier"]:
        print(f"    {key}: {metrics[key]:.4f}")

    # Feature importance
    importance = gb.feature_importances_
    ranked = sorted(zip(feature_names, importance), key=lambda t: t[1], reverse=True)
    print(f"\n  Top features:")
    for name, imp in ranked[:8]:
        print(f"    {name}: {imp:.4f}")

    return calibrated, metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Train cricket prediction models.")
    parser.add_argument("--data-dir", type=str, default="data")
    parser.add_argument("--model-dir", type=str, default="models")
    parser.add_argument("--from-cricsheet", action="store_true",
                        help="Generate real data from Cricsheet before training")
    parser.add_argument("--tournament", type=str, default="ipl")
    parser.add_argument("--max-matches", type=int, default=2000)
    parser.add_argument("--prematch-rows", type=int, default=6000)
    parser.add_argument("--live-rows", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--force-generate", action="store_true")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    model_dir = Path(args.model_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    prematch_path = data_dir / "historical_matches.csv"
    live_path = data_dir / "live_states.csv"

    if args.from_cricsheet:
        print("Generating training data from Cricsheet archives...")
        prematch_df, live_df = generate_from_cricsheet(
            data_dir=data_dir,
            tournament_key=args.tournament,
            max_matches=args.max_matches,
        )
        prematch_df.to_csv(prematch_path, index=False)
        live_df.to_csv(live_path, index=False)
    elif args.force_generate or not prematch_path.exists() or not live_path.exists():
        prematch_df = generate_prematch_rows(args.prematch_rows, args.seed)
        live_df = generate_live_rows(args.live_rows, args.seed)
        prematch_df.to_csv(prematch_path, index=False)
        live_df.to_csv(live_path, index=False)
        print("Generated synthetic datasets.")
    else:
        prematch_df = pd.read_csv(prematch_path)
        live_df = pd.read_csv(live_path)

    # Build feature arrays
    print("\nBuilding pre-match feature arrays...")
    X_pre, y_pre = _build_prematch_arrays(prematch_df)

    print("Building live feature arrays...")
    X_live, y_live = _build_live_arrays(live_df)

    # Train models
    prematch_model, prematch_metrics = _train_model(
        X_pre, y_pre, PREMATCH_FEATURES, "Pre-Match Predictor",
    )
    live_model, live_metrics = _train_model(
        X_live, y_live, LIVE_FEATURES, "Live Match Predictor",
    )

    # Save
    joblib.dump(prematch_model, model_dir / "prematch_model.joblib")
    joblib.dump(live_model, model_dir / "live_model.joblib")
    joblib.dump(PREMATCH_FEATURES, model_dir / "prematch_features.joblib")
    joblib.dump(LIVE_FEATURES, model_dir / "live_features.joblib")

    print(f"\n{'='*50}")
    print(f"Models saved to: {model_dir.resolve()}")
    print(f"{'='*50}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
