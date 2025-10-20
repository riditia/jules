import pandas as pd
from core.indicators import calculate_ema, calculate_adx

class BasicStrategy:
    """
    A basic trading strategy based on EMA crossover and ADX.
    """
    def __init__(self, broker, config):
        """
        Initializes the BasicStrategy with a broker and a configuration.
        """
        self.broker = broker
        self.config = config

    def run(self):
        """
        Runs the trading strategy for all NIFTY 50 symbols.
        """
        signals = []
        from datetime import datetime, timedelta

        today = datetime.now()
        from_date = (today - timedelta(days=365)).strftime('%Y-%m-%d')
        to_date = today.strftime('%Y-%m-%d')

        for symbol in self.config['instruments']['nifty50_symbols']:
            security_id = self.broker.security_id_map.get(symbol)
            if security_id is None:
                print(f"Could not find security ID for symbol: {symbol}")
                continue

            # 1. Fetch historical data (1H timeframe)
            df = self.broker.get_intraday_data(
                security_id=str(security_id),
                exchange_segment='NSE_EQ',
                instrument_type='EQUITY',
                interval='60'
            )

            if df is not None and not df.empty and isinstance(df, pd.DataFrame):
                # 2. Calculate indicators
                df = calculate_ema(df, self.config['strategy']['ema_short_period'])
                df = calculate_ema(df, self.config['strategy']['ema_long_period'])
                df = calculate_adx(df, self.config['strategy']['adx_period'])

                # 3. Check for signals
                signal = self._check_signal(df)
                if signal != 'HOLD':
                    signals.append({'symbol': symbol, 'signal': signal, 'security_id': security_id})
        return signals

    def _check_signal(self, df):
        """
        Checks for a trading signal in the given DataFrame.
        """
        ema_short_period = self.config['strategy']['ema_short_period']
        ema_long_period = self.config['strategy']['ema_long_period']
        adx_period = self.config['strategy']['adx_period']
        adx_threshold = self.config['strategy']['adx_threshold']
        adx_fall_period = self.config['strategy']['adx_fall_period']

        # EMA Crossover
        ema_short = df[f'EMA_{ema_short_period}']
        ema_long = df[f'EMA_{ema_long_period}']

        # Buy Signal: EMA short crosses above EMA long
        if ema_short.iloc[-2] < ema_long.iloc[-2] and ema_short.iloc[-1] > ema_long.iloc[-1]:
            # ADX Condition
            adx = df[f'ADX_{adx_period}']
            if adx.iloc[-1] >= adx_threshold or not (adx.iloc[-1] < adx.iloc[-2] and adx.iloc[-2] < adx.iloc[-3] and adx.iloc[-3] < adx.iloc[-4]):
                return 'BUY'

        # Sell Signal: EMA short crosses below EMA long
        if ema_short.iloc[-2] > ema_long.iloc[-2] and ema_short.iloc[-1] < ema_long.iloc[-1]:
            return 'SELL'

        return 'HOLD'
