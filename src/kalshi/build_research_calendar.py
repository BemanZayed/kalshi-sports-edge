import json
import sys
from pathlib import Path

import pandas as pd


KALSHI_MODULE_DIR = Path(__file__).resolve().parent

if str(KALSHI_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_MODULE_DIR))

from pipeline_config import load_config


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RUNS_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "kalshi"
    / "event_runs"
)

OUT_DIR = PROJECT_ROOT / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# SHARED CONFIGURATION
# ============================================================

PIPELINE_CONFIG = load_config()

SERIES_SPORT_MAP = PIPELINE_CONFIG["series_sport_map"]


# ============================================================
# HELPERS
# ============================================================

def timestamp(value):
    return pd.to_datetime(
        value,
        utc=True,
        errors="coerce",
    )


def number(value):
    return pd.to_numeric(
        value,
        errors="coerce",
    )


def find_latest_completed_run():
    completed_runs = []

    for manifest_path in RUNS_DIR.glob("*/manifest.json"):
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )

        if manifest.get("status") == "complete":
            completed_runs.append(
                (manifest_path.parent, manifest)
            )

    if not completed_runs:
        raise FileNotFoundError(
            "No completed collection run found. "
            "Run src/kalshi/collect_events.py first."
        )

    return max(
        completed_runs,
        key=lambda item: item[1]["started_at_utc"],
    )


def get_research_window(manifest):
    window = manifest.get("research_window")

    if not isinstance(window, dict):
        raise ValueError(
            "The latest completed run has no research_window. "
            "Run the updated collector first."
        )

    required_fields = (
        "calendar_timezone",
        "start_date_inclusive",
        "end_date_inclusive",
        "start_utc",
        "end_utc_exclusive",
    )

    for field in required_fields:
        if not isinstance(window.get(field), str):
            raise ValueError(
                f"The run research_window is missing {field}"
            )

    timezone_name = window["calendar_timezone"]

    start_local = pd.Timestamp(
        window["start_date_inclusive"],
        tz=timezone_name,
    )

    end_local_inclusive = pd.Timestamp(
        window["end_date_inclusive"],
        tz=timezone_name,
    )

    end_local_exclusive = (
        end_local_inclusive
        + pd.DateOffset(days=1)
    )

    start_utc = timestamp(window["start_utc"])

    end_utc_exclusive = timestamp(
        window["end_utc_exclusive"]
    )

    if pd.isna(start_utc) or pd.isna(end_utc_exclusive):
        raise ValueError(
            "The run research_window has invalid UTC boundaries."
        )

    if end_local_exclusive != end_utc_exclusive.tz_convert(
        timezone_name
    ):
        raise ValueError(
            "The run research_window dates and UTC boundaries disagree."
        )

    if start_local.tz_convert("UTC") != start_utc:
        raise ValueError(
            "The run research_window start date and UTC boundary disagree."
        )

    return {
        "timezone": timezone_name,
        "start_date_inclusive": window[
            "start_date_inclusive"
        ],
        "end_date_inclusive": window[
            "end_date_inclusive"
        ],
        "start_utc": start_utc,
        "end_utc_exclusive": end_utc_exclusive,
    }


def keep_latest_milestone(milestones, milestone):
    milestone_id = milestone.get("id")

    if not milestone_id:
        raise ValueError(
            "A milestone is missing its ID."
        )

    previous = milestones.get(milestone_id)

    if previous is None:
        milestones[milestone_id] = milestone
        return

    old_updated = timestamp(
        previous.get("last_updated_ts")
    )

    new_updated = timestamp(
        milestone.get("last_updated_ts")
    )

    if pd.notna(new_updated) and (
        pd.isna(old_updated)
        or new_updated > old_updated
    ):
        milestones[milestone_id] = milestone


