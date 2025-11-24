from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import datetime  # For datetime objects
import os.path  # To manage paths
import sys  # To find out the script name (in argv[0])
import backtrader as bt
import pandas as pd
from datetime import datetime
import sys

class AdvancedGridStrategy(bt.Strategy):
    """
    高级动态ATR网格策略
    特点：
    1. 使用ATR计算动态网格间距。
    2. 包含趋势过滤器（SMA），防止在暴跌趋势中无脑加仓。
    3. 每一笔买单成交后，自动挂出对应的止盈卖单。
    """
    
    params = (
        ('atr_period', 14),       # ATR计算周期
        ('atr_dist_factor', 1.0), # 网格间距倍数 (1.0 表示 1倍ATR)
        ('trend_period', 200),    # 趋势线周期 (SMA200)
        ('qty_per_grid', 10),     # 每一格买入的数量
        ('max_grids', 10),        # 最大允许持有的网格层数 (风控)
        ('print_log', True),      # 是否打印日志
    )

    def log(self, txt, dt=None):
        """ 日志记录函数 """
        if self.params.print_log:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}, {txt}')

    def __init__(self):
        # 初始化指标
        self.atr = bt.indicators.ATR(self.data, period=self.params.atr_period)
        self.sma = bt.indicators.SMA(self.data, period=self.params.trend_period)
        
        # 内部变量
        self.order_pairs = {}  # 记录买单ID和对应的卖单信息
        self.grids_quantity = 0 # 当前持仓的网格数量

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'✅ 网格买入成交: 价格: {order.executed.price:.2f}, 成本: {order.executed.value:.2f}, 手续费: {order.executed.comm:.2f}')
                
                # 买单成交后，立即计算止盈价格并挂卖单
                price = order.executed.price
                # 获取成交时的ATR (为了简化，这里取当天的ATR值，实盘可能需要更精细)
                # 注意：在回测中，order.executed发生时，curr_atr可能已经变化，
                # 这里为了稳健，使用买入价格 + 动态间距
                grid_spread = self.atr[0] * self.params.atr_dist_factor
                target_price = price + grid_spread
                
                # 挂止盈单 (Sell Limit)
                sell_order = self.sell(price=target_price, size=order.executed.size, exectype=bt.Order.Limit)
                
                # 记录配对关系 (可选，用于后续分析)
                self.order_pairs[order.ref] = sell_order.ref
                self.grids_quantity += 1
                self.log(f'⏳ 已挂出止盈单: 目标价格: {target_price:.2f} (间距: {grid_spread:.2f})')

            elif order.issell():
                self.log(f'💰 网格止盈成交: 价格: {order.executed.price:.2f}, 收益: {order.executed.value:.2f}, 手续费: {order.executed.comm:.2f}')
                self.grids_quantity -= 1

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('⚠️ 订单被取消/保证金不足/拒绝')

    def next(self):
        # 1. 趋势风控检查
        # 如果收盘价在SMA之下，且我们没有底仓，或者为了安全起见，暂停开新网格
        is_uptrend = self.data.close[0] > self.sma[0]
        
        # 如果是严重下跌趋势，且持仓过重，这里可以加入止损逻辑 (本策略略过，专注网格)
        
        # 2. 动态网格逻辑
        # 如果当前没有待处理的买单，且持仓数未达上限，且处于上升/震荡趋势中
        if self.grids_quantity < self.params.max_grids and is_uptrend:
            
            # 这是一个简单的连续入场逻辑：
            # 如果最近没有pending的买单，我们基于当前价格下方挂一个新的Buy Limit
            # 实际高级网格通常会预先计算好 Levels，这里演示动态挂单逻辑
            
            # 获取当前动态间距
            current_grid_dist = self.atr[0] * self.params.atr_dist_factor
            buy_price = self.data.close[0] - current_grid_dist
            
            # 检查是否已经有类似的挂单 (防止在同一位置重复挂单)
            # Backtrader的get_orders获取所有未成交订单
            existing_orders = [o for o in self.broker.orders if o.status == bt.Order.Submitted]
            is_duplicate = False
            for o in existing_orders:
                if o.isbuy() and abs(o.price - buy_price) < (current_grid_dist * 0.1):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                self.log(f'📉 发现入场机会 (ATR: {self.atr[0]:.2f}), 挂买单 @ {buy_price:.2f}')
                self.buy(price=buy_price, size=self.params.qty_per_grid, exectype=bt.Order.Limit)

