import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import date2num
from mplfinance.original_flavor import candlestick_ohlc
from matplotlib.ticker import FuncFormatter
import streamlit as st
from datetime import timedelta

# Streamlit標題
st.title("股票分析工具")

# 輸入股票代碼
stock_code = st.text_input("輸入股票代碼（例如 2330.TW 或 TSLA）", value="TSLA")

# 抓取股票數據（3年）
stock = yf.Ticker(stock_code)
data = stock.history(period="3y")

# 確保索引是 DatetimeIndex
if not isinstance(data.index, pd.DatetimeIndex):
    data.index = pd.to_datetime(data.index)

# 定義指標計算函數
def calculate_indicators(data):
    data["EMA5"] = data["Close"].ewm(span=5, adjust=False).mean()
    data["EMA13"] = data["Close"].ewm(span=13, adjust=False).mean()
    data["EMA55"] = data["Close"].ewm(span=55, adjust=False).mean()
    data["EMA233"] = data["Close"].ewm(span=233, adjust=False).mean()
    data["EMA12"] = data["Close"].ewm(span=12, adjust=False).mean()
    data["EMA26"] = data["Close"].ewm(span=26, adjust=False).mean()
    data["MACD"] = data["EMA12"] - data["EMA26"]
    data["Signal_Line"] = data["MACD"].ewm(span=9, adjust=False).mean()
    data["MACD_Hist"] = data["MACD"] - data["Signal_Line"]
    delta = data["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    data["RSI"] = 100 - (100 / (1 + rs))
    data["HighLevel"] = data["High"].rolling(window=15).max()
    data["LowLevel"] = data["Low"].rolling(window=15).min()
    data["EMA233_Slope"] = data["EMA233"].diff()
    data["Color"] = data["Close"].diff().apply(lambda x: '#00ff00' if x >= 0 else '#ff0000')
    return data

# 定義策略函數
def apply_strategy(data):
    bullish_conditions = (
        (data["EMA5"] > data["EMA13"])
        & (data["MACD"] < 0)
        & (data["Signal_Line"] < 0)
        & (data["MACD"] > data["Signal_Line"])
        & (data["EMA233_Slope"] > 0)
        & (data["Close"] > data["LowLevel"])
        & (data["RSI"] > data["RSI"].shift(1))
    )
    bearish_conditions = (
        (data["EMA5"] < data["EMA13"])
        & (data["MACD"] > 0)
        & (data["Signal_Line"] > 0)
        & (data["MACD"] < data["Signal_Line"])
        & (data["EMA233_Slope"] < 0)
        & (data["Close"] < data["HighLevel"])
        & (data["RSI"] < data["RSI"].shift(1))
    )
    data["Signal"] = 0
    data.loc[bullish_conditions, "Signal"] = 1  # Buy
    data.loc[bearish_conditions, "Signal"] = -1  # Sell
    return data

# 計算指標和訊號
data = calculate_indicators(data)
data = apply_strategy(data)

# 切片近8個月數據
try:
    end_date = data.index.max()
    display_start = end_date - timedelta(days=8*30)
    data_display = data.loc[display_start:end_date].copy()
except Exception as e:
    st.error(f"日期計算錯誤：{e}")
    st.stop()

# 轉換日期為數字（candlestick_ohlc需要）
data_display["DateNum"] = date2num(data_display.index.to_pydatetime())

# 準備K線數據
ohlc = data_display[['DateNum', 'Open', 'High', 'Low', 'Close']].values

# 提取八個月內的買賣訊號並生成表格
signals_df = data_display[data_display['Signal'] != 0][['Signal']].copy()
signals_df['Date'] = signals_df.index
signals_df['Stock'] = stock_code.upper()
signals_df['Signal Type'] = signals_df['Signal'].map({1: 'Buy', -1: 'Sell'})
signals_df = signals_df[['Date', 'Stock', 'Signal Type']].reset_index(drop=True)

# 顯示表格
st.subheader("近八個月內的買賣訊號")
if not signals_df.empty:
    st.dataframe(signals_df)
else:
    st.write("近八個月內無買賣訊號。")

# 繪製圖表
fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(14, 14), gridspec_kw={"height_ratios": [6, 2, 2, 2]}, sharex=True)
fig.patch.set_facecolor('#1e1e1e')

