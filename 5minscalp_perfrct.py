import ccxt
import pandas as pd
import ta
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from datetime import datetime
import matplotlib.dates as mdates

# Setup
exchange = ccxt.delta()
symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT']

# Fetch OHLCV
def fetch_ohlcv(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=200)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

# Strategy Logic
def apply_strategy(df):
    df['EMA9'] = ta.trend.ema_indicator(df['close'], window=9)
    supertrend = ta.trend.STCIndicator(close=df['close'], fillna=True)
    df['supertrend'] = supertrend.stc()
    df['supertrend'] = df['supertrend'] > 0.5

    df['signal'] = None
    df['exit_signal'] = None
    df['take_profit'] = None

    in_position = None
    last_trade_time = None
    cooldown = 5
    tp_multiplier = 1.5

    for i in range(1, len(df)):
        current_time = df['timestamp'].iloc[i]

        if last_trade_time and in_position is None:
            time_diff = (current_time - last_trade_time).total_seconds() / 60.0
            if time_diff < cooldown:
                continue

        if (
            df['close'].iloc[i] > df['EMA9'].iloc[i] and
            df['supertrend'].iloc[i] and
            df['close'].iloc[i] > df['high'].iloc[i-1] and
            in_position is None
        ):
            df.at[i, 'signal'] = 'BUY'
            atr = df['high'].iloc[i] - df['low'].iloc[i]
            df.at[i, 'take_profit'] = df['close'].iloc[i] + tp_multiplier * atr
            last_trade_time = current_time
            in_position = 'BUY'

        elif (
            df['close'].iloc[i] < df['EMA9'].iloc[i] and
            not df['supertrend'].iloc[i] and
            df['close'].iloc[i] < df['low'].iloc[i-1] and
            in_position is None
        ):
            df.at[i, 'signal'] = 'SELL'
            atr = df['high'].iloc[i] - df['low'].iloc[i]
            df.at[i, 'take_profit'] = df['close'].iloc[i] - tp_multiplier * atr
            last_trade_time = current_time
            in_position = 'SELL'

        if in_position == 'BUY' and (
            not df['supertrend'].iloc[i] or
            df['close'].iloc[i] < df['low'].iloc[i-1]
        ):
            df.at[i, 'exit_signal'] = 'EXIT BUY'
            in_position = None

        elif in_position == 'SELL' and (
            df['supertrend'].iloc[i] or
            df['close'].iloc[i] > df['high'].iloc[i-1]
        ):
            df.at[i, 'exit_signal'] = 'EXIT SELL'
            in_position = None

    return df

# Charting
fig, axs = plt.subplots(2, 2, figsize=(15, 10))
symbol_axes = dict(zip(symbols, axs.flatten()))

def update(frame):
    for symbol, ax in symbol_axes.items():
        df = fetch_ohlcv(symbol)
        df = apply_strategy(df)

        ax.clear()
        ax.plot(df['timestamp'], df['close'], label='Close', color='blue')
        ax.plot(df['timestamp'], df['EMA9'], label='EMA9', color='orange')

        # Supertrend coloring
        ax.fill_between(df['timestamp'], df['low'], df['high'],
                        where=df['supertrend'], color='green', alpha=0.1, label='Supertrend Green')
        ax.fill_between(df['timestamp'], df['low'], df['high'],
                        where=~df['supertrend'], color='red', alpha=0.1, label='Supertrend Red')

        # Buy/Sell markers
        for i in range(len(df)):
            if df['signal'].iloc[i] == 'BUY':
                ax.scatter(df['timestamp'].iloc[i], df['close'].iloc[i], color='green', marker='^', s=100, label='BUY')
            elif df['signal'].iloc[i] == 'SELL':
                ax.scatter(df['timestamp'].iloc[i], df['close'].iloc[i], color='red', marker='v', s=100, label='SELL')
            elif df['exit_signal'].iloc[i] == 'EXIT BUY':
                ax.scatter(df['timestamp'].iloc[i], df['close'].iloc[i], color='orange', marker='x', s=100, label='EXIT BUY')
            elif df['exit_signal'].iloc[i] == 'EXIT SELL':
                ax.scatter(df['timestamp'].iloc[i], df['close'].iloc[i], color='purple', marker='x', s=100, label='EXIT SELL')

        ax.set_title(symbol)
        ax.legend(loc='upper left')
        ax.set_xlim(df['timestamp'].iloc[-100], df['timestamp'].iloc[-1])
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

ani = FuncAnimation(fig, update, interval=15000)
plt.tight_layout()
plt.show()
