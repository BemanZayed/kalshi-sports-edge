import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_DIR = PROJECT_ROOT / "config"
RAW_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "football_data"
)

OUT_DIR = PROJECT_ROOT / "data" / "processed"

RAW_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# FIXTURE WINDOW
# November 21 through December 5, inclusive, Amsterdam time.
# ============================================================

TIMEZONE = "Europe/Amsterdam"

START_DATE = "2026-11-22"
END_DATE_INCLUSIVE = "2026-12-05"

START_LOCAL = pd.Timestamp(START_DATE, tz=TIMEZONE)

END_LOCAL_EXCLUSIVE = (
    pd.Timestamp(END_DATE_INCLUSIVE, tz=TIMEZONE)
    + pd.DateOffset(days=1)
)

START_UTC = START_LOCAL.tz_convert("UTC")
END_UTC_EXCLUSIVE = END_LOCAL_EXCLUSIVE.tz_convert("UTC")


# ============================================================
# FOOTBALL COMPETITIONS
# football-data.org competition codes.
# DED is Eredivisie, not Bundesliga.
# BL1 is Bundesliga.
# ============================================================

COMPETITIONS = {
    "PL": {
        "name": "Premier League",
        "country": "England",
        "level": "top_flight",
    },
    "ELC": {
        "name": "EFL Championship",
        "country": "England",
        "level": "second_tier",
    },
    "BL1": {
        "name": "Bundesliga",
        "country": "Germany",
        "level": "top_flight",
    },
    "PD": {
        "name": "La Liga",
        "country": "Spain",
        "level": "top_flight",
    },
    "SA": {
        "name": "Serie A",
        "country": "Italy",
        "level": "top_flight",
    },
    "FL1": {
        "name": "Ligue 1",
        "country": "France",
        "level": "top_flight",
    },
}


# ============================================================
# HELPERS
# ============================================================

def load_token():
    token_path = CONFIG_DIR / "football_data_token.txt"

    if not token_path.exists():
        raise FileNotFoundError(
            "Missing API token. Create:\n"
            "config\\football_data_token.txt\n"
            "and paste only your football-data.org token "
            "into that file."
        )

    token = token_path.read_text(
        encoding="utf-8"
    ).strip()

    if not token:
        raise ValueError(
            "The token file is empty."
        )

    return token


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def save_response(
    competition_code,
    page_number,
    payload,
):
    run_time = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%S")

    run_dir = (
        RAW_DIR
        / f"{run_time}_{START_DATE}_{END_DATE_INCLUSIVE}"
    )

    run_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    competition_dir = run_dir / competition_code

    competition_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        competition_dir
        / f"page_{page_number:03d}.json"
    )

    output_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return run_dir, output_path


def request_matches(
    token,
    competition_code,
):
    url = (
        "https://api.football-data.org/v4/competitions/"
        f"{competition_code}/matches"
    )

    headers = {
        "X-Auth-Token": token,
    }

    params = {
        "dateFrom": START_DATE,
        "dateTo": END_DATE_INCLUSIVE,
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"HTTP {response.status_code} for "
            f"{competition_code}: {response.text}"
        )

    return response.json()


