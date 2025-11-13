# strategies.py
import pandas as pd
import numpy as np
from indicators import TechnicalIndicators
from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    """Classe de base pour toutes les stratégies"""

    # Par défaut, les stratégies utilisent le stop-loss / take-profit gérés
    # dans le backtester. Les stratégies qui ne doivent pas y être soumises
    # (ex: Buy & Hold) peuvent surcharger ce flag.
    allow_stop_take = True
    
    def __init__(self, params=None):
        self.params = params or {}
        self.indicators = TechnicalIndicators()
        
    @abstractmethod
    def generate_signals(self, data):
        """Génère les signaux de trading"""
        pass
    
    def apply_risk_management(self, signals, data):
        """Applique les règles de gestion du risque"""
        # Stop Loss et Take Profit seront gérés dans le backtester
        return signals

class RSIStrategy(BaseStrategy):
    """Stratégie basée sur le RSI"""
    
    def __init__(self, params=None):
        super().__init__(params)
        self.rsi_period = self.params.get('rsi_period', 14)
        self.rsi_oversold = self.params.get('rsi_oversold', 30)
        self.rsi_overbought = self.params.get('rsi_overbought', 70)
    
    def generate_signals(self, data):
        """Génère les signaux basés sur le RSI"""
        df = data.copy()
        
        # Calculer RSI
        df['RSI'] = self.indicators.RSI(df['close'], self.rsi_period)
        
        # Initialiser les signaux
        df['signal'] = 0
        df['position'] = 0
        
        # Générer les signaux
        # Achat quand RSI < oversold
        df.loc[df['RSI'] < self.rsi_oversold, 'signal'] = 1
        # Vente quand RSI > overbought
        df.loc[df['RSI'] > self.rsi_overbought, 'signal'] = -1
        
        # Calculer les positions
        df['position'] = df['signal'].replace(to_replace=0, method='ffill').fillna(0)
        
        return df

class MACDStrategy(BaseStrategy):
    """Stratégie basée sur le MACD"""
    
    def __init__(self, params=None):
        super().__init__(params)
        self.fast = self.params.get('macd_fast', 12)
        self.slow = self.params.get('macd_slow', 26)
        self.signal_period = self.params.get('macd_signal', 9)
    
    def generate_signals(self, data):
        """Génère les signaux basés sur le MACD"""
        df = data.copy()
        
        # Calculer MACD
        df['MACD'], df['Signal'], df['Histogram'] = self.indicators.MACD(
            df['close'], self.fast, self.slow, self.signal_period
        )
        
        # Initialiser les signaux
        df['signal'] = 0
        df['position'] = 0
        
        # Générer les signaux - Croisement MACD et ligne de signal
        df['prev_macd'] = df['MACD'].shift(1)
        df['prev_signal'] = df['Signal'].shift(1)
        
        # Signal d'achat : MACD croise au-dessus de la ligne de signal
        buy_signal = (df['MACD'] > df['Signal']) & (df['prev_macd'] <= df['prev_signal'])
        df.loc[buy_signal, 'signal'] = 1
        
        # Signal de vente : MACD croise en-dessous de la ligne de signal
        sell_signal = (df['MACD'] < df['Signal']) & (df['prev_macd'] >= df['prev_signal'])
        df.loc[sell_signal, 'signal'] = -1
        
        # Calculer les positions
        df['position'] = df['signal'].replace(to_replace=0, method='ffill').fillna(0)
        
        return df

class BollingerBandsStrategy(BaseStrategy):
    """Stratégie basée sur les Bandes de Bollinger"""
    
    def __init__(self, params=None):
        super().__init__(params)
        self.period = self.params.get('bb_period', 20)
        self.std_dev = self.params.get('bb_std', 2)
    
    def generate_signals(self, data):
        """Génère les signaux basés sur les Bandes de Bollinger"""
        df = data.copy()
        
        # Calculer les Bandes de Bollinger
        df['BB_Upper'], df['BB_Middle'], df['BB_Lower'] = self.indicators.Bollinger_Bands(
            df['close'], self.period, self.std_dev
        )
        
        # Initialiser les signaux
        df['signal'] = 0
        df['position'] = 0
        
        # Générer les signaux
        # Achat quand le prix touche la bande inférieure
        df.loc[df['close'] <= df['BB_Lower'], 'signal'] = 1
        # Vente quand le prix touche la bande supérieure
        df.loc[df['close'] >= df['BB_Upper'], 'signal'] = -1
        
        # Calculer les positions
        df['position'] = df['signal'].replace(to_replace=0, method='ffill').fillna(0)
        
        return df

