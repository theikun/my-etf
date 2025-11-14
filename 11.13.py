from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import datetime  # For datetime objects
import os.path  # To manage paths
import sys  # To find out the script name (in argv[0])
import backtrader as bt
import pandas as pd
from datetime import datetime
import sys

class GridStrategy(bt.Strategy):
    params = (
        ('grid_interval', 0.01),      # 间隔值：绝对值 or 百分比（小数形式）
        ('grid_type', 'absolute'),    # 'absolute' 或 'percentage'
        ('grid_levels', 10),          # 网格层数（上下各 N 层）
        ('stake', 10),                # 每格交易数量
    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.datetime(0)
        print('%s, %s  position.size=%d !!' % (dt.isoformat(), txt,self.position.size))



    def __init__(self):
        self.dataclose = self.datas[0].close
        self.dataopen = self.datas[0].open  # 新增：获取开盘价
        self.order = None
        self.base_price = None
        self.grid_prices = []
        self.active_grids = set()
        self.total_commission = 0.0
        self.last_trading_day = None  # 记录上一个交易日

    # def nextstart(self):
    #     if self.base_price is None:
    #         self.base_price = float(self.dataclose[0])
    #         self.grid_prices = []

    #         if self.p.grid_type == 'percentage':
    #             interval = self.p.grid_interval  # 如 0.005 表示 0.5%
    #             for i in range(-self.p.grid_levels, self.p.grid_levels + 1):
    #                 price = self.base_price * (1 + i * interval)
    #                 self.grid_prices.append(price)
    #         elif self.p.grid_type == 'absolute':
    #             interval = self.p.grid_interval  # 如 0.01 元
    #             for i in range(-self.p.grid_levels, self.p.grid_levels + 1):
    #                 price = self.base_price + i * interval
    #                 self.grid_prices.append(price)
    #         else:
    #             raise ValueError("grid_type must be 'absolute' or 'percentage'")

    #         print(f"Initial grid prices: {self.grid_prices}")

    #         self.grid_prices.sort()
    #         self.log(
    #             f"Grid initialized. Base={self.base_price:.6f}, "
    #             f"Type={self.p.grid_type}, Interval={self.p.grid_interval}, "
    #             f"Levels=±{self.p.grid_levels}"
    #        )
    #交易策略：
    def next(self):
        if self.order:
            return

        current_datetime = self.datas[0].datetime.datetime(0)
        current_date = current_datetime.date()

        # 判断是否是新的一天（且是当天的第一根K线）
        if self.last_trading_day != current_date:
            # 是新一天：重置网格
            self.last_trading_day = current_date
            self.base_price = float(self.dataopen[0])  # 使用当日开盘价作为新基准

            # 重新生成网格
            self.grid_prices = []
            if self.p.grid_type == 'percentage':
                interval = self.p.grid_interval
                for i in range(-self.p.grid_levels, self.p.grid_levels + 1):
                    price = self.base_price * (1 + i * interval)
                    self.grid_prices.append(price)
            elif self.p.grid_type == 'absolute':
                interval = self.p.grid_interval
                for i in range(-self.p.grid_levels, self.p.grid_levels + 1):
                    price = self.base_price + i * interval
                    self.grid_prices.append(price)
            else:
                raise ValueError("grid_type must be 'absolute' or 'percentage'")

            self.grid_prices.sort()
            self.active_grids.clear()  # 可选：清空已触发的网格记录

            self.log(
                f"New day grid initialized. Date={current_date}, "
                f"Base={self.base_price:.6f}, Type={self.p.grid_type}, "
                f"Interval={self.p.grid_interval}, Levels=±{self.p.grid_levels}"
            )

        # 原有的网格交易逻辑（保持不变）
        current_price = float(self.dataclose[0])
        candidate_grids = []

        for price in self.grid_prices:
            key = round(price, 3)
            if key in self.active_grids:
                continue

            if self.p.grid_type == 'absolute':
                tolerance = self.p.grid_interval * 0.1
            else:
                tolerance = abs(self.base_price * self.p.grid_interval * 0.1)

            crossed = False
            if abs(current_price - price) <= tolerance:
                crossed = True
            elif len(self) > 1:
                prev_close = float(self.dataclose[-1])
                if (prev_close < price <= current_price) or (prev_close > price >= current_price):
                    crossed = True

            if crossed:
                candidate_grids.append(price)

        if candidate_grids:
            candidate_grids.sort(key=lambda p: abs(current_price - p))
            best_price = candidate_grids[0]
            key = round(best_price, 3)
            self.active_grids.add(key)

            if best_price > self.base_price:
                if self.position:
                    self.log(f'SELL at grid {best_price:.6f} (current={current_price:.6f})')
                    self.order = self.sell(size=self.p.stake)
                else:
                    self.log(f'SKIP SELL (no position) at {best_price:.6f}')
            elif best_price < self.base_price:
                self.log(f'BUY at grid {best_price:.6f} (current={current_price:.6f})')
                self.order = self.buy(size=self.p.stake)

    #监听订单状态
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status == order.Completed:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.6f}')
            else:
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.6f}')
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
        self.order = None
    #记录每次交易
    def notify_trade(self, trade):
        if trade.isclosed:
            self.log(f'TRADE PROFIT, GROSS {trade.pnl:.3f}, NET {trade.pnlcomm:.3f}')
            commission = trade.commission
            self.total_commission += commission
            self.log(f'>>> Commission this trade: {commission:.3f}, Total so far: {self.total_commission:.3f}')
        
if __name__ == '__main__':
    cerebro = bt.Cerebro()
    #cerebro.addstrategy(TestStrategy)
    cerebro.addstrategy(GridStrategy,grid_type='absolute',grid_interval=0.0004,grid_levels=10,stake=1500)

    modpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    datapath = os.path.join(modpath, '../../datas/orcl-1995-2014.txt')
           #######
    #df = pd.read_excel('my513300.xlsx')
    df = pd.read_excel('sh513310.xlsx')
    df['datetime'] = pd.to_datetime(
    df['date'].dt.strftime('%Y-%m-%d') + ' ' + df['time'].astype(str)
    )
    
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)

    data = bt.feeds.PandasData(
        dataname=df,
        open='open',
        high='high',
        low='low',
        close='close',
        volume='vol',
        fromdate=datetime(2025, 8, 5),
        todate=datetime(2025, 11, 10),
            timeframe=bt.TimeFrame.Minutes,  # 指定时间框架为分钟
        compression=1  # 1分钟线    
    )
    cerebro.adddata(data)

    cerebro.broker.setcash(15000)
    # 0.1% ... 除以 100 以去掉百分号
    cerebro.broker.setcommission(commission=0.00005)
    # cerebro.addsizer(bt.sizers.FixedSize, stake=10)
    # cerebro.broker.setcommission(commission=0.0)

    print('Starting Portfolio Value: %.3f' % cerebro.broker.getvalue())

    cerebro.run()

    print('Final Portfolio Value: %.3f' % cerebro.broker.getvalue())
    
        
    # Plot the result
    
    cerebro.plot()