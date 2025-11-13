import itertools
import pandas as pd
from datetime import datetime, timedelta

from config import DEFAULT_SYMBOL
from data_manager import DataManager
from backtester import Backtester
from strategies import MACDStrategy


def get_date_range(choice: int):
    """Retourne start_date / end_date selon le choix utilisateur"""
    end_dt = datetime.today()

    if choice == 1:   # 30 jours
        start_dt = end_dt - timedelta(days=30)
    elif choice == 2:  # 90 jours
        start_dt = end_dt - timedelta(days=90)
    elif choice == 3:  # 6 mois
        start_dt = end_dt - timedelta(days=180)
    elif choice == 4:  # 1 an
        start_dt = end_dt - timedelta(days=365)
    else:  # 2 ans
        start_dt = end_dt - timedelta(days=730)

    return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")


def main():
    print("=" * 60)
    print("🔧 MACD STRATEGY OPTIMIZER")
    print("=" * 60)

    print("\n📅 Choisis la période d’optimisation :")
    print("1) 30 jours")
    print("2) 90 jours")
    print("3) 6 mois")
    print("4) 1 an")
    print("5) 2 ans (recommandé)")
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
    print("🔍 Optimizing MACD Strategy...")

    fast_list = [8, 12, 16]
    slow_list = [18, 26, 35]
    signal_list = [5, 9, 12]

    combinations = list(itertools.product(fast_list, slow_list, signal_list))
    print(f"  Testing {len(combinations)} parameter combinations...")

    results = []
    best = None

    for idx, (fast, slow, signal_period) in enumerate(combinations, start=1):
        strat = MACDStrategy({
            "macd_fast": fast,
            "macd_slow": slow,
            "macd_signal": signal_period
        })

        bt = Backtester()
        _, metrics = bt.run(df, strat)

        result = {
            "fast": fast,
            "slow": slow,
            "signal": signal_period,
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

    print("\n🏆 Meilleurs paramètres trouvés :")
    print(best)

    df_res = pd.DataFrame(results)
    df_res = df_res.sort_values(by="return", ascending=False)

    print("\n📈 TOP 10 COMBOS :")
    top10 = df_res.head(10)
    for i, row in top10.iterrows():
        print(f"{len(results)}. fast={row['fast']}, slow={row['slow']}, signal={row['signal']} "
              f"| Return={row['return']:.2f}% | Sharpe={row['sharpe']:.2f} | MaxDD={row['maxdd']:.2f}% "
              f"| Trades={row['trades']} | WinRate={row['winrate']:.1f}%")

    df_res.to_csv("optimization_macd_results.csv", index=False)
    print("\n💾 Résultats sauvegardés → optimization_macd_results.csv")


if __name__ == "__main__":
    main()
