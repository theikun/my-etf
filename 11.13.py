from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import datetime  # For datetime objects
import os.path  # To manage paths
import sys  # To find out the script name (in argv[0])
import backtrader as bt
import pandas as pd
from datetime import datetime
import sys
class ATRChannelBreakout(bt.Strategy):
    """
    ATR通道突破策略:
    1. 计算ATR指标
    2. 构建价格通道(中轨为收盘价,上轨=中轨+n*ATR,下轨=中轨-n*ATR)
    3. 价格突破上轨时买入
    4. 价格跌破下轨时卖出
    """
    params = (
        ('atr_period', 14),       # ATR计算周期
        ('atr_multiplier', 2.0),  # ATR乘数，决定通道宽度
        ('stake', 10),            # 每次交易数量
        ('use_trailing_stop', False),  # 是否使用追踪止损
        ('trailing_percent', 0.05),    # 追踪止损百分比
        ('printlog', True),       # 是否打印日志
    )

    def log(self, txt, dt=None, doprint=False):
        ''' 日志记录函数 '''
        if self.params.printlog or doprint:
            dt = dt or self.datas[0].datetime.datetime(0)
            print('%s, %s' % (dt.isoformat(), txt))
            
    def __init__(self):
        # 保留对data[0]的引用
        self.dataclose = self.datas[0].close
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low
        
        # 订单和交易状态变量
        self.order = None
        self.buyprice = None
        self.buycomm = None
        self.entry_price = None  # 记录入场价格，用于追踪止损
        
        # 计算ATR指标
        self.atr = bt.indicators.ATR(
            self.datas[0],
            period=self.p.atr_period
        )
        
        # 计算通道中轨 (这里使用收盘价作为中轨，也可使用其他价格如(最高+最低)/2)
        self.middle = self.dataclose
        
        # 计算通道上轨和下轨
        self.upper = self.middle + self.p.atr_multiplier * self.atr
        self.lower = self.middle - self.p.atr_multiplier * self.atr

        # 追踪止损价格
        self.trail_stop_price = None
        
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
            
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    'BUY EXECUTED, Price: %.4f, Cost: %.2f, Comm %.2f' %
                    (order.executed.price,
                     order.executed.value,
                     order.executed.comm))
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
                self.entry_price = order.executed.price  # 保存入场价格
            else:  # Sell
                self.log('SELL EXECUTED, Price: %.4f, Cost: %.2f, Comm %.2f' %
                         (order.executed.price,
                          order.executed.value,
                          order.executed.comm))
                
            self.bar_executed = len(self)
            
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
            
        self.order = None
        
    def notify_trade(self, trade):
        if not trade.isclosed:
            return
            
        self.log('OPERATION PROFIT, GROSS %.2f, NET %.2f' %
                 (trade.pnl, trade.pnlcomm))
                 
    def next(self):
        # 检查是否有挂起的订单，如果有，不执行新订单
        if self.order:
            return
            
        # 检查当前是否有持仓
        if not self.position:  # 没有持仓
            # 买入条件：收盘价突破上轨
            if self.dataclose[0] > self.upper[0]:
                self.log('BUY CREATE, %.4f' % self.dataclose[0])
                self.order = self.buy(size=self.p.stake)
                self.trail_stop_price = None  # 重置追踪止损价格
                
        else:  # 有持仓
            # 如果使用追踪止损
            if self.p.use_trailing_stop and self.entry_price:
                # 计算最新的追踪止损价格
                current_trail_stop = self.dataclose[0] * (1 - self.p.trailing_percent)
                # 如果是首次设置或价格上升，更新追踪止损价格
                if self.trail_stop_price is None or current_trail_stop > self.trail_stop_price:
                    self.trail_stop_price = current_trail_stop
                
                # 检查是否触发追踪止损
                if self.dataclose[0] < self.trail_stop_price:
                    self.log('TRAILING STOP TRIGGERED, %.4f' % self.dataclose[0])
                    self.order = self.sell(size=self.p.stake)
                    return
                    
            # 卖出条件：收盘价跌破下轨
            if self.dataclose[0] < self.lower[0]:
                self.log('SELL CREATE, %.4f' % self.dataclose[0])
                self.order = self.sell(size=self.p.stake)
                
    def stop(self):
        self.log('(ATR Period %2d, Multiplier %.2f) Ending Value %.2f' %
                 (self.params.atr_period, self.params.atr_multiplier,
                  self.broker.getvalue()), doprint=True)
        
class GridStrategy(bt.Strategy):  #ai
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
        
