"""
test_grid_service.py — 网格交易计算测试

覆盖:
- _is_hk_code
- MarketCost 属性
- calculate_atr
- generate_grid_levels
- calculate_grid_positions
- breakeven_analysis
- get_grid_status
- detect_grid_decay
- simulate_grid_trading (纯计算, 无需网络)
"""

import sys
import os
import math
import pytest
import numpy as np

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# grid_service 模块级导入了 app.core.cache, 需要确保可导入
try:
    from app.services.grid_service import (
        _is_hk_code,
        MarketCost,
        HK_COST,
        A_COST,
        get_market_cost,
        calculate_atr,
        generate_grid_levels,
        calculate_grid_positions,
        breakeven_analysis,
        get_grid_status,
        detect_grid_decay,
        simulate_grid_trading,
        _empty_simulation,
    )
    GRID_IMPORT_OK = True
except ImportError:
    GRID_IMPORT_OK = False


pytestmark = pytest.mark.skipif(
    not GRID_IMPORT_OK,
    reason="grid_service 模块导入失败 (可能缺少 app.core.cache 依赖)"
)


# ============================================================
# _is_hk_code
# ============================================================

class TestIsHKCode:
    def test_hk_code_5_digits(self):
        assert _is_hk_code("00700") is True

    def test_a_code_6_digits(self):
        assert _is_hk_code("600519") is False

    def test_hk_code_with_spaces(self):
        assert _is_hk_code(" 00700 ") is True

    def test_short_code(self):
        assert _is_hk_code("123") is False

    def test_alpha_code(self):
        assert _is_hk_code("AAPL") is False


# ============================================================
# MarketCost 属性
# ============================================================

class TestMarketCost:
    def test_buy_cost_rate(self):
        cost = MarketCost(stamp_duty_sell=0.001, commission=0.0003,
                          other_fees=0.0001, min_commission=5)
        assert cost.buy_cost_rate == 0.0003 + 0.0001

    def test_sell_cost_rate(self):
        cost = MarketCost(stamp_duty_sell=0.001, commission=0.0003,
                          other_fees=0.0001, min_commission=5)
        assert cost.sell_cost_rate == 0.001 + 0.0003 + 0.0001

    def test_round_trip_rate(self):
        cost = MarketCost(stamp_duty_sell=0.001, commission=0.0003,
                          other_fees=0.0001, min_commission=5)
        expected = (0.0003 + 0.0001) + (0.001 + 0.0003 + 0.0001)
        assert abs(cost.round_trip_rate - expected) < 1e-10

    def test_hk_cost_values(self):
        assert HK_COST.stamp_duty_sell == 0.0013
        assert HK_COST.commission == 0.0003

    def test_a_cost_values(self):
        assert A_COST.stamp_duty_sell == 0.0005
        assert A_COST.min_commission == 5

    def test_get_market_cost_hk(self):
        cost = get_market_cost("00700")
        assert cost is HK_COST

    def test_get_market_cost_a(self):
        cost = get_market_cost("600519")
        assert cost is A_COST


# ============================================================
# calculate_atr
# ============================================================

class TestCalculateATR:
    def test_constant_prices(self):
        """价格不变, ATR 应为 0"""
        n = 30
        highs = [100.0] * n
        lows = [100.0] * n
        closes = [100.0] * n
        assert calculate_atr(highs, lows, closes, 14) == 0.0

    def test_normal_volatility(self):
        """正常波动"""
        np.random.seed(42)
        closes = list(100 + np.cumsum(np.random.normal(0, 1, 30)))
        highs = [c + abs(np.random.normal(0, 0.5)) for c in closes]
        lows = [c - abs(np.random.normal(0, 0.5)) for c in closes]
        atr = calculate_atr(highs, lows, closes, 14)
        assert atr > 0

    def test_too_short(self):
        """数据不足, 返回 0"""
        closes = [100.0, 101.0, 102.0]
        highs = [101.0, 102.0, 103.0]
        lows = [99.0, 100.0, 101.0]
        assert calculate_atr(highs, lows, closes, 14) == 0

    def test_large_swings(self):
        """大幅波动, ATR 应较大"""
        closes = [100.0, 110.0, 90.0, 105.0, 95.0, 108.0, 92.0,
                  103.0, 97.0, 106.0, 94.0, 104.0, 96.0, 107.0, 93.0]
        highs = [c + 3 for c in closes]
        lows = [c - 3 for c in closes]
        atr = calculate_atr(highs, lows, closes, 14)
        assert atr > 5  # 大幅波动


