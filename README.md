# Kalshi Sports Edge

Kalshi Sports Edge is a research project for collecting Kalshi sports-market
data, building a research calendar, auditing candidate markets, and preparing
a paper-trading engine for future integration with a separate sports-modeling
project.

**This project is for research and paper trading only. It does not place real
orders, use real money, or send orders to Kalshi Demo.**

## Current status

| Component | Status |
|---|---|
| Kalshi event and market collection | Working |
| Research calendar builder | Working |
| Market snapshot processing | Working |
| Candidate-market audit | Working |
| Paper-trading engine | Built, but inactive |
| Model integration | Not connected yet |
| Mock positions | Zero |
| Real orders | Permanently disabled |
| Dashboard | Working |

The paper-trading engine is intentionally inactive. It cannot create even mock
positions until the modeling project is integrated and position creation is
explicitly enabled.

## Safety rules

The following settings are enforced in `config/simulator.json`:

```json
"paper_trading_only": true,
"allow_real_orders": false
```

The integration safety gate is also disabled:

```json
"integration": {
  "enabled": false,
  "allow_position_creation": false
}
```

This means:

- No real Kalshi orders are sent.
- No Kalshi Demo orders are sent.
- No real money is used.
- No mock positions are created.
- No portfolio cash is deducted.
- No match results are assumed.
- No positions are settled automatically.

Do not enable `allow_real_orders` under any circumstances. This project is
designed for research and paper trading only.

## Project goal

The long-term goal is to combine:

1. Kalshi market data
2. Scraped historical results and fixtures
3. Team and player features
4. Odds and other external market data
5. Probability models
6. A paper-trading engine
7. A dashboard for monitoring research and simulated portfolios

The modeling project will eventually produce probability estimates and trading
signals. The Kalshi project will validate those signals against available
markets and, only after explicit approval, create mock paper positions.

```text
Kalshi market snapshots
        +
Scraped results / features / odds
        |
        v
Match Kalshi events to real fixtures
        |
        v
Build features and estimate probabilities
        |
        v
Compare model probability with Kalshi implied probability
        |
        v
Create validated model signals
        |
        v
Paper engine evaluates signals
        |
        v
Mock positions may be created only after explicit approval
        |
        v
Actual results settle mock positions
        |
        v
Research reports and dashboard
```

## Repository structure

```text
kalshi-sports-edge/
├── README.md
├── requirements.txt
├── .gitignore
├── config/
│   ├── pipeline.json
│   └── simulator.json
├── scripts/
│   ├── add_integration_config.py
│   ├── archive_legacy_files.py
│   └── run_kalshi_collection.bat
├── src/
│   ├── kalshi/
│   │   ├── collect_events.py
│   │   ├── build_research_calendar.py
│   │   ├── pipeline_config.py
│   │   ├── simulator_state.py
│   │   ├── simulator_candidate_audit.py
│   │   ├── model_interface.py
│   │   ├── signal_builder.py
│   │   ├── paper_engine.py
│   │   └── dashboard.py
│   ├── fixtures/
│   └── tennis/
├── data/
│   ├── raw/                 # local only; not committed
│   ├── processed/           # local only; not committed
│   └── integration/         # local only; not committed
├── archive/                 # local only; not committed
├── backups/                 # local only; not committed
└── logs/                    # local only; not committed
```

## Kalshi collection

The collector requests selected football and tennis event series from Kalshi
and saves the raw API responses locally.

Run:

```bat
"C:\Users\besho\anaconda3\envs\kalshi-sports-edge\python.exe" "C:\Users\besho\Documents\kalshi-sports-edge\src\kalshi\collect_events.py"
```

Or use:

```bat
"C:\Users\besho\Documents\kalshi-sports-edge\scripts\run_kalshi_collection.bat"
```

Raw responses are saved under:

```text
data/raw/kalshi/event_runs/<run_id>/
```

Each run has its own folder and a `manifest.json` file. Raw collection history
is preserved. Do not delete or overwrite old raw run folders.

The collector uses the settings in:

```text
config/pipeline.json
```

These settings include the selected series, request delay, page limit, timeout,
retry behavior, and research window.

## Research calendar

After a collection run, build the processed research calendar:

```bat
"C:\Users\besho\anaconda3\envs\kalshi-sports-edge\python.exe" "C:\Users\besho\Documents\kalshi-sports-edge\src\kalshi\build_research_calendar.py"
```

This creates files such as:

```text
data/processed/kalshi_events_clean.csv
data/processed/kalshi_market_snapshots.csv
data/processed/kalshi_calendar_candidates.csv
data/processed/kalshi_calendar_market_snapshots.csv
data/processed/kalshi_calendar_settings.json
data/processed/kalshi_schedule_review.csv
```

Important: the processed calendar files are overwritten by each new calendar
build. They are working files, not a historical archive. The raw run folders
preserve the original observations.

The current calendar uses a rolling 14-day window in the Europe/Amsterdam
timezone. Schedules come from Kalshi milestones and are not independently
verified.

## Candidate audit

