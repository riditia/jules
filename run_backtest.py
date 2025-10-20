import pandas as pd
from core.backtester import Backtester
from strategies.basic import BasicStrategy
from brokers.dhan import DhanBroker
import yaml

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
    from_date = (today - timedelta(days=365)).strftime('%Y-%m-%d')
    to_date = today.strftime('%Y-%m-%d')

    data = {}
    for symbol in config['instruments']['nifty50_symbols']:
        security_id = broker.security_id_map.get(symbol)
        if security_id:
            df = broker.get_intraday_data(
                security_id=str(security_id),
                exchange_segment='NSE_EQ',
                instrument_type='EQUITY',
                interval='60'
            )
            if df is not None and not df.empty and isinstance(df, pd.DataFrame):
                df['date'] = pd.to_datetime(df['start_Time'])
                df = df.set_index('date')
                data[symbol] = df

    if not data:
        print("No data found for backtesting. Exiting.")
        return

    backtester = Backtester(strategy, data)
    backtester.run()
    backtester.generate_report()

if __name__ == '__main__':
    main()
