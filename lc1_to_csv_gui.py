import struct
from datetime import datetime, timedelta
import csv
import tkinter as tk
from tkinter import filedialog

def read_lc1_file(file_path):
    with open(file_path, "rb") as ofile:
        data = ofile.read()

    kline_data = []
    record_size = 32
    record_count = len(data) // record_size
    cols = ["date", "time", "open", "high", "low", "close", "amount", "vol"]

    for i in range(record_count):
        start = i * record_size
        record = data[start : start + record_size]
        unpacked_data = struct.unpack("hhfffffii", record)

        year = str(int(unpacked_data[0] / 2048) + datetime.now().year + 10)
        month = str(int(unpacked_data[0] % 2048 / 100)).zfill(2)
        day = str(unpacked_data[0] % 2048 % 100).zfill(2)
        hour = str(int(unpacked_data[1] / 60)).zfill(2)
        minute = str(unpacked_data[1] % 60).zfill(2)
        second = "00"
        _open = round(unpacked_data[2], 3)
        _high = round(unpacked_data[3], 3)
        _low = round(unpacked_data[4], 3)
        _close = round(unpacked_data[5], 3)
        _amt = unpacked_data[6]
        _vol = unpacked_data[7] / 100.0

        dt = datetime(
            int(year), int(month), int(day), int(hour), int(minute), int(second)
        )
        dt = dt - timedelta(minutes=1)

        kline_data.append(
            {
                cols[0]: f"{dt.year}-{dt.month}-{dt.day}",
                cols[1]: f"{dt.hour}:{dt.minute}:{dt.second}",
                cols[2]: _open,
                cols[3]: _high,
                cols[4]: _low,
                cols[5]: _close,
                cols[6]: _amt,
                cols[7]: _vol,
            }
        )

    return kline_data, cols

def write_to_csv(kline_data, cols, csv_file_path):
    with open(csv_file_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=cols)
        writer.writeheader()
        for kline in kline_data:
            writer.writerow(kline)

if __name__ == "__main__":
    # 隐藏主窗口
    root = tk.Tk()
    root.withdraw()

    # 选择 .lc1 源文件
    lc1_file = filedialog.askopenfilename(
        title="请选择 .lc1 源文件",
        filetypes=[("LC1 files", "*.lc1"), ("All files", "*.*")]
    )
    if not lc1_file:
        print("未选择源文件，程序退出。")
        exit()

    # 选择保存 CSV 的路径
    csv_file = filedialog.asksaveasfilename(
        title="请选择保存 CSV 文件的位置",
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )
    if not csv_file:
        print("未选择保存路径，程序退出。")
        exit()

    kline_data, cols = read_lc1_file(lc1_file)
    write_to_csv(kline_data, cols, csv_file)
    print(f"数据已成功写入：{csv_file}")