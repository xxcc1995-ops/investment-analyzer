"""
网格交易服务 — 专业级网格交易引擎
===================================

核心功能：
1. 自动生成网格价格（等距/等比两种模式）
2. 历史回测模拟（模拟过去一段时间如果用网格策略会赚多少）
3. 风险指标计算（夏普比率、最大回撤等专业指标）
4. 盈亏平衡分析（网格宽度是否能覆盖交易成本）
5. 参数优化（自动扫描最优网格参数组合）

支持市场：A股、港股（自动识别）

什么是网格交易？
  网格交易就像在价格区间里织一张"网"：
  - 把资金分成N份，每份对应一个价格"格子"
  - 价格每跌到一个格子就买一份，每涨到上一个格子就卖一份
  - 在震荡市中反复低买高卖，赚取差价
  - 适合长期横盘、上下波动的股票
"""

import time
import math
import logging
import requests
import statistics
import random
import json
import os
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)
from datetime import datetime, timedelta
from dataclasses import dataclass

# ============================================================
# 缓存设置 — 避免重复请求同一个股票的数据
# ============================================================
# 缓存600秒（10分钟），因为网格分析不需要实时更新

from app.core.cache import get_cache as _base_get_cache, set_cache as _set_cached
_CACHE_TTL = 600  # 缓存有效期：600秒

def _get_cached(key: str):
    """从缓存中获取数据，如果缓存过期则返回None"""
    return _base_get_cache(key, ttl_seconds=_CACHE_TTL)


# ============================================================
# 市场识别 — 自动判断股票是A股还是港股
# ============================================================

def _is_hk_code(code: str) -> bool:
    """
    判断股票代码是否为港股

    规则：
    - 港股代码是5位数字（如 00700 = 腾讯）
    - A股代码是6位数字（如 600519 = 贵州茅台）

    参数：
        code: 股票代码字符串
    返回：
        True = 港股，False = A股
    """
    clean = code.strip()
    return len(clean) == 5 and clean.isdigit()


# ============================================================
# 交易成本模型 — 不同市场的手续费结构
# ============================================================

@dataclass
class MarketCost:
    """
    交易成本数据类 — 记录一次买卖需要花多少手续费

    为什么要关心交易成本？
      网格交易靠频繁买卖赚差价，如果手续费太高，可能赚的钱还不够交手续费。
      所以必须先算清楚成本，再决定网格宽度。

    字段说明：
        stamp_duty_sell: 印花税（只有卖出时收取）
        commission: 佣金（买卖都收）
        other_fees: 其他费用（征费、过户费等）
        min_commission: 最低佣金（不足此金额按此金额收）
    """
    stamp_duty_sell: float    # 印花税（卖方收取）
    commission: float         # 佣金费率（双向）
    other_fees: float         # 其他杂费
    min_commission: float     # 最低佣金（元）

    @property
    def buy_cost_rate(self) -> float:
        """买入时的总费率 = 佣金 + 其他费用"""
        return self.commission + self.other_fees

    @property
    def sell_cost_rate(self) -> float:
        """卖出时的总费率 = 印花税 + 佣金 + 其他费用"""
        return self.stamp_duty_sell + self.commission + self.other_fees

    @property
    def round_trip_rate(self) -> float:
        """一次完整买卖（买+卖）的总费率"""
        return self.buy_cost_rate + self.sell_cost_rate


# 港股交易成本（2024年标准）
HK_COST = MarketCost(
    stamp_duty_sell=0.0013,   # 印花税 0.13%（卖方）
    commission=0.0003,        # 佣金 0.03%（常见券商费率）
    other_fees=0.0000565,     # 交易征费+交收费等
    min_commission=0,         # 港股一般无最低佣金
)

# A股交易成本（2024年标准）
A_COST = MarketCost(
    stamp_duty_sell=0.0005,   # 印花税 0.05%（卖方，2023年减半后）
    commission=0.00025,       # 佣金 0.025%（万2.5，常见费率）
    other_fees=0.00001,       # 过户费 0.001%（上海）
    min_commission=5,         # 最低佣金5元
)


def get_market_cost(code: str) -> MarketCost:
    """
    根据股票代码获取对应的交易成本

    参数：
        code: 股票代码
    返回：
        MarketCost 对象，包含该市场的所有费率
    """
    return HK_COST if _is_hk_code(code) else A_COST


# ============================================================
# 历史数据获取 — 从网络获取股票的历史价格
# ============================================================

def _fetch_hk_historical(code: str = '00700', days: int = 252) -> list[dict]:
    """
    获取港股历史K线数据（日线）

    数据来源：腾讯财经API（web.ifzq.gtimg.cn）
    返回格式：[{date, open, high, low, close, volume}, ...]

    参数：
        code: 港股代码（如 '00700'）
        days: 获取最近多少个交易日的数据（默认252个，约1年）
    返回：
        包含每日OHLCV数据的列表，按日期从旧到新排列
    """
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days + 30)).strftime('%Y-%m-%d')
        url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
        params = {'param': f'hk{code},day,{start_date},{end_date},{days + 30},qfq'}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if 'data' in data and f'hk{code}' in data['data']:
            klines = data['data'][f'hk{code}']
            rows = klines.get('qfqday') or klines.get('day') or []
            records = []
            for row in rows:
                if len(row) >= 6:
                    records.append({
                        'date': str(row[0]),
                        'open': float(row[1]),
                        'high': float(row[3]),   # 腾讯格式：开、收、高、低
                        'low': float(row[4]),
                        'close': float(row[2]),
                        'volume': float(row[5]),
                    })
            return records
    except Exception as e:
        logger.warning(f"历史行情获取失败: {e}")
    return []


def _fetch_a_historical(code: str = '600519', days: int = 252) -> list[dict]:
    """
    获取A股历史K线数据（日线，前复权）

    数据来源：腾讯财经API（与港股共用同一个API，只是symbol格式不同）
    前复权(qfq)：除权除息后的价格，使历史价格具有可比性

    参数：
        code: A股代码（如 '600519'）
        days: 获取最近多少个交易日的数据
    返回：
        包含每日OHLCV数据的列表
    """
    try:
        # A股symbol规则：6开头是上海（sh），其他是深圳（sz）
        symbol = f'sh{code}' if code.startswith('6') else f'sz{code}'
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days + 30)).strftime('%Y-%m-%d')
        url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
        params = {'param': f'{symbol},day,{start_date},{end_date},{days + 30},qfq'}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if 'data' in data and symbol in data['data']:
            klines = data['data'][symbol]
            rows = klines.get('qfqday') or klines.get('day') or []
            records = []
            for row in rows:
                if len(row) >= 6:
                    records.append({
                        'date': str(row[0]),
                        'open': float(row[1]),
                        'high': float(row[3]),
                        'low': float(row[4]),
                        'close': float(row[2]),
                        'volume': float(row[5]),
                    })
            return records
    except Exception as e:
        logger.warning(f"历史行情获取失败: {e}")
    return []


def _fetch_historical(code: str, days: int = 252) -> list[dict]:
    """
    统一的历史数据获取入口 — 自动识别A股/港股

    参数：
        code: 股票代码（自动判断市场）
        days: 获取天数
    返回：
        历史K线数据列表
    """
    if _is_hk_code(code):
        return _fetch_hk_historical(code, days)
    else:
        return _fetch_a_historical(code, days)


def _get_stock_data(code: str) -> Optional[dict]:
    """
    统一的实时行情获取入口 — 自动识别A股/港股

    返回格式：
        {
            'name': '股票名称',
            'price': 当前价格,
            'change_pct': 涨跌幅(%),
            'market': 'A' 或 'HK'
        }
    """
    if _is_hk_code(code):
        # 港股：从vi_service获取
        from app.services.vi_service import _get_hk_stock_data
        data = _get_hk_stock_data(code)
        if data:
            data['market'] = 'HK'
        return data
    else:
        # A股：从multi_source_quote获取
        try:
            from app.services.multi_source_quote import multi_source_service
            quote = multi_source_service.get_quote(code, market='A')
            if quote and quote.get('price'):
                return {
                    'name': quote.get('name', code),
                    'price': quote['price'],
                    'change_pct': quote.get('change_pct', 0),
                    'market': 'A',
                }
        except Exception as e:
            logger.warning(f"股票数据获取失败: {e}")
        return None


# ============================================================
# ATR（平均真实波幅）— 衡量股票波动程度的指标
# ============================================================

def calculate_atr(highs: list[float], lows: list[float],
                  closes: list[float], period: int = 14) -> float:
    """
    计算ATR（Average True Range，平均真实波幅）

    什么是ATR？
      ATR衡量的是股票每天的波动幅度。ATR越大，说明股票波动越剧烈。
      在网格交易中，ATR用来决定网格的宽度：
      - ATR太小 → 网格太窄 → 利润被手续费吃掉
      - ATR太大 → 网格太宽 → 资金闲置效率低

    计算方法（Wilder平滑法）：
      1. True Range = max(当日最高-最低, |当日最高-昨日收盘|, |当日最低-昨日收盘|)
      2. ATR = 前N天True Range的指数移动平均

    参数：
        highs: 每日最高价列表
        lows: 每日最低价列表
        closes: 每日收盘价列表
        period: 计算周期（默认14天，是技术分析的标准参数）
    返回：
        ATR值（价格单位）
    """
    # 数据不够时无法计算
    if len(closes) < period + 1:
        return 0

    # 第一步：计算每天的True Range（真实波幅）
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],           # 当日最高 - 当日最低
            abs(highs[i] - closes[i - 1]), # 当日最高 - 昨日收盘
            abs(lows[i] - closes[i - 1])   # 当日最低 - 昨日收盘
        )
        trs.append(tr)

    if len(trs) < period:
        return sum(trs) / len(trs) if trs else 0

    # 第二步：用Wilder平滑法计算ATR
    # 先用前period天的简单平均作为初始ATR
    atr = sum(trs[:period]) / period
    # 然后用指数移动平均公式：ATR = (前ATR × (N-1) + 今日TR) / N
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period

    return round(atr, 4)


