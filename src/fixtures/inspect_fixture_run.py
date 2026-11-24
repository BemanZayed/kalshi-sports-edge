import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "football_data"
)

manifest_path = RAW_DIR / "latest_fixture_run.json"

manifest = json.loads(
    manifest_path.read_text(encoding="utf-8")
)

run_dirs = manifest["raw_run_directories"]

rows = []

for run_dir in run_dirs:
    run_path = Path(run_dir)

    for page_path in sorted(
        run_path.glob("*/*.json")
    ):
        payload = json.loads(
            page_path.read_text(
                encoding="utf-8"
            )
        )

        competition = payload.get(
            "competition"
        ) or {}

        matches = payload.get("matches") or []

        for match in matches:
            home = match.get("homeTeam") or {}
            away = match.get("awayTeam") or {}

            rows.append(
                {
                    "saved_file": str(
                        page_path.relative_to(
                            RAW_DIR
                        )
                    ),
                    "requested_competition_code": (
                        page_path.parent.name
                    ),
                    "returned_competition_code": (
                        competition.get("code")
                    ),
                    "returned_competition_name": (
                        competition.get("name")
                    ),
                    "match_id": match.get("id"),
                    "utc_date": match.get(
                        "utcDate"
                    ),
                    "home_team": home.get("name"),
                    "away_team": away.get("name"),
                    "stage": match.get("stage"),
                    "matchday": match.get(
                        "matchday"
                    ),
                    "status": match.get("status"),
                }
            )

df = pd.DataFrame(rows)

print("RAW RESPONSE INSPECTION")
print("Total inspected rows:", len(df))

print("\nRETURNED COMPETITION CODES")
print(
    df[
        [
            "requested_competition_code",
            "returned_competition_code",
            "returned_competition_name",
        ]
    ]
    .drop_duplicates()
    .to_string(index=False)
)

print("\nSAMPLE MATCHES BY REQUESTED CODE")

for code, group in df.groupby(
    "requested_competition_code"
):
    print(f"\n--- {code} ---")
    print(
        group[
            [
                "utc_date",
                "home_team",
                "away_team",
                "stage",
                "matchday",
                "status",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )

print("\nINSPECTION COMPLETE")