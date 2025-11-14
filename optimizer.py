# optimizer.py
import json
from datetime import datetime
import time
from binance.exceptions import BinanceAPIException
from binance.client import Client
import numpy as np
import pandas as pd
from itertools import product
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
from backtester import Backtester
from strategies import *


class StrategyOptimizer:
    """Optimise les paramètres des stratégies"""

    def __init__(self, data, initial_capital=10000, commission=0.001):
        self.data = data
        self.initial_capital = initial_capital
        self.commission = commission
        self.results = []

    def optimize_rsi_strategy(self, param_ranges=None):
        """Optimise les paramètres de la stratégie RSI"""

        if param_ranges is None:
            param_ranges = {
                'rsi_period': range(10, 21, 2),
                'rsi_oversold': range(20, 35, 5),
                'rsi_overbought': range(65, 81, 5)
            }

        print("🔍 Optimizing RSI Strategy...")
        best_params = None
        best_return = -float('inf')

        # Générer toutes les combinaisons
        param_combinations = list(product(
            param_ranges['rsi_period'],
            param_ranges['rsi_oversold'],
            param_ranges['rsi_overbought']
        ))

        total = len(param_combinations)
        print(f"  Testing {total} parameter combinations...")

        for i, (period, oversold, overbought) in enumerate(param_combinations):
            # Skip invalid combinations
            if oversold >= overbought:
                continue

            params = {
                'rsi_period': period,
                'rsi_oversold': oversold,
                'rsi_overbought': overbought
            }

            # Test strategy
            strategy = RSIStrategy(params)
            backtester = Backtester(self.initial_capital, self.commission)

            try:
                df_results, metrics = backtester.run(
                    self.data,
                    strategy,
                    stop_loss=0.02,
                    take_profit=0.05
                )

                total_return = metrics['total_return_pct']
                sharpe = metrics['sharpe_ratio']

                # Score combiné (return + sharpe)
                score = total_return + (sharpe * 10)

                self.results.append({
                    'strategy': 'RSI',
                    'params': params,
                    'return': total_return,
                    'sharpe': sharpe,
                    'max_dd': metrics['max_drawdown'],
                    'trades': metrics['total_trades'],
                    'win_rate': metrics['win_rate'],
                    'score': score
                })

                if score > best_return:
                    best_return = score
                    best_params = params
                    print(
                        f"    ✅ New best: Return={total_return:.2f}%, Sharpe={sharpe:.2f}")

            except Exception as e:
                continue

            # Progress
            if (i + 1) % 10 == 0:
                print(f"    Progress: {i+1}/{total}")

        return best_params, self.results

    def optimize_macd_strategy(self, param_ranges=None):
        """Optimise les paramètres de la stratégie MACD"""

        if param_ranges is None:
            param_ranges = {
                'macd_fast': range(8, 15, 2),
                'macd_slow': range(20, 30, 2),
                'macd_signal': range(7, 12, 1)
            }

        print("🔍 Optimizing MACD Strategy...")
        best_params = None
        best_return = -float('inf')

        param_combinations = list(product(
            param_ranges['macd_fast'],
            param_ranges['macd_slow'],
            param_ranges['macd_signal']
        ))

        for fast, slow, signal in param_combinations:
            if fast >= slow:
                continue

            params = {
                'macd_fast': fast,
                'macd_slow': slow,
                'macd_signal': signal
            }

            strategy = MACDStrategy(params)
            backtester = Backtester(self.initial_capital, self.commission)

            try:
                df_results, metrics = backtester.run(
                    self.data,
                    strategy,
                    stop_loss=0.02,
                    take_profit=0.05
                )

                score = metrics['total_return_pct'] + \
                    (metrics['sharpe_ratio'] * 10)

                if score > best_return:
                    best_return = score
                    best_params = params

            except:
                continue

        return best_params

    def grid_search(self, strategy_class, param_grid, scoring='return'):
        """
        Recherche exhaustive sur une grille de paramètres

        Args:
            strategy_class: Classe de stratégie à optimiser
            param_grid: Dictionnaire des paramètres et leurs valeurs
            scoring: Métrique à optimiser ('return', 'sharpe', 'calmar')
        """
        results = []
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())

        for params in product(*param_values):
            param_dict = dict(zip(param_names, params))

            strategy = strategy_class(param_dict)
            backtester = Backtester(self.initial_capital, self.commission)

            try:
                df_results, metrics = backtester.run(self.data, strategy)

                if scoring == 'return':
                    score = metrics['total_return_pct']
                elif scoring == 'sharpe':
                    score = metrics['sharpe_ratio']
                elif scoring == 'calmar':
                    score = metrics['calmar_ratio']
                else:
                    score = metrics['total_return_pct']

                results.append({
                    'params': param_dict,
                    'score': score,
                    'metrics': metrics
                })
            except:
                continue

        # Trier par score
        results.sort(key=lambda x: x['score'], reverse=True)

        return results[0] if results else None

    def walk_forward_analysis(self, strategy_class, params, window_size=30, step_size=7):
        """
        Walk-forward analysis pour validation

        Args:
            strategy_class: Classe de stratégie
            params: Paramètres de la stratégie
            window_size: Taille de la fenêtre d'entraînement (jours)
            step_size: Pas de déplacement (jours)
        """
        results = []
        data_length = len(self.data)

        # Convertir en nombre de périodes
        periods_per_day = 24  # Pour des données horaires
        window_periods = window_size * periods_per_day
        step_periods = step_size * periods_per_day

        start = 0
        while start + window_periods < data_length:
            # Données d'entraînement
            train_data = self.data.iloc[start:start + window_periods]

            # Données de test (prochain step)
            test_start = start + window_periods
            test_end = min(test_start + step_periods, data_length)
            test_data = self.data.iloc[test_start:test_end]

            # Backtest sur données de test
            strategy = strategy_class(params)
            backtester = Backtester(self.initial_capital, self.commission)

            try:
                df_results, metrics = backtester.run(test_data, strategy)
                results.append({
                    'period_start': test_data.iloc[0]['timestamp'],
                    'period_end': test_data.iloc[-1]['timestamp'],
                    'return': metrics['total_return_pct'],
                    'sharpe': metrics['sharpe_ratio'],
                    'trades': metrics['total_trades']
                })
            except:
                pass

            start += step_periods

        # Calculer les statistiques
        if results:
            avg_return = np.mean([r['return'] for r in results])
            std_return = np.std([r['return'] for r in results])
            win_periods = sum(1 for r in results if r['return'] > 0)
            consistency = win_periods / len(results) * 100

            return {
                'avg_return': avg_return,
                'std_return': std_return,
                'consistency': consistency,
                'periods': results
            }

        return None


