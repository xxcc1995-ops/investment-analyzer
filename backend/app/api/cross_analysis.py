"""交叉分析模块 - 机构级多维度公司分析

提供：
1. 多指标交叉验证（ROE-利润率-负债-现金流一致性检查）
2. 行业轮动分析（相对竞争力评估）
3. 估值-盈利-动量三维分析
4. 相关性分析（指标间趋势相关性）
5. 综合评分模型（8维度加权评分）
"""

import math
import logging
from fastapi import APIRouter, HTTPException
from app.services.data_service import DataService, _get_annual_report
from datetime import datetime
from typing import Optional

router = APIRouter()
data_service = DataService()
logger = logging.getLogger(__name__)

# ============ 行业竞品映射表（扩展版） ============

INDUSTRY_PEERS = {
    # 白酒
    '600519': ['600519', '000858', '000568', '600809', '002304', '000596'],
    '000858': ['600519', '000858', '000568', '600809', '002304', '000596'],
    '000568': ['600519', '000858', '000568', '600809', '002304', '000596'],
    '600809': ['600519', '000858', '000568', '600809', '002304', '000596'],
    '002304': ['600519', '000858', '000568', '600809', '002304', '000596'],
    '000596': ['600519', '000858', '000568', '600809', '002304', '000596'],
    '000799': ['600519', '000858', '000568', '600809', '002304', '000596', '000799'],

    # 银行
    '601398': ['601398', '601288', '601939', '601988', '600036', '601166', '600016', '601818'],
    '601288': ['601398', '601288', '601939', '601988', '600036', '601166', '600016', '601818'],
    '601939': ['601398', '601288', '601939', '601988', '600036', '601166', '600016', '601818'],
    '601988': ['601398', '601288', '601939', '601988', '600036', '601166', '600016', '601818'],
    '600036': ['601398', '601288', '601939', '601988', '600036', '601166', '600016', '601818'],
    '601166': ['601398', '601288', '601939', '601988', '600036', '601166', '600016', '601818'],
    '600016': ['601398', '601288', '601939', '601988', '600036', '601166', '600016', '601818'],
    '601818': ['601398', '601288', '601939', '601988', '600036', '601166', '600016', '601818'],

    # 家电
    '000333': ['000333', '000651', '600690', '002032'],
    '000651': ['000333', '000651', '600690', '002032'],
    '600690': ['000333', '000651', '600690', '002032'],
    '002032': ['000333', '000651', '600690', '002032'],

    # 新能源/锂电
    '300750': ['300750', '002594', '600438', '601012'],
    '002594': ['300750', '002594', '600438', '601012'],

    # 医药
    '600276': ['600276', '000538', '002001', '600196', '300015'],
    '000538': ['600276', '000538', '002001', '600196', '300015'],
    '600196': ['600276', '000538', '002001', '600196', '300015'],

    # 互联网/科技
    '00700': ['00700', '09988', '03690', '09618', '09888'],
    '09988': ['00700', '09988', '03690', '09618', '09888'],

    # 能源
    '601088': ['601088', '600188', '601857', '600028', '601898'],
    '601857': ['601088', '600188', '601857', '600028', '601898'],
    '600028': ['601088', '600188', '601857', '600028', '601898'],

    # 电力
    '600900': ['600900', '600886', '600795', '600023', '601985'],
    '600886': ['600900', '600886', '600795', '600023', '601985'],

    # 保险
    '601318': ['601318', '601628', '601601', '02628'],
    '601628': ['601318', '601628', '601601', '02628'],

    # 地产
    '001979': ['001979', '600048', '000002', '601155'],
    '600048': ['001979', '600048', '000002', '601155'],
    '000002': ['001979', '600048', '000002', '601155'],

    # 钢铁
    '600019': ['600019', '601003', '000898', '000709'],
    '601003': ['600019', '601003', '000898', '000709'],

    # 汽车
    '002594': ['002594', '601238', '000625', '600104'],
    '601238': ['002594', '601238', '000625', '600104'],

    # 证券
    '601211': ['601211', '600030', '601688', '601066', '600999'],
    '600030': ['601211', '600030', '601688', '601066', '600999'],

    # 食品饮料（非白酒）
    '600887': ['600887', '002714', '603288', '600597'],
    '603288': ['600887', '002714', '603288', '600597'],
}

# 行业名称映射
INDUSTRY_NAMES = {
    '600519': '白酒', '000858': '白酒', '000568': '白酒', '600809': '白酒',
    '002304': '白酒', '000596': '白酒', '000799': '白酒',
    '601398': '银行', '601288': '银行', '601939': '银行', '601988': '银行',
    '600036': '银行', '601166': '银行', '600016': '银行', '601818': '银行',
    '000333': '家电', '000651': '家电', '600690': '家电', '002032': '家电',
    '300750': '新能源', '002594': '新能源',
    '600276': '医药', '000538': '医药', '600196': '医药', '300015': '医药',
    '00700': '互联网', '09988': '互联网', '03690': '互联网', '09618': '互联网',
    '601088': '能源', '600188': '能源', '601857': '能源', '600028': '能源', '601898': '能源',
    '600900': '电力', '600886': '电力', '600795': '电力',
    '601318': '保险', '601628': '保险', '601601': '保险',
    '001979': '地产', '600048': '地产', '000002': '地产', '601155': '地产',
    '600019': '钢铁', '601003': '钢铁', '000898': '钢铁',
    '601238': '汽车', '000625': '汽车',
    '601211': '证券', '600030': '证券', '601688': '证券',
    '600887': '食品饮料', '603288': '食品饮料',
}


# ============ 工具函数 ============

def get_peer_codes(stock_code: str) -> list:
    """获取同行业竞品代码"""
    return INDUSTRY_PEERS.get(stock_code, [stock_code])


