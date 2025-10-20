# Dhan Trading Bot

This is a Python-based trading bot that implements a basic EMA crossover strategy for the Dhan trading platform.

## Features

- **Automated Trading:** Executes trades automatically based on a predefined strategy.
- **Real-time Monitoring:** Provides a terminal-based interface to monitor technical indicators, open positions, and account balance.
- **Backtesting:** Includes a backtesting engine to test the strategy on historical data.
- **Secure:** Uses environment variables to store sensitive API credentials, preventing them from being hardcoded in the source code.

## Prerequisites

- Python 3.8+
- A Dhan trading account
- Dhan API Client ID and Access Token

## Setup and Deployment on a VPS

### 1. Clone the Repository

```bash
git clone <repository_url>
cd <repository_name>
```

### 2. Install Dependencies

It is highly recommended to use a virtual environment to manage the project's dependencies.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Set Environment Variables

For security, the bot uses environment variables to store your Dhan API credentials. **Do not hardcode your API keys in the source code.**

Set the following environment variables:

```bash
export DHAN_CLIENT_ID="your_client_id"
export DHAN_ACCESS_TOKEN="your_access_token"
```

To make these variables persistent across reboots, you can add them to your shell's profile file (e.g., `~/.bashrc` or `~/.zshrc`).

### 4. Configure the Strategy

The trading strategy can be configured by editing the `configs/config.yaml` file. This file allows you to adjust parameters such as EMA periods, ADX thresholds, and risk management rules.

### 5. Running the Bot

To start the trading bot, run the `main.py` script:

```bash
python main.py
```

It is recommended to use a process manager like `tmux` or `screen` to keep the bot running in the background after you disconnect from the VPS.

## Backtesting

To backtest the strategy on historical data, you can use the `backtester.py` script. You will need to modify the script to load the historical data you want to test.

## Disclaimer

This trading bot is provided for educational purposes only. Trading in financial markets involves risk, and you are solely responsible for your trading decisions. The author is not responsible for any financial losses you may incur.
