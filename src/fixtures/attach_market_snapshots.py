from pathlib import Path
import json
import pandas as pd


def run(calendar_path, snapshots_path, events_path, output_dir):
    calendar = pd.read_csv(calendar_path)
    markets = pd.read_csv(snapshots_path)
    events = pd.read_csv(events_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    requirements = [
        (calendar, ["match_id", "join_status", "kalshi_run_id", "kalshi_event_ticker"], "calendar"),
        (markets, ["run_id", "event_ticker", "market_ticker", "outcome_role", "custom_strike", "yes_bid", "yes_ask", "collected_at_utc", "rules_primary", "rules_secondary"], "markets"),
        (events, ["run_id", "event_ticker", "home_team_id", "away_team_id", "tie_id"], "events"),
    ]
    for frame, columns, label in requirements:
        missing = set(columns) - set(frame.columns)
        if missing:
            raise ValueError(f"{label}: missing columns {sorted(missing)}")
    if calendar.match_id.isna().any() or calendar.match_id.duplicated().any():
        raise ValueError("Missing or duplicated fixture IDs")
    if markets[["run_id", "event_ticker", "market_ticker"]].isna().any().any():
        raise ValueError("Missing snapshot keys")
    if markets.duplicated(["run_id", "market_ticker"]).any():
        raise ValueError("Duplicate snapshot market key in one run")
    if events.duplicated(["run_id", "event_ticker"]).any():
        raise ValueError("Duplicate event key in one run")

    # Only approved fixture/event links can acquire markets.
    approved = calendar.loc[calendar.join_status == "matched_pair_and_start"].copy()
    if approved[["kalshi_run_id", "kalshi_event_ticker"]].isna().any().any():
        raise ValueError("Approved link has missing run/event keys")
    if approved.duplicated(["kalshi_run_id", "kalshi_event_ticker"]).any():
        raise ValueError("An event is approved for more than one fixture")

    market_columns = {col: "snapshot_" + col for col in markets.columns}
    snapshots = markets.rename(columns=market_columns)
    details = approved.merge(
        snapshots,
        left_on=["kalshi_run_id", "kalshi_event_ticker"],
        right_on=["snapshot_run_id", "snapshot_event_ticker"],
        how="left", validate="one_to_many",
    )
    refs = events[["run_id", "event_ticker", "home_team_id", "away_team_id", "tie_id"]].rename(columns={
        "run_id": "reference_run_id", "event_ticker": "reference_event_ticker",
        "home_team_id": "reference_home_team_id", "away_team_id": "reference_away_team_id", "tie_id": "reference_tie_id",
    })
    details = details.merge(refs, left_on=["kalshi_run_id", "kalshi_event_ticker"], right_on=["reference_run_id", "reference_event_ticker"], how="left", validate="many_to_one")

    def check_role(row):
        if pd.isna(row["snapshot_market_ticker"]):
            return "missing_snapshot"
        try:
            strike = json.loads(row["snapshot_custom_strike"])
        except (TypeError, ValueError):
            return "invalid_custom_strike"
        if not isinstance(strike, dict):
            return "invalid_custom_strike"
        expected = {"home": "reference_home_team_id", "away": "reference_away_team_id", "draw": "reference_tie_id"}.get(row["snapshot_outcome_role"])
        if expected is None:
            return "unexpected_outcome_role"
        reference = row[expected]
        competitor = strike.get("soccer_team")
        if pd.isna(reference) or not competitor:
            return "missing_structured_id"
        return "consistent" if competitor == reference else "structured_id_mismatch"

    details["structured_role_check"] = details.apply(check_role, axis=1)
    bid = pd.to_numeric(details["snapshot_yes_bid"], errors="coerce")
    ask = pd.to_numeric(details["snapshot_yes_ask"], errors="coerce")
    details["quote_bounds_valid"] = bid.between(0, 1) & ask.between(0, 1) & bid.le(ask)
    details["interior_quote_rechecked"] = details["quote_bounds_valid"] & bid.gt(0) & ask.lt(1)
    details["spread_recomputed"] = (ask - bid).where(details["quote_bounds_valid"])
    details["rules_primary_present"] = details["snapshot_rules_primary"].fillna("").str.strip().ne("")
    details["rules_secondary_present"] = details["snapshot_rules_secondary"].fillna("").str.strip().ne("")
    details["rules_manually_verified"] = False
    details["fixture_side_alignment_verified"] = False
    details["snapshot_is_live_quote"] = False

    rows = []
    for match_id, group in details.groupby("match_id", sort=False):
        actual = group.loc[group.snapshot_market_ticker.notna()]
        roles = actual.snapshot_outcome_role.value_counts().to_dict()
        issues = []
        if len(actual) != 3:
            issues.append("expected_three_markets")
        if roles != {"home": 1, "away": 1, "draw": 1}:
            issues.append("outcome_role_set_incomplete_or_duplicated")
        if not group.structured_role_check.eq("consistent").all():
            issues.append("structured_role_check_failed")
        if not actual.rules_primary_present.all():
            issues.append("missing_primary_rules")
        if not actual.rules_secondary_present.all():
            issues.append("missing_secondary_rules")
        if not actual.quote_bounds_valid.all():
            issues.append("missing_or_invalid_quote")
        rows.append({"match_id": match_id, "attached_market_count": len(actual), "interior_quote_market_count": int(actual.interior_quote_rechecked.sum()), "market_attachment_status": "review_required" if issues else "attached_checks_passed", "market_attachment_issues": " | ".join(issues)})
    checks = pd.DataFrame(rows, columns=["match_id", "attached_market_count", "interior_quote_market_count", "market_attachment_status", "market_attachment_issues"])
    summary = calendar.merge(checks, on="match_id", how="left", validate="one_to_one")
    summary["market_attachment_status"] = summary.market_attachment_status.fillna("not_attached_no_approved_event_link")
    for column in ["attached_market_count", "interior_quote_market_count"]:
        summary[column] = summary[column].fillna(0).astype(int)
    summary["fixture_side_alignment_verified"] = False
    summary["rules_manually_verified"] = False
    assert len(summary) == len(calendar)

    # A long-format left join includes one placeholder row for
    # fixtures with no attached market, preserving the master scope.
    enrichment_columns = [c for c in details.columns if c not in calendar.columns] + ["match_id"]
    long_calendar = calendar.merge(details[enrichment_columns], on="match_id", how="left", validate="one_to_many")
    review = summary.loc[summary.market_attachment_status == "review_required"]
    actual_details = details.loc[details.snapshot_market_ticker.notna()]
    for name, frame in {
        "fixtures_market_summary.csv": summary,
        "fixture_market_snapshots.csv": actual_details,
        "research_calendar_markets_long.csv": long_calendar,
        "fixture_market_attachment_review.csv": review,
    }.items():
        frame.to_csv(output_dir / name, index=False)
    print("MARKET ATTACHMENT SUMMARY")
    print("Independent fixtures preserved:", len(summary))
    print("Approved fixture/event links:", len(approved))
    print("Attached market snapshots:", len(actual_details))
    print("Attachment checks passed:", (summary.market_attachment_status == "attached_checks_passed").sum())
    print("Fixtures requiring attachment review:", len(review))
    print("Fixtures without approved event link:", (summary.market_attachment_status == "not_attached_no_approved_event_link").sum())
    print("Interior quote snapshots:", int(actual_details.interior_quote_rechecked.sum()))
    print("\nSTRUCTURED ROLE CHECK")
    print(details.structured_role_check.value_counts().to_string())
    print("\nCOLLECTION TIMES (UTC)")
    times = pd.to_datetime(actual_details.snapshot_collected_at_utc, utc=True, errors="coerce")
    print("Earliest:", times.min())
    print("Latest:", times.max())
    print("\nSaved outputs:", output_dir)
    print("Structured IDs are checked within Kalshi; fixture home/away alignment is not verified.")
    print("Quotes are historical snapshots, not live prices or trade recommendations.")
    print("MARKET ATTACHMENT COMPLETE")
    return summary, actual_details


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    folder = root / "data" / "processed"
    run(folder / "fixtures_with_kalshi.csv", folder / "kalshi_market_snapshots.csv", folder / "kalshi_events_clean.csv", folder)
