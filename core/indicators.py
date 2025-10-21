import pandas as pd
import ta

def calculate_ema(df, length):
    """
    Calculates the Exponential Moving Average (EMA).
    """
    df[f'EMA_{length}'] = ta.trend.ema_indicator(df['close'], window=length)
    return df

def calculate_adx(df, length):
    """
    Calculates the Average Directional Index (ADX).
    """
    adx = ta.trend.adx(df['high'], df['low'], df['close'], window=length)
    if adx is not None:
        df = df.join(adx)
    return df

def calculate_rsi(df, length):
    """
    Calculates the Relative Strength Index (RSI).
    """
    df[f'RSI_{length}'] = ta.rsi(df['close'], length=length)
    return df

def calculate_vwap(df):
    """
    Calculates the Volume Weighted Average Price (VWAP).
    """
    df['VWAP'] = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
    return df
