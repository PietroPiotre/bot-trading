import itertools
import pandas as pd
from datetime import datetime, timedelta

from config import DEFAULT_SYMBOL
from data_manager import DataManager
from backtester import Backtester
from strategies import MovingAverageCrossStrategy


def get_date_range(choice: int):
    end_dt = datetime.today()

    if choice == 1:
        start_dt = end_dt - timedelta(days=30)
    elif choice == 2:
        start_dt = end_dt - timedelta(days=90)
    elif choice == 3:
        start_dt = end_dt - timedelta(days=180)
    elif choice == 4:
        start_dt = end_dt - timedelta(days=365)
    else:
        start_dt = end_dt - timedelta(days=730)

    return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")


def main():
    print("=" * 60)
    print("🔧 MOVING AVERAGE CROSS OPTIMIZER")
    print("=" * 60)

    print("\n📅 Durée :")
    print("1) 30 jours")
    print("2) 90 jours")
    print("3) 6 mois")
    print("4) 1 an")
    print("5) 2 ans")
    choice = int(input("\n👉 Ton choix : "))

    START_DATE, END_DATE = get_date_range(choice)
    SYMBOL = DEFAULT_SYMBOL
    INTERVAL = "1h"

    print(f"\n📊 Données : {SYMBOL} | {INTERVAL} | {START_DATE} → {END_DATE}")

    dm = DataManager()
    df = dm.get_historical_data(
        symbol=SYMBOL,
        interval=INTERVAL,
        start_date=START_DATE,
        end_date=END_DATE
    )

    print(f"📂 Loaded {len(df)} candles\n")
    print("🔍 Optimizing MA Cross Strategy...")

    fast_list = [10, 20, 30]
    slow_list = [50, 100, 200]
    types = ["EMA", "SMA"]

    combinations = list(itertools.product(fast_list, slow_list, types))
    print(f"  Testing {len(combinations)} combinations...")

    results = []
    best = None

    for idx, (fast, slow, ma_type) in enumerate(combinations, start=1):
        if fast >= slow:
            continue  # évite des croisements absurdes

        strat = MovingAverageCrossStrategy({
            "ma_fast": fast,
            "ma_slow": slow,
            "ma_type": ma_type
        })

        bt = Backtester()
        _, metrics = bt.run(df, strat)

        result = {
            "fast": fast,
            "slow": slow,
            "type": ma_type,
            "return": metrics["total_return_pct"],
            "sharpe": metrics["sharpe_ratio"],
            "maxdd": metrics["max_drawdown"],
            "trades": metrics["total_trades"],
            "winrate": metrics["win_rate"],
        }
        results.append(result)

        if best is None or result["return"] > best["return"]:
            best = result
            print(f"    ✅ New best: Return={best['return']:.2f}% | Sharpe={best['sharpe']:.2f}")

        if idx % 10 == 0:
            print(f"    Progress: {idx}/{len(combinations)}")

    print("\n🏆 Best MA Cross params:")
    print(best)

    df_res = pd.DataFrame(results).sort_values(by="return", ascending=False)

    print("\n📈 TOP 10 :")
    for i, row in df_res.head(10).iterrows():
        print(f" • fast={row['fast']}, slow={row['slow']}, type={row['type']} "
              f"| Return={row['return']:.2f}% | Sharpe={row['sharpe']:.2f} "
              f"| MaxDD={row['maxdd']:.2f}% | Trades={row['trades']} "
              f"| WinRate={row['winrate']:.1f}%")

    df_res.to_csv("optimization_ma_results.csv", index=False)
    print("\n💾 Saved → optimization_ma_results.csv")


if __name__ == "__main__":
    main()
