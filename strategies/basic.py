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

    def prepare_data(self, data):
        """
        Calculates all the necessary indicators for the historical data.
        """
        for symbol in data:
            df = data[symbol]
            df = calculate_ema(df, self.config['strategy']['ema_short_period'])
            df = calculate_ema(df, self.config['strategy']['ema_long_period'])
            df = calculate_adx(df, self.config['strategy']['adx_period'])
            data[symbol] = df
        return data

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