def get_industry_name(stock_code: str) -> str:
    """获取行业名称"""
    return INDUSTRY_NAMES.get(stock_code, '未知行业')


def _safe(val, default=0.0):
    """安全取值，None返回default"""
    return val if val is not None else default


def _percentile_rank(value: float, values: list) -> Optional[float]:
    """计算value在values中的百分位排名 (0-100)"""
    if not values or value is None:
        return None
    below = sum(1 for v in values if v <= value)
    return round(below / len(values) * 100, 1)


def _calc_trend_slope(values: list) -> Optional[float]:
    """计算趋势斜率（最小二乘法线性回归），正值=上升趋势"""
    if not values or len(values) < 2:
        return None
    n = len(values)
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    if denominator == 0:
        return 0
    return round(numerator / denominator, 4)


def _calc_volatility(values: list) -> Optional[float]:
    """计算波动系数(CV = std/mean)，越低越稳定"""
    if not values or len(values) < 2:
        return None
    mean = sum(values) / len(values)
    if mean == 0:
        return None
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    std = math.sqrt(variance) if variance > 0 else 0
    return round(std / abs(mean) * 100, 2)  # 百分比形式


def _calc_correlation(xs: list, ys: list) -> Optional[float]:
    """计算Pearson相关系数"""
    if not xs or not ys or len(xs) != len(ys) or len(xs) < 3:
        return None
    n = len(xs)
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    cov = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / (n - 1)
    x_std = math.sqrt(sum((x - x_mean) ** 2 for x in xs) / (n - 1))
    y_std = math.sqrt(sum((y - y_mean) ** 2 for y in ys) / (n - 1))
    if x_std == 0 or y_std == 0:
        return None
    return round(cov / (x_std * y_std), 3)


def _calc_cagr(start: float, end: float, years: int) -> Optional[float]:
    """计算复合年增长率"""
    if not start or start <= 0 or not end or end <= 0 or years <= 0:
        return None
    try:
        return round((pow(end / start, 1.0 / years) - 1) * 100, 2)
    except (ZeroDivisionError, ValueError, OverflowError):
        return None


def analyze_lifecycle_stage(reports: list) -> dict:
    """分析公司所处生命周期阶段（增强版）"""
    if not reports or len(reports) < 2:
        return {'stage': '数据不足', 'confidence': 0, 'details': {}}

    recent = reports[:min(3, len(reports))]

    revenue_growth = [_safe(r.get('revenue_growth')) for r in recent]
    profit_growth = [_safe(r.get('profit_growth')) for r in recent]
    roe_values = [_safe(r.get('roe')) for r in recent]

    avg_rev_growth = sum(revenue_growth) / len(revenue_growth)
    avg_profit_growth = sum(profit_growth) / len(profit_growth)
    avg_roe = sum(roe_values) / len(roe_values)

    # 趋势一致性检查
    rev_trend = _calc_trend_slope(revenue_growth)
    profit_trend = _calc_trend_slope(profit_growth)

    # 判断阶段
    if avg_rev_growth > 20 and avg_profit_growth > 20:
        stage = '高速成长期'
        confidence = 90 if avg_roe > 15 else 70
    elif avg_rev_growth > 10 and avg_profit_growth > 10:
        stage = '稳定成长期'
        confidence = 85
    elif avg_rev_growth > 0 and avg_profit_growth > 0:
        stage = '成熟期'
        confidence = 80
    elif avg_rev_growth < 0 and avg_profit_growth < 0:
        stage = '衰退期'
        confidence = 85
    elif avg_rev_growth < 0 and avg_profit_growth > 0:
        stage = '收缩优化期'
        confidence = 70
    elif avg_rev_growth > 0 and avg_profit_growth < 0:
        stage = '增收不增利'
        confidence = 75
    else:
        stage = '转型期'
        confidence = 50

    # 趋势信号
    trend_signal = '稳定'
    if rev_trend and profit_trend:
        if rev_trend > 0 and profit_trend > 0:
            trend_signal = '加速'
        elif rev_trend < 0 and profit_trend < 0:
            trend_signal = '减速'
        elif rev_trend > 0 and profit_trend < 0:
            trend_signal = '增收不增利'

    return {
        'stage': stage,
        'confidence': confidence,
        'trend_signal': trend_signal,
        'details': {
            'avg_revenue_growth': round(avg_rev_growth, 2),
            'avg_profit_growth': round(avg_profit_growth, 2),
            'avg_roe': round(avg_roe, 2),
            'revenue_trend': rev_trend,
            'profit_trend': profit_trend,
        }
    }


def generate_timeline(reports: list) -> list:
    """生成财务指标时间线（增强版：含趋势标记）"""
    timeline = []
    for r in reversed(reports):
        timeline.append({
            'date': r.get('date', ''),
            'report_name': r.get('report_name', ''),
            'roe': r.get('roe'),
            'gross_margin': r.get('gross_margin'),
            'net_margin': r.get('net_margin'),
            'revenue_growth': r.get('revenue_growth'),
            'profit_growth': r.get('profit_growth'),
            'debt_ratio': r.get('debt_ratio'),
        })

    # 为每个指标添加趋势标记
    for field in ['roe', 'gross_margin', 'net_margin', 'debt_ratio']:
        values = [t[field] for t in timeline if t.get(field) is not None]
        if len(values) >= 3:
            slope = _calc_trend_slope(values[-3:])
            if slope is not None:
                for t in timeline[-3:]:
                    t[f'{field}_trend'] = 'up' if slope > 0.5 else ('down' if slope < -0.5 else 'flat')

    return timeline