def identify_outcome_role(row, event_lookup):
    event = event_lookup.loc[row["event_ticker"]]
    strike = json.loads(row["custom_strike"])

    if event["sport"] == "football":
        competitor_id = strike.get("soccer_team")

        choices = [
            ("home", event["home_team_id"]),
            ("away", event["away_team_id"]),
            ("draw", event["tie_id"]),
        ]

    elif event["sport"] == "tennis":
        competitor_id = strike.get(
            "tennis_competitor"
        )

        choices = [
            ("player_1", event["first_competitor_id"]),
            ("player_2", event["second_competitor_id"]),
        ]

    else:
        return "unmapped"

    for role, reference_id in choices:
        if (
            competitor_id
            and competitor_id == reference_id
        ):
            return role

    return "unmapped"


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():
    run_dir, manifest = find_latest_completed_run()

    research_window = get_research_window(manifest)

    timezone_name = research_window["timezone"]
    start_date = research_window["start_date_inclusive"]
    end_date = research_window["end_date_inclusive"]
    start_utc = research_window["start_utc"]
    end_utc_exclusive = research_window["end_utc_exclusive"]

    print("Reading completed run:", run_dir.name)
    print(
        "Research window:",
        start_date,
        "through",
        end_date,
        "(inclusive)",
    )
    print("Calendar timezone:", timezone_name)

    events = {}
    milestones = {}
    market_rows = []

    for series in manifest["series"]:
        series_dir = run_dir / series
        page_paths = sorted(
            series_dir.glob("page_*.json")
        )

        if not page_paths:
            raise FileNotFoundError(
                f"No saved pages found for {series}"
            )

        for page_path in page_paths:
            record = json.loads(
                page_path.read_text(encoding="utf-8")
            )

            if record.get("http_status") != 200:
                raise ValueError(
                    f"Unsuccessful saved response: {page_path}"
                )

            payload = record["payload"]

            for milestone in (
                payload.get("milestones") or []
            ):
                keep_latest_milestone(
                    milestones,
                    milestone,
                )

            for event in payload.get("events") or []:
                event_id = event["event_ticker"]

                if event_id in events:
                    raise ValueError(
                        "Duplicate event across pages: "
                        f"{event_id}"
                    )

                events[event_id] = event

                for market in (
                    event.get("markets") or []
                ):
                    bid = number(
                        market.get("yes_bid_dollars")
                    )

                    ask = number(
                        market.get("yes_ask_dollars")
                    )

                    valid_quote = (
                        pd.notna(bid)
                        and pd.notna(ask)
                        and 0 < bid <= ask < 1
                    )

                    market_rows.append(
                        {
                            "run_id": manifest["run_id"],
                            "collected_at_utc": record[
                                "collected_at_utc"
                            ],
                            "event_ticker": event_id,
                            "market_ticker": market.get(
                                "ticker"
                            ),
                            "outcome_name": market.get(
                                "yes_sub_title"
                            ),
                            "custom_strike": json.dumps(
                                market.get("custom_strike")
                                or {},
                                ensure_ascii=False,
                            ),
                            "status": market.get("status"),
                            "yes_bid": bid,
                            "yes_ask": ask,
                            "has_interior_quote": valid_quote,
                            "quoted_spread": (
                                ask - bid
                                if valid_quote
                                else float("nan")
                            ),
                            "yes_bid_size": number(
                                market.get(
                                    "yes_bid_size_fp"
                                )
                            ),
                            "yes_ask_size": number(
                                market.get(
                                    "yes_ask_size_fp"
                                )
                            ),
                            "volume_contracts": number(
                                market.get("volume_fp")
                            ),
                            "open_interest_contracts": number(
                                market.get(
                                    "open_interest_fp"
                                )
                            ),
                            "market_occurrence_utc": (
                                market.get(
                                    "occurrence_datetime"
                                )
                            ),
                            "market_close_utc": market.get(
                                "close_time"
                            ),
                            "rules_primary": market.get(
                                "rules_primary"
                            ),
                            "rules_secondary": market.get(
                                "rules_secondary"
                            ),
                        }
                    )

    milestone_map = {}

    for milestone in milestones.values():
        linked_events = set(
            (
                milestone.get(
                    "primary_event_tickers"
                )
                or []
            )
            + (
                milestone.get(
                    "related_event_tickers"
                )
                or []
            )
        )

        for event_id in linked_events:
            milestone_map.setdefault(
                event_id, []
            ).append(milestone)

    event_rows = []

    for event_id, event in events.items():
        linked = milestone_map.get(
            event_id, []
        )

        milestone = (
            linked[0]
            if len(linked) == 1
            else {}
        )

        details = (
            milestone.get("details") or {}
        )

        metadata = (
            event.get("product_metadata") or {}
        )

        scheduled_start = timestamp(
            milestone.get("start_date")
        )

        schedule_needs_review = (
            len(linked) != 1
            or pd.isna(scheduled_start)
        )

        candidate_in_window = (
            pd.notna(scheduled_start)
            and (
                start_utc
                <= scheduled_start
                < end_utc_exclusive
            )
        )

        series = event.get("series_ticker")

        event_rows.append(
            {
                "run_id": manifest["run_id"],
                "sport": SERIES_SPORT_MAP.get(
                    series,
                    "unclassified",
                ),
                "series_ticker": series,
                "event_ticker": event_id,
                "event_title": event.get("title"),
                "competition": metadata.get(
                    "competition"
                ),
                "scheduled_start_utc": (
                    scheduled_start
                ),
                "scheduled_start_local": (
                    scheduled_start
                    .tz_convert(timezone_name)
                    .isoformat()
                    if pd.notna(scheduled_start)
                    else None
                ),
                "schedule_source": (
                    "kalshi_milestone"
                ),
                "schedule_independently_verified": False,
                "linked_milestone_count": len(linked),
                "schedule_needs_review": (
                    schedule_needs_review
                ),
                "candidate_in_window": (
                    candidate_in_window
                ),
                "milestone_id": milestone.get("id"),
                "milestone_updated_utc": (
                    milestone.get(
                        "last_updated_ts"
                    )
                ),
                "milestone_status": details.get(
                    "status"
                ),
                "home_team_id": details.get(
                    "home_team_id"
                ),
                "away_team_id": details.get(
                    "away_team_id"
                ),
                "tie_id": details.get("tie_id"),
                "first_competitor_id": details.get(
                    "first_competitor_id"
                ),
                "second_competitor_id": details.get(
                    "second_competitor_id"
                ),
                "best_of": details.get("best_of"),
                "tour": details.get("tour"),
                "market_count": len(
                    event.get("markets") or []
                ),
            }
        )

    event_df = pd.DataFrame(event_rows)
    market_df = pd.DataFrame(market_rows)

    if event_df.empty:
        print("\nNo events found in this collection run.")
        return

    event_df = event_df.sort_values(
        ["scheduled_start_utc", "event_ticker"],
        na_position="last",
    )

    if not market_df.empty:
        if market_df["market_ticker"].duplicated().any():
            raise ValueError(
                "Duplicate market tickers found."
            )

        event_lookup = event_df.set_index(
            "event_ticker"
        )

        market_df["outcome_role"] = market_df.apply(
            identify_outcome_role,
            axis=1,
            event_lookup=event_lookup,
        )

        market_df = market_df.merge(
            event_df[
                [
                    "event_ticker",
                    "sport",
                    "event_title",
                    "scheduled_start_utc",
                    "candidate_in_window",
                ]
            ],
            on="event_ticker",
            how="left",
            validate="many_to_one",
        )

    candidates = event_df.loc[
        event_df["candidate_in_window"]
    ].copy()

    schedule_review = event_df.loc[
        event_df["schedule_needs_review"]
    ].copy()

    if not market_df.empty:
        candidate_markets = market_df.loc[
            market_df["candidate_in_window"]
        ].copy()
    else:
        candidate_markets = market_df.copy()

    event_df.to_csv(
        OUT_DIR / "kalshi_events_clean.csv",
        index=False,
    )

    market_df.to_csv(
        OUT_DIR / "kalshi_market_snapshots.csv",
        index=False,
    )

    candidates.to_csv(
        OUT_DIR / "kalshi_calendar_candidates.csv",
        index=False,
    )

    candidate_markets.to_csv(
        OUT_DIR / "kalshi_calendar_market_snapshots.csv",
        index=False,
    )

    schedule_review.to_csv(
        OUT_DIR / "kalshi_schedule_review.csv",
        index=False,
    )

    settings = {
        "source_run_id": manifest["run_id"],
        "calendar_timezone": timezone_name,
        "start_date_inclusive": start_date,
        "end_date_inclusive": end_date,
        "start_utc": start_utc.isoformat(),
        "end_utc_exclusive": (
            end_utc_exclusive.isoformat()
        ),
        "series_sport_map": SERIES_SPORT_MAP,
        "schedule_source": "kalshi_milestone",
        "independently_verified": False,
    }

    (
        OUT_DIR / "kalshi_calendar_settings.json"
    ).write_text(
        json.dumps(
            settings,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\nEVENT SUMMARY")
    print("All collected events:", len(event_df))
    print("Calendar candidates:", len(candidates))
    print(
        "Schedules needing review:",
        len(schedule_review),
    )
    print(
        "Market snapshots, full run:",
        len(market_df),
    )
    print(
        "Market snapshots, target window:",
        len(candidate_markets),
    )

    print("\nCANDIDATES BY SPORT")

    if candidates.empty:
        print("No events fall inside the target window.")
    else:
        print(
            candidates.groupby("sport")
            .size()
            .to_string()
        )

    print("\nUPCOMING CANDIDATES")

    print(
        candidates[
            [
                "sport",
                "event_title",
                "scheduled_start_local",
                "market_count",
            ]
        ].to_string(index=False)
    )

    if not market_df.empty:
        print("\nOUTCOME MAPPING — FULL RUN")

        print(
            market_df.groupby("outcome_role")
            .size()
            .to_string()
        )

        print("\nOUTCOME MAPPING — TARGET WINDOW")

        print(
            candidate_markets.groupby("outcome_role")
            .size()
            .to_string()
        )

    print("\nTables saved in:")
    print(OUT_DIR)

    print(
        "\nScope: selected-series Kalshi calendar, "
        "not all football and tennis fixtures."
    )

    print(
        "Schedules are source-reported, "
        "not independently verified."
    )

    print("\nCALENDAR BUILD COMPLETE")


if __name__ == "__main__":
    main()