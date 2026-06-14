"""回撤控制分析服务 - 参考顶级机构风控方法论

融合桥水阶梯减仓、Citadel实时P&L监控、文艺复兴波动率调整、
Two Sigma因子归因、AQR动量崩溃保护等方法论。
"""

import logging
import math
from datetime import datetime
from typing import Optional

from app.core.cache import cached
from app.services.right_side_service import fetch_ohlcv

logger = logging.getLogger(__name__)


# ============================================================
# 1. 核心计算函数
# ============================================================

def _compute_equity_curve(records: list[dict]) -> list[dict]:
    """从OHLCV计算权益曲线（以第一天为基准100）"""
    if not records:
        return []
    base = records[0]['close']
    curve = []
    for r in records:
        curve.append({
            'date': r['date'],
            'close': r['close'],
            'equity': round(r['close'] / base * 100, 2) if base else 100,
        })
    return curve


def _compute_running_max(curve: list[dict]) -> list[Optional[float]]:
    """计算滚动最高权益"""
    if not curve:
        return []
    running_max = []
    current_max = curve[0]['equity']
    for point in curve:
        eq = point['equity']
        current_max = max(current_max, eq)
        running_max.append(current_max)
    return running_max


def _detect_drawdowns(curve: list[dict], running_max: list[Optional[float]],
                      min_depth_pct: float = 3.0) -> list[dict]:
    """识别所有回撤事件

    Args:
        curve: 权益曲线
        running_max: 滚动最高值
        min_depth_pct: 最小回撤深度阈值（%），默认3%

    Returns:
        回撤事件列表，每个包含 start_date, trough_date, end_date, depth_pct, duration_days, recovery_days
    """
    if len(curve) < 2:
        return []

    drawdowns = []
    in_drawdown = False
    dd_start_idx = None
    dd_trough_idx = None
    dd_trough_depth = 0

    for i in range(len(curve)):
        peak = running_max[i]
        eq = curve[i]['equity']
        dd_pct = (peak - eq) / peak * 100 if peak > 0 else 0

        if dd_pct > 0.5:  # 进入回撤
            if not in_drawdown:
                in_drawdown = True
                dd_start_idx = i
                dd_trough_idx = i
                dd_trough_depth = dd_pct
            else:
                if dd_pct > dd_trough_depth:
                    dd_trough_depth = dd_pct
                    dd_trough_idx = i
        else:  # 恢复到新高
            if in_drawdown and dd_trough_depth >= min_depth_pct:
                # 计算实际从开始到谷底的天数
                try:
                    start_date = datetime.strptime(curve[dd_start_idx]['date'], '%Y-%m-%d')
                    trough_date = datetime.strptime(curve[dd_trough_idx]['date'], '%Y-%m-%d')
                    end_date = datetime.strptime(curve[i]['date'], '%Y-%m-%d')
                    duration = (trough_date - start_date).days
                    recovery = (end_date - trough_date).days
                except (ValueError, IndexError):
                    duration = dd_trough_idx - dd_start_idx
                    recovery = i - dd_trough_idx

                drawdowns.append({
                    'start_date': curve[dd_start_idx]['date'],
                    'trough_date': curve[dd_trough_idx]['date'],
                    'end_date': curve[i]['date'],
                    'depth_pct': round(dd_trough_depth, 2),
                    'duration_days': max(duration, 0),
                    'recovery_days': max(recovery, 0),
                    'start_equity': curve[dd_start_idx]['equity'],
                    'trough_equity': curve[dd_trough_idx]['equity'],
                    'recovered': True,
                })
            in_drawdown = False
            dd_start_idx = None
            dd_trough_idx = None
            dd_trough_depth = 0

    # 处理当前仍在进行中的回撤
    if in_drawdown and dd_trough_depth >= min_depth_pct:
        try:
            start_date = datetime.strptime(curve[dd_start_idx]['date'], '%Y-%m-%d')
            trough_date = datetime.strptime(curve[dd_trough_idx]['date'], '%Y-%m-%d')
            last_date = datetime.strptime(curve[-1]['date'], '%Y-%m-%d')
            duration = (trough_date - start_date).days
            ongoing = (last_date - trough_date).days
        except (ValueError, IndexError):
            duration = dd_trough_idx - dd_start_idx
            ongoing = len(curve) - 1 - dd_trough_idx

        drawdowns.append({
            'start_date': curve[dd_start_idx]['date'],
            'trough_date': curve[dd_trough_idx]['date'],
            'end_date': None,
            'depth_pct': round(dd_trough_depth, 2),
            'duration_days': max(duration, 0),
            'recovery_days': None,
            'ongoing_days': max(ongoing, 0),
            'start_equity': curve[dd_start_idx]['equity'],
            'trough_equity': curve[dd_trough_idx]['equity'],
            'recovered': False,
        })

    # 按回撤深度排序
    drawdowns.sort(key=lambda x: x['depth_pct'], reverse=True)
    return drawdowns


