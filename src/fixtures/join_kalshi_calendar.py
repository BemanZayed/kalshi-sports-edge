import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

TIMEZONE = "Europe/Amsterdam"
START_DATE = "2026-11-22"
END_DATE_INCLUSIVE = "2026-12-05"
CANDIDATE_WINDOW_HOURS = 48
CONFIG = json.loads(r'''{"BL1": {"series": "KXBUNDESLIGAGAME", "aliases": {"Augsburg": "FC Augsburg", "Bayern Munich": "FC Bayern M\u00fcnchen", "Bremen": "SV Werder Bremen", "Dortmund": "Borussia Dortmund", "Elversberg": "SV 07 Elversberg", "Frankfurt": "Eintracht Frankfurt", "Freiburg": "SC Freiburg", "Hamburg": "Hamburger SV", "Hoffenheim": "TSG 1899 Hoffenheim", "FC K\u00f6ln": "1. FC K\u00f6ln", "Leipzig": "RB Leipzig", "Leverkusen": "Bayer 04 Leverkusen", "Mainz": "1. FSV Mainz 05", "M\u00b4gladbach": "Borussia M\u00f6nchengladbach", "Paderborn": "SC Paderborn 07", "Schalke": "FC Schalke 04", "Stuttgart": "VfB Stuttgart", "Union Berlin": "1. FC Union Berlin"}}, "PL": {"series": "KXEPLGAME", "aliases": {"Arsenal": "Arsenal FC", "Aston Villa": "Aston Villa FC", "Bournemouth": "AFC Bournemouth", "Brentford": "Brentford FC", "Brighton": "Brighton & Hove Albion FC", "Chelsea": "Chelsea FC", "Coventry": "Coventry City FC", "Crystal Palace": "Crystal Palace FC", "Everton": "Everton FC", "Fulham": "Fulham FC", "Hull City": "Hull City AFC", "Ipswich Town": "Ipswich Town FC", "Leeds United": "Leeds United FC", "Liverpool": "Liverpool FC", "Manchester City": "Manchester City FC", "Manchester United": "Manchester United FC", "Newcastle": "Newcastle United FC", "Nottingham Forest": "Nottingham Forest FC", "Sunderland": "Sunderland AFC", "Tottenham": "Tottenham Hotspur FC"}}, "ELC": {"series": "KXEFLCHAMPIONSHIPGAME", "aliases": {"Birmingham": "Birmingham City FC", "Blackburn": "Blackburn Rovers FC", "Bolton": "Bolton Wanderers FC", "Bristol City": "Bristol City FC", "Burnley": "Burnley FC", "Cardiff": "Cardiff City FC", "Charlton": "Charlton Athletic FC", "Derby": "Derby County FC", "Lincoln": "Lincoln City FC", "Middlesbrough": "Middlesbrough FC", "Millwall": "Millwall FC", "Norwich": "Norwich City FC", "Portsmouth": "Portsmouth FC", "Preston": "Preston North End FC", "QPR": "Queens Park Rangers FC", "Sheffield United": "Sheffield United FC", "Southampton": "Southampton FC", "Stoke": "Stoke City FC", "Swansea": "Swansea City AFC", "Watford": "Watford FC", "West Bromwich": "West Bromwich Albion FC", "West Ham": "West Ham United FC", "Wolverhampton": "Wolverhampton Wanderers FC", "Wrexham": "Wrexham AFC"}}, "PD": {"series": "KXLALIGAGAME", "aliases": {"Alaves": "Deportivo Alav\u00e9s", "Atletico": "Club Atl\u00e9tico de Madrid", "Barcelona": "FC Barcelona", "Bilbao": "Athletic Club", "Celta Vigo": "RC Celta de Vigo", "Deportivo De La Coruna": "RC Deportivo La Coru\u00f1a", "Elche": "Elche CF", "Espanyol": "RCD Espanyol de Barcelona", "Getafe": "Getafe CF", "Levante": "Levante UD", "Malaga": "M\u00e1laga CF", "Osasuna": "CA Osasuna", "Real Betis": "Real Betis Balompi\u00e9", "Real Madrid": "Real Madrid CF", "Real Sociedad": "Real Sociedad de F\u00fatbol", "Santander": "Real Racing Club de Santander", "Sevilla": "Sevilla FC", "Valencia": "Valencia CF", "Vallecano": "Rayo Vallecano de Madrid", "Villarreal": "Villarreal CF"}}, "SA": {"series": "KXSERIEAGAME", "aliases": {"Atalanta": "Atalanta BC", "Bologna": "Bologna FC 1909", "Cagliari": "Cagliari Calcio", "Como": "Como 1907", "Fiorentina": "ACF Fiorentina", "Frosinone": "Frosinone Calcio", "Genoa": "Genoa CFC", "Inter": "FC Internazionale Milano", "Juventus": "Juventus FC", "Lazio": "SS Lazio", "Lecce": "US Lecce", "Milan": "AC Milan", "Monza": "AC Monza", "Napoli": "SSC Napoli", "Parma Calcio": "Parma Calcio 1913", "Roma": "AS Roma", "Sassuolo": "US Sassuolo Calcio", "Torino": "Torino FC", "Udinese": "Udinese Calcio", "Venezia": "Venezia FC"}}, "FL1": {"series": "KXLIGUE1GAME", "aliases": {"Angers": "Angers SCO", "Auxerre": "AJ Auxerre", "Le Havre": "Le Havre AC", "Le Mans": "Le Mans FC", "Lens": "Racing Club de Lens", "Lille": "Lille OSC", "Lorient": "FC Lorient", "Lyon": "Olympique Lyonnais", "Marseille": "Olympique de Marseille", "Monaco": "AS Monaco FC", "Nice": "OGC Nice", "Paris FC": "Paris FC", "PSG": "Paris Saint-Germain FC", "Stade Brest 29": "Stade Brestois 29", "Stade Rennais": "Stade Rennais FC 1901", "Strasbourg Alsace": "RC Strasbourg Alsace", "Toulouse": "Toulouse FC", "Troyes": "ES Troyes AC"}}}''')


