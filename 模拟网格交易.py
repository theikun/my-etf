import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import matplotlib.dates as mdates
from matplotlib.widgets import TextBox

# 1. 读取数据
file_path = "my513300.xlsx"
df = pd.read_excel(file_path)

# 2. 数据预处理
# 合并 date 和 time 列为一个 datetime 列
df['datetime'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str))

def update_plot(text):
    """根据文本框中的日期更新图像"""
    try:
        target_date = pd.to_datetime(text).date()
        df_day = df[df['datetime'].dt.date == target_date].copy()
        if not df_day.empty:
            df_day = df_day.sort_values('datetime')
            ax.clear()
            ax.plot(df_day['datetime'], df_day['close'], linestyle='-', linewidth=1.5, markersize=3)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=30))
            ax.set_title(f'ETF 513300 - {text}', fontsize=16)
            ax.set_xlabel('time', fontsize=12)
            ax.set_ylabel('price', fontsize=12)
            ax.grid(True, linestyle='--', alpha=0.6)
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.draw()
        else:
            print("没有找到该日期的数据")
    except ValueError:
        print("请输入正确的日期格式：YYYY-MM-DD")

# 创建绘图
fig, ax = plt.subplots(figsize=(12, 6))

# 初始日期设置和绘图
initial_date = '2025-07-28'
update_plot(initial_date)

# 添加文本框
axbox = fig.add_axes([0.1, 0.94, 0.1, 0.07]) # 调整位置和大小
text_box = TextBox(axbox, "Enter Date", initial=initial_date)
text_box.on_submit(update_plot)

plt.show()