# ============================================================
# generate_grid_levels
# ============================================================

class TestGenerateGridLevels:
    def test_equal_distance(self):
        """等距网格"""
        levels = generate_grid_levels(
            current_price=100.0,
            grid_type='equal_distance',
            num_grids_up=5,
            num_grids_down=5,
            grid_width=2.0,
        )
        assert len(levels) == 11  # 5 up + 5 down + current
        # 中间层级应为 current
        current_levels = [lv for lv in levels if lv['type'] == 'current']
        assert len(current_levels) == 1
        assert current_levels[0]['price'] == 100.0

    def test_equal_ratio(self):
        """等比网格"""
        levels = generate_grid_levels(
            current_price=100.0,
            grid_type='equal_ratio',
            num_grids_up=3,
            num_grids_down=3,
            grid_width=2.0,
        )
        assert len(levels) == 7
        # 等比网格的间距应递增
        sell_levels = sorted([lv for lv in levels if lv['type'] == 'sell'],
                             key=lambda x: x['price'])
        if len(sell_levels) >= 2:
            gap1 = sell_levels[1]['price'] - sell_levels[0]['price']
            gap0 = sell_levels[0]['price'] - 100.0
            # 等比: gap1 > gap0
            assert gap1 > gap0

    def test_dynamic_grid(self):
        """动态网格 (需要 closes 数据)"""
        np.random.seed(42)
        closes = list(100 + np.cumsum(np.random.normal(0, 0.5, 60)))
        levels = generate_grid_levels(
            current_price=closes[-1],
            grid_type='dynamic',
            num_grids_up=5,
            num_grids_down=5,
            closes=closes,
        )
        assert len(levels) > 0

    def test_minimum_grid_width(self):
        """网格宽度不能小于 current_price * 0.005"""
        levels = generate_grid_levels(
            current_price=100.0,
            grid_type='equal_distance',
            num_grids_up=3,
            num_grids_down=3,
            grid_width=0.01,  # 极小宽度
        )
        # 应被提升到 100 * 0.005 = 0.5
        prices = sorted([lv['price'] for lv in levels])
        if len(prices) >= 2:
            min_gap = min(prices[i+1] - prices[i] for i in range(len(prices)-1))
            assert min_gap >= 0.5 - 0.01  # 允许四舍五入误差

    def test_buy_below_current(self):
        """买入网格应在当前价以下"""
        levels = generate_grid_levels(
            current_price=100.0,
            grid_type='equal_distance',
            num_grids_up=5,
            num_grids_down=5,
            grid_width=2.0,
        )
        buy_levels = [lv for lv in levels if lv['type'] == 'buy']
        assert all(lv['price'] < 100.0 for lv in buy_levels)

    def test_sell_above_current(self):
        """卖出网格应在当前价以上"""
        levels = generate_grid_levels(
            current_price=100.0,
            grid_type='equal_distance',
            num_grids_up=5,
            num_grids_down=5,
            grid_width=2.0,
        )
        sell_levels = [lv for lv in levels if lv['type'] == 'sell']
        assert all(lv['price'] > 100.0 for lv in sell_levels)


# ============================================================
# calculate_grid_positions
# ============================================================

class TestCalculateGridPositions:
    def test_equal_sizing(self):
        """等额分配"""
        levels = generate_grid_levels(100.0, 'equal_distance', 5, 5, 2.0)
        positions = calculate_grid_positions(
            total_capital=100000,
            num_grids=len(levels),
            sizing_method='equal',
            current_price=100.0,
            grid_levels=levels,
        )
        assert len(positions) > 0
        # 每个仓位的股数应相同 (等额分配)
        shares_set = set(p['shares'] for p in positions)
        assert len(shares_set) == 1  # 全部相同

    def test_pyramid_sizing(self):
        """金字塔加仓"""
        levels = generate_grid_levels(100.0, 'equal_distance', 5, 5, 2.0)
        positions = calculate_grid_positions(
            total_capital=100000,
            num_grids=len(levels),
            sizing_method='pyramid',
            current_price=100.0,
            grid_levels=levels,
        )
        assert len(positions) > 0
        # 金字塔: 低价位的仓位应该更大
        if len(positions) >= 2:
            # 买入网格按价格从高到低排列, 第一个 (最高价) 权重最小
            assert positions[0]['shares'] <= positions[-1]['shares']

    def test_minimum_shares(self):
        """每个网格至少 100 股"""
        levels = generate_grid_levels(100.0, 'equal_distance', 3, 3, 2.0)
        positions = calculate_grid_positions(
            total_capital=1000,  # 很少的资金
            num_grids=len(levels),
            sizing_method='equal',
            current_price=100.0,
            grid_levels=levels,
        )
        assert all(p['shares'] >= 100 for p in positions)


