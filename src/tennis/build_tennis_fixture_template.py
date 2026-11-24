"""
Build a tennis fixture template from approved Kalshi tennis candidates.

Input:
- data/processed/tennis_market_candidates.csv

Output:
- data/processed/tennis_fixtures_template.csv

This script does not make network requests.
It does not modify the input file.
"""

from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BASE_DIR / "data" / "processed"

CANDIDATES_PATH = PROCESSED_DIR / "tennis_market_candidates.csv"
OUTPUT_PATH = PROCESSED_DIR / "tennis_fixtures_template.csv"


def main():
    candidates = pd.read_csv(CANDIDATES_PATH)

    print("=" * 60)
    print("TENNIS FIXTURE TEMPLATE BUILDER")
    print("=" * 60)
    print(f"Reading: {CANDIDATES_PATH}")
    print(f"Candidate rows: {len(candidates)}")

    if candidates.empty:
        raise ValueError("No tennis candidates found.")

    required_columns = [
        "run_id",
        "event_ticker",
        "event_title",
        "series_ticker",
        "competition",
        "tour",
        "scheduled_start_utc",
        "scheduled_start_local",
        "first_competitor_id",
        "second_competitor_id",
        "best_of",
        "market_count",
        "market_rows",
        "player_1",
        "player_2",
        "attachment_status",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in candidates.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    approved = candidates[
        candidates["attachment_status"] == "ok"
    ].copy()

    print(f"Approved candidates: {len(approved)}")

    if approved.empty:
        raise ValueError("No approved tennis candidates found.")

    approved["fixture_id"] = [
        f"tennis_{index + 1:04d}"
        for index in range(len(approved))
    ]

    approved["player_1_name"] = approved["event_title"].str.split(
        " vs ",
        n=1,
        expand=True,
    )[0]

    approved["player_2_name"] = approved["event_title"].str.split(
        " vs ",
        n=1,
        expand=True,
    )[1]

    approved["independent_tournament"] = ""
    approved["independent_surface"] = ""
    approved["independent_round"] = ""
    approved["independent_best_of"] = ""
    approved["independent_start_time_utc"] = ""

    approved["home_away_orientation_verified"] = False
    approved["match_status"] = "pending_independent_match"
    approved["review_notes"] = ""

    output_columns = [
        "fixture_id",
        "run_id",
        "event_ticker",
        "event_title",
        "series_ticker",
        "competition",
        "tour",
        "scheduled_start_utc",
        "scheduled_start_local",
        "player_1_kalshi_id",
        "player_2_kalshi_id",
        "player_1_name",
        "player_2_name",
        "independent_tournament",
        "independent_surface",
        "independent_round",
        "independent_best_of",
        "independent_start_time_utc",
        "home_away_orientation_verified",
        "match_status",
        "review_notes",
        "market_count",
        "market_rows",
        "player_1",
        "player_2",
        "attachment_status",
    ]

    template = approved.rename(
        columns={
            "first_competitor_id": "player_1_kalshi_id",
            "second_competitor_id": "player_2_kalshi_id",
        }
    )[output_columns]

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    template.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print("\nTEMPLATE SUMMARY")
    print(f"Fixtures created: {len(template)}")
    print(f"Unique event tickers: {template['event_ticker'].nunique()}")
    print(f"Unique player-ID pairs: {template[['player_1_kalshi_id', 'player_2_kalshi_id']].drop_duplicates().shape[0]}")

    print("\nFIXTURES BY SERIES")
    print(
        template.groupby("series_ticker").size().to_string()
    )

    print("\nFIXTURES BY LOCAL DATE")
    print(
        pd.to_datetime(template["scheduled_start_local"])
        .dt.date.value_counts()
        .sort_index()
        .to_string()
    )

    print("\nMISSING MATCH-FORMAT VALUES")
    print(
        template["independent_best_of"].isna().sum()
    )

    print("\nOUTPUT SAVED")
    print(OUTPUT_PATH)

    print("\nTENNIS FIXTURE TEMPLATE COMPLETE")


if __name__ == "__main__":
    main()