# ============================================================
# 网格生成 — 在当前价格上下生成等距或等比的价格格子
# ============================================================

def generate_grid_levels(
    current_price: float,
    grid_type: str = 'equal_distance',
    num_grids_up: int = 10,
    num_grids_down: int = 10,
    grid_width: float = None,
    atr: float = None,
    atr_multiplier: float = 1.0,
    highs: list[float] = None,
    lows: list[float] = None,
    closes: list[float] = None,
) -> list[dict]:
    """
    生成网格价格层级

    什么是网格层级？
      以当前价格为中心，向上和向下各画N条水平线，
      每条线就是一个"网格层级"。价格触及某条线时触发买入或卖出。

    三种网格类型：
      1. 等距网格（equal_distance）：每条线之间的距离相等
         适合：价格在窄幅区间震荡的股票
         公式：Level[i] = 当前价 + i × 网格宽度

      2. 等比网格（equal_ratio）：每条线之间的比例相等
         适合：价格波动较大的股票（低价时波动小，高价时波动大）
         公式：Level[i] = 当前价 × (1 + 比率)^i

      3. 动态网格（dynamic）：基于布林带自适应，波动大时网格宽，波动小时网格窄
         适合：波动率变化较大的股票
         公式：上下界 = MA ± k × STD，网格宽度 = 2 × k × STD / 总格数

    参数：
        current_price: 当前股票价格
        grid_type: 'equal_distance'(等距), 'equal_ratio'(等比), 'dynamic'(动态)
        num_grids_up: 向上生成几个网格（卖出区域）
        num_grids_down: 向下生成几个网格（买入区域）
        grid_width: 手动指定网格宽度（价格单位），None则用ATR自动计算
        atr: ATR值，用于自动计算网格宽度
        atr_multiplier: ATR倍数（默认1.0，即网格宽度=ATR）
        highs: 最高价序列（动态网格需要）
        lows: 最低价序列（动态网格需要）
        closes: 收盘价序列（动态网格需要）
    返回：
        网格层级列表，每个元素包含：price(价格), index(序号),
        distance_pct(距现价百分比), type(buy/sell/current)
    """
    # 确定网格宽度
    if grid_width is None and atr is not None:
        grid_width = atr * atr_multiplier  # 用ATR自动计算
    elif grid_width is None:
        grid_width = current_price * 0.02  # 默认：当前价的2%

    # 最小网格宽度保护：不能小于当前价的0.5%
    # 太窄的话，利润会被手续费吃掉
    grid_width = max(grid_width, current_price * 0.005)

    levels = []  # 存储所有网格层级

    if grid_type == 'dynamic' and closes and len(closes) >= 20:
        # ===== 动态网格（布林带自适应）=====
        # 用最近60天的收盘价计算均值和标准差
        lookback = min(60, len(closes))
        recent = closes[-lookback:]
        ma = sum(recent) / len(recent)
        std = math.sqrt(sum((x - ma) ** 2 for x in recent) / len(recent))
        # 布林带上下界：MA ± 2×STD
        upper = ma + 2 * std
        lower = ma - 2 * std
        # 确保下界为正
        lower = max(lower, current_price * 0.5)
        # 如果当前价不在布林带内，以当前价为中心重新调整
        if current_price > upper or current_price < lower:
            upper = current_price + 2 * std
            lower = current_price - 2 * std
            lower = max(lower, current_price * 0.5)
        total_grids = num_grids_up + num_grids_down
        grid_step = (upper - lower) / total_grids if total_grids > 0 else grid_width
        grid_step = max(grid_step, current_price * 0.005)  # 最小保护

        for i in range(-num_grids_down, num_grids_up + 1):
            price = round(current_price + i * grid_step, 2)
            if price <= 0:
                continue
            level_type = 'buy' if i < 0 else ('sell' if i > 0 else 'current')
            levels.append({
                'price': price,
                'index': i,
                'distance_pct': round((price - current_price) / current_price * 100, 2),
                'type': level_type,
            })
    elif grid_type == 'equal_distance':
        # ===== 等距网格 =====
        # 每个格子的宽度相同，像尺子上的刻度
        base = current_price
        for i in range(-num_grids_down, num_grids_up + 1):
            price = round(base + i * grid_width, 2)
            if price <= 0:
                continue  # 价格不能为负
            # i<0 是买入区域（价格低于现价），i>0 是卖出区域
            level_type = 'buy' if i < 0 else ('sell' if i > 0 else 'current')
            levels.append({
                'price': price,
                'index': i,
                'distance_pct': round((price - current_price) / current_price * 100, 2),
                'type': level_type,
            })
    else:
        # ===== 等比网格 =====
        # 每个格子之间的比例相同，像对数刻度
        # ratio = 1 + (网格宽度/当前价)，这样等比网格在当前价附近近似等距
        ratio = 1 + (grid_width / current_price)
        base = current_price
        for i in range(-num_grids_down, num_grids_up + 1):
            price = round(base * (ratio ** i), 2)
            if price <= 0:
                continue
            level_type = 'buy' if i < 0 else ('sell' if i > 0 else 'current')
            levels.append({
                'price': price,
                'index': i,
                'distance_pct': round((price - current_price) / current_price * 100, 2),
                'type': level_type,
            })

    return levels


# ============================================================
# 仓位计算 — 每个格子买多少股
# ============================================================

def calculate_grid_positions(total_capital: float, num_grids: int,
                             sizing_method: str = 'equal',
                             current_price: float = 100,
                             grid_levels: list[dict] = None) -> list[dict]:
    """
    计算每个网格层级的仓位大小（买多少股）

    两种仓位分配方法：
      1. 等额分配（equal）：每个格子分配相同的资金
         优点：简单易懂
         缺点：低价时买到的股数少，高价时买到的股数多（不太合理）

      2. 金字塔加仓（pyramid）：低价的格子分配更多资金
         优点：越跌越买，降低平均成本
         缺点：需要更多总资金

    参数：
        total_capital: 总投入资金
        num_grids: 网格总数
        sizing_method: 'equal'(等额) 或 'pyramid'(金字塔)
        current_price: 当前价格（用于计算股数）
        grid_levels: 网格层级列表（金字塔模式需要，用于按实际价格计算股数）
    返回：
        仓位列表，每个元素包含：shares(股数), capital(资金), level_price(对应网格价格)
    """
    # 提取买入网格的价格（type=='buy'的层级），按价格从高到低排列
    buy_levels = []
    if grid_levels:
        buy_levels = sorted(
            [lv for lv in grid_levels if lv.get('type') == 'buy'],
            key=lambda x: x['price'], reverse=True  # 高价在前
        )

    if sizing_method == 'equal':
        # ===== 等额分配 =====
        # 重要：资金只分配给买入网格，不能除以总网格数（含卖出网格）
        num_buy_levels = len(buy_levels) if buy_levels else num_grids
        capital_per_grid = total_capital / max(num_buy_levels, 1)
        if buy_levels:
            # 按每个网格的实际价格计算股数
            positions = []
            for lv in buy_levels:
                price = lv['price']
                shares = int(capital_per_grid / price / 100) * 100
                shares = max(shares, 100)  # 最少1手
                positions.append({
                    'method': 'equal', 'shares': shares,
                    'capital': round(shares * price, 2),
                    'level_price': price,
                })
            return positions
        else:
            shares_per_grid = int(capital_per_grid / current_price / 100) * 100
            shares_per_grid = max(shares_per_grid, 100)
            return [{'method': 'equal', 'shares': shares_per_grid,
                     'capital': round(shares_per_grid * current_price, 2),
                     'level_price': current_price}] * num_grids
    else:
        # ===== 金字塔加仓 =====
        # 越低价的格子分配越多资金（降低平均成本）
        # 买入网格按价格从高到低排列，权重从1递增
        target_levels = buy_levels if buy_levels else [{'price': current_price}] * num_grids
        num_buy = len(target_levels)
        weights = list(range(1, num_buy + 1))  # [1, 2, 3, ..., N]
        total_weight = sum(weights)
        positions = []
        for i, lv in enumerate(target_levels):
            price = lv['price'] if isinstance(lv, dict) else lv
            weight = weights[i]  # 高价网格权重小(1)，低价网格权重大(N)
            capital = total_capital * weight / total_weight
            shares = int(capital / price / 100) * 100
            shares = max(shares, 100)
            positions.append({
                'method': 'pyramid', 'shares': shares,
                'capital': round(shares * price, 2),
                'level_price': price,
            })
        return positions


# ============================================================
# 回测模拟 — 用历史数据模拟网格交易策略的表现
# ============================================================

