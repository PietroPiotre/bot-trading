# Structure du Projet Trading Bot avec Backtesting

```
crypto-trading-bot/
│
├── .env                    # Variables d'environnement
├── requirements.txt        # Dépendances Python
├── config.py              # Configuration générale
├── data_manager.py        # Gestion des données
├── indicators.py          # Indicateurs techniques
├── strategies.py          # Stratégies de trading
├── backtester.py          # Moteur de backtesting
├── bot.py                 # Bot principal
├── visualizer.py          # Visualisation des résultats
├── optimizer.py           # Optimisation des paramètres
└── main.py               # Point d'entrée principal
```

## Installation des dépendances

```bash
pip install python-binance pandas numpy matplotlib plotly ta-lib scikit-optimize python-dotenv rich
```

## Configuration (.env)

```env
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
TEST_MODE=True
INITIAL_CAPITAL=10000
TRADING_FEE=0.001
```