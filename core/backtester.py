import pandas as pd
from datetime import time
import os

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
        self.portfolio_value = [100000] # Initialize with starting capital

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

        market_open = time(9, 15)
        market_close = time(15, 30)

        for date, group in all_data.groupby(level='date'):
            if not market_open <= date.time() <= market_close:
                continue

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
                    quantity = int(trade_value / entry_price) # Ensure integer quantity
                    if quantity > 0:
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
                if (sym, date) in all_data.index:
                    current_price = all_data.loc[(sym, date), 'close']
                    current_value += (current_price - position['entry_price']) * position['quantity']
            self.portfolio_value.append(current_value)


    def generate_report(self):
        """
        Generates a detailed performance report and saves trade logs to CSV.
        """
        if not self.trades:
            print("No trades were made during the backtest.")
            return

        trade_df = pd.DataFrame(self.trades)

        # --- Per-Symbol Summary Calculation ---
        summary_rows = []
        for symbol, group in trade_df.groupby('symbol'):
            sells = group[group['type'] == 'SELL']
            total_pnl = sells['pnl'].sum()
            num_trades = len(sells)
            winning_trades = sells[sells['pnl'] > 0]
            losing_trades = sells[sells['pnl'] <= 0]
            num_winning = len(winning_trades)
            num_losing = len(losing_trades)
            win_loss_ratio = num_winning / num_losing if num_losing > 0 else float('inf')

            # Per-symbol max drawdown
            symbol_trades = trade_df[trade_df['symbol'] == symbol]
            symbol_portfolio_value = [100000] # Start with initial capital for each symbol
            for _, row in symbol_trades.iterrows():
                if 'pnl' in row and pd.notna(row['pnl']):
                    symbol_portfolio_value.append(symbol_portfolio_value[-1] + row['pnl'])

            portfolio_series = pd.Series(symbol_portfolio_value)
            peak = portfolio_series.expanding(min_periods=1).max()
            drawdown = (portfolio_series - peak) / peak
            max_drawdown = drawdown.min()


            summary_rows.append({
                "Symbol": symbol,
                "Total_P/L": f"{total_pnl:,.2f}",
                "Total_Trades": num_trades,
                "Winning_Trades": num_winning,
                "Losing_Trades": num_losing,
                "Win/Loss_Ratio": f"{win_loss_ratio:.2f}",
                "Max_Drawdown": f"{max_drawdown:.2%}"
            })

        summary_df = pd.DataFrame(summary_rows)

        print("\n-------------------------------------------Backtest Summary-----------------------------------------")
        print(summary_df.to_string(index=False))

        # --- CSV Export ---
        if not os.path.exists('backtest'):
            os.makedirs('backtest')

        # Group trades by symbol and save each to a CSV
        for symbol, group in trade_df.groupby('symbol'):
            csv_path = os.path.join('backtest', f"{symbol}_tradelog.csv")
            group.to_csv(csv_path, index=False)
            print(f"\nTrade log for {symbol} saved to {csv_path}")