# K線圖
candlestick_ohlc(ax1, ohlc, width=0.6, colorup='#32CD32', colordown='#FF6347', alpha=0.8)
ax1.plot(data_display.index, data_display['EMA5'], label='EMA5', color='#1e90ff', linewidth=1)
ax1.plot(data_display.index, data_display['EMA13'], label='EMA13', color='#32cd32', linewidth=1)
ax1.plot(data_display.index, data_display['EMA55'], label='EMA55', color='#FFD700', linewidth=1.5)
ax1.plot(data_display.index, data_display['EMA233'], label='EMA233', color='#DA70D6', linewidth=2)

# 買賣訊號
buy_signals = data_display[data_display['Signal'] == 1]
sell_signals = data_display[data_display['Signal'] == -1]
ax1.scatter(buy_signals.index, buy_signals['Low'] * 0.9, marker='^', color='#3CB371', s=100, label='Buy')
ax1.scatter(sell_signals.index, sell_signals['High'] * 1.1, marker='v', color='#FF6347', s=100, label='Sell')

ax1.set_title(f'{stock_code.upper()} Stock Analysis', fontsize=16, fontweight='bold', color='#e1e1e1')
ax1.set_ylabel('Price', color='#e1e1e1')
ax1.legend(loc='upper left', fancybox=True, framealpha=0.3, fontsize=10)
ax1.grid(True, linestyle='--', alpha=0.3)
ax1.set_facecolor('#2a2a2a')

# Volume子圖（無網格線）
ax2.bar(data_display.index, data_display['Volume'], color=data_display['Color'], alpha=0.3, width=0.8)
ax2.set_ylabel('Volume', color='#e1e1e1')
ax2.set_facecolor('#2a2a2a')
ax2.grid(False)

# RSI子圖
ax3.plot(data_display.index, data_display['RSI'], label='RSI', color='#e1e1e1', linewidth=1.5)
ax3.axhline(y=70, color='#ff4500', linestyle='--', alpha=0.5)
ax3.axhline(y=30, color='#00ff00', linestyle='--', alpha=0.5)
ax3.set_ylabel('RSI', color='#e1e1e1')
ax3.legend(loc='upper left', fancybox=True, framealpha=0.3, fontsize=10)
ax3.grid(True, linestyle='--', alpha=0.3)
ax3.set_facecolor('#2a2a2a')

# MACD子圖
ax4.plot(data_display.index, data_display['MACD'], label='MACD', color='#1e90ff', linewidth=1.5)
ax4.plot(data_display.index, data_display['Signal_Line'], label='Signal', color='#ffa500', linewidth=1.5)
ax4.bar(data_display.index, data_display['MACD_Hist'], label='Histogram', color='#e1e1e1', alpha=0.5, width=0.8)
ax4.set_ylabel('MACD', color='#e1e1e1')
ax4.legend(loc='upper left', fancybox=True, framealpha=0.3, fontsize=10)
ax4.grid(True, linestyle='--', alpha=0.3)
ax4.set_facecolor('#2a2a2a')

# 設置X軸日期格式
ax4.xaxis_date()
ax4.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%Y-%m-%d'))
fig.autofmt_xdate()

# 設置Y軸價格格式
def price_formatter(x, p):
    return f'${x:,.2f}'
ax1.yaxis.set_major_formatter(FuncFormatter(price_formatter))

# 設置Volume子圖Y軸格式（簡化為K或M）
def volume_formatter(x, p):
    if x >= 1e6:
        return f'{x / 1e6:.1f}M'
    elif x >= 1e3:
        return f'{x / 1e3:.1f}K'
    else:
        return f'{x:.0f}'
ax2.yaxis.set_major_formatter(FuncFormatter(volume_formatter))

# 將X軸和Y軸文字設為白色，並將Y軸移到右邊
for ax in [ax1, ax2, ax3, ax4]:
    ax.tick_params(axis='x', colors='#e1e1e1')
    ax.tick_params(axis='y', colors='#e1e1e1')
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")

# 調整子圖間距
plt.subplots_adjust(hspace=0.05)

# 用Streamlit顯示圖表
st.pyplot(fig)