class GridStrategy1(bt.Strategy):
    params=(
        # 设置档位总数
        ('number', 10),
        # 设置初始仓位
        ('open_percent', 0.5),
        # 设置挡位间距
        ('distance', 0),
        # 设置基准价格
        ('base_price',0)
    )

    def __init__(self):
        # 设置初始订单状态
        self.open_flg=False
        self.last_index = 0
        self.per_size=0
        self.max_index = 0
        self.min_index = 0
        self.order=None

        
    def log(self, txt, dt=None):
        dt = dt or self.data.datetime[0]
        dt = bt.num2date(dt).date()
        print(f'{dt}: {txt}')

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # 订单状态 submitted/accepted，无动作
            return

        # 订单完成
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log('买单执行,%s, %.3f, %i' % (order.data._name,
                                                order.executed.price, order.executed.size))
                
            elif order.issell():
                self.log('卖单执行, %s, %.3f, %i' % (order.data._name,
                                                 order.executed.price, order.executed.size))
            print('佣金 %.2f, 市值 %.2f, 现金 %.2f' %
                  ( order.executed.comm, self.broker.getvalue(), self.broker.getcash()))
            
        else:
            self.log('订单作废 %s, %s, isbuy=%i, size %i, open price %.2f' %
                     (order.data._name, order.getstatusname(), order.isbuy(), order.created.size, order.data.open[0]))
        self.order=None # 重置订单状态

    def next(self):
        # 判断是否已买入初始订单
        if self.open_flg:
            # 计算今日挡位
            index = (self.data.close[0] - self.p.base_price) // self.p.distance

            # 如果今日挡位低于下边界
            if index < self.min_index:
                # 用下边界替代今日挡位
                index = self.min_index
            # 如果当前挡位高于上边界
            elif index > self.max_index:
                # 用上边界替代今日挡位
                index = self.max_index

            self.log("上一交易日挡位:{}".format(self.last_index))
            self.log("当前交易日挡位:{}".format(index))

            # 计算挡位变化数
            change_index = index - self.last_index
            # 如果挡位变化数大于0
            if change_index > 0:
                # 执行卖出
                self.sell(data=self.data, size=change_index*self.per_size)
            # 如果挡位变化数小于0
            elif change_index < 0:
                # 执行买入
                self.buy(data=self.data, size=change_index*self.per_size)
            
            # 更新前一日挡位
            self.last_index = index
        # 判断是否已买入初始订单
        if not self.open_flg and math.fabs(self.data.close[0]-self.p.base_price)/self.p.base_price < 0.01:

            # 计算所需买入的初始订单数量
            buy_size = self.broker.getvalue() / self.data.close[0] * self.p.open_percent // 100 * 100
            # 执行买入
            self.buy(data=self.data, size=buy_size)

            # 记录前一交易日的挡位，初始挡位是0
            self.last_index = 0
            # 计算每变化一挡对应的订单数量
            self.per_size = self.broker.getvalue() / self.data.close[0] / self.p.number // 100 * 100
            # 计算档位的上边界
            self.max_index = round(self.p.number * self.p.open_percent)
            # 计算档位的下边界，由于在初始挡位的下方，所以结果是负数
            self.min_index = self.max_index - self.p.number 

            # 更新初始订单状态
            self.open_flg = True
            self.log('已买入初始订单')
        

        self.log("当前持仓规模:{},市值:{},现金:{}".format(self.getposition(self.data).size,self.broker.getvalue(), self.broker.getcash()))

class MovingAverageCrossStrategy(bt.Strategy):
    params = (
        ('fast_length', 10),
        ('slow_length', 30),
    )
    
    def __init__(self):
        self.fast_ma = bt.indicators.SMA(self.data.close, period=self.params.fast_length)
        self.slow_ma = bt.indicators.SMA(self.data.close, period=self.params.slow_length)
    
    def next(self):
        if self.fast_ma[0] > self.slow_ma[0]:
            self.buy()
        elif self.fast_ma[0] < self.slow_ma[0]:
            self.sell()

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    #cerebro.addstrategy(TestStrategy)
    #cerebro.addstrategy(GridStrategy,grid_type='percentage',grid_interval=0.001,grid_levels=10,stake=1000)
    cerebro.addstrategy(
        ATRChannelBreakout,
        atr_period=14,
        atr_multiplier=2.0,
        stake=1000,
        use_trailing_stop=True,
        trailing_percent=0.03,
        printlog=True
    )

    # cerebro.addstrategy(MovingAverageCrossStrategy)
    
    modpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    datapath = os.path.join(modpath, '../../datas/orcl-1995-2014.txt')
           #######
    df = pd.read_excel('sh513310.xlsx')
    #df = pd.read_excel('sh511700场内货币.xlsx')
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
        fromdate=datetime(2025, 7, 5),
        todate=datetime(2025, 11, 6),
            timeframe=bt.TimeFrame.Minutes,  # 指定时间框架为分钟
        compression=1  # 1分钟线    
    )
    cerebro.adddata(data)

    cerebro.broker.setcash(1500000)
    # 0.1% ... 除以 100 以去掉百分号
    cerebro.broker.setcommission(commission=0.00005)

    # 修复2: 显式添加买卖标记观察器
    cerebro.addobserver(bt.observers.BuySell)  # 关键！确保显示买卖标记、
    cerebro.addobserver(bt.observers.Value)    # 添加资金曲线观察器

    print('Starting Portfolio Value: %.3f' % cerebro.broker.getvalue())

    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    thestrats = cerebro.run()
    # 获取
    returns = thestrats[0].analyzers.returns.get_analysis()['rtot']
    print(f"Returns: {returns}")
    
    print('Final Portfolio Value: %.3f' % cerebro.broker.getvalue())
    
        
    # Plot the result
    
    cerebro.plot()