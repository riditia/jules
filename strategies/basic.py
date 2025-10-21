import pandas as pd
import logging
from datetime import datetime, timedelta
from core.indicators import calculate_ema, calculate_adx

class BasicStrategy:
    """
    Enhanced basic trading strategy based on EMA crossover and ADX with improved
    error handling and signal generation.
    """
    
    def __init__(self, broker, config):
        """
        Initializes the BasicStrategy with a broker and a configuration.
        """
        self.broker = broker
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Validate configuration
        self._validate_config()
        
        self.logger.info("BasicStrategy initialized successfully")
    
    def _validate_config(self):
        """
        Validates the strategy configuration.
        """
        required_keys = [
            'strategy.ema_short_period',
            'strategy.ema_long_period', 
            'strategy.adx_period',
            'strategy.adx_threshold'
        ]
        
        for key in required_keys:
            keys = key.split('.')
            config_section = self.config
            
            for k in keys:
                if k not in config_section:
                    raise ValueError(f"Missing required configuration: {key}")
                config_section = config_section[k]
                
        # Validate EMA periods
        if self.config['strategy']['ema_short_period'] >= self.config['strategy']['ema_long_period']:
            raise ValueError("Short EMA period must be less than long EMA period")
            
        self.logger.info("Strategy configuration validated")

    def prepare_data(self, data):
        """
        Calculates all the necessary indicators for the historical data.
        """
        try:
            for symbol in data:
                df = data[symbol]
                
                if df is None or df.empty:
                    self.logger.warning(f"No data available for {symbol}")
                    continue
                    
                # Calculate indicators
                df = calculate_ema(df, self.config['strategy']['ema_short_period'])
                df = calculate_ema(df, self.config['strategy']['ema_long_period'])
                df = calculate_adx(df, self.config['strategy']['adx_period'])
                
                data[symbol] = df
                
            return data
            
        except Exception as e:
            self.logger.error(f"Error preparing data: {e}")
            return data

    def _check_signal(self, df):
        """
        Checks for a trading signal in the given DataFrame with enhanced validation.
        """
        try:
            if df is None or len(df) < max(self.config['strategy']['ema_long_period'], 
                                          self.config['strategy']['adx_period']) + 5:
                self.logger.warning("Insufficient data for signal generation")
                return 'HOLD'
            
            ema_short_period = self.config['strategy']['ema_short_period']
            ema_long_period = self.config['strategy']['ema_long_period']
            adx_period = self.config['strategy']['adx_period']
            adx_threshold = self.config['strategy']['adx_threshold']

            # Get indicator columns
            ema_short_col = f'EMA_{ema_short_period}'
            ema_long_col = f'EMA_{ema_long_period}'
            adx_col = f'ADX_{adx_period}'
            
            # Validate indicator columns exist
            required_cols = [ema_short_col, ema_long_col, adx_col]
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                self.logger.error(f"Missing indicator columns: {missing_cols}")
                return 'HOLD'

            # Get EMA values
            ema_short = df[ema_short_col]
            ema_long = df[ema_long_col]
            adx = df[adx_col]
            
            # Check for valid values
            if (pd.isna(ema_short.iloc[-2:]).any() or 
                pd.isna(ema_long.iloc[-2:]).any() or 
                pd.isna(adx.iloc[-4:]).any()):
                self.logger.warning("NaN values found in indicators")
                return 'HOLD'

            # Buy Signal: EMA short crosses above EMA long
            if (ema_short.iloc[-2] <= ema_long.iloc[-2] and 
                ema_short.iloc[-1] > ema_long.iloc[-1]):
                
                # ADX Condition for trend strength
                current_adx = adx.iloc[-1]
                
                if current_adx >= adx_threshold:
                    self.logger.info(f"BUY signal generated - ADX: {current_adx:.2f}")
                    return 'BUY'
                else:
                    # Check for ADX not falling for consecutive periods
                    adx_falling = (adx.iloc[-1] < adx.iloc[-2] and 
                                  adx.iloc[-2] < adx.iloc[-3] and 
                                  adx.iloc[-3] < adx.iloc[-4])
                    
                    if not adx_falling:
                        self.logger.info(f"BUY signal generated - ADX not falling: {current_adx:.2f}")
                        return 'BUY'

            # Sell Signal: EMA short crosses below EMA long
            elif (ema_short.iloc[-2] >= ema_long.iloc[-2] and 
                  ema_short.iloc[-1] < ema_long.iloc[-1]):
                self.logger.info("SELL signal generated")
                return 'SELL'

            return 'HOLD'
            
        except Exception as e:
            self.logger.error(f"Error checking signal: {e}")
            return 'HOLD'
    
    def run(self):
        """
        Runs the strategy and returns trading signals.
        """
        signals = []
        
        try:
            # Get symbols from config or use default
            symbols = self.config.get('symbols', ['NIFTY 50'])
            
            for symbol in symbols:
                try:
                    # Get security ID from broker's map
                    security_id = self.broker.get_security_id(symbol)
                    if not security_id:
                        self.logger.warning(f"Security ID not found for {symbol}")
                        continue
                        
                    # Determine exchange segment and instrument type based on symbol
                    if 'NIFTY' in symbol.upper() or 'SENSEX' in symbol.upper():
                        exchange_segment = 'NSE_INDEX'
                        instrument_type = 'INDEX'
                    else:
                        exchange_segment = 'NSE_EQ'
                        instrument_type = 'EQUITY'
                    
                    # Fetch recent data for signal generation
                    df = self.broker.intraday_data(
                        security_id=security_id,
                        exchange_segment=exchange_segment,
                        instrument_type=instrument_type,
                        interval='60'
                    )
                    
                    if df is not None and len(df) > 50:  # Ensure enough data
                        # Prepare data with indicators
                        data_dict = {symbol: df}
                        prepared_data = self.prepare_data(data_dict)
                        df_prepared = prepared_data[symbol]
                        
                        # Generate signal
                        signal = self._check_signal(df_prepared)
                        
                        if signal != 'HOLD':
                            signal_data = {
                                'symbol': symbol,
                                'signal': signal,
                                'security_id': security_id,
                                'exchange_segment': exchange_segment,
                                'instrument_type': instrument_type,
                                'timestamp': datetime.now(),
                                'confidence': self._calculate_confidence(df_prepared)
                            }
                            
                            signals.append(signal_data)
                            self.logger.info(f"Signal generated for {symbol}: {signal}")
                    else:
                        self.logger.warning(f"Insufficient data for {symbol}: {len(df) if df is not None else 0} rows")
                        
                except Exception as e:
                    self.logger.error(f"Error generating signal for {symbol}: {e}")
                    continue
            
            self.logger.info(f"Generated {len(signals)} trading signals")
            return signals
            
        except Exception as e:
            self.logger.error(f"Error running strategy: {e}")
            return []
    
    def _calculate_confidence(self, df):
        """
        Calculate confidence score for the signal based on various factors.
        """
        try:
            confidence = 0.5  # Base confidence
            
            # ADX strength factor
            adx_col = f"ADX_{self.config['strategy']['adx_period']}"
            if adx_col in df.columns:
                adx_value = df[adx_col].iloc[-1]
                if adx_value > self.config['strategy']['adx_threshold'] * 1.5:
                    confidence += 0.2
                elif adx_value > self.config['strategy']['adx_threshold']:
                    confidence += 0.1
            
            # Volume factor (if available)
            if 'volume' in df.columns:
                recent_volume = df['volume'].iloc[-5:].mean()
                historical_volume = df['volume'].iloc[-20:-5].mean()
                
                if recent_volume > historical_volume * 1.2:
                    confidence += 0.1
            
            return min(confidence, 1.0)
            
        except Exception as e:
            self.logger.warning(f"Error calculating confidence: {e}")
            return 0.5
    
    def get_risk_metrics(self, symbol):
        """
        Get risk metrics for a given symbol.
        """
        try:
            security_id = self.broker.get_security_id(symbol)
            if not security_id:
                return None
                
            # Fetch recent data
            df = self.broker.intraday_data(
                security_id=security_id,
                exchange_segment='NSE_EQ',
                instrument_type='EQUITY',
                interval='60'
            )
            
            if df is None or len(df) < 20:
                return None
            
            # Calculate volatility (standard deviation of returns)
            df['returns'] = df['close'].pct_change()
            volatility = df['returns'].std() * (252 ** 0.5)  # Annualized
            
            # Calculate maximum drawdown
            df['cumulative'] = (1 + df['returns']).cumprod()
            df['running_max'] = df['cumulative'].cummax()
            df['drawdown'] = (df['cumulative'] - df['running_max']) / df['running_max']
            max_drawdown = df['drawdown'].min()
            
            return {
                'volatility': volatility,
                'max_drawdown': abs(max_drawdown),
                'current_price': df['close'].iloc[-1],
                'avg_volume': df['volume'].mean() if 'volume' in df.columns else None
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating risk metrics for {symbol}: {e}")
            return None