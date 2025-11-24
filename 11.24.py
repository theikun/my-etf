from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import datetime  # For datetime objects
import os.path  # To manage paths
import sys  # To find out the script name (in argv[0])
import backtrader as bt
import pandas as pd
from datetime import datetime
import itertools
import numpy as np
import matplotlib.pyplot as plt

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
        ('printlog', False),          # 参数优化时关闭日志，避免输出过多
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
        
        # 用于跟踪策略表现
        self.trade_count = 0

    def notify_order(self, order):
        """订单状态发生变化时调用"""
        if order.status in [order.Submitted, order.Accepted]:
            return # 订单已提交/接受，等待执行

        if order.status in [order.Completed]:
            if order.isbuy():
                self.trade_count += 1
            elif order.issell():
                pass
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            pass

        self.order = None

    def notify_trade(self, trade):
        """交易状态发生变化时调用 (平仓时)"""
        pass

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
                target_value = self.broker.getvalue() * self.p.order_percent
                
                # 发出市价买入订单，将持仓价值调整到目标百分比
                self.order = self.order_target_value(target=target_value)
                
        # 2. 如果持有头寸 - 寻找卖出信号
        else:
            # 超买信号 (平仓条件)：RSI 高于超买阈值
            is_overbought = self.rsi[0] > self.p.rsi_high
            
            if is_overbought:
                # 发出卖出订单，将持仓价值调整到 0 (即全部平仓)
                self.order = self.close()


def run_optimization():
    """运行参数优化并返回结果"""
    # 1. 准备数据
    df = pd.read_excel('sh513310.xlsx')
    df['datetime'] = pd.to_datetime(
        df['date'].dt.strftime('%Y-%m-%d') + ' ' + df['time'].astype(str)
    )
    df.set_index('datetime', inplace=True)
    
    # 2. 创建cerebro实例
    cerebro = bt.Cerebro(maxcpus=None, optreturn=False)  # optreturn=False获取完整策略实例
    
    # 3. 添加数据
    data = bt.feeds.PandasData(
        dataname=df,
        open='open',
        high='high',
        low='low',
        close='close',
        volume='vol',
        fromdate=datetime(2025, 7, 5),
        todate=datetime(2025, 11, 6),
        timeframe=bt.TimeFrame.Minutes,
        compression=1  # 1分钟线    
    )
    cerebro.adddata(data)
    
    # 4. 设置初始资金和佣金
    cerebro.broker.setcash(1500000)
    cerebro.broker.setcommission(commission=0.00005)  # 0.005%
    
    # 5. 添加分析器
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.0)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    
    # 6. 设置参数优化
    # 定义要测试的参数范围
    rsi_low_range = range(20, 41, 5)  # 20, 25, 30, 35, 40
    rsi_high_range = range(60, 81, 5) # 60, 65, 70, 75, 80
    
    # 添加策略进行优化
    cerebro.optstrategy(
        RSI_EMA_IntradayStrategy,
        rsi_period=14,
        ema_period=50,
        order_percent=0.95,
        rsi_low=rsi_low_range,
        rsi_high=rsi_high_range,
        printlog=False
    )
    
    # 7. 运行回测
    print(f"开始参数优化，共测试 {len(rsi_low_range)*len(rsi_high_range)} 种参数组合...")
    optimized_runs = cerebro.run()
    
    # 8. 收集结果
    results = []
    for run in optimized_runs:
        strategy = run[0]
        params = strategy.params
        
        # 获取分析结果
        returns_analysis = strategy.analyzers.returns.get_analysis()
        sharpe_analysis = strategy.analyzers.sharpe.get_analysis()
        drawdown_analysis = strategy.analyzers.drawdown.get_analysis()
        trades_analysis = strategy.analyzers.trades.get_analysis()
        
        # 计算总收益率
        total_return = returns_analysis.get('rtot', 0)
        
        # 计算交易次数
        total_trades = 0
        if hasattr(trades_analysis, 'total'):
            total_trades = trades_analysis.total.total
        
        results.append({
            'rsi_low': params.rsi_low,
            'rsi_high': params.rsi_high,
            'final_value': strategy.broker.getvalue(),
            'total_return': total_return * 100,  # 转换为百分比
            'sharpe_ratio': sharpe_analysis.get('sharperatio', 0),
            'max_drawdown': drawdown_analysis.max.drawdown,
            'trade_count': total_trades,
        })
    
    return results


