import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SIMULATOR_CONFIG_PATH = (
    PROJECT_ROOT / "config" / "simulator.json"
)


def load_simulator_config():
    with SIMULATOR_CONFIG_PATH.open(
        encoding="utf-8-sig"
    ) as handle:
        config = json.load(handle)

    if not isinstance(config, dict):
        raise ValueError(
            "simulator.json must contain a JSON object"
        )

    if config.get("schema_version") != 1:
        raise ValueError(
            "simulator.json: schema_version must be 1"
        )

    execution = config.get("execution_rules")

    if not isinstance(execution, dict):
        raise ValueError(
            "simulator.json: execution_rules must be an object"
        )

    if execution.get("paper_trading_only") is not True:
        raise ValueError(
            "simulator.json: paper_trading_only must be true"
        )

    if execution.get("allow_real_orders") is not False:
        raise ValueError(
            "simulator.json: allow_real_orders must be false"
        )

    portfolios = config.get("portfolios")

    if not isinstance(portfolios, list) or not portfolios:
        raise ValueError(
            "simulator.json: portfolios must be a non-empty list"
        )

    portfolio_ids = []

    for portfolio in portfolios:
        if not isinstance(portfolio, dict):
            raise ValueError(
                "simulator.json: each portfolio must be an object"
            )

        portfolio_id = portfolio.get("portfolio_id")

        if (
            not isinstance(portfolio_id, str)
            or not portfolio_id.strip()
            or portfolio_id != portfolio_id.strip()
        ):
            raise ValueError(
                "simulator.json: invalid portfolio_id"
            )

        if portfolio_id in portfolio_ids:
            raise ValueError(
                f"simulator.json: duplicate portfolio_id: {portfolio_id}"
            )

        portfolio_ids.append(portfolio_id)

        starting_cash = portfolio.get("starting_cash")

        if (
            type(starting_cash) not in (int, float)
            or not math.isfinite(starting_cash)
            or starting_cash <= 0
        ):
            raise ValueError(
                f"simulator.json: invalid starting_cash for {portfolio_id}"
            )

        for field_name in (
            "max_open_positions",
            "max_stake_per_position",
            "max_total_exposure",
        ):
            value = portfolio.get(field_name)

            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(
                    f"simulator.json: invalid {field_name} "
                    f"for {portfolio_id}"
                )

        if portfolio.get("sizing_mode") not in (
            "equal_weight",
            "dynamic",
        ):
            raise ValueError(
                f"simulator.json: invalid sizing_mode for {portfolio_id}"
            )

        strategies = portfolio.get("strategies")

        if (
            not isinstance(strategies, list)
            or not strategies
            or not all(
                isinstance(strategy, str)
                and strategy.strip()
                for strategy in strategies
            )
        ):
            raise ValueError(
                f"simulator.json: invalid strategies for {portfolio_id}"
            )

        strategy_definitions = config.get(
            "strategy_definitions"
        )

        if not isinstance(strategy_definitions, dict):
            raise ValueError(
                "simulator.json: strategy_definitions must be an object"
            )

        for strategy in strategies:
            if strategy not in strategy_definitions:
                raise ValueError(
                    f"simulator.json: unknown strategy "
                    f"{strategy!r} for {portfolio_id}"
                )

    return config


@dataclass
class PaperPosition:
    position_id: str
    portfolio_id: str
    strategy_id: str
    run_id: str
    event_ticker: str
    market_ticker: str
    outcome_role: str
    entry_snapshot_utc: str
    entry_price: float
    contracts: int
    stake: float
    status: str = "open"
    exit_snapshot_utc: str | None = None
    exit_price: float | None = None
    realized_pnl: float | None = None
    notes: str = ""


@dataclass
class PortfolioState:
    portfolio_id: str
    starting_cash: float
    currency: str
    sizing_mode: str
    max_open_positions: int
    max_stake_per_position: float
    max_total_exposure: float
    strategies: list[str]
    sport_filter: list[str]
    series_filter: list[str]
    cash: float
    open_positions: dict[str, PaperPosition] = field(
        default_factory=dict
    )
    closed_positions: dict[str, PaperPosition] = field(
        default_factory=dict
    )

    @property
    def total_exposure(self):
        return sum(
            position.stake
            for position in self.open_positions.values()
        )

    @property
    def equity(self):
        return self.cash + self.total_exposure

    @property
    def realized_pnl(self):
        return sum(
            position.realized_pnl or 0.0
            for position in self.closed_positions.values()
        )

    def can_open_position(
        self,
        stake,
        open_position_count,
    ):
        if stake > self.cash:
            return False, "insufficient_cash"

        if stake > self.max_stake_per_position:
            return False, "stake_limit"

        if (
            self.total_exposure + stake
            > self.max_total_exposure
        ):
            return False, "exposure_limit"

        if (
            open_position_count
            >= self.max_open_positions
        ):
            return False, "open_position_limit"

        return True, "allowed"


