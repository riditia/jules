import yaml
import time
import pandas as pd
import logging
import os
from datetime import datetime, timedelta
from brokers.dhan import DhanBroker
from strategies.basic import BasicStrategy
from core.ui import display_indicators, display_positions, display_funds
from core.indicators import calculate_rsi, calculate_adx, calculate_vwap

def setup_logging():
    """
    Sets up logging configuration with file and console handlers.
    """
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Configure logging
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    log_filename = f'logs/trading_bot_{datetime.now().strftime("%Y%m%d")}.log'
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)

def load_config():
    """
    Loads and validates configuration from configs/config.yaml.
    """
    try:
        with open('configs/config.yaml', 'r') as f:
            config = yaml.safe_load(f)
            
        # Validate required config sections
        required_sections = ['strategy', 'risk_management']
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required config section: {section}")
        
        # Validate required strategy parameters
        required_strategy_params = [
            'ema_short_period', 'ema_long_period', 'adx_period', 
            'adx_threshold', 'rsi_period'
        ]
        
        for param in required_strategy_params:
            if param not in config['strategy']:
                raise ValueError(f"Missing required strategy parameter: {param}")
        
        # Validate required risk management parameters
        required_risk_params = [
            'max_open_positions', 'capital_allocation_per_trade'
        ]
        
        for param in required_risk_params:
            if param not in config['risk_management']:
                raise ValueError(f"Missing required risk management parameter: {param}")
                
        return config
        
    except FileNotFoundError:
        raise FileNotFoundError("Configuration file not found: configs/config.yaml")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML configuration: {e}")

def validate_trading_environment(broker, config, logger):
    """
    Validates that the trading environment is ready.
    """
    try:
        # Check broker health
        if not broker.health_check():
            raise RuntimeError("Broker health check failed")
            
        # Check account balance
        balance = broker.get_account_balance()
        if not balance or not balance.get('data'):
            raise RuntimeError("Unable to fetch account balance")
            
        available_balance = balance['data'].get('availableBalance', 0)
        if available_balance <= 0:
            raise RuntimeError("Insufficient account balance for trading")
            
        logger.info(f"Trading environment validated - Available balance: {available_balance}")
        return True
        
    except Exception as e:
        logger.error(f"Trading environment validation failed: {e}")
        return False