def _dupont_decompose(reports: list) -> dict:
    """杜邦分析分解 - 评估ROE质量"""
    if not reports:
        return {}

    latest = reports[0]
    roe = _safe(latest.get('roe'))
    net_margin = _safe(latest.get('net_margin'))
    gross_margin = _safe(latest.get('gross_margin'))
    debt_ratio = _safe(latest.get('debt_ratio'))

    # 估算资产周转率和权益乘数
    # ROE = 净利率 x 资产周转率 x 权益乘数
    asset_turnover = None
    equity_multiplier = None
    if net_margin and net_margin > 0 and roe:
        # 权益乘数 = 1 / (1 - 资产负债率/100)
        if debt_ratio is not None:
            equity_multiplier = round(1 / (1 - debt_ratio / 100), 2) if debt_ratio < 100 else None
            if equity_multiplier and equity_multiplier > 0:
                # 资产周转率 = ROE / (净利率 x 权益乘数)
                calculated_turnover = roe / (net_margin * equity_multiplier)
                asset_turnover = round(calculated_turnover, 3)

    # ROE质量评估
    roe_quality = 'unknown'
    roe_quality_score = 50  # 中性

    if roe and roe > 15:
        if net_margin and net_margin > 10:
            # 高ROE来自高利润率 = 高质量
            roe_quality = '高质量（利润率驱动）'
            roe_quality_score = 90
        elif asset_turnover and asset_turnover > 1.0:
            # 高ROE来自高周转 = 中等质量
            roe_quality = '中质量（周转驱动）'
            roe_quality_score = 70
        elif equity_multiplier and equity_multiplier > 2.5:
            # 高ROE来自高杠杆 = 低质量
            roe_quality = '低质量（杠杆驱动）'
            roe_quality_score = 40
    elif roe and roe > 10:
        roe_quality = '中等'
        roe_quality_score = 60
    elif roe:
        roe_quality = '偏低'
        roe_quality_score = 30

    return {
        'roe': round(roe, 2) if roe else None,
        'net_margin': round(net_margin, 2) if net_margin else None,
        'gross_margin': round(gross_margin, 2) if gross_margin else None,
        'asset_turnover': asset_turnover,
        'equity_multiplier': equity_multiplier,
        'roe_quality': roe_quality,
        'roe_quality_score': roe_quality_score,
    }


def _calc_cross_validation(reports: list, cashflow_data: list = None) -> dict:
    """多指标交叉验证 - 检查指标间一致性"""
    if not reports or len(reports) < 2:
        return {'consistency_score': 50, 'flags': [], 'details': []}

    latest = reports[0]
    flags = []
    details = []
    score = 100  # 从满分开始扣分

    roe = _safe(latest.get('roe'))
    gross_margin = _safe(latest.get('gross_margin'))
    net_margin = _safe(latest.get('net_margin'))
    debt_ratio = _safe(latest.get('debt_ratio'))
    revenue_growth = _safe(latest.get('revenue_growth'))
    profit_growth = _safe(latest.get('profit_growth'))

    # --- 交叉验证1: ROE vs 利润率 ---
    if roe and gross_margin and net_margin:
        if roe > 15 and gross_margin < 20:
            flags.append('ROE偏高但毛利率偏低，可能依赖高杠杆或非经常性收益')
            score -= 15
        if gross_margin > 50 and net_margin < 5:
            flags.append('毛利率高但净利率极低，期间费用或减值侵蚀严重')
            score -= 15
        details.append({
            'check': 'ROE-利润率一致性',
            'status': 'pass' if not (roe > 15 and gross_margin < 20) else 'warning',
        })

    # --- 交叉验证2: 增长 vs 盈利 ---
    if revenue_growth and profit_growth:
        if revenue_growth > 20 and profit_growth < -10:
            flags.append('营收高增长但利润大幅下滑，增收不增利')
            score -= 20
        if revenue_growth < -10 and profit_growth > 20:
            flags.append('营收下滑但利润增长，关注可持续性')
            score -= 10
        details.append({
            'check': '增长-盈利一致性',
            'status': 'pass' if not (revenue_growth > 20 and profit_growth < -10) else 'warning',
        })

    # --- 交叉验证3: 负债 vs ROE ---
    if debt_ratio and roe:
        if debt_ratio > 70 and roe > 15:
            flags.append('高负债驱动的ROE，财务风险较大')
            score -= 10
        if debt_ratio < 30 and roe > 20:
            details.append({
                'check': '低负债高ROE',
                'status': 'excellent',
            })
            score += 5  # 加分

    # --- 交叉验证4: 趋势一致性 ---
    roe_values = [_safe(r.get('roe')) for r in reports[:5] if r.get('roe') is not None]
    margin_values = [_safe(r.get('gross_margin')) for r in reports[:5] if r.get('gross_margin') is not None]

    if len(roe_values) >= 3 and len(margin_values) >= 3:
        roe_slope = _calc_trend_slope(roe_values)
        margin_slope = _calc_trend_slope(margin_values)
        if roe_slope and margin_slope:
            # ROE上升但毛利率下降 = 可能杠杆驱动
            if roe_slope > 0.5 and margin_slope < -0.5:
                flags.append('ROE上升但毛利率下降，盈利质量存疑')
                score -= 10
            # 两者同向 = 健康
            elif (roe_slope > 0 and margin_slope > 0) or (roe_slope < 0 and margin_slope < 0):
                details.append({
                    'check': '趋势一致性',
                    'status': 'pass',
                })

    # --- 交叉验证5: 现金流验证（如果可用） ---
    if cashflow_data:
        latest_cf = cashflow_data[0] if cashflow_data else None
        if latest_cf:
            fcf = latest_cf.get('free_cashflow')
            net_profit = _safe(latest.get('net_profit'))
            if fcf is not None and net_profit and net_profit > 0:
                cash_conversion = fcf / net_profit
                if cash_conversion < 0.3:
                    flags.append('自由现金流远低于净利润，利润含金量低')
                    score -= 15
                elif cash_conversion > 0.8:
                    details.append({
                        'check': '现金流质量',
                        'status': 'excellent',
                    })

    score = max(0, min(100, score))

    return {
        'consistency_score': score,
        'flags': flags,
        'details': details,
    }


