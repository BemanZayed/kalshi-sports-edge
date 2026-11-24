import shutil
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
SIMULATOR_DIR = PROCESSED_DIR / "simulator"
SAMPLE_DIR = PROJECT_ROOT / "data" / "samples"

SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_FILES = [
    (
        PROCESSED_DIR / "kalshi_events_clean.csv",
        SAMPLE_DIR / "kalshi_events_clean_sample.csv",
    ),
    (
        PROCESSED_DIR / "kalshi_market_snapshots.csv",
        SAMPLE_DIR / "kalshi_market_snapshots_sample.csv",
    ),
    (
        PROCESSED_DIR / "kalshi_calendar_candidates.csv",
        SAMPLE_DIR / "kalshi_calendar_candidates_sample.csv",
    ),
    (
        PROCESSED_DIR / "kalshi_calendar_market_snapshots.csv",
        SAMPLE_DIR / "kalshi_calendar_market_snapshots_sample.csv",
    ),
    (
        PROCESSED_DIR / "kalshi_calendar_settings.json",
        SAMPLE_DIR / "kalshi_calendar_settings.json",
    ),
    (
        SIMULATOR_DIR / "candidate_audit_favorite_back.csv",
        SAMPLE_DIR / "candidate_audit_favorite_back_sample.csv",
    ),
    (
        SIMULATOR_DIR / "candidate_audit_longshot_back.csv",
        SAMPLE_DIR / "candidate_audit_longshot_back_sample.csv",
    ),
    (
        SIMULATOR_DIR / "selected_candidates_favorite_back.csv",
        SAMPLE_DIR / "selected_candidates_favorite_back_sample.csv",
    ),
    (
        SIMULATOR_DIR / "selected_candidates_longshot_back.csv",
        SAMPLE_DIR / "selected_candidates_longshot_back_sample.csv",
    ),
]

ROW_LIMIT = 25


def main():
    copied = []
    missing = []

    for source, destination in SAMPLE_FILES:
        if not source.exists():
            missing.append(str(source.relative_to(PROJECT_ROOT)))
            continue

        if source.suffix.lower() == ".csv":
            frame = pd.read_csv(source)

            if frame.empty:
                sample = frame
            else:
                sample = frame.head(ROW_LIMIT)

            sample.to_csv(destination, index=False)
        else:
            shutil.copy2(source, destination)

        copied.append(
            str(destination.relative_to(PROJECT_ROOT))
        )

    print("DATA SAMPLES CREATED")
    print("Files copied:", len(copied))
    print("Missing source files:", len(missing))

    for item in copied:
        print("-", item)

    if missing:
        print("\nMissing files:")
        for item in missing:
            print("-", item)

    print("\nThese are small reference samples only.")
    print("The full processed data remains local and is not committed.")


if __name__ == "__main__":
    main()