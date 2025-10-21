import pandas as pd

class Backtester:
    """
    A class for backtesting a trading strategy.
    """
    def __init__(self, strategy, data):
        """
        Initializes the Backtester with a strategy and historical data.
        """
        self.strategy = strategy
        self.data = data
        self.trades = []
        self.portfolio_value = []

    def run(self, initial_capital=100000):
        """
        Runs the backtest.
        """
        capital = initial_capital
        positions = {} # {symbol: {entry_price, quantity}}

        # Prepare the data by calculating all necessary indicators
        self.data = self.strategy.prepare_data(self.data)

        # Combine all data into a single DataFrame with a multi-index
        all_data = pd.concat(self.data.values(), keys=self.data.keys(), names=['symbol', 'date'])
        all_data.sort_index(inplace=True)

        for date, group in all_data.groupby(level='date'):
            for idx, row in group.iterrows():
                symbol = idx[0] # Get the symbol from the multi-index tuple (symbol, date)
                df = self.data[symbol]
                df_slice = df.loc[:date]

                if len(df_slice) < 2:
                    continue

                signal = self.strategy._check_signal(df_slice)

                if signal == 'BUY' and symbol not in positions and len(positions) < self.strategy.config['risk_management']['max_open_positions']:
                    # Open a new position
                    entry_price = row['close']
                    trade_value = capital * self.strategy.config['risk_management']['capital_allocation_per_trade']
                    quantity = trade_value / entry_price
                    positions[symbol] = {'entry_price': entry_price, 'quantity': quantity}
                    self.trades.append({'symbol': symbol, 'type': 'BUY', 'price': entry_price, 'quantity': quantity, 'date': date})

                elif signal == 'SELL' and symbol in positions:
                    # Close the existing position
                    exit_price = row['close']
                    pnl = (exit_price - positions[symbol]['entry_price']) * positions[symbol]['quantity']
                    capital += pnl
                    self.trades.append({'symbol': symbol, 'type': 'SELL', 'price': exit_price, 'quantity': positions[symbol]['quantity'], 'pnl': pnl, 'date': date})
                    del positions[symbol]

            # Update portfolio value
            current_value = capital
            for sym, position in positions.items():
                current_value += (all_data.loc[(sym, date), 'close'] - position['entry_price']) * position['quantity']
            self.portfolio_value.append(current_value)

    def generate_report(self):
        """
        Generates a performance report.
        """
        total_pnl = sum(trade['pnl'] for trade in self.trades if 'pnl' in trade)
        winning_trades = [trade for trade in self.trades if 'pnl' in trade and trade['pnl'] > 0]
        losing_trades = [trade for trade in self.trades if 'pnl' in trade and trade['pnl'] <= 0]
        win_loss_ratio = len(winning_trades) / len(losing_trades) if len(losing_trades) > 0 else float('inf')

        # Max Drawdown
        peak = self.portfolio_value[0]
        max_drawdown = 0
        for value in self.portfolio_value:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        print("--- Backtest Report ---")
        print(f"Total P/L: {total_pnl:.2f}")
        print(f"Win/Loss Ratio: {win_loss_ratio:.2f}")
        print(f"Max Drawdown: {max_drawdown:.2%}")

        print("\n--- Trade Log ---")
        for trade in self.trades:
            print(trade)
