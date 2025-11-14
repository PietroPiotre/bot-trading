# data_manager.py
import pandas as pd
import numpy as np
from binance.client import Client
from datetime import datetime, timedelta
import json
import os


class DataManager:
    def __init__(self, api_key=None, api_secret=None):
        """Initialise le gestionnaire de données"""
        self.client = Client(api_key or '', api_secret or '')
        self.cache_dir = 'data_cache'
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def fetch_historical_data(self, symbol, interval, start_date, end_date=None):
        """
        Récupère les données historiques de Binance

        Args:
            symbol: Paire de trading (ex: 'BTCUSDT')
            interval: Intervalle temporel (ex: '1h')
            start_date: Date de début (datetime ou string)
            end_date: Date de fin (datetime ou string)
        """

        # Conversion des dates
        if isinstance(start_date, str):
            start_date = pd.to_datetime(start_date)
        if end_date and isinstance(end_date, str):
            end_date = pd.to_datetime(end_date)

        # Vérifier le cache d'abord
        cache_file = self._get_cache_filename(
            symbol, interval, start_date, end_date)
        if os.path.exists(cache_file):
            print(f"📂 Chargement depuis le cache: {cache_file}")
            return pd.read_csv(cache_file, parse_dates=['timestamp'])

        print(
            f"📥 Téléchargement des données {symbol} {interval} depuis Binance...")

        # Convertir les dates en millisecondes
        start_ms = int(start_date.timestamp() * 1000)
        end_ms = int(end_date.timestamp() * 1000) if end_date else None

        # Récupérer les données
        klines = []
        temp_end_ms = end_ms

        while True:
            try:
                if temp_end_ms:
                    temp_klines = self.client.get_historical_klines(
                        symbol, interval, start_ms, temp_end_ms, limit=1000
                    )
                else:
                    temp_klines = self.client.get_historical_klines(
                        symbol, interval, start_ms, limit=1000
                    )

                if not temp_klines:
                    break

                klines.extend(temp_klines)

                # Si on a moins de 1000 résultats, on a tout récupéré
                if len(temp_klines) < 1000:
                    break

                # Mettre à jour start_ms pour la prochaine requête
                start_ms = int(temp_klines[-1][0]) + 1

                # Si on a dépassé la date de fin, arrêter
                if end_ms and start_ms >= end_ms:
                    break

            except Exception as e:
                print(f"Erreur lors de la récupération des données: {e}")
                break

        # Créer DataFrame
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])

        # Convertir les types
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')

        for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Supprimer les colonnes inutiles
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]

        # Sauvegarder en cache
        df.to_csv(cache_file, index=False)
        print(f"💾 Données sauvegardées en cache: {cache_file}")

        return df

    def get_historical_data(
        self,
        symbol,
        interval,
        start_date,
        end_date=None,
        prepare: bool = True,
    ):
        """Public helper used across the app to load cached Binance data.

        Historically the project referenced ``get_historical_data`` while the
        implementation only exposed ``fetch_historical_data``.  Re-introducing
        this wrapper keeps backward compatibility and centralises optional data
        preparation for the backtester.

        Args:
            symbol: Trading pair, e.g. ``'BTCUSDT'``.
            interval: Candle interval accepted by Binance, e.g. ``'1h'``.
            start_date: Start date (``datetime`` or ISO string).
            end_date: Optional end date (``datetime`` or ISO string).
            prepare: When ``True`` (default) enriches the dataset with returns
                via :meth:`prepare_data_for_backtesting`.

        Returns:
            pandas.DataFrame: cleaned OHLCV dataset ready for backtesting, or
            ``None`` if no data could be retrieved.
        """

        df = self.fetch_historical_data(symbol, interval, start_date, end_date)

        if df is None or df.empty:
            return df

        if prepare:
            df = self.prepare_data_for_backtesting(df)

        return df

    def _get_cache_filename(self, symbol, interval, start_date, end_date):
        """Génère un nom de fichier pour le cache"""
        start_str = start_date.strftime('%Y%m%d')
        end_str = end_date.strftime('%Y%m%d') if end_date else 'now'
        return os.path.join(
            self.cache_dir,
            f"{symbol}_{interval}_{start_str}_{end_str}.csv"
        )

    def prepare_data_for_backtesting(self, df):
        """Prépare les données pour le backtesting"""
        # S'assurer que les données sont triées par date
        df = df.sort_values('timestamp').reset_index(drop=True)

        # Ajouter des colonnes utiles
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))

        return df

    def get_latest_data(self, symbol, interval='1m', limit=100):
        """Récupère les dernières données pour le trading en temps réel"""
        klines = self.client.get_klines(
            symbol=symbol,
            interval=interval,
            limit=limit
        )

        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])

        # Convertir les types
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]

    def save_backtest_results(self, results, filename):
        """Sauvegarde les résultats du backtesting"""
        results_dir = 'backtest_results'
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)

        filepath = os.path.join(results_dir, filename)

        # Sauvegarder en JSON pour les dictionnaires
        if isinstance(results, dict):
            with open(filepath + '.json', 'w') as f:
                json.dump(results, f, indent=4, default=str)

        # Sauvegarder en CSV pour les DataFrames
        elif isinstance(results, pd.DataFrame):
            results.to_csv(filepath + '.csv', index=False)

        print(f"📊 Résultats sauvegardés: {filepath}")