def _calc_valuation_dimension(basic: dict, valuation_stats: dict = None) -> dict:
    """估值维度评分"""
    pe = basic.get('pe')
    pb = basic.get('pb')
    score = 50  # 中性起点
    details = []

    if valuation_stats and valuation_stats.get('pe'):
        pe_stats = valuation_stats['pe']
        pe_pct = pe_stats.get('percentile')
        if pe_pct is not None:
            if pe_pct <= 20:
                score += 30
                details.append(f'PE处于历史{pe_pct:.0f}%分位，极度低估')
            elif pe_pct <= 40:
                score += 20
                details.append(f'PE处于历史{pe_pct:.0f}%分位，低估')
            elif pe_pct <= 60:
                score += 5
                details.append(f'PE处于历史{pe_pct:.0f}%分位，合理')
            elif pe_pct <= 80:
                score -= 10
                details.append(f'PE处于历史{pe_pct:.0f}%分位，偏高')
            else:
                score -= 25
                details.append(f'PE处于历史{pe_pct:.0f}%分位，高估')

    if valuation_stats and valuation_stats.get('pb'):
        pb_stats = valuation_stats['pb']
        pb_pct = pb_stats.get('percentile')
        if pb_pct is not None:
            if pb_pct <= 20:
                score += 15
            elif pb_pct <= 40:
                score += 8
            elif pb_pct > 80:
                score -= 15

    # PEG
    if pe and pe > 0:
        # 简单PEG评估
        details.append(f'当前PE={pe:.1f}')

    score = max(0, min(100, score))
    return {
        'score': score,
        'details': details,
    }


def _calc_profitability_dimension(reports: list) -> dict:
    """盈利能力维度评分"""
    if not reports:
        return {'score': 0, 'details': []}

    latest = reports[0]
    roe = _safe(latest.get('roe'))
    gross_margin = _safe(latest.get('gross_margin'))
    net_margin = _safe(latest.get('net_margin'))

    score = 0
    details = []

    # ROE评分 (40分)
    if roe:
        if roe > 20:
            score += 40
            details.append(f'ROE={roe:.1f}%，卓越')
        elif roe > 15:
            score += 32
            details.append(f'ROE={roe:.1f}%，优秀')
        elif roe > 10:
            score += 20
            details.append(f'ROE={roe:.1f}%，良好')
        elif roe > 5:
            score += 10
            details.append(f'ROE={roe:.1f}%，一般')
        else:
            score += 3
            details.append(f'ROE={roe:.1f}%，偏低')

    # 毛利率评分 (30分)
    if gross_margin:
        if gross_margin > 50:
            score += 30
        elif gross_margin > 40:
            score += 24
        elif gross_margin > 30:
            score += 15
        elif gross_margin > 20:
            score += 8
        else:
            score += 3

    # 净利率评分 (30分)
    if net_margin:
        if net_margin > 20:
            score += 30
        elif net_margin > 15:
            score += 24
        elif net_margin > 10:
            score += 18
        elif net_margin > 5:
            score += 10
        else:
            score += 3

    score = max(0, min(100, score))
    return {'score': score, 'details': details}


def _calc_growth_dimension(reports: list) -> dict:
    """成长维度评分（含可持续性评估）"""
    if not reports or len(reports) < 2:
        return {'score': 0, 'details': []}

    score = 0
    details = []

    latest = reports[0]
    revenue_growth = _safe(latest.get('revenue_growth'))
    profit_growth = _safe(latest.get('profit_growth'))

    # 增长率评分 (50分)
    if revenue_growth is not None:
        if revenue_growth > 30:
            score += 25
        elif revenue_growth > 20:
            score += 20
        elif revenue_growth > 10:
            score += 15
        elif revenue_growth > 0:
            score += 8
        else:
            score += 2

    if profit_growth is not None:
        if profit_growth > 30:
            score += 25
        elif profit_growth > 20:
            score += 20
        elif profit_growth > 10:
            score += 15
        elif profit_growth > 0:
            score += 8
        else:
            score += 2

    # 增长可持续性 (50分) - 看3年趋势
    rev_growths = [_safe(r.get('revenue_growth')) for r in reports[:4] if r.get('revenue_growth') is not None]
    profit_growths = [_safe(r.get('profit_growth')) for r in reports[:4] if r.get('profit_growth') is not None]

    if len(rev_growths) >= 3:
        rev_cv = _calc_volatility(rev_growths)
        if rev_cv is not None:
            if rev_cv < 30:
                score += 25
                details.append(f'营收增长稳定(CV={rev_cv:.0f}%)')
            elif rev_cv < 60:
                score += 15
            else:
                score += 5
                details.append(f'营收增长波动大(CV={rev_cv:.0f}%)')

    if len(profit_growths) >= 3:
        profit_cv = _calc_volatility(profit_growths)
        if profit_cv is not None:
            if profit_cv < 30:
                score += 25
            elif profit_cv < 60:
                score += 15
            else:
                score += 5

    score = max(0, min(100, score))
    return {'score': score, 'details': details}