def analyze_and_plot_results(results):
    """分析和可视化优化结果"""
    # 转换为DataFrame
    results_df = pd.DataFrame(results)
    
    # 按总收益率排序
    results_df = results_df.sort_values('total_return', ascending=False)
    
    print("\n" + "="*80)
    print("参数优化结果 (按总收益率排序):")
    print("="*80)
    print(results_df.to_string(index=False))
    
    # 保存结果到CSV
    results_df.to_csv('rsi_optimization_results.csv', index=False)
    print(f"\n结果已保存到 rsi_optimization_results.csv")
    
    # 创建热力图
    plt.figure(figsize=(16, 10))
    
    # 1. 总收益率热力图
    pivot_return = results_df.pivot(index='rsi_low', columns='rsi_high', values='total_return')
    plt.subplot(2, 2, 1)
    im = plt.imshow(pivot_return, cmap='RdYlGn', aspect='auto')
    plt.colorbar(im, label='总收益率 (%)')
    plt.title('RSI参数组合 - 总收益率 (%)')
    plt.xlabel('RSI High 阈值')
    plt.ylabel('RSI Low 阈值')
    
    # 添加数值标签
    for i in range(len(pivot_return.index)):
        for j in range(len(pivot_return.columns)):
            plt.text(j, i, f'{pivot_return.iloc[i, j]:.1f}%',
                    ha='center', va='center', color='black' if abs(pivot_return.iloc[i, j]) < 50 else 'white')
    
    # 2. 夏普比率热力图
    pivot_sharpe = results_df.pivot(index='rsi_low', columns='rsi_high', values='sharpe_ratio')
    plt.subplot(2, 2, 2)
    im = plt.imshow(pivot_sharpe, cmap='RdYlGn', aspect='auto')
    plt.colorbar(im, label='夏普比率')
    plt.title('RSI参数组合 - 夏普比率')
    plt.xlabel('RSI High 阈值')
    plt.ylabel('RSI Low 阈值')
    
    # 3. 3D图表：收益率 vs RSI Low vs RSI High
    ax = plt.subplot(2, 2, 3, projection='3d')
    
    # 为3D图准备数据
    rsi_lows = results_df['rsi_low'].values
    rsi_highs = results_df['rsi_high'].values
    returns = results_df['total_return'].values
    
    # 3D散点图
    sc = ax.scatter(rsi_lows, rsi_highs, returns, c=returns, cmap='viridis', s=50, alpha=0.8)
    ax.set_xlabel('RSI Low')
    ax.set_ylabel('RSI High')
    ax.set_zlabel('总收益率 (%)')
    ax.set_title('3D: RSI参数与收益率关系')
    plt.colorbar(sc, ax=ax, label='总收益率 (%)')
    
    # 4. 交易次数与收益率关系
    plt.subplot(2, 2, 4)
    scatter = plt.scatter(results_df['trade_count'], results_df['total_return'], 
                         c=results_df['sharpe_ratio'], s=50, alpha=0.7, cmap='viridis')
    plt.colorbar(scatter, label='夏普比率')
    plt.xlabel('总交易次数')
    plt.ylabel('总收益率 (%)')
    plt.title('交易频率与收益关系')
    plt.grid(True)
    
    plt.tight_layout()
    plt.savefig('rsi_optimization_analysis.png', dpi=300, bbox_inches='tight')
    print(f"\n分析图表已保存到 rsi_optimization_analysis.png")
    
    # 找出最佳参数组合
    best_result = results_df.iloc[0]
    print("\n" + "="*80)
    print(f"最佳参数组合: RSI Low = {best_result['rsi_low']}, RSI High = {best_result['rsi_high']}")
    print(f"预期总收益率: {best_result['total_return']:.2f}%")
    print(f"夏普比率: {best_result['sharpe_ratio']:.2f}")
    print(f"最大回撤: {best_result['max_drawdown']:.2f}%")
    print(f"总交易次数: {best_result['trade_count']}")
    print("="*80)
    
    return best_result


