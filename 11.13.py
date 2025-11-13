from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import datetime  # For datetime objects
import os.path  # To manage paths
import sys  # To find out the script name (in argv[0])
import backtrader as bt
import pandas as pd
from datetime import datetime
import sys
# class TestStrategy(bt.Strategy):
#     params = (
#         ('maperiod', 15),
#     )

#     def log(self, txt, dt=None):
#         dt = dt or self.datas[0].datetime.datetime(0)
#         print('%s, %s' % (dt.isoformat(), txt))

#     def __init__(self):
#         self.dataclose = self.datas[0].close
#         self.order = None
#         self.buyprice = None
#         self.buycomm = None
#         self.sma = bt.indicators.SimpleMovingAverage(
#             self.datas[0], period=self.params.maperiod)

#     def notify_order(self, order):
#         if order.status in [order.Submitted, order.Accepted]:
#             return

#         if order.status in [order.Completed]:
#             if order.isbuy():
#                 self.log('BUY EXECUTED, Price: %.3f, Cost: %.3f, Comm %.3f' %
#                          (order.executed.price,
#                           order.executed.value,
#                           order.executed.comm))
#                 self.buyprice = order.executed.price
#                 self.buycomm = order.executed.comm
#             else:
#                 self.log('SELL EXECUTED, Price: %.3f, Cost: %.3f, Comm %.3f' %
#                          (order.executed.price,
#                           order.executed.value,
#                           order.executed.comm))
#             self.bar_executed = len(self)

#         elif order.status in [order.Canceled, order.Margin, order.Rejected]:
#             self.log('Order Canceled/Margin/Rejected')

#         self.order = None

#     def notify_trade(self, trade):
#         if not trade.isclosed:
#             return
#         self.log('OPERATION PROFIT, GROSS %.3f, NET %.3f' %
#                  (trade.pnl, trade.pnlcomm))
#     def next(self):
#         self.log('Close, %.3f' % self.dataclose[0])

#         if self.order:
#             return

#         if not self.position:
#             if self.dataclose[0] < self.dataclose[-1]:
#                 if self.dataclose[-1] < self.dataclose[-2]:
#                     self.log('BUY CREATE, %.3f' % self.dataclose[0])
#                     self.order = self.buy()
#         else:
#             if len(self) >= (self.bar_executed + 10):
#                 self.log('SELL CREATE, %.3f' % self.dataclose[0])
#                 self.order = self.sell()

class GridStrategy(bt.Strategy):
    params = (
        ('grid_interval', 0.01),      # 间隔值：绝对值 or 百分比（小数形式）
        ('grid_type', 'absolute'),    # 'absolute' 或 'percentage'
        ('grid_levels', 10),          # 网格层数（上下各 N 层）
        ('stake', 10),                # 每格交易数量
    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.datetime(0)
        print('%s, %s' % (dt.isoformat(), txt))

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.order = None
        self.base_price = None
        self.grid_prices = []
        self.active_grids = set()
        self.total_commission = 0.0

    def nextstart(self):
        if self.base_price is None:
            self.base_price = float(self.dataclose[0])
            self.grid_prices = []

            if self.p.grid_type == 'percentage':
                interval = self.p.grid_interval  # 如 0.005 表示 0.5%
                for i in range(-self.p.grid_levels, self.p.grid_levels + 1):
                    price = self.base_price * (1 + i * interval)
                    self.grid_prices.append(price)
            elif self.p.grid_type == 'absolute':
                interval = self.p.grid_interval  # 如 0.01 元
                for i in range(-self.p.grid_levels, self.p.grid_levels + 1):
                    price = self.base_price + i * interval
                    self.grid_prices.append(price)
            else:
                raise ValueError("grid_type must be 'absolute' or 'percentage'")

            print(f"Initial grid prices: {self.grid_prices}")

            self.grid_prices.sort()
            self.log(
                f"Grid initialized. Base={self.base_price:.6f}, "
                f"Type={self.p.grid_type}, Interval={self.p.grid_interval}, "
                f"Levels=±{self.p.grid_levels}"
            )

    # def next(self):
    #     if self.order:
    #         return

    #     current_price = float(self.dataclose[0])

    #     for price in self.grid_prices:
    #         # 使用四舍五入避免浮点误差（保留6位足够）
    #         key = round(price, 3)
    #         if key not in self.active_grids:
    #             # 判断是否“穿过”该网格（简单起见：只要达到就算）
    #             if self.p.grid_type == 'absolute':
    #                 tolerance = self.p.grid_interval * 0.1  # 容忍微小误差
    #             else:
    #                 tolerance = abs(self.base_price * self.p.grid_interval * 0.1)

    #             if abs(current_price - price) <= tolerance or \
    #                (len(self) > 1 and 
    #                 (self.dataclose[-1] < price <= current_price or 
    #                  self.dataclose[-1] > price >= current_price)):
    #                 # 触发网格
    #                 self.active_grids.add(key)

    #                 if price > self.base_price:
    #                     if self.position:
    #                         self.log(f'SELL at grid {price:.6f} (current={current_price:.6f})')
    #                         self.order = self.sell(size=self.p.stake)
    #                     else:
    #                         self.log(f'SKIP SELL (no position) at {price:.6f}')
    #                 elif price < self.base_price:
    #                     self.log(f'BUY at grid {price:.6f} (current={current_price:.6f})')
    #                     self.order = self.buy(size=self.p.stake)
    #                 # price == base_price: 忽略（或可作为初始仓位）

    #交易策略：
    def next(self):
        if self.order:
            return

        current_price = float(self.dataclose[0])
        candidate_grids = []

        for price in self.grid_prices:
            key = round(price, 3)
            if key in self.active_grids:
                continue

            # 判断是否穿过，可触发
            if self.p.grid_type == 'absolute':
                tolerance = self.p.grid_interval * 0.1
            else:
                tolerance = abs(self.base_price * self.p.grid_interval * 0.1)

            crossed = False
            if abs(current_price - price) <= tolerance:
                crossed = True
            elif len(self) > 1:
                if (self.dataclose[-1] < price <= current_price) or \
                (self.dataclose[-1] > price >= current_price):
                    crossed = True

            if crossed:
                candidate_grids.append(price)

        # 只触发距离当前价最近的那个网格
        if candidate_grids:
            # 按距离当前价的绝对值升序排列
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
    cerebro.addstrategy(GridStrategy,grid_type='absolute',grid_interval=0.004,grid_levels=10,stake=800)

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
        fromdate=datetime(2025, 11, 11),
        todate=datetime(2025, 11, 12),
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