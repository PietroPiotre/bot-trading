# main.py
import argparse
import os
import logging

from dotenv import load_dotenv

from config import (
    DEFAULT_SYMBOL,
    DEFAULT_INTERVAL,
    ALLOWED_INTERVALS,
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


# ------------------ PARAMÈTRES GLOBAUX SIMPLES ------------------
# BNB par défaut
SYMBOL = DEFAULT_SYMBOL if DEFAULT_SYMBOL else "BNBUSDT"

# Période par défaut pour le backtest (choix 1)
START_DATE = "2024-01-01"
END_DATE = "2025-11-01"

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
def run_multi_strategy_backtest(interval: str = DEFAULT_INTERVAL):
    load_dotenv()
    setup_logging()

    symbol = SYMBOL
    start_date = START_DATE
    end_date = END_DATE

    if interval not in ALLOWED_INTERVALS:
        logging.warning(
            "Interval '%s' is not supported. Falling back to '%s'.",
            interval,
            DEFAULT_INTERVAL,
        )
        interval = DEFAULT_INTERVAL

    stop_loss = STOP_LOSS_PERCENT
    take_profit = TAKE_PROFIT_PERCENT

    print("=" * 60)
    print("CRYPTO TRADING BOT - MULTI STRATEGY BACKTEST")
    print("=" * 60)
    print(f"Symbol      : {symbol}")
    print(f"Interval    : {interval}")
    print(f"Period      : {start_date} -> {end_date}")
    print(f"Capital init: ${INITIAL_CAPITAL:,.2f}")
    print(f"Stop loss   : {stop_loss * 100:.2f} %")
    print(f"Take profit : {take_profit * 100:.2f} %")
    print()

    logging.info(
        f"Backtest multi-strategies: {symbol} {interval} {start_date} -> {end_date}"
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
    strategy_list = [
        ("RSI Strategy", RSIStrategy()),
        ("MACD Strategy", MACDStrategy()),
        ("Bollinger Bands", BollingerBandsStrategy()),
        ("MA Cross", MovingAverageCrossStrategy()),
        ("Combined Strategy", CombinedStrategy()),
        # Référence Buy & Hold ajoutée pour le benchmark simple.
        ("Buy & Hold", BuyAndHoldStrategy()),
    ]

    backtester = Backtester(
        initial_capital=INITIAL_CAPITAL,
        commission=COMMISSION,
        slippage=SLIPPAGE,
    )

    best = None
    benchmark_metrics = None

    for name, strategy in strategy_list:
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

        if name == "Buy & Hold":
            # On mémorise les métriques pour le comparatif final (copie défensive).
            benchmark_metrics = metrics.copy()

        log_strategy_metrics(name, metrics)

        if best is None or metrics.get("total_return", -999) > best["metrics"].get(
            "total_return", -999
        ):
            best = {
                "name": name,
                # On stocke une copie pour éviter qu'une mutation ultérieure n'affecte le résumé.
                "metrics": metrics.copy(),
                "df": bt_df,
                "trades": trades_df,
            }

    print()
    if best is None:
        print("No strategy produced results.")
        return

    best_name = best["name"]
    best_metrics = best["metrics"]
    best_df = best["df"]
    best_trades = best["trades"]
    logging.info(f"Best strategy: {best_name}")
    print(f"Best strategy: {best_name}")

    # ---- Résumé ----
    print()
    print("=" * 60)
    print("BACKTEST SUMMARY")
    print("=" * 60)

    final_value = best_metrics.get("final_capital", INITIAL_CAPITAL)
    total_return = best_metrics.get("total_return_pct", 0.0)
    win_rate = best_metrics.get("win_rate", 0.0)
    max_dd = best_metrics.get("max_drawdown", 0.0)
    sharpe = best_metrics.get("sharpe_ratio", 0.0)
    calmar = best_metrics.get("calmar_ratio", 0.0)
    num_trades = best_metrics.get("total_trades", 0)

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

    if benchmark_metrics is not None:
        bench_final = benchmark_metrics.get("final_capital", INITIAL_CAPITAL)
        bench_return = benchmark_metrics.get("total_return_pct", 0.0)
        bench_max_dd = benchmark_metrics.get("max_drawdown", 0.0)

        print()
        print("Benchmark Buy & Hold:")
        print(f"  • Final capital : ${bench_final:,.2f}")
        print(f"  • Return        : {bench_return:.2f}%")
        print(f"  • Max drawdown  : {bench_max_dd:.2f}%")

        diff = total_return - bench_return
        print(f"Compared to Buy & Hold: {diff:+.2f}%")

    print("=" * 60)

    # ---- Graphiques ----
    viz = BacktestVisualizer(figsize=(16, 10))
    viz.plot_backtest(
        df=best_df,
        trades=best_trades,
        title=f"Best Strategy: {best_name} - {symbol} ({interval})",
    )


# ------------------ MENU PRINCIPAL ------------------
def main_menu(default_interval: str = DEFAULT_INTERVAL):
    setup_logging()
    load_dotenv()

    current_interval = default_interval if default_interval in ALLOWED_INTERVALS else DEFAULT_INTERVAL

    while True:
        print()
        print("=" * 60)
        print("TheMiidsOne Crypto Bot - MAIN MENU")
        print("=" * 60)
        print(f"1) Backtest multi-strategies (BNBUSDT, {current_interval})")
        print("2) Optimisation RSI")
        print("3) Live Bot (TEST MODE)")
        print("0) Quit")
        print()

        choice = input("Your choice: ").strip()

        if choice == "1":
            selected_interval = prompt_interval(current_interval)
            run_multi_strategy_backtest(interval=selected_interval)
            current_interval = selected_interval
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
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main_menu(default_interval=args.interval)