def simulate_grid_trading(
    historical_prices: list[dict],
    grid_levels: list[dict],
    shares_per_grid: int,
    initial_capital: float,
    trading_cost: MarketCost = None,
    stock_code: str = '',
    stop_loss_pct: float = 0.10,
    enable_stop_loss: bool = True,
    warmup_days: int = 20,
) -> dict:
    """
    网格交易历史回测模拟（机构级）

    核心算法：用过去的价格数据，模拟如果执行网格策略会怎样。

    工作原理：
      逐日遍历历史数据，每天检查：
      1. 价格是否跌到了某个网格的买入价？→ 买入（盘中触及即触发）
      2. 价格是否涨到下一个网格层级？→ 卖出获利
      3. 是否触发了止损？→ 清仓并停止交易

    资金追踪方式：
      直接追踪 cash（现金余额），确保资金计算准确：
      - 买入时：cash -= (股数 × 价格 + 买入手续费)
      - 卖出时：cash += (股数 × 价格 - 卖出手续费)
      - 总资产 = cash + 持仓市值

    参数：
        historical_prices: 历史K线数据 [{date, open, high, low, close, volume}]
        grid_levels: 网格层级列表
        shares_per_grid: 每个网格买入的股数
        initial_capital: 初始总资金
        trading_cost: 交易成本配置
        stock_code: 股票代码（用于确定交易成本）
        stop_loss_pct: 止损比例（默认10%）
        enable_stop_loss: 是否启用止损
        warmup_days: 暖机天数（前N天不交易，用于指标预热）
    返回：
        回测结果字典，包含交易记录、盈亏、风险指标等
    """
    # 数据校验
    if not historical_prices or not grid_levels:
        return _empty_simulation()

    # 确定交易成本
    if trading_cost is None:
        trading_cost = get_market_cost(stock_code)

    # 提取所有买入网格价格并排序（从低到高）
    buy_level_prices = sorted([lv['price'] for lv in grid_levels if lv.get('type') == 'buy'])

    # 构建卖出目标映射：每个买入网格 → 对应的卖出网格（上一格）
    # 这样无论等距还是等比网格，卖出目标都是正确的下一个层级
    all_level_prices = sorted([lv['price'] for lv in grid_levels])
    sell_target_map = {}
    for i, price in enumerate(all_level_prices):
        if i < len(all_level_prices) - 1:
            sell_target_map[price] = all_level_prices[i + 1]

    # 也用全局网格宽度作为后备（对于不在映射中的价格）
    grid_width = all_level_prices[1] - all_level_prices[0] if len(all_level_prices) > 1 else 0

    # 止损价 = 最下方网格价格 × (1 - 止损比例)
    lowest_grid = all_level_prices[0] if all_level_prices else 0
    stop_loss_price = lowest_grid * (1 - stop_loss_pct) if enable_stop_loss else 0

    # 跟踪状态
    positions = {}        # 当前持仓 {网格价格: {shares, entry_price, buy_fee}}
    trades = []           # 所有交易记录
    cash = initial_capital  # 当前现金（核心：直接追踪现金，避免累积误差）
    equity_curve = []     # 每天的总资产曲线
    peak_equity = initial_capital  # 历史最高资产（用于计算回撤）
    max_drawdown = 0      # 最大回撤
    stop_loss_triggered = False  # 是否已触发止损
    consecutive_losses = 0       # 当前连续亏损次数
    max_consecutive_losses = 0   # 最大连续亏损次数
    total_fees_paid = 0   # 累计手续费

    for day_idx, day in enumerate(historical_prices):
        low, high, close = day['low'], day['high'], day['close']

        # 暖机期：不交易，只记录资产曲线
        if day_idx < warmup_days:
            position_value = sum(p['shares'] * close for p in positions.values())
            total_equity = cash + position_value
            equity_curve.append({'date': day['date'], 'equity': round(total_equity, 2)})
            continue

        # ===== 止损检查 =====
        # 价格跌破止损线 → 清仓并停止后续交易
        if enable_stop_loss and not stop_loss_triggered and low <= stop_loss_price and positions:
            for lv in list(positions.keys()):
                pos = positions[lv]
                sell_price = stop_loss_price  # 按止损价卖出
                revenue = pos['shares'] * sell_price
                fee = revenue * trading_cost.sell_cost_rate
                if not _is_hk_code(stock_code):
                    fee = max(fee, A_COST.min_commission)
                pnl = (sell_price - pos['entry_price']) * pos['shares'] - fee - pos.get('buy_fee', 0)
                cash += revenue - fee  # 卖出回款
                total_fees_paid += fee
                trades.append({
                    'date': day['date'], 'action': 'stop_loss',
                    'price': sell_price, 'level': lv,
                    'shares': pos['shares'],
                    'pnl': round(pnl, 2),
                    'cost': round(fee, 2),
                })
                consecutive_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
            positions.clear()
            stop_loss_triggered = True

        # 止损后不再交易，但继续记录资产曲线
        if stop_loss_triggered:
            position_value = sum(p['shares'] * close for p in positions.values())
            total_equity = cash + position_value
            equity_curve.append({'date': day['date'], 'equity': round(total_equity, 2)})
            peak_equity = max(peak_equity, total_equity)
            drawdown = (peak_equity - total_equity) / peak_equity * 100 if peak_equity > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)
            continue

        # ===== 买入信号 =====
        for level in buy_level_prices:
            # 条件：该网格未持仓 + 盘中价格触及该网格
            # 买入条件放宽：只要 low <= level <= high 即可（盘中触及即成交）
            if level not in positions and low <= level <= high:
                cost = shares_per_grid * level
                fee = cost * trading_cost.buy_cost_rate
                if not _is_hk_code(stock_code):
                    fee = max(fee, A_COST.min_commission)
                # 检查资金是否足够
                if cost + fee <= cash:
                    positions[level] = {
                        'shares': shares_per_grid,
                        'entry_price': level,
                        'buy_fee': fee,  # 记录买入手续费，卖出时计算真实盈亏
                    }
                    cash -= (cost + fee)  # 扣除现金
                    total_fees_paid += fee
                    trades.append({
                        'date': day['date'], 'action': 'buy',
                        'price': level, 'level': level,
                        'shares': shares_per_grid,
                        'cost': round(cost + fee, 2),
                        'pnl': 0,
                    })

        # ===== 卖出信号 =====
        # 使用正确的卖出目标：下一个网格层级（而非固定的grid_width）
        for level in sorted(positions.keys(), reverse=True):
            # 卖出目标价 = 映射中的下一个网格层级
            sell_target = sell_target_map.get(level, level + grid_width)
            if high >= sell_target:
                pos = positions[level]
                sell_price = sell_target
                revenue = pos['shares'] * sell_price
                fee = revenue * trading_cost.sell_cost_rate
                if not _is_hk_code(stock_code):
                    fee = max(fee, A_COST.min_commission)
                # 真实盈亏 = 卖出收入 - 买入成本 - 买入手续费 - 卖出手续费
                pnl = (sell_price - pos['entry_price']) * pos['shares'] - fee - pos.get('buy_fee', 0)
                cash += revenue - fee  # 卖出回款
                total_fees_paid += fee
                del positions[level]
                trades.append({
                    'date': day['date'], 'action': 'sell',
                    'price': sell_price, 'level': level,
                    'shares': pos['shares'],
                    'revenue': round(revenue - fee, 2),
                    'pnl': round(pnl, 2),
                })
                # 连续亏损统计
                if pnl < 0:
                    consecutive_losses += 1
                    max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
                else:
                    consecutive_losses = 0

        # ===== 记录每日资产 =====
        # 总资产 = 现金 + 持仓市值（简洁准确的计算方式）
        position_value = sum(p['shares'] * close for p in positions.values())
        total_equity = cash + position_value
        equity_curve.append({'date': day['date'], 'equity': round(total_equity, 2)})

        # 计算回撤（从历史最高点下跌了多少百分比）
        peak_equity = max(peak_equity, total_equity)
        drawdown = (peak_equity - total_equity) / peak_equity * 100 if peak_equity > 0 else 0
        max_drawdown = max(max_drawdown, drawdown)

    # ===== 汇总统计 =====
    num_buys = len([t for t in trades if t['action'] == 'buy'])
    num_sells = len([t for t in trades if t['action'] == 'sell'])
    num_stop_loss = len([t for t in trades if t['action'] == 'stop_loss'])
    # 胜率只计算正常卖出（不含止损）
    winning_trades = len([t for t in trades if t['action'] == 'sell' and t.get('pnl', 0) > 0])
    losing_trades = [t for t in trades if t['action'] == 'sell' and t.get('pnl', 0) < 0]
    win_rate = round(winning_trades / num_sells * 100, 1) if num_sells > 0 else 0

    # 盈亏比：平均盈利 / 平均亏损的绝对值
    avg_win = (sum(t['pnl'] for t in trades if t['action'] == 'sell' and t.get('pnl', 0) > 0)
               / winning_trades) if winning_trades > 0 else 0
    avg_loss = abs(sum(t['pnl'] for t in losing_trades) / len(losing_trades)) if losing_trades else 0
    profit_loss_ratio = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0

    # 未实现盈亏（还持有的仓位）
    last_price = historical_prices[-1]['close'] if historical_prices else 0
    unrealized = sum((last_price - p['entry_price']) * p['shares'] for p in positions.values())

    # 已实现盈亏 = 卖出的所有盈亏之和
    realized_pnl = sum(t.get('pnl', 0) for t in trades if t['action'] in ('sell', 'stop_loss'))

    total_return = round((realized_pnl + unrealized) / initial_capital * 100, 2)

    # 计算波动率和夏普比率
    sharpe = 0
    sortino = 0
    annual_vol = 0
    annual_return = 0
    if len(equity_curve) > 1:
        daily_returns = []
        for i in range(1, len(equity_curve)):
            prev = equity_curve[i-1]['equity']
            curr = equity_curve[i]['equity']
            if prev > 0:
                daily_returns.append((curr - prev) / prev)
        if daily_returns:
            avg_return = sum(daily_returns) / len(daily_returns)
            variance = sum((r - avg_return)**2 for r in daily_returns) / len(daily_returns)
            daily_vol = math.sqrt(variance)
            annual_vol = daily_vol * math.sqrt(252)
            risk_free_rate = 0.02
            annual_return = (1 + total_return/100) ** (252/max(len(daily_returns),1)) - 1 if total_return > -100 else -1
            sharpe = round((annual_return - risk_free_rate) / annual_vol, 2) if annual_vol > 0 else 0
            downside_returns = [r for r in daily_returns if r < 0]
            if downside_returns:
                downside_var = sum(r**2 for r in downside_returns) / len(downside_returns)
                downside_vol = math.sqrt(downside_var) * math.sqrt(252)
                sortino = round((annual_return - risk_free_rate) / downside_vol, 2) if downside_vol > 0 else 0
            else:
                sortino = 0

    # 卡尔玛比率 = 年化收益 / 最大回撤
    calmar = round(annual_return / (max_drawdown/100), 2) if max_drawdown > 0 and total_return > -100 else 0

    # 资金使用效率 = 平均持仓市值 / 初始资金
    if equity_curve:
        avg_equity = sum(e['equity'] for e in equity_curve) / len(equity_curve)
        avg_capital_used = (avg_equity - cash) / initial_capital * 100 if initial_capital > 0 else 0
    else:
        avg_capital_used = 0

    return {
        'trades': trades[-50:],  # 只返回最近50笔交易（避免数据太大）
        'total_trades': len(trades),
        'num_buys': num_buys,
        'num_sells': num_sells,
        'num_stop_loss': num_stop_loss,
        'realized_pnl': round(realized_pnl, 2),
        'unrealized_pnl': round(unrealized, 2),
        'total_pnl': round(realized_pnl + unrealized, 2),
        'total_return_pct': total_return,
        'win_rate': win_rate,
        'profit_loss_ratio': profit_loss_ratio,
        'max_drawdown': round(max_drawdown, 2),
        'sharpe_ratio': sharpe,
        'sortino_ratio': sortino,
        'calmar_ratio': calmar,
        'annual_volatility': round(annual_vol * 100, 2),
        'max_consecutive_losses': max_consecutive_losses,
        'capital_utilization': round(avg_capital_used, 1),
        'total_fees_paid': round(total_fees_paid, 2),
        'equity_curve': equity_curve,
        'open_positions': len(positions),
        'position_details': [
            {'level': lv, 'shares': pos['shares'], 'entry': pos['entry_price'],
             'unrealized': round((last_price - pos['entry_price']) * pos['shares'], 2)}
            for lv, pos in positions.items()
        ],
        'stop_loss_triggered': stop_loss_triggered,
    }


