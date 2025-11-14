# indicators.py
import pandas as pd
import numpy as np


class TechnicalIndicators:
    """Classe contenant tous les indicateurs techniques"""

    @staticmethod
    def SMA(data, period):
        """Simple Moving Average"""
        return data.rolling(window=period).mean()

    @staticmethod
    def EMA(data, period):
        """Exponential Moving Average"""
        return data.ewm(span=period, adjust=False).mean()

    @staticmethod
    def RSI(data, period=14):
        """Relative Strength Index"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def MACD(data, fast_period=12, slow_period=26, signal_period=9):
        """MACD - Moving Average Convergence Divergence"""
        ema_fast = data.ewm(span=fast_period, adjust=False).mean()
        ema_slow = data.ewm(span=slow_period, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def Bollinger_Bands(data, period=20, std_dev=2):
        """Bollinger Bands"""
        sma = data.rolling(window=period).mean()
        std = data.rolling(window=period).std()
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        return upper_band, sma, lower_band

    @staticmethod
    def ATR(high, low, close, period=14):
        """Average True Range"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr

    @staticmethod
    def Stochastic(high, low, close, period=14, smooth_k=3, smooth_d=3):
        """Stochastic Oscillator"""
        lowest_low = low.rolling(window=period).min()
        highest_high = high.rolling(window=period).max()
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        k_percent = k_percent.rolling(window=smooth_k).mean()
        d_percent = k_percent.rolling(window=smooth_d).mean()
        return k_percent, d_percent

    @staticmethod
    def Volume_Profile(volume, close, bins=20):
        """Volume Profile - Distribution du volume par niveau de prix"""
        price_bins = pd.cut(close, bins=bins)
        volume_profile = volume.groupby(price_bins).sum()
        return volume_profile
