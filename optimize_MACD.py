"""MACD strategy grid-search optimisation.

This module mirrors the interactive experience offered by the RSI optimiser
while focusing on tuning the three main MACD parameters (fast EMA, slow EMA,
signal EMA).  It relies on the shared configuration helpers so that interval
and period selections stay consistent with the rest of the application.
"""

from __future__ import annotations

import argparse
import itertools
import logging
from dataclasses import dataclass
from typing import Iterable, List, Tuple

import pandas as pd

from config import (
    DEFAULT_SYMBOL,
    DEFAULT_INTERVAL,
    ALLOWED_INTERVALS,
    DEFAULT_PERIOD,
    ALLOWED_PERIODS,
    PERIOD_DEFINITIONS,
    compute_period_bounds,
    INITIAL_CAPITAL,
    TRADING_FEE,
    SLIPPAGE,
)
from data_manager import DataManager
from backtester import Backtester
from strategies import MACDStrategy

# ---------------------------------------------------------------------------
# Parameter ranges (easily adjustable at the top of the file as requested)
# ---------------------------------------------------------------------------
FAST_RANGE = range(8, 15)
SLOW_RANGE = range(20, 31)
SIGNAL_RANGE = range(5, 13)


@dataclass
class MacdResult:
    """Container used to keep optimisation results tidy."""

    fast_period: int
    slow_period: int
    signal_period: int
    final_capital: float
    total_return_pct: float
    max_drawdown_pct: float
    total_trades: int

    @property
    def as_dict(self) -> dict:
        return {
            "fast_period": self.fast_period,
            "slow_period": self.slow_period,
            "signal_period": self.signal_period,
            "final_capital": self.final_capital,
            "total_return_pct": self.total_return_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "total_trades": self.total_trades,
        }


def prompt_interval(default: str = DEFAULT_INTERVAL) -> str:
    """Prompt the user for a Binance interval and validate the choice."""

    allowed_display = ", ".join(ALLOWED_INTERVALS)
    print(f"\n📏 Intervalles disponibles : {allowed_display}")
    choice = input(f"👉 Intervalle [{default}] : ").strip()

    if not choice:
        return default

    if choice not in ALLOWED_INTERVALS:
        print(f"❌ Intervalle invalide '{choice}'. On conserve '{default}'.")
        return default

    return choice


def prompt_period(default: str = DEFAULT_PERIOD) -> str:
    """Prompt the user for a historical period code."""

    print("\n⏱️ Choisis la durée du backtest :")
    period_items = list(enumerate(ALLOWED_PERIODS, start=1))
    for index, code in period_items:
        label = PERIOD_DEFINITIONS[code]["label"]
        marker = " (défaut)" if code == default else ""
        print(f" {index}) {label} [{code}]{marker}")

    default_label = PERIOD_DEFINITIONS[default]["label"]
    choice = input(f"\n👉 Ton choix [{default_label}] : ").strip().lower()

    if not choice:
        return default

    if choice in PERIOD_DEFINITIONS:
        return choice

    if choice.isdigit():
        try:
            return period_items[int(choice) - 1][1]
        except (IndexError, ValueError):
            pass

    print(
        f"❌ Période invalide '{choice}'. On conserve '{default_label}' ({default})."
    )
    return default


def grid_search_macd(
    data,
    fast_range: Iterable[int] = FAST_RANGE,
    slow_range: Iterable[int] = SLOW_RANGE,
    signal_range: Iterable[int] = SIGNAL_RANGE,
) -> List[MacdResult]:
    """Run a brute-force grid search on MACD parameters."""

    backtester = Backtester(
        initial_capital=INITIAL_CAPITAL,
        commission=TRADING_FEE,
        slippage=SLIPPAGE,
    )

    results: List[MacdResult] = []

    fast_values = list(fast_range)
    slow_values = list(slow_range)
    signal_values = list(signal_range)

    combos = [
        (fast, slow, signal)
        for fast, slow, signal in itertools.product(
            fast_values, slow_values, signal_values
        )
        if slow > fast
    ]

    total_combinations = len(combos)
    if not total_combinations:
        print("❌ Aucun ensemble de paramètres MACD valide.")
        return results

    print(f"🔍 Testing {total_combinations} combinations...")
    for index, (fast, slow, signal_period) in enumerate(combos, start=1):

        strategy = MACDStrategy(
            params={
                "macd_fast": fast,
                "macd_slow": slow,
                "macd_signal": signal_period,
            }
        )

        _, metrics = backtester.run(
            data=data.copy(),
            strategy=strategy,
        )

        result = MacdResult(
            fast_period=fast,
            slow_period=slow,
            signal_period=signal_period,
            final_capital=metrics.get("final_capital", INITIAL_CAPITAL),
            total_return_pct=metrics.get("total_return_pct", 0.0),
            max_drawdown_pct=metrics.get("max_drawdown", 0.0),
            total_trades=metrics.get("total_trades", 0),
        )
        results.append(result)

        if index % 10 == 0 or index == total_combinations:
            print(f"    Progress: {index}/{total_combinations}")

    return results


