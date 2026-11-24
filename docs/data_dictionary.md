# Data dictionary

This document explains the main fields in the Kalshi research data and the
future model-signal interface.

## Kalshi events

File:

```text
data/samples/kalshi_events_clean_sample.csv
```

| Column | Meaning |
|---|---|
| `run_id` | Kalshi collection run that produced the row |
| `sport` | `football` or `tennis` |
| `series_ticker` | Kalshi series, such as `KXEPLGAME` or `KXATPMATCH` |
| `event_ticker` | Unique Kalshi event identifier |
| `event_title` | Human-readable event title |
| `competition` | Competition metadata supplied by Kalshi |
| `scheduled_start_utc` | Kalshi-reported event start time in UTC |
| `scheduled_start_local` | Event start time in Europe/Amsterdam |
| `candidate_in_window` | Whether the event falls within the active research window |
| `schedule_needs_review` | Whether the schedule needs manual review |
| `market_count` | Number of markets attached to the event |

## Kalshi market snapshots

File:

```text
data/samples/kalshi_market_snapshots_sample.csv
```

| Column | Meaning |
|---|---|
| `market_ticker` | Unique Kalshi market identifier |
| `event_ticker` | Parent Kalshi event |
| `outcome_role` | `home`, `away`, `draw`, `player_1`, `player_2`, or `unmapped` |
| `yes_bid` | Best available yes bid |
| `yes_ask` | Best available yes ask |
| `quoted_spread` | `yes_ask - yes_bid` |
| `volume_contracts` | Contracts traded |
| `open_interest_contracts` | Open interest in contracts |
| `market_occurrence_utc` | Market-level occurrence time |
| `market_close_utc` | Market close time |

## Candidate audit

Files:

```text
data/samples/candidate_audit_favorite_back_sample.csv
data/samples/candidate_audit_longshot_back_sample.csv
```

The candidate audit evaluates whether a market satisfies a strategy’s rules.

| Column | Meaning |
|---|---|
| `strategy_id` | Strategy being evaluated |
| `entry_price` | Price used for a hypothetical entry |
| `eligible` | Whether the market passed all rules |
| `selected` | Whether the market was selected for that strategy |
| `skip_reason` | Reason a market was not selected |

These files are research outputs only. They do not create positions.

## Future model signals

The modeling project will later write:

```text
data/integration/model_signals.csv
```

| Column | Meaning |
|---|---|
| `signal_id` | Unique signal identifier |
| `source_run_id` | Kalshi run used for the market snapshot |
| `event_ticker` | Kalshi event |
| `market_ticker` | Kalshi market |
| `outcome_role` | Outcome being considered |
| `model_probability` | Model probability for the outcome |
| `market_implied_probability` | Probability implied by the entry price |
| `estimated_edge` | `model_probability - market_implied_probability` |
| `entry_price` | Intended entry price |
| `action` | `buy_yes` or `buy_no` |
| `model_version` | Version of the model |
| `features_version` | Version of the feature set |
| `created_at_utc` | Signal creation time |

The paper engine will not create positions until integration is explicitly
enabled.