class RSI_EMA_IntradayStrategy(bt.Strategy):
    """
    基于 RSI 超买超卖和 EMA 趋势过滤的日内交易策略
    适用于分钟/小时级别的 K 线数据。
    """
    params = (
        ('rsi_period', 14),           # RSI 计算周期
        ('rsi_low', 30),              # RSI 超卖阈值 (买入条件)
        ('rsi_high', 70),             # RSI 超买阈值 (卖出条件)
        ('ema_period', 50),           # 长期 EMA 周期 (趋势过滤)
        ('order_percent', 0.95),      # 每次交易投入总资金的百分比
        ('printlog', True),           # 是否打印交易日志
    )

    def __init__(self):
        # 记录收盘价和订单状态
        self.dataclose = self.datas[0].close
        self.order = None
        
        # 1. 创建指标
        # 相对强弱指数 (RSI)
        self.rsi = bt.indicators.RSI(self.datas[0], period=self.p.rsi_period)
        
        # 指数移动平均线 (EMA) 作为趋势过滤
        self.ema = bt.indicators.ExponentialMovingAverage(
            self.datas[0], 
            period=self.p.ema_period
        )

        # 额外的指标: 用于图表显示
        # self.stoch = bt.indicators.Stochastic(self.datas[0])
        # self.macd = bt.indicators.MACD(self.datas[0])

    def notify_order(self, order):
        """订单状态发生变化时调用"""
        if order.status in [order.Submitted, order.Accepted]:
            return # 订单已提交/接受，等待执行

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f'BUY EXECUTED, Price: {order.executed.price:.4f}, Size: {order.executed.size}',
                    order_type='BUY'
                )
            elif order.issell():
                self.log(
                    f'SELL EXECUTED, Price: {order.executed.price:.4f}, Size: {order.executed.size}',
                    order_type='SELL'
                )
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected', order_type='ERROR')

        self.order = None

    def notify_trade(self, trade):
        """交易状态发生变化时调用 (平仓时)"""
        if not trade.isclosed:
            return

        self.log(
            f'OPERATION PROFIT, Gross: {trade.pnl:.2f}, Net: {trade.pnlcomm:.2f}', 
            order_type='PROFIT'
        )

    def log(self, txt, order_type='INFO', dt=None):
        """自定义日志函数，支持打印日志开关"""
        if not self.p.printlog:
            return
        dt = dt or self.datas[0].datetime.datetime(0)
        # 打印日期、时间、类型和信息
        print(f'{dt.isoformat()} [{order_type}] {txt}')

    def next(self):
        """主逻辑函数，每个新的 K 线 (分钟/小时) 都会调用一次"""
        # 如果有待处理的订单，则等待订单完成
        if self.order:
            return

        current_close = self.dataclose[0]
        
        # --- 交易逻辑 ---

        # 1. 如果没有头寸 (未持仓) - 寻找买入信号
        if not self.position:
            # 趋势向上过滤：收盘价在长期 EMA 上方
            is_uptrend = current_close > self.ema[0]
            
            # 超卖信号：RSI 低于超卖阈值
            is_oversold = self.rsi[0] < self.p.rsi_low
            
        
            if is_uptrend and is_oversold:
                # 计算买入手数 (使用可用资金的指定百分比)
                # 注意：使用 order_target_percent 更方便管理仓位
                target_value = self.broker.getvalue() * self.p.order_percent
                
                self.log(
                    f'BUY SIGNAL: RSI={self.rsi[0]:.2f} < {self.p.rsi_low} AND Close > EMA', 
                    order_type='SIGNAL'
                )
                
                # 发出市价买入订单，将持仓价值调整到目标百分比
                print("buy signal")
                self.order = self.order_target_value(target=target_value)
                
        # 2. 如果持有头寸 - 寻找卖出信号
        else:
            # 超买信号 (平仓条件)：RSI 高于超买阈值
            is_overbought = self.rsi[0] > self.p.rsi_high
            
            if is_overbought:
                self.log(
                    f'SELL SIGNAL: RSI={self.rsi[0]:.2f} > {self.p.rsi_high}', 
                    order_type='SIGNAL'
                )
                
                # 发出卖出订单，将持仓价值调整到 0 (即全部平仓)
                print("sell signal")
                self.order = self.close()

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    #cerebro.addstrategy(TestStrategy)
    #cerebro.addstrategy(GridStrategy,grid_type='percentage',grid_interval=0.001,grid_levels=10,stake=1000)
    #cerebro.addstrategy(ATRChannelBreakout, atr_period=5, channel_period=20, atr_mult=2.0, printlog=True)
    #RSI_EMA_IntradayStrategy
    #cerebro.addstrategy(RSI_EMA_IntradayStrategy, rsi_period=14,ema_period=50,order_percent=0.95,rsi_low=30,rsi_high=70,printlog=True)
    cerebro.addstrategy(AdvancedGridStrategy, 
                            atr_period=14, 
                            atr_dist_factor=1.5, # 1.5倍ATR作为间距
                            max_grids=20)        # 最多持仓20层
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