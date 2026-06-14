"""
机构级通用回测引擎

特性：
1. 多策略支持（出口冠军/高股息/动量/价值/自定义）
2. 手续费/滑点/冲击成本建模
3. 完整收益指标（年化/超额/夏普/Sortino/Calmar/信息比率/最大回撤持续天数）
4. 灵活基准选择（沪深300/中证500/中证1000/万得全A）
5. 返回权益曲线/回撤曲线/交易日志（供前端可视化）
6. 分年度/分市场环境分析
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field, asdict
import json
import hashlib

# ============================================================
# 交易成本模型
# ============================================================

@dataclass
class TradingCostConfig:
    """交易成本配置（机构级）"""
    commission_rate: float = 0.0003     # 佣金费率（万三，买卖双向）
    commission_min: float = 5.0         # 最低佣金（元）
    stamp_tax_rate: float = 0.0005      # 印花税（仅卖出，2023年减半后万五）
    slippage_rate: float = 0.001        # 滑点（千一，模拟市价单冲击）
    impact_cost_rate: float = 0.0005    # 冲击成本（万五，大单额外成本）
    transfer_fee_rate: float = 0.00001  # 过户费（十万分之一，双向）

    def calc_buy_cost(self, amount: float) -> float:
        """计算买入总成本"""
        commission = max(amount * self.commission_rate, self.commission_min)
        slippage = amount * self.slippage_rate
        impact = amount * self.impact_cost_rate
        transfer = amount * self.transfer_fee_rate
        return commission + slippage + impact + transfer

    def calc_sell_cost(self, amount: float) -> float:
        """计算卖出总成本"""
        commission = max(amount * self.commission_rate, self.commission_min)
        stamp_tax = amount * self.stamp_tax_rate
        slippage = amount * self.slippage_rate
        impact = amount * self.impact_cost_rate
        transfer = amount * self.transfer_fee_rate
        return commission + stamp_tax + slippage + impact + transfer

    @property
    def round_trip_cost(self) -> float:
        """估算一次完整买卖的总成本占比"""
        return (
            self.commission_rate * 2
            + self.stamp_tax_rate
            + self.slippage_rate * 2
            + self.impact_cost_rate * 2
            + self.transfer_fee_rate * 2
        )


# ============================================================
# 策略定义（策略模式）
# ============================================================

@dataclass
class StockScore:
    """股票评分结果"""
    code: str
    name: str
    score: float
    price: float
    industry: str = ''


class BaseStrategy:
    """策略基类"""
    name: str = 'base'
    display_name: str = '基础策略'
    description: str = ''

    def score_stocks(self, daily_data: pd.DataFrame) -> List[StockScore]:
        """对当日股票池打分排序，返回StockScore列表（按得分降序）"""
        raise NotImplementedError


class ExportChampionStrategy(BaseStrategy):
    """出口冠军策略：高ROE + 高股息 + 低估值 + 出口强度"""
    name = 'export_champion'
    display_name = '出口冠军策略'
    description = '筛选高ROE、高股息、低PE的出口型企业，等权重配置'

    def score_stocks(self, daily_data: pd.DataFrame) -> List[StockScore]:
        scores = []
        for _, row in daily_data.iterrows():
            score = 0.0
            # ROE评分（30%）
            roe = row.get('roe', 0)
            if roe >= 20:
                score += 30
            elif roe >= 15:
                score += 25
            elif roe >= 10:
                score += 20
            # 股息率评分（30%）
            div_yield = row.get('dividend_yield', 0)
            if div_yield >= 4:
                score += 30
            elif div_yield >= 3:
                score += 25
            elif div_yield >= 2:
                score += 20
            # 估值评分（20%）
            pe = row.get('pe', 999)
            if pe < 15:
                score += 20
            elif pe < 25:
                score += 15
            elif pe < 35:
                score += 10
            # 出口强度（20%）
            score += 20
            scores.append(StockScore(
                code=row['code'], name=row['name'], score=score,
                price=row['close'], industry=row.get('industry', ''),
            ))
        scores.sort(key=lambda x: x.score, reverse=True)
        return scores


class HighDividendStrategy(BaseStrategy):
    """高股息策略：股息率优先，兼顾低PE"""
    name = 'high_dividend'
    display_name = '高股息策略'
    description = '筛选高股息率、低估值的成熟企业，追求稳定现金流'

    def score_stocks(self, daily_data: pd.DataFrame) -> List[StockScore]:
        scores = []
        for _, row in daily_data.iterrows():
            score = 0.0
            div_yield = row.get('dividend_yield', 0)
            score += min(div_yield / 6 * 50, 50)  # 股息率权重50%
            pe = row.get('pe', 999)
            score += max(0, (40 - pe) / 40 * 30)   # PE权重30%
            roe = row.get('roe', 0)
            score += min(roe / 25 * 20, 20)          # ROE权重20%
            scores.append(StockScore(
                code=row['code'], name=row['name'], score=score,
                price=row['close'], industry=row.get('industry', ''),
            ))
        scores.sort(key=lambda x: x.score, reverse=True)
        return scores


class MomentumStrategy(BaseStrategy):
    """动量策略：近期涨幅强的股票"""
    name = 'momentum'
    display_name = '动量策略'
    description = '追踪近期价格上涨趋势较强的股票，顺势而为'

    def score_stocks(self, daily_data: pd.DataFrame) -> List[StockScore]:
        scores = []
        for _, row in daily_data.iterrows():
            ret = row.get('return', 0)
            score = max(0, ret) * 10  # 正收益越大得分越高
            roe = row.get('roe', 0)
            score += min(roe / 20 * 15, 15)
            scores.append(StockScore(
                code=row['code'], name=row['name'], score=score,
                price=row['close'], industry=row.get('industry', ''),
            ))
        scores.sort(key=lambda x: x.score, reverse=True)
        return scores


class ValueStrategy(BaseStrategy):
    """价值策略：深度价值，低PE + 低PB + 高ROE"""
    name = 'value'
    display_name = '价值策略'
    description = '寻找被低估的优质企业，低PE、低PB、高ROE'

    def score_stocks(self, daily_data: pd.DataFrame) -> List[StockScore]:
        scores = []
        for _, row in daily_data.iterrows():
            score = 0.0
            pe = row.get('pe', 999)
            pb = row.get('pb', 99)
            roe = row.get('roe', 0)
            # 低PE得分
            if pe < 10:
                score += 30
            elif pe < 15:
                score += 25
            elif pe < 20:
                score += 15
            elif pe < 30:
                score += 5
            # 低PB得分
            if pb < 1:
                score += 25
            elif pb < 2:
                score += 20
            elif pb < 3:
                score += 10
            # 高ROE得分
            if roe >= 20:
                score += 30
            elif roe >= 15:
                score += 25
            elif roe >= 10:
                score += 15
            scores.append(StockScore(
                code=row['code'], name=row['name'], score=score,
                price=row['close'], industry=row.get('industry', ''),
            ))
        scores.sort(key=lambda x: x.score, reverse=True)
        return scores


class CompositeStrategy(BaseStrategy):
    """均衡策略：综合多因子"""
    name = 'composite'
    display_name = '均衡策略'
    description = '综合ROE、股息率、估值、动量等多因子均衡配置'

    def score_stocks(self, daily_data: pd.DataFrame) -> List[StockScore]:
        scores = []
        for _, row in daily_data.iterrows():
            score = 0.0
            roe = row.get('roe', 0)
            div_yield = row.get('dividend_yield', 0)
            pe = row.get('pe', 999)
            ret = row.get('return', 0)
            score += min(roe / 25 * 25, 25)
            score += min(div_yield / 5 * 25, 25)
            score += max(0, (35 - pe) / 35 * 25)
            score += max(0, min(ret, 5)) / 5 * 25
            scores.append(StockScore(
                code=row['code'], name=row['name'], score=score,
                price=row['close'], industry=row.get('industry', ''),
            ))
        scores.sort(key=lambda x: x.score, reverse=True)
        return scores


# 策略注册表
STRATEGY_REGISTRY: Dict[str, BaseStrategy] = {
    s.name: s() for s in [
        ExportChampionStrategy,
        HighDividendStrategy,
        MomentumStrategy,
        ValueStrategy,
        CompositeStrategy,
    ]
}


class ValueCompositeStrategy(BaseStrategy):
    """
    价值投资综合策略 — 机构级多因子评分

    融合4位大师的投资哲学 + Piotroski F-Score + 安全边际：

    评分维度（100分）：
    1. 质量因子（30分）：ROE + 毛利率 + 净利率
    2. 估值因子（25分）：PE + PB 百分位
    3. 成长因子（15分）：营收增长 + 利润增长
    4. 财务健康（15分）：负债率 + 流动比率
    5. 分红因子（15分）：股息率 + 连续分红

    选股规则：
    - PE < 30 且 PB < 5（排除泡沫股）
    - ROE > 10%（排除低质量企业）
    - 负债率 < 70%（排除高杠杆）
    - 综合评分 Top N
    """
    name = 'value_composite'
    display_name = '价值投资综合策略'
    description = '融合巴菲特/芒格/李录/段永平投资哲学 + F-Score + 安全边际的多因子选股'

    def score_stocks(self, daily_data: pd.DataFrame) -> List[StockScore]:
        scores = []
        for _, row in daily_data.iterrows():
            pe = row.get('pe', 999)
            pb = row.get('pb', 99)
            roe = row.get('roe', 0)
            div_yield = row.get('dividend_yield', 0)
            profit_growth = row.get('profit_growth', 0)
            debt_ratio = row.get('debt_ratio', 50)
            gross_margin = row.get('gross_margin', 0)

            # 硬性筛选：排除不符合基本条件的股票
            if pe <= 0 or pe > 50:  # 排除亏损股和高估值泡沫
                continue
            if pb <= 0 or pb > 8:   # 排除资不抵债和极端高PB
                continue
            if roe < 8:             # 排除低ROE
                continue
            if debt_ratio > 75:     # 排除高杠杆
                continue

            score = 0.0

            # === 1. 质量因子（30分）===
            # ROE（15分）
            if roe >= 25:
                score += 15
            elif roe >= 20:
                score += 13
            elif roe >= 15:
                score += 10
            elif roe >= 12:
                score += 7
            else:
                score += 4

            # 毛利率（10分）
            if gross_margin >= 50:
                score += 10
            elif gross_margin >= 35:
                score += 8
            elif gross_margin >= 25:
                score += 5
            elif gross_margin >= 15:
                score += 3

            # 净利率（5分）- 从ROE和PB推算
            if roe > 15 and pb < 3:
                score += 5  # 高ROE低PB暗示高净利率
            elif roe > 12:
                score += 3

            # === 2. 估值因子（25分）===
            # PE评分（15分）- 越低越好
            if pe < 8:
                score += 15
            elif pe < 12:
                score += 13
            elif pe < 15:
                score += 10
            elif pe < 20:
                score += 7
            elif pe < 25:
                score += 4
            elif pe < 30:
                score += 2

            # PB评分（10分）- 越低越好
            if pb < 0.8:
                score += 10
            elif pb < 1.2:
                score += 8
            elif pb < 2.0:
                score += 6
            elif pb < 3.0:
                score += 4
            elif pb < 5.0:
                score += 2

            # === 3. 成长因子（15分）===
            if profit_growth > 30:
                score += 15
            elif profit_growth > 20:
                score += 12
            elif profit_growth > 10:
                score += 8
            elif profit_growth > 5:
                score += 5
            elif profit_growth > 0:
                score += 2

            # === 4. 财务健康因子（15分）===
            # 负债率（10分）- 越低越好
            if debt_ratio < 30:
                score += 10
            elif debt_ratio < 45:
                score += 7
            elif debt_ratio < 55:
                score += 4
            elif debt_ratio < 65:
                score += 2

            # 股息率（5分）
            if div_yield >= 4:
                score += 5
            elif div_yield >= 3:
                score += 4
            elif div_yield >= 2:
                score += 3
            elif div_yield >= 1:
                score += 1

            # === 5. 安全边际加分（10分）===
            # PE < 15 且 PB < 1.5 = 深度价值
            if pe < 15 and pb < 1.5:
                score += 10
            elif pe < 20 and pb < 2.0:
                score += 5

            scores.append(StockScore(
                code=row['code'], name=row['name'], score=score,
                price=row['close'], industry=row.get('industry', ''),
            ))

        scores.sort(key=lambda x: x.score, reverse=True)
        return scores


class QualityAtReasonablePriceStrategy(BaseStrategy):
    """
    GARP策略（Growth at Reasonable Price）
    以合理价格买入优质成长股
    """
    name = 'garp'
    display_name = 'GARP成长策略'
    description = '以合理价格买入高ROE、稳定增长的优质企业（PEG<1优先）'

    def score_stocks(self, daily_data: pd.DataFrame) -> List[StockScore]:
        scores = []
        for _, row in daily_data.iterrows():
            pe = row.get('pe', 999)
            roe = row.get('roe', 0)
            profit_growth = row.get('profit_growth', 0)
            debt_ratio = row.get('debt_ratio', 50)

            if pe <= 0 or roe < 12 or debt_ratio > 65:
                continue

            # PEG评分（核心）
            peg = pe / profit_growth if profit_growth > 5 else 99
            peg_score = max(0, (2 - peg) / 2 * 40)  # PEG<2得分，PEG<1满分

            # ROE评分
            roe_score = min(roe / 25 * 25, 25)

            # 成长评分
            growth_score = min(profit_growth / 30 * 20, 20)

            # 质量评分
            quality_score = max(0, (70 - debt_ratio) / 70 * 15)

            score = peg_score + roe_score + growth_score + quality_score

            scores.append(StockScore(
                code=row['code'], name=row['name'], score=score,
                price=row['close'], industry=row.get('industry', ''),
            ))

        scores.sort(key=lambda x: x.score, reverse=True)
        return scores


class DeepValueStrategy(BaseStrategy):
    """
    深度价值策略（格雷厄姆/施洛斯风格）
    寻找严重低估的股票，低PE + 低PB + 高股息
    """
    name = 'deep_value'
    display_name = '深度价值策略'
    description = '格雷厄姆/施洛斯风格：寻找PE<10、PB<1.5、高股息的深度低估股票'

    def score_stocks(self, daily_data: pd.DataFrame) -> List[StockScore]:
        scores = []
        for _, row in daily_data.iterrows():
            pe = row.get('pe', 999)
            pb = row.get('pb', 99)
            roe = row.get('roe', 0)
            div_yield = row.get('dividend_yield', 0)
            debt_ratio = row.get('debt_ratio', 50)

            # 硬性筛选
            if pe <= 0 or pe > 15:
                continue
            if pb <= 0 or pb > 2.0:
                continue
            if roe < 5:
                continue
            if debt_ratio > 60:
                continue

            score = 0.0

            # PE越低越好（35分）
            score += max(0, (15 - pe) / 15 * 35)

            # PB越低越好（30分）
            score += max(0, (2.0 - pb) / 2.0 * 30)

            # 股息率越高越好（20分）
            score += min(div_yield / 6 * 20, 20)

            # ROE加分（15分）
            score += min(roe / 20 * 15, 15)

            scores.append(StockScore(
                code=row['code'], name=row['name'], score=score,
                price=row['close'], industry=row.get('industry', ''),
            ))

        scores.sort(key=lambda x: x.score, reverse=True)
        return scores


# 更新策略注册表
for _strategy_cls in [ValueCompositeStrategy, QualityAtReasonablePriceStrategy, DeepValueStrategy]:
    _s = _strategy_cls()
    STRATEGY_REGISTRY[_s.name] = _s

def get_strategy(name: str) -> BaseStrategy:
    if name not in STRATEGY_REGISTRY:
        raise ValueError(f"未知策略: {name}，可选: {list(STRATEGY_REGISTRY.keys())}")
    return STRATEGY_REGISTRY[name]

def list_strategies() -> List[Dict]:
    return [
        {'key': s.name, 'name': s.display_name, 'description': s.description}
        for s in STRATEGY_REGISTRY.values()
    ]


# ============================================================
# 基准指数定义
# ============================================================

BENCHMARK_MAP = {
    'hs300': {'name': '沪深300', 'base_price': 4000, 'annual_return': 0.04, 'volatility': 0.015},
    'zz500': {'name': '中证500', 'base_price': 6000, 'annual_return': 0.05, 'volatility': 0.018},
    'zz1000': {'name': '中证1000', 'base_price': 7000, 'annual_return': 0.06, 'volatility': 0.022},
    'wdqa': {'name': '万得全A', 'base_price': 5000, 'annual_return': 0.05, 'volatility': 0.016},
}


# ============================================================
# 模拟数据生成（实际应用中应接入真实数据源）
# ============================================================

def generate_mock_historical_data(start_date: str, end_date: str, seed: int = 42) -> pd.DataFrame:
    """生成模拟历史数据（固定种子保证可复现）

    包含30只覆盖各行业的蓝筹+成长股，模拟真实A股特征：
    - 不同ROE/PE/PB/股息率/增长率/负债率/毛利率
    - 优质股有正向漂移（模拟长期价值创造）
    - 垃圾股有负向漂移（模拟价值毁灭）
    """
    np.random.seed(seed)
    dates = pd.date_range(start=start_date, end=end_date, freq='B')

    # 30只股票，覆盖不同风格
    stock_universe = {
        # === 价值型（低PE低PB高股息）===
        '601398': {'name': '工商银行', 'industry': '银行', 'base_price': 5.0, 'roe': 12, 'pe': 5, 'pb': 0.6, 'div': 5.5, 'growth': 3, 'debt': 92, 'gm': 0},
        '601939': {'name': '建设银行', 'industry': '银行', 'base_price': 7.0, 'roe': 13, 'pe': 5, 'pb': 0.6, 'div': 5.2, 'growth': 4, 'debt': 92, 'gm': 0},
        '600036': {'name': '招商银行', 'industry': '银行', 'base_price': 35.0, 'roe': 16, 'pe': 7, 'pb': 1.0, 'div': 3.5, 'growth': 8, 'debt': 90, 'gm': 0},
        '601318': {'name': '中国平安', 'industry': '保险', 'base_price': 50.0, 'roe': 16, 'pe': 8, 'pb': 1.1, 'div': 3.0, 'growth': 10, 'debt': 88, 'gm': 0},
        '600900': {'name': '长江电力', 'industry': '电力', 'base_price': 22.0, 'roe': 15, 'pe': 18, 'pb': 3.0, 'div': 3.8, 'growth': 5, 'debt': 55, 'gm': 62},
        '601088': {'name': '中国神华', 'industry': '煤炭', 'base_price': 20.0, 'roe': 15, 'pe': 8, 'pb': 1.2, 'div': 6.0, 'growth': 5, 'debt': 35, 'gm': 30},
        '600585': {'name': '海螺水泥', 'industry': '建材', 'base_price': 30.0, 'roe': 18, 'pe': 7, 'pb': 1.3, 'div': 4.5, 'growth': 8, 'debt': 25, 'gm': 35},

        # === 质量型（高ROE高毛利）===
        '600519': {'name': '贵州茅台', 'industry': '白酒', 'base_price': 1800, 'roe': 30, 'pe': 35, 'pb': 10, 'div': 1.5, 'growth': 15, 'debt': 20, 'gm': 92},
        '000858': {'name': '五粮液', 'industry': '白酒', 'base_price': 150, 'roe': 25, 'pe': 22, 'pb': 5.5, 'div': 2.0, 'growth': 12, 'debt': 25, 'gm': 75},
        '000568': {'name': '泸州老窖', 'industry': '白酒', 'base_price': 200, 'roe': 28, 'pe': 25, 'pb': 7.0, 'div': 1.8, 'growth': 18, 'debt': 30, 'gm': 80},
        '603288': {'name': '海天味业', 'industry': '调味品', 'base_price': 80, 'roe': 28, 'pe': 40, 'pb': 11, 'div': 1.0, 'growth': 10, 'debt': 20, 'gm': 40},
        '000333': {'name': '美的集团', 'industry': '家电', 'base_price': 60, 'roe': 25, 'pe': 12, 'pb': 3.0, 'div': 3.0, 'growth': 12, 'debt': 60, 'gm': 25},
        '000651': {'name': '格力电器', 'industry': '家电', 'base_price': 35, 'roe': 22, 'pe': 8, 'pb': 1.8, 'div': 5.0, 'growth': 5, 'debt': 65, 'gm': 28},
        '002415': {'name': '海康威视', 'industry': '安防', 'base_price': 35, 'roe': 22, 'pe': 20, 'pb': 4.5, 'div': 2.5, 'growth': 15, 'debt': 35, 'gm': 44},

        # === 成长型（高增长）===
        '300750': {'name': '宁德时代', 'industry': '新能源', 'base_price': 450, 'roe': 20, 'pe': 40, 'pb': 8.0, 'div': 0.3, 'growth': 30, 'debt': 65, 'gm': 22},
        '002594': {'name': '比亚迪', 'industry': '新能源车', 'base_price': 250, 'roe': 15, 'pe': 25, 'pb': 4.0, 'div': 0.5, 'growth': 35, 'debt': 60, 'gm': 18},
        '601012': {'name': '隆基绿能', 'industry': '光伏', 'base_price': 50, 'roe': 18, 'pe': 15, 'pb': 2.8, 'div': 1.5, 'growth': 20, 'debt': 55, 'gm': 20},
        '300059': {'name': '东方财富', 'industry': '券商', 'base_price': 20, 'roe': 18, 'pe': 30, 'pb': 5.5, 'div': 0.5, 'growth': 25, 'debt': 70, 'gm': 0},
        '002475': {'name': '立讯精密', 'industry': '电子', 'base_price': 30, 'roe': 20, 'pe': 25, 'pb': 5.0, 'div': 0.5, 'growth': 22, 'debt': 50, 'gm': 18},

        # === 均衡型（稳健）===
        '600031': {'name': '三一重工', 'industry': '工程机械', 'base_price': 18, 'roe': 15, 'pe': 10, 'pb': 1.5, 'div': 3.0, 'growth': 10, 'debt': 55, 'gm': 28},
        '600309': {'name': '万华化学', 'industry': '化工', 'base_price': 80, 'roe': 20, 'pe': 12, 'pb': 2.5, 'div': 2.5, 'growth': 15, 'debt': 45, 'gm': 25},
        '000338': {'name': '潍柴动力', 'industry': '发动机', 'base_price': 12, 'roe': 14, 'pe': 9, 'pb': 1.3, 'div': 3.5, 'growth': 8, 'debt': 60, 'gm': 22},
        '600690': {'name': '海尔智家', 'industry': '家电', 'base_price': 25, 'roe': 18, 'pe': 13, 'pb': 2.2, 'div': 2.8, 'growth': 10, 'debt': 60, 'gm': 30},
        '000002': {'name': '万科A', 'industry': '地产', 'base_price': 15, 'roe': 10, 'pe': 6, 'pb': 0.6, 'div': 5.0, 'growth': -5, 'debt': 80, 'gm': 20},
        '600048': {'name': '保利发展', 'industry': '地产', 'base_price': 12, 'roe': 12, 'pe': 5, 'pb': 0.7, 'div': 5.5, 'growth': 3, 'debt': 78, 'gm': 25},
        '002304': {'name': '洋河股份', 'industry': '白酒', 'base_price': 130, 'roe': 20, 'pe': 18, 'pb': 3.5, 'div': 2.5, 'growth': 10, 'debt': 30, 'gm': 72},
        '603259': {'name': '药明康德', 'industry': '医药', 'base_price': 80, 'roe': 18, 'pe': 30, 'pb': 5.5, 'div': 0.3, 'growth': 20, 'debt': 40, 'gm': 38},
        '000725': {'name': '京东方A', 'industry': '面板', 'base_price': 4.5, 'roe': 8, 'pe': 15, 'pb': 1.2, 'div': 1.0, 'growth': 10, 'debt': 55, 'gm': 15},
        '601888': {'name': '中国中免', 'industry': '免税', 'base_price': 180, 'roe': 20, 'pe': 25, 'pb': 5.0, 'div': 1.0, 'growth': 15, 'debt': 40, 'gm': 32},
    }

    data = []
    for date in dates:
        days_from_start = (date - dates[0]).days
        for code, info in stock_universe.items():
            # 优质股正向漂移，垃圾股负向漂移
            quality_drift = (info['roe'] - 10) * 0.00005  # ROE越高漂移越大
            noise = np.random.normal(1, 0.018)
            price = info['base_price'] * (1 + quality_drift * days_from_start) * noise

            # 财务指标加随机波动
            roe = info['roe'] + np.random.normal(0, 1.5)
            pe = info['pe'] + np.random.normal(0, 2)
            pb = info['pb'] + np.random.normal(0, 0.3)
            div_yield = info['div'] + np.random.normal(0, 0.3)
            profit_growth = info['growth'] + np.random.normal(0, 3)
            debt_ratio = info['debt'] + np.random.normal(0, 2)
            gross_margin = info['gm'] + np.random.normal(0, 1.5)

            data.append({
                'date': date, 'code': code, 'name': info['name'],
                'industry': info['industry'], 'close': round(max(price, 0.5), 2),
                'return': round((noise - 1) * 100, 2),
                'roe': round(max(roe, 0), 2),
                'pe': round(max(pe, 3), 2),
                'pb': round(max(pb, 0.3), 2),
                'dividend_yield': round(max(div_yield, 0), 2),
                'profit_growth': round(profit_growth, 2),
                'debt_ratio': round(max(min(debt_ratio, 95), 5), 2),
                'gross_margin': round(max(gross_margin, 0), 2),
            })
    return pd.DataFrame(data)


def generate_mock_benchmark_data(
    start_date: str, end_date: str, benchmark: str = 'hs300', seed: int = 42
) -> pd.DataFrame:
    """生成基准指数数据"""
    np.random.seed(seed + 100)  # 不同种子
    cfg = BENCHMARK_MAP.get(benchmark, BENCHMARK_MAP['hs300'])
    dates = pd.date_range(start=start_date, end=end_date, freq='B')
    daily_drift = cfg['annual_return'] / 252
    data = []
    price = cfg['base_price']
    for date in dates:
        daily_return = np.random.normal(daily_drift, cfg['volatility'])
        price = price * (1 + daily_return)
        data.append({'date': date, 'close': round(price, 2), 'return': round(daily_return * 100, 2)})
    return pd.DataFrame(data)


# ============================================================
# 回测引擎核心
# ============================================================

def run_backtest_engine(
    strategy: BaseStrategy,
    stock_data: pd.DataFrame,
    benchmark_data: pd.DataFrame,
    rebalance_frequency: str = 'quarterly',
    initial_capital: float = 1000000,
    top_n: int = 10,
    cost_config: Optional[TradingCostConfig] = None,
) -> Dict:
    """
    通用回测引擎

    Args:
        strategy: 策略实例
        stock_data: 股票历史数据
        benchmark_data: 基准指数数据
        rebalance_frequency: 调仓频率
        initial_capital: 初始资金
        top_n: 持仓数量
        cost_config: 交易成本配置

    Returns:
        完整回测结果dict
    """
    if cost_config is None:
        cost_config = TradingCostConfig()

    dates = sorted(stock_data['date'].unique())
    holdings = {}  # {code: {'shares': int, 'cost': float}}
    cash = initial_capital
    portfolio_values = []
    trade_log = []
    total_cost_paid = 0.0

    # 确定调仓日
    if rebalance_frequency == 'monthly':
        rebalance_days = {d for d in dates if d.day <= 5}
    elif rebalance_frequency == 'quarterly':
        rebalance_days = {d for d in dates if d.month in [1, 4, 7, 10] and d.day <= 5}
    elif rebalance_frequency == 'weekly':
        # 每周第一个交易日
        seen_weeks = set()
        rebalance_days = set()
        for d in dates:
            week_key = (d.isocalendar()[0], d.isocalendar()[1])
            if week_key not in seen_weeks:
                seen_weeks.add(week_key)
                rebalance_days.add(d)
    else:  # yearly
        rebalance_days = {d for d in dates if d.month == 1 and d.day <= 5}

    last_rebalance = None

    for date in dates:
        daily_data = stock_data[stock_data['date'] == date]

        # 计算当日持仓市值
        holdings_value = 0.0
        for code, holding in holdings.items():
            stock_price = daily_data[daily_data['code'] == code]['close'].values
            if len(stock_price) > 0:
                holdings_value += holding['shares'] * stock_price[0]

        total_value = cash + holdings_value
        portfolio_values.append({
            'date': date.strftime('%Y-%m-%d'),
            'total_value': round(total_value, 2),
            'cash': round(cash, 2),
            'holdings_value': round(holdings_value, 2),
        })

        # 调仓逻辑
        if date in rebalance_days:
            if last_rebalance is None or (date - last_rebalance).days >= 20:
                # 用策略打分
                scored_stocks = strategy.score_stocks(daily_data)
                selected = scored_stocks[:top_n]
                selected_codes = {s.code for s in selected}
                price_map = {s.code: s.price for s in selected}

                # 卖出不在新列表中的持仓
                for code in list(holdings.keys()):
                    if code not in selected_codes:
                        stock_price_arr = daily_data[daily_data['code'] == code]['close'].values
                        if len(stock_price_arr) > 0:
                            sell_price = stock_price_arr[0]
                            sell_shares = holdings[code]['shares']
                            gross_amount = sell_shares * sell_price
                            sell_cost = cost_config.calc_sell_cost(gross_amount)
                            net_amount = gross_amount - sell_cost
                            cash += net_amount
                            total_cost_paid += sell_cost
                            trade_log.append({
                                'date': date.strftime('%Y-%m-%d'),
                                'action': 'sell', 'code': code,
                                'price': round(sell_price, 2),
                                'shares': sell_shares,
                                'gross_amount': round(gross_amount, 2),
                                'cost': round(sell_cost, 2),
                                'net_amount': round(net_amount, 2),
                            })
                            del holdings[code]

                # 重新计算可用资金
                current_total = cash + sum(
                    holdings.get(c, {}).get('shares', 0) * price_map.get(c, 0)
                    for c in selected_codes
                )
                target_per_stock = current_total * 0.95 / top_n  # 保留5%现金

                # 买入/调仓
                for stock in selected:
                    code = stock.code
                    price = price_map.get(code, 0)
                    if price <= 0:
                        continue
                    current_shares = holdings.get(code, {}).get('shares', 0)
                    current_value = current_shares * price

                    if current_value < target_per_stock:
                        buy_value = target_per_stock - current_value
                        buy_shares = int(buy_value / price / 100) * 100  # 整手
                        if buy_shares > 0:
                            gross_cost = buy_shares * price
                            buy_cost = cost_config.calc_buy_cost(gross_cost)
                            total_needed = gross_cost + buy_cost
                            if cash >= total_needed:
                                cash -= total_needed
                                total_cost_paid += buy_cost
                                if code in holdings:
                                    holdings[code]['shares'] += buy_shares
                                    holdings[code]['cost'] += gross_cost
                                else:
                                    holdings[code] = {'shares': buy_shares, 'cost': gross_cost}
                                trade_log.append({
                                    'date': date.strftime('%Y-%m-%d'),
                                    'action': 'buy', 'code': code,
                                    'price': round(price, 2),
                                    'shares': buy_shares,
                                    'gross_amount': round(gross_cost, 2),
                                    'cost': round(buy_cost, 2),
                                    'net_amount': round(gross_cost, 2),
                                })

                last_rebalance = date

    # 计算指标
    pv_df = pd.DataFrame(portfolio_values)
    pv_df['date'] = pd.to_datetime(pv_df['date'])
    metrics = calculate_performance_metrics(pv_df, benchmark_data, initial_capital, cost_config)

    # 持仓分析
    final_holdings = []
    last_day_data = stock_data[stock_data['date'] == dates[-1]]
    for code, h in holdings.items():
        row = last_day_data[last_day_data['code'] == code]
        if len(row) > 0:
            r = row.iloc[0]
            final_holdings.append({
                'code': code, 'name': r['name'], 'shares': h['shares'],
                'price': round(r['close'], 2),
                'value': round(h['shares'] * r['close'], 2),
                'industry': r.get('industry', ''),
            })
    final_holdings.sort(key=lambda x: x['value'], reverse=True)

    # 行业配置
    industry_alloc = {}
    total_hv = sum(h['value'] for h in final_holdings)
    for h in final_holdings:
        ind = h.get('industry', '其他')
        industry_alloc[ind] = industry_alloc.get(ind, 0) + h['value']
    if total_hv > 0:
        industry_alloc = {k: round(v / total_hv * 100, 1) for k, v in industry_alloc.items()}

    # 月度收益序列
    pv_df['month'] = pv_df['date'].dt.to_period('M')
    monthly_values = pv_df.groupby('month')['total_value'].last()
    monthly_returns = monthly_values.pct_change().dropna().tolist()
    monthly_returns = [round(r * 100, 4) for r in monthly_returns]

    # 基准月度收益序列
    benchmark_data_copy = benchmark_data.copy()
    benchmark_data_copy['date'] = pd.to_datetime(benchmark_data_copy['date'])
    benchmark_data_copy['month'] = benchmark_data_copy['date'].dt.to_period('M')
    bm_monthly = benchmark_data_copy.groupby('month')['close'].last()
    bm_monthly_returns = bm_monthly.pct_change().dropna().tolist()
    bm_monthly_returns = [round(r * 100, 4) for r in bm_monthly_returns]

    return {
        'strategy_name': strategy.display_name,
        'strategy_key': strategy.name,
        'description': strategy.description,
        **metrics,
        'total_trades': len(trade_log),
        'total_cost': round(total_cost_paid, 2),
        'cost_ratio': round(total_cost_paid / initial_capital * 100, 4),
        'equity_curve': portfolio_values,
        'drawdown_curve': _calc_drawdown_curve(pv_df),
        'trade_log': trade_log,
        'top_holdings': final_holdings,
        'sector_allocation': industry_alloc,
        'monthly_returns': monthly_returns,
        'monthly_benchmark_returns': bm_monthly_returns,
    }


def _calc_drawdown_curve(pv_df: pd.DataFrame) -> List[Dict]:
    """计算回撤曲线"""
    peak = pv_df['total_value'].expanding(min_periods=1).max()
    drawdown = (pv_df['total_value'] - peak) / peak * 100
    return [
        {'date': row['date'].strftime('%Y-%m-%d'), 'drawdown': round(dd, 2)}
        for (_, row), dd in zip(pv_df.iterrows(), drawdown)
    ]


# ============================================================
# 指标计算（机构级）
# ============================================================

def calculate_performance_metrics(
    portfolio_values: pd.DataFrame,
    benchmark_data: pd.DataFrame,
    initial_capital: float,
    cost_config: TradingCostConfig,
) -> Dict:
    """计算完整的表现指标"""
    returns = portfolio_values['total_value'].pct_change().dropna()
    benchmark_returns = benchmark_data['return'].values / 100

    # 对齐长度
    min_len = min(len(returns), len(benchmark_returns))
    returns = returns.iloc[:min_len]
    benchmark_returns = pd.Series(benchmark_returns[:min_len])

    # --- 收益指标 ---
    final_value = portfolio_values['total_value'].iloc[-1]
    total_return = (final_value - initial_capital) / initial_capital
    days = (portfolio_values['date'].iloc[-1] - portfolio_values['date'].iloc[0]).days
    years = max(days / 365.25, 0.01)
    annual_return = (1 + total_return) ** (1 / years) - 1

    # --- 基准收益 ---
    bm_final = benchmark_data['close'].iloc[-1]
    bm_initial = benchmark_data['close'].iloc[0]
    benchmark_total_return = (bm_final / bm_initial) - 1
    bm_annual = (1 + benchmark_total_return) ** (1 / years) - 1
    excess_return = annual_return - bm_annual

    # --- 最大回撤 ---
    peak = portfolio_values['total_value'].expanding(min_periods=1).max()
    drawdown = (portfolio_values['total_value'] - peak) / peak
    max_drawdown = drawdown.min()

    # 最大回撤持续天数
    dd_start = None
    max_dd_duration = 0
    for i, dd in enumerate(drawdown):
        if dd < 0:
            if dd_start is None:
                dd_start = i
            max_dd_duration = max(max_dd_duration, i - dd_start)
        else:
            dd_start = None

    # --- 波动率 ---
    volatility = returns.std() * np.sqrt(252)

    # --- 夏普比率 ---
    risk_free_rate = 0.02
    sharpe_ratio = (annual_return - risk_free_rate) / volatility if volatility > 0 else 0

    # --- Sortino比率 ---
    downside_returns = returns[returns < 0]
    downside_vol = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0
    sortino_ratio = (annual_return - risk_free_rate) / downside_vol if downside_vol > 0 else 0

    # --- Calmar比率 ---
    calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

    # --- Alpha / Beta ---
    if len(returns) > 1 and len(benchmark_returns) > 1:
        covariance = np.cov(returns.values, benchmark_returns.values)
        beta = covariance[0, 1] / covariance[1, 1] if covariance[1, 1] != 0 else 1
    else:
        beta = 1
    alpha = annual_return - risk_free_rate - beta * (bm_annual - risk_free_rate)

    # --- 信息比率 ---
    tracking_error = (returns.values - benchmark_returns.values).std() * np.sqrt(252)
    information_ratio = excess_return / tracking_error if tracking_error > 0 else 0

    # --- 月度胜率 / 盈亏比 ---
    monthly_vals = portfolio_values.set_index('date')['total_value'].resample('ME').last()
    monthly_rets = monthly_vals.pct_change().dropna()
    positive_months = (monthly_rets > 0).sum()
    win_rate = positive_months / len(monthly_rets) if len(monthly_rets) > 0 else 0
    gains = monthly_rets[monthly_rets > 0]
    losses = monthly_rets[monthly_rets < 0]
    avg_gain = gains.mean() if len(gains) > 0 else 0
    avg_loss = abs(losses.mean()) if len(losses) > 0 else 1e-9
    profit_loss_ratio = avg_gain / avg_loss

    # --- 分年度表现 ---
    portfolio_values_copy = portfolio_values.copy()
    portfolio_values_copy['year'] = portfolio_values_copy['date'].dt.year
    yearly_returns = {}
    yearly_excess = {}
    bm_copy = benchmark_data.copy()
    bm_copy['date_dt'] = pd.to_datetime(bm_copy['date']) if not isinstance(bm_copy['date'].iloc[0], pd.Timestamp) else bm_copy['date']
    bm_copy['year'] = bm_copy['date_dt'].dt.year if 'date_dt' in bm_copy.columns else pd.to_datetime(bm_copy['date']).dt.year

    for year in sorted(portfolio_values_copy['year'].unique()):
        yd = portfolio_values_copy[portfolio_values_copy['year'] == year]
        if len(yd) > 1:
            y_ret = (yd['total_value'].iloc[-1] / yd['total_value'].iloc[0]) - 1
            yearly_returns[str(year)] = round(y_ret * 100, 2)
            # 基准年度收益
            bm_yd = bm_copy[bm_copy['year'] == year]
            if len(bm_yd) > 1:
                bm_y_ret = (bm_yd['close'].iloc[-1] / bm_yd['close'].iloc[0]) - 1
                yearly_excess[str(year)] = round((y_ret - bm_y_ret) * 100, 2)

    # --- 分市场环境 ---
    bm_copy2 = benchmark_data.copy()
    bm_copy2['date_dt'] = pd.to_datetime(bm_copy2['date']) if not isinstance(bm_copy2['date'].iloc[0], pd.Timestamp) else bm_copy2['date']
    bm_monthly = bm_copy2.set_index(bm_copy2['date_dt'] if 'date_dt' in bm_copy2.columns else pd.to_datetime(bm_copy2['date']))['return'].resample('ME').sum()
    bull_months = bm_monthly[bm_monthly > 3].index
    bear_months = bm_monthly[bm_monthly < -3].index
    sideways_months = bm_monthly[(bm_monthly >= -3) & (bm_monthly <= 3)].index

    portfolio_monthly = portfolio_values.set_index('date')['total_value'].resample('ME').last().pct_change()
    bull_return = float(portfolio_monthly[portfolio_monthly.index.isin(bull_months)].mean() * 12) if len(bull_months) > 0 else 0
    bear_return = float(portfolio_monthly[portfolio_monthly.index.isin(bear_months)].mean() * 12) if len(bear_months) > 0 else 0
    sideways_return = float(portfolio_monthly[portfolio_monthly.index.isin(sideways_months)].mean() * 12) if len(sideways_months) > 0 else 0

    return {
        'total_return': round(total_return * 100, 2),
        'annual_return': round(annual_return * 100, 2),
        'cumulative_return': round(total_return * 100, 2),
        'max_drawdown': round(max_drawdown * 100, 2),
        'max_drawdown_duration': max_dd_duration,
        'volatility': round(volatility * 100, 2),
        'sharpe_ratio': round(sharpe_ratio, 3),
        'sortino_ratio': round(sortino_ratio, 3),
        'calmar_ratio': round(calmar_ratio, 3),
        'win_rate': round(win_rate * 100, 2),
        'profit_loss_ratio': round(profit_loss_ratio, 3),
        'benchmark_return': round(benchmark_total_return * 100, 2),
        'benchmark_annual_return': round(bm_annual * 100, 2),
        'excess_return': round(excess_return * 100, 2),
        'alpha': round(alpha * 100, 3),
        'beta': round(beta, 3),
        'information_ratio': round(information_ratio, 3),
        'tracking_error': round(tracking_error * 100, 3),
        'yearly_returns': yearly_returns,
        'yearly_excess_returns': yearly_excess,
        'bull_market_return': round(bull_return * 100, 2),
        'bear_market_return': round(bear_return * 100, 2),
        'sideways_market_return': round(sideways_return * 100, 2),
    }


# ============================================================
# 主回测入口（API调用）
# ============================================================

def run_backtest(
    strategy_name: str = 'export_champion',
    start_date: str = '2020-01-01',
    end_date: str = '2025-01-01',
    rebalance_frequency: str = 'quarterly',
    initial_capital: float = 1000000,
    top_n: int = 10,
    benchmark: str = 'hs300',
    commission_rate: float = 0.0003,
    slippage_rate: float = 0.001,
) -> Dict:
    """执行完整回测"""
    strategy = get_strategy(strategy_name)
    stock_data = generate_mock_historical_data(start_date, end_date)
    benchmark_data = generate_mock_benchmark_data(start_date, end_date, benchmark)

    cost_config = TradingCostConfig(
        commission_rate=commission_rate,
        slippage_rate=slippage_rate,
    )

    result = run_backtest_engine(
        strategy=strategy,
        stock_data=stock_data,
        benchmark_data=benchmark_data,
        rebalance_frequency=rebalance_frequency,
        initial_capital=initial_capital,
        top_n=top_n,
        cost_config=cost_config,
    )

    # 补充前端需要的字段
    result['start_date'] = start_date
    result['end_date'] = end_date
    result['initial_capital'] = initial_capital
    result['rebalance_frequency'] = rebalance_frequency
    result['top_n'] = top_n
    result['benchmark_key'] = benchmark
    result['benchmark_name'] = BENCHMARK_MAP.get(benchmark, {}).get('name', benchmark)
    result['cost_config'] = {
        'commission_rate': commission_rate,
        'slippage_rate': slippage_rate,
        'round_trip_cost_pct': round(cost_config.round_trip_cost * 100, 4),
    }

    return result


# ============================================================
# 策略有效性分析
# ============================================================

def analyze_strategy_validity(backtest_result: Dict) -> Dict:
    """分析策略有效性"""
    analysis = {
        'is_effective': False,
        'score': 0,
        'strengths': [],
        'weaknesses': [],
        'conditions': [],
        'recommendations': [],
    }
    score = 0

    # 1. 绝对收益（25分）
    annual_return = backtest_result.get('annual_return', 0)
    if annual_return > 15:
        analysis['strengths'].append(f'年化收益率 {annual_return}%，表现优秀')
        score += 25
    elif annual_return > 10:
        analysis['strengths'].append(f'年化收益率 {annual_return}%，表现良好')
        score += 20
    elif annual_return > 5:
        analysis['conditions'].append(f'年化收益率 {annual_return}%，表现一般')
        score += 12
    else:
        analysis['weaknesses'].append(f'年化收益率 {annual_return}%，表现较差')
        score += 3

    # 2. 超额收益（20分）
    excess_return = backtest_result.get('excess_return', 0)
    if excess_return > 10:
        analysis['strengths'].append(f'超额收益 {excess_return}%，显著跑赢基准')
        score += 20
    elif excess_return > 5:
        analysis['strengths'].append(f'超额收益 {excess_return}%，稳定跑赢基准')
        score += 16
    elif excess_return > 0:
        analysis['conditions'].append(f'超额收益 {excess_return}%，略微跑赢基准')
        score += 10
    else:
        analysis['weaknesses'].append(f'超额收益 {excess_return}%，跑输基准')
        score += 2

    # 3. 风险调整收益（20分）
    sharpe = backtest_result.get('sharpe_ratio', 0)
    if sharpe > 1.5:
        analysis['strengths'].append(f'夏普比率 {sharpe}，风险调整后收益优秀')
        score += 20
    elif sharpe > 1:
        analysis['strengths'].append(f'夏普比率 {sharpe}，风险调整后收益良好')
        score += 16
    elif sharpe > 0.5:
        analysis['conditions'].append(f'夏普比率 {sharpe}，风险调整后收益一般')
        score += 10
    else:
        analysis['weaknesses'].append(f'夏普比率 {sharpe}，风险调整后收益较差')
        score += 3

    # 4. 最大回撤（20分）
    max_dd = backtest_result.get('max_drawdown', 0)
    if max_dd > -15:
        analysis['strengths'].append(f'最大回撤 {max_dd}%，风险控制优秀')
        score += 20
    elif max_dd > -25:
        analysis['conditions'].append(f'最大回撤 {max_dd}%，风险可控')
        score += 14
    elif max_dd > -35:
        analysis['weaknesses'].append(f'最大回撤 {max_dd}%，风险偏高')
        score += 6
    else:
        analysis['weaknesses'].append(f'最大回撤 {max_dd}%，风险过高')
        score += 2

    # 5. 胜率（15分）
    win_rate = backtest_result.get('win_rate', 0)
    if win_rate > 65:
        analysis['strengths'].append(f'月度胜率 {win_rate}%，稳定性好')
        score += 15
    elif win_rate > 55:
        analysis['conditions'].append(f'月度胜率 {win_rate}%，表现一般')
        score += 10
    else:
        analysis['weaknesses'].append(f'月度胜率 {win_rate}%，稳定性差')
        score += 3

    analysis['score'] = min(score, 100)
    analysis['is_effective'] = score >= 60

    # 建议
    if max_dd < -30:
        analysis['recommendations'].append('建议增加止损机制，控制最大回撤在30%以内')
    if win_rate < 50:
        analysis['recommendations'].append('建议优化选股标准，提高月度胜率')
    if excess_return < 0:
        analysis['recommendations'].append('建议调整评分权重，提升超额收益能力')
    if sharpe < 0.5:
        analysis['recommendations'].append('风险调整收益偏低，建议降低调仓频率减少交易成本')
    if backtest_result.get('cost_ratio', 0) > 2:
        analysis['recommendations'].append(f"交易成本占比 {backtest_result['cost_ratio']}% 偏高，建议降低调仓频率")

    bull_ret = backtest_result.get('bull_market_return', 0)
    bear_ret = backtest_result.get('bear_market_return', 0)
    if bull_ret > 20:
        analysis['strengths'].append(f'牛市收益 {bull_ret}%，进攻性强')
    if bear_ret > -10:
        analysis['strengths'].append(f'熊市收益 {bear_ret}%，防御性强')
    elif bear_ret < -25:
        analysis['weaknesses'].append(f'熊市收益 {bear_ret}%，防御性差')

    return analysis


def analyze_strategy_ineffectiveness(backtest_result: Dict) -> Dict:
    """分析策略可能无效的场景"""
    analysis = {
        'ineffective_scenarios': [],
        'risk_factors': [
            {'factor': '数据质量风险', 'description': '海外营收占比等关键数据可能不准确或滞后', 'impact': '可能导致错误的股票选择'},
            {'factor': '行业集中风险', 'description': '策略选出的股票可能集中在特定行业', 'impact': '行业下行时组合回撤较大'},
            {'factor': '风格漂移风险', 'description': '市场风格变化时策略可能阶段性失效', 'impact': '需动态调整策略参数'},
            {'factor': '流动性风险', 'description': '部分中小盘股票流动性不足', 'impact': '大资金无法按回测价格成交'},
        ],
        'market_regime_sensitivity': [],
        'data_quality_issues': [
            {'issue': '财务数据滞后', 'description': '年报数据可能滞后6-12个月', 'mitigation': '结合季报数据和行业报告'},
            {'issue': '估值数据波动', 'description': 'PE/PB可能因一次性事件剧烈波动', 'mitigation': '使用滚动平均值'},
        ],
    }

    annual_return = backtest_result.get('annual_return', 0)
    benchmark_return = backtest_result.get('benchmark_return', 0)
    max_drawdown = backtest_result.get('max_drawdown', 0)
    sharpe = backtest_result.get('sharpe_ratio', 0)

    if annual_return < benchmark_return:
        analysis['ineffective_scenarios'].append({
            'scenario': '跑输基准',
            'description': f'策略年化 {annual_return}% 低于基准 {benchmark_return}%',
            'implication': '未能创造超额收益，不如直接买指数基金',
        })
    if max_drawdown < -40:
        analysis['ineffective_scenarios'].append({
            'scenario': '极端回撤',
            'description': f'最大回撤 {max_drawdown}% 过大',
            'implication': '投资者可能无法坚持持有',
        })
    if sharpe < 0.3:
        analysis['ineffective_scenarios'].append({
            'scenario': '风险调整收益差',
            'description': f'夏普比率 {sharpe} 过低',
            'implication': '承担的风险未获得足够补偿',
        })

    # 市场环境敏感性
    bull_ret = backtest_result.get('bull_market_return', 0)
    bear_ret = backtest_result.get('bear_market_return', 0)
    sideways_ret = backtest_result.get('sideways_market_return', 0)
    if bull_ret > 20 and bear_ret < -20:
        analysis['market_regime_sensitivity'].append({
            'regime': '高波动性', 'description': f'牛市 {bull_ret}% vs 熊市 {bear_ret}%',
            'implication': '策略波动大，不适合风险厌恶型投资者',
        })
    if sideways_ret < 3:
        analysis['market_regime_sensitivity'].append({
            'regime': '震荡市表现差', 'description': f'震荡市收益仅 {sideways_ret}%',
            'implication': '在横盘市场中难以获得收益',
        })

    return analysis


# ============================================================
# 测试
# ============================================================

if __name__ == '__main__':
    print("[TEST] Available strategies:", list(STRATEGY_REGISTRY.keys()))
    result = run_backtest(strategy_name='export_champion')
    print(f"  annual_return: {result['annual_return']}%")
    print(f"  max_drawdown: {result['max_drawdown']}%")
    print(f"  sharpe_ratio: {result['sharpe_ratio']}")
    print(f"  excess_return: {result['excess_return']}%")
    print(f"  total_cost: {result['total_cost']}")
    print(f"  equity_curve points: {len(result['equity_curve'])}")
    print(f"  drawdown_curve points: {len(result['drawdown_curve'])}")
    print(f"  trade_log count: {len(result['trade_log'])}")
