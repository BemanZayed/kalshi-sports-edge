import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ARCHIVE_ROOT = PROJECT_ROOT / "archive"
MANIFEST_PATH = ARCHIVE_ROOT / "archive_manifest.json"

LEGACY_FILES = [
    "project_inventory.txt",
    "src/test_setup.py",
    "src/kalshi/clean_tennis_sample.py",
    "src/kalshi/discover_football_series.py",
    "src/kalshi/discover_sports_series.py",
    "src/kalshi/inspect_api.py",
    "src/kalshi/inspect_football_events.py",
    "src/kalshi/inspect_series_scopes.py",
    "src/kalshi/inspect_tennis_events.py",
    "src/kalshi/organise_sports_series.py",
    "data/processed/fixture_market_attachment_review.csv",
    "data/processed/fixture_market_snapshots.csv",
    "data/processed/fixtures_market_summary.csv",
    "data/processed/fixtures_master.csv",
    "data/processed/fixtures_validation.csv",
    "data/processed/fixtures_with_kalshi.csv",
    "data/processed/fixtures_without_saved_kalshi_candidate.csv",
    "data/processed/kalshi_events_without_fixture_candidate.csv",
    "data/processed/kalshi_fixture_candidates.csv",
    "data/processed/kalshi_fixture_join_review.csv",
    "data/processed/kalshi_football_series_candidates.csv",
    "data/processed/kalshi_football_tennis_series.csv",
    "data/processed/kalshi_game_series_candidates.csv",
    "data/processed/kalshi_join_summary.csv",
    "data/processed/kalshi_scope_summary.csv",
    "data/processed/kalshi_series_family_summary.csv",
    "data/processed/kalshi_sports_series.csv",
    "data/processed/kalshi_sports_series_candidates.csv",
    "data/processed/kalshi_sports_series_catalogue.csv",
    "data/processed/kalshi_sports_tag_counts.csv",
    "data/processed/kalshi_unknown_team_aliases.csv",
    "data/processed/research_calendar_markets_long.csv",
    "data/processed/tennis_fixtures_template.csv",
    "data/processed/tennis_market_attachment_review.csv",
    "data/processed/tennis_market_audit_summary.csv",
    "data/processed/tennis_market_candidates.csv",
    "data/processed/tennis_market_quality.csv",
]


def main():
    ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)

    moved = []
    already_archived = []
    missing = []

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )

    for relative_path in LEGACY_FILES:
        source = PROJECT_ROOT / relative_path

        if not source.exists():
            missing.append(relative_path)
            continue

        destination = (
            ARCHIVE_ROOT
            / timestamp
            / relative_path
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if destination.exists():
            already_archived.append(relative_path)
            continue

        shutil.move(str(source), str(destination))

        moved.append(
            {
                "original_path": relative_path,
                "archived_path": str(
                    destination.relative_to(PROJECT_ROOT)
                ),
            }
        )

    manifest = {
        "archive_run_id": timestamp,
        "created_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "files_moved": moved,
        "files_already_archived": already_archived,
        "files_missing": missing,
        "files_deleted": [],
        "raw_data_touched": False,
    }

    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("LEGACY FILE ARCHIVE COMPLETE")
    print("Files moved:", len(moved))
    print("Files already archived:", len(already_archived))
    print("Files missing:", len(missing))
    print("Files deleted: 0")
    print("Raw data touched: False")
    print("Manifest:")
    print(MANIFEST_PATH)

    if missing:
        print("\nMissing files:")
        for item in missing:
            print("-", item)


if __name__ == "__main__":
    main()