from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "fixtures_master.csv"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "fixtures_validation.csv"
)

fixtures = pd.read_csv(INPUT_PATH)

print("FIXTURE VALIDATION")
print("Total fixture rows:", len(fixtures))

print("\nCOMPETITION COUNTS")
print(
    fixtures.groupby("competition")
    .size()
    .to_string()
)

# Find teams assigned to more than one competition.
team_competitions = pd.concat(
    [
        fixtures[
            [
                "home_team",
                "competition",
            ]
        ].rename(
            columns={
                "home_team": "team"
            }
        ),
        fixtures[
            [
                "away_team",
                "competition",
            ]
        ].rename(
            columns={
                "away_team": "team"
            }
        ),
    ],
    ignore_index=True,
)

team_competitions = (
    team_competitions.dropna(
        subset=["team"]
    )
    .drop_duplicates()
)

multi_competition_teams = (
    team_competitions.groupby("team")[
        "competition"
    ]
    .nunique()
    .loc[lambda values: values > 1]
)

multi_team_names = (
    multi_competition_teams.index.tolist()
)

print(
    "\nTEAMS ASSIGNED TO MULTIPLE COMPETITIONS:",
    len(multi_team_names),
)

if multi_team_names:
    print(
        team_competitions.loc[
            team_competitions["team"].isin(
                multi_team_names
            )
        ]
        .sort_values(
            ["team", "competition"]
        )
        .to_string(index=False)
    )

# Create a row-level validation table.
fixtures["team_conflict"] = (
    fixtures["home_team"].isin(
        multi_team_names
    )
    | fixtures["away_team"].isin(
        multi_team_names
    )
)

fixtures["needs_manual_review"] = (
    fixtures["team_conflict"]
)

fixtures.to_csv(
    OUTPUT_PATH,
    index=False,
)

print("\nROW-LEVEL VALIDATION")
print(
    fixtures.groupby(
        ["competition", "team_conflict"]
    )
    .size()
    .to_string()
)

print("\nFLAGGED FIXTURES")

flagged = fixtures.loc[
    fixtures["needs_manual_review"],
    [
        "scheduled_start_local",
        "competition",
        "home_team",
        "away_team",
        "stage",
        "matchday",
        "status",
    ],
]

print(
    flagged.to_string(index=False)
    if not flagged.empty
    else "No fixtures flagged."
)

print("\nSaved validation table:")
print(OUTPUT_PATH)

print("\nVALIDATION COMPLETE")