def _empty_simulation() -> dict:
    """返回空的回测结果（当没有数据时使用）"""
    return {
        'trades': [], 'total_trades': 0, 'num_buys': 0, 'num_sells': 0,
        'num_stop_loss': 0, 'realized_pnl': 0, 'unrealized_pnl': 0,
        'total_pnl': 0, 'total_return_pct': 0, 'win_rate': 0,
        'profit_loss_ratio': 0, 'max_drawdown': 0, 'sharpe_ratio': 0,
        'sortino_ratio': 0, 'calmar_ratio': 0, 'annual_volatility': 0,
        'max_consecutive_losses': 0, 'capital_utilization': 0,
        'total_fees_paid': 0,
        'equity_curve': [], 'open_positions': 0, 'position_details': [],
        'stop_loss_triggered': False,
    }


# ============================================================
# 网格状态 — 当前价格在网格中的位置
# ============================================================

def get_grid_status(current_price: float, grid_levels: list[dict]) -> dict:
    """
    获取当前价格在网格中的位置状态

    告诉用户：
    - 当前价最近的网格是哪个？
    - 下一个买入触发价是多少？
    - 下一个卖出触发价是多少？
    """
    # 找到距离当前价最近的网格
    nearest_level = None
    min_dist = float('inf')
    for lv in grid_levels:
        dist = abs(lv['price'] - current_price)
        if dist < min_dist:
            min_dist = dist
            nearest_level = lv

    # 找下一个买入触发价（从高到低，找第一个低于现价的）
    buy_levels = sorted([lv for lv in grid_levels if lv['type'] == 'buy'],
                        key=lambda x: x['price'], reverse=True)
    # 找下一个卖出触发价（从低到高，找第一个高于现价的）
    sell_levels = sorted([lv for lv in grid_levels if lv['type'] == 'sell'],
                         key=lambda x: x['price'])

    next_buy = buy_levels[0] if buy_levels else None
    next_sell = sell_levels[0] if sell_levels else None

    return {
        'current_price': current_price,
        'nearest_level': nearest_level,
        'next_buy': next_buy,
        'next_sell': next_sell,
        'total_levels': len(grid_levels),
        'buy_levels': len(buy_levels),
        'sell_levels': len(sell_levels),
    }


# ============================================================
# 盈亏平衡分析 — 网格宽度是否能覆盖交易成本
# ============================================================

def breakeven_analysis(grid_width: float, shares_per_grid: int,
                       current_price: float,
                       trading_cost: MarketCost = None,
                       stock_code: str = '') -> dict:
    """
    盈亏平衡分析 — 计算最小盈利网格宽度

    为什么要算这个？
      网格交易赚的是每个格子的差价，但如果差价太小，
      赚的钱还不够交手续费，那就白忙活了。
      所以必须确保：网格宽度 > 交易成本

    参数：
        grid_width: 当前网格宽度（价格单位）
        shares_per_grid: 每格股数
        current_price: 当前价格
        trading_cost: 交易成本配置
        stock_code: 股票代码
    """
    if trading_cost is None:
        trading_cost = get_market_cost(stock_code)

    # 一次完整买卖（买+卖）的每股成本
    cost_per_share = current_price * trading_cost.round_trip_rate
    # A股最低佣金分摊
    if not _is_hk_code(stock_code) and shares_per_grid > 0:
        min_cost_per_share = A_COST.min_commission * 2 / shares_per_grid
        cost_per_share = max(cost_per_share, min_cost_per_share)

    min_grid_width = cost_per_share  # 最小网格宽度 = 至少能覆盖成本
    min_grid_pct = round(cost_per_share / current_price * 100, 2)

    # 每格利润 = (网格宽度 - 每股成本) × 股数
    profit_per_trade = (grid_width - cost_per_share) * shares_per_grid

    return {
        'min_grid_width': round(min_grid_width, 2),
        'min_grid_pct': min_grid_pct,
        'current_grid_width': round(grid_width, 2),
        'current_grid_pct': round(grid_width / current_price * 100, 2),
        'profit_per_trade': round(profit_per_trade, 2),
        'is_profitable': grid_width > min_grid_width,
        'trading_cost_per_share': round(cost_per_share, 4),
    }


# ============================================================
# 参数优化 — 自动扫描最优网格参数
# ============================================================

def optimize_parameters(
    stock_code: str,
    total_capital: float = 1000000,
    hist_days: int = 252,
) -> dict:
    """
    网格参数优化 — 扫描不同参数组合，找出最优配置

    扫描维度：
      1. 网格宽度：1%, 1.5%, 2%, 2.5%, 3%, 4%, 5%
      2. 网格数量：8, 10, 12, 15, 20
      3. 仓位方法：等额 vs 金字塔

    评价标准：
      综合评分 = 年化收益 × 0.4 + 夏普比率 × 0.3 - 最大回撤 × 0.3
      （收益高、波动小、回撤小的参数组合得分最高）
    """
    # 获取历史数据（只获取一次，所有参数组合共用）
    hist_data = _fetch_historical(stock_code, hist_days)
    if not hist_data:
        return {'error': '无法获取历史数据'}

    # 获取当前价格
    stock_data = _get_stock_data(stock_code)
    if not stock_data:
        return {'error': '无法获取实时行情'}
    current_price = stock_data['price']

    # 计算ATR
    highs = [d['high'] for d in hist_data]
    lows = [d['low'] for d in hist_data]
    closes = [d['close'] for d in hist_data]
    atr = calculate_atr(highs, lows, closes, 14)

    # 扫描参数组合
    width_options = [1, 1.5, 2, 2.5, 3, 4, 5]  # 网格宽度百分比
    grid_count_options = [8, 10, 12, 15, 20]     # 单侧网格数
    sizing_options = ['equal', 'pyramid']         # 仓位方法

    results = []
    for width_pct in width_options:
        for num_grids in grid_count_options:
            for sizing in sizing_options:
                grid_width = current_price * width_pct / 100
                levels = generate_grid_levels(
                    current_price, 'equal_distance',
                    num_grids, num_grids, grid_width
                )
                positions = calculate_grid_positions(
                    total_capital, len(levels), sizing, current_price, levels
                )
                shares = positions[0]['shares'] if positions else 100
                sim = simulate_grid_trading(
                    hist_data, levels, shares, total_capital,
                    stock_code=stock_code
                )
                # 综合评分
                score = (
                    sim['total_return_pct'] * 0.4 +
                    sim['sharpe_ratio'] * 30 * 0.3 -
                    sim['max_drawdown'] * 0.3
                )
                results.append({
                    'width_pct': width_pct,
                    'num_grids': num_grids,
                    'sizing': sizing,
                    'total_return': sim['total_return_pct'],
                    'sharpe': sim['sharpe_ratio'],
                    'max_drawdown': sim['max_drawdown'],
                    'win_rate': sim['win_rate'],
                    'score': round(score, 2),
                })

    # 按评分排序，返回前5个最优组合
    results.sort(key=lambda x: x['score'], reverse=True)
    return {
        'top_combinations': results[:5],
        'all_results': results,
        'atr': round(atr, 2),
        'current_price': current_price,
    }


