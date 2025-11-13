import struct
from datetime import datetime, timedelta
import csv
import sys
import os

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
    os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)
    with open(csv_file_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=cols)
        writer.writeheader()
        for kline in kline_data:
            writer.writerow(kline)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python script.py <源.lc1文件路径> <目标.csv文件路径>")
        print("例如: python convert.py data/70#US0452.lc1 output/kline.csv")
        sys.exit(1)

    lc1_file = sys.argv[1]
    csv_file = sys.argv[2]

    if not os.path.isfile(lc1_file):
        print(f"错误：源文件不存在：{lc1_file}")
        sys.exit(1)

    kline_data, cols = read_lc1_file(lc1_file)
    write_to_csv(kline_data, cols, csv_file)
    print(f"数据已成功写入：{csv_file}")