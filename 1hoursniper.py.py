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
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=200)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

# Strategy Logic (Improved with EMA, ADX, Volume filters)
def apply_strategy(df):
    df['EMA9'] = ta.trend.ema_indicator(df['close'], window=9)
    df['EMA20'] = ta.trend.ema_indicator(df['close'], window=20)
    df['EMA50'] = ta.trend.ema_indicator(df['close'], window=50)

    # Supertrend (using STC for simplicity)
    supertrend = ta.trend.STCIndicator(close=df['close'], fillna=True)
    df['supertrend'] = supertrend.stc()
    df['supertrend'] = df['supertrend'] > 0.5

    # ADX (trend strength)
    df['ADX'] = ta.trend.adx(df['high'], df['low'], df['close'], window=14)

    # Volume breakout (compare with 20-period average)
    df['vol_avg'] = df['volume'].rolling(window=20).mean()

    df['signal'] = None
    df['exit_signal'] = None
    position = None

    for i in range(1, len(df)):
        strong_trend = df['ADX'].iloc[i] > 20
        volume_breakout = df['volume'].iloc[i] > df['vol_avg'].iloc[i]

        # BUY Signal
        if (
            df['close'].iloc[i] > df['EMA20'].iloc[i] and
            df['EMA20'].iloc[i] > df['EMA50'].iloc[i] and
            df['supertrend'].iloc[i] and
            df['close'].iloc[i] > df['high'].iloc[i - 1] and
            strong_trend and volume_breakout and
            position is None
        ):
            df.at[i, 'signal'] = 'BUY'
            position = 'BUY'

        # SELL Signal
        elif (
            df['close'].iloc[i] < df['EMA20'].iloc[i] and
            df['EMA20'].iloc[i] < df['EMA50'].iloc[i] and
            not df['supertrend'].iloc[i] and
            df['close'].iloc[i] < df['low'].iloc[i - 1] and
            strong_trend and volume_breakout and
            position is None
        ):
            df.at[i, 'signal'] = 'SELL'
            position = 'SELL'

        # EXIT Conditions
        elif position == 'BUY' and (
            not df['supertrend'].iloc[i] or df['close'].iloc[i] < df['low'].iloc[i - 1]
        ):
            df.at[i, 'exit_signal'] = 'EXIT'
            position = None

        elif position == 'SELL' and (
            df['supertrend'].iloc[i] or df['close'].iloc[i] > df['high'].iloc[i - 1]
        ):
            df.at[i, 'exit_signal'] = 'EXIT'
            position = None

    return df

# Chart Setup
fig, axs = plt.subplots(2, 2, figsize=(16, 10))
symbol_axes = dict(zip(symbols, axs.flatten()))

# Shared Legend
custom_lines = [
    plt.Line2D([0], [0], color='blue', label='Close'),
    plt.Line2D([0], [0], color='orange', label='EMA9'),
    plt.Line2D([0], [0], marker='^', color='green', lw=0, label='BUY'),
    plt.Line2D([0], [0], marker='v', color='purple', lw=0, label='SELL'),
    plt.Line2D([0], [0], marker='x', color='red', lw=0, label='EXIT'),
]
fig.legend(handles=custom_lines, loc='upper center', ncol=5, fontsize='medium')

# Update chart
def update(frame):
    for symbol, ax in symbol_axes.items():
        df = fetch_ohlcv(symbol)
        df = apply_strategy(df)

        ax.clear()
        ax.plot(df['timestamp'], df['close'], label='Close', color='blue')
        ax.plot(df['timestamp'], df['EMA9'], label='EMA9', color='orange')

        # Supertrend fill
        ax.fill_between(df['timestamp'], df['low'], df['high'],
                        where=df['supertrend'], color='green', alpha=0.1)
        ax.fill_between(df['timestamp'], df['low'], df['high'],
                        where=~df['supertrend'], color='red', alpha=0.1)

        # Plot signals
        for i in range(len(df)):
            if df['signal'].iloc[i] == 'BUY':
                ax.scatter(df['timestamp'].iloc[i], df['close'].iloc[i], color='green', marker='^', s=100)
            elif df['signal'].iloc[i] == 'SELL':
                ax.scatter(df['timestamp'].iloc[i], df['close'].iloc[i], color='purple', marker='v', s=100)
            elif df['exit_signal'].iloc[i] == 'EXIT':
                ax.scatter(df['timestamp'].iloc[i], df['close'].iloc[i], color='red', marker='x', s=100)

        ax.set_title(symbol)
        ax.set_xlim(df['timestamp'].iloc[-100], df['timestamp'].iloc[-1])
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

    plt.tight_layout(rect=[0, 0, 1, 0.95])  # room for top legend

# Auto-refresh every 5 minutes
ani = FuncAnimation(fig, update, interval=60000, cache_frame_data=False)
plt.show()
