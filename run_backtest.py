import pandas as pd
from core.backtester import Backtester
from strategies.basic import BasicStrategy
from brokers.dhan import DhanBroker
import yaml
import time

def load_config():
    """
    Loads the configuration from configs/config.yaml.
    """
    with open('configs/config.yaml', 'r') as f:
        return yaml.safe_load(f)

def main():
    """
    The main entry point for the backtester.
    """
    config = load_config()
    broker = DhanBroker() # Not used for backtesting, but required by the strategy
    strategy = BasicStrategy(broker, config)

    # Load historical data from Dhan API
    from datetime import datetime, timedelta
    today = datetime.now()
    days_of_data = config['backtest']['days_of_data']
    interval = config['backtest']['interval']
    overall_from_date = today - timedelta(days=days_of_data)

    data = {}
    for symbol in config['instruments']['nifty50_symbols']:
        security_id = broker.security_id_map.get(symbol)
        if security_id:
            all_chunks = []
            current_from_date = overall_from_date

            while current_from_date < today:
                current_to_date = current_from_date + timedelta(days=90)
                if current_to_date > today:
                    current_to_date = today

                from_date_str = current_from_date.strftime('%Y-%m-%d')
                to_date_str = current_to_date.strftime('%Y-%m-%d')

                df_chunk = broker.intraday_data(
                    security_id=str(security_id),
                    exchange_segment='NSE_EQ',
                    instrument_type='EQUITY',
                    interval=interval,
                    from_date=from_date_str,
                    to_date=to_date_str
                )

                if df_chunk is not None and isinstance(df_chunk, pd.DataFrame) and not df_chunk.empty:
                    all_chunks.append(df_chunk)

                current_from_date += timedelta(days=90)

                # Add a delay to respect API rate limits
                time.sleep(0.25)

            if all_chunks:
                df = pd.concat(all_chunks)
                df['date'] = pd.to_datetime(df['start_Time']).dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
                df = df.set_index('date')
                # Remove duplicate timestamps
                df = df[~df.index.duplicated(keep='first')]
                data[symbol] = df

    if not data:
        print("No data found for backtesting. Exiting.")
        return

    backtester = Backtester(strategy, data)
    backtester.run()
    backtester.generate_report()

if __name__ == '__main__':
    main()