def process_trading_signals(signals, broker, config, logger):
    """
    Process trading signals and execute orders with enhanced validation.
    """
    try:
        # Get current positions and account info
        open_positions_data = broker.get_open_positions()
        open_positions = open_positions_data['data'] if open_positions_data and 'data' in open_positions_data else []
        
        account_balance = broker.get_account_balance()
        if not account_balance or not account_balance.get('data'):
            logger.warning("Unable to fetch account balance - skipping signal processing")
            return
            
        available_balance = account_balance['data'].get('availableBalance', 0)
        total_value = account_balance['data'].get('totalValue', available_balance)
        
        for signal in signals:
            try:
                symbol = signal['symbol']
                action = signal['signal']
                security_id = signal['security_id']
                exchange_segment = signal.get('exchange_segment', 'NSE_EQ')
                confidence = signal.get('confidence', 0.5)
                
                logger.info(f"Processing signal: {symbol} - {action} (confidence: {confidence:.2f})")
                
                # Buy signal processing
                if action == 'BUY':
                    # Check position limits
                    if len(open_positions) >= config['risk_management']['max_open_positions']:
                        logger.warning(f"Maximum positions limit reached ({config['risk_management']['max_open_positions']})")
                        continue
                    
                    # Check if already have position in this symbol
                    existing_position = next((pos for pos in open_positions if pos.get('tradingSymbol') == symbol), None)
                    if existing_position:
                        logger.info(f"Already have position in {symbol} - skipping buy signal")
                        continue
                    
                    # Calculate position size
                    base_allocation = config['risk_management']['capital_allocation_per_trade']
                    # Adjust allocation based on confidence
                    adjusted_allocation = base_allocation * confidence
                    trade_value = total_value * adjusted_allocation
                    
                    # Get current market price
                    live_data = broker.get_live_market_data(
                        security_id=security_id, 
                        exchange_segment=exchange_segment
                    )
                    
                    if live_data and live_data.get('data', {}).get('last_trade_price', 0) > 0:
                        current_price = live_data['data']['last_trade_price']
                        quantity = int(trade_value / current_price)
                        
                        if quantity > 0:
                            # Validate trade size
                            try:
                                broker.validate_trade_size(quantity, current_price, available_balance)
                                
                                # Place buy order
                                order_response = broker.place_order(
                                    security_id=str(security_id),
                                    exchange_segment=exchange_segment,
                                    transaction_type='BUY',
                                    quantity=quantity,
                                    order_type='MARKET',
                                    product_type='MTF'
                                )
                                
                                if order_response and order_response.get('status') == 'success':
                                    logger.info(f"Buy order placed successfully for {symbol}: {quantity} shares at ~{current_price}")
                                else:
                                    logger.error(f"Buy order failed for {symbol}: {order_response}")
                                    
                            except ValueError as ve:
                                logger.warning(f"Trade validation failed for {symbol}: {ve}")
                        else:
                            logger.warning(f"Calculated quantity is 0 for {symbol} - trade value too small")
                    else:
                        logger.warning(f"Unable to get live price for {symbol}")
                
                # Sell signal processing
                elif action == 'SELL':
                    # Find matching positions to close
                    matching_positions = [pos for pos in open_positions if pos.get('tradingSymbol') == symbol]
                    
                    for position in matching_positions:
                        if position.get('netQty', 0) > 0:  # Only close long positions
                            order_response = broker.place_order(
                                security_id=position['securityId'],
                                exchange_segment=position['exchangeSegment'],
                                transaction_type='SELL',
                                quantity=position['netQty'],
                                order_type='MARKET',
                                product_type='MTF'
                            )
                            
                            if order_response and order_response.get('status') == 'success':
                                logger.info(f"Sell order placed successfully for {symbol}: {position['netQty']} shares")
                            else:
                                logger.error(f"Sell order failed for {symbol}: {order_response}")
                            break
                    else:
                        logger.info(f"No long position found to close for {symbol}")
                        
            except Exception as e:
                logger.error(f"Error processing signal for {signal.get('symbol', 'Unknown')}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error in signal processing: {e}")