def _calc_financial_health_dimension(reports: list) -> dict:
    """财务健康维度评分"""
    if not reports:
        return {'score': 0, 'details': []}

    latest = reports[0]
    debt_ratio = _safe(latest.get('debt_ratio'))
    score = 50  # 中性起点
    details = []

    if debt_ratio is not None:
        if debt_ratio < 30:
            score += 35
            details.append(f'资产负债率{debt_ratio:.1f}%，非常健康')
        elif debt_ratio < 45:
            score += 20
            details.append(f'资产负债率{debt_ratio:.1f}%，健康')
        elif debt_ratio < 60:
            score += 5
            details.append(f'资产负债率{debt_ratio:.1f}%，适中')
        elif debt_ratio < 70:
            score -= 15
            details.append(f'资产负债率{debt_ratio:.1f}%，偏高')
        else:
            score -= 30
            details.append(f'资产负债率{debt_ratio:.1f}%，高风险')

    # 负债趋势
    debt_values = [_safe(r.get('debt_ratio')) for r in reports[:4] if r.get('debt_ratio') is not None]
    if len(debt_values) >= 3:
        debt_slope = _calc_trend_slope(debt_values)
        if debt_slope is not None:
            if debt_slope < -1:
                score += 15
                details.append('负债率持续下降')
            elif debt_slope > 2:
                score -= 10
                details.append('负债率持续上升')

    score = max(0, min(100, score))
    return {'score': score, 'details': details}


def _calc_profitability_stability_dimension(reports: list) -> dict:
    """盈利稳定性维度评分"""
    if not reports or len(reports) < 2:
        return {'score': 0, 'details': []}

    score = 0
    details = []

    gm_values = [_safe(r.get('gross_margin')) for r in reports[:5] if r.get('gross_margin') is not None]
    nm_values = [_safe(r.get('net_margin')) for r in reports[:5] if r.get('net_margin') is not None]
    roe_values = [_safe(r.get('roe')) for r in reports[:5] if r.get('roe') is not None]

    # 毛利率稳定性 (35分)
    if len(gm_values) >= 3:
        gm_cv = _calc_volatility(gm_values)
        if gm_cv is not None:
            if gm_cv < 10:
                score += 35
                details.append(f'毛利率极稳定(CV={gm_cv:.0f}%)')
            elif gm_cv < 20:
                score += 25
            elif gm_cv < 40:
                score += 15
            else:
                score += 5
                details.append(f'毛利率波动大(CV={gm_cv:.0f}%)')

    # 净利率稳定性 (35分)
    if len(nm_values) >= 3:
        nm_cv = _calc_volatility(nm_values)
        if nm_cv is not None:
            if nm_cv < 15:
                score += 35
            elif nm_cv < 30:
                score += 20
            else:
                score += 5

    # ROE稳定性 (30分)
    if len(roe_values) >= 3:
        roe_cv = _calc_volatility(roe_values)
        if roe_cv is not None:
            if roe_cv < 15:
                score += 30
            elif roe_cv < 30:
                score += 20
            else:
                score += 5

    score = max(0, min(100, score))
    return {'score': score, 'details': details}


def _calc_momentum_dimension(reports: list) -> dict:
    """动量维度评分 - 基本面动量（趋势改善程度）"""
    if not reports or len(reports) < 3:
        return {'score': 50, 'details': []}

    score = 50  # 中性起点
    details = []

    # 各指标趋势
    for field, label, weight in [
        ('roe', 'ROE', 25),
        ('gross_margin', '毛利率', 15),
        ('revenue_growth', '营收增长', 20),
        ('profit_growth', '利润增长', 20),
    ]:
        values = [_safe(r.get(field)) for r in reports[:5] if r.get(field) is not None]
        if len(values) >= 3:
            slope = _calc_trend_slope(values)
            if slope is not None:
                if slope > 1:
                    score += weight
                    details.append(f'{label}趋势向好')
                elif slope > 0:
                    score += weight // 2
                elif slope < -1:
                    score -= weight
                    details.append(f'{label}趋势恶化')
                else:
                    score -= weight // 3

    score = max(0, min(100, score))
    return {'score': score, 'details': details}


def _calc_competitive_position(peers_data: list, target: dict) -> dict:
    """竞争力定位 - 与同行业对比"""
    if not peers_data:
        return {'score': 50, 'rankings': {}, 'details': []}

    score = 50
    rankings = {}
    details = []

    # 包含自身数据
    all_data = peers_data + [target]

    for field, label, weight, higher_better in [
        ('roe', 'ROE', 20, True),
        ('gross_margin', '毛利率', 15, True),
        ('net_margin', '净利率', 15, True),
        ('revenue_growth', '营收增长', 15, True),
        ('debt_ratio', '负债率', 15, False),
    ]:
        values = [(d.get('code', ''), _safe(d.get(field))) for d in all_data if d.get(field) is not None]
        target_val = _safe(target.get(field))

        if target_val is not None and len(values) >= 2:
            sorted_vals = sorted(values, key=lambda x: x[1], reverse=higher_better)
            rank = next((i + 1 for i, (code, _) in enumerate(sorted_vals) if code == target.get('code', '')), None)
            if rank:
                total = len(sorted_vals)
                rankings[label] = {'rank': rank, 'total': total}
                # 排名评分
                rank_pct = 1 - (rank - 1) / max(total - 1, 1)
                score += int((rank_pct - 0.5) * weight * 2)  # 中位=0, 最好=+weight, 最差=-weight

                if rank == 1:
                    details.append(f'{label}行业第1')
                elif rank <= total * 0.3:
                    details.append(f'{label}行业前30%')

    score = max(0, min(100, score))
    return {'score': score, 'rankings': rankings, 'details': details}


