import json
from pathlib import Path

import pandas as pd

from simulator_state import load_simulator_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
INTEGRATION_DIR = PROCESSED_DIR / "integration"

EVENTS_PATH = PROCESSED_DIR / "kalshi_events_clean.csv"
MARKETS_PATH = (
    PROCESSED_DIR / "kalshi_market_snapshots.csv"
)
SETTINGS_PATH = (
    PROCESSED_DIR / "kalshi_calendar_settings.json"
)

VALIDATED_SIGNALS_PATH = (
    INTEGRATION_DIR / "validated_signals.csv"
)
ENGINE_REPORT_PATH = (
    INTEGRATION_DIR / "paper_engine_dry_run.json"
)


def line():
    print("-" * 78)


def main():
    config = load_simulator_config()
    integration = config["integration"]

    line()
    print("KALSHI SPORTS EDGE — PAPER TRADING DASHBOARD")
    line()
    print("PAPER TRADING ONLY — NO REAL ORDERS")

    if not integration["enabled"]:
        print(
            "INTEGRATION DISABLED — NO MOCK POSITIONS "
            "MAY BE CREATED"
        )
    elif not integration["allow_position_creation"]:
        print(
            "INTEGRATION ENABLED — POSITION CREATION "
            "STILL DISABLED"
        )
    else:
        print(
            "INTEGRATION ENABLED — MOCK POSITION CREATION "
            "PERMITTED"
        )

    line()

    settings = {}

    if SETTINGS_PATH.exists():
        settings = json.loads(
            SETTINGS_PATH.read_text(
                encoding="utf-8-sig"
            )
        )

    print("KALSHI DATA")
    print(
        "Source run:",
        settings.get("source_run_id", "Not available"),
    )
    print(
        "Window:",
        settings.get(
            "start_date_inclusive",
            "Not available",
        ),
        "through",
        settings.get(
            "end_date_inclusive",
            "Not available",
        ),
    )

    if EVENTS_PATH.exists():
        events = pd.read_csv(EVENTS_PATH)
        print("Events:", len(events))
    else:
        print("Events: Calendar not built")

    if MARKETS_PATH.exists():
        markets = pd.read_csv(MARKETS_PATH)
        print("Market snapshots:", len(markets))
    else:
        print("Market snapshots: Calendar not built")

    line()
    print("MODEL INTEGRATION")
    print(
        "Integration enabled:",
        integration["enabled"],
    )
    print(
        "Position creation allowed:",
        integration["allow_position_creation"],
    )
    print(
        "Signal file:",
        integration["signal_file"],
    )

    if VALIDATED_SIGNALS_PATH.exists():
        signals = pd.read_csv(VALIDATED_SIGNALS_PATH)
        print("Validated signals available:", len(signals))
    else:
        print("Validated signals available: 0")

    if ENGINE_REPORT_PATH.exists():
        report = json.loads(
            ENGINE_REPORT_PATH.read_text(
                encoding="utf-8"
            )
        )
        print("Last engine mode:", report.get("mode"))
        print(
            "Last positions created:",
            report.get("positions_created", 0),
        )
    else:
        print("Last engine mode: Not run")

    line()
    print("PAPER PORTFOLIOS")
    print(
        "No mock positions have been created because "
        "integration is not complete."
    )

    for portfolio in config["portfolios"]:
        status = (
            "enabled"
            if portfolio["enabled"]
            else "disabled"
        )

        print(
            f"{portfolio['portfolio_id']}: {status}, "
            f"starting_cash="
            f"{portfolio['starting_cash']:.2f} "
            f"{portfolio['currency']}, "
            f"open_positions=0, "
            f"exposure=0.00, "
            f"equity="
            f"{portfolio['starting_cash']:.2f}"
        )

    line()
    print("NEXT INTEGRATION INPUT")
    print(
        "Your modeling project should later write "
        "model_signals.csv to:"
    )
    print(PROJECT_ROOT / integration["signal_file"])
    line()


if __name__ == "__main__":
    main()