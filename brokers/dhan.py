import os
import pandas as pd
import traceback
import time
import logging
from collections import defaultdict, deque
from threading import Lock
from functools import wraps
from dhanhq import dhanhq
from dotenv import load_dotenv

load_dotenv()

class RateLimiter:
    """Rate limiter to comply with DhanHQ API limits."""
    
    def __init__(self):
        self.call_history = defaultdict(deque)
        self.lock = Lock()
        
    def wait_if_needed(self, api_type):
        """Wait if rate limits would be exceeded for the given API type."""
        limits = {
            'order': {'per_second': 25, 'per_minute': 250, 'per_hour': 1000, 'per_day': 7000},
            'data': {'per_second': 5, 'per_day': 100000},
            'quote': {'per_second': 1},
            'non_trading': {'per_second': 20}
        }
        
        with self.lock:
            now = time.time()
            history = self.call_history[api_type]
            
            # Clean old entries and check limits
            for period, limit in limits[api_type].items():
                seconds = {'per_second': 1, 'per_minute': 60, 'per_hour': 3600, 'per_day': 86400}[period]
                cutoff = now - seconds
                
                while history and history[0] < cutoff:
                    history.popleft()
                    
                if len(history) >= limit:
                    sleep_time = seconds - (now - history[0])
                    if sleep_time > 0:
                        logging.info(f"Rate limit reached for {api_type}. Sleeping for {sleep_time:.2f} seconds.")
                        time.sleep(sleep_time)
                        
            history.append(now)

