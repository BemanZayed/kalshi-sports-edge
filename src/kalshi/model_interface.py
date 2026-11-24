import math
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_SIGNAL_COLUMNS = [
    "signal_id",
    "source_run_id",
    "event_ticker",
    "market_ticker",
    "outcome_role",
    "model_probability",
    "market_implied_probability",
    "estimated_edge",
    "entry_price",
    "action",
    "model_version",
    "features_version",
    "created_at_utc",
]

ALLOWED_ACTIONS = {
    "buy_yes",
    "buy_no",
}

ALLOWED_OUTCOME_ROLES = {
    "home",
    "away",
    "draw",
    "player_1",
    "player_2",
}


def validate_signal_row(
    row,
    minimum_price,
    maximum_price,
    minimum_edge,
):
    reasons = []

    for column in REQUIRED_SIGNAL_COLUMNS:
        value = row.get(column)

        if (
            value is None
            or (isinstance(value, float) and math.isnan(value))
            or (isinstance(value, str) and not value.strip())
        ):
            reasons.append(f"missing_or_empty_{column}")

    if reasons:
        return False, reasons

    model_probability = pd.to_numeric(
        row["model_probability"],
        errors="coerce",
    )

    market_implied_probability = pd.to_numeric(
        row["market_implied_probability"],
        errors="coerce",
    )

    estimated_edge = pd.to_numeric(
        row["estimated_edge"],
        errors="coerce",
    )

    entry_price = pd.to_numeric(
        row["entry_price"],
        errors="coerce",
    )

    if not (
        0.0 <= model_probability <= 1.0
    ):
        reasons.append("invalid_model_probability")

    if not (
        0.0 <= market_implied_probability <= 1.0
    ):
        reasons.append(
            "invalid_market_implied_probability"
        )

    if not (
        minimum_price
        <= entry_price
        <= maximum_price
    ):
        reasons.append("invalid_entry_price")

    if row["action"] not in ALLOWED_ACTIONS:
        reasons.append("invalid_action")

    if (
        row["outcome_role"]
        not in ALLOWED_OUTCOME_ROLES
    ):
        reasons.append("invalid_outcome_role")

    expected_edge = (
        model_probability
        - market_implied_probability
    )

    if pd.isna(estimated_edge):
        reasons.append("missing_estimated_edge")
    elif abs(estimated_edge - expected_edge) > 0.0001:
        reasons.append("estimated_edge_mismatch")

    if estimated_edge < minimum_edge:
        reasons.append("edge_below_minimum")

    return not reasons, reasons


def validate_signal_file(
    signals_path,
    minimum_price,
    maximum_price,
    minimum_edge,
):
    signals = pd.read_csv(signals_path)

    missing_columns = set(
        REQUIRED_SIGNAL_COLUMNS
    ) - set(signals.columns)

    if missing_columns:
        raise ValueError(
            "Signal file is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    validated_rows = []
    rejected_rows = []

    for _, row in signals.iterrows():
        valid, reasons = validate_signal_row(
            row,
            minimum_price,
            maximum_price,
            minimum_edge,
        )

        record = row.to_dict()
        record["validation_status"] = (
            "valid" if valid else "rejected"
        )
        record["validation_reasons"] = (
            ";".join(reasons)
        )

        if valid:
            validated_rows.append(record)
        else:
            rejected_rows.append(record)

    return (
        pd.DataFrame(validated_rows),
        pd.DataFrame(rejected_rows),
    )