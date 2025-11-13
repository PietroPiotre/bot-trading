import os
from dotenv import load_dotenv
from optimizer import LiveTradingBot
from strategies import RSIStrategy

def main():
    print("=" * 60)
    print("🤖 LIVE TRADING BOT (TEST MODE)")
    print("=" * 60)

    # Charger les variables d'environnement (.env)
    load_dotenv()

    API_KEY = os.getenv("BINANCE_API_KEY")
    API_SECRET = os.getenv("BINANCE_API_SECRET")

    if not API_KEY or not API_SECRET:
        print("❌ Erreur : API Key ou Secret manquant dans le fichier .env")
        print("   Vérifie que tu as bien :")
        print("   BINANCE_API_KEY=xxxxxxxxxx")
        print("   BINANCE_API_SECRET=xxxxxxxxxx")
        return

    # Stratégie utilisée par le bot (RSI simple par défaut)
    strategy = RSIStrategy(
        {
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
        }
    )

    # Création du bot
    bot = LiveTradingBot(
        api_key=API_KEY,
        api_secret=API_SECRET,
        strategy=strategy,
        symbol="BNBUSDT",
        test_mode=True,   # ⚠️ ON RESTE EN MODE TEST
        interval="1h",
    )

    # Lancer le bot (par exemple 6h pour commencer)
    bot.run(duration_hours=6)

if __name__ == "__main__":
    main()
