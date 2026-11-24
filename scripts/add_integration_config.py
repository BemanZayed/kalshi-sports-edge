import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "simulator.json"
BACKUP_DIR = PROJECT_ROOT / "backups" / "simulator_config"


def main():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(CONFIG_PATH)

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )

    backup_path = BACKUP_DIR / f"simulator_{timestamp}.json"
    shutil.copy2(CONFIG_PATH, backup_path)

    config = json.loads(
        CONFIG_PATH.read_text(encoding="utf-8-sig")
    )

    if "integration" in config:
        print("Integration settings already exist.")
        print("No changes were made.")
        return

    config["integration"] = {
        "enabled": False,
        "signal_file": "data/integration/model_signals.csv",
        "require_model_probability": True,
        "require_market_match": True,
        "allow_position_creation": False,
        "minimum_edge": 0.03,
        "maximum_signals_per_run": 100,
        "require_model_version": True,
        "require_features_version": True
    }

    CONFIG_PATH.write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("INTEGRATION SAFETY GATE ADDED")
    print("Backup created:")
    print(backup_path)
    print("Updated configuration:")
    print(CONFIG_PATH)
    print()
    print("integration.enabled = False")
    print("allow_position_creation = False")
    print("allow_real_orders = False")
    print()
    print("No mock positions were created.")


if __name__ == "__main__":
    main()