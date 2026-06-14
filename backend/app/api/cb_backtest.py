"""可转债大师策略回测API"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.services.cb_backtest_service import (
    run_cb_backtest,
    run_multi_strategy_compare,
    STRATEGIES,
    DEFAULT_COMMISSION_RATE,
    DEFAULT_SLIPPAGE_BPS,
)

router = APIRouter()


@router.get("/strategies")
async def get_strategies():
    """获取所有可回测的策略定义"""
    strategies = []
    for key, strat in STRATEGIES.items():
        strategies.append({
            'key': key,
            'name': strat['name'],
            'description': strat['description'],
            'sell_rule': strat.get('sell_rule', ''),
        })
    return {
        'strategies': strategies,
        'rebalance_options': [
            {'key': 'weekly', 'name': '每周'},
            {'key': 'biweekly', 'name': '每两周'},
            {'key': 'monthly', 'name': '每月'},
        ],
        'cost_defaults': {
            'commission_rate': DEFAULT_COMMISSION_RATE,
            'slippage_bps': DEFAULT_SLIPPAGE_BPS,
        },
    }


@router.get("/run")
async def run_backtest(
    strategy: str = Query('dual_low', description='策略名称'),
    start_date: str = Query('2023-01-01', description='开始日期'),
    end_date: str = Query('2026-06-13', description='结束日期'),
    rebalance_freq: str = Query('weekly', description='调仓频率'),
    top_n: int = Query(15, description='持仓数量'),
    initial_capital: float = Query(100000, description='初始资金'),
    commission_rate: float = Query(DEFAULT_COMMISSION_RATE, description='佣金费率（单边，默认万2）'),
    slippage_bps: float = Query(DEFAULT_SLIPPAGE_BPS, description='滑点基点（默认2bp）'),
):
    """执行单策略回测"""
    try:
        result = run_cb_backtest(
            strategy=strategy,
            start_date=start_date,
            end_date=end_date,
            rebalance_freq=rebalance_freq,
            top_n=top_n,
            initial_capital=initial_capital,
            commission_rate=commission_rate,
            slippage_bps=slippage_bps,
        )

        if 'error' in result:
            raise HTTPException(status_code=400, detail=result['error'])

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'回测失败: {str(e)}')


@router.get("/compare")
async def compare_strategies(
    strategies: str = Query('dual_low,pancake,andaoquan', description='策略列表，逗号分隔'),
    start_date: str = Query('2023-01-01', description='开始日期'),
    end_date: str = Query('2026-06-13', description='结束日期'),
    rebalance_freq: str = Query('weekly', description='调仓频率'),
    top_n: int = Query(15, description='持仓数量'),
    initial_capital: float = Query(100000, description='初始资金'),
    commission_rate: float = Query(DEFAULT_COMMISSION_RATE, description='佣金费率（单边）'),
    slippage_bps: float = Query(DEFAULT_SLIPPAGE_BPS, description='滑点基点'),
):
    """多策略对比"""
    try:
        strategy_list = [s.strip() for s in strategies.split(',') if s.strip()]

        # 验证策略名称
        for s in strategy_list:
            if s not in STRATEGIES:
                raise HTTPException(
                    status_code=400,
                    detail=f'未知策略: {s}，可选: {", ".join(STRATEGIES.keys())}'
                )

        result = run_multi_strategy_compare(
            strategies=strategy_list,
            start_date=start_date,
            end_date=end_date,
            rebalance_freq=rebalance_freq,
            top_n=top_n,
            initial_capital=initial_capital,
            commission_rate=commission_rate,
            slippage_bps=slippage_bps,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'策略对比失败: {str(e)}')
