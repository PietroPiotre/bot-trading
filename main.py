# main.py
import argparse
import os
import logging

from dotenv import load_dotenv

from config import (
    DEFAULT_SYMBOL,
    DEFAULT_INTERVAL,
    ALLOWED_INTERVALS,
    DEFAULT_PERIOD,
    ALLOWED_PERIODS,
    PERIOD_DEFINITIONS,
    compute_period_bounds,
)  # on ne récupère plus STOP_LOSS_PERCENT ici

from data_manager import DataManager
from backtester import Backtester
from strategies import (
    RSIStrategy,
    MACDStrategy,
    BollingerBandsStrategy,
    MovingAverageCrossStrategy,
    CombinedStrategy,
    BuyAndHoldStrategy,
)
from visualizer import BacktestVisualizer
from optimize import main as rsi_optimize_main
from run_live_bot import main as live_bot_main


def log_strategy_metrics(name: str, metrics: dict) -> None:
    """Affiche et journalise les métriques d'une stratégie.

    Extraite pour réutilisation après le refactoring Buy & Hold afin de garder
    `run_multi_strategy_backtest` lisible.
    """

    total_return = metrics.get("total_return_pct", 0.0)
    sharpe = metrics.get("sharpe_ratio", 0.0)
    trades_count = metrics.get("total_trades", 0)
    max_dd = metrics.get("max_drawdown", 0.0)

    print(
        f"    • Return: {total_return:.2f}% | "
        f"Sharpe: {sharpe:.2f} | "
        f"Trades: {trades_count} | "
        f"Max DD: {max_dd:.2f}%"
    )

    logging.info(
        f"Result {name}: return={total_return:.2f}% "
        f"sharpe={sharpe:.2f} trades={trades_count} maxDD={max_dd:.2f}%"
    )


def run_strategy_once(
    backtester: Backtester,
    base_df,
    strategy,
    stop_loss: float,
    take_profit: float,
):
    """Exécute un backtest pour une stratégie et retourne les éléments utiles.

    Cette fonction utilitaire centralise l'application conditionnelle du stop-loss /
    take-profit (Buy & Hold n'en veut pas) et la duplication du journal de trades
    avant la réinitialisation du backtester.
    """

    df_copy = base_df.copy()
    strategy_stop_loss = stop_loss if getattr(strategy, "allow_stop_take", True) else None
    strategy_take_profit = take_profit if getattr(strategy, "allow_stop_take", True) else None

    bt_df, metrics = backtester.run(
        data=df_copy,
        strategy=strategy,
        stop_loss=strategy_stop_loss,
        take_profit=strategy_take_profit,
    )

    trades_df = backtester.get_trade_log().copy()
    return bt_df, metrics, trades_df


def prompt_interval(default_interval: str = DEFAULT_INTERVAL) -> str:
    """Prompt the user for a candle interval and validate the choice."""

    allowed_display = ", ".join(ALLOWED_INTERVALS)
    print()
    print(f"Available intervals: {allowed_display}")
    user_input = input(
        f"Choose interval [{default_interval}]: "
    ).strip()

    if not user_input:
        return default_interval

    if user_input not in ALLOWED_INTERVALS:
        print(
            f"Invalid interval '{user_input}'. Using default '{default_interval}'."
        )
        return default_interval

    return user_input


def prompt_period(default_period: str = DEFAULT_PERIOD) -> str:
    """Prompt the user for a historical window duration."""

    print()
    print("Select backtest period:")
    period_items = list(enumerate(ALLOWED_PERIODS, start=1))
    for index, code in period_items:
        label = PERIOD_DEFINITIONS[code]["label"]
        marker = " (default)" if code == default_period else ""
        print(f"  {index}) {label} [{code}]{marker}")

    default_label = PERIOD_DEFINITIONS[default_period]["label"]
    user_input = input(
        f"Choice [{default_label}]: "
    ).strip().lower()

    if not user_input:
        return default_period

    if user_input in PERIOD_DEFINITIONS:
        return user_input

    if user_input.isdigit():
        try:
            selected_code = period_items[int(user_input) - 1][1]
            return selected_code
        except (IndexError, ValueError):
            pass

    print(
        f"Invalid period '{user_input}'. Using default '{default_label}' ({default_period})."
    )
    return default_period


# ------------------ PARAMÈTRES GLOBAUX SIMPLES ------------------
# BNB par défaut
SYMBOL = DEFAULT_SYMBOL if DEFAULT_SYMBOL else "BNBUSDT"

# Gestion du risque (intégré directement ici)
INITIAL_CAPITAL = 10_000
STOP_LOSS_PERCENT = 0.02     # 2%
TAKE_PROFIT_PERCENT = 0.05   # 5%
COMMISSION = 0.00075
SLIPPAGE = 0.00030


