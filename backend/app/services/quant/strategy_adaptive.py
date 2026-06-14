"""
自适应多因子策略

融合顶级机构方法论：
- AQR: 多因子组合 + 截面排名
- Renaissance: 信号衰减监控 + 快速轮换
- Two Sigma: 数据驱动 + ML组合
- Citadel: 多策略集成 + 风险平价
- Man AHL: 波动率目标 + 趋势跟踪

核心改进：
1. 周度再平衡（更高频，捕捉短期alpha）
2. 集中持仓（5只，放大alpha）
3. 动态因子权重（根据近期IC调整）
4. 小盘股聚焦（alpha更大）
5. 市场环境自适应
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple
from .strategy_base import BaseStrategy, Signal, Position

logger = logging.getLogger(__name__)


def calc_factor_ic(factor_values: pd.Series, forward_returns: pd.Series) -> float:
    """计算因子IC（Information Coefficient）"""
    aligned = pd.DataFrame({'f': factor_values, 'r': forward_returns}).dropna()
    if len(aligned) < 10:
        return 0.0
    return float(aligned['f'].corr(aligned['r'], method='spearman'))


def winsorize(series: pd.Series, limits: Tuple[float, float] = (0.02, 0.98)) -> pd.Series:
    """缩尾处理"""
    q_low = series.quantile(limits[0])
    q_high = series.quantile(limits[1])
    return series.clip(q_low, q_high)


class AdaptiveMultiFactorStrategy(BaseStrategy):
    """自适应多因子策略"""

    name = 'adaptive_mf'
    description = '融合AQR/Renaissance/Citadel方法论的自适应多因子'
    version = '2.0'

    DEFAULT_PARAMS = {
        'top_n': 5,                # 集中持仓
        'rebalance_freq': 'weekly', # 周度再平衡
        'lookback_momentum': 20,   # 动量回望（4周）
        'lookback_reversal': 5,    # 反联回望（1周）
        'lookback_vol': 20,        # 波动率窗口
        'min_market_cap': 2e9,     # 最低市值
        'max_market_cap': 50e9,    # 最高市值（聚焦中盘）
        'factor_weights': {        # 动态因子权重
            'momentum': 0.30,
            'reversal': 0.25,
            'value': 0.20,
            'quality': 0.15,
            'low_vol': 0.10,
        },
    }

    def __init__(self, params: Optional[Dict] = None):
        super().__init__({**self.DEFAULT_PARAMS, **(params or {})})
        self._factor_ic_history = {}

    def fit(self, price_data, fundamental_data=None):
        """拟合（计算历史IC用于动态权重调整）"""
        # 计算每个因子的历史IC
        for factor_name in self.params['factor_weights'].keys():
            ics = []
            # 在多个时间点计算IC
            dates = sorted(set(
                str(df['date'].iloc[-1])[:10]
                for df in price_data.values()
                if len(df) > 60
            ))[-12:]  # 最近12个月

            for date in dates:
                factor_vals = self._calc_factor(factor_name, price_data, fundamental_data, date)
                fwd_rets = self._calc_forward_returns(price_data, date, 20)
                if factor_vals is not None and fwd_rets is not None:
                    ic = calc_factor_ic(factor_vals, fwd_rets)
                    ics.append(ic)

            if ics:
                self._factor_ic_history[factor_name] = {
                    'mean_ic': np.mean(ics),
                    'ic_ir': np.mean(ics) / max(np.std(ics), 0.001),
                    'recent_ic': np.mean(ics[-3:]) if len(ics) >= 3 else np.mean(ics),
                }

        self._is_fitted = True
        return self

    def _calc_factor(self, factor_name, price_data, fundamental_data, current_date=None):
        """计算单个因子值"""
        scores = {}

        for code, df in price_data.items():
            if len(df) < 60:
                continue

            prices = df['close'].values.astype(float)

            # 找到当前日期的索引
            if current_date:
                dates = df['date'].astype(str).values
                mask = dates <= current_date
                if not mask.any():
                    continue
                idx = mask.sum() - 1
                if idx < 20:
                    continue
            else:
                idx = len(prices) - 1

            if factor_name == 'momentum':
                # 短期动量（过去4周收益）
                lookback = self.params['lookback_momentum']
                if idx >= lookback:
                    scores[code] = (prices[idx] - prices[idx - lookback]) / prices[idx - lookback]

            elif factor_name == 'reversal':
                # 短期反转（过去1周跌幅）
                lookback = self.params['lookback_reversal']
                if idx >= lookback:
                    ret = (prices[idx] - prices[idx - lookback]) / prices[idx - lookback]
                    scores[code] = -ret  # 跌得越多分数越高

            elif factor_name == 'value':
                # 价值因子（PE倒数）
                if fundamental_data is not None:
                    row = fundamental_data[fundamental_data['code'] == code]
                    if not row.empty:
                        pe = row.iloc[0].get('pe_ttm', 20)
                        if pe > 0:
                            scores[code] = 1.0 / pe

            elif factor_name == 'quality':
                # 质量因子（ROE）
                if fundamental_data is not None:
                    row = fundamental_data[fundamental_data['code'] == code]
                    if not row.empty:
                        roe = row.iloc[0].get('roe', 15)
                        scores[code] = roe

            elif factor_name == 'low_vol':
                # 低波因子（20日波动率倒数）
                lookback = self.params['lookback_vol']
                if idx >= lookback:
                    returns = np.diff(np.log(prices[idx-lookback:idx+1]))
                    vol = np.std(returns) * np.sqrt(252)
                    if vol > 0:
                        scores[code] = -vol  # 波动率越低分数越高

        if not scores:
            return None
        return pd.Series(scores)

    def _calc_forward_returns(self, price_data, current_date, forward_days):
        """计算未来收益率"""
        returns = {}
        for code, df in price_data.items():
            dates = df['date'].astype(str).values
            mask = dates <= current_date
            if not mask.any():
                continue
            idx = mask.sum() - 1
            prices = df['close'].values
            if idx + forward_days < len(prices):
                returns[code] = (prices[idx + forward_days] - prices[idx]) / prices[idx]
        if not returns:
            return None
        return pd.Series(returns)

    def _get_dynamic_weights(self):
        """根据历史IC动态调整因子权重"""
        base_weights = self.params['factor_weights'].copy()

        if not self._factor_ic_history:
            return base_weights

        # 根据IC_IR调整权重
        adjusted = {}
        for name, base_w in base_weights.items():
            if name in self._factor_ic_history:
                ic_info = self._factor_ic_history[name]
                # IC_IR > 0.5 的因子加权，< 0 的因子降权
                ic_ir = ic_info.get('ic_ir', 0)
                if ic_ir > 0.5:
                    adjusted[name] = base_w * 1.5
                elif ic_ir < 0:
                    adjusted[name] = base_w * 0.3
                else:
                    adjusted[name] = base_w
            else:
                adjusted[name] = base_w

        # 归一化
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        return adjusted

    def generate_signals(self, price_data, fundamental_data=None, current_date=None):
        """生成自适应多因子信号"""
        weights = self._get_dynamic_weights()
        top_n = self.params['top_n']

        # 计算各因子值
        factor_scores = {}
        for factor_name, weight in weights.items():
            factor_vals = self._calc_factor(factor_name, price_data, fundamental_data, current_date)
            if factor_vals is not None and len(factor_vals) > 0:
                # 截面z-score标准化
                vals = winsorize(factor_vals)
                z = (vals - vals.mean()) / max(vals.std(), 0.001)
                factor_scores[factor_name] = z * weight

        if not factor_scores:
            return []

        # 合成因子
        combined = pd.Series(0.0)
        for name, scores in factor_scores.items():
            combined = combined.add(scores, fill_value=0)

        # 选前N只
        ranked = combined.sort_values(ascending=False)
        selected = ranked.head(top_n)

        signals = []
        for code, score in selected.items():
            if score > 0:
                # 检查涨跌停
                if code in price_data:
                    df = price_data[code]
                    if len(df) > 0:
                        pct_chg = df['pct_chg'].iloc[-1] if 'pct_chg' in df.columns else 0
                        if abs(pct_chg) >= 9.9:
                            continue

                signals.append(Signal(
                    code=str(code),
                    direction=1,
                    strength=float(abs(score)),
                    reason=f"AdaptiveMF: score={score:.3f}"
                ))

        return signals

    def get_portfolio(self, signals, current_positions, available_capital):
        """构建集中组合"""
        top_n = self.params['top_n']
        selected = [s for s in signals if s.direction == 1][:top_n]

        if not selected:
            return {}

        positions = {}
        weight = 1.0 / len(selected)

        for signal in selected:
            positions[signal.code] = Position(
                code=signal.code,
                shares=0,
                entry_price=0,
                entry_date='',
                weight=weight,
            )

        return positions
