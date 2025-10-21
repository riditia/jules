import yaml
import time
import pandas as pd
from brokers.dhan import DhanBroker
from strategies.basic import BasicStrategy
from core.ui import display_indicators, display_positions, display_funds
from core.indicators import calculate_rsi, calculate_adx, calculate_vwap

def load_config():
    """
    Loads the configuration from configs/config.yaml.
    """
    with open('configs/config.yaml', 'r') as f:
        return yaml.safe_load(f)

def main():
    """
    The main entry point for the trading bot.
    """
    config = load_config()
    broker = DhanBroker()
    strategy = BasicStrategy(broker, config)
    from datetime import datetime, timedelta

    while True:
        # 1. Generate signals for all configured symbols
        all_signals = []
        for symbol in config['instruments']['nifty50_symbols']:
            signals = strategy.get_live_signals(symbol)
            if signals:
                all_signals.extend(signals)

        # 2. Process signals and place orders
        open_positions_data = broker.get_open_positions()
        open_positions = []
        if open_positions_data and open_positions_data.get('status') == 'success' and isinstance(open_positions_data.get('data'), list):
            open_positions = open_positions_data['data']
        account_balance = broker.get_account_balance()

        if account_balance and account_balance.get('data'):
            for action, symbol in all_signals:
                security_id = broker.security_id_map.get(symbol)
                if not security_id:
                    print(f"Could not find security ID for {symbol}, skipping order.")
                    continue

                # Check if we can open a new position
                if action == 'BUY' and len(open_positions) < config['risk_management']['max_open_positions']:
                    trade_value = account_balance['data']['totalValue'] * config['risk_management']['capital_allocation_per_trade']
                    live_data = broker.get_live_market_data(security_id=str(security_id))

                    if live_data and 'data' in live_data and live_data['data']['last_trade_price'] > 0:
                        last_price = live_data['data']['last_trade_price']
                        quantity = int(trade_value / last_price)
                        if quantity > 0:
                            print(f"Placing BUY order for {symbol}, Qty: {quantity}")
                            broker.place_order(
                                security_id=str(security_id),
                                exchange_segment='NSE_EQ',
                                transaction_type='BUY',
                                quantity=quantity,
                                order_type='MARKET',
                                product_type='MTF' # Using MTF as per memory
                            )

                # Check if we need to close a position
                if action == 'SELL':
                    for position in open_positions:
                        if position['tradingSymbol'] == symbol:
                            print(f"Placing SELL order for {symbol}, Qty: {position['netQty']}")
                            broker.place_order(
                                security_id=position['securityId'],
                                exchange_segment=position['exchangeSegment'],
                                transaction_type='SELL',
                                quantity=position['netQty'],
                                order_type='MARKET',
                                product_type='MTF' # Using MTF as per memory
                            )
                            break

        # 3. Update terminal display
        nifty_50_security_id = '13' # NIFTY 50 Index
        today = datetime.now()

        # Fetch data for 1D indicators
        from_date_1d = (today - timedelta(days=365)).strftime('%Y-%m-%d')
        to_date_1d = today.strftime('%Y-%m-%d')
        df_1d = broker.get_daily_data(
            security_id=nifty_50_security_id,
            exchange_segment='NSE_INDEX',
            instrument_type='INDEX',
            from_date=from_date_1d,
            to_date=to_date_1d
        )

        # Fetch data for 1H indicators (last 10 days for relevance)
        from_date_1h = (today - timedelta(days=10)).strftime('%Y-%m-%d')
        to_date_1h = today.strftime('%Y-%m-%d')
        df_1h = broker.intraday_data(
            security_id=nifty_50_security_id,
            exchange_segment='NSE_INDEX',
            instrument_type='INDEX',
            interval='60',
            from_date=from_date_1h,
            to_date=to_date_1h
        )

        if df_1h is not None and df_1d is not None and isinstance(df_1h, pd.DataFrame) and isinstance(df_1d, pd.DataFrame):
            # Calculate indicators for 1H
            df_1h['start_Time'] = pd.to_datetime(df_1h['start_Time'])
            df_1h = df_1h.set_index('start_Time')
            df_1h = calculate_rsi(df_1h, config['strategy']['rsi_period'])
            df_1h = calculate_adx(df_1h, config['strategy']['adx_period'])
            df_1h = calculate_vwap(df_1h)

            # Calculate indicators for 1D
            df_1d['start_Time'] = pd.to_datetime(df_1d['start_Time'])
            df_1d = df_1d.set_index('start_Time')
            df_1d = calculate_rsi(df_1d, config['strategy']['rsi_period'])
            df_1d = calculate_adx(df_1d, config['strategy']['adx_period'])
            df_1d = calculate_vwap(df_1d)

            indicators = {
                'RSI': {'1H': df_1h[f'RSI_{config["strategy"]["rsi_period"]}'].iloc[-1], '1D': df_1d[f'RSI_{config["strategy"]["rsi_period"]}'].iloc[-1]},
                'ADX': {'1H': df_1h[f'ADX_{config["strategy"]["adx_period"]}'].iloc[-1], '1D': df_1d[f'ADX_{config["strategy"]["adx_period"]}'].iloc[-1]},
                'VWAP': {'1H': df_1h['VWAP'].iloc[-1], '1D': df_1d['VWAP'].iloc[-1]}
            }
            display_indicators(indicators)

        # Calculate P/L for open positions and display
        if open_positions:
            for position in open_positions:
                live_data = broker.get_live_market_data(security_id=position['securityId'], exchange_segment=position['exchangeSegment'])
                if live_data and 'data' in live_data and live_data['data']['last_trade_price'] > 0:
                    pnl_percentage = ((live_data['data']['last_trade_price'] - position['buyAvg']) / position['buyAvg']) * 100
                    position['pnl_percentage'] = pnl_percentage
                else:
                    position['pnl_percentage'] = 0.0
            display_positions(open_positions)

        # Display available funds
        if account_balance and account_balance.get('data') and 'availableBalance' in account_balance['data']:
            display_funds({'availableBalance': account_balance['data']['availableBalance']})

        print(f"--- Loop finished, waiting for 30 minutes ---")
        time.sleep(1800)

if __name__ == '__main__':
    main()