def parse_match(
    competition_code,
    competition_info,
    match,
):
    utc_date = match.get("utcDate")

    kickoff_utc = (
        pd.to_datetime(utc_date, utc=True)
        if utc_date
        else pd.NaT
    )

    kickoff_local = (
        kickoff_utc.tz_convert(TIMEZONE)
        if pd.notna(kickoff_utc)
        else pd.NaT
    )

    home = match.get("homeTeam") or {}
    away = match.get("awayTeam") or {}
    competition = match.get("competition") or {}
    season = match.get("season") or {}

    stage = match.get("stage")

    if isinstance(stage, dict):
        stage_name = stage.get("stage")
    else:
        stage_name = stage

    return {
        "sport": "football",
        "competition_code": competition_code,
        "competition": competition_info["name"],
        "competition_country": competition_info[
            "country"
        ],
        "competition_level": competition_info[
            "level"
        ],
        "source_competition_code": competition.get(
            "code"
        ),
        "source_competition_name": competition.get(
            "name"
        ),
        "season": season.get("startDate"),
        "match_id": match.get("id"),
        "scheduled_start_utc": kickoff_utc,
        "scheduled_start_local": (
            kickoff_local.isoformat()
            if pd.notna(kickoff_local)
            else None
        ),
        "home_team": home.get("name"),
        "away_team": away.get("name"),
        "home_team_id": home.get("id"),
        "away_team_id": away.get("id"),
        "stage": stage_name,
        "matchday": match.get("matchday"),
        "status": match.get("status"),
        "venue": match.get("venue"),
        "source_name": "football-data.org",
        "source_url": (
            "https://api.football-data.org/v4/"
            f"competitions/{competition_code}/matches"
        ),
        "source_retrieved_at_utc": utc_now_iso(),
        "schedule_independently_verified": False,
        "kalshi_event_ticker": "",
        "kalshi_market_count": pd.NA,
    }


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():
    token = load_token()

    print("Football fixture calendar")
    print("Source: football-data.org")
    print(
        "Window:",
        START_DATE,
        "through",
        END_DATE_INCLUSIVE,
        "inclusive,",
        TIMEZONE,
    )

    all_matches = []
    run_dirs = set()

    for index, (
        competition_code,
        competition_info,
    ) in enumerate(
        COMPETITIONS.items(),
        start=1,
    ):
        print(
            f"\nCollecting {competition_info['name']} "
            f"({competition_code})..."
        )

        payload = request_matches(
            token,
            competition_code,
        )

        run_dir, output_path = save_response(
            competition_code,
            index,
            payload,
        )

        run_dirs.add(run_dir)

        matches = payload.get("matches") or []

        returned_competition = (
            payload.get("competition") or {}
        )

        returned_code = (
            returned_competition.get("code")
        )

        if returned_code != competition_code:
            raise ValueError(
                f"Competition mismatch for "
                f"{competition_code}: API returned "
                f"{returned_code} "
                f"({returned_competition.get('name')})"
            )

        print(
            f"Matches returned: {len(matches)}"
        )

        for match in matches:
            all_matches.append(
                parse_match(
                    competition_code,
                    competition_info,
                    match,
                )
            )

        # Stay below the documented free-plan rate limit.
        time.sleep(7)

    if not all_matches:
        raise ValueError(
            "No football matches were returned."
        )

    fixtures = pd.DataFrame(all_matches)

    fixtures["scheduled_start_utc"] = pd.to_datetime(
        fixtures["scheduled_start_utc"],
        utc=True,
        errors="coerce",
    )

    fixtures["kalshi_market_count"] = pd.to_numeric(
        fixtures["kalshi_market_count"],
        errors="coerce",
    )

    fixtures = fixtures.sort_values(
        [
            "scheduled_start_utc",
            "competition",
            "home_team",
            "away_team",
        ]
    )

    if fixtures["match_id"].duplicated().any():
        duplicates = fixtures.loc[
            fixtures["match_id"].duplicated(
                keep=False
            ),
            "match_id",
        ].unique()

        raise ValueError(
            "Duplicate match IDs found: "
            f"{', '.join(map(str, duplicates))}"
        )

    output_path = OUT_DIR / "fixtures_master.csv"

    fixtures.to_csv(
        output_path,
        index=False,
    )

    manifest = {
        "source": "football-data.org",
        "collected_at_utc": utc_now_iso(),
        "calendar_timezone": TIMEZONE,
        "start_date_inclusive": START_DATE,
        "end_date_inclusive": END_DATE_INCLUSIVE,
        "start_utc": START_UTC.isoformat(),
        "end_utc_exclusive": (
            END_UTC_EXCLUSIVE.isoformat()
        ),
        "competitions": COMPETITIONS,
        "raw_run_directories": [
            str(path) for path in sorted(run_dirs)
        ],
        "total_matches_collected": len(fixtures),
        "schedule_independently_verified": False,
    }

    (
        RAW_DIR
        / "latest_fixture_run.json"
    ).write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\nFIXTURE SUMMARY")
    print("Total matches:", len(fixtures))

    print("\nBY COMPETITION")
    print(
        fixtures.groupby("competition")
        .size()
        .to_string()
    )

    print("\nBY DATE")
    print(
        fixtures.assign(
            local_date=fixtures[
                "scheduled_start_local"
            ].str[:10]
        )
        .groupby("local_date")
        .size()
        .to_string()
    )

    print("\nUPCOMING FIXTURES")
    print(
        fixtures[
            [
                "scheduled_start_local",
                "competition",
                "home_team",
                "away_team",
            ]
        ].to_string(index=False)
    )

    print("\nSaved master calendar:")
    print(output_path)

    print(
        "\nThis is a source-reported fixture calendar. "
        "It has not yet been independently verified."
    )

    print("\nFOOTBALL FIXTURE COLLECTION COMPLETE")


if __name__ == "__main__":
    main()