class PaperSimulator:
    def __init__(self, config):
        self.config = config
        self.execution_rules = config[
            "execution_rules"
        ]
        self.portfolios = {}

        for portfolio_config in config["portfolios"]:
            if not portfolio_config.get("enabled"):
                continue

            portfolio_id = portfolio_config[
                "portfolio_id"
            ]

            self.portfolios[portfolio_id] = (
                PortfolioState(
                    portfolio_id=portfolio_id,
                    starting_cash=portfolio_config[
                        "starting_cash"
                    ],
                    currency=portfolio_config[
                        "currency"
                    ],
                    sizing_mode=portfolio_config[
                        "sizing_mode"
                    ],
                    max_open_positions=portfolio_config[
                        "max_open_positions"
                    ],
                    max_stake_per_position=portfolio_config[
                        "max_stake_per_position"
                    ],
                    max_total_exposure=portfolio_config[
                        "max_total_exposure"
                    ],
                    strategies=portfolio_config[
                        "strategies"
                    ],
                    sport_filter=portfolio_config[
                        "sport_filter"
                    ],
                    series_filter=portfolio_config[
                        "series_filter"
                    ],
                    cash=portfolio_config[
                        "starting_cash"
                    ],
                )
            )

    def calculate_stake(
        self,
        portfolio,
        candidate,
    ):
        if (
            portfolio.sizing_mode
            == "equal_weight"
        ):
            stake = min(
                self.config["dynamic_sizing"][
                    "base_stake"
                ],
                portfolio.max_stake_per_position,
            )
            return stake

        dynamic = self.config["dynamic_sizing"]
        confidence = candidate.get("confidence", 0.0)

        if (
            type(confidence) not in (int, float)
            or not math.isfinite(confidence)
        ):
            confidence = 0.0

        confidence = max(
            dynamic["minimum_confidence"],
            min(
                dynamic["maximum_confidence"],
                confidence,
            ),
        )

        stake = dynamic["base_stake"] * (
            1.0 + confidence
        )

        stake = max(
            dynamic["minimum_stake"],
            min(
                dynamic["maximum_stake"],
                stake,
            ),
        )

        stake = min(
            stake,
            portfolio.max_stake_per_position,
        )

        return stake

    def open_position(
        self,
        portfolio_id,
        strategy_id,
        candidate,
    ):
        if portfolio_id not in self.portfolios:
            raise ValueError(
                f"Unknown portfolio: {portfolio_id}"
            )

        portfolio = self.portfolios[portfolio_id]

        if strategy_id not in portfolio.strategies:
            raise ValueError(
                f"Strategy {strategy_id!r} is not enabled "
                f"for portfolio {portfolio_id!r}"
            )

        entry_price = candidate.get("entry_price")

        if (
            type(entry_price) not in (int, float)
            or not math.isfinite(entry_price)
            or not (
                self.execution_rules["minimum_price"]
                <= entry_price
                <= self.execution_rules["maximum_price"]
            )
        ):
            raise ValueError(
                "Invalid entry price for paper position"
            )

        stake = self.calculate_stake(
            portfolio,
            candidate,
        )

        allowed, reason = portfolio.can_open_position(
            stake,
            len(portfolio.open_positions),
        )

        if not allowed:
            return None, reason

        contracts = math.floor(
            stake / entry_price
        )

        if (
            contracts
            < self.execution_rules[
                "minimum_contract_size"
            ]
        ):
            return None, "contract_size_too_small"

        actual_stake = contracts * entry_price

        if actual_stake > portfolio.cash:
            return None, "insufficient_cash"

        position_id = (
            f"{portfolio_id}:{candidate['market_ticker']}:"
            f"{strategy_id}"
        )

        if (
            position_id in portfolio.open_positions
            or position_id in portfolio.closed_positions
        ):
            return None, "duplicate_position"

        position = PaperPosition(
            position_id=position_id,
            portfolio_id=portfolio_id,
            strategy_id=strategy_id,
            run_id=candidate["run_id"],
            event_ticker=candidate["event_ticker"],
            market_ticker=candidate["market_ticker"],
            outcome_role=candidate["outcome_role"],
            entry_snapshot_utc=candidate[
                "snapshot_utc"
            ],
            entry_price=entry_price,
            contracts=contracts,
            stake=actual_stake,
        )

        portfolio.cash -= actual_stake
        portfolio.open_positions[position_id] = (
            position
        )

        return position, "opened"

    def close_position(
        self,
        portfolio_id,
        position_id,
        exit_price,
        exit_snapshot_utc,
    ):
        if portfolio_id not in self.portfolios:
            raise ValueError(
                f"Unknown portfolio: {portfolio_id}"
            )

        portfolio = self.portfolios[portfolio_id]
        position = portfolio.open_positions.get(
            position_id
        )

        if position is None:
            raise ValueError(
                f"Position is not open: {position_id}"
            )

        if (
            type(exit_price) not in (int, float)
            or not math.isfinite(exit_price)
            or not (
                self.execution_rules["minimum_price"]
                <= exit_price
                <= self.execution_rules["maximum_price"]
            )
        ):
            raise ValueError(
                "Invalid exit price for paper position"
            )

        proceeds = position.contracts * exit_price
        realized_pnl = proceeds - position.stake

        portfolio.cash += proceeds
        position.status = "closed"
        position.exit_snapshot_utc = (
            exit_snapshot_utc
        )
        position.exit_price = exit_price
        position.realized_pnl = realized_pnl

        portfolio.closed_positions[position_id] = (
            position
        )
        del portfolio.open_positions[position_id]

        return position

    def portfolio_summary(self):
        summaries = []

        for portfolio in self.portfolios.values():
            summaries.append(
                {
                    "portfolio_id": portfolio.portfolio_id,
                    "currency": portfolio.currency,
                    "starting_cash": portfolio.starting_cash,
                    "cash": portfolio.cash,
                    "open_positions": len(
                        portfolio.open_positions
                    ),
                    "closed_positions": len(
                        portfolio.closed_positions
                    ),
                    "total_exposure": portfolio.total_exposure,
                    "equity": portfolio.equity,
                    "realized_pnl": portfolio.realized_pnl,
                }
            )

        return summaries