# ------------------ LOGGING ------------------
def setup_logging():
    os.makedirs("logs", exist_ok=True)
    log_file = os.path.join("logs", "main.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


# ------------------ BACKTEST MULTI-STRATÉGIES (CHOIX 1) ------------------
def run_multi_strategy_backtest(
    interval: str = DEFAULT_INTERVAL,
    period: str = DEFAULT_PERIOD,
):
    load_dotenv()
    setup_logging()

    symbol = SYMBOL

    if interval not in ALLOWED_INTERVALS:
        logging.warning(
            "Interval '%s' is not supported. Falling back to '%s'.",
            interval,
            DEFAULT_INTERVAL,
        )
        interval = DEFAULT_INTERVAL

    if period not in ALLOWED_PERIODS:
        logging.warning(
            "Period '%s' is not supported. Falling back to '%s'.",
            period,
            DEFAULT_PERIOD,
        )
        period = DEFAULT_PERIOD

    start_date, end_date = compute_period_bounds(period)
    period_label = PERIOD_DEFINITIONS[period]["label"]

    stop_loss = STOP_LOSS_PERCENT
    take_profit = TAKE_PROFIT_PERCENT

    print("=" * 60)
    print("CRYPTO TRADING BOT - MULTI STRATEGY BACKTEST")
    print("=" * 60)
    print(f"Symbol      : {symbol}")
    print(f"Interval    : {interval}")
    print(f"Period      : {start_date} -> {end_date} ({period_label})")
    print(f"Capital init: ${INITIAL_CAPITAL:,.2f}")
    print(f"Stop loss   : {stop_loss * 100:.2f} %")
    print(f"Take profit : {take_profit * 100:.2f} %")
    print()

    logging.info(
        "Backtest multi-strategies: %s %s %s -> %s (%s)",
        symbol,
        interval,
        start_date,
        end_date,
        period,
    )

    # ---- Chargement des données ----
    dm = DataManager()
    df = dm.get_historical_data(symbol, interval, start_date, end_date)

    if df is None or df.empty:
        print("ERROR: no historical data loaded.")
        return

    print(f"Loaded {len(df)} candles.")
    logging.info("Historical data loaded")

    # ---- Stratégies à tester ----
    benchmark_name = "Buy & Hold (benchmark)"
    strategy_list = [
        ("RSI Strategy", RSIStrategy(), False),
        ("MACD Strategy", MACDStrategy(), False),
        ("Bollinger Bands", BollingerBandsStrategy(), False),
        ("MA Cross", MovingAverageCrossStrategy(), False),
        ("Combined Strategy", CombinedStrategy(), False),
        # Référence Buy & Hold ajoutée pour le benchmark simple.
        (benchmark_name, BuyAndHoldStrategy(), True),
    ]

    backtester = Backtester(
        initial_capital=INITIAL_CAPITAL,
        commission=COMMISSION,
        slippage=SLIPPAGE,
    )

    results = []
    benchmark_result = None

    for name, strategy, is_benchmark in strategy_list:
        print()
        print(f"  Testing: {name}...")
        logging.info(f"Test strategy: {name}")

        bt_df, metrics, trades_df = run_strategy_once(
            backtester,
            df,
            strategy,
            stop_loss,
            take_profit,
        )

        metrics_copy = metrics.copy()
        log_strategy_metrics(name, metrics_copy)

        result_entry = {
            "name": name,
            "metrics": metrics_copy,
            "df": bt_df,
            "trades": trades_df,
            "is_benchmark": is_benchmark,
        }
        results.append(result_entry)

        if is_benchmark:
            benchmark_result = result_entry

    print()
    if not results:
        print("No strategy produced results.")
        return

    benchmark_metrics = benchmark_result["metrics"] if benchmark_result else None
    benchmark_return = (
        benchmark_metrics.get("total_return_pct", 0.0)
        if benchmark_metrics
        else 0.0
    )

    # ---- Tableau récapitulatif ----
    print("=" * 92)
    print("STRATEGY PERFORMANCE VS BUY & HOLD")
    print("=" * 92)

    header = (
        f"{'Strategy':<30}{'Final Capital':>16}{'Total %':>10}"
        f"{'Max DD %':>10}{'Trades':>10}{'Δ vs B&H':>12}"
    )
    print(header)
    print("-" * len(header))

    for entry in results:
        metrics = entry["metrics"]
        total_return_pct = metrics.get("total_return_pct", 0.0)
        diff_vs_bench = total_return_pct - benchmark_return
        if entry["is_benchmark"]:
            diff_vs_bench = 0.0

        print(
            f"{entry['name']:<30}"
            f"${metrics.get('final_capital', INITIAL_CAPITAL):>15,.2f}"
            f"{total_return_pct:>9.2f}%"
            f"{metrics.get('max_drawdown', 0.0):>9.2f}%"
            f"{metrics.get('total_trades', 0):>10d}"
            f"{diff_vs_bench:>11.2f}%"
        )

    print("=" * 92)

    if benchmark_result:
        non_benchmark_results = [r for r in results if not r["is_benchmark"]]
        outperform = sum(
            1
            for r in non_benchmark_results
            if r["metrics"].get("total_return_pct", 0.0) > benchmark_return
        )
        underperform = sum(
            1
            for r in non_benchmark_results
            if r["metrics"].get("total_return_pct", 0.0) < benchmark_return
        )
        tie = len(non_benchmark_results) - outperform - underperform

        print(
            f"Strategies outperforming Buy & Hold: {outperform} | "
            f"Underperforming: {underperform} | Similar: {tie}"
        )

        top_non_benchmark = (
            max(
                non_benchmark_results,
                key=lambda r: r["metrics"].get("total_return", float('-inf')),
            )
            if non_benchmark_results
            else None
        )
    else:
        top_non_benchmark = None

    if top_non_benchmark:
        top_name = top_non_benchmark["name"]
        top_metrics = top_non_benchmark["metrics"]
        top_df = top_non_benchmark["df"]
        top_trades = top_non_benchmark["trades"]

        print()
        print("=" * 60)
        print("TOP NON-BENCHMARK STRATEGY SUMMARY")
        print("=" * 60)

        final_value = top_metrics.get("final_capital", INITIAL_CAPITAL)
        total_return = top_metrics.get("total_return_pct", 0.0)
        win_rate = top_metrics.get("win_rate", 0.0)
        max_dd = top_metrics.get("max_drawdown", 0.0)
        sharpe = top_metrics.get("sharpe_ratio", 0.0)
        calmar = top_metrics.get("calmar_ratio", 0.0)
        num_trades = top_metrics.get("total_trades", 0)

        print(f"Strategy: {top_name}")
        print("Capital:")
        print(f"  • Initial: ${INITIAL_CAPITAL:,.2f}")
        print(f"  • Final  : ${final_value:,.2f}")
        print(f"  • Return : {total_return:.2f}%")
        print()
        print("Trading:")
        print(f"  • Total trades : {num_trades}")
        print(f"  • Win rate     : {win_rate:.2f}%")
        print()
        print("Risk:")
        print(f"  • Max drawdown : {max_dd:.2f}%")
        print(f"  • Sharpe ratio : {sharpe:.2f}")
        print(f"  • Calmar ratio : {calmar:.2f}")

        diff = total_return - benchmark_return
        if benchmark_result:
            print(f"  • Δ vs Buy & Hold: {diff:+.2f}%")

        print("=" * 60)

        # ---- Graphiques ----
        viz = BacktestVisualizer(figsize=(16, 10))
        viz.plot_backtest(
            df=top_df,
            trades=top_trades,
            title=(
                f"Top Non-Benchmark: {top_name} - {symbol} ({interval}, {period})"
            ),
        )
    else:
        print("No non-benchmark strategies available for detailed summary.")


# ------------------ MENU PRINCIPAL ------------------
def main_menu(
    default_interval: str = DEFAULT_INTERVAL,
    default_period: str = DEFAULT_PERIOD,
):
    setup_logging()
    load_dotenv()

    current_interval = (
        default_interval if default_interval in ALLOWED_INTERVALS else DEFAULT_INTERVAL
    )
    current_period = (
        default_period if default_period in ALLOWED_PERIODS else DEFAULT_PERIOD
    )

    while True:
        print()
        print("=" * 60)
        print("TheMiidsOne Crypto Bot - MAIN MENU")
        print("=" * 60)
        print(
            "1) Backtest multi-strategies (BNBUSDT, "
            f"{current_interval}, {PERIOD_DEFINITIONS[current_period]['label']})"
        )
        print("2) Optimisation RSI")
        print("3) Live Bot (TEST MODE)")
        print("0) Quit")
        print()

        choice = input("Your choice: ").strip()

        if choice == "1":
            selected_interval = prompt_interval(current_interval)
            selected_period = prompt_period(current_period)
            run_multi_strategy_backtest(
                interval=selected_interval,
                period=selected_period,
            )
            current_interval = selected_interval
            current_period = selected_period
        elif choice == "2":
            rsi_optimize_main()
        elif choice == "3":
            live_bot_main()
        elif choice == "0":
            print("Bye.")
            break
        else:
            print("Invalid choice, try again.")


def parse_args():
    parser = argparse.ArgumentParser(description="Crypto bot main menu")
    parser.add_argument(
        "--interval",
        choices=ALLOWED_INTERVALS,
        default=DEFAULT_INTERVAL,
        help="Default interval used for multi-strategy backtests.",
    )
    parser.add_argument(
        "--period",
        choices=ALLOWED_PERIODS,
        default=DEFAULT_PERIOD,
        help="Default history length used for multi-strategy backtests.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main_menu(
        default_interval=args.interval,
        default_period=args.period,
    )