def _calc_correlation_analysis(reports: list) -> dict:
    """相关性分析 - 指标间趋势相关性"""
    if not reports or len(reports) < 3:
        return {'pairs': [], 'summary': '数据不足'}

    # 提取各指标序列
    metrics = {}
    for field in ['roe', 'gross_margin', 'net_margin', 'revenue_growth', 'profit_growth', 'debt_ratio']:
        values = [_safe(r.get(field)) for r in reports[:5] if r.get(field) is not None]
        if len(values) >= 3:
            metrics[field] = values

    pairs = []
    field_names = {
        'roe': 'ROE', 'gross_margin': '毛利率', 'net_margin': '净利率',
        'revenue_growth': '营收增长', 'profit_growth': '利润增长', 'debt_ratio': '负债率',
    }

    checked = set()
    for f1 in metrics:
        for f2 in metrics:
            if f1 >= f2 or (f1, f2) in checked:
                continue
            checked.add((f1, f2))
            # 取相同长度
            min_len = min(len(metrics[f1]), len(metrics[f2]))
            if min_len >= 3:
                corr = _calc_correlation(metrics[f1][:min_len], metrics[f2][:min_len])
                if corr is not None:
                    strength = '强' if abs(corr) > 0.7 else ('中' if abs(corr) > 0.4 else '弱')
                    direction = '正' if corr > 0 else '负'
                    pairs.append({
                        'metric1': field_names.get(f1, f1),
                        'metric2': field_names.get(f2, f2),
                        'correlation': corr,
                        'strength': strength,
                        'direction': direction,
                    })

    # 按相关性强度排序
    pairs.sort(key=lambda x: abs(x['correlation']), reverse=True)

    summary = f'共分析{len(pairs)}组指标对'
    strong_pairs = [p for p in pairs if p['strength'] == '强']
    if strong_pairs:
        summary += f'，其中{len(strong_pairs)}组强相关'

    return {'pairs': pairs[:10], 'summary': summary}  # 最多返回10组


def generate_insights(basic: dict, latest: dict, peers: list, industry_avg: dict,
                      lifecycle: dict, cross_validation: dict, dupont: dict,
                      competitive: dict) -> dict:
    """生成投资洞察（增强版）"""
    insights = {
        'summary': '',
        'strengths': [],
        'weaknesses': [],
        'opportunities': [],
        'threats': [],
        'key_risks': [],
        'conclusion': '',
    }

    name = basic.get('name', '该公司')
    roe = _safe(latest.get('roe'))
    gross_margin = _safe(latest.get('gross_margin'))
    net_margin = _safe(latest.get('net_margin'))
    revenue_growth = _safe(latest.get('revenue_growth'))
    debt_ratio = _safe(latest.get('debt_ratio'))

    stage = lifecycle.get('stage', '未知')

    # 一句话结论 - 基于综合评分
    if roe > 15 and gross_margin > 40 and debt_ratio < 50:
        insights['summary'] = f'{name}是一家盈利能力突出、财务健康的优质企业，ROE={roe:.1f}%，毛利率={gross_margin:.1f}%。'
    elif roe > 10 and revenue_growth > 10:
        insights['summary'] = f'{name}盈利能力良好且保持增长，处于{stage}阶段。'
    elif roe > 10:
        insights['summary'] = f'{name}盈利能力尚可，处于{stage}阶段，需关注增长动力。'
    else:
        insights['summary'] = f'{name}盈利能力一般(ROE={roe:.1f}%)，需关注基本面变化。'

    # 优势
    if roe and roe > 15:
        insights['strengths'].append(f'ROE={roe:.1f}%，盈利能力优秀')
    if gross_margin and gross_margin > 40:
        insights['strengths'].append(f'毛利率={gross_margin:.1f}%，护城河较宽')
    if revenue_growth and revenue_growth > 10:
        insights['strengths'].append(f'营收增长={revenue_growth:.1f}%，成长性好')
    if debt_ratio and debt_ratio < 40:
        insights['strengths'].append(f'资产负债率={debt_ratio:.1f}%，财务稳健')

    # 杜邦分析优势
    if dupont.get('roe_quality_score', 0) >= 80:
        insights['strengths'].append(f'ROE质量高：{dupont["roe_quality"]}')

    # 竞争力优势
    if competitive.get('rankings'):
        top_ranks = [f'{k}第{v["rank"]}/{v["total"]}'
                     for k, v in competitive['rankings'].items() if v['rank'] == 1]
        if top_ranks:
            insights['strengths'].append(f'行业领先：{", ".join(top_ranks)}')

    # 劣势
    if roe and roe < 10:
        insights['weaknesses'].append(f'ROE={roe:.1f}%，盈利能力偏弱')
    if gross_margin and gross_margin < 30:
        insights['weaknesses'].append(f'毛利率={gross_margin:.1f}%，护城河窄')
    if revenue_growth and revenue_growth < 0:
        insights['weaknesses'].append(f'营收增长={revenue_growth:.1f}%，业务收缩')
    if debt_ratio and debt_ratio > 60:
        insights['weaknesses'].append(f'资产负债率={debt_ratio:.1f}%，负债偏高')

    # 杜邦分析劣势
    if dupont.get('roe_quality_score', 100) <= 40:
        insights['weaknesses'].append(f'ROE质量低：{dupont["roe_quality"]}')

    # 交叉验证风险
    if cross_validation.get('flags'):
        for flag in cross_validation['flags']:
            insights['key_risks'].append(flag)

    # 机会
    if '成长' in stage:
        insights['opportunities'].append(f'公司处于{stage}，未来增长空间较大')
    if industry_avg.get('roe', 0) > 0 and roe and roe > industry_avg['roe']:
        insights['opportunities'].append(f'ROE({roe:.1f}%)高于行业均值({industry_avg["roe"]:.1f}%)，竞争优势明显')
    if lifecycle.get('trend_signal') == '加速':
        insights['opportunities'].append('基本面趋势加速改善')

    # 威胁
    if '衰退' in stage:
        insights['threats'].append('公司处于衰退期，需关注转型进展')
    if revenue_growth and revenue_growth < 0:
        insights['threats'].append('营收下滑，需关注市场变化')
    if lifecycle.get('trend_signal') == '减速':
        insights['threats'].append('基本面趋势减速，需警惕拐点')

    # 总结
    s_count = len(insights['strengths'])
    w_count = len(insights['weaknesses'])
    r_count = len(insights['key_risks'])

    if s_count > w_count + r_count:
        insights['conclusion'] = f'{name}整体表现优秀，优势明显，建议关注。'
    elif s_count > w_count:
        insights['conclusion'] = f'{name}整体偏正面，但需关注{r_count}个风险点。'
    elif s_count == w_count:
        insights['conclusion'] = f'{name}表现中性，优劣均衡，需进一步研究。'
    else:
        insights['conclusion'] = f'{name}存在较多风险因素，建议谨慎。'

    return insights


