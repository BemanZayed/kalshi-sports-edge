import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from simulator_state import load_simulator_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
INTEGRATION_DIR = PROCESSED_DIR / "integration"
MARKETS_PATH = (
    PROCESSED_DIR / "kalshi_market_snapshots.csv"
)

OUTPUT_DIR = INTEGRATION_DIR
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    config = load_simulator_config()
    integration = config["integration"]

    validated_path = (
        OUTPUT_DIR / "validated_signals.csv"
    )

    if not integration["enabled"]:
        print("PAPER ENGINE: INTEGRATION DISABLED")
        print("No signals were evaluated.")
        print("No mock positions were created.")
        print("No orders were sent.")
        return

    if not validated_path.exists():
        print("PAPER ENGINE: NO VALIDATED SIGNALS")
        print("Run signal_builder.py first.")
        print("No mock positions were created.")
        print("No orders were sent.")
        return

    signals = pd.read_csv(validated_path)

    if signals.empty:
        print("PAPER ENGINE: NO VALID SIGNALS")
        print("No mock positions were created.")
        print("No orders were sent.")
        return

    markets = pd.read_csv(MARKETS_PATH)

    market_tickers = set(
        markets["market_ticker"]
    )

    matched_signals = []
    unmatched_signals = []

    for _, signal in signals.iterrows():
        if signal["market_ticker"] in market_tickers:
            matched_signals.append(signal.to_dict())
        else:
            unmatched_signals.append(
                {
                    **signal.to_dict(),
                    "engine_status": "market_not_found",
                }
            )

    matched_df = pd.DataFrame(matched_signals)
    unmatched_df = pd.DataFrame(unmatched_signals)

    report = {
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "integration_enabled": integration["enabled"],
        "position_creation_allowed": integration[
            "allow_position_creation"
        ],
        "signals_evaluated": len(signals),
        "signals_matched_to_market": len(
            matched_signals
        ),
        "signals_not_matched_to_market": len(
            unmatched_signals
        ),
        "positions_created": 0,
        "orders_sent": 0,
        "mode": "dry_run_only",
        "note": (
            "The engine validated market availability only. "
            "It did not create mock positions."
        ),
    }

    report_path = OUTPUT_DIR / "paper_engine_dry_run.json"
    matched_path = OUTPUT_DIR / "engine_matched_signals.csv"
    unmatched_path = (
        OUTPUT_DIR / "engine_unmatched_signals.csv"
    )

    matched_df.to_csv(matched_path, index=False)
    unmatched_df.to_csv(unmatched_path, index=False)

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("PAPER ENGINE DRY RUN COMPLETE")
    print("Signals evaluated:", report["signals_evaluated"])
    print(
        "Matched to current market snapshot:",
        report["signals_matched_to_market"],
    )
    print(
        "Not matched to current market snapshot:",
        report["signals_not_matched_to_market"],
    )
    print("Positions created: 0")
    print("Orders sent: 0")
    print("Report:")
    print(report_path)


if __name__ == "__main__":
    main()