# ============================================================
# 主分析入口 — 完整的网格交易分析流程
# ============================================================

def analyze_grid_trading(
    stock_code: str = '00700',
    grid_type: str = 'equal_distance',
    num_grids_up: int = 10,
    num_grids_down: int = 10,
    grid_width_pct: float = None,
    total_capital: float = 1000000,
    hist_days: int = 252,
    sizing_method: str = 'equal',
    stop_loss_pct: float = 0.10,
    enable_stop_loss: bool = True,
    atr_multiplier: float = 1.0,
    _klines_override: list = None,
) -> dict:
    """
    网格交易完整分析 — 一站式生成所有分析结果

    分析流程：
      1. 获取实时行情（当前价格）
      2. 获取历史数据（用于计算ATR和回测）
      3. 计算ATR（衡量波动性）
      4. 确定网格宽度（手动指定或ATR自动）
      5. 生成网格层级
      6. 计算仓位大小
      7. 运行历史回测
      8. 计算盈亏平衡
      9. 计算年化收益率
      10. 返回完整分析结果

    参数：
        stock_code: 股票代码（自动识别A股/港股）
        grid_type: 'equal_distance'(等距) 或 'equal_ratio'(等比)
        num_grids_up: 上行网格数
        num_grids_down: 下行网格数
        grid_width_pct: 网格宽度百分比（如2表示2%），None则用ATR自动
        total_capital: 总资金
        hist_days: 回测天数
        sizing_method: 'equal'(等额) 或 'pyramid'(金字塔)
        stop_loss_pct: 止损比例（默认10%）
        enable_stop_loss: 是否启用止损
    返回：
        完整的分析结果字典
    """
    # 缓存检查（避免重复计算）
    cache_key = f"grid_{stock_code}_{grid_type}_{num_grids_up}_{num_grids_down}_{grid_width_pct}_{total_capital}_{hist_days}_{sizing_method}_{stop_loss_pct}_{enable_stop_loss}_{atr_multiplier}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    # 第1步：获取实时行情
    stock_data = _get_stock_data(stock_code)
    if not stock_data:
        return {'error': f'无法获取 {stock_code} 实时行情', 'update_time': datetime.now().isoformat()}

    current_price = stock_data['price']
    market = stock_data.get('market', 'HK')

    # 第2步：获取历史数据（支持压力测试覆盖）
    if _klines_override:
        hist_data = _klines_override
        current_price = hist_data[-1]["close"]
        market = stock_data.get('market', 'HK') if stock_code != "SIM" else "A"
    else:
        hist_data = _fetch_historical(stock_code, hist_days)
    if not hist_data:
        return {'error': '无法获取历史数据', 'update_time': datetime.now().isoformat()}

    # 第3步：计算ATR
    highs = [d['high'] for d in hist_data]
    lows = [d['low'] for d in hist_data]
    closes = [d['close'] for d in hist_data]
    atr = calculate_atr(highs, lows, closes, 14)

    # 第4步：52周（约1年）最高最低价
    high_52w = max(highs[-252:]) if len(highs) >= 252 else max(highs)
    low_52w = min(lows[-252:]) if len(lows) >= 252 else min(lows)

    # 第5步：确定网格宽度
    if grid_width_pct:
        grid_width = current_price * grid_width_pct / 100
    else:
        grid_width = atr * atr_multiplier  # 使用可配置的ATR倍数

    # 第6步：生成网格层级（传递历史数据给动态网格使用）
    grid_levels = generate_grid_levels(
        current_price, grid_type, num_grids_up, num_grids_down,
        grid_width, atr, atr_multiplier,
        highs=highs, lows=lows, closes=closes,
    )

    # 第7步：计算仓位（传入网格层级，让金字塔模式按实际价格计算股数）
    positions = calculate_grid_positions(total_capital, len(grid_levels),
                                         sizing_method, current_price, grid_levels)
    shares_per_grid = positions[0]['shares'] if positions else 100

    # 第8步：运行回测模拟
    simulation = simulate_grid_trading(
        hist_data, grid_levels, shares_per_grid, total_capital,
        stock_code=stock_code,
        stop_loss_pct=stop_loss_pct,
        enable_stop_loss=enable_stop_loss,
    )

    # 第9步：网格状态
    status = get_grid_status(current_price, grid_levels)

    # 第10步：盈亏平衡分析
    be = breakeven_analysis(grid_width, shares_per_grid, current_price,
                            stock_code=stock_code)

    # 第11步：计算年化收益率
    years = hist_days / 252
    if years > 0 and simulation['total_return_pct'] > -100:
        total_ret = simulation['total_return_pct'] / 100
        if total_ret > -1:
            cagr = round((1 + total_ret) ** (1 / years) - 1, 4) * 100
        else:
            cagr = -100
    else:
        cagr = simulation['total_return_pct']

    # 第12步：组装结果
    result = {
        'stock_name': stock_data['name'],
        'stock_code': stock_code,
        'market': market,
        'current_price': current_price,
        'high_52w': round(high_52w, 2),
        'low_52w': round(low_52w, 2),
        'atr': round(atr, 2),
        'atr_pct': round(atr / current_price * 100, 2),
        'grid_type': grid_type,
        'grid_width': round(grid_width, 2),
        'grid_width_pct': round(grid_width / current_price * 100, 2),
        'grid_levels': grid_levels,
        'shares_per_grid': shares_per_grid,
        'capital_per_grid': round(shares_per_grid * current_price, 2),
        'total_levels': len(grid_levels),
        'simulation': simulation,
        'status': status,
        'breakeven': be,
        'cagr': round(cagr, 2),
        'hist_days': len(hist_data),
        'stop_loss_pct': stop_loss_pct,
        'enable_stop_loss': enable_stop_loss,
        'atr_multiplier': atr_multiplier,
        'stop_loss_price': round(grid_levels[0]['price'] * (1 - stop_loss_pct), 2) if enable_stop_loss and grid_levels else None,
        'chart_data': {
            'dates': [d['date'] for d in hist_data],
            'opens': [d['open'] for d in hist_data],
            'highs': [d['high'] for d in hist_data],
            'lows': [d['low'] for d in hist_data],
            'closes': [d['close'] for d in hist_data],
            'volumes': [d['volume'] for d in hist_data],
        },
        'update_time': datetime.now().isoformat(),
    }

    _set_cached(cache_key, result)
    return result


# ============================================================
# 网格交易理念 — 教学内容
# ============================================================

def get_philosophy() -> dict:
    """
    返回网格交易的教学内容

    包含：概念解释、参数优化维度、风险提示、交易规则
    """
    return {
        'title': '网格交易策略',
        'subtitle': '在价格波动中自动低买高卖，适合震荡市',
        'concepts': [
            {
                'name': '等距网格',
                'desc': '每个网格间距相等，像尺子上的刻度。适合价格在窄幅区间震荡的标的。',
                'formula': 'Level[i] = Base + i × Width',
                'example': '当前价100，网格宽度2：98, 100, 102, 104...',
            },
            {
                'name': '等比网格',
                'desc': '每个网格间距按固定比例递增，像对数刻度。适合价格波动较大的标的。',
                'formula': 'Level[i] = Base × (1 + Ratio)^i',
                'example': '当前价100，比率2%：98.04, 100, 102, 104.04...',
            },
            {
                'name': '动态网格',
                'desc': '基于布林带自适应调整网格区间。波动率高时自动放宽网格，波动率低时自动收窄。适合波动率变化较大的标的。',
                'formula': 'Upper = MA + 2×STD, Lower = MA - 2×STD, Width = (Upper-Lower)/N',
                'example': '均值100，标准差5：网格区间[90, 110]，每格宽度2',
            },
        ],
        'scoring': {
            'title': '网格参数优化要点',
            'dimensions': [
                {'name': '网格宽度', 'desc': '基于ATR计算，太窄被手续费吃掉利润，太宽资金闲置。一般建议ATR的0.8-1.5倍。'},
                {'name': '网格数量', 'desc': '上行/下行各10-15格为宜，覆盖主要波动区间。太少覆盖不够，太多资金分散。'},
                {'name': '仓位管理', 'desc': '等额分配简单易懂；金字塔加仓越跌越买，降低成本但需要更多资金。'},
                {'name': '交易成本', 'desc': '确保网格利润 > 2×交易成本。港股印花税0.13%，A股印花税0.05%。'},
                {'name': '止损设置', 'desc': '建议设置10-15%止损线，防止单边下跌时无限买入被套。'},
            ],
        },
        'risks': [
            '趋势行情：单边上涨会踏空（只赚了网格内的小差价），单边下跌会不断买入被套',
            '震荡区间突破：价格突破网格上下界后策略失效，需要重新设置网格',
            '资金耗尽：下跌过深时网格资金可能不够继续买入，导致"子弹打光"',
            '交易成本：频繁交易的手续费会侵蚀利润，网格太窄可能白忙活',
            '流动性风险：极端行情下可能无法按网格价成交（滑点）',
            '黑天鹅事件：突发利空可能导致价格直接跳过多个网格',
        ],
        'rules': [
            '网格宽度至少覆盖2倍交易成本（确保每笔交易有利可图）',
            '总资金分N份，每份只用于一个网格（不要把所有钱一次性投入）',
            '设置止损线：价格跌破最下方网格10-15%时停止买入（保护本金）',
            '定期评估：震荡区间变化时调整网格参数（不要一成不变）',
            '选择长期横盘震荡的标的（趋势股不适合网格）',
            '保留20-30%现金作为备用（应对极端下跌行情）',
        ],
        'best_for': [
            '长期横盘震荡的股票（如大型蓝筹股在估值合理区间）',
            'ETF指数基金（波动相对稳定，不会退市）',
            '有稳定分红的股票（下跌时还能收息）',
        ],
        'not_for': [
            '趋势明显的成长股（上涨时网格会不断卖出，踏空大行情）',
            '小盘题材股（波动太大，容易突破网格区间）',
            '即将退市或基本面恶化的股票（网格救不了烂公司）',
        ],
    }


