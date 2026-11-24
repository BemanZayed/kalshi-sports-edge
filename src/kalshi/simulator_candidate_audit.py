import json
import sys
from pathlib import Path

import pandas as pd


KALSHI_MODULE_DIR = Path(__file__).resolve().parent

if str(KALSHI_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_MODULE_DIR))

from simulator_state import load_simulator_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
AUDIT_DIR = PROCESSED_DIR / "simulator"

AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def load_market_data():
    events_path = (
        PROCESSED_DIR / "kalshi_events_clean.csv"
    )

    markets_path = (
        PROCESSED_DIR
        / "kalshi_market_snapshots.csv"
    )

    if not events_path.exists():
        raise FileNotFoundError(
            f"Missing processed events file: {events_path}"
        )

    if not markets_path.exists():
        raise FileNotFoundError(
            f"Missing processed markets file: {markets_path}"
        )

    events = pd.read_csv(events_path)
    markets = pd.read_csv(markets_path)

    required_event_columns = {
        "run_id",
        "sport",
        "series_ticker",
        "event_ticker",
        "scheduled_start_utc",
        "candidate_in_window",
    }

    required_market_columns = {
        "run_id",
        "collected_at_utc",
        "event_ticker",
        "market_ticker",
        "outcome_role",
        "yes_bid",
        "yes_ask",
        "has_interior_quote",
        "quoted_spread",
        "volume_contracts",
        "open_interest_contracts",
    }

    missing_event_columns = (
        required_event_columns - set(events.columns)
    )

    if missing_event_columns:
        raise ValueError(
            "Missing event columns: "
            f"{sorted(missing_event_columns)}"
        )

    missing_market_columns = (
        required_market_columns - set(markets.columns)
    )

    if missing_market_columns:
        raise ValueError(
            "Missing market columns: "
            f"{sorted(missing_market_columns)}"
        )

    events["scheduled_start_utc"] = pd.to_datetime(
        events["scheduled_start_utc"],
        utc=True,
        errors="coerce",
    )

    markets["collected_at_utc"] = pd.to_datetime(
        markets["collected_at_utc"],
        utc=True,
        errors="coerce",
    )

    return events, markets


def build_event_lookup(events):
    lookup = events.set_index("event_ticker")

    if lookup.index.duplicated().any():
        raise ValueError(
            "Duplicate event tickers in processed events."
        )

    return lookup


def evaluate_market(
    market,
    event,
    strategy,
    snapshot_time,
):
    checks = []

    has_interior_quote = bool(
        market["has_interior_quote"]
    )

    checks.append(
        {
            "check": "interior_quote",
            "passed": has_interior_quote,
            "failure_reason": (
                "" if has_interior_quote
                else "no_interior_quote"
            ),
        }
    )

    bid = market["yes_bid"]
    ask = market["yes_ask"]

    has_quote = pd.notna(bid) and pd.notna(ask)

    checks.append(
        {
            "check": "quote_present",
            "passed": has_quote,
            "failure_reason": (
                "" if has_quote else "missing_quote"
            ),
        }
    )

    spread = (
        ask - bid
        if has_quote
        else float("nan")
    )

    spread_ok = (
        has_quote
        and spread >= strategy["minimum_spread"]
        and spread <= strategy["maximum_spread"]
    )

    checks.append(
        {
            "check": "spread_range",
            "passed": spread_ok,
            "failure_reason": (
                ""
                if spread_ok
                else (
                    "spread_too_narrow"
                    if has_quote
                    and spread
                    < strategy["minimum_spread"]
                    else "spread_too_wide"
                )
            ),
        }
    )

    price_ok = (
        has_quote
        and strategy["minimum_entry_price"]
        <= ask
        <= strategy["maximum_entry_price"]
    )

    checks.append(
        {
            "check": "entry_price_range",
            "passed": price_ok,
            "failure_reason": (
                ""
                if price_ok
                else "entry_price_outside_range"
            ),
        }
    )

    schedule_ok = bool(
        event["candidate_in_window"]
    )

    if strategy[
        "require_schedule_in_window"
    ]:
        checks.append(
            {
                "check": "schedule_in_window",
                "passed": schedule_ok,
                "failure_reason": (
                    ""
                    if schedule_ok
                    else "outside_research_window"
                ),
            }
        )

    scheduled_start = event[
        "scheduled_start_utc"
    ]

    not_started = (
        pd.notna(scheduled_start)
        and scheduled_start > snapshot_time
    )

    if strategy["exclude_started_events"]:
        checks.append(
            {
                "check": "event_not_started",
                "passed": not_started,
                "failure_reason": (
                    ""
                    if not_started
                    else (
                        "missing_schedule"
                        if pd.isna(scheduled_start)
                        else "event_already_started"
                    )
                ),
            }
        )

    volume = market["volume_contracts"]
    open_interest = market[
        "open_interest_contracts"
    ]

    volume_ok = (
        pd.isna(volume)
        or volume
        >= strategy["minimum_volume_contracts"]
    )

    checks.append(
        {
            "check": "minimum_volume",
            "passed": volume_ok,
            "failure_reason": (
                ""
                if volume_ok
                else "insufficient_volume"
            ),
        }
    )

    open_interest_ok = (
        pd.isna(open_interest)
        or open_interest
        >= strategy[
            "minimum_open_interest_contracts"
        ]
    )

    checks.append(
        {
            "check": "minimum_open_interest",
            "passed": open_interest_ok,
            "failure_reason": (
                ""
                if open_interest_ok
                else "insufficient_open_interest"
            ),
        }
    )

    eligible = all(
        check["passed"] for check in checks
    )

    failure_reasons = [
        check["failure_reason"]
        for check in checks
        if not check["passed"]
    ]

    return eligible, failure_reasons


