from __future__ import (absolute_import, division, print_function, unicode_literals)
import backtrader as bt
import datetime
import pandas as pd
import os
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

# 回测主程序
if __name__ == '__main__':
    # 创建Cerebro引擎
    cerebro = bt.Cerebro()
    
    # 设置策略参数，可以尝试不同参数组合
    strats = cerebro.addstrategy(
        ATRChannelBreakout,
        atr_period=14,
        atr_multiplier=2.0,
        stake=1000,
        use_trailing_stop=True,
        trailing_percent=0.03,
        printlog=True
    )
    
    # 加载数据
    modpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    
    # 读取数据
    try:
        # 尝试读取Excel文件
        df = pd.read_excel('sh513310.xlsx')
        # 处理日期时间
        df['datetime'] = pd.to_datetime(
            df['date'].dt.strftime('%Y-%m-%d') + ' ' + df['time'].astype(str)
        )
        df.set_index('datetime', inplace=True)
        
        # 创建数据源
        data = bt.feeds.PandasData(
            dataname=df,
            open='open',
            high='high',
            low='low',
            close='close',
            volume='vol',
            fromdate=datetime.datetime(2025, 7, 5),
            todate=datetime.datetime(2025, 11, 6),
            timeframe=bt.TimeFrame.Minutes,
            compression=1  # 1分钟线
        )
    except Exception as e:
        print(f"数据加载错误: {e}")
        print("使用默认示例数据")
        # 使用默认数据
        datapath = os.path.join(modpath, '../../datas/orcl-1995-2014.txt')
        data = bt.feeds.YahooFinanceCSVData(
            dataname=datapath,
            fromdate=datetime.datetime(2000, 1, 1),
            todate=datetime.datetime(2000, 12, 31),
            reverse=False)
    
    # 添加数据到cerebro
    cerebro.adddata(data)
    
    # 设置初始资金
    cerebro.broker.setcash(15000.0)
    
    # 设置佣金
    cerebro.broker.setcommission(commission=0.00005)  # 0.005%
    
    # 添加观察器
    cerebro.addobserver(bt.observers.BuySell)  # 买卖标记
    cerebro.addobserver(bt.observers.Value)    # 资金曲线
    cerebro.addobserver(bt.observers.DrawDown) # 回撤
    
    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    
    # 打印初始资金
    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
    
    # 运行回测
    results = cerebro.run()
    strat = results[0]
    
    # 打印分析结果
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
    print('Sharpe Ratio:', strat.analyzers.sharpe.get_analysis())
    print('DrawDown:', strat.analyzers.drawdown.get_analysis())
    print('Returns:', strat.analyzers.returns.get_analysis())
    
    # 绘制结果
    cerebro.plot(style='candlestick')