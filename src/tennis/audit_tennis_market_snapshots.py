"""
Audit tennis market snapshots.

Inputs:
- data/processed/kalshi_events_clean.csv
- data/processed/kalshi_market_snapshots.csv

Outputs:
- data/processed/tennis_market_audit_summary.csv
- data/processed/tennis_market_quality.csv
- data/processed/tennis_market_attachment_review.csv
- data/processed/tennis_market_candidates.csv

This script does not make network requests.
It does not modify either input file.
"""

from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BASE_DIR / "data" / "processed"

EVENTS_PATH = PROCESSED_DIR / "kalshi_events_clean.csv"
SNAPSHOTS_PATH = PROCESSED_DIR / "kalshi_market_snapshots.csv"

TENNIS_OUTCOME_ROLES = {"player_1", "player_2"}


def main():
    events = pd.read_csv(EVENTS_PATH)
    snapshots = pd.read_csv(SNAPSHOTS_PATH)

    events["candidate_in_window"] = events["candidate_in_window"].astype(str).str.lower() == "true"

    tennis_events = events[events["sport"] == "tennis"].copy()
    tennis_candidates = tennis_events[tennis_events["candidate_in_window"]].copy()

    tennis_snapshots = snapshots[snapshots["sport"] == "tennis"].copy()

    print("=" * 60)
    print("TENNIS MARKET SNAPSHOT AUDIT")
    print("=" * 60)
    print(f"Event run: {events['run_id'].iloc[0]}")
    print(f"Snapshot run: {snapshots['run_id'].iloc[0]}")
    print(f"Collected tennis events: {len(tennis_events)}")
    print(f"Tennis candidates in window: {len(tennis_candidates)}")
    print(f"Tennis market snapshot rows: {len(tennis_snapshots)}")

    if tennis_candidates.empty:
        raise ValueError("No tennis candidates found in the research window.")

    if tennis_snapshots.empty:
        raise ValueError("No tennis market snapshot rows found.")

    event_run_id = events["run_id"].iloc[0]
    snapshot_run_id = snapshots["run_id"].iloc[0]

    if event_run_id != snapshot_run_id:
        print("WARNING: event and snapshot run IDs differ.")

    market_counts = (
        tennis_snapshots
        .groupby("event_ticker")
        .size()
        .rename("market_rows")
        .reset_index()
    )

    role_counts = (
        tennis_snapshots
        .groupby(["event_ticker", "outcome_role"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )

    for role in TENNIS_OUTCOME_ROLES:
        if role not in role_counts.columns:
            role_counts[role] = 0

    audit = tennis_candidates.merge(
        market_counts,
        on="event_ticker",
        how="left",
    ).merge(
        role_counts,
        on="event_ticker",
        how="left",
    )

    audit["market_rows"] = audit["market_rows"].fillna(0).astype(int)
    audit["player_1"] = audit["player_1"].fillna(0).astype(int)
    audit["player_2"] = audit["player_2"].fillna(0).astype(int)

    audit["has_expected_two_markets"] = audit["market_rows"] == 2
    audit["has_both_player_roles"] = (
        (audit["player_1"] == 1) & (audit["player_2"] == 1)
    )

    audit["missing_player_1"] = audit["player_1"] == 0
    audit["missing_player_2"] = audit["player_2"] == 0

    audit["duplicate_player_1"] = audit["player_1"] > 1
    audit["duplicate_player_2"] = audit["player_2"] > 1

    audit["attachment_status"] = "ok"
    audit.loc[
        ~audit["has_expected_two_markets"]
        | ~audit["has_both_player_roles"],
        "attachment_status",
    ] = "review"

    missing_events = tennis_candidates[
        ~tennis_candidates["event_ticker"].isin(tennis_snapshots["event_ticker"])
    ]

    print("\nATTACHMENT SUMMARY")
    print(f"Candidates with exactly two markets: {audit['has_expected_two_markets'].sum()}")
    print(f"Candidates with player_1 and player_2: {audit['has_both_player_roles'].sum()}")
    print(f"Candidates needing review: {(audit['attachment_status'] == 'review').sum()}")
    print(f"Candidates with no market rows: {len(missing_events)}")

    print("\nCANDIDATES BY SERIES")
    print(
        audit.groupby("series_ticker")["attachment_status"]
        .value_counts()
        .unstack(fill_value=0)
        .to_string()
    )

    numeric_columns = [
        "yes_bid",
        "yes_ask",
        "quoted_spread",
        "yes_bid_size",
        "yes_ask_size",
        "volume_contracts",
        "open_interest_contracts",
    ]

    for column in numeric_columns:
        if column in tennis_snapshots.columns:
            tennis_snapshots[column] = pd.to_numeric(
                tennis_snapshots[column],
                errors="coerce",
            )

    tennis_snapshots["has_interior_quote"] = (
        tennis_snapshots["has_interior_quote"].astype(str).str.lower() == "true"
    )

    tennis_snapshots["usable_two_sided_quote"] = (
        tennis_snapshots["has_interior_quote"]
        & tennis_snapshots["yes_bid"].notna()
        & tennis_snapshots["yes_ask"].notna()
        & (tennis_snapshots["yes_bid"] > 0)
        & (tennis_snapshots["yes_ask"] < 1)
    )

    tennis_snapshots["spread_bucket"] = pd.cut(
        tennis_snapshots["quoted_spread"],
        bins=[-0.001, 0.02, 0.05, 0.10, 0.25, 1.01],
        labels=[
            "0.00-0.02",
            "0.02-0.05",
            "0.05-0.10",
            "0.10-0.25",
            "0.25+",
        ],
    )

    tennis_snapshots["liquidity_status"] = "usable"
    tennis_snapshots.loc[
        ~tennis_snapshots["usable_two_sided_quote"],
        "liquidity_status",
    ] = "no_usable_two_sided_quote"
    tennis_snapshots.loc[
        tennis_snapshots["usable_two_sided_quote"]
        & (tennis_snapshots["quoted_spread"] > 0.10),
        "liquidity_status",
    ] = "wide_spread"

    quality = tennis_snapshots.merge(
        tennis_candidates[
            [
                "event_ticker",
                "series_ticker",
                "competition",
                "tour",
                "scheduled_start_local",
            ]
        ],
        on="event_ticker",
        how="left",
    )

    quality["candidate_in_window"] = quality["event_ticker"].isin(
        tennis_candidates["event_ticker"]
    )

    print("\nQUOTE QUALITY — ALL COLLECTED TENNIS MARKETS")
    print(
        quality["liquidity_status"]
        .value_counts()
        .to_string()
    )

    print("\nQUOTE QUALITY — TARGET WINDOW TENNIS MARKETS")
    target_quality = quality[quality["candidate_in_window"]]

    print(
        target_quality["liquidity_status"]
        .value_counts()
        .to_string()
    )

    print("\nSPREAD BUCKETS — TARGET WINDOW")
    print(
        target_quality["spread_bucket"]
        .value_counts(dropna=False)
        .sort_index()
        .to_string()
    )

    print("\nQUOTE QUALITY BY SERIES — TARGET WINDOW")
    print(
        target_quality
        .groupby("series_ticker")["liquidity_status"]
        .value_counts()
        .unstack(fill_value=0)
        .to_string()
    )

    review_rows = []

    for _, row in audit.iterrows():
        issues = []

        if not row["has_expected_two_markets"]:
            issues.append("unexpected_market_count")

        if row["missing_player_1"]:
            issues.append("missing_player_1")

        if row["missing_player_2"]:
            issues.append("missing_player_2")

        if row["duplicate_player_1"]:
            issues.append("duplicate_player_1")

        if row["duplicate_player_2"]:
            issues.append("duplicate_player_2")

        if issues:
            review_rows.append(
                {
                    "event_ticker": row["event_ticker"],
                    "event_title": row["event_title"],
                    "series_ticker": row["series_ticker"],
                    "scheduled_start_local": row["scheduled_start_local"],
                    "market_rows": row["market_rows"],
                    "player_1_rows": row["player_1"],
                    "player_2_rows": row["player_2"],
                    "issues": ";".join(issues),
                }
            )

    review = pd.DataFrame(review_rows)

    if review.empty:
        review = pd.DataFrame(
            columns=[
                "event_ticker",
                "event_title",
                "series_ticker",
                "scheduled_start_local",
                "market_rows",
                "player_1_rows",
                "player_2_rows",
                "issues",
            ]
        )

    candidate_export_columns = [
        "run_id",
        "event_ticker",
        "event_title",
        "series_ticker",
        "competition",
        "tour",
        "scheduled_start_utc",
        "scheduled_start_local",
        "schedule_source",
        "schedule_independently_verified",
        "first_competitor_id",
        "second_competitor_id",
        "best_of",
        "market_count",
        "market_rows",
        "player_1",
        "player_2",
        "has_expected_two_markets",
        "has_both_player_roles",
        "attachment_status",
    ]

    candidate_export = audit[candidate_export_columns].copy()

    summary_rows = [
        {
            "metric": "event_run_id",
            "value": event_run_id,
        },
        {
            "metric": "snapshot_run_id",
            "value": snapshot_run_id,
        },
        {
            "metric": "collected_tennis_events",
            "value": len(tennis_events),
        },
        {
            "metric": "tennis_candidates_in_window",
            "value": len(tennis_candidates),
        },
        {
            "metric": "tennis_market_snapshot_rows",
            "value": len(tennis_snapshots),
        },
        {
            "metric": "target_window_market_rows",
            "value": len(target_quality),
        },
        {
            "metric": "candidates_with_two_markets",
            "value": audit["has_expected_two_markets"].sum(),
        },
        {
            "metric": "candidates_with_both_roles",
            "value": audit["has_both_player_roles"].sum(),
        },
        {
            "metric": "candidates_needing_review",
            "value": (audit["attachment_status"] == "review").sum(),
        },
        {
            "metric": "candidates_without_market_rows",
            "value": len(missing_events),
        },
        {
            "metric": "target_window_usable_two_sided_quotes",
            "value": target_quality["usable_two_sided_quote"].sum(),
        },
        {
            "metric": "target_window_wide_spread_quotes",
            "value": (target_quality["liquidity_status"] == "wide_spread").sum(),
        },
    ]

    summary = pd.DataFrame(summary_rows)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    summary.to_csv(
        PROCESSED_DIR / "tennis_market_audit_summary.csv",
        index=False,
    )

    quality.to_csv(
        PROCESSED_DIR / "tennis_market_quality.csv",
        index=False,
    )

    review.to_csv(
        PROCESSED_DIR / "tennis_market_attachment_review.csv",
        index=False,
    )

    candidate_export.to_csv(
        PROCESSED_DIR / "tennis_market_candidates.csv",
        index=False,
    )

    print("\nOUTPUTS SAVED")
    print(PROCESSED_DIR / "tennis_market_audit_summary.csv")
    print(PROCESSED_DIR / "tennis_market_quality.csv")
    print(PROCESSED_DIR / "tennis_market_attachment_review.csv")
    print(PROCESSED_DIR / "tennis_market_candidates.csv")

    print("\nTENNIS MARKET AUDIT COMPLETE")


if __name__ == "__main__":
    main()