def normalize(value):
    text = unicodedata.normalize("NFKD", str(value).casefold())
    return re.sub(r"[^a-z0-9]", "", text)


def run(fixtures_path, kalshi_path, output_dir):
    fixtures = pd.read_csv(fixtures_path)
    kalshi = pd.read_csv(kalshi_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    required = {
        "fixtures": (fixtures, ["match_id", "competition_code", "home_team", "away_team", "scheduled_start_utc"]),
        "kalshi": (kalshi, ["event_ticker", "series_ticker", "event_title", "scheduled_start_utc", "market_count"]),
    }
    for label, (frame, columns) in required.items():
        missing = set(columns) - set(frame.columns)
        if missing:
            raise ValueError(f"{label}: missing columns {sorted(missing)}")
    for frame, column in [(fixtures, "match_id"), (kalshi, "event_ticker")]:
        if frame[column].isna().any() or frame[column].duplicated().any():
            raise ValueError(f"Missing or duplicate {column}")

    lower = pd.Timestamp(START_DATE, tz=TIMEZONE).tz_convert("UTC")
    upper = (pd.Timestamp(END_DATE_INCLUSIVE, tz=TIMEZONE) + pd.DateOffset(days=1)).tz_convert("UTC")
    result = fixtures.copy()
    result["fixture_start_utc"] = pd.to_datetime(result["scheduled_start_utc"], utc=True, errors="coerce")
    result["fixture_start_local"] = result["fixture_start_utc"].dt.tz_convert(TIMEZONE).astype("string")
    result["fixture_in_research_window"] = result["fixture_start_utc"].ge(lower) & result["fixture_start_utc"].lt(upper)
    result["join_status"] = "not_in_current_join_scope"
    for col in ["kalshi_event_ticker", "kalshi_event_title", "kalshi_run_id", "matched_team_pair_basis"]:
        result[col] = pd.Series(pd.NA, index=result.index, dtype="string")
    result["kalshi_market_count"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    result["kalshi_candidate_count"] = 0
    result["kalshi_start_utc"] = pd.Series(pd.NaT, index=result.index, dtype="datetime64[ns, UTC]")
    result["start_difference_minutes"] = float("nan")
    result["home_away_alignment_verified"] = False
    kalshi["_start"] = pd.to_datetime(kalshi["scheduled_start_utc"], utc=True, errors="coerce")
    unknown, candidates, audit, uses = [], [], [], {}

    for code, config in CONFIG.items():
        lookup = {}
        for alias, canonical in config["aliases"].items():
            for name in [alias, canonical]:
                key = normalize(name)
                if key in lookup and lookup[key] != canonical:
                    raise ValueError(f"Alias collision: {code} {name}")
                lookup[key] = canonical

        def identify(name, source, record_id):
            value = lookup.get(normalize(name))
            if value is None:
                unknown.append({"competition_code": code, "source": source, "record_id": record_id, "team_name": name})
            return value

        events = []
        for _, event in kalshi.loc[kalshi["series_ticker"] == config["series"]].iterrows():
            item = event.to_dict()
            parts = re.split(r"\s+vs\.?\s+", str(event["event_title"]).strip(), flags=re.I)
            item["_pair"] = None
            item["_issue"] = "unrecognized_title_format"
            if len(parts) == 2:
                teams = [identify(name, "kalshi", event["event_ticker"]) for name in parts]
                item["_issue"] = "unknown_team_alias"
                if all(teams):
                    item["_pair"] = tuple(sorted(teams))
                    item["_issue"] = ""
            events.append(item)

        for idx, fixture in result.loc[result["competition_code"] == code].iterrows():
            start = fixture["fixture_start_utc"]
            if pd.isna(start):
                result.at[idx, "join_status"] = "review_missing_fixture_start"
                continue
            if not fixture["fixture_in_research_window"]:
                result.at[idx, "join_status"] = "outside_research_window"
                continue
            teams = [identify(fixture[c], "fixtures", fixture["match_id"]) for c in ["home_team", "away_team"]]
            if not all(teams):
                result.at[idx, "join_status"] = "review_unknown_fixture_alias"
                continue
            pair = tuple(sorted(teams))
            found = []
            for event in events:
                if event["_pair"] != pair:
                    continue
                event_start = event["_start"]
                diff = float("nan") if pd.isna(event_start) else (event_start - start).total_seconds() / 60
                if pd.notna(diff) and abs(diff) > CANDIDATE_WINDOW_HOURS * 60:
                    continue
                found.append((event, diff))
                uses.setdefault(event["event_ticker"], set()).add(idx)
                candidates.append({"competition_code": code, "match_id": fixture["match_id"], "home_team": fixture["home_team"], "away_team": fixture["away_team"], "fixture_start_utc": start, "kalshi_event_ticker": event["event_ticker"], "kalshi_event_title": event["event_title"], "kalshi_start_utc": event_start, "start_difference_minutes": diff})
            result.at[idx, "kalshi_candidate_count"] = len(found)
            if not found:
                result.at[idx, "join_status"] = "no_candidate_in_saved_kalshi_data"
            elif len(found) > 1:
                result.at[idx, "join_status"] = "review_multiple_candidates"
            else:
                event, diff = found[0]
                for output, source in [("kalshi_event_ticker", "event_ticker"), ("kalshi_event_title", "event_title"), ("kalshi_run_id", "run_id")]:
                    result.at[idx, output] = event.get(source, pd.NA)
                result.at[idx, "kalshi_start_utc"] = event["_start"]
                count = pd.to_numeric(event["market_count"], errors="coerce")
                if pd.notna(count):
                    result.at[idx, "kalshi_market_count"] = int(count)
                result.at[idx, "start_difference_minutes"] = diff
                result.at[idx, "matched_team_pair_basis"] = "explicit_alias_unordered_pair"
                result.at[idx, "join_status"] = ("review_missing_kalshi_start" if pd.isna(event["_start"]) else "matched_pair_and_start" if diff == 0 else "review_start_difference")

        for event in events:
            if event["event_ticker"] not in uses:
                start = event["_start"]
                reason = event["_issue"] or ("missing_kalshi_start" if pd.isna(start) else "outside_research_window" if not lower <= start < upper else "no_fixture_candidate_within_window")
                audit.append({"competition_code": code, "event_ticker": event["event_ticker"], "event_title": event["event_title"], "kalshi_start_utc": start, "reason": reason})

    for ticker, indices in uses.items():
        if len(indices) > 1:
            for idx in indices:
                result.at[idx, "join_status"] = "review_event_reused_across_fixtures"
    result["kalshi_start_local"] = result["kalshi_start_utc"].dt.tz_convert(TIMEZONE).astype("string")
    review = result.loc[result["join_status"].str.startswith("review_")].copy()
    unmatched = result.loc[result["join_status"] == "no_candidate_in_saved_kalshi_data"].copy()
    unknown_df = pd.DataFrame(unknown, columns=["competition_code", "source", "record_id", "team_name"]).drop_duplicates()
    candidate_df = pd.DataFrame(candidates, columns=["competition_code", "match_id", "home_team", "away_team", "fixture_start_utc", "kalshi_event_ticker", "kalshi_event_title", "kalshi_start_utc", "start_difference_minutes"])
    audit_df = pd.DataFrame(audit, columns=["competition_code", "event_ticker", "event_title", "kalshi_start_utc", "reason"])
    summary = result.groupby(["competition_code", "join_status"]).size().unstack(fill_value=0)
    assert len(result) == len(fixtures)
    for name, frame in {"fixtures_with_kalshi.csv": result, "kalshi_fixture_candidates.csv": candidate_df, "kalshi_fixture_join_review.csv": review, "kalshi_unknown_team_aliases.csv": unknown_df, "kalshi_events_without_fixture_candidate.csv": audit_df, "fixtures_without_saved_kalshi_candidate.csv": unmatched}.items():
        frame.to_csv(output_dir / name, index=False)
    summary.to_csv(output_dir / "kalshi_join_summary.csv")
    print("JOIN SUMMARY")
    print("Research window:", START_DATE, "through", END_DATE_INCLUSIVE)
    print("Independent fixture rows preserved:", len(result))
    print("Matched pair and exact start:", (result.join_status == "matched_pair_and_start").sum())
    print("No saved Kalshi candidate:", len(unmatched))
    print("Fixtures requiring review:", len(review))
    print("Unknown alias records:", len(unknown_df))
    print("\nBY COMPETITION")
    print(summary.to_string())
    print("\nUNMATCHED FIXTURES")
    print(unmatched[["competition_code", "home_team", "away_team", "fixture_start_local"]].to_string(index=False))
    print("\nSaved tables:", output_dir)
    print("Team-pair agreement does not verify home/away market alignment.")
    print("No candidate means absent from this saved collection, not necessarily absent from Kalshi.")
    print("JOIN COMPLETE")
    return result, summary


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    folder = root / "data" / "processed"
    run(folder / "fixtures_master.csv", folder / "kalshi_events_clean.csv", folder)
