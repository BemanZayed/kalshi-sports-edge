# Sample data

These files are small, curated samples intended to help teammates understand
the structure of the project’s processed Kalshi data.

They are reference examples only. They are not complete datasets and should not
be used for production decisions, backtests, or trading.

The full processed data remains local under:

```text
data/processed/
```

That folder is excluded from Git because it is regenerated whenever the
research calendar is rebuilt.

## Sample files

| File | Purpose |
|---|---|
| `kalshi_events_clean_sample.csv` | First 25 processed Kalshi events |
| `kalshi_market_snapshots_sample.csv` | First 25 market snapshots |
| `kalshi_calendar_candidates_sample.csv` | First 25 events inside the active research window |
| `kalshi_calendar_market_snapshots_sample.csv` | First 25 markets attached to in-window events |
| `kalshi_calendar_settings.json` | Settings used to build the current calendar |
| `candidate_audit_favorite_back_sample.csv` | First 25 favorite-back audit rows |
| `candidate_audit_longshot_back_sample.csv` | First 25 longshot-back audit rows |
| `selected_candidates_favorite_back_sample.csv` | First 25 selected favorite-back candidates |
| `selected_candidates_longshot_back_sample.csv` | First 25 selected longshot-back candidates |

## Important context

The samples were generated from Kalshi collection run:

```text
20261124T180009786171Z
```

The active research window is:

```text
2026-11-24 through 2026-12-07
```

The current full dataset contains:

```text
312 events
756 market snapshots
```

## Safety

These samples do not represent trades, positions, or model predictions.

No mock positions have been created. The paper engine remains inactive until
the modeling project is integrated.