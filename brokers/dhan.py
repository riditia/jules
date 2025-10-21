import os
import pandas as pd
import traceback
from dhanhq import dhanhq
from dotenv import load_dotenv

load_dotenv()

class DhanBroker:
    """
    A broker class for interacting with the Dhan API.
    """
    def __init__(self):
        """
        Initializes the DhanBroker with API credentials from environment variables.
        """
        client_id = os.getenv("DHAN_CLIENT_ID")
        access_token = os.getenv("DHAN_ACCESS_TOKEN")

        if not client_id or not access_token:
            raise ValueError("DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN must be set as environment variables.")

        self.dhan = dhanhq(client_id, access_token)
        self.security_id_map = self._load_security_id_map()

    def _load_security_id_map(self):
        """
        Loads the security ID map from the Dhan API.
        """
        try:
            url = "https://images.dhan.co/api-data/api-scrip-master.csv"
            df = pd.read_csv(url, low_memory=False)
            # The column name for security ID in the CSV is 'SEM_SMST_SECURITY_ID'
            # The column name for the symbol is 'SEM_TRADING_SYMBOL'
            return df.set_index('SEM_TRADING_SYMBOL')['SEM_SMST_SECURITY_ID'].to_dict()
        except Exception as e:
            print(f"Error loading security ID map: {e}")
            return {}

    def get_live_market_data(self, security_id, exchange_segment='NSE_EQ', instrument_type='EQUITY'):
        """
        Fetches live market data for a given security ID.
        """
        try:
            return self.dhan.get_quotes(security_id=str(security_id), exchange_segment=exchange_segment)
        except Exception as e:
            print(f"Error fetching live market data: {e}")
            return None

    def intraday_data(self, security_id, exchange_segment, instrument_type, interval, from_date, to_date):
        """
        Fetches intraday historical data for a given symbol.
        """
        try:
            response = self.dhan.intraday_minute_data(
                security_id=str(security_id),
                exchange_segment=exchange_segment,
                instrument_type=instrument_type,
                interval=interval,
                from_date=from_date,
                to_date=to_date
            )

            if response and response.get('status') == 'success' and 'data' in response:
                df = pd.DataFrame(response['data'])
                # Convert epoch timestamp to datetime and set as index
                df['start_Time'] = pd.to_datetime(df['timestamp'], unit='s')
                return df
            else:
                print(f"Received unexpected or failed response for security ID {security_id}: {response}")
                return None

        except Exception:
            print(f"An exception occurred while fetching intraday data for security ID {security_id}:")
            traceback.print_exc()
            return None

    def get_daily_data(self, security_id, exchange_segment, instrument_type, from_date, to_date):
        """
        Fetches daily historical data for a given symbol.
        """
        try:
            response = self.dhan.historical_daily_data(
                security_id=str(security_id),
                exchange_segment=exchange_segment,
                instrument_type=instrument_type,
                from_date=from_date,
                to_date=to_date
            )

            if response and response.get('status') == 'success' and 'data' in response:
                df = pd.DataFrame(response['data'])
                df['start_Time'] = pd.to_datetime(df['start_Time'])
                return df
            else:
                print(f"Received unexpected or failed response for security ID {security_id}: {response}")
                return None
        except Exception as e:
            print(f"Error fetching daily historical data for security ID {security_id}: {e}")
            traceback.print_exc()
            return None

    def get_account_balance(self):
        """
        Retrieves the current account balance.
        """
        try:
            return self.dhan.get_fund_limits()
        except Exception as e:
            print(f"Error fetching account balance: {e}")
            return None

    def get_open_positions(self):
        """
        RetrieAves a list of open positions.
        """
        try:
            return self.dhan.get_positions()
        except Exception as e:
            print(f"Error fetching open positions: {e}")
            return None

    def place_order(self, security_id, exchange_segment, transaction_type, quantity, order_type, product_type, price=0):
        """
        Places a new order.
        """
        try:
            return self.dhan.place_order(
                security_id=str(security_id),
                exchange_segment=exchange_segment,
                transaction_type=transaction_type,
                quantity=quantity,
                order_type=order_type,
                product_type=product_type,
                price=price
            )
        except Exception as e:
            print(f"Error placing order: {e}")
            return None
