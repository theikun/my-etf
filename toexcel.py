import struct
from datetime import datetime, timedelta
import csv

csv_file_path = "my513300.csv"
def read_lc1_file(file_path):
    # 打开lc1文件
    with open(file_path, "rb") as ofile:
        data = ofile.read()

    # 初始化一个列表来存储解析后的数据
    kline_data = []

    # 每条记录的长度为32字节
    record_size = 32
    # 计算记录数量
    record_count = len(data) // record_size

    cols = ["date", "time", "open", "high", "low", "close", "amount", "vol"]

    # 遍历每条记录
    for i in range(record_count):
        # 计算记录的起始位置
        start = i * record_size
        # 解析记录
        record = data[start : start + record_size]
        # 使用struct模块解析二进制数据
        unpacked_data = struct.unpack("hhfffffii", record)

        # 解析后的数据格式为：
        # (年月日, 时间, 开盘价, 最高价, 最低价, 收盘价, 成交额, 成交量, 保留字段)
        year = str(int(unpacked_data[0] / 2048) + datetime.now().year + 10)
        month = str(int(unpacked_data[0] % 2048 / 100)).zfill(2)
        day = str(unpacked_data[0] % 2048 % 100).zfill(2)
        hour = str(int(unpacked_data[1] / 60)).zfill(2)
        minute = str(unpacked_data[1] % 60).zfill(2)
        second = "00"
        _open = round(unpacked_data[2], 4)
        _high = round(unpacked_data[3], 4)
        _low = round(unpacked_data[4], 4)
        _close = round(unpacked_data[5], 4)
        _amt = unpacked_data[6]
        _vol = unpacked_data[7] / 100.0

        # 分钟减去1
        dt = datetime(
            int(year), int(month), int(day), int(hour), int(minute), int(second)
        )
        dt = dt - timedelta(minutes=1)

        # 将解析后的数据添加到列表中
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
    # 打开CSV文件并写入数据
    with open(csv_file_path, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=cols)
        writer.writeheader()
        for kline in kline_data:
            writer.writerow(kline)

kline_data, cols = read_lc1_file("E:\\new_tdx\\vipdoc\\sh\\minline\\sh513300.lc1")
write_to_csv(kline_data, cols, csv_file_path)
print(f"数据已写入 {csv_file_path}")