The candidate audit is read-only. It evaluates market snapshots against
strategy rules such as price range, spread, volume, open interest, and schedule
window.

Run:

```bat
"C:\Users\besho\anaconda3\envs\kalshi-sports-edge\python.exe" "C:\Users\besho\Documents\kalshi-sports-edge\src\kalshi\simulator_candidate_audit.py"
```

Outputs are saved under:

```text
data/processed/simulator/
```

The audit does not create positions, deduct cash, or contact Kalshi.

## Paper-trading engine

The paper engine is integration-ready but inactive.

It is designed to receive signals from the modeling project later. It does not
select trades by itself from price-based candidate files.

The modeling project will write signals to:

```text
data/integration/model_signals.csv
```

Each signal should contain:

```text
signal_id
source_run_id
event_ticker
market_ticker
outcome_role
model_probability
market_implied_probability
estimated_edge
entry_price
action
model_version
features_version
created_at_utc
```

The signal builder validates the signal file:

```bat
"C:\Users\besho\anaconda3\envs\kalshi-sports-edge\python.exe" "C:\Users\besho\Documents\kalshi-sports-edge\src\kalshi\signal_builder.py"
```

The paper engine performs a dry run:

```bat
"C:\Users\besho\anaconda3\envs\kalshi-sports-edge\python.exe" "C:\Users\besho\Documents\kalshi-sports-edge\src\kalshi\paper_engine.py"
```

While integration is disabled, both commands refuse to process signals or
create positions.

## Integration status

The modeling integration is not complete.

We are waiting for the modeling project to provide:

- Historical match results
- Fixture-level features
- Team and player features
- Odds or external market data, if available
- Probability estimates for football and tennis outcomes
- A reliable way to match real fixtures to Kalshi events
- Model version and feature-version metadata

The Kalshi project currently provides market snapshots, event schedules,
outcome-role mapping, liquidity fields, and a paper-trading engine.

No mock positions should be created until these inputs are connected and
reviewed.

## Football-Data token

The project uses a Football-Data API token for fixture and results data.

The token is stored locally at:

```text
config/football_data_token.txt
```

This file is excluded from Git by `.gitignore`:

```gitignore
config/football_data_token.txt
```

Never commit, share, email, screenshot, or paste this token into a repository,
Slack message, issue, or chat.

If a teammate needs access to Football-Data, they should create their own
account and token. Do not share one token across the team.

If a token is accidentally committed, revoke it immediately and create a new
one.

## Dashboard

Run:

```bat
"C:\Users\besho\anaconda3\envs\kalshi-sports-edge\python.exe" "C:\Users\besho\Documents\kalshi-sports-edge\src\kalshi\dashboard.py"
```

The dashboard shows:

- Kalshi source run and research window
- Event and market-snapshot counts
- Integration status
- Signal availability
- Portfolio cash, exposure, and open positions
- Clear warnings that no real orders are allowed

The dashboard reads local files only. It does not contact Kalshi or create
positions.

## Teammate workflow

1. Install Python 3.11 or newer.
2. Create or use the `kalshi-sports-edge` Anaconda environment.
3. Install dependencies:

```bat
pip install -r requirements.txt
```

4. Review `config/pipeline.json` and `config/simulator.json`.
5. Run the dashboard first:

```bat
"C:\Users\besho\anaconda3\envs\kalshi-sports-edge\python.exe" "C:\Users\besho\Documents\kalshi-sports-edge\src\kalshi\dashboard.py"
```

6. Do not run the collector unnecessarily; it creates a new raw run folder.
7. Do not enable integration or position creation without team review.
8. Do not commit raw data, generated CSV files, logs, backups, or tokens.
9. Do not send real orders. The project is paper-trading only.

## Sample data

Small reference samples are included in:

```text
data/samples/
```

They help teammates understand the structure of the processed Kalshi data
without committing the full regenerated dataset.

The samples include:

- Event samples
- Market-snapshot samples
- Calendar-candidate samples
- Candidate-audit samples
- Selected-candidate samples
- Calendar settings

See:

```text
data/samples/README.md
```

and:

```text
docs/data_dictionary.md
```

The full processed data remains local and is excluded from Git because it is
overwritten by each calendar build.

## Data handling

The following folders and files are local-only and excluded from Git:

```text
data/raw/
data/processed/
data/integration/
archive/
backups/
logs/
config/football_data_token.txt
```

The repository should contain code, configuration, documentation, and tests—not
large datasets or credentials.

## Cleanup policy

Old inspection scripts, exploratory outputs, and superseded research files were
moved to:

```text
archive/
```

They were not deleted. The archive manifest is:

```text
archive/archive_manifest.json
```

Raw API responses in `data/raw/` were not moved or modified.

## Next steps

1. Review and finalize the README and repository structure.
2. Initialize Git and inspect `git status` before the first commit.
3. Create an initial commit containing only code, configuration, and docs.
4. Connect the modeling project through `data/integration/model_signals.csv`.
5. Validate signals with the signal builder.
6. Run the paper engine in dry-run mode.
7. Only after team review, enable mock-position creation.
8. Build a separate settlement process using verified actual results.