def _compute_daily_drawdowns(curve: list[dict], running_max: list[Optional[float]]) -> list[dict]:
    """计算每日回撤数据（用于水下曲线图）"""
    daily_dd = []
    for i, point in enumerate(curve):
        peak = running_max[i]
        eq = point['equity']
        dd_pct = (peak - eq) / peak * 100 if peak > 0 else 0
        daily_dd.append({
            'date': point['date'],
            'drawdown_pct': round(-dd_pct, 2),  # 负数表示回撤
            'equity': eq,
            'peak': peak,
        })
    return daily_dd


def _compute_volatility(records: list[dict], window: int = 20) -> list[Optional[float]]:
    """计算滚动波动率（年化）"""
    if len(records) < window + 1:
        return [None] * len(records)

    # 计算日收益率
    returns = []
    for i in range(1, len(records)):
        prev_close = records[i - 1]['close']
        curr_close = records[i]['close']
        if prev_close > 0:
            returns.append((curr_close - prev_close) / prev_close)
        else:
            returns.append(0)

    vol_list = [None]  # 第一天没有收益率
    for i in range(len(returns)):
        if i < window - 1:
            vol_list.append(None)
        else:
            window_returns = returns[i - window + 1: i + 1]
            mean_r = sum(window_returns) / len(window_returns)
            variance = sum((r - mean_r) ** 2 for r in window_returns) / (len(window_returns) - 1)
            daily_vol = math.sqrt(variance)
            annual_vol = daily_vol * math.sqrt(252)
            vol_list.append(round(annual_vol * 100, 2))

    return vol_list


def _compute_volatility_adjusted_drawdown(daily_dd: list[dict], vol_list: list[Optional[float]]) -> list[dict]:
    """波动率调整后的回撤（类似文艺复兴的方法）

    高波动率时期同等回撤的严重程度更低，低波动率时期同等回撤更危险。
    """
    result = []
    for i, dd in enumerate(daily_dd):
        vol = vol_list[i] if i < len(vol_list) else None
        if vol and vol > 0:
            # 标准化回撤 = 回撤 / 波动率
            adj_dd = dd['drawdown_pct'] / vol * 20  # 基准20%波动率
        else:
            adj_dd = dd['drawdown_pct']
        result.append({
            'date': dd['date'],
            'raw_drawdown': dd['drawdown_pct'],
            'vol_adjusted_drawdown': round(adj_dd, 2),
            'volatility': vol,
        })
    return result


def _tiered_warning(current_dd_pct: float, current_duration_days: int = 0) -> dict:
    """阶梯预警系统（类似桥水的阶梯式减仓）

    Level 0: 无回撤 (< 3%)  — 绿灯
    Level 1: 轻度回撤 (3-8%) — 蓝灯，关注
    Level 2: 中度回撤 (8-15%) — 黄灯，减仓至80%
    Level 3: 较大回撤 (15-25%) — 橙灯，减仓至60%
    Level 4: 严重回撤 (25-40%) — 红灯，减仓至40%
    Level 5: 极端回撤 (> 40%) — 深红，减仓至20%

    注意：对于A股/港股，单只股票20-30%回撤在熊市中很常见，
    不应直接建议清仓。只有极端回撤(>40%)才建议大幅减仓。
    长期回撤（>180天）会额外提升一级预警。
    """
    abs_dd = abs(current_dd_pct)

    thresholds = [
        (3, 0, '安全区', 'green', '正常持有，无需调整', 100),
        (8, 1, '关注区', 'blue', '关注走势变化，设好心理止损位', 100),
        (15, 2, '警戒区', 'yellow', '考虑减仓至80%，设置止损线', 80),
        (25, 3, '危险区', 'orange', '减仓至60%，严格执行止损', 60),
        (40, 4, '严重区', 'red', '减仓至40%，考虑对冲或换仓', 40),
        (999, 5, '极端区', 'darkred', '减仓至20%，等待企稳信号再考虑加仓', 20),
    ]

    level = 0
    result = thresholds[0]
    for limit, lv, label, color, action, max_position in thresholds:
        if abs_dd < limit:
            result = (limit, lv, label, color, action, max_position)
            level = lv
            break
    else:
        result = thresholds[-1]
        level = result[1]

    # 长期回撤额外提升一级（超过180天仍未恢复，说明趋势可能已改变）
    if current_duration_days > 180 and level < 5:
        level += 1
        result = thresholds[level]

    _, _, label, color, action, max_position = result
    return {
        'level': level,
        'label': label,
        'color': color,
        'action': action,
        'max_position_pct': max_position,
        'drawdown_pct': round(abs_dd, 2),
        'duration_days': current_duration_days,
    }


def _calmar_ratio(records: list[dict], max_dd_pct: float) -> Optional[float]:
    """Calmar比率 = 年化收益 / 最大回撤"""
    if not records or len(records) < 2 or max_dd_pct == 0:
        return None

    first_close = records[0]['close']
    last_close = records[-1]['close']
    try:
        start_date = datetime.strptime(records[0]['date'], '%Y-%m-%d')
        end_date = datetime.strptime(records[-1]['date'], '%Y-%m-%d')
        years = (end_date - start_date).days / 365.25
    except (ValueError, IndexError):
        years = len(records) / 252

    if years <= 0 or first_close <= 0:
        return None

    total_return = last_close / first_close
    annual_return = total_return ** (1 / years) - 1
    calmar = annual_return / (max_dd_pct / 100) if max_dd_pct > 0 else 0
    return round(calmar, 3)