def audit_strategy(
    strategy_id,
    strategy,
    events,
    markets,
):
    event_lookup = build_event_lookup(events)

    rows = []

    market_groups = markets.groupby(
        "event_ticker"
    )

    for event_ticker, markets_for_event in (
        market_groups
    ):
        if event_ticker not in event_lookup.index:
            continue

        event = event_lookup.loc[event_ticker]

        snapshot_time = markets_for_event[
            "collected_at_utc"
        ].min()

        for _, market in (
            markets_for_event.iterrows()
        ):
            eligible, failure_reasons = (
                evaluate_market(
                    market,
                    event,
                    strategy,
                    snapshot_time,
                )
            )

            rows.append(
                {
                    "strategy_id": strategy_id,
                    "run_id": market["run_id"],
                    "snapshot_utc": market[
                        "collected_at_utc"
                    ].isoformat(),
                    "sport": event["sport"],
                    "series_ticker": event[
                        "series_ticker"
                    ],
                    "event_ticker": event_ticker,
                    "market_ticker": market[
                        "market_ticker"
                    ],
                    "outcome_role": market[
                        "outcome_role"
                    ],
                    "yes_bid": market["yes_bid"],
                    "yes_ask": market["yes_ask"],
                    "quoted_spread": market[
                        "quoted_spread"
                    ],
                    "volume_contracts": market[
                        "volume_contracts"
                    ],
                    "open_interest_contracts": (
                        market[
                            "open_interest_contracts"
                        ]
                    ),
                    "eligible": eligible,
                    "failure_reasons": (
                        ";".join(failure_reasons)
                    ),
                }
            )

    audit = pd.DataFrame(rows)

    if audit.empty:
        return audit, pd.DataFrame()

    selected = audit.loc[audit["eligible"]].copy()

    if selected.empty:
        return audit, selected

    if strategy["selection"] == "lowest_yes_price":
        selected = selected.sort_values(
            [
                "yes_ask",
                "market_ticker",
            ]
        )

    elif strategy["selection"] == "highest_yes_price":
        selected = selected.sort_values(
            [
                "yes_ask",
                "market_ticker",
            ],
            ascending=[False, True],
        )

    else:
        raise ValueError(
            f"Unsupported selection rule: "
            f"{strategy['selection']}"
        )

    selected = selected.drop_duplicates(
        subset=["event_ticker"],
        keep="first",
    )

    selected["strategy_id"] = strategy_id
    selected["entry_price"] = selected["yes_ask"]

    return audit, selected


def main():
    simulator_config = load_simulator_config()

    events, markets = load_market_data()

    strategy_definitions = simulator_config[
        "strategy_definitions"
    ]

    summary_rows = []

    for strategy_id, strategy in (
        strategy_definitions.items()
    ):
        audit, selected = audit_strategy(
            strategy_id,
            strategy,
            events,
            markets,
        )

        audit_path = (
            AUDIT_DIR
            / f"candidate_audit_{strategy_id}.csv"
        )

        selected_path = (
            AUDIT_DIR
            / f"selected_candidates_{strategy_id}.csv"
        )

        audit.to_csv(
            audit_path,
            index=False,
        )

        selected.to_csv(
            selected_path,
            index=False,
        )

        failure_counts = (
            audit.loc[~audit["eligible"]]
            .groupby("failure_reasons")
            .size()
            .sort_values(ascending=False)
        )

        summary_rows.append(
            {
                "strategy_id": strategy_id,
                "markets_evaluated": len(audit),
                "eligible_markets": int(
                    audit["eligible"].sum()
                ),
                "selected_events": len(selected),
                "audit_file": audit_path.name,
                "selected_file": selected_path.name,
            }
        )

        print(f"\nSTRATEGY: {strategy_id}")
        print(
            "Markets evaluated:",
            len(audit),
        )
        print(
            "Eligible markets:",
            int(audit["eligible"].sum()),
        )
        print(
            "Selected events:",
            len(selected),
        )

        if not failure_counts.empty:
            print("\nExclusion reasons:")

            print(
                failure_counts.to_string()
            )

        if not selected.empty:
            print("\nSelected candidates by sport:")

            print(
                selected.groupby("sport")
                .size()
                .to_string()
            )

            print("\nEntry-price summary:")

            print(
                selected["entry_price"]
                .describe()
                .to_string()
            )

    summary = pd.DataFrame(summary_rows)

    summary_path = (
        AUDIT_DIR / "candidate_audit_summary.csv"
    )

    summary.to_csv(
        summary_path,
        index=False,
    )

    print("\nAUDIT SUMMARY")

    print(summary.to_string(index=False))

    print("\nAudit files saved in:")
    print(AUDIT_DIR)

    print("\nCANDIDATE AUDIT COMPLETE")
    print(
        "This audit did not create trades, "
        "modify raw data, or overwrite "
        "the main processed CSVs."
    )


if __name__ == "__main__":
    main()