def update_display(broker, config, logger):
    """
    Updates the terminal display with current market data and positions.
    """
    try:
        # Get market data for display
        nifty_50_security_id = '13'
        
        # Fetch hourly and daily data
        df_1h = broker.intraday_data(
            security_id=nifty_50_security_id,
            exchange_segment='NSE_INDEX',
            instrument_type='INDEX',
            interval='60'
        )
        
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
        
        # Calculate and display indicators
        if (df_1h is not None and df_1d is not None and 
            isinstance(df_1h, pd.DataFrame) and isinstance(df_1d, dict)):
            
            # Convert historical data response to DataFrame if needed
            if isinstance(df_1d, dict) and 'data' in df_1d:
                df_1d = pd.DataFrame(df_1d['data'])
            
            if isinstance(df_1d, pd.DataFrame) and not df_1d.empty:
                # Calculate indicators
                df_1h = calculate_rsi(df_1h, config['strategy']['rsi_period'])
                df_1h = calculate_adx(df_1h, config['strategy']['adx_period'])
                df_1h = calculate_vwap(df_1h)

                df_1d_calc = calculate_rsi(df_1d.copy(), config['strategy']['rsi_period'])
                df_1d_calc = calculate_adx(df_1d_calc, config['strategy']['adx_period'])
                df_1d_calc = calculate_vwap(df_1d_calc)

                # Prepare indicators for display
                indicators = {
                    'RSI': {
                        '1H': df_1h[f'RSI_{config["strategy"]["rsi_period"]}'].iloc[-1] if not df_1h.empty else 0,
                        '1D': df_1d_calc[f'RSI_{config["strategy"]["rsi_period"]}'].iloc[-1] if not df_1d_calc.empty else 0
                    },
                    'ADX': {
                        '1H': df_1h[f'ADX_{config["strategy"]["adx_period"]}'].iloc[-1] if not df_1h.empty else 0,
                        '1D': df_1d_calc[f'ADX_{config["strategy"]["adx_period"]}'].iloc[-1] if not df_1d_calc.empty else 0
                    },
                    'VWAP': {
                        '1H': df_1h['VWAP'].iloc[-1] if not df_1h.empty else 0,
                        '1D': df_1d_calc['VWAP'].iloc[-1] if not df_1d_calc.empty else 0
                    }
                }
                display_indicators(indicators)
        
        # Display positions with P&L
        open_positions_data = broker.get_open_positions()
        open_positions = open_positions_data['data'] if open_positions_data and 'data' in open_positions_data else []
        
        if open_positions:
            for position in open_positions:
                try:
                    live_data = broker.get_live_market_data(
                        security_id=position['securityId'], 
                        exchange_segment=position['exchangeSegment']
                    )
                    
                    if live_data and live_data.get('data', {}).get('last_trade_price', 0) > 0:
                        current_price = live_data['data']['last_trade_price']
                        buy_avg = position.get('buyAvg', 0)
                        
                        if buy_avg > 0:
                            pnl_percentage = ((current_price - buy_avg) / buy_avg) * 100
                            position['pnl_percentage'] = pnl_percentage
                            position['current_price'] = current_price
                        else:
                            position['pnl_percentage'] = 0.0
                    else:
                        position['pnl_percentage'] = 0.0
                        
                except Exception as e:
                    logger.warning(f"Error calculating P&L for position {position.get('tradingSymbol', 'Unknown')}: {e}")
                    position['pnl_percentage'] = 0.0
                    
            display_positions(open_positions)
        
        # Display account balance
        account_balance = broker.get_account_balance()
        if account_balance and account_balance.get('data'):
            display_funds({
                'availableBalance': account_balance['data'].get('availableBalance', 0),
                'totalValue': account_balance['data'].get('totalValue', 0)
            })
            
    except Exception as e:
        logger.error(f"Error updating display: {e}")

def main():
    """
    Enhanced main entry point for the trading bot with comprehensive error handling.
    """
    logger = setup_logging()
    logger.info("Starting Dhan Trading Bot...")
    
    try:
        # Load configuration
        config = load_config()
        logger.info("Configuration loaded successfully")
        
        # Initialize broker
        broker = DhanBroker()
        logger.info("Broker initialized successfully")
        
        # Initialize strategy
        strategy = BasicStrategy(broker, config)
        logger.info("Strategy initialized successfully")
        
        # Validate trading environment
        if not validate_trading_environment(broker, config, logger):
            logger.error("Trading environment validation failed - exiting")
            return
        
        # Main trading loop
        loop_count = 0
        last_health_check = time.time()
        
        while True:
            try:
                loop_start = time.time()
                loop_count += 1
                
                logger.info(f"Starting trading loop #{loop_count}")
                
                # Periodic health check (every 10 minutes)
                if time.time() - last_health_check > 600:
                    if not broker.health_check():
                        logger.warning("Broker health check failed - continuing with caution")
                    last_health_check = time.time()
                
                # 1. Run the strategy to get signals
                signals = strategy.run()
                logger.info(f"Generated {len(signals)} signals")

                # 2. Process signals and place orders
                if signals:
                    process_trading_signals(signals, broker, config, logger)
                
                # 3. Update terminal display
                update_display(broker, config, logger)
                
                # Calculate and log loop timing
                loop_duration = time.time() - loop_start
                logger.info(f"Trading loop #{loop_count} completed in {loop_duration:.2f} seconds")
                
                # Wait for next iteration (60 seconds)
                time.sleep(60)
                
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt - shutting down gracefully")
                break
            except Exception as e:
                logger.error(f"Error in main trading loop: {e}")
                logger.info("Waiting 60 seconds before retrying...")
                time.sleep(60)
                
    except Exception as e:
        logger.error(f"Critical error in main function: {e}")
        raise
    finally:
        logger.info("Dhan Trading Bot stopped")

if __name__ == '__main__':
    main()