def _sortino_ratio(records: list[dict], risk_free_rate: float = 0.02) -> Optional[float]:
    """Sortino比率 = (年化收益 - 无风险利率) / 下行波动率

    使用几何年化收益（与Calmar比率一致），下行波动率使用半方差法。
    """
    if not records or len(records) < 20:
        return None

    returns = []
    for i in range(1, len(records)):
        if records[i - 1]['close'] > 0:
            returns.append((records[i]['close'] - records[i - 1]['close']) / records[i - 1]['close'])

    if not returns:
        return None

    # 几何年化收益
    total_return = 1.0
    for r in returns:
        total_return *= (1 + r)
    try:
        years = len(returns) / 252
        annual_return = total_return ** (1 / years) - 1
    except (ValueError, ZeroDivisionError):
        return None

    # 下行波动率（仅负收益参与）
    downside_returns = [r for r in returns if r < 0]
    if not downside_returns:
        return None

    downside_var = sum(r ** 2 for r in downside_returns) / len(downside_returns)
    downside_vol = math.sqrt(downside_var) * math.sqrt(252)

    if downside_vol == 0:
        return None

    sortino = (annual_return - risk_free_rate) / downside_vol
    return round(sortino, 3)


# ============================================================
# 1.5 机构级附加指标
# ============================================================

def _compute_atr(records: list[dict], period: int = 14) -> list[Optional[float]]:
    """Average True Range (ATR)

    TR = max(高-低, |高-昨收|, |低-昨收|)
    ATR = SMA(TR, period)
    """
    if len(records) < 2:
        return [None] * len(records)

    tr_list = [None]  # 第一天无TR
    for i in range(1, len(records)):
        high = records[i].get('high', records[i]['close'])
        low = records[i].get('low', records[i]['close'])
        prev_close = records[i - 1]['close']
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)

    atr_list = [None] * period
    # 初始ATR用前period个TR的简单平均
    first_trs = [t for t in tr_list[1:period + 1] if t is not None]
    if not first_trs:
        return [None] * len(records)

    current_atr = sum(first_trs) / len(first_trs)
    atr_list = [None] * period
    atr_list.append(round(current_atr, 4))

    for i in range(period + 1, len(tr_list)):
        if tr_list[i] is not None:
            current_atr = (current_atr * (period - 1) + tr_list[i]) / period
        atr_list.append(round(current_atr, 4))

    return atr_list


def _compute_var_cvar(returns: list[float], confidence: float = 0.95) -> tuple[Optional[float], Optional[float]]:
    """历史VaR和CVaR（条件风险价值）

    VaR: 在给定置信水平下的最大损失
    CVaR: 超过VaR阈值时的平均损失（尾部风险）
    """
    if not returns or len(returns) < 20:
        return None, None

    sorted_returns = sorted(returns)
    n = len(sorted_returns)

    # VaR = 第 (1-confidence) 分位数的损失（取负值）
    var_index = int(n * (1 - confidence))
    var_index = max(0, min(var_index, n - 1))
    var = -sorted_returns[var_index]

    # CVaR = 低于VaR阈值的所有收益的平均值
    tail_returns = sorted_returns[:var_index + 1]
    cvar = -sum(tail_returns) / len(tail_returns) if tail_returns else var

    # 年化
    annual_var = var * math.sqrt(252)
    annual_cvar = cvar * math.sqrt(252)

    return round(annual_var * 100, 2), round(annual_cvar * 100, 2)


def _compute_ulcer_index(daily_dd: list[dict]) -> Optional[float]:
    """Ulcer Index（溃疡指数）

    UI = sqrt( mean( drawdown_pct^2 ) )
    专门衡量回撤深度和持续时间的综合指标，比标准差更贴合下行风险。

    评级：
    - UI < 5: 优秀（低回撤标的）
    - UI 5-10: 良好
    - UI 10-20: 一般
    - UI > 20: 差（高回撤标的）
    """
    if not daily_dd:
        return None

    dd_squared = [d['drawdown_pct'] ** 2 for d in daily_dd]
    ui = math.sqrt(sum(dd_squared) / len(dd_squared))
    return round(ui, 2)


def _compute_ulcer_performance_index(records: list[dict], ulcer_index: float) -> Optional[float]:
    """Ulcer Performance Index (UPI)

    UPI = (年化收益 - 无风险利率) / Ulcer Index
    类似Sharpe比率但用UI替代标准差，更关注下行风险。
    """
    if not records or len(records) < 20 or not ulcer_index or ulcer_index == 0:
        return None

    total_return = records[-1]['close'] / records[0]['close']
    years = len(records) / 252
    try:
        annual_return = total_return ** (1 / years) - 1
    except (ValueError, ZeroDivisionError):
        return None

    risk_free = 0.02
    upi = (annual_return - risk_free) / (ulcer_index / 100)
    return round(upi, 3)


