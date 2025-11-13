 # Crypto Trading Bot - Pack de Fichiers

Ce dossier contient les fichiers Python déjà prêts avec la nouvelle structure :

 - `config.py`          : configuration générale (API, capital, paramètres globaux)
 - `data_manager.py`    : récupération et préparation des données Binance
 - `indicators.py`      : classe `TechnicalIndicators` (RSI, MACD, Bollinger, etc.)
 - `strategies.py`      : stratégies de trading (RSI, MACD, Bollinger, MA Cross, Combined)
 - `backtester.py`      : moteur de backtesting
 - `optimizer.py`       : optimisation des stratégies + bot live (Binance)
 - `visualizer.py`      : visualisation des résultats + fonction `main()` de backtest
 - `trading-bot-structure.md` : schéma de la structure du projet
 - `setup-guide.md`     : guide d'installation et d'utilisation

 Place simplement tout le contenu de ce dossier dans ton projet
 `crypto-trading-bot/` (ou clone ce dossier tel quel), crée ton
 environnement virtuel, installe les dépendances depuis `setup-guide.md`
 puis lance par exemple :

 ```bash
 python -m venv venv
 source venv/bin/activate  # ou venv\Scripts\activate sous Windows
 pip install -r requirements.txt  # à créer selon setup-guide.md
 python visualizer.py      # pour lancer le main() de backtest
 ```