def run_best_strategy(best_params):
    """使用最佳参数运行完整回测，生成详细图表和日志"""
    print("\n" + "="*80)
    print(f"使用最佳参数运行完整回测: RSI Low={best_params['rsi_low']}, RSI High={best_params['rsi_high']}")
    print("="*80)
    
    # 1. 准备数据
    df = pd.read_excel('sh513310.xlsx')
    df['datetime'] = pd.to_datetime(
        df['date'].dt.strftime('%Y-%m-%d') + ' ' + df['time'].astype(str)
    )
    df.set_index('datetime', inplace=True)
    
    # 2. 创建cerebro实例
    cerebro = bt.Cerebro()
    
    # 3. 添加数据
    data = bt.feeds.PandasData(
        dataname=df,
        open='open',
        high='high',
        low='low',
        close='close',
        volume='vol',
        fromdate=datetime(2025, 7, 5),
        todate=datetime(2025, 11, 6),
        timeframe=bt.TimeFrame.Minutes,
        compression=1  # 1分钟线    
    )
    cerebro.adddata(data)
    
    # 4. 设置初始资金和佣金
    initial_cash = 1500000
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=0.00005)
    
    # 5. 添加策略（使用最佳参数）
    cerebro.addstrategy(
        RSI_EMA_IntradayStrategy,
        rsi_period=14,
        ema_period=50,
        order_percent=0.95,
        rsi_low=best_params['rsi_low'],
        rsi_high=best_params['rsi_high'],
        printlog=True  # 这次开启详细日志
    )
    
    # 6. 添加观察器
    cerebro.addobserver(bt.observers.BuySell)  # 买卖标记
    cerebro.addobserver(bt.observers.Value)    # 资金曲线
    cerebro.addobserver(bt.observers.DrawDown) # 回撤曲线
    cerebro.addobserver(bt.observers.Trades)   # 交易记录
    
    # 7. 添加分析器
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    
    # 8. 运行回测
    print(f'初始资金: {initial_cash:.2f}')
    results = cerebro.run()
    strategy = results[0]
    
    # 9. 打印详细结果
    final_value = cerebro.broker.getvalue()
    total_return = (final_value - initial_cash) / initial_cash * 100
    
    print(f'\n最终资金: {final_value:.2f}')
    print(f'总收益率: {total_return:.2f}%')
    print(f"夏普比率: {strategy.analyzers.sharpe.get_analysis().get('sharperatio', 0):.2f}")
    print(f"最大回撤: {strategy.analyzers.drawdown.get_analysis().max.drawdown:.2f}%")
    
    # 10. 绘制详细图表
    print("\n生成详细回测图表...")
    cerebro.plot(
        style='candlestick',
        barup='red', bardown='green',  # A股习惯红涨绿跌
        volume=False,
        subplot=True,
        plotvaluetrades=True,
        plotname=f"RSI_EMA策略 (RSI-Low={best_params['rsi_low']}, RSI-High={best_params['rsi_high']})",
        figsize=(16, 10)
    )
    
    print("图表已生成并显示。按任意键继续...")
    input()  # 等待用户按键


if __name__ == '__main__':
    # 步骤1: 运行参数优化
    optimization_results = run_optimization()
    
    # 步骤2: 分析和可视化结果
    best_params = analyze_and_plot_results(optimization_results)
    
    # 步骤3: 使用最佳参数运行完整回测
    run_best_strategy(best_params)