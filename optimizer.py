# optimizer.py
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
                    print(f"    ✅ New best: Return={total_return:.2f}%, Sharpe={sharpe:.2f}")
                
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
                
                score = metrics['total_return_pct'] + (metrics['sharpe_ratio'] * 10)
                
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

# ============================================
# bot.py - Bot de Trading Live
from binance.client import Client
from binance.exceptions import BinanceAPIException
import time
from datetime import datetime
import json

class LiveTradingBot:
    """Bot de trading en temps réel"""
    
    def __init__(self, api_key, api_secret, strategy, symbol='BTCUSDT', 
                 test_mode=True, interval='1h'):
        self.client = Client(api_key, api_secret)
        self.strategy = strategy
        self.symbol = symbol
        self.test_mode = test_mode
        self.interval = interval
        self.position = None
        self.trades_log = []
        
        # Risk management
        self.max_position_size = 0.95
        self.stop_loss_pct = 0.02
        self.take_profit_pct = 0.05
        
        print(f"🤖 Bot initialized - Mode: {'TEST' if test_mode else 'LIVE'}")
        print(f"📊 Trading {symbol} on {interval} timeframe")
    
    def get_account_balance(self):
        """Récupère le solde du compte"""
        try:
            account = self.client.get_account()
            balances = {}
            
            for asset in account['balances']:
                free = float(asset['free'])
                locked = float(asset['locked'])
                if free > 0 or locked > 0:
                    balances[asset['asset']] = {
                        'free': free,
                        'locked': locked,
                        'total': free + locked
                    }
            
            return balances
        except BinanceAPIException as e:
            print(f"Error getting balance: {e}")
            return {}
    
    def get_latest_data(self, limit=100):
        """Récupère les dernières données"""
        try:
            klines = self.client.get_klines(
                symbol=self.symbol,
                interval=self.interval,
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
                df[col] = pd.to_numeric(df[col])
            
            return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
        except BinanceAPIException as e:
            print(f"Error getting data: {e}")
            return None
    
    def calculate_position_size(self, capital, price):
        """Calcule la taille de position appropriée"""
        # Utiliser max_position_size du capital disponible
        position_value = capital * self.max_position_size
        quantity = position_value / price
        
        # Arrondir selon les règles de Binance
        # BTC a généralement 6 décimales
        quantity = round(quantity, 6)
        
        return quantity
    
    def place_order(self, side, quantity):
        """Place un ordre sur Binance"""
        if self.test_mode:
            # Mode test - simuler l'ordre
            current_price = float(self.client.get_symbol_ticker(symbol=self.symbol)['price'])
            
            print(f"[TEST ORDER]")
            print(f"  Side: {side}")
            print(f"  Quantity: {quantity}")
            print(f"  Price: ${current_price:,.2f}")
            
            return {
                'orderId': f"TEST_{int(time.time())}",
                'status': 'FILLED',
                'side': side,
                'executedQty': quantity,
                'price': current_price
            }
        
        try:
            # Mode live - ordre réel
            if side == 'BUY':
                order = self.client.create_order(
                    symbol=self.symbol,
                    side=Client.SIDE_BUY,
                    type=Client.ORDER_TYPE_MARKET,
                    quantity=quantity
                )
            else:  # SELL
                order = self.client.create_order(
                    symbol=self.symbol,
                    side=Client.SIDE_SELL,
                    type=Client.ORDER_TYPE_MARKET,
                    quantity=quantity
                )
            
            print(f"✅ Order executed: {order['orderId']}")
            return order
            
        except BinanceAPIException as e:
            print(f"❌ Order failed: {e}")
            return None
    
    def check_stop_loss_take_profit(self):
        """Vérifie si SL ou TP est atteint"""
        if self.position is None:
            return False
        
        current_price = float(self.client.get_symbol_ticker(symbol=self.symbol)['price'])
        entry_price = self.position['entry_price']
        
        # Calculer le changement en %
        price_change = (current_price - entry_price) / entry_price
        
        # Check Stop Loss
        if price_change <= -self.stop_loss_pct:
            print(f"🛑 Stop Loss triggered at {price_change*100:.2f}%")
            return 'STOP_LOSS'
        
        # Check Take Profit
        if price_change >= self.take_profit_pct:
            print(f"🎯 Take Profit triggered at {price_change*100:.2f}%")
            return 'TAKE_PROFIT'
        
        return False
    
    def run(self, duration_hours=24):
        """
        Exécute le bot pendant une durée spécifiée
        
        Args:
            duration_hours: Durée d'exécution en heures
        """
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=duration_hours)
        
        print(f"\n🚀 Bot started at {start_time}")
        print(f"⏰ Will run until {end_time}")
        print("-" * 50)
        
        while datetime.now() < end_time:
            try:
                # 1. Récupérer les données
                data = self.get_latest_data(100)
                
                if data is not None:
                    # 2. Générer les signaux
                    signals_df = self.strategy.generate_signals(data)
                    latest_signal = signals_df.iloc[-1]
                    
                    # 3. Afficher les infos
                    current_time = datetime.now().strftime("%H:%M:%S")
                    current_price = latest_signal['close']
                    
                    print(f"\n[{current_time}] Price: ${current_price:,.2f}")
                    
                    # 4. Vérifier SL/TP
                    sl_tp_trigger = self.check_stop_loss_take_profit()
                    if sl_tp_trigger and self.position:
                        # Fermer la position
                        order = self.place_order('SELL', self.position['quantity'])
                        if order:
                            self.position = None
                            print(f"Position closed - Reason: {sl_tp_trigger}")
                    
                    # 5. Traiter les signaux
                    if latest_signal['signal'] == 1 and not self.position:
                        # Signal d'achat
                        print("🟢 BUY SIGNAL DETECTED")
                        
                        # Calculer la taille de position
                        if self.test_mode:
                            available_capital = 10000  # Capital simulé
                        else:
                            balances = self.get_account_balance()
                            available_capital = balances.get('USDT', {}).get('free', 0)
                        
                        quantity = self.calculate_position_size(available_capital, current_price)
                        
                        # Placer l'ordre
                        order = self.place_order('BUY', quantity)
                        if order:
                            self.position = {
                                'entry_price': current_price,
                                'quantity': quantity,
                                'entry_time': datetime.now()
                            }
                    
                    elif latest_signal['signal'] == -1 and self.position:
                        # Signal de vente
                        print("🔴 SELL SIGNAL DETECTED")
                        
                        # Fermer la position
                        order = self.place_order('SELL', self.position['quantity'])
                        if order:
                            # Calculer le P&L
                            pnl = (current_price - self.position['entry_price']) * self.position['quantity']
                            pnl_pct = ((current_price - self.position['entry_price']) / self.position['entry_price']) * 100
                            
                            print(f"Position closed - P&L: ${pnl:.2f} ({pnl_pct:.2f}%)")
                            
                            # Logger le trade
                            self.trades_log.append({
                                'entry_time': self.position['entry_time'],
                                'exit_time': datetime.now(),
                                'entry_price': self.position['entry_price'],
                                'exit_price': current_price,
                                'quantity': self.position['quantity'],
                                'pnl': pnl,
                                'pnl_pct': pnl_pct
                            })
                            
                            self.position = None
                    
                    # 6. Afficher le statut
                    if self.position:
                        pnl = (current_price - self.position['entry_price']) * self.position['quantity']
                        pnl_pct = ((current_price - self.position['entry_price']) / self.position['entry_price']) * 100
                        print(f"📊 Position: LONG | P&L: ${pnl:.2f} ({pnl_pct:+.2f}%)")
                    else:
                        print("📊 Position: NONE")
                
                # Attendre avant la prochaine itération
                time.sleep(60)  # Vérifier toutes les minutes
                
            except KeyboardInterrupt:
                print("\n⚠️ Bot stopped by user")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(60)
        
        # Fin du bot
        self.print_summary()
    
    def print_summary(self):
        """Affiche un résumé des performances"""
        print("\n" + "="*60)
        print("📊 TRADING SUMMARY")
        print("="*60)
        
        if self.trades_log:
            total_trades = len(self.trades_log)
            winning_trades = sum(1 for t in self.trades_log if t['pnl'] > 0)
            total_pnl = sum(t['pnl'] for t in self.trades_log)
            
            print(f"Total Trades: {total_trades}")
            print(f"Winning Trades: {winning_trades}")
            print(f"Win Rate: {(winning_trades/total_trades)*100:.2f}%")
            print(f"Total P&L: ${total_pnl:.2f}")
            
            # Sauvegarder les trades
            with open(f"trades_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w') as f:
                json.dump(self.trades_log, f, indent=4, default=str)
        else:
            print("No trades executed")
        
        print("="*60)