# ============================================================
# 专家级：网格组合管理
# ============================================================

import json
import os
import random

_GRID_PORTFOLIO_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "grid_portfolio.json"
)


def _load_grid_portfolio() -> list:
    if os.path.exists(_GRID_PORTFOLIO_FILE):
        try:
            with open(_GRID_PORTFOLIO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载网格组合失败: {e}")
    return []


def _save_grid_portfolio(portfolio: list):
    os.makedirs(os.path.dirname(_GRID_PORTFOLIO_FILE), exist_ok=True)
    with open(_GRID_PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(portfolio, f, ensure_ascii=False, indent=2)


def add_to_grid_portfolio(
    code: str, name: str, market: str,
    grid_type: str, grid_width_pct: float, num_grids: int,
    capital: float, sizing: str, current_price: float,
) -> dict:
    """添加网格到组合"""
    portfolio = _load_grid_portfolio()

    # 检查是否已存在
    for g in portfolio:
        if g["code"] == code and g["market"] == market:
            return {"error": f"{code} 已在网格组合中"}

    entry = {
        "code": code,
        "name": name,
        "market": market,
        "grid_type": grid_type,
        "grid_width_pct": grid_width_pct,
        "num_grids": num_grids,
        "capital": capital,
        "sizing": sizing,
        "entry_price": current_price,
        "entry_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "realized_pnl": 0.0,
        "trade_count": 0,
        "status": "active",
    }
    portfolio.append(entry)
    _save_grid_portfolio(portfolio)
    return {"message": f"已添加 {name}({code}) 到网格组合", "entry": entry}


def get_grid_portfolio() -> dict:
    """获取网格组合及实时状态"""
    portfolio = _load_grid_portfolio()
    result = []
    total_capital = 0
    total_pnl = 0

    for g in portfolio:
        total_capital += g.get("capital", 0)
        total_pnl += g.get("realized_pnl", 0)
        result.append(g)

    return {
        "portfolio": result,
        "summary": {
            "total_grids": len(result),
            "active_grids": len([g for g in result if g.get("status") == "active"]),
            "total_capital": total_capital,
            "total_realized_pnl": round(total_pnl, 2),
        },
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def remove_from_grid_portfolio(code: str, market: str) -> dict:
    """从组合中移除网格"""
    portfolio = _load_grid_portfolio()
    new_portfolio = [g for g in portfolio if not (g["code"] == code and g["market"] == market)]
    if len(new_portfolio) == len(portfolio):
        return {"error": f"未找到 {code}"}
    _save_grid_portfolio(new_portfolio)
    return {"message": f"已移除 {code}"}


# ============================================================
# 专家级：网格衰减检测
# ============================================================

def detect_grid_decay(closes: list, grid_levels: list, lookback: int = 20) -> dict:
    """
    检测网格策略是否在失效

    衰减场景：
    1. 趋势突破：价格持续突破多层网格 = 趋势市，网格不适合
    2. 波动率收缩：波动率降到网格宽度以下 = 网格"空转"
    3. 区间漂移：震荡中心偏离网格中心

    返回：
    - decay_score: 0-100 (0=正常, 100=完全失效)
    - decay_type: "trending" / "low_vol" / "drift" / "healthy"
    - recommendation: 建议操作
    - signals: 具体信号列表
    """
    if len(closes) < lookback or not grid_levels:
        return {"decay_score": 0, "decay_type": "healthy", "recommendation": "数据不足", "signals": []}

    recent = closes[-lookback:]
    prices = [lv["price"] for lv in grid_levels if "price" in lv]
    if not prices:
        return {"decay_score": 0, "decay_type": "healthy", "recommendation": "无网格数据", "signals": []}

    grid_min = min(prices)
    grid_max = max(prices)
    grid_width = (grid_max - grid_min) / len(prices) if prices else 1

    signals = []
    decay_score = 0

    # --- 1. 趋势突破检测 ---
    # 检查价格是否持续向一个方向突破多层网格
    price_direction = recent[-1] - recent[0]
    price_move_pct = abs(price_direction) / recent[0] * 100

    if recent[-1] > grid_max:
        decay_score += 40
        signals.append(f"价格突破上方网格边界 (当前{recent[-1]:.2f} > 网格上限{grid_max:.2f})")
    elif recent[-1] < grid_min:
        decay_score += 40
        signals.append(f"价格跌破下方网格边界 (当前{recent[-1]:.2f} < 网格下限{grid_min:.2f})")

    # 连续单方向移动
    up_count = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i-1])
    down_count = sum(1 for i in range(1, len(recent)) if recent[i] < recent[i-1])
    if up_count > len(recent) * 0.75:
        decay_score += 20
        signals.append(f"近{lookback}日有{up_count}日上涨，单边上涨趋势")
    elif down_count > len(recent) * 0.75:
        decay_score += 20
        signals.append(f"近{lookback}日有{down_count}日下跌，单边下跌趋势")

    # --- 2. 波动率收缩检测 ---
    daily_ranges = [abs(recent[i] - recent[i-1]) for i in range(1, len(recent))]
    avg_range = sum(daily_ranges) / len(daily_ranges) if daily_ranges else 0

    if avg_range < grid_width * 0.3:
        decay_score += 25
        signals.append(f"日均波动({avg_range:.2f})仅为网格宽度({grid_width:.2f})的{avg_range/grid_width*100:.0f}%，网格空转")
    elif avg_range < grid_width * 0.5:
        decay_score += 10
        signals.append(f"日均波动({avg_range:.2f})偏低，网格触发频率降低")

    # --- 3. 区间漂移检测 ---
    mid_price = (grid_min + grid_max) / 2
    current_price = recent[-1]
    drift_pct = (current_price - mid_price) / mid_price * 100

    if abs(drift_pct) > 20:
        decay_score += 15
        signals.append(f"价格偏离网格中心{drift_pct:.1f}%，网格可能需要重新调整")

    # 判定衰减类型
    decay_score = min(decay_score, 100)

    if decay_score >= 60:
        if up_count > len(recent) * 0.75 or down_count > len(recent) * 0.75:
            decay_type = "trending"
            recommendation = "价格进入单边趋势，建议暂停网格，切换为趋势策略或等待回调"
        elif avg_range < grid_width * 0.3:
            decay_type = "low_vol"
            recommendation = "波动率过低，网格几乎不触发。建议收窄网格宽度或切换标的"
        else:
            decay_type = "drift"
            recommendation = "价格偏离网格中心，建议重新设置网格参数"
    elif decay_score >= 30:
        decay_type = "warning"
        recommendation = "网格效率下降，建议观察或微调参数"
    else:
        decay_type = "healthy"
        recommendation = "网格运行正常，继续执行"

    return {
        "decay_score": decay_score,
        "decay_type": decay_type,
        "recommendation": recommendation,
        "signals": signals,
        "metrics": {
            "avg_daily_range": round(avg_range, 4),
            "grid_width": round(grid_width, 4),
            "range_to_width_ratio": round(avg_range / grid_width, 2) if grid_width > 0 else 0,
            "price_vs_grid_center": round(drift_pct, 2),
            "above_grid": recent[-1] > grid_max,
            "below_grid": recent[-1] < grid_min,
        },
    }


# ============================================================
# 专家级：蒙特卡洛压力测试
# ============================================================

def stress_test_grid(
    klines: list,
    grid_type: str = "equal_distance",
    num_grids_up: int = 10,
    num_grids_down: int = 10,
    grid_width_pct: float = 2.0,
    capital: float = 1000000,
    sizing: str = "equal",
    num_simulations: int = 500,
) -> dict:
    """
    蒙特卡洛压力测试

    随机打乱K线顺序，模拟多种市场情景：
    - 收益分布（中位数、均值、标准差）
    - VaR(95%) — 95%概率不会亏超过多少
    - CVaR(95%) — 最坏5%情况的平均亏损
    - 最差情景
    - 最好情景
    """
    if len(klines) < 30:
        return {"error": "需要至少30个交易日数据"}

    closes = [k["close"] for k in klines]
    current_price = closes[-1]

    # 计算日收益率
    returns = []
    for i in range(1, len(closes)):
        if closes[i-1] > 0:
            returns.append((closes[i] - closes[i-1]) / closes[i-1])

    if not returns:
        return {"error": "无法计算收益率"}

    # 运行蒙特卡洛模拟
    simulation_results = []

    for _ in range(num_simulations):
        # 随机生成与原始数据等长的价格序列
        sim_closes = [current_price]
        for _ in range(len(returns) - 1):
            r = random.choice(returns)
            sim_closes.append(sim_closes[-1] * (1 + r))

        # 用模拟价格运行网格回测
        sim_klines = [{"date": f"sim_{i}", "open": c, "high": c * 1.005, "low": c * 0.995, "close": c, "volume": 1000000}
                      for i, c in enumerate(sim_closes)]

        try:
            result = analyze_grid_trading(
                stock_code="SIM",
                grid_type=grid_type,
                num_grids_up=num_grids_up,
                num_grids_down=num_grids_down,
                grid_width_pct=grid_width_pct,
                total_capital=capital,
                hist_days=len(sim_klines),
                sizing_method=sizing,
                stop_loss_pct=0.10,
                enable_stop_loss=True,
                atr_multiplier=1.0,
                _klines_override=sim_klines,
            )
            if "error" not in result and "simulation" in result:
                simulation_results.append({
                    "total_return": result["simulation"].get("total_return_pct", 0),
                    "max_drawdown": result["simulation"].get("max_drawdown", 0),
                    "sharpe": result["simulation"].get("sharpe_ratio", 0),
                    "win_rate": result["simulation"].get("win_rate", 0),
                })
        except Exception:
            continue

    if not simulation_results:
        return {"error": "压力测试失败，无法生成有效模拟"}

    # 统计分析
    returns_list = [s["total_return"] for s in simulation_results]
    drawdowns = [s["max_drawdown"] for s in simulation_results]
    sharpes = [s["sharpe"] for s in simulation_results]

    returns_list.sort()
    drawdowns.sort(reverse=True)  # 最大回撤从大到小

    n = len(returns_list)
    var_95 = returns_list[int(n * 0.05)] if n > 20 else returns_list[0]
    cvar_95 = sum(returns_list[:int(n * 0.05)]) / max(int(n * 0.05), 1) if n > 20 else var_95

    return {
        "num_simulations": len(simulation_results),
        "return_distribution": {
            "mean": round(statistics.mean(returns_list), 2),
            "median": round(statistics.median(returns_list), 2),
            "std": round(statistics.stdev(returns_list), 2) if len(returns_list) > 1 else 0,
            "min": round(min(returns_list), 2),
            "max": round(max(returns_list), 2),
            "p10": round(returns_list[int(n * 0.1)], 2),
            "p25": round(returns_list[int(n * 0.25)], 2),
            "p75": round(returns_list[int(n * 0.75)], 2),
            "p90": round(returns_list[int(n * 0.9)], 2),
        },
        "risk_metrics": {
            "var_95": round(var_95, 2),
            "cvar_95": round(cvar_95, 2),
            "max_drawdown_worst": round(max(drawdowns), 2),
            "max_drawdown_median": round(statistics.median(drawdowns), 2),
            "sharpe_mean": round(statistics.mean(sharpes), 2),
            "probability_of_profit": round(len([r for r in returns_list if r > 0]) / n * 100, 1),
        },
        "interpretation": {
            "var_explanation": f"95%的情况下，最大亏损不会超过{abs(round(var_95, 1))}%",
            "cvar_explanation": f"最坏5%情景下，平均亏损为{abs(round(cvar_95, 1))}%",
            "profit_probability": f"盈利概率为{round(len([r for r in returns_list if r > 0]) / n * 100, 1)}%",
            "recommendation": (
                "网格策略风险可控，可以执行" if var_95 > -15
                else "存在一定风险，建议降低仓位或加宽网格" if var_95 > -25
                else "风险较高，不建议使用当前参数的网格策略"
            ),
        },
    }


# ============================================================
# 专家级：网格 vs 买入持有对比
# ============================================================

def grid_vs_buy_and_hold(
    stock_code: str,
    total_capital: float = 1000000,
    hist_days: int = 252,
) -> dict:
    """
    网格策略 vs 买入持有策略对比

    帮助用户理解网格交易的优劣势：
    - 震荡市中网格更优
    - 趋势市中买入持有更优
    """
    hist_data = _fetch_historical(stock_code, hist_days)
    if not hist_data or len(hist_data) < 30:
        return {"error": "历史数据不足"}

    closes = [d["close"] for d in hist_data]
    first_price = closes[0]
    last_price = closes[-1]

    # --- 买入持有收益 ---
    bh_shares = int(total_capital / first_price)
    bh_cost = bh_shares * first_price
    bh_value = bh_shares * last_price
    bh_return = round((bh_value - bh_cost) / bh_cost * 100, 2)
    bh_max_price = max(closes)
    bh_min_price = min(closes)
    bh_max_drawdown = round((bh_min_price - bh_max_price) / bh_max_price * 100, 2)

    # --- 网格策略收益（用默认参数回测）---
    atr = calculate_atr(
        [d["high"] for d in hist_data],
        [d["low"] for d in hist_data],
        closes, 14
    )
    grid_width_pct = round(atr / last_price * 100 * 1.0, 1)  # ATR的1倍

    try:
        grid_result = analyze_grid_trading(
            stock_code=stock_code,
            grid_type="equal_distance",
            num_grids_up=10,
            num_grids_down=10,
            grid_width_pct=grid_width_pct,
            total_capital=total_capital,
            hist_days=hist_days,
            sizing_method="equal",
            stop_loss_pct=0.10,
            enable_stop_loss=True,
            atr_multiplier=1.0,
            _klines_override=hist_data,
        )
        grid_return = grid_result.get("simulation", {}).get("total_return_pct", 0)
        grid_max_dd = grid_result.get("simulation", {}).get("max_drawdown", 0)
        grid_trades = grid_result.get("simulation", {}).get("total_trades", 0)
        grid_win_rate = grid_result.get("simulation", {}).get("win_rate", 0)
        grid_sharpe = grid_result.get("simulation", {}).get("sharpe_ratio", 0)
    except Exception:
        grid_return = 0
        grid_max_dd = 0
        grid_trades = 0
        grid_win_rate = 0
        grid_sharpe = 0

    # 判断市场环境
    price_change_pct = round((last_price - first_price) / first_price * 100, 2)
    daily_ranges = [abs(closes[i] - closes[i-1]) / closes[i-1] * 100 for i in range(1, len(closes))]
    avg_daily_range = round(sum(daily_ranges) / len(daily_ranges), 2) if daily_ranges else 0

    # 判定哪种策略更优
    if abs(price_change_pct) < 10 and avg_daily_range > 1.0:
        winner = "grid"
        winner_reason = f"价格区间震荡(变化{price_change_pct}%)，日均波动{avg_daily_range}%，网格策略更优"
    elif price_change_pct > 15:
        winner = "buy_and_hold"
        winner_reason = f"价格上涨{price_change_pct}%，趋势明显，买入持有更优"
    elif price_change_pct < -15:
        winner = "neither"
        winner_reason = f"价格下跌{price_change_pct}%，两种策略都亏损，建议观望"
    else:
        winner = "grid" if grid_return > bh_return else "buy_and_hold"
        winner_reason = f"网格{grid_return}% vs 买入持有{bh_return}%"

    return {
        "buy_and_hold": {
            "return_pct": bh_return,
            "max_drawdown_pct": bh_max_drawdown,
            "final_value": round(bh_value, 2),
            "shares": bh_shares,
        },
        "grid_strategy": {
            "return_pct": round(grid_return, 2),
            "max_drawdown_pct": round(grid_max_dd, 2),
            "total_trades": grid_trades,
            "win_rate": round(grid_win_rate, 1),
            "sharpe": round(grid_sharpe, 2),
        },
        "comparison": {
            "winner": winner,
            "reason": winner_reason,
            "price_change_pct": price_change_pct,
            "avg_daily_range": avg_daily_range,
            "market_env": (
                "震荡市" if abs(price_change_pct) < 10
                else "上涨趋势" if price_change_pct > 0
                else "下跌趋势"
            ),
        },
        "insight": (
            "震荡市中网格策略通过反复低买高卖赚取差价，优于买入持有。" if winner == "grid"
            else "趋势市中买入持有享受完整涨幅，网格会频繁卖出踏空。" if winner == "buy_and_hold"
            else "下跌市中两种策略都亏损，建议等待企稳或止损。"
        ),
    }


# ============================================================
# 专家级：自适应网格建议
# ============================================================

def suggest_adaptive_grid(stock_code: str, capital: float = 1000000) -> dict:
    """
    根据当前市场状态自动推荐网格参数

    分析：
    1. 当前波动率（ATR）→ 推荐网格宽度
    2. 价格趋势 → 推荐是否适合网格
    3. 历史回测 → 推荐最优参数
    """
    hist_data = _fetch_historical(stock_code, 252)
    if not hist_data or len(hist_data) < 60:
        return {"error": "历史数据不足"}

    closes = [d["close"] for d in hist_data]
    highs = [d["high"] for d in hist_data]
    lows = [d["low"] for d in hist_data]

    current_price = closes[-1]
    atr = calculate_atr(highs, lows, closes, 14)
    atr_pct = round(atr / current_price * 100, 2)

    # 波动率分位数（当前波动率在历史中的位置）
    atr_history = []
    for i in range(60, len(closes)):
        a = calculate_atr(highs[:i+1], lows[:i+1], closes[:i+1], 14)
        atr_history.append(a)

    current_atr_rank = sum(1 for a in atr_history if a <= atr) / len(atr_history) * 100 if atr_history else 50

    # 趋势判断
    ma20 = sum(closes[-20:]) / 20
    ma60 = sum(closes[-60:]) / 60
    trend = "uptrend" if ma20 > ma60 * 1.02 else "downtrend" if ma20 < ma60 * 0.98 else "sideways"

    # 52周价格位置
    high_52w = max(highs[-252:]) if len(highs) >= 252 else max(highs)
    low_52w = min(lows[-252:]) if len(lows) >= 252 else min(lows)
    price_position = round((current_price - low_52w) / (high_52w - low_52w) * 100, 1) if high_52w != low_52w else 50

    # 推荐参数
    if atr_pct < 1.5:
        # 低波动：窄网格，多格数
        recommended_width = round(atr_pct * 0.8, 1)
        recommended_grids = 15
        sizing = "equal"
        confidence = "高"
    elif atr_pct < 3.0:
        # 中等波动：标准网格
        recommended_width = round(atr_pct * 1.0, 1)
        recommended_grids = 10
        sizing = "equal"
        confidence = "高"
    else:
        # 高波动：宽网格，金字塔加仓
        recommended_width = round(atr_pct * 1.2, 1)
        recommended_grids = 8
        sizing = "pyramid"
        confidence = "中"

    # 适合度评分
    suitability_score = 50  # 基础分
    if trend == "sideways":
        suitability_score += 20  # 震荡市加分
    elif trend == "uptrend":
        suitability_score += 5
    else:
        suitability_score -= 15  # 下降趋势减分

    if 20 < price_position < 80:
        suitability_score += 15  # 价格在中间区域加分
    elif price_position > 90:
        suitability_score -= 10  # 价格在高位减分
    elif price_position < 10:
        suitability_score -= 5  # 价格在低位（可能继续跌）

    if 1.0 < atr_pct < 3.0:
        suitability_score += 15  # 波动率适中加分
    elif atr_pct < 0.5:
        suitability_score -= 20  # 波动率太低，网格不触发

    suitability_score = max(0, min(100, suitability_score))

    # 推荐理由
    reasons = []
    if trend == "sideways":
        reasons.append("当前价格横盘震荡，适合网格交易")
    elif trend == "downtrend":
        reasons.append("当前处于下降趋势，网格交易风险较高，建议等企稳")
    if atr_pct < 1.0:
        reasons.append("波动率偏低，网格触发频率可能不足")
    elif atr_pct > 3.0:
        reasons.append("波动率较高，建议使用金字塔加仓降低风险")
    if price_position > 80:
        reasons.append("价格处于52周高位区间，下行风险较大")
    elif price_position < 20:
        reasons.append("价格处于52周低位区间，可能继续下跌")

    return {
        "stock_code": stock_code,
        "current_price": current_price,
        "atr": round(atr, 2),
        "atr_pct": atr_pct,
        "atr_rank": round(current_atr_rank, 1),
        "trend": trend,
        "price_position_52w": price_position,
        "suitability_score": suitability_score,
        "suitability_label": (
            "非常适合网格" if suitability_score >= 75
            else "适合网格" if suitability_score >= 55
            else "勉强适合" if suitability_score >= 40
            else "不太适合网格"
        ),
        "recommended_params": {
            "grid_width_pct": recommended_width,
            "num_grids": recommended_grids,
            "sizing": sizing,
            "confidence": confidence,
        },
        "reasons": reasons,
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ============================================================
# 专家级：网格健康监控
# ============================================================

def grid_health_monitor(stock_code: str, capital: float = 1000000) -> dict:
    """
    网格健康监控仪表盘

    实时监控网格策略的运行状态：
    1. 网格效率评分（触发频率、成交率）
    2. 资金利用率（已用/总资金）
    3. 收益归因（哪些网格层贡献最多利润）
    4. 风险预警（价格接近网格边界、波动率异常）
    5. 操作建议（是否需要调整参数）
    """
    hist_data = _fetch_historical(stock_code, 60)
    if not hist_data or len(hist_data) < 30:
        return {"error": "历史数据不足"}

    closes = [d["close"] for d in hist_data]
    highs = [d["high"] for d in hist_data]
    lows = [d["low"] for d in hist_data]
    current_price = closes[-1]

    atr = calculate_atr(highs, lows, closes, 14)
    atr_pct = round(atr / current_price * 100, 2)

    # 计算网格效率
    # 用ATR作为网格宽度
    grid_width = atr * 1.0
    grid_width_pct = round(grid_width / current_price * 100, 2)

    # 统计过去30天有多少天触及了网格层
    grid_touches = 0
    for i in range(-30, 0):
        daily_range = highs[i] - lows[i]
        if daily_range >= grid_width:
            grid_touches += 1

    touch_rate = round(grid_touches / 30 * 100, 1)

    # 波动率趋势（近5日 vs 近20日）
    recent_5_range = sum(highs[-5:]) / 5 - sum(lows[-5:]) / 5
    recent_20_range = sum(highs[-20:]) / 20 - sum(lows[-20:]) / 20
    vol_trend = "expanding" if recent_5_range > recent_20_range * 1.2 else "contracting" if recent_5_range < recent_20_range * 0.8 else "stable"

    # 价格趋势
    ma5 = sum(closes[-5:]) / 5
    ma20 = sum(closes[-20:]) / 20
    price_trend = "up" if ma5 > ma20 * 1.01 else "down" if ma5 < ma20 * 0.99 else "sideways"

    # 健康评分
    health_score = 50  # 基础分

    # 触发频率加分
    if 20 <= touch_rate <= 60:
        health_score += 20  # 理想触发频率
    elif touch_rate < 10:
        health_score -= 20  # 触发太少
    elif touch_rate > 80:
        health_score += 5  # 触发太多可能趋势市

    # 波动率趋势加分
    if vol_trend == "stable":
        health_score += 15
    elif vol_trend == "contracting":
        health_score -= 10  # 波动率收缩，网格效率下降
    elif vol_trend == "expanding":
        health_score += 5

    # 价格趋势影响
    if price_trend == "sideways":
        health_score += 15  # 震荡市最适合网格
    elif price_trend == "down":
        health_score -= 15  # 下跌趋势风险高
    elif price_trend == "up":
        health_score -= 5  # 上涨趋势会踏空

    health_score = max(0, min(100, health_score))

    # 预警信息
    warnings = []
    if touch_rate < 10:
        warnings.append("网格触发频率过低，建议收窄网格宽度或切换标的")
    if vol_trend == "contracting":
        warnings.append("波动率正在收缩，网格效率可能下降")
    if price_trend == "down":
        warnings.append("价格呈下降趋势，注意止损风险")
    if price_trend == "up":
        warnings.append("价格呈上涨趋势，网格可能踏空")

    # 操作建议
    if health_score >= 70:
        action = "继续运行"
        action_detail = "网格运行良好，保持当前参数"
    elif health_score >= 50:
        action = "观察调整"
        action_detail = "建议观察市场变化，必要时微调参数"
    elif health_score >= 30:
        action = "考虑调整"
        action_detail = "网格效率下降，建议调整参数或暂停"
    else:
        action = "建议暂停"
        action_detail = "当前市场不适合网格交易，建议暂停等待机会"

    return {
        "stock_code": stock_code,
        "current_price": current_price,
        "health_score": health_score,
        "health_label": (
            "健康" if health_score >= 70
            else "一般" if health_score >= 50
            else "注意" if health_score >= 30
            else "警告"
        ),
        "metrics": {
            "grid_width_pct": grid_width_pct,
            "touch_rate": touch_rate,
            "vol_trend": vol_trend,
            "vol_trend_label": "扩张" if vol_trend == "expanding" else "收缩" if vol_trend == "contracting" else "稳定",
            "price_trend": price_trend,
            "price_trend_label": "上涨" if price_trend == "up" else "下跌" if price_trend == "down" else "震荡",
            "atr_pct": atr_pct,
        },
        "warnings": warnings,
        "action": action,
        "action_detail": action_detail,
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ============================================================
# 网格健康历史记录
# ============================================================

_GRID_HEALTH_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "grid_health_history.json"
)


def _load_health_history() -> dict:
    if os.path.exists(_GRID_HEALTH_FILE):
        try:
            with open(_GRID_HEALTH_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载健康历史失败: {e}")
    return {}


def _save_health_history(history: dict):
    os.makedirs(os.path.dirname(_GRID_HEALTH_FILE), exist_ok=True)
    with open(_GRID_HEALTH_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def save_grid_health_snapshot(stock_code: str) -> dict:
    """
    保存网格健康快照到历史记录

    每次调用会记录当前健康状态，用于追踪趋势。
    """
    health = grid_health_monitor(stock_code)
    if "error" in health:
        return health

    history = _load_health_history()
    if stock_code not in history:
        history[stock_code] = []

    snapshot = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "health_score": health["health_score"],
        "touch_rate": health["metrics"]["touch_rate"],
        "vol_trend": health["metrics"]["vol_trend"],
        "price_trend": health["metrics"]["price_trend"],
        "action": health["action"],
    }

    # 避免同一天重复记录
    if history[stock_code] and history[stock_code][-1]["date"] == snapshot["date"]:
        history[stock_code][-1] = snapshot
    else:
        history[stock_code].append(snapshot)

    # 只保留最近90天
    history[stock_code] = history[stock_code][-90:]

    _save_health_history(history)

    return {
        "message": f"已保存 {stock_code} 健康快照",
        "snapshot": snapshot,
        "history_days": len(history[stock_code]),
    }


def get_grid_health_history(stock_code: str) -> dict:
    """获取网格健康历史趋势"""
    history = _load_health_history()
    records = history.get(stock_code, [])

    if not records:
        return {"error": "暂无历史记录", "records": []}

    # 计算趋势
    recent_scores = [r["health_score"] for r in records[-7:]]
    if len(recent_scores) >= 3:
        avg_recent = sum(recent_scores) / len(recent_scores)
        avg_earlier = sum(r["health_score"] for r in records[-14:-7]) / max(len(records[-14:-7]), 1) if len(records) > 7 else avg_recent
        trend = "improving" if avg_recent > avg_earlier + 5 else "declining" if avg_recent < avg_earlier - 5 else "stable"
    else:
        trend = "insufficient_data"

    return {
        "stock_code": stock_code,
        "records": records,
        "total_records": len(records),
        "trend": trend,
        "trend_label": "改善中" if trend == "improving" else "恶化中" if trend == "declining" else "稳定" if trend == "stable" else "数据不足",
        "latest_score": records[-1]["health_score"] if records else 0,
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