def _compute_gain_to_pain_ratio(returns: list[float]) -> Optional[float]:
    """Gain-to-Pain Ratio (收益痛苦比)

    GPR = sum(所有收益) / sum(|所有损失|)
    > 1.0 良好, > 2.0 优秀
    """
    if not returns:
        return None

    total_gain = sum(r for r in returns if r > 0)
    total_pain = sum(abs(r) for r in returns if r < 0)

    if total_pain == 0:
        return None

    return round(total_gain / total_pain, 3)


def _compute_drawdown_percentiles(drawdowns: list[dict]) -> dict:
    """回撤深度百分位分析

    提供P10/P25/P50/P75/P90/P95/P99分位数，
    用于评估回撤分布的尾部风险。
    """
    if not drawdowns:
        return {
            'p10': None, 'p25': None, 'p50': None,
            'p75': None, 'p90': None, 'p95': None, 'p99': None,
            'count': 0,
        }

    depths = sorted([d['depth_pct'] for d in drawdowns])
    n = len(depths)

    def _percentile(data: list[float], p: float) -> float:
        """线性插值百分位数"""
        if not data:
            return 0
        k = (len(data) - 1) * p / 100
        f = int(k)
        c = min(f + 1, len(data) - 1)
        d = k - f
        return data[f] + d * (data[c] - data[f])

    return {
        'p10': round(_percentile(depths, 10), 2),
        'p25': round(_percentile(depths, 25), 2),
        'p50': round(_percentile(depths, 50), 2),
        'p75': round(_percentile(depths, 75), 2),
        'p90': round(_percentile(depths, 90), 2),
        'p95': round(_percentile(depths, 95), 2),
        'p99': round(_percentile(depths, 99), 2),
        'count': n,
    }


def _compute_vol_adjusted_position_sizing(
    current_price: float,
    atr: float,
    volatility_pct: float,
    total_capital: float = 100000,
    risk_per_trade_pct: float = 1.0,
    stop_multiplier: float = 2.0,
) -> dict:
    """波动率自适应仓位计算（文艺复兴/Medallion方法论）

    三种方法：
    1. ATR法：仓位 = 风险预算 / (N × ATR)
    2. 波动率反比法：仓位 ∝ 1/σ（低波动高仓位）
    3. Kelly法：f* = (p*b - q) / b（简化版）

    Args:
        current_price: 当前价格
        atr: 当前ATR值
        volatility_pct: 年化波动率（百分比）
        total_capital: 总资金
        risk_per_trade_pct: 单笔风险预算（百分比）
        stop_multiplier: ATR止损倍数
    """
    if current_price <= 0 or atr <= 0:
        return {
            'atr_method': None,
            'vol_inverse_method': None,
            'max_loss_per_trade': None,
            'recommended_shares': None,
            'recommended_pct': None,
        }

    risk_budget = total_capital * risk_per_trade_pct / 100

    # 方法1：ATR法
    risk_per_share = atr * stop_multiplier
    atr_shares = int(risk_budget / risk_per_share) if risk_per_share > 0 else 0
    atr_position_value = atr_shares * current_price
    atr_pct = atr_position_value / total_capital * 100

    # 方法2：波动率反比法（目标组合波动率15%）
    target_vol = 15.0  # 目标年化波动率
    vol_ratio = target_vol / volatility_pct if volatility_pct > 0 else 1.0
    vol_pct = min(vol_ratio * 100, 100)  # 最大100%

    # 方法3：简化Kelly（假设胜率55%，盈亏比1.5:1）
    win_rate = 0.55
    win_loss_ratio = 1.5
    kelly_fraction = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
    kelly_pct = max(0, min(kelly_fraction * 100, 25))  # 上限25%（半Kelly）

    # 取三者中最保守的
    recommended_pct = min(atr_pct, vol_pct, kelly_pct)
    recommended_shares = int(total_capital * recommended_pct / 100 / current_price)

    return {
        'atr_method': {
            'shares': atr_shares,
            'position_value': round(atr_position_value, 0),
            'position_pct': round(atr_pct, 1),
            'risk_per_share': round(risk_per_share, 2),
            'stop_loss_price': round(current_price - risk_per_share, 2),
        },
        'vol_inverse_method': {
            'position_pct': round(vol_pct, 1),
            'target_vol': target_vol,
            'current_vol': volatility_pct,
        },
        'kelly_method': {
            'position_pct': round(kelly_pct, 1),
            'kelly_fraction': round(kelly_fraction * 100, 2),
            'note': '半Kelly，上限25%',
        },
        'recommended': {
            'shares': recommended_shares,
            'position_pct': round(recommended_pct, 1),
            'position_value': round(recommended_shares * current_price, 0),
            'max_loss': round(recommended_shares * risk_per_share, 0),
        },
        'total_capital': total_capital,
    }


