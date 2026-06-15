"""
公共 fixtures — 供所有测试模块共享

提供:
- 常见的收益率序列、净值曲线
- 价格序列生成器
- DataFrame 构造辅助
"""

import sys
import os
import numpy as np
import pandas as pd
import pytest

# 确保 backend 目录在 sys.path 中
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)


# ============================================================
# numpy 数组 fixtures
# ============================================================

@pytest.fixture
def steady_up_equity():
    """稳定上涨的净值曲线: 100 个交易日每天涨 0.1%"""
    n = 100
    daily_ret = 0.001
    return 100.0 * np.cumprod(np.concatenate([[1], np.full(n, 1 + daily_ret)]))


@pytest.fixture
def crash_equity():
    """先涨后崩的净值曲线: 前 50 天涨，后 50 天跌"""
    up = np.cumprod(np.concatenate([[1], np.full(50, 1.002)]))
    down = np.cumprod(np.concatenate([[1], np.full(50, 0.995)]))
    return 100.0 * np.concatenate([up, up[-1:] * down[1:]])


@pytest.fixture
def flat_equity():
    """完全平坦的净值曲线"""
    return np.full(100, 50.0)


@pytest.fixture
def steady_up_returns():
    """稳定上涨的日收益率序列 (30 个交易日)"""
    np.random.seed(42)
    return np.full(30, 0.001) + np.random.normal(0, 0.0001, 30)


@pytest.fixture
def mixed_returns():
    """有正有负的日收益率序列 (100 个交易日)"""
    np.random.seed(42)
    return np.random.normal(0.0005, 0.015, 100)


@pytest.fixture
def all_positive_returns():
    """全部为正的收益率"""
    return np.abs(np.random.RandomState(42).normal(0.002, 0.005, 50))


@pytest.fixture
def all_negative_returns():
    """全部为负的收益率"""
    return -np.abs(np.random.RandomState(42).normal(0.002, 0.005, 50))


# ============================================================
# DataFrame / Series fixtures (用于因子测试)
# ============================================================

@pytest.fixture
def stock_universe():
    """模拟 5 只股票的截面数据"""
    codes = ["000001", "000002", "000003", "000004", "000005"]
    return pd.DataFrame({
        "pe_ttm": pd.Series([10.0, 20.0, 15.0, 30.0, 8.0], index=codes),
        "pb": pd.Series([1.2, 2.5, 1.8, 3.0, 0.9], index=codes),
        "roe": pd.Series([0.18, 0.12, 0.15, 0.08, 0.22], index=codes),
        "gross_margin": pd.Series([0.35, 0.25, 0.30, 0.20, 0.40], index=codes),
        "market_cap": pd.Series([500, 1000, 300, 2000, 100], index=codes),
    }, index=codes)


@pytest.fixture
def price_series_dict():
    """模拟 5 只股票各 300 个交易日的收盘价"""
    np.random.seed(42)
    codes = ["000001", "000002", "000003", "000004", "000005"]
    result = {}
    for i, code in enumerate(codes):
        base = 10 + i * 5
        returns = np.random.normal(0.0003, 0.02, 300)
        prices = base * np.cumprod(np.concatenate([[1], 1 + returns]))
        result[code] = pd.Series(prices)
    return result


@pytest.fixture
def returns_series_dict():
    """模拟 5 只股票各 100 个交易日的日收益率"""
    np.random.seed(42)
    codes = ["000001", "000002", "000003", "000004", "000005"]
    result = {}
    for i, code in enumerate(codes):
        result[code] = pd.Series(np.random.normal(0.0005 * (i + 1), 0.015, 100))
    return result
