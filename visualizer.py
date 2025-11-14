# visualizer.py
from strategies import (RSIStrategy, MACDStrategy, BollingerBandsStrategy,
                        CombinedStrategy, MovingAverageCrossStrategy)
import warnings
from backtester import Backtester
from data_manager import DataManager
from datetime import datetime, timedelta
import sys
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.gridspec import GridSpec
import pandas as pd
import numpy as np
import seaborn as sns


class BacktestVisualizer:
    """Classe pour visualiser les résultats du backtesting"""

    def __init__(self, figsize=(15, 10)):
        self.figsize = figsize
        sns.set_style("darkgrid")
        plt.rcParams['figure.facecolor'] = 'white'
        plt.rcParams['axes.facecolor'] = 'white'

    def plot_backtest_results(self, df, trades_df=None, title="Backtest Results"):
        """
        Crée un graphique complet des résultats du backtest

        Args:
            df: DataFrame avec les résultats du backtest
            trades_df: DataFrame avec les détails des trades
            title: Titre du graphique
        """
        fig = plt.figure(figsize=(15, 12))
        gs = GridSpec(4, 2, figure=fig, hspace=0.3, wspace=0.3)

        # 1. Prix et signaux de trading
        ax1 = fig.add_subplot(gs[0, :])
        ax1.plot(df['timestamp'], df['close'],
                 label='Close Price', linewidth=1)

        # Marquer les points d'achat et de vente
        buy_signals = df[df['signal'] == 1]
        sell_signals = df[df['signal'] == -1]

        ax1.scatter(buy_signals['timestamp'], buy_signals['close'],
                    color='green', marker='^', s=100, label='Buy Signal', zorder=5)
        ax1.scatter(sell_signals['timestamp'], sell_signals['close'],
                    color='red', marker='v', s=100, label='Sell Signal', zorder=5)

        ax1.set_title(f'{title} - Price and Trading Signals',
                      fontsize=12, fontweight='bold')
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Price ($)')
        ax1.legend(loc='best')
        ax1.grid(True, alpha=0.3)

        # 2. Equity Curve
        ax2 = fig.add_subplot(gs[1, :])
        ax2.plot(df['timestamp'], df['total_value'], label='Portfolio Value',
                 color='blue', linewidth=2)
        ax2.axhline(y=df['total_value'].iloc[0], color='gray',
                    linestyle='--', alpha=0.5, label='Initial Capital')

        # Colorier les zones de profit/perte
        ax2.fill_between(df['timestamp'], df['total_value'].iloc[0], df['total_value'],
                         where=(df['total_value'] >=
                                df['total_value'].iloc[0]),
                         color='green', alpha=0.1, label='Profit')
        ax2.fill_between(df['timestamp'], df['total_value'].iloc[0], df['total_value'],
                         where=(df['total_value'] < df['total_value'].iloc[0]),
                         color='red', alpha=0.1, label='Loss')

        ax2.set_title('Equity Curve', fontsize=12, fontweight='bold')
        ax2.set_xlabel('Date')
        ax2.set_ylabel('Portfolio Value ($)')
        ax2.legend(loc='best')
        ax2.grid(True, alpha=0.3)

        # 3. Drawdown
        ax3 = fig.add_subplot(gs[2, :])
        running_max = df['total_value'].cummax()
        drawdown = ((df['total_value'] - running_max) / running_max) * 100

        ax3.fill_between(df['timestamp'], 0, drawdown, color='red', alpha=0.3)
        ax3.plot(df['timestamp'], drawdown, color='red', linewidth=1)

        ax3.set_title('Drawdown (%)', fontsize=12, fontweight='bold')
        ax3.set_xlabel('Date')
        ax3.set_ylabel('Drawdown (%)')
        ax3.grid(True, alpha=0.3)

        # 4. Distribution des returns
        ax4 = fig.add_subplot(gs[3, 0])
        returns = df['returns'].dropna() * 100  # En pourcentage
        ax4.hist(returns, bins=50, color='blue', alpha=0.6, edgecolor='black')
        ax4.axvline(x=0, color='red', linestyle='--', alpha=0.5)
        ax4.set_title('Returns Distribution', fontsize=12, fontweight='bold')
        ax4.set_xlabel('Returns (%)')
        ax4.set_ylabel('Frequency')
        ax4.grid(True, alpha=0.3)

        # Ajouter statistiques sur le graphique
        mean_return = returns.mean()
        std_return = returns.std()
        ax4.text(0.05, 0.95, f'Mean: {mean_return:.3f}%\nStd: {std_return:.3f}%',
                 transform=ax4.transAxes, verticalalignment='top',
                 bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        # 5. Trades P&L
        ax5 = fig.add_subplot(gs[3, 1])
        if trades_df is not None and len(trades_df) > 0:
            pnl_pct = trades_df['pnl_percent'] * 100
            colors = ['green' if x > 0 else 'red' for x in pnl_pct]
            bars = ax5.bar(range(len(pnl_pct)), pnl_pct,
                           color=colors, alpha=0.6)

            ax5.set_title('Individual Trade P&L (%)',
                          fontsize=12, fontweight='bold')
            ax5.set_xlabel('Trade Number')
            ax5.set_ylabel('P&L (%)')
            ax5.axhline(y=0, color='black', linestyle='-', alpha=0.3)
            ax5.grid(True, alpha=0.3)

            # Ajouter la moyenne
            avg_pnl = pnl_pct.mean()
            ax5.axhline(y=avg_pnl, color='blue', linestyle='--',
                        alpha=0.5, label=f'Avg: {avg_pnl:.2f}%')
            ax5.legend()

        plt.suptitle(title, fontsize=16, fontweight='bold', y=1.02)
        plt.tight_layout()
        return fig

    def plot_backtest(self, df, trades=None, title="Backtest Results"):
        """Compatibilité ascendante avec l'API historique du visualiseur.

        L'interface du projet appelait auparavant :meth:`plot_backtest`, mais le
        corps principal a été renommé en :meth:`plot_backtest_results`.  Cette
        fine couche délègue simplement pour éviter les attribut errors.
        """

        return self.plot_backtest_results(df, trades_df=trades, title=title)

    def plot_strategy_comparison(self, results_dict):
        """
        Compare plusieurs stratégies

        Args:
            results_dict: Dictionnaire {strategy_name: (df, metrics)}
        """
        fig, axes = plt.subplots(2, 2, figsize=self.figsize)

        # 1. Comparaison des equity curves
        ax1 = axes[0, 0]
        for name, (df, metrics) in results_dict.items():
            ax1.plot(df['timestamp'], df['total_value'],
                     label=name, linewidth=2)

        ax1.set_title('Equity Curves Comparison', fontweight='bold')
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Portfolio Value ($)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # 2. Comparaison des returns
        ax2 = axes[0, 1]
        returns_data = []
        labels = []
        for name, (df, metrics) in results_dict.items():
            returns_data.append(metrics['total_return_pct'])
            labels.append(name)

        bars = ax2.bar(labels, returns_data)
        for i, bar in enumerate(bars):
            bar.set_color('green' if returns_data[i] > 0 else 'red')
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                     f'{returns_data[i]:.1f}%', ha='center', va='bottom')

        ax2.set_title('Total Return Comparison', fontweight='bold')
        ax2.set_ylabel('Return (%)')
        ax2.grid(True, alpha=0.3)

        # 3. Comparaison du Sharpe Ratio
        ax3 = axes[1, 0]
        sharpe_data = []
        for name, (df, metrics) in results_dict.items():
            sharpe_data.append(metrics['sharpe_ratio'])

        bars = ax3.bar(labels, sharpe_data)
        for i, bar in enumerate(bars):
            ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                     f'{sharpe_data[i]:.2f}', ha='center', va='bottom')

        ax3.set_title('Sharpe Ratio Comparison', fontweight='bold')
        ax3.set_ylabel('Sharpe Ratio')
        ax3.grid(True, alpha=0.3)

        # 4. Comparaison du Max Drawdown
        ax4 = axes[1, 1]
        dd_data = []
        for name, (df, metrics) in results_dict.items():
            dd_data.append(abs(metrics['max_drawdown']))

        bars = ax4.bar(labels, dd_data, color='red', alpha=0.6)
        for i, bar in enumerate(bars):
            ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                     f'{dd_data[i]:.1f}%', ha='center', va='bottom')

        ax4.set_title('Max Drawdown Comparison', fontweight='bold')
        ax4.set_ylabel('Max Drawdown (%)')
        ax4.grid(True, alpha=0.3)

        plt.suptitle('Strategy Comparison', fontsize=16, fontweight='bold')
        plt.tight_layout()
        return fig

    def plot_heatmap(self, df, indicator='RSI'):
        """Crée une heatmap pour visualiser un indicateur"""
        # Créer un pivot pour la heatmap
        df['hour'] = df['timestamp'].dt.hour
        df['day'] = df['timestamp'].dt.date

        if indicator in df.columns:
            pivot = df.pivot_table(values=indicator, index='hour',
                                   columns='day', aggfunc='mean')

            fig, ax = plt.subplots(figsize=(15, 8))
            sns.heatmap(pivot, cmap='RdYlGn_r', center=50,
                        cbar_kws={'label': indicator}, ax=ax)
            ax.set_title(f'{indicator} Heatmap by Hour and Day',
                         fontweight='bold')
            ax.set_xlabel('Date')
            ax.set_ylabel('Hour of Day')

            return fig
        else:
            print(f"Indicator {indicator} not found in dataframe")
            return None


