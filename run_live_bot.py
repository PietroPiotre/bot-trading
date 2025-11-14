import os
from dotenv import load_dotenv
from strategies import RSIStrategy
import json
from datetime import datetime, timedelta
import time
from binance.exceptions import BinanceAPIException
from binance.client import Client
import pandas as pd


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
            current_price = float(self.client.get_symbol_ticker(
                symbol=self.symbol)['price'])

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

        current_price = float(self.client.get_symbol_ticker(
            symbol=self.symbol)['price'])
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
                        order = self.place_order(
                            'SELL', self.position['quantity'])
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
                            available_capital = balances.get(
                                'USDT', {}).get('free', 0)

                        quantity = self.calculate_position_size(
                            available_capital, current_price)

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
                        order = self.place_order(
                            'SELL', self.position['quantity'])
                        if order:
                            # Calculer le P&L
                            pnl = (
                                current_price - self.position['entry_price']) * self.position['quantity']
                            pnl_pct = (
                                (current_price - self.position['entry_price']) / self.position['entry_price']) * 100

                            print(
                                f"Position closed - P&L: ${pnl:.2f} ({pnl_pct:.2f}%)")

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
                        pnl = (
                            current_price - self.position['entry_price']) * self.position['quantity']
                        pnl_pct = (
                            (current_price - self.position['entry_price']) / self.position['entry_price']) * 100
                        print(
                            f"📊 Position: LONG | P&L: ${pnl:.2f} ({pnl_pct:+.2f}%)")
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