def calculate_rating(latest: dict, industry_avg: dict, cross_validation: dict,
                     dupont: dict, valuation_score: float,
                     growth_score: float, stability_score: float,
                     momentum_score: float, health_score: float,
                     competitive_score: float) -> dict:
    """计算综合投资评级（8维度加权评分）

    权重设计参考机构级多因子模型：
    - 盈利能力 20% (核心)
    - 成长性 15% (核心)
    - 估值 15% (核心)
    - 财务健康 12%
    - 盈利稳定性 10%
    - 动量 10%
    - 交叉验证一致性 10%
    - 竞争力定位 8%
    """
    weights = {
        'profitability': 0.20,
        'growth': 0.15,
        'valuation': 0.15,
        'health': 0.12,
        'stability': 0.10,
        'momentum': 0.10,
        'consistency': 0.10,
        'competitive': 0.08,
    }

    scores = {
        'profitability': valuation_score,  # Will be overridden below
        'growth': growth_score,
        'valuation': valuation_score,
        'health': health_score,
        'stability': stability_score,
        'momentum': momentum_score,
        'consistency': cross_validation.get('consistency_score', 50),
        'competitive': competitive_score,
    }

    # 修正盈利能力评分
    roe = _safe(latest.get('roe'))
    gross_margin = _safe(latest.get('gross_margin'))
    net_margin = _safe(latest.get('net_margin'))

    profit_score = 0
    if roe:
        if roe > 20: profit_score += 40
        elif roe > 15: profit_score += 32
        elif roe > 10: profit_score += 20
        elif roe > 5: profit_score += 10
        else: profit_score += 3
    if gross_margin:
        if gross_margin > 50: profit_score += 30
        elif gross_margin > 40: profit_score += 24
        elif gross_margin > 30: profit_score += 15
        else: profit_score += 5
    if net_margin:
        if net_margin > 20: profit_score += 30
        elif net_margin > 15: profit_score += 24
        elif net_margin > 10: profit_score += 18
        else: profit_score += 5
    scores['profitability'] = min(100, profit_score)

    # 加权总分
    total_score = sum(scores[k] * weights[k] for k in weights)
    total_score = round(total_score, 1)

    # 评级
    if total_score >= 85:
        grade = 'A+'
        recommendation = '强烈推荐'
    elif total_score >= 75:
        grade = 'A'
        recommendation = '推荐'
    elif total_score >= 65:
        grade = 'B+'
        recommendation = '谨慎推荐'
    elif total_score >= 55:
        grade = 'B'
        recommendation = '中性'
    elif total_score >= 45:
        grade = 'C'
        recommendation = '观望'
    elif total_score >= 35:
        grade = 'C-'
        recommendation = '不推荐'
    else:
        grade = 'D'
        recommendation = '回避'

    # 各维度详情
    dim_names = {
        'profitability': '盈利能力',
        'growth': '成长性',
        'valuation': '估值',
        'health': '财务健康',
        'stability': '盈利稳定性',
        'momentum': '基本面动量',
        'consistency': '指标一致性',
        'competitive': '竞争力定位',
    }

    details = []
    for key in weights:
        details.append({
            'item': dim_names[key],
            'score': round(scores[key], 1),
            'weight': f'{int(weights[key] * 100)}%',
            'weighted_score': round(scores[key] * weights[key], 1),
        })

    # 按加权贡献排序，找出最大正面和负面因子
    details.sort(key=lambda x: x['weighted_score'], reverse=True)
    top_factor = details[0]['item'] if details else ''
    worst_factor = details[-1]['item'] if details else ''

    return {
        'score': total_score,
        'grade': grade,
        'recommendation': recommendation,
        'details': details,
        'top_factor': top_factor,
        'worst_factor': worst_factor,
        'dimension_scores': {dim_names[k]: round(v, 1) for k, v in scores.items()},
    }


# ============ 主接口 ============