def retry_on_failure(max_retries=3, delay=1, backoff=2):
    """Decorator for retrying failed API calls with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logging.error(f"Final attempt failed for {func.__name__}: {e}")
                        raise e
                    sleep_time = delay * (backoff ** attempt)
                    logging.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
            return None
        return wrapper
    return decorator

class CircuitBreaker:
    """Circuit breaker pattern to handle API failures gracefully."""
    
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
                logging.info("Circuit breaker moving to HALF_OPEN state")
            else:
                raise Exception("Circuit breaker is OPEN - API calls blocked")
                
        try:
            result = func(*args, **kwargs)
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                self.failure_count = 0
                logging.info("Circuit breaker reset to CLOSED state")
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
                logging.error(f"Circuit breaker OPEN - {self.failure_count} failures reached")
            raise e

def validate_dataframe(df, required_columns=None):
    """Validates DataFrame structure and data quality."""
    if df is None or not isinstance(df, pd.DataFrame):
        raise ValueError("Invalid DataFrame: must be a pandas DataFrame")
        
    if df.empty:
        raise ValueError("DataFrame is empty")
        
    if required_columns:
        missing_cols = set(required_columns) - set(df.columns)
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
            
    return True

class DhanBroker:
    """
    Enhanced broker class for interacting with the Dhan API with rate limiting,
    error handling, and robustness improvements.
    """
    
    def __init__(self):
        """
        Initializes the DhanBroker with API credentials from environment variables.
        """
        self.logger = logging.getLogger(__name__)
        
        client_id = os.getenv("DHAN_CLIENT_ID")
        access_token = os.getenv("DHAN_ACCESS_TOKEN")

        if not client_id or not access_token:
            raise ValueError("DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN must be set as environment variables.")

        self.dhan = dhanhq(client_id, access_token)
        self.rate_limiter = RateLimiter()
        self.circuit_breaker = CircuitBreaker()
        self.security_id_map = self._load_security_id_map()
        
        self.logger.info("DhanBroker initialized successfully")

    def _load_security_id_map(self):
        """
        Loads the security ID map from the Dhan API with error handling.
        """
        try:
            url = "https://images.dhan.co/api-data/api-scrip-master.csv"
            df = pd.read_csv(url, low_memory=False)
            
            validate_dataframe(df, ['SEM_TRADING_SYMBOL', 'SEM_SMST_SECURITY_ID'])
            
            security_map = df.set_index('SEM_TRADING_SYMBOL')['SEM_SMST_SECURITY_ID'].to_dict()
            self.logger.info(f"Loaded {len(security_map)} securities from master file")
            return security_map
            
        except Exception as e:
            self.logger.error(f"Error loading security ID map: {e}")
            return {}

    def validate_trade_size(self, quantity, price, account_balance, max_allocation_pct=0.1):
        """
        Validates trade size against risk parameters.
        """
        if quantity <= 0 or price <= 0:
            raise ValueError("Quantity and price must be positive")
            
        trade_value = quantity * price
        max_trade_value = account_balance * max_allocation_pct
        
        if trade_value > max_trade_value:
            raise ValueError(f"Trade size {trade_value:.2f} exceeds maximum allowed {max_trade_value:.2f}")
            
        return True

    @retry_on_failure(max_retries=3)
    def get_live_market_data(self, security_id, exchange_segment='NSE_EQ', instrument_type='EQUITY'):
        """
        Fetches live market data for a given security ID with rate limiting and error handling.
        """
        self.rate_limiter.wait_if_needed('quote')
        
        def _fetch_quote():
            response = self.dhan.get_quotes(security_id=str(security_id), exchange_segment=exchange_segment)
            
            if not response or response.get('status') != 'success':
                raise ValueError(f"API returned unsuccessful response: {response}")
                
            return response
            
        try:
            return self.circuit_breaker.call(_fetch_quote)
        except Exception as e:
            self.logger.error(f"Error fetching live market data for {security_id}: {e}")
            return None

    @retry_on_failure(max_retries=3)
    def intraday_data(self, security_id, exchange_segment, instrument_type, interval, from_date=None, to_date=None):
        """
        Fetches intraday historical data for a given symbol with enhanced error handling.
        """
        self.rate_limiter.wait_if_needed('data')
        
        # Set default dates if not provided
        if not from_date or not to_date:
            from datetime import datetime, timedelta
            today = datetime.now()
            from_date = (today - timedelta(days=5)).strftime('%Y-%m-%d')
            to_date = today.strftime('%Y-%m-%d')
        
        def _fetch_intraday():
            response = self.dhan.intraday_minute_data(
                security_id=str(security_id),
                exchange_segment=exchange_segment,
                instrument_type=instrument_type,
                interval=interval,
                from_date=from_date,
                to_date=to_date
            )

            if not response or response.get('status') != 'success' or 'data' not in response:
                raise ValueError(f"Invalid response for security ID {security_id}: {response}")
                
            df = pd.DataFrame(response['data'])
            
            if df.empty:
                raise ValueError(f"No data returned for security ID {security_id}")
                
            # Convert epoch timestamp to datetime and set as index
            df['start_Time'] = pd.to_datetime(df['timestamp'], unit='s')
            
            validate_dataframe(df, ['open', 'high', 'low', 'close', 'volume'])
            
            return df

        try:
            return self.circuit_breaker.call(_fetch_intraday)
        except Exception as e:
            self.logger.error(f"Error fetching intraday data for {security_id}: {e}")
            return None

    @retry_on_failure(max_retries=3)
    def get_historical_data(self, security_id, exchange_segment, instrument_type, from_date, to_date):
        """
        Fetches historical data for a given symbol with rate limiting.
        """
        self.rate_limiter.wait_if_needed('data')
        
        def _fetch_historical():
            response = self.dhan.get_historical_data(
                security_id=security_id,
                exchange_segment=exchange_segment,
                instrument_type=instrument_type,
                from_date=from_date,
                to_date=to_date
            )
            
            if not response or response.get('status') != 'success':
                raise ValueError(f"Invalid historical data response: {response}")
                
            return response
            
        try:
            return self.circuit_breaker.call(_fetch_historical)
        except Exception as e:
            self.logger.error(f"Error fetching historical data: {e}")
            return None

    @retry_on_failure(max_retries=3)
    def get_account_balance(self):
        """
        Retrieves the current account balance with rate limiting.
        """
        self.rate_limiter.wait_if_needed('non_trading')
        
        def _fetch_balance():
            response = self.dhan.get_fund_limits()
            
            if not response or response.get('status') != 'success':
                raise ValueError(f"Invalid fund limits response: {response}")
                
            return response
            
        try:
            return self.circuit_breaker.call(_fetch_balance)
        except Exception as e:
            self.logger.error(f"Error fetching account balance: {e}")
            return None

    @retry_on_failure(max_retries=3)
    def get_open_positions(self):
        """
        Retrieves a list of open positions with rate limiting.
        """
        self.rate_limiter.wait_if_needed('non_trading')
        
        def _fetch_positions():
            response = self.dhan.get_positions()
            
            if not response or response.get('status') != 'success':
                raise ValueError(f"Invalid positions response: {response}")
                
            return response
            
        try:
            return self.circuit_breaker.call(_fetch_positions)
        except Exception as e:
            self.logger.error(f"Error fetching open positions: {e}")
            return None

    @retry_on_failure(max_retries=2)  # Fewer retries for order placement
    def place_order(self, security_id, exchange_segment, transaction_type, quantity, order_type, product_type, price=0, **kwargs):
        """
        Places a new order with comprehensive validation and rate limiting.
        """
        self.rate_limiter.wait_if_needed('order')
        
        # Validate required parameters
        required_params = {
            'security_id': security_id,
            'exchange_segment': exchange_segment,
            'transaction_type': transaction_type,
            'quantity': quantity,
            'order_type': order_type,
            'product_type': product_type
        }
        
        missing_params = [k for k, v in required_params.items() if not v]
        if missing_params:
            raise ValueError(f"Missing required order parameters: {missing_params}")
            
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
            
        if order_type == 'LIMIT' and price <= 0:
            raise ValueError("Limit orders require a positive price")
        
        def _place_order():
            order_data = {
                'security_id': str(security_id),
                'exchange_segment': exchange_segment,
                'transaction_type': transaction_type,
                'quantity': quantity,
                'order_type': order_type,
                'product_type': product_type,
                'price': price
            }
            
            # Add any additional parameters
            order_data.update(kwargs)
            
            response = self.dhan.place_order(**order_data)
            
            if not response or response.get('status') != 'success':
                raise ValueError(f"Order placement failed: {response}")
                
            self.logger.info(f"Order placed successfully: {order_data}")
            return response
            
        try:
            return self.circuit_breaker.call(_place_order)
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            return None

    def get_security_id(self, symbol):
        """
        Helper method to get security ID for a given symbol.
        """
        security_id = self.security_id_map.get(symbol)
        if not security_id:
            self.logger.warning(f"Security ID not found for symbol: {symbol}")
        return security_id

    def health_check(self):
        """
        Performs a basic health check of the broker connection.
        """
        try:
            balance = self.get_account_balance()
            return balance is not None and balance.get('status') == 'success'
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False