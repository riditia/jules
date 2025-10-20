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

    # Fetch daily data once at startup
    nifty_50_security_id = '13'
    from datetime import datetime, timedelta
    today = datetime.now()
    from_date_1d = (today - timedelta(days=365)).strftime('%Y-%m-%d')
    to_date_1d = today.strftime('%Y-%m-%d')
    df_1d = broker.get_historical_data(
        security_id=nifty_50_security_id,
        exchange_segment='NSE_INDEX',
        instrument_type='INDEX',
        from_date=from_date_1d,
        to_date=to_date_1d
    )

    while True:
        # 1. Run the strategy to get signals
        signals = strategy.run()

        # 2. Process signals and place orders
        open_positions_data = broker.get_open_positions()
        open_positions = open_positions_data['data'] if open_positions_data and 'data' in open_positions_data else []
        account_balance = broker.get_account_balance()

        if account_balance and account_balance.get('data'):
            for signal in signals:
                symbol = signal['symbol']
                action = signal['signal']
                security_id = signal['security_id']

                # Check if we can open a new position
                if action == 'BUY' and len(open_positions) < config['risk_management']['max_open_positions']:
                    # Check capital allocation
                    trade_value = account_balance['data']['totalValue'] * config['risk_management']['capital_allocation_per_trade']

                    live_data = broker.get_live_market_data(security_id=security_id)
                    if live_data and live_data['data']['last_trade_price'] > 0:
                        quantity = int(trade_value / live_data['data']['last_trade_price'])
                        if quantity > 0:
                            broker.place_order(
                                security_id=str(security_id),
                                exchange_segment='NSE_EQ',
                                transaction_type='BUY',
                                quantity=quantity,
                                order_type='MARKET',
                                product_type='MTF'
                            )

                # Check if we need to close a position
                if action == 'SELL':
                    for position in open_positions:
                        if position['tradingSymbol'] == symbol:
                            broker.place_order(
                                security_id=position['securityId'],
                                exchange_segment=position['exchangeSegment'],
                                transaction_type='SELL',
                                quantity=position['netQty'],
                                order_type='MARKET',
                                product_type='MTF'
                            )
                            break

        # 3. Update terminal display
        df_1h = broker.intraday_data(
            security_id=nifty_50_security_id,
            exchange_segment='NSE_INDEX',
            instrument_type='INDEX',
            interval='60'
        )

        if df_1h is not None and df_1d is not None and isinstance(df_1h, pd.DataFrame) and isinstance(df_1d, pd.DataFrame):
            df_1h = calculate_rsi(df_1h, config['strategy']['rsi_period'])
            df_1h = calculate_adx(df_1h, config['strategy']['adx_period'])
            df_1h = calculate_vwap(df_1h)

            df_1d_calc = calculate_rsi(df_1d.copy(), config['strategy']['rsi_period'])
            df_1d_calc = calculate_adx(df_1d_calc, config['strategy']['adx_period'])
            df_1d_calc = calculate_vwap(df_1d_calc)

            indicators = {
                'RSI': {'1H': df_1h[f'RSI_{config["strategy"]["rsi_period"]}'].iloc[-1], '1D': df_1d_calc[f'RSI_{config["strategy"]["rsi_period"]}'].iloc[-1]},
                'ADX': {'1H': df_1h[f'ADX_{config["strategy"]["adx_period"]}'].iloc[-1], '1D': df_1d_calc[f'ADX_{config["strategy"]["adx_period"]}'].iloc[-1]},
                'VWAP': {'1H': df_1h['VWAP'].iloc[-1], '1D': df_1d_calc['VWAP'].iloc[-1]}
            }
            display_indicators(indicators)

        # Calculate P/L for open positions
        if open_positions:
            for position in open_positions:
                live_data = broker.get_live_market_data(security_id=position['securityId'], exchange_segment=position['exchangeSegment'])
                if live_data and live_data['data']['last_trade_price'] > 0:
                    pnl_percentage = ((live_data['data']['last_trade_price'] - position['buyAvg']) / position['buyAvg']) * 100
                    position['pnl_percentage'] = pnl_percentage
                else:
                    position['pnl_percentage'] = 0.0
            display_positions(open_positions)

        if account_balance and account_balance.get('data'):
            display_funds({'availableBalance': account_balance['data']['availableBalance']})

        time.sleep(60)  # Wait for 1 minute before the next iteration

if __name__ == '__main__':
    main()