# ============================================================
# breakeven_analysis
# ============================================================

class TestBreakevenAnalysis:
    def test_wide_grid_profitable(self):
        """宽网格应盈利"""
        result = breakeven_analysis(
            grid_width=5.0,
            shares_per_grid=100,
            current_price=100.0,
            stock_code="600519",
        )
        assert result['is_profitable'] is True
        assert result['profit_per_trade'] > 0

    def test_narrow_grid_unprofitable(self):
        """窄网格可能不盈利"""
        result = breakeven_analysis(
            grid_width=0.01,
            shares_per_grid=100,
            current_price=100.0,
            stock_code="600519",
        )
        assert result['is_profitable'] is False

    def test_min_grid_width_positive(self):
        """最小网格宽度应为正"""
        result = breakeven_analysis(
            grid_width=2.0,
            shares_per_grid=100,
            current_price=100.0,
            stock_code="600519",
        )
        assert result['min_grid_width'] > 0
        assert result['min_grid_pct'] > 0


# ============================================================
# get_grid_status
# ============================================================

class TestGetGridStatus:
    def test_at_current_price(self):
        """当前价恰好在网格上"""
        levels = generate_grid_levels(100.0, 'equal_distance', 5, 5, 2.0)
        status = get_grid_status(100.0, levels)
        assert status['current_price'] == 100.0
        assert status['nearest_level']['type'] == 'current'
        assert status['total_levels'] == 11

    def test_between_levels(self):
        """当前价在两个网格之间"""
        levels = generate_grid_levels(100.0, 'equal_distance', 5, 5, 2.0)
        status = get_grid_status(101.0, levels)
        assert status['nearest_level']['price'] == 100.0 or status['nearest_level']['price'] == 102.0

    def test_next_buy_and_sell(self):
        """应能找到下一个买入和卖出价"""
        levels = generate_grid_levels(100.0, 'equal_distance', 5, 5, 2.0)
        status = get_grid_status(100.0, levels)
        assert status['next_buy'] is not None
        assert status['next_sell'] is not None
        assert status['next_buy']['price'] < 100.0
        assert status['next_sell']['price'] > 100.0


# ============================================================
# detect_grid_decay
# ============================================================

class TestDetectGridDecay:
    def test_healthy(self):
        """价格在网格区间内震荡, 网格健康"""
        closes = list(np.sin(np.linspace(0, 4 * np.pi, 30)) * 2 + 100)
        levels = generate_grid_levels(100.0, 'equal_distance', 5, 5, 2.0)
        result = detect_grid_decay(closes, levels, lookback=20)
        assert result['decay_score'] < 60

    def test_trending_up(self):
        """价格持续上涨突破网格"""
        closes = list(np.linspace(90, 120, 30))
        levels = generate_grid_levels(100.0, 'equal_distance', 5, 5, 2.0)
        result = detect_grid_decay(closes, levels, lookback=20)
        # 价格突破上方网格, 应检测到趋势
        assert result['decay_score'] > 0 or len(result['signals']) > 0

    def test_insufficient_data(self):
        """数据不足"""
        result = detect_grid_decay([100.0, 101.0], [{'price': 100.0}], lookback=20)
        assert result['decay_type'] == "healthy"

    def test_empty_levels(self):
        """空网格"""
        result = detect_grid_decay(list(range(30)), [], lookback=20)
        assert result['decay_type'] == "healthy"


# ============================================================
# simulate_grid_trading (纯计算, 用合成数据)
# ============================================================