def run_macd_optimisation(symbol: str, interval: str, period: str) -> Tuple[str, str, List[MacdResult]]:
    """Load data and execute the MACD grid-search."""

    if interval not in ALLOWED_INTERVALS:
        raise ValueError(f"Interval '{interval}' is not supported.")

    if period not in ALLOWED_PERIODS:
        raise ValueError(f"Period '{period}' is not supported.")

    start_date, end_date = compute_period_bounds(period)
    logging.info(
        "Optimisation MACD sur %s | %s | %s -> %s (%s)",
        symbol,
        interval,
        start_date,
        end_date,
        period,
    )

    dm = DataManager()
    df = dm.get_historical_data(symbol, interval, start_date, end_date)

    if df is None or df.empty:
        print("❌ Optimisation interrompue : aucune donnée disponible.")
        return start_date, end_date, []

    print(f"\n📊 Données : {symbol} | {interval} | {start_date} → {end_date}")
    results = grid_search_macd(df)

    return start_date, end_date, results


def display_results(results: List[MacdResult]) -> None:
    """Display the optimisation summary in a sorted table."""

    if not results:
        print("Aucun résultat à afficher.")
        return

    results_df = pd.DataFrame(r.as_dict for r in results)
    results_df = results_df.sort_values(by="final_capital", ascending=False).reset_index(
        drop=True
    )

    best = results_df.iloc[0]
    print("\n🏆 Meilleure combinaison trouvée :")
    print(
        "  - fast_period : {fast}\n"
        "  - slow_period : {slow}\n"
        "  - signal_period : {signal}\n"
        "  - Final capital : ${capital:,.2f}\n"
        "  - Total return : {ret:.2f}%\n"
        "  - Max drawdown : {dd:.2f}%\n"
        "  - Trades : {trades}".format(
            fast=int(best["fast_period"]),
            slow=int(best["slow_period"]),
            signal=int(best["signal_period"]),
            capital=float(best["final_capital"]),
            ret=float(best["total_return_pct"]),
            dd=float(best["max_drawdown_pct"]),
            trades=int(best["total_trades"]),
        )
    )

    print("\n📈 TOP 10 COMBINAISONS :")
    top10 = results_df.head(10)
    formatters = {
        "final_capital": "${:,.2f}".format,
        "total_return_pct": "{:,.2f}%".format,
        "max_drawdown_pct": "{:,.2f}%".format,
    }
    print(top10.to_string(index=False, formatters=formatters))

    results_df.to_csv("optimization_macd_results.csv", index=False)
    print("\n💾 Résultats sauvegardés → optimization_macd_results.csv")


def cli(symbol: str, interval: str, period: str) -> None:
    """Entry point used by both the module and the main menu."""

    start_date, end_date, results = run_macd_optimisation(symbol, interval, period)
    if not results:
        return

    print(
        f"\nRésumé de l'optimisation MACD pour {symbol} | {interval} | {start_date} → {end_date}"
    )
    display_results(results)


def interactive_session(
    default_symbol: str = DEFAULT_SYMBOL,
    default_interval: str = DEFAULT_INTERVAL,
    default_period: str = DEFAULT_PERIOD,
) -> Tuple[str, str, str]:
    """Run the optimiser with interactive prompts (menu integration).

    Returns the symbol, interval and period that were used so the caller can
    keep them as defaults for subsequent actions.
    """

    symbol = default_symbol
    interval = default_interval
    period = default_period

    print("=" * 60)
    print("🔧 MACD STRATEGY OPTIMIZER")
    print("=" * 60)

    print(f"\n📌 Symbole par défaut : {symbol}")
    use_default = input("Utiliser un autre symbole ? (O/n) : ").strip().lower()
    if use_default == "n":
        entered_symbol = input("👉 Entre un symbole (ex: BTCUSDT) : ").upper().strip()
        if entered_symbol:
            symbol = entered_symbol

    interval = prompt_interval(interval)
    period = prompt_period(period)

    cli(symbol=symbol, interval=interval, period=period)

    return symbol, interval, period


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optimisation MACD")
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL, help="Paire à optimiser.")
    parser.add_argument(
        "--interval",
        choices=ALLOWED_INTERVALS,
        default=DEFAULT_INTERVAL,
        help="Intervalle de chandelles.",
    )
    parser.add_argument(
        "--period",
        choices=ALLOWED_PERIODS,
        default=DEFAULT_PERIOD,
        help="Durée historique à analyser.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Demander les paramètres via des invites interactives.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    args = parse_args()

    if args.interactive:
        interactive_session(
            default_symbol=args.symbol.upper(),
            default_interval=args.interval,
            default_period=args.period,
        )
    else:
        cli(symbol=args.symbol.upper(), interval=args.interval, period=args.period)


if __name__ == "__main__":
    main()

