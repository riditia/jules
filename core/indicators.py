import pandas as pd
from ta.trend import ema_indicator, adx
from ta.momentum import rsi
from ta.volume import volume_weighted_average_price

def calculate_ema(df, length):
    """
    Calculates the Exponential Moving Average (EMA).
    """
    df[f'EMA_{length}'] = ema_indicator(df['close'], window=length)
    return df

def calculate_adx(df, length):
    """
    Calculates the Average Directional Index (ADX).
    """
    # The 'ta' library function for ADX returns a series with just the ADX line.
    # We need to explicitly name it to avoid issues when joining.
    adx_series = adx(df['high'], df['low'], df['close'], window=length)
    if adx_series is not None:
        df[f'ADX_{length}'] = adx_series
    return df

def calculate_rsi(df, length):
    """
    Calculates the Relative Strength Index (RSI).
    """
    df[f'RSI_{length}'] = rsi(df['close'], window=length)
    return df

def calculate_vwap(df):
    """
    Calculates the Volume Weighted Average Price (VWAP).
    """
    df['VWAP'] = volume_weighted_average_price(df['high'], df['low'], df['close'], df['volume'])
    return df