def _compute_stop_loss_levels(
    current_price: float,
    atr: float,
    recent_high: float,
    volatility_pct: float,
    holding_days: int = 0,
    ma20: Optional[float] = None,
    ma60: Optional[float] = None,
) -> dict:
    """多模式止损计算

    支持6种止损方法，每种给出具体止损价位：
    1. ATR吊灯止损
    2. 均线止损
    3. SAR近似（基于ATR加速因子）
    4. 固定百分比
    5. 波动率止损
    6. 时间止损（仅提示）
    """
    if current_price <= 0:
        return {}

    results = {}

    # 1. ATR吊灯止损
    if atr > 0:
        for n in [2, 2.5, 3]:
            stop = round(recent_high - n * atr, 2)
            pct = round((current_price - stop) / current_price * 100, 2)
            results[f'atr_{n}x'] = {
                'stop_price': stop,
                'loss_pct': pct,
                'label': f'ATR吊灯止损 (N={n})',
            }

    # 2. 均线止损
    if ma20 and ma20 > 0:
        pct = round((current_price - ma20) / current_price * 100, 2)
        results['ma20'] = {
            'stop_price': round(ma20, 2),
            'loss_pct': pct,
            'label': 'MA20止损（短线）',
        }
    if ma60 and ma60 > 0:
        pct = round((current_price - ma60) / current_price * 100, 2)
        results['ma60'] = {
            'stop_price': round(ma60, 2),
            'loss_pct': pct,
            'label': 'MA60止损（中线）',
        }

    # 3. SAR近似（AF加速因子法）
    if atr > 0:
        # SAR初始AF=0.02，每创新高+0.02，最大0.2
        af = min(0.02 + holding_days * 0.002, 0.2)
        sar_stop = round(recent_high - (2 / af) * atr, 2) if af > 0 else current_price
        pct = round((current_price - sar_stop) / current_price * 100, 2)
        results['sar_approx'] = {
            'stop_price': sar_stop,
            'loss_pct': pct,
            'label': f'SAR近似止损 (AF={af:.2f})',
        }

    # 4. 固定百分比止损
    for p in [5, 8, 10]:
        stop = round(current_price * (1 - p / 100), 2)
        results[f'fixed_{p}pct'] = {
            'stop_price': stop,
            'loss_pct': p,
            'label': f'固定{p}%止损',
        }

    # 5. 波动率止损（2倍标准差）
    if volatility_pct > 0:
        daily_vol = volatility_pct / 100 / math.sqrt(252)
        stop = round(current_price * (1 - 2 * daily_vol), 2)
        pct = round((current_price - stop) / current_price * 100, 2)
        results['vol_2std'] = {
            'stop_price': stop,
            'loss_pct': pct,
            'label': '波动率止损 (2σ)',
        }

    # 6. 阶梯止盈锁利
    results['trailing_lock'] = {
        'levels': [
            {'profit_pct': 5, 'stop_type': '保本', 'stop_price': current_price},
            {'profit_pct': 10, 'stop_type': '锁定5%', 'stop_price': round(current_price * 1.05, 2)},
            {'profit_pct': 20, 'stop_type': '锁定10%', 'stop_price': round(current_price * 1.10, 2)},
        ],
        'label': '阶梯止盈锁利',
    }

    # 7. 时间止损
    results['time_stop'] = {
        'trigger_days': 20,
        'current_days': holding_days,
        'status': '已触发' if holding_days > 20 else '未触发',
        'label': '时间止损（20天未启动）',
    }

    return results


