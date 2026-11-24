import json
from datetime import datetime, timezone
from pathlib import Path

from model_interface import validate_signal_file
from simulator_state import load_simulator_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INTEGRATION_DIR = (
    PROJECT_ROOT / "data" / "integration"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "integration"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    config = load_simulator_config()

    integration = config["integration"]

    if not integration["enabled"]:
        print("INTEGRATION IS DISABLED")
        print("No signals were processed.")
        print("No positions were created.")
        return

    signal_path = PROJECT_ROOT / integration[
        "signal_file"
    ]

    if not signal_path.exists():
        print("NO SIGNAL FILE FOUND")
        print(signal_path)
        print("No signals were processed.")
        print("No positions were created.")
        return

    execution = config["execution_rules"]

    valid_signals, rejected_signals = (
        validate_signal_file(
            signal_path,
            execution["minimum_price"],
            execution["maximum_price"],
            integration["minimum_edge"],
        )
    )

    if len(valid_signals) > integration[
        "maximum_signals_per_run"
    ]:
        valid_signals = valid_signals.head(
            integration["maximum_signals_per_run"]
        )

    valid_path = OUTPUT_DIR / "validated_signals.csv"
    rejected_path = OUTPUT_DIR / "rejected_signals.csv"
    report_path = OUTPUT_DIR / "signal_validation_report.json"

    valid_signals.to_csv(valid_path, index=False)
    rejected_signals.to_csv(rejected_path, index=False)

    report = {
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "signal_file": str(signal_path),
        "signals_read": len(valid_signals) + len(
            rejected_signals
        ),
        "signals_valid": len(valid_signals),
        "signals_rejected": len(rejected_signals),
        "maximum_signals_per_run": integration[
            "maximum_signals_per_run"
        ],
        "minimum_edge": integration["minimum_edge"],
        "position_creation_allowed": integration[
            "allow_position_creation"
        ],
        "positions_created": 0,
        "note": (
            "Signal validation only. "
            "No mock positions were created."
        ),
    }

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("SIGNAL VALIDATION COMPLETE")
    print("Signals read:", report["signals_read"])
    print("Valid signals:", report["signals_valid"])
    print("Rejected signals:", report["signals_rejected"])
    print("Positions created: 0")
    print("Valid signals:")
    print(valid_path)
    print("Rejected signals:")
    print(rejected_path)
    print("Report:")
    print(report_path)


if __name__ == "__main__":
    main()