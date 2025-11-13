# backtester.py
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

from datetime import datetime
from typing import Dict, List, Tuple, Optional


class Backtester:
    """
    Moteur de backtesting pour tester les stratégies.

    Modèle d'exécution réaliste pour le spot crypto :
    - Commission par trade (par défaut 0.075% ≈ Binance avec réduction BNB)
    - Slippage + spread moyen (par défaut 0.025% par côté)
    - Latence : exécution sur la bougie suivante (latency_bars = 1)
    - Prix d'exécution : open de la bougie d'exécution
    """

    def __init__(
        self,
        initial_capital: float = 10000.0,
        commission: float = 0.00075,
        slippage: float = 0.00025,
        latency_bars: int = 1,
        execution_mode: str = "next_open",
    ):
        """
        Args:
            initial_capital: Capital initial
            commission: Commission par trade (0.00075 = 0.075%)
            slippage: Slippage + spread estimé (0.00025 = 0.025%)
            latency_bars: Nombre de bougies de latence entre signal et exécution
            execution_mode: Mode de prix d'exécution
                - "next_open": prix = open de la bougie d'exécution
        """
        self.initial_capital = float(initial_capital)
        self.commission = float(commission)
        self.slippage = float(slippage)
        self.latency_bars = int(latency_bars)
        self.execution_mode = execution_mode

        self.reset()

    def reset(self):
        """Réinitialise l'état du backtester."""
        self.capital = self.initial_capital
        self.position = 0.0           # quantité de l'actif
        self.entry_price: Optional[float] = None
        self.trades: List[Dict] = []
        self.current_trade: Optional[Dict] = None

    # ------------------------------------------------------------------ #
    #  Helpers d'exécution
    # ------------------------------------------------------------------ #
    def _get_execution_index(self, i: int, last_index: int) -> int:
        """
        Retourne l'index de la bougie d'exécution en tenant compte de la latence.
        On borne pour éviter de dépasser la dernière bougie.
        """
        exec_idx = i + self.latency_bars
        if exec_idx > last_index:
            exec_idx = last_index
        return exec_idx

    def _get_execution_price(self, df: pd.DataFrame, exec_idx: int, side: str) -> float:
        """
        Calcule le prix d'exécution brut (sans commission) selon le mode choisi.
        side: "buy" ou "sell"
        """
        if self.execution_mode == "next_open":
            base_price = float(df.iloc[exec_idx]["open"])
        else:
            # fallback : close
            base_price = float(df.iloc[exec_idx]["close"])

        # Slippage + spread : on majore le prix à l'achat, on minore à la vente
        if side == "buy":
            return base_price * (1.0 + self.slippage)
        else:
            return base_price * (1.0 - self.slippage)

    # ------------------------------------------------------------------ #
    #  Backtest principal
    # ------------------------------------------------------------------ #
    def run(
        self,
        data: pd.DataFrame,
        strategy,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        position_size: float = 1.0,
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Exécute le backtest sur les données et la stratégie donnée.

        Args:
            data: DataFrame OHLCV avec au minimum: ['timestamp','open','high','low','close','volume']
            strategy: instance de stratégie avec méthode generate_signals(df) -> df avec colonne 'signal'
            stop_loss: stop loss en pourcentage (0.02 = 2%). Si None => pas de SL.
            take_profit: take profit en pourcentage (0.05 = 5%). Si None => pas de TP.
            position_size: fraction du capital allouée quand on ouvre une position (0.5 = 50% du capital)

        Returns:
            df_result: DataFrame avec la courbe d'équité et colonnes de suivi
            metrics: dict des métriques de performance
        """
        # Sécurité
        if "timestamp" not in data.columns:
            data = data.copy()
            data["timestamp"] = data.index

        # Reset state
        self.reset()

        # Générer les signaux (1 = buy, -1 = sell, 0 = rien)
        df = strategy.generate_signals(data.copy())

        # Colonnes de suivi
        df["capital"] = self.initial_capital
        df["position_qty"] = 0.0
        df["position_value"] = 0.0
        df["cash"] = self.initial_capital
        df["total_value"] = self.initial_capital
        df["returns"] = 0.0
        df["cumulative_returns"] = 0.0
        df["drawdown"] = 0.0
        df["peak"] = self.initial_capital

        last_index = len(df) - 1

        # Boucle principale
        for i in range(1, len(df)):
            price_close = float(df.iloc[i]["close"])

            # Mettre à jour la valeur de la position au prix actuel (close)
            position_value = self.position * price_close

            # Vérifier Stop Loss / Take Profit sur la position ouverte (sur close)
            signal = df.iloc[i]["signal"] if "signal" in df.columns else 0

            if self.position != 0 and self.entry_price is not None:
                price_change_pct = (price_close - self.entry_price) / self.entry_price

                # Long uniquement pour l'instant
                if self.position > 0:
                    if stop_loss is not None and price_change_pct <= -abs(stop_loss):
                        self._close_position(df, i, "Stop Loss")
                        signal = 0  # déjà sorti
                    elif take_profit is not None and price_change_pct >= abs(take_profit):
                        self._close_position(df, i, "Take Profit")
                        signal = 0

            # Gestion des signaux d'entrée/sortie
            if signal == 1:
                # BUY signal
                if self.position == 0:
                    self._open_position(df, i, side="buy", position_size=position_size)
                else:
                    # On est déjà en position long -> possibilité de pyramiding plus tard
                    pass

            elif signal == -1:
                # SELL signal = fermer la position long
                if self.position > 0:
                    self._close_position(df, i, "Signal Exit")

            # Mettre à jour les colonnes finales pour cette bougie
            price_close = float(df.iloc[i]["close"])
            position_value = self.position * price_close
            total_value = self.capital + position_value

            df.iloc[i, df.columns.get_loc("position_qty")] = self.position
            df.iloc[i, df.columns.get_loc("position_value")] = position_value
            df.iloc[i, df.columns.get_loc("cash")] = self.capital
            df.iloc[i, df.columns.get_loc("total_value")] = total_value

            # Returns & drawdown
            prev_total = df.iloc[i - 1]["total_value"]
            if prev_total != 0:
                ret = (total_value - prev_total) / prev_total
            else:
                ret = 0.0
            df.iloc[i, df.columns.get_loc("returns")] = ret

            cum_ret = (total_value - self.initial_capital) / self.initial_capital
            df.iloc[i, df.columns.get_loc("cumulative_returns")] = cum_ret

            peak = max(df.iloc[i - 1]["peak"], total_value)
            df.iloc[i, df.columns.get_loc("peak")] = peak
            drawdown = (total_value - peak) / peak if peak != 0 else 0.0
            df.iloc[i, df.columns.get_loc("drawdown")] = drawdown

        # Forcer la clôture de toute position encore ouverte à la fin du backtest.
        if self.position > 0:
            self._close_position(df, last_index, "End of Period")

        metrics = self.calculate_metrics(df)
        return df, metrics

    # ------------------------------------------------------------------ #
    #  Gestion des positions
    # ------------------------------------------------------------------ #
    def _open_position(
        self,
        df: pd.DataFrame,
        index: int,
        side: str = "buy",
        position_size: float = 1.0,
    ):
        """Ouvre une position (long uniquement pour l'instant)."""
        last_index = len(df) - 1
        exec_idx = self._get_execution_index(index, last_index)
        exec_price = self._get_execution_price(df, exec_idx, side=side)

        # Capital disponible pour cette position
        available_capital = self.capital * float(position_size)

        # Coût brut
        qty = available_capital / exec_price if exec_price > 0 else 0.0
        gross_cost = qty * exec_price
        trade_cost = gross_cost * self.commission

        if qty <= 0 or available_capital <= 0:
            return

        # Mettre à jour le capital
        self.position = qty
        self.entry_price = exec_price
        self.capital -= (gross_cost + trade_cost)

        # Créer le trade
        self.current_trade = {
            "entry_date": df.iloc[exec_idx]["timestamp"],
            "entry_price": exec_price,
            "quantity": qty,
            "side": side,
            "commission": trade_cost,
        }

    def _close_position(
        self,
        df: pd.DataFrame,
        index: int,
        reason: str = "Exit",
    ):
        """Ferme la position long actuelle."""
        if self.position == 0 or self.entry_price is None:
            return

        last_index = len(df) - 1
        exec_idx = self._get_execution_index(index, last_index)
        exec_price = self._get_execution_price(df, exec_idx, side="sell")

        qty = self.position
        gross_proceeds = qty * exec_price
        trade_cost = gross_proceeds * self.commission

        # Mettre à jour le capital
        self.capital += (gross_proceeds - trade_cost)

        # Enregistrer le trade
        if self.current_trade is None:
            self.current_trade = {
                "entry_date": df.iloc[exec_idx]["timestamp"],
                "entry_price": self.entry_price,
                "quantity": qty,
                "side": "buy",
                "commission": 0.0,
            }

        pnl = (exec_price - self.current_trade["entry_price"]) * qty
        pnl_pct = (exec_price - self.current_trade["entry_price"]) / self.current_trade["entry_price"]

        self.current_trade.update(
            {
                "exit_date": df.iloc[exec_idx]["timestamp"],
                "exit_price": exec_price,
                "exit_reason": reason,
                "pnl": pnl,
                "pnl_percent": pnl_pct,
                "commission": self.current_trade.get("commission", 0.0) + trade_cost,
            }
        )

        self.trades.append(self.current_trade)
        self.current_trade = None
        self.position = 0.0
        self.entry_price = None

    # ------------------------------------------------------------------ #
    #  Métriques & reporting
    # ------------------------------------------------------------------ #
    def calculate_metrics(self, df: pd.DataFrame) -> Dict:
        """Calcule les métriques de performance."""
        metrics: Dict = {}

        # Métriques de base
        metrics["initial_capital"] = self.initial_capital
        metrics["final_capital"] = float(df.iloc[-1]["total_value"])
        metrics["total_return"] = (metrics["final_capital"] - self.initial_capital) / self.initial_capital
        metrics["total_return_pct"] = metrics["total_return"] * 100.0

        # Métriques des trades
        metrics["total_trades"] = len(self.trades)

        if self.trades:
            winning_trades = [t for t in self.trades if t["pnl"] > 0]
            losing_trades = [t for t in self.trades if t["pnl"] < 0]

            metrics["winning_trades"] = len(winning_trades)
            metrics["losing_trades"] = len(losing_trades)
            metrics["win_rate"] = (
                (metrics["winning_trades"] / metrics["total_trades"]) * 100.0
                if metrics["total_trades"] > 0
                else 0.0
            )

            metrics["avg_win"] = float(np.mean([t["pnl"] for t in winning_trades])) if winning_trades else 0.0
            metrics["avg_loss"] = float(np.mean([t["pnl"] for t in losing_trades])) if losing_trades else 0.0

            if metrics["avg_loss"] != 0 and metrics["losing_trades"] > 0:
                metrics["profit_factor"] = abs(metrics["avg_win"] / metrics["avg_loss"])
            else:
                metrics["profit_factor"] = 0.0

            metrics["max_win"] = max([t["pnl"] for t in winning_trades]) if winning_trades else 0.0
            metrics["max_loss"] = min([t["pnl"] for t in losing_trades]) if losing_trades else 0.0
        else:
            metrics["winning_trades"] = 0
            metrics["losing_trades"] = 0
            metrics["win_rate"] = 0.0
            metrics["avg_win"] = 0.0
            metrics["avg_loss"] = 0.0
            metrics["profit_factor"] = 0.0
            metrics["max_win"] = 0.0
            metrics["max_loss"] = 0.0

        # Volatilité & Sharpe
        returns = df["returns"].dropna()
        if len(returns) > 0:
            metrics["volatility"] = float(returns.std() * np.sqrt(365))
            metrics["sharpe_ratio"] = (
                metrics["total_return"] / metrics["volatility"] if metrics["volatility"] > 0 else 0.0
            )
        else:
            metrics["volatility"] = 0.0
            metrics["sharpe_ratio"] = 0.0

        # Drawdown max & Calmar
        drawdowns = df["drawdown"].dropna()
        if len(drawdowns) > 0:
            metrics["max_drawdown"] = float(drawdowns.min() * 100.0)
        else:
            metrics["max_drawdown"] = 0.0

        if metrics["max_drawdown"] != 0:
            metrics["calmar_ratio"] = metrics["total_return_pct"] / abs(metrics["max_drawdown"])
        else:
            metrics["calmar_ratio"] = 0.0

        # Période de backtest
        try:
            start_ts = pd.to_datetime(df["timestamp"].iloc[0])
            end_ts = pd.to_datetime(df["timestamp"].iloc[-1])
            days = (end_ts - start_ts).days
        except Exception:
            days = 0

        metrics["backtest_days"] = days
        metrics["annual_return"] = (
            (1 + metrics["total_return"]) ** (365.0 / days) - 1 if days > 0 else 0.0
        ) * 100.0

        return metrics

    def get_trade_log(self) -> pd.DataFrame:
        """Retourne le journal des trades sous forme de DataFrame."""
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame(self.trades)

    def print_performance_summary(self, metrics: Dict):
        """Affiche un résumé lisible des performances."""
        print("\n============================================================")
        print("📊 RÉSUMÉ DES PERFORMANCES DU BACKTEST")
        print("============================================================")

        print("\n💰 Capital:")
        print(f"  • Initial: ${metrics['initial_capital']:,.2f}")
        print(f"  • Final: ${metrics['final_capital']:,.2f}")
        print(f"  • Return: {metrics['total_return_pct']:.2f}%")

        print("\n📈 Trading:")
        print(f"  • Total Trades: {metrics['total_trades']}")
        print(f"  • Winning Trades: {metrics['winning_trades']}")
        print(f"  • Losing Trades: {metrics['losing_trades']}")
        print(f"  • Win Rate: {metrics['win_rate']:.2f}%")

        print("\n💵 Profit/Loss:")
        print(f"  • Average Win: ${metrics['avg_win']:,.2f}")
        print(f"  • Average Loss: ${metrics['avg_loss']:,.2f}")
        print(f"  • Max Win: ${metrics['max_win']:,.2f}")
        print(f"  • Max Loss: ${metrics['max_loss']:,.2f}")
        print(f"  • Profit Factor: {metrics['profit_factor']:.2f}")

        print("\n📉 Risk Metrics:")
        print(f"  • Max Drawdown: {metrics['max_drawdown']:.2f}%")
        print(f"  • Volatility (Annual): {metrics['volatility']*100:.2f}%")
        print(f"  • Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"  • Calmar Ratio: {metrics['calmar_ratio']:.2f}")

        print("\n⏱️ Time:")
        print(f"  • Backtest Period: {metrics.get('backtest_days', 0)} days")
        print(f"  • Annual Return: {metrics.get('annual_return', 0):.2f}%")
        print("============================================================")