class CombinedStrategy(BaseStrategy):
    """Stratégie combinant plusieurs indicateurs"""
    
    def __init__(self, params=None):
        super().__init__(params)
        self.rsi_period = self.params.get('rsi_period', 14)
        self.macd_fast = self.params.get('macd_fast', 12)
        self.macd_slow = self.params.get('macd_slow', 26)
        self.macd_signal = self.params.get('macd_signal', 9)
        self.bb_period = self.params.get('bb_period', 20)
        self.bb_std = self.params.get('bb_std', 2)
        
    def generate_signals(self, data):
        """Génère les signaux en combinant RSI, MACD et BB"""
        df = data.copy()
        
        # Calculer tous les indicateurs
        df['RSI'] = self.indicators.RSI(df['close'], self.rsi_period)
        df['MACD'], df['MACD_Signal'], _ = self.indicators.MACD(
            df['close'], self.macd_fast, self.macd_slow, self.macd_signal
        )
        df['BB_Upper'], df['BB_Middle'], df['BB_Lower'] = self.indicators.Bollinger_Bands(
            df['close'], self.bb_period, self.bb_std
        )
        
        # Initialiser les signaux et scores
        df['buy_score'] = 0
        df['sell_score'] = 0
        df['signal'] = 0
        df['position'] = 0
        
        # Scoring système pour les signaux d'achat
        # RSI oversold
        df.loc[df['RSI'] < 30, 'buy_score'] += 1
        df.loc[df['RSI'] < 20, 'buy_score'] += 1  # Signal fort
        
        # MACD bullish
        df.loc[df['MACD'] > df['MACD_Signal'], 'buy_score'] += 1
        
        # Prix près de BB Lower
        df.loc[df['close'] <= df['BB_Lower'], 'buy_score'] += 1
        
        # Scoring système pour les signaux de vente
        # RSI overbought
        df.loc[df['RSI'] > 70, 'sell_score'] += 1
        df.loc[df['RSI'] > 80, 'sell_score'] += 1  # Signal fort
        
        # MACD bearish
        df.loc[df['MACD'] < df['MACD_Signal'], 'sell_score'] += 1
        
        # Prix près de BB Upper
        df.loc[df['close'] >= df['BB_Upper'], 'sell_score'] += 1
        
        # Générer les signaux basés sur les scores
        # Signal d'achat si score >= 2
        df.loc[df['buy_score'] >= 2, 'signal'] = 1
        # Signal de vente si score >= 2
        df.loc[df['sell_score'] >= 2, 'signal'] = -1
        
        # Pour éviter les conflits, priorité aux signaux de vente
        df.loc[(df['buy_score'] >= 2) & (df['sell_score'] >= 2), 'signal'] = 0
        
        # Calculer les positions
        df['position'] = df['signal'].replace(to_replace=0, method='ffill').fillna(0)
        
        # Ajouter des informations supplémentaires pour le debug
        df['signal_strength'] = df[['buy_score', 'sell_score']].max(axis=1)
        
        return df

class MovingAverageCrossStrategy(BaseStrategy):
    """Stratégie de croisement de moyennes mobiles"""

    def __init__(self, params=None):
        super().__init__(params)
        self.fast_period = self.params.get('ma_fast', 20)
        self.slow_period = self.params.get('ma_slow', 50)
        self.ma_type = self.params.get('ma_type', 'EMA')  # 'SMA' ou 'EMA'

    def generate_signals(self, data):
        """Génère les signaux basés sur le croisement de MA"""
        df = data.copy()
        
        # Calculer les moyennes mobiles
        if self.ma_type == 'EMA':
            df['MA_Fast'] = self.indicators.EMA(df['close'], self.fast_period)
            df['MA_Slow'] = self.indicators.EMA(df['close'], self.slow_period)
        else:
            df['MA_Fast'] = self.indicators.SMA(df['close'], self.fast_period)
            df['MA_Slow'] = self.indicators.SMA(df['close'], self.slow_period)
        
        # Initialiser les signaux
        df['signal'] = 0
        df['position'] = 0
        
        # Calculer les croisements
        df['prev_fast'] = df['MA_Fast'].shift(1)
        df['prev_slow'] = df['MA_Slow'].shift(1)
        
        # Golden Cross (achat)
        golden_cross = (df['MA_Fast'] > df['MA_Slow']) & (df['prev_fast'] <= df['prev_slow'])
        df.loc[golden_cross, 'signal'] = 1
        
        # Death Cross (vente)
        death_cross = (df['MA_Fast'] < df['MA_Slow']) & (df['prev_fast'] >= df['prev_slow'])
        df.loc[death_cross, 'signal'] = -1

        # Calculer les positions
        df['position'] = df['signal'].replace(to_replace=0, method='ffill').fillna(0)

        return df


class BuyAndHoldStrategy(BaseStrategy):
    """Stratégie de référence Buy & Hold"""

    # On n'applique pas de stop-loss / take-profit pour Buy & Hold.
    allow_stop_take = False

    def generate_signals(self, data):
        """Achète une seule fois au début puis conserve la position."""
        df = data.copy()

        df['signal'] = 0
        df['position'] = 0

        if len(df) > 1:
            first_tradable_index = df.index[1]
            # On déclenche l'achat sur la première bougie exploitable.
            df.loc[first_tradable_index, 'signal'] = 1

        # La position reste ouverte après le premier achat.
        df['position'] = df['signal'].replace(to_replace=0, method='ffill').fillna(0)

        return df