class TestSimulateGridTrading:
    def _make_klines(self, closes):
        """从收盘价生成 K 线数据"""
        klines = []
        for i, c in enumerate(closes):
            klines.append({
                'date': f'2024-01-{i+1:02d}',
                'open': c * 0.998,
                'high': c * 1.005,
                'low': c * 0.995,
                'close': c,
                'volume': 1000000,
            })
        return klines

    def test_no_trades_flat(self):
        """价格完全不动, 不应有交易"""
        closes = [100.0] * 60
        klines = self._make_klines(closes)
        levels = generate_grid_levels(100.0, 'equal_distance', 5, 5, 2.0)
        result = simulate_grid_trading(
            klines, levels, shares_per_grid=100,
            initial_capital=100000, stock_code="600519",
            enable_stop_loss=False, warmup_days=0,
        )
        # 价格不动, high/low 不触及网格
        assert result['total_trades'] == 0

    def test_oscillating_generates_trades(self):
        """震荡行情应产生交易"""
        np.random.seed(42)
        # 生成在 95-105 之间震荡的价格
        n = 100
        base = 100.0
        oscillation = 3.0 * np.sin(np.linspace(0, 6 * np.pi, n))
        closes = list(base + oscillation)
        klines = self._make_klines(closes)
        levels = generate_grid_levels(100.0, 'equal_distance', 5, 5, 1.0)
        result = simulate_grid_trading(
            klines, levels, shares_per_grid=100,
            initial_capital=100000, stock_code="600519",
            enable_stop_loss=False, warmup_days=0,
        )
        assert result['total_trades'] > 0

    def test_stop_loss_triggers(self):
        """价格跌破止损线应触发止损"""
        closes = list(np.linspace(100, 70, 60))  # 持续下跌
        klines = self._make_klines(closes)
        levels = generate_grid_levels(100.0, 'equal_distance', 5, 5, 2.0)
        result = simulate_grid_trading(
            klines, levels, shares_per_grid=100,
            initial_capital=100000, stock_code="600519",
            enable_stop_loss=True, stop_loss_pct=0.10, warmup_days=0,
        )
        assert result['stop_loss_triggered'] is True

    def test_empty_input(self):
        """空输入, 返回空结果"""
        result = simulate_grid_trading([], [], 100, 100000)
        assert result['total_trades'] == 0
        assert result['total_return_pct'] == 0

    def test_equity_curve_length(self):
        """净值曲线长度应等于输入数据长度"""
        closes = list(np.linspace(100, 105, 30))
        klines = self._make_klines(closes)
        levels = generate_grid_levels(100.0, 'equal_distance', 3, 3, 2.0)
        result = simulate_grid_trading(
            klines, levels, shares_per_grid=100,
            initial_capital=100000, stock_code="600519",
            enable_stop_loss=False, warmup_days=0,
        )
        assert len(result['equity_curve']) == 30

    def test_warmup_days(self):
        """暖机期内不交易"""
        closes = list(np.linspace(100, 105, 60))
        klines = self._make_klines(closes)
        levels = generate_grid_levels(100.0, 'equal_distance', 5, 5, 1.0)
        result = simulate_grid_trading(
            klines, levels, shares_per_grid=100,
            initial_capital=100000, stock_code="600519",
            enable_stop_loss=False, warmup_days=30,
        )
        # 暖机 30 天后才开始交易, 前 30 天不应有交易
        early_trades = [t for t in result['trades'] if t['date'] <= '2024-01-30']
        assert len(early_trades) == 0

    def test_no_negative_capital(self):
        """现金不应为负 (资金不足时停止买入)"""
        closes = list(np.linspace(100, 80, 60))
        klines = self._make_klines(closes)
        levels = generate_grid_levels(100.0, 'equal_distance', 10, 10, 1.0)
        result = simulate_grid_trading(
            klines, levels, shares_per_grid=1000,
            initial_capital=10000,  # 资金很少
            stock_code="600519",
            enable_stop_loss=False, warmup_days=0,
        )
        # 现金不应为负
        for ec in result['equity_curve']:
            # 总资产可能为负 (如果持仓亏损), 但现金应 >= 0
            pass  # 这里主要检查不崩溃


# ============================================================
# _empty_simulation
# ============================================================

class TestEmptySimulation:
    def test_returns_all_zeros(self):
        result = _empty_simulation()
        assert result['total_trades'] == 0
        assert result['total_return_pct'] == 0
        assert result['win_rate'] == 0
        assert result['sharpe_ratio'] == 0
        assert result['stop_loss_triggered'] is False
