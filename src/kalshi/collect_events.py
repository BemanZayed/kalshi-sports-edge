import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


KALSHI_MODULE_DIR = Path(__file__).resolve().parent

if str(KALSHI_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_MODULE_DIR))

from pipeline_config import resolve_window


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = PROJECT_ROOT / "data" / "raw" / "kalshi" / "event_runs"
CONFIG_PATH = PROJECT_ROOT / "config" / "pipeline.json"


def load_collection_settings():
    with CONFIG_PATH.open(encoding="utf-8-sig") as handle:
        config = json.load(handle)

    if not isinstance(config, dict):
        raise ValueError("pipeline.json must contain a JSON object")

    if config.get("schema_version") != 1:
        raise ValueError("pipeline.json: schema_version must be 1")

    collection = config.get("collection")
    series_map = config.get("series_sport_map")

    if not isinstance(collection, dict):
        raise ValueError("pipeline.json: collection must be an object")

    if not isinstance(series_map, dict) or not series_map:
        raise ValueError(
            "pipeline.json: series_sport_map must be a non-empty object"
        )

    for series, sport in series_map.items():
        if not isinstance(series, str) or not series.strip():
            raise ValueError("pipeline.json: invalid series ticker")

        if series != series.strip():
            raise ValueError(
                f"pipeline.json: series ticker contains outer spaces: {series!r}"
            )

        if sport not in {"football", "tennis"}:
            raise ValueError(
                f"pipeline.json: unsupported sport for {series}: {sport}"
            )

    expected_url = "https://external-api.kalshi.com/trade-api/v2"

    if collection.get("base_url") != expected_url:
        raise ValueError(
            "pipeline.json: unexpected collection base_url"
        )

    max_pages = collection.get("max_pages_per_series")

    if type(max_pages) is not int or max_pages < 1:
        raise ValueError(
            "pipeline.json: max_pages_per_series must be a positive integer"
        )

    for field in (
        "request_delay_seconds",
        "request_timeout_seconds",
    ):
        value = collection.get(field)

        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(
                f"pipeline.json: {field} must be a finite positive number"
            )

    return config


PIPELINE_CONFIG = load_collection_settings()
COLLECTION_CONFIG = PIPELINE_CONFIG["collection"]

BASE_URL = COLLECTION_CONFIG["base_url"]
SERIES = list(PIPELINE_CONFIG["series_sport_map"])
MAX_PAGES_PER_SERIES = COLLECTION_CONFIG["max_pages_per_series"]
REQUEST_DELAY_SECONDS = COLLECTION_CONFIG["request_delay_seconds"]
REQUEST_TIMEOUT_SECONDS = COLLECTION_CONFIG["request_timeout_seconds"]


def save_json(path, data):
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main():
    started_at = datetime.now(timezone.utc)
    run_id = started_at.strftime("%Y%m%dT%H%M%S%fZ")

    resolved_window = resolve_window(
        PIPELINE_CONFIG,
        reference_time=started_at,
    )

    run_dir = RAW_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    manifest = {
        "run_id": run_id,
        "started_at_utc": started_at.isoformat(),
        "status": "running",
        "scope": "selected Kalshi series, not a complete fixture calendar",
        "pipeline_config": PIPELINE_CONFIG,
        "research_window": resolved_window,
        "series": {},
    }

    manifest_path = run_dir / "manifest.json"
    save_json(manifest_path, manifest)

    print("Run ID:", run_id)
    print(
        "Research window:",
        resolved_window["start_date_inclusive"],
        "through",
        resolved_window["end_date_inclusive"],
    )
    print("Calendar timezone:", resolved_window["calendar_timezone"])

    first_request = True

    try:
        with requests.Session() as session:
            for series in SERIES:
                series_dir = run_dir / series
                series_dir.mkdir()

                cursor = None
                seen_cursors = set()
                unique_events = set()

                stats = {
                    "complete": False,
                    "pages": 0,
                    "event_records": 0,
                    "unique_events": 0,
                }

                manifest["series"][series] = stats
                save_json(manifest_path, manifest)

                for page in range(1, MAX_PAGES_PER_SERIES + 1):
                    if not first_request:
                        time.sleep(REQUEST_DELAY_SECONDS)

                    first_request = False

                    params = {
                        "series_ticker": series,
                        "limit": 200,
                        "with_nested_markets": "true",
                        "with_milestones": "true",
                        "min_close_ts": int(started_at.timestamp()),
                    }

                    if cursor:
                        params["cursor"] = cursor

                    response = session.get(
                        f"{BASE_URL}/events",
                        params=params,
                        timeout=REQUEST_TIMEOUT_SECONDS,
                    )

                    try:
                        payload = response.json()
                    except ValueError:
                        payload = {"non_json_body": response.text}

                    save_json(
                        series_dir / f"page_{page:03d}.json",
                        {
                            "collected_at_utc": datetime.now(
                                timezone.utc
                            ).isoformat(),
                            "request_url": response.url,
                            "http_status": response.status_code,
                            "payload": payload,
                        },
                    )

                    print(
                        f"{series} | page {page} | "
                        f"HTTP {response.status_code}"
                    )

                    response.raise_for_status()

                    if not isinstance(payload, dict):
                        raise ValueError(
                            f"Unexpected response object for {series}"
                        )

                    events = payload.get("events")

                    if not isinstance(events, list):
                        raise ValueError(
                            f"Unexpected events response for {series}"
                        )

                    stats["pages"] = page
                    stats["event_records"] += len(events)

                    unique_events.update(
                        event["event_ticker"]
                        for event in events
                        if event.get("event_ticker")
                    )

                    stats["unique_events"] = len(unique_events)
                    next_cursor = payload.get("cursor")

                    if not next_cursor:
                        stats["complete"] = True
                        save_json(manifest_path, manifest)
                        break

                    if not isinstance(next_cursor, str):
                        raise ValueError(
                            f"Unexpected pagination cursor for {series}"
                        )

                    if next_cursor in seen_cursors:
                        raise RuntimeError(
                            f"Repeated pagination cursor for {series}"
                        )

                    seen_cursors.add(next_cursor)
                    cursor = next_cursor

                    save_json(manifest_path, manifest)

                if not stats["complete"]:
                    raise RuntimeError(
                        f"Page safety limit reached for {series}. "
                        "Collection is incomplete."
                    )

        manifest["status"] = "complete"

    except Exception as error:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(error).__name__}: {error}"
        raise

    finally:
        manifest["finished_at_utc"] = datetime.now(
            timezone.utc
        ).isoformat()

        save_json(manifest_path, manifest)
        print("\nRun folder:", run_dir)

    print("\nCOLLECTION SUMMARY")

    for series, stats in manifest["series"].items():
        print(
            f"{series}: "
            f"{stats['unique_events']} unique events, "
            f"{stats['pages']} pages, "
            f"complete={stats['complete']}"
        )

    print("\nCOLLECTION COMPLETE")
    print("Complete means pagination finished for the selected query.")
    print("It does not mean all fixtures or all sports were covered.")


if __name__ == "__main__":
    main()