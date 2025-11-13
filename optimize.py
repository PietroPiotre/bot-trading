import logging
from datetime import datetime, timedelta
from data_manager import DataManager
from backtester import Backtester
from strategies import RSIStrategy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# =====================================================================
# UTILITAIRES : Durées prédéfinies
# =====================================================================

def get_date_range(option):
    """
    Retourne start_date, end_date selon la durée choisie.
    """
    end = datetime.today()

    if option == "1":     # 30 jours
        start = end - timedelta(days=30)
    elif option == "2":   # 90 jours
        start = end - timedelta(days=90)
    elif option == "3":   # 6 mois
        start = end - timedelta(days=180)
    elif option == "4":   # 1 an
        start = end - timedelta(days=365)
    elif option == "5":   # 2 ans
        start = end - timedelta(days=730)
    else:
        raise ValueError("Option invalide.")

    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


# =====================================================================
# OPTIMISATION RSI
# =====================================================================

def optimize_rsi(symbol, interval, start_date, end_date):
    """
    Teste une grille de RSI et retourne les meilleures combinaisons.
    """
    logging.info(f"Optimisation RSI sur {symbol} | {interval} | {start_date} -> {end_date}")

    dm = DataManager()
    df = dm.get_historical_data(symbol, interval, start_date, end_date)

    if df is None or df.empty:
        logging.error("No historical data retrieved. Aborting optimisation.")
        return []

    results = []
    combinations = 0

    # Grille simple mais efficace
    rsi_periods = [10, 12, 14, 16, 18, 20]
    oversold_levels = [20, 25, 30]
    overbought_levels = [70, 75, 80]

    total_combos = len(rsi_periods) * len(oversold_levels) * len(overbought_levels)
    print(f"🔍 Testing {total_combos} combinations...")

    backtester = Backtester()

    for period in rsi_periods:
        for oversold in oversold_levels:
            for overbought in overbought_levels:

                strategy = RSIStrategy(
                    rsi_period=period,
                    oversold=oversold,
                    overbought=overbought
                )

                _, performance = backtester.run(
                    data=df.copy(),
                    strategy=strategy,
                )

                results.append({
                    "period": period,
                    "oversold": oversold,
                    "overbought": overbought,
                    "return": performance["total_return_pct"],
                    "sharpe": performance["sharpe_ratio"],
                    "maxdd": performance["max_drawdown"],
                    "trades": performance["total_trades"],
                    "winrate": performance["win_rate"]
                })

                combinations += 1
                if combinations % 10 == 0:
                    print(f"Progress: {combinations}/{total_combos}")

    # Trier du meilleur rendement vers le pire
    results = sorted(results, key=lambda x: x["return"], reverse=True)

    return results


# =====================================================================
# MENU PRINCIPAL
# =====================================================================

def main():
    print("=" * 60)
    print("🔧 RSI STRATEGY OPTIMIZER")
    print("=" * 60)

    # --------------------------------------------------------
    # PAR DÉFAUT : BNB
    # --------------------------------------------------------
    default_symbol = "BNBUSDT"

    print(f"\n📌 Symbole par défaut : {default_symbol}")
    use_default = input("Utiliser BNB ? (O/n) : ").strip().lower()

    if use_default == "n":
        symbol = input("👉 Entre un symbole (ex: BTCUSDT) : ").upper().strip()
    else:
        symbol = default_symbol

    interval = "1h"

    # --------------------------------------------------------
    # CHOIX DE DURÉE
    # --------------------------------------------------------

    print("\n⏱️ Choisis la durée du backtest :")
    print(" 1) 30 jours")
    print(" 2) 90 jours")
    print(" 3) 6 mois")
    print(" 4) 1 an")
    print(" 5) 2 ans")

    choice = input("\n👉 Ton choix : ").strip()

    start_date, end_date = get_date_range(choice)

    print(f"\n📊 Optimisation sur {symbol} | {interval} | {start_date} → {end_date}\n")

    # --------------------------------------------------------
    # LANCER L'OPTIMISATION
    # --------------------------------------------------------

    results = optimize_rsi(symbol, interval, start_date, end_date)

    if not results:
        print("❌ Optimisation interrompue : aucune donnée disponible.")
        return

    best = results[0]
    print("\n🏆 BEST PARAMETERS FOUND :")
    print(best)

    print("\n📈 TOP 10 COMBINATIONS :")
    for i, r in enumerate(results[:10], start=1):
        print(
            f"{i}. period={r['period']}, oversold={r['oversold']}, overbought={r['overbought']} "
            f"| Return={r['return']:.2f}% | Sharpe={r['sharpe']:.2f} | MaxDD={r['maxdd']:.2f}% "
            f"| Trades={r['trades']} | WinRate={r['winrate']:.1f}%"
        )


# =====================================================================
if __name__ == "__main__":
    main()

