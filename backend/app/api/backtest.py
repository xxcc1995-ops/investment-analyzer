"""
通用回测API

支持：
- 多策略选择（出口冠军/高股息/动量/价值/均衡）
- 多基准选择（沪深300/中证500/中证1000/万得全A）
- 手续费/滑点自定义
- 策略对比、敏感性分析、情景分析
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.services.backtest_service import (
    run_backtest,
    analyze_strategy_validity,
    analyze_strategy_ineffectiveness,
    list_strategies,
    BENCHMARK_MAP,
)

router = APIRouter()


@router.get("/strategies")
async def get_strategies():
    """获取可用策略列表"""
    return {
        'strategies': list_strategies(),
        'benchmarks': [
            {'key': k, 'name': v['name']}
            for k, v in BENCHMARK_MAP.items()
        ],
    }


@router.get("")
async def get_backtest_results(
    strategy: str = Query('export_champion', description='策略名称'),
    start_date: str = Query('2020-01-01', description='开始日期'),
    end_date: str = Query('2025-01-01', description='结束日期'),
    rebalance_frequency: str = Query('quarterly', description='调仓频率: weekly/monthly/quarterly/yearly'),
    initial_capital: float = Query(1000000, description='初始资金'),
    top_n: int = Query(10, description='持仓股票数量'),
    benchmark: str = Query('hs300', description='基准指数: hs300/zz500/zz1000/wdqa'),
    commission_rate: float = Query(0.0003, description='佣金费率'),
    slippage_rate: float = Query(0.001, description='滑点率'),
):
    """执行策略回测"""
    try:
        result = run_backtest(
            strategy_name=strategy,
            start_date=start_date,
            end_date=end_date,
            rebalance_frequency=rebalance_frequency,
            initial_capital=initial_capital,
            top_n=top_n,
            benchmark=benchmark,
            commission_rate=commission_rate,
            slippage_rate=slippage_rate,
        )
        validity_analysis = analyze_strategy_validity(result)
        ineffectiveness_analysis = analyze_strategy_ineffectiveness(result)
        return {
            'backtest_result': result,
            'validity_analysis': validity_analysis,
            'ineffectiveness_analysis': ineffectiveness_analysis,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'回测失败: {str(e)}')


@router.get("/compare")
async def compare_strategies(
    strategies: str = Query('export_champion,high_dividend,value', description='策略列表，逗号分隔'),
    start_date: str = Query('2020-01-01', description='开始日期'),
    end_date: str = Query('2025-01-01', description='结束日期'),
    rebalance_frequency: str = Query('quarterly', description='调仓频率'),
    initial_capital: float = Query(1000000, description='初始资金'),
    top_n: int = Query(10, description='持仓数量'),
    benchmark: str = Query('hs300', description='基准指数'),
):
    """多策略对比"""
    try:
        strategy_list = [s.strip() for s in strategies.split(',') if s.strip()]
        results = []
        comparison = []

        for strategy_name in strategy_list:
            result = run_backtest(
                strategy_name=strategy_name,
                start_date=start_date,
                end_date=end_date,
                rebalance_frequency=rebalance_frequency,
                initial_capital=initial_capital,
                top_n=top_n,
                benchmark=benchmark,
            )
            validity = analyze_strategy_validity(result)
            results.append({
                'strategy': strategy_name,
                'name': result['strategy_name'],
                'metrics': {
                    'annual_return': result['annual_return'],
                    'total_return': result['total_return'],
                    'max_drawdown': result['max_drawdown'],
                    'sharpe_ratio': result['sharpe_ratio'],
                    'sortino_ratio': result['sortino_ratio'],
                    'calmar_ratio': result['calmar_ratio'],
                    'volatility': result['volatility'],
                    'win_rate': result['win_rate'],
                    'excess_return': result['excess_return'],
                    'information_ratio': result['information_ratio'],
                    'benchmark_return': result['benchmark_return'],
                },
                'analysis': validity,
                'equity_curve': result['equity_curve'],
                'drawdown_curve': result['drawdown_curve'],
            })
            comparison.append({
                'strategy': strategy_name,
                'name': result['strategy_name'],
                'annual_return': result['annual_return'],
                'total_return': result['total_return'],
                'max_drawdown': result['max_drawdown'],
                'sharpe': result['sharpe_ratio'],
                'sortino': result['sortino_ratio'],
                'calmar': result['calmar_ratio'],
                'volatility': result['volatility'],
                'win_rate': result['win_rate'],
                'excess_return': result['excess_return'],
                'is_effective': validity['is_effective'],
                'score': validity['score'],
            })

        # 按得分排序
        comparison.sort(key=lambda x: x.get('score', 0), reverse=True)

        return {'strategies': results, 'comparison': comparison}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'策略比较失败: {str(e)}')


@router.get("/sensitivity")
async def sensitivity_analysis(
    strategy: str = Query('export_champion', description='策略名称'),
    parameter: str = Query('top_n', description='参数: top_n / rebalance_frequency / commission_rate'),
    start_date: str = Query('2020-01-01', description='开始日期'),
    end_date: str = Query('2025-01-01', description='结束日期'),
    benchmark: str = Query('hs300', description='基准指数'),
    min_value: float = Query(5, description='最小值'),
    max_value: float = Query(20, description='最大值'),
    step: float = Query(5, description='步长'),
):
    """参数敏感性分析"""
    try:
        results = []

        if parameter == 'top_n':
            for top_n in range(int(min_value), int(max_value) + 1, int(step)):
                result = run_backtest(
                    strategy_name=strategy, start_date=start_date, end_date=end_date,
                    top_n=top_n, benchmark=benchmark,
                )
                results.append({
                    'parameter_value': top_n,
                    'annual_return': result['annual_return'],
                    'max_drawdown': result['max_drawdown'],
                    'sharpe_ratio': result['sharpe_ratio'],
                    'excess_return': result['excess_return'],
                    'total_cost': result['total_cost'],
                })
        elif parameter == 'rebalance_frequency':
            for freq in ['weekly', 'monthly', 'quarterly', 'yearly']:
                result = run_backtest(
                    strategy_name=strategy, start_date=start_date, end_date=end_date,
                    rebalance_frequency=freq, benchmark=benchmark,
                )
                results.append({
                    'parameter_value': freq,
                    'annual_return': result['annual_return'],
                    'max_drawdown': result['max_drawdown'],
                    'sharpe_ratio': result['sharpe_ratio'],
                    'excess_return': result['excess_return'],
                    'total_cost': result['total_cost'],
                    'total_trades': result['total_trades'],
                })
        elif parameter == 'commission_rate':
            for rate in np.arange(min_value, max_value + step, step):
                rate = round(rate, 5)
                result = run_backtest(
                    strategy_name=strategy, start_date=start_date, end_date=end_date,
                    commission_rate=rate, benchmark=benchmark,
                )
                results.append({
                    'parameter_value': rate,
                    'annual_return': result['annual_return'],
                    'max_drawdown': result['max_drawdown'],
                    'sharpe_ratio': result['sharpe_ratio'],
                    'total_cost': result['total_cost'],
                })
        else:
            raise HTTPException(status_code=400, detail=f'不支持的参数: {parameter}')

        return {'parameter': parameter, 'results': results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'敏感性分析失败: {str(e)}')


@router.get("/scenarios")
async def scenario_analysis(
    strategy: str = Query('export_champion', description='策略名称'),
    start_date: str = Query('2020-01-01', description='开始日期'),
    end_date: str = Query('2025-01-01', description='结束日期'),
    benchmark: str = Query('hs300', description='基准指数'),
):
    """情景分析 - 不同市场环境"""
    try:
        result = run_backtest(
            strategy_name=strategy, start_date=start_date,
            end_date=end_date, benchmark=benchmark,
        )
        bull = result['bull_market_return']
        bear = result['bear_market_return']
        sideways = result['sideways_market_return']

        return {
            'scenario_results': {
                'bull_market': {
                    'return': bull,
                    'description': '牛市环境（基准涨幅 > 3%/月）',
                    'assessment': '优秀' if bull > 20 else '良好' if bull > 10 else '一般',
                },
                'bear_market': {
                    'return': bear,
                    'description': '熊市环境（基准跌幅 > 3%/月）',
                    'assessment': '优秀' if bear > -5 else '良好' if bear > -15 else '较差',
                },
                'sideways_market': {
                    'return': sideways,
                    'description': '震荡市环境（基准波动 ±3%/月）',
                    'assessment': '优秀' if sideways > 10 else '良好' if sideways > 3 else '一般',
                },
            },
            'recommendations': _get_scenario_recommendations(result),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'情景分析失败: {str(e)}')


def _get_scenario_recommendations(result: dict) -> list:
    """根据情景分析生成建议"""
    recommendations = []
    bull = result.get('bull_market_return', 0)
    bear = result.get('bear_market_return', 0)
    sideways = result.get('sideways_market_return', 0)

    if bull > 20 and bear < -20:
        recommendations.append({'type': 'warning', 'message': '策略波动较大，牛市进攻强但熊市回撤深，适合风险承受能力强的投资者'})
    if bear > -10:
        recommendations.append({'type': 'positive', 'message': '策略防御性强，在熊市中表现稳健'})
    elif bear < -25:
        recommendations.append({'type': 'warning', 'message': '熊市回撤较大，建议增加防御性资产配置'})
    if sideways < 3:
        recommendations.append({'type': 'info', 'message': '策略在震荡市中表现一般，可考虑增加分红权重或降低调仓频率'})
    if bull > 15 and bear > -10:
        recommendations.append({'type': 'positive', 'message': '策略攻守兼备，适合作为核心配置'})

    return recommendations


# numpy import for sensitivity analysis
import numpy as np
