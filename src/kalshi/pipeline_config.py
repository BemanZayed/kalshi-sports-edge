import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "pipeline.json"


def load_config():
    with CONFIG_PATH.open(encoding="utf-8-sig") as handle:
        config = json.load(handle)

    if not isinstance(config, dict):
        raise ValueError("pipeline.json must contain a JSON object")

    if config.get("schema_version") != 1:
        raise ValueError("pipeline.json: schema_version must be 1")

    return config


def resolve_window(config, reference_time=None):
    """
    Resolve the research window once using a timezone-aware reference time.

    Rolling mode includes the reference local date and days - 1 further dates.
    Fixed mode includes both configured endpoint dates.
    """
    timezone_name = config.get("timezone")

    if not isinstance(timezone_name, str) or not timezone_name.strip():
        raise ValueError("pipeline.json: timezone is required")

    window = config.get("window")

    if not isinstance(window, dict):
        raise ValueError("pipeline.json: window must be an object")

    if reference_time is None:
        reference_time = datetime.now(timezone.utc)

    reference = pd.Timestamp(reference_time)

    if pd.isna(reference) or reference.tzinfo is None:
        raise ValueError("reference_time must be a valid timezone-aware time")

    reference_local = reference.tz_convert(timezone_name)
    mode = window.get("mode")

    if mode == "rolling":
        days = window.get("days")

        if type(days) is not int or days < 1:
            raise ValueError(
                "pipeline.json: window.days must be a positive integer"
            )

        start_date = reference_local.date()
        start_local = pd.Timestamp(start_date, tz=timezone_name)
        end_local_exclusive = start_local + pd.DateOffset(days=days)

    elif mode == "fixed":
        boundaries = []

        for key in (
            "fixed_start_date",
            "fixed_end_date_inclusive",
        ):
            value = window.get(key)

            if not isinstance(value, str):
                raise ValueError(f"pipeline.json: {key} must be YYYY-MM-DD")

            try:
                parsed = datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError as error:
                raise ValueError(
                    f"pipeline.json: {key} must be YYYY-MM-DD"
                ) from error

            if parsed.isoformat() != value:
                raise ValueError(f"pipeline.json: {key} must be YYYY-MM-DD")

            boundaries.append(pd.Timestamp(parsed, tz=timezone_name))

        start_local, end_local_inclusive = boundaries

        if end_local_inclusive < start_local:
            raise ValueError("pipeline.json: end date precedes start date")

        end_local_exclusive = end_local_inclusive + pd.DateOffset(days=1)

    else:
        raise ValueError(
            "pipeline.json: window.mode must be 'rolling' or 'fixed'"
        )

    end_local_inclusive = end_local_exclusive - pd.DateOffset(days=1)

    return {
        "window_mode": mode,
        "resolved_at_utc": reference.tz_convert("UTC").isoformat(),
        "calendar_timezone": timezone_name,
        "start_date_inclusive": start_local.date().isoformat(),
        "end_date_inclusive": end_local_inclusive.date().isoformat(),
        "start_utc": start_local.tz_convert("UTC").isoformat(),
        "end_utc_exclusive": end_local_exclusive.tz_convert("UTC").isoformat(),
    }