def _estimate_recovery_time(drawdowns: list[dict]) -> dict:
    """估计当前回撤的预期恢复时间

    策略：
    1. 有多个已恢复回撤 → 用相似深度的历史恢复时间
    2. 只有1个已恢复回撤 → 用深度比例缩放 + 经验基准
    3. 无已恢复回撤 → 用经验基准（A股/港股经验值：每1%回撤约需15-30天恢复）
    4. 当前回撤已持续很久 → 考虑已持续时间，给出更保守的估计
    """
    recovered = [d for d in drawdowns if d.get('recovered')]
    ongoing = [d for d in drawdowns if not d.get('recovered') and d.get('ongoing_days') is not None]

    # 已恢复回撤的统计
    recovery_days = [d['recovery_days'] for d in recovered if d.get('recovery_days') is not None]
    avg_recovery = sum(recovery_days) / len(recovery_days) if recovery_days else None
    sorted_days = sorted(recovery_days) if recovery_days else []
    median_recovery = sorted_days[len(sorted_days) // 2] if sorted_days else None
    max_recovery = max(recovery_days) if recovery_days else None

    # 当前回撤信息
    current_depth = 0
    current_ongoing_days = 0
    if ongoing:
        current_depth = ongoing[0]['depth_pct']
        current_ongoing_days = ongoing[0].get('ongoing_days', 0)

    # 经验基准：A股/港股，每1%回撤平均需要约20天恢复（经验值）
    # 深度越大，恢复越慢（非线性关系）
    def _heuristic_estimate(depth_pct: float) -> int:
        """基于经验的恢复时间估计"""
        if depth_pct <= 5:
            return int(depth_pct * 10)  # 浅回撤：每1%约10天
        elif depth_pct <= 15:
            return int(50 + (depth_pct - 5) * 15)  # 中等：每1%约15天
        elif depth_pct <= 30:
            return int(200 + (depth_pct - 15) * 20)  # 深回撤：每1%约20天
        else:
            return int(500 + (depth_pct - 30) * 30)  # 极深：每1%约30天

    # 计算估计值
    est = None
    confidence = '数据不足'

    if current_depth > 0:
        # 优先用历史相似深度的数据
        if len(recovery_days) >= 3:
            similar = [d for d in recovered if abs(d['depth_pct'] - current_depth) < current_depth * 0.5]
            if similar:
                est = sum(d['recovery_days'] for d in similar) / len(similar)
                confidence = '较高'
            else:
                # 用深度比例缩放
                avg_depth = sum(d['depth_pct'] for d in recovered) / len(recovered)
                est = avg_recovery * (current_depth / avg_depth) if avg_depth > 0 else _heuristic_estimate(current_depth)
                confidence = '中等'
        elif len(recovery_days) == 1:
            # 只有1个数据点，用深度比例缩放 + 经验基准加权
            hist_est = recovery_days[0] * (current_depth / recovered[0]['depth_pct']) if recovered[0]['depth_pct'] > 0 else 0
            heuristic = _heuristic_estimate(current_depth)
            # 权重：历史30%，经验70%（因为只有1个数据点不可靠）
            est = hist_est * 0.3 + heuristic * 0.7
            confidence = '参考值'
        elif len(recovery_days) == 2:
            # 2个数据点，用深度比例 + 经验基准加权
            avg_historical = sum(d['recovery_days'] * (current_depth / d['depth_pct']) for d in recovered) / len(recovered) if all(d['depth_pct'] > 0 for d in recovered) else 0
            heuristic = _heuristic_estimate(current_depth)
            est = avg_historical * 0.5 + heuristic * 0.5
            confidence = '参考值'
        else:
            # 无历史数据，纯经验
            est = _heuristic_estimate(current_depth)
            confidence = '经验估计'

        # 如果当前回撤已持续很久，剩余恢复时间应该更少
        if est and current_ongoing_days > est * 0.5:
            # 已经恢复了一部分，剩余时间 = 总估计 - 已持续时间
            remaining = max(est - current_ongoing_days, est * 0.3)  # 至少保留30%
            est = remaining
            confidence += '（已考虑持续时间）'

    return {
        'avg_recovery_days': round(avg_recovery) if avg_recovery else None,
        'median_recovery_days': median_recovery,
        'max_recovery_days': max_recovery,
        'estimated_recovery_days': round(est) if est else None,
        'confidence': confidence,
        'current_ongoing_days': current_ongoing_days,
        'current_depth': current_depth,
        'heuristic_baseline': _heuristic_estimate(current_depth) if current_depth > 0 else None,
    }


def _compute_drawdown_distribution(drawdowns: list[dict]) -> dict:
    """回撤分布统计"""
    if not drawdowns:
        return {
            'count': 0,
            'avg_depth': 0,
            'median_depth': 0,
            'max_depth': 0,
            'min_depth': 0,
            'histogram': [],
        }

    depths = [d['depth_pct'] for d in drawdowns]
    avg_depth = sum(depths) / len(depths)
    sorted_depths = sorted(depths)
    median_depth = sorted_depths[len(sorted_depths) // 2]

    # 构建直方图
    bins = [0, 3, 5, 8, 10, 15, 20, 30, 50, 100]
    histogram = []
    for i in range(len(bins) - 1):
        count = sum(1 for d in depths if bins[i] <= d < bins[i + 1])
        if count > 0:
            histogram.append({
                'range': f'{bins[i]}-{bins[i + 1]}%',
                'count': count,
                'label': f'{bins[i]}%~{bins[i + 1]}%',
            })

    return {
        'count': len(drawdowns),
        'avg_depth': round(avg_depth, 2),
        'median_depth': round(median_depth, 2),
        'max_depth': round(max(depths), 2),
        'min_depth': round(min(depths), 2),
        'histogram': histogram,
    }


def _score_drawdown_health(max_dd: float, current_dd: float, calmar: Optional[float],
                           avg_recovery: Optional[int], vol: Optional[float],
                           current_duration_days: int = 0, drawdown_count: int = 0) -> tuple:
    """综合评分（0-100）

    评分维度：
    1. 历史最大回撤（-30分）：反映标的的极端风险
    2. 当前回撤深度（-25分）：当前风险暴露
    3. 当前回撤持续时间（-10分）：长期回撤比短期更危险
    4. Calmar比率（-20分）：风险调整后收益
    5. 恢复能力（-10分）：历史恢复速度
    6. 波动率（-5分）：波动越大越难预测
    """
    score = 100
    signals = []

    # 1. 最大回撤扣分 (最多-30分)
    if max_dd > 50:
        score -= 30
        signals.append('⚠️ 历史最大回撤超过50%，极端风险')
    elif max_dd > 35:
        score -= 22
        signals.append('⚠️ 历史最大回撤超过35%，高风险标的')
    elif max_dd > 20:
        score -= 15
        signals.append('历史最大回撤超过20%，波动较大')
    elif max_dd > 10:
        score -= 8

    # 2. 当前回撤扣分 (最多-25分)
    if current_dd > 30:
        score -= 25
        signals.append('🚨 当前回撤超过30%，深度套牢区')
    elif current_dd > 20:
        score -= 20
        signals.append('🔴 当前回撤超过20%，严重浮亏')
    elif current_dd > 15:
        score -= 15
        signals.append('🟠 当前回撤超过15%，需警惕')
    elif current_dd > 10:
        score -= 10
        signals.append('🟡 当前回撤超过10%，关注中')
    elif current_dd > 5:
        score -= 5

    # 3. 回撤持续时间扣分 (最多-10分)
    if current_duration_days > 365:
        score -= 10
        signals.append(f'回撤已持续{current_duration_days}天（超1年），趋势可能已改变')
    elif current_duration_days > 180:
        score -= 7
        signals.append(f'回撤已持续{current_duration_days}天（超半年）')
    elif current_duration_days > 90:
        score -= 4
    elif current_duration_days > 30:
        score -= 2

    # 4. Calmar比率 (最多-20分)
    if calmar is not None:
        if calmar < 0:
            score -= 20
            signals.append('Calmar比率为负，收益不及无风险利率')
        elif calmar < 0.2:
            score -= 15
            signals.append('Calmar比率极低，风险收益比差')
        elif calmar < 0.5:
            score -= 8
        elif calmar < 1.0:
            score -= 3

    # 5. 恢复能力 (最多-10分)
    if avg_recovery is not None:
        if avg_recovery > 180:
            score -= 10
            signals.append('历史平均恢复时间超过半年')
        elif avg_recovery > 90:
            score -= 6
        elif avg_recovery > 60:
            score -= 3

    # 6. 波动率 (最多-5分)
    if vol is not None:
        if vol > 50:
            score -= 5
            signals.append('波动率极高（>50%），难以预测')
        elif vol > 35:
            score -= 3
        elif vol > 25:
            score -= 1

    score = max(0, min(100, score))

    if score >= 80:
        verdict = '健康'
    elif score >= 65:
        verdict = '一般'
    elif score >= 45:
        verdict = '较差'
    else:
        verdict = '危险'

    return score, verdict, signals


# ============================================================
# 2. 主分析入口
# ============================================================

@cached(ttl_seconds=300, key_prefix="drawdown")
def analyze_drawdown(stock_code: str, days: int = 500) -> dict:
    """回撤控制分析主入口

    输出机构级指标：
    - 最大回撤（精确到每日）+ 回撤事件识别
    - VaR / CVaR（95%和99%置信度）
    - Ulcer Index / Ulcer Performance Index
    - 波动率自适应仓位（ATR法 + 波动率反比法 + Kelly法）
    - 多模式止损价计算（6种方法）
    - 历史回撤百分位分布
    - 阶梯预警 + 综合健康评分
    """
    try:
        # 1. 获取数据
        records = fetch_ohlcv(stock_code, days)
        if not records or len(records) < 10:
            return {'error': f'无法获取 {stock_code} 的行情数据，或数据量不足'}

        # 2. 计算权益曲线
        curve = _compute_equity_curve(records)
        running_max = _compute_running_max(curve)

        # 3. 识别历史回撤
        drawdowns = _detect_drawdowns(curve, running_max, min_depth_pct=3.0)

        # 4. 每日回撤数据（水下曲线）
        daily_dd = _compute_daily_drawdowns(curve, running_max)

        # 5. 波动率
        vol_list = _compute_volatility(records)
        current_vol = next((v for v in reversed(vol_list) if v is not None), None)

        # 6. 波动率调整回撤
        vol_adj_dd = _compute_volatility_adjusted_drawdown(daily_dd, vol_list)

        # 7. 当前回撤状态
        current_dd_pct = abs(daily_dd[-1]['drawdown_pct']) if daily_dd else 0
        current_peak = running_max[-1] if running_max else 100
        current_equity = curve[-1]['equity'] if curve else 100
        is_at_peak = current_dd_pct < 0.5

        # 8. 最大回撤（事件 + 每日 取最大值）
        max_dd_pct = max((d['depth_pct'] for d in drawdowns), default=0)
        daily_max_dd = max((abs(d['drawdown_pct']) for d in daily_dd), default=0)
        max_dd_pct = max(max_dd_pct, daily_max_dd)

        # 9. Calmar 比率
        calmar = _calmar_ratio(records, max_dd_pct)

        # 10. Sortino 比率
        sortino = _sortino_ratio(records)

        # 11. 恢复分析
        recovery_stats = _estimate_recovery_time(drawdowns)

        # 12. 回撤分布
        distribution = _compute_drawdown_distribution(drawdowns)

        # 13. 当前回撤持续天数
        current_dd_duration = 0
        ongoing_drawdowns = [d for d in drawdowns if not d.get('recovered')]
        if ongoing_drawdowns:
            current_dd_duration = ongoing_drawdowns[0].get('ongoing_days', 0) + ongoing_drawdowns[0].get('duration_days', 0)

        # 14. 阶梯预警
        warning = _tiered_warning(current_dd_pct, current_dd_duration)

        # 15. 综合评分
        score, verdict, signals = _score_drawdown_health(
            max_dd_pct, current_dd_pct, calmar,
            recovery_stats.get('avg_recovery_days'), current_vol,
            current_dd_duration, len(drawdowns)
        )

        # ============================================================
        # 16. 机构级附加指标
        # ============================================================

        # 日收益率（用于VaR/CVaR/GPR）
        daily_returns = []
        for i in range(1, len(records)):
            if records[i - 1]['close'] > 0:
                daily_returns.append((records[i]['close'] - records[i - 1]['close']) / records[i - 1]['close'])

        # VaR / CVaR
        var_95, cvar_95 = _compute_var_cvar(daily_returns, 0.95)
        var_99, cvar_99 = _compute_var_cvar(daily_returns, 0.99)

        # Ulcer Index
        ulcer_index = _compute_ulcer_index(daily_dd)
        upi = _compute_ulcer_performance_index(records, ulcer_index) if ulcer_index else None

        # Gain-to-Pain Ratio
        gpr = _compute_gain_to_pain_ratio(daily_returns)

        # ATR
        atr_list = _compute_atr(records)
        current_atr = next((v for v in reversed(atr_list) if v is not None), None)

        # 回撤百分位分析
        dd_percentiles = _compute_drawdown_percentiles(drawdowns)

        # 波动率自适应仓位
        current_price = records[-1]['close']
        recent_high = max((r.get('high', r['close']) for r in records[-60:]), default=current_price)
        # 计算MA20和MA60
        ma20 = None
        ma60 = None
        if len(records) >= 20:
            ma20 = sum(r['close'] for r in records[-20:]) / 20
        if len(records) >= 60:
            ma60 = sum(r['close'] for r in records[-60:]) / 60

        position_sizing = _compute_vol_adjusted_position_sizing(
            current_price=current_price,
            atr=current_atr or 0,
            volatility_pct=current_vol or 20,
        )

        # 多模式止损
        stop_loss = _compute_stop_loss_levels(
            current_price=current_price,
            atr=current_atr or 0,
            recent_high=recent_high,
            volatility_pct=current_vol or 20,
            holding_days=current_dd_duration,
            ma20=ma20,
            ma60=ma60,
        )

        # 图表数据
        equity_dates = [p['date'] for p in curve]
        equity_values = [p['equity'] for p in curve]
        peak_values = running_max
        underwater_dates = [d['date'] for d in daily_dd]
        underwater_values = [d['drawdown_pct'] for d in daily_dd]

        # ATR图表数据（最近120天）
        atr_chart = []
        for i in range(max(0, len(records) - 120), len(records)):
            if atr_list[i] is not None:
                atr_chart.append({
                    'date': records[i]['date'],
                    'atr': round(atr_list[i], 2),
                    'atr_pct': round(atr_list[i] / records[i]['close'] * 100, 2) if records[i]['close'] > 0 else 0,
                })

        return {
            'code': stock_code,
            'days': days,
            'data_count': len(records),
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),

            # 核心指标
            'current_drawdown_pct': round(current_dd_pct, 2),
            'max_drawdown_pct': round(max_dd_pct, 2),
            'is_at_peak': is_at_peak,
            'current_equity': round(current_equity, 2),
            'current_peak': round(current_peak, 2),
            'calmar_ratio': calmar,
            'sortino_ratio': sortino,
            'current_volatility': current_vol,
            'current_drawdown_days': current_dd_duration,
            'current_price': round(current_price, 2),

            # 综合评分
            'score': score,
            'verdict': verdict,
            'signals': signals,

            # 阶梯预警
            'warning': warning,

            # 仓位建议（桥水阶梯式）
            'position_advice': {
                'max_position_pct': warning['max_position_pct'],
                'action': warning['action'],
                'level': warning['level'],
                'duration_days': current_dd_duration,
            },

            # 波动率自适应仓位（文艺复兴方法论）
            'position_sizing': position_sizing,

            # 多模式止损
            'stop_loss': stop_loss,

            # VaR / CVaR
            'var_cvar': {
                'var_95': var_95,
                'cvar_95': cvar_95,
                'var_99': var_99,
                'cvar_99': cvar_99,
            },

            # Ulcer Index
            'ulcer_index': ulcer_index,
            'ulcer_performance_index': upi,
            'gain_to_pain_ratio': gpr,

            # ATR
            'current_atr': round(current_atr, 2) if current_atr else None,
            'current_atr_pct': round(current_atr / current_price * 100, 2) if current_atr and current_price > 0 else None,

            # MA
            'ma20': round(ma20, 2) if ma20 else None,
            'ma60': round(ma60, 2) if ma60 else None,
            'recent_high': round(recent_high, 2),

            # 历史回撤
            'drawdowns': drawdowns[:10],
            'drawdown_count': len(drawdowns),
            'distribution': distribution,
            'drawdown_percentiles': dd_percentiles,

            # 恢复分析
            'recovery': recovery_stats,

            # 图表数据
            'chart': {
                'equity': {
                    'dates': equity_dates,
                    'values': equity_values,
                    'peaks': peak_values,
                },
                'underwater': {
                    'dates': underwater_dates,
                    'values': underwater_values,
                },
                'vol_adjusted': vol_adj_dd[-120:] if len(vol_adj_dd) > 120 else vol_adj_dd,
                'distribution': distribution.get('histogram', []),
                'atr': atr_chart,
            },
        }

    except Exception as e:
        logger.error(f"analyze_drawdown failed for {stock_code}: {e}", exc_info=True)
        return {'error': f'分析失败: {str(e)}'}