@router.get("/analyze/{stock_code}")
def cross_analysis(stock_code: str):
    """
    交叉分析 - 机构级多维度公司分析

    返回：
    1. 纵向分析：公司历史财务指标趋势 + 生命周期
    2. 横向分析：与同行业竞品对比 + 竞争力排名
    3. 交叉验证：多指标一致性检查
    4. 三维分析：估值-盈利-动量
    5. 相关性分析：指标间趋势相关性
    6. 综合评分：8维度加权模型
    """
    try:
        # 1. 获取目标公司数据
        basic = data_service.get_stock_basic(stock_code)
        if 'error' in basic:
            raise HTTPException(status_code=400, detail=basic['error'])

        financials = data_service.get_financial_indicators(stock_code)
        if 'error' in financials:
            raise HTTPException(status_code=400, detail=financials['error'])

        reports = financials.get('reports', [])
        if not reports:
            raise HTTPException(status_code=400, detail='未找到财务数据')

        latest = _get_annual_report(reports)

        # 2. 获取现金流数据（用于交叉验证）
        cashflow_data = []
        try:
            statements = data_service.get_financial_statements(stock_code)
            if 'error' not in statements:
                cashflow_data = statements.get('cashflow', [])
        except Exception:
            pass

        # 3. 获取估值统计（用于估值维度）
        valuation_stats = None
        try:
            val_history = data_service.get_valuation_history(stock_code)
            if 'error' not in val_history:
                valuation_stats = val_history.get('stats')
        except Exception:
            pass

        # 4. 纵向分析
        timeline = generate_timeline(reports)
        lifecycle = analyze_lifecycle_stage(reports)

        # 趋势数据
        roe_trend = [r.get('roe') for r in reports if r.get('roe') is not None]
        gross_margin_trend = [r.get('gross_margin') for r in reports if r.get('gross_margin') is not None]
        revenue_growth_trend = [r.get('revenue_growth') for r in reports if r.get('revenue_growth') is not None]

        # 5. 杜邦分析
        dupont = _dupont_decompose(reports)

        # 6. 多指标交叉验证
        cross_validation = _calc_cross_validation(reports, cashflow_data)

        # 7. 横向分析
        peer_codes = get_peer_codes(stock_code)
        industry_name = get_industry_name(stock_code)

        target_data = {
            'code': stock_code,
            'name': basic.get('name', ''),
            'roe': latest.get('roe'),
            'gross_margin': latest.get('gross_margin'),
            'net_margin': latest.get('net_margin'),
            'revenue_growth': latest.get('revenue_growth'),
            'profit_growth': latest.get('profit_growth'),
            'debt_ratio': latest.get('debt_ratio'),
        }

        peers_data = []
        for code in peer_codes:
            if code == stock_code:
                continue
            try:
                peer_basic = data_service.get_stock_basic(code)
                peer_financials = data_service.get_financial_indicators(code)
                if 'error' not in peer_basic and 'error' not in peer_financials:
                    peer_reports = peer_financials.get('reports', [])
                    if peer_reports:
                        peer_latest = _get_annual_report(peer_reports)
                        peers_data.append({
                            'code': code,
                            'name': peer_basic.get('name', ''),
                            'price': peer_basic.get('price', 0),
                            'pe': peer_basic.get('pe'),
                            'pb': peer_basic.get('pb'),
                            'roe': peer_latest.get('roe'),
                            'gross_margin': peer_latest.get('gross_margin'),
                            'net_margin': peer_latest.get('net_margin'),
                            'revenue_growth': peer_latest.get('revenue_growth'),
                            'profit_growth': peer_latest.get('profit_growth'),
                            'debt_ratio': peer_latest.get('debt_ratio'),
                        })
            except Exception:
                continue

        # 行业平均值
        industry_avg = {}
        if peers_data:
            for field in ['roe', 'gross_margin', 'net_margin', 'revenue_growth', 'profit_growth', 'debt_ratio']:
                values = [p.get(field) for p in peers_data + [target_data] if p.get(field) is not None]
                if values:
                    industry_avg[field] = round(sum(values) / len(values), 2)

        # 8. 各维度评分
        profitability_result = _calc_profitability_dimension(reports)
        growth_result = _calc_growth_dimension(reports)
        health_result = _calc_financial_health_dimension(reports)
        stability_result = _calc_profitability_stability_dimension(reports)
        momentum_result = _calc_momentum_dimension(reports)
        valuation_result = _calc_valuation_dimension(basic, valuation_stats)
        competitive_result = _calc_competitive_position(peers_data, target_data)

        # 9. 相关性分析
        correlation_analysis = _calc_correlation_analysis(reports)

        # 10. 三维分析摘要
        three_dimension = {
            'valuation': {
                'score': valuation_result['score'],
                'level': '低估' if valuation_result['score'] >= 70 else ('合理' if valuation_result['score'] >= 45 else '偏高'),
                'details': valuation_result['details'],
            },
            'profitability': {
                'score': profitability_result['score'],
                'level': '优秀' if profitability_result['score'] >= 75 else ('良好' if profitability_result['score'] >= 50 else '一般'),
                'details': profitability_result['details'],
            },
            'momentum': {
                'score': momentum_result['score'],
                'level': '加速' if momentum_result['score'] >= 70 else ('稳定' if momentum_result['score'] >= 45 else '减速'),
                'details': momentum_result['details'],
            },
        }

        # 11. 综合评级
        rating = calculate_rating(
            latest, industry_avg, cross_validation, dupont,
            valuation_result['score'], growth_result['score'],
            stability_result['score'], momentum_result['score'],
            health_result['score'], competitive_result['score'],
        )

        # 12. 生成洞察
        insights = generate_insights(
            basic, latest, peers_data, industry_avg,
            lifecycle, cross_validation, dupont, competitive_result,
        )

        return {
            'stock': {
                'code': stock_code,
                'name': basic.get('name', ''),
                'price': basic.get('price', 0),
                'pe': basic.get('pe'),
                'pb': basic.get('pb'),
                'market_cap': basic.get('market_cap'),
            },
            'vertical_analysis': {
                'lifecycle': lifecycle,
                'timeline': timeline,
                'roe_trend': roe_trend,
                'gross_margin_trend': gross_margin_trend,
                'revenue_growth_trend': revenue_growth_trend,
                'latest_metrics': {
                    'roe': latest.get('roe'),
                    'gross_margin': latest.get('gross_margin'),
                    'net_margin': latest.get('net_margin'),
                    'revenue_growth': latest.get('revenue_growth'),
                    'profit_growth': latest.get('profit_growth'),
                    'debt_ratio': latest.get('debt_ratio'),
                },
            },
            'horizontal_analysis': {
                'industry': industry_name,
                'peers': peers_data,
                'industry_avg': industry_avg,
                'competitive_position': competitive_result,
            },
            'dupont': dupont,
            'cross_validation': cross_validation,
            'three_dimension': three_dimension,
            'dimension_scores': {
                'profitability': profitability_result,
                'growth': growth_result,
                'valuation': valuation_result,
                'health': health_result,
                'stability': stability_result,
                'momentum': momentum_result,
            },
            'correlation_analysis': correlation_analysis,
            'insights': insights,
            'rating': rating,
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"cross_analysis failed for {stock_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
