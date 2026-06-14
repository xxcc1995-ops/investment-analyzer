"""出口冠军筛选服务 - 筛选具备全球竞争力、分红稳健、且满足价值投资标准的企业

机构级优化:
1. 汇率影响实时评估 (AKShare currency_boc_sina)
2. 关税/贸易政策风险分行业量化评估
3. 同行业公司对比分析 (行业均值/中位数/排名)
4. 数据来源透明化
5. 修复A股代码筛选逻辑
"""

import time
import math
import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from app.services.data_service import DataService, _safe_float, _get_annual_report
from app.services.vi_service import (
    _get_hk_stock_data,
    _score_buffett,
    _score_munger,
    _score_li_lu,
    _score_duan_yongping,
)

logger = logging.getLogger(__name__)

# ============================================================
# 出口冠军股票池 - 精选具备全球竞争力的A股和港股
# ============================================================

EXPORT_STOCKS = {
    # === 家电出口 ===
    "000333": {"name": "美的集团", "industry": "家电出口", "sub_industry": "白色家电", "export_intensity": "high", "est_overseas_pct": 40, "tariff_sensitivity": "medium", "main_export_markets": ["东南亚", "欧洲", "北美"], "competitive_advantage": "全品类覆盖+全球供应链"},
    "000651": {"name": "格力电器", "industry": "家电出口", "sub_industry": "白色家电", "export_intensity": "medium", "est_overseas_pct": 15, "tariff_sensitivity": "medium", "main_export_markets": ["东南亚", "中东"], "competitive_advantage": "空调技术领先"},
    "002032": {"name": "苏泊尔", "industry": "家电出口", "sub_industry": "小家电", "export_intensity": "high", "est_overseas_pct": 50, "tariff_sensitivity": "low", "main_export_markets": ["欧洲", "东南亚"], "competitive_advantage": "SEB集团全球渠道"},
    "600690": {"name": "海尔智家", "industry": "家电出口", "sub_industry": "白色家电", "export_intensity": "high", "est_overseas_pct": 50, "tariff_sensitivity": "medium", "main_export_markets": ["北美", "欧洲", "东南亚", "日本"], "competitive_advantage": "全球化品牌矩阵(海尔/卡萨帝/GE/Fisher&Paykel)"},
    "600060": {"name": "海信视像", "industry": "家电出口", "sub_industry": "黑色家电", "export_intensity": "high", "est_overseas_pct": 40, "tariff_sensitivity": "medium", "main_export_markets": ["北美", "欧洲", "日本"], "competitive_advantage": "显示技术+体育营销全球化"},

    # === 动力电池 / 新能源车 ===
    "300750": {"name": "宁德时代", "industry": "动力电池", "sub_industry": "锂电池", "export_intensity": "high", "est_overseas_pct": 35, "tariff_sensitivity": "high", "main_export_markets": ["欧洲", "北美", "东南亚"], "competitive_advantage": "全球市占率37%+技术代差"},
    "002594": {"name": "比亚迪", "industry": "新能源车", "sub_industry": "整车", "export_intensity": "high", "est_overseas_pct": 25, "tariff_sensitivity": "high", "main_export_markets": ["东南亚", "欧洲", "中东", "南美"], "competitive_advantage": "垂直一体化(电池+芯片+整车)"},
    "002460": {"name": "赣锋锂业", "industry": "锂矿", "sub_industry": "锂资源", "export_intensity": "high", "est_overseas_pct": 45, "tariff_sensitivity": "low", "main_export_markets": ["全球"], "competitive_advantage": "全球锂资源布局+加工能力"},
    "601633": {"name": "长城汽车", "industry": "汽车出口", "sub_industry": "整车", "export_intensity": "high", "est_overseas_pct": 30, "tariff_sensitivity": "high", "main_export_markets": ["俄罗斯", "东南亚", "中东", "澳洲"], "competitive_advantage": "SUV/皮卡差异化+本地化生产"},

    # === 光伏 / 太阳能 ===
    "601012": {"name": "隆基绿能", "industry": "光伏", "sub_industry": "硅片+组件", "export_intensity": "high", "est_overseas_pct": 35, "tariff_sensitivity": "high", "main_export_markets": ["欧洲", "北美", "东南亚"], "competitive_advantage": "单晶硅片技术龙头"},
    "600438": {"name": "通威股份", "industry": "光伏", "sub_industry": "多晶硅+电池", "export_intensity": "high", "est_overseas_pct": 30, "tariff_sensitivity": "high", "main_export_markets": ["东南亚", "欧洲"], "competitive_advantage": "硅料成本最低+电池片龙头"},
    "002459": {"name": "晶澳科技", "industry": "光伏", "sub_industry": "组件", "export_intensity": "high", "est_overseas_pct": 60, "tariff_sensitivity": "high", "main_export_markets": ["欧洲", "北美", "日本", "东南亚"], "competitive_advantage": "N型电池技术+全球渠道"},

    # === 船舶制造 / 重工 ===
    "600150": {"name": "中国船舶", "industry": "船舶制造", "sub_industry": "造船", "export_intensity": "high", "est_overseas_pct": 70, "tariff_sensitivity": "low", "main_export_markets": ["全球"], "competitive_advantage": "全球最大造船集团+LNG船突破"},
    "601989": {"name": "中国重工", "industry": "船舶制造", "sub_industry": "造船+军工", "export_intensity": "high", "est_overseas_pct": 50, "tariff_sensitivity": "low", "main_export_markets": ["全球"], "competitive_advantage": "军民融合+大型船舶"},

    # === 工程机械 ===
    "600031": {"name": "三一重工", "industry": "工程机械", "sub_industry": "工程机械", "export_intensity": "high", "est_overseas_pct": 45, "tariff_sensitivity": "medium", "main_export_markets": ["东南亚", "欧洲", "北美", "中东"], "competitive_advantage": "挖掘机全球前三+海外本地化"},
    "000157": {"name": "中联重科", "industry": "工程机械", "sub_industry": "工程机械", "export_intensity": "high", "est_overseas_pct": 35, "tariff_sensitivity": "medium", "main_export_markets": ["东南亚", "中东", "非洲"], "competitive_advantage": "起重机全球龙头"},

    # === 电子 / 消费电子 ===
    "002415": {"name": "海康威视", "industry": "安防设备", "sub_industry": "安防", "export_intensity": "high", "est_overseas_pct": 35, "tariff_sensitivity": "high", "main_export_markets": ["欧洲", "东南亚", "中东"], "competitive_advantage": "AI视觉技术领先+全球服务网络"},
    "000725": {"name": "京东方A", "industry": "面板", "sub_industry": "显示面板", "export_intensity": "high", "est_overseas_pct": 50, "tariff_sensitivity": "low", "main_export_markets": ["全球"], "competitive_advantage": "LCD全球第一+OLED追赶"},
    "002241": {"name": "歌尔股份", "industry": "消费电子", "sub_industry": "精密制造", "export_intensity": "high", "est_overseas_pct": 75, "tariff_sensitivity": "medium", "main_export_markets": ["北美", "欧洲"], "competitive_advantage": "苹果/索尼核心供应商+XR布局"},
    "002475": {"name": "立讯精密", "industry": "消费电子", "sub_industry": "精密制造", "export_intensity": "high", "est_overseas_pct": 80, "tariff_sensitivity": "medium", "main_export_markets": ["北美", "欧洲"], "competitive_advantage": "苹果第一大代工商+汽车电子转型"},
    "601138": {"name": "工业富联", "industry": "电子制造", "sub_industry": "EMS代工", "export_intensity": "high", "est_overseas_pct": 70, "tariff_sensitivity": "medium", "main_export_markets": ["北美", "欧洲"], "competitive_advantage": "全球最大EMS+AI服务器"},

    # === 化工 / 材料 ===
    "600309": {"name": "万华化学", "industry": "化工", "sub_industry": "MDI", "export_intensity": "high", "est_overseas_pct": 45, "tariff_sensitivity": "low", "main_export_markets": ["全球"], "competitive_advantage": "全球MDI龙头(市占率25%)+技术壁垒"},
    "002353": {"name": "杰瑞股份", "industry": "油服设备", "sub_industry": "油气装备", "export_intensity": "high", "est_overseas_pct": 50, "tariff_sensitivity": "low", "main_export_markets": ["中东", "北美", "中亚"], "competitive_advantage": "压裂设备全球竞争力"},

    # === 通信设备 ===
    "000063": {"name": "中兴通讯", "industry": "通信设备", "sub_industry": "电信设备", "export_intensity": "high", "est_overseas_pct": 30, "tariff_sensitivity": "high", "main_export_markets": ["东南亚", "非洲", "中东"], "competitive_advantage": "5G技术第二梯队+性价比"},

    # === 半导体 ===
    "603501": {"name": "韦尔股份", "industry": "半导体", "sub_industry": "芯片设计", "export_intensity": "high", "est_overseas_pct": 60, "tariff_sensitivity": "high", "main_export_markets": ["全球"], "competitive_advantage": "CIS全球第三+汽车CIS增长"},

    # === 发动机 / 工业 ===
    "000338": {"name": "潍柴动力", "industry": "发动机", "sub_industry": "动力总成", "export_intensity": "high", "est_overseas_pct": 40, "tariff_sensitivity": "medium", "main_export_markets": ["东南亚", "中东", "非洲", "南美"], "competitive_advantage": "柴油发动机全球领先+液压龙头(林德)"},

    # === 港股 ===
    "01810": {"name": "小米集团", "industry": "消费电子", "sub_industry": "智能硬件", "export_intensity": "high", "est_overseas_pct": 40, "tariff_sensitivity": "medium", "main_export_markets": ["印度", "东南亚", "欧洲"], "competitive_advantage": "性价比+IoT生态+造车"},
    "01211": {"name": "比亚迪股份", "industry": "新能源车", "sub_industry": "整车", "export_intensity": "high", "est_overseas_pct": 25, "tariff_sensitivity": "high", "main_export_markets": ["东南亚", "欧洲", "中东"], "competitive_advantage": "垂直一体化+刀片电池"},
    "02333": {"name": "长城汽车", "industry": "汽车出口", "sub_industry": "整车", "export_intensity": "high", "est_overseas_pct": 30, "tariff_sensitivity": "high", "main_export_markets": ["俄罗斯", "东南亚", "中东"], "competitive_advantage": "SUV/皮卡+海外工厂"},
    "00175": {"name": "吉利汽车", "industry": "汽车出口", "sub_industry": "整车", "export_intensity": "high", "est_overseas_pct": 20, "tariff_sensitivity": "high", "main_export_markets": ["东南亚", "中东"], "competitive_advantage": "沃尔沃技术+极氪高端化"},
    "02269": {"name": "药明生物", "industry": "CXO", "sub_industry": "生物制药CDMO", "export_intensity": "high", "est_overseas_pct": 70, "tariff_sensitivity": "low", "main_export_markets": ["北美", "欧洲"], "competitive_advantage": "全球CDMO第二+技术平台"},
    "06690": {"name": "海尔智家H", "industry": "家电出口", "sub_industry": "白色家电", "export_intensity": "high", "est_overseas_pct": 50, "tariff_sensitivity": "medium", "main_export_markets": ["北美", "欧洲", "东南亚", "日本"], "competitive_advantage": "全球化品牌矩阵"},
    "09992": {"name": "泡泡玛特", "industry": "潮玩", "sub_industry": "潮流玩具", "export_intensity": "high", "est_overseas_pct": 30, "tariff_sensitivity": "low", "main_export_markets": ["东南亚", "日韩", "欧美"], "competitive_advantage": "IP运营+盲盒模式全球化"},
    "01929": {"name": "周大福", "industry": "珠宝", "sub_industry": "珠宝零售", "export_intensity": "medium", "est_overseas_pct": 15, "tariff_sensitivity": "low", "main_export_markets": ["港澳", "东南亚"], "competitive_advantage": "品牌+渠道+黄金工艺"},
}

# A股代码: 6位数字, 以0/3/6开头
# 港股代码: 5位数字
A_EXPORT_STOCKS = [c for c in EXPORT_STOCKS if len(c) == 6]
HK_EXPORT_STOCKS = [c for c in EXPORT_STOCKS if len(c) == 5]

# 行业分组索引
INDUSTRY_GROUPS: Dict[str, List[str]] = {}
for _code, _info in EXPORT_STOCKS.items():
    _ind = _info['industry']
    if _ind not in INDUSTRY_GROUPS:
        INDUSTRY_GROUPS[_ind] = []
    INDUSTRY_GROUPS[_ind].append(_code)

# ============================================================
# Data Fetching
# ============================================================


def _get_a_stock_data(code: str) -> Optional[dict]:
    """Fetch A-share data from EastMoney."""
    try:
        basic = DataService.get_stock_basic(code)
        if "error" in basic:
            return None

        financials = DataService.get_financial_indicators(code)
        reports = financials.get("reports", [])
        latest = _get_annual_report(reports) if reports else {}

        _div = DataService._get_actual_dividend(code)
        div_per_share = _div["dividend_per_share"]
        consecutive_years = _div["consecutive_years"]
        dividend_ratio = _div["dividend_ratio"]
        dividend_yield = None
        if div_per_share > 0 and basic.get('price', 0) > 0:
            dividend_yield = round(div_per_share / basic['price'] * 100, 2)

        export_info = EXPORT_STOCKS.get(code, {})

        return {
            'code': code, 'name': basic.get('name', ''), 'market': 'A',
            'price': basic.get('price', 0),
            'change_pct': basic.get('change_pct', 0),
            'pe': basic.get('pe'),
            'pb': basic.get('pb'),
            'market_cap': basic.get('market_cap'),
            'dividend_yield': dividend_yield,
            'consecutive_years': consecutive_years,
            'dividend_ratio': dividend_ratio,
            'roe': latest.get('roe'),
            'gross_margin': latest.get('gross_margin'),
            'net_margin': latest.get('net_margin'),
            'debt_ratio': latest.get('debt_ratio'),
            'revenue_growth': latest.get('revenue_growth'),
            'profit_growth': latest.get('profit_growth'),
            'report_period': latest.get('report_period', ''),
            'industry': export_info.get('industry', ''),
            'export_intensity': export_info.get('export_intensity', 'low'),
            'est_overseas_pct': export_info.get('est_overseas_pct', 0),
        }
    except Exception:
        return None


def _get_hk_data(code: str) -> Optional[dict]:
    """Fetch HK stock data and enrich with export info."""
    stock = _get_hk_stock_data(code)
    if not stock:
        return None

    # Fix data quality: Tencent API returns negative PB for HK stocks with
    # negative net assets (or data issues), which causes ROE to be garbage.
    # When PB is None or non-positive, ROE is unreliable — clear it.
    pb = stock.get('pb')
    if pb is None or pb <= 0:
        stock['pb'] = None
        stock['roe'] = None

    export_info = EXPORT_STOCKS.get(code, {})
    stock['industry'] = export_info.get('industry', '')
    stock['export_intensity'] = export_info.get('export_intensity', 'low')
    stock['est_overseas_pct'] = export_info.get('est_overseas_pct', 0)
    stock['consecutive_years'] = None
    stock['dividend_ratio'] = None
    return stock


# ============================================================
# 汇率数据服务
# ============================================================

def get_exchange_rate_data() -> Optional[Dict]:
    """获取USD/CNY汇率数据及趋势分析 (数据源: AKShare -> 中国银行外汇牌价)"""
    cache_key = "export_fx_usdcny"
    cached = _get_cached(cache_key, cache_type='financial')
    if cached:
        return cached

    try:
        import akshare as ak
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')
        df = ak.currency_boc_sina(symbol='美元', start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            return None

        # 中间价在第5列 (index 4)
        col_name = df.columns[4]
        df = df.dropna(subset=[col_name])
        df['rate'] = df[col_name].astype(float) / 100.0  # 转换为标准汇率

        latest_rate = float(df['rate'].iloc[-1])
        latest_date = str(df.iloc[-1, 0])

        # 计算趋势
        rates = df['rate'].tolist()
        rate_7d = float(rates[-7]) if len(rates) >= 7 else float(rates[0])
        rate_30d = float(rates[-22]) if len(rates) >= 22 else float(rates[0])
        rate_90d = float(rates[0])

        change_7d = round((latest_rate / rate_7d - 1) * 100, 3)
        change_30d = round((latest_rate / rate_30d - 1) * 100, 3)
        change_90d = round((latest_rate / rate_90d - 1) * 100, 3)

        # 汇率趋势判断
        if change_30d > 1.0:
            trend = "人民币贬值"
            trend_desc = "近30天人民币贬值超过1%，利好出口企业营收换算"
            export_impact = "positive"
        elif change_30d < -1.0:
            trend = "人民币升值"
            trend_desc = "近30天人民币升值超过1%，利空出口企业营收换算"
            export_impact = "negative"
        else:
            trend = "汇率稳定"
            trend_desc = "近30天人民币汇率波动在1%以内，对出口企业影响有限"
            export_impact = "neutral"

        # 高海外收入企业的汇率敏感度
        high_fx_stocks = []
        for code, info in EXPORT_STOCKS.items():
            if info['est_overseas_pct'] >= 50:
                # 粗略估计: 海外营收占比 * 汇率变动 = 营收影响
                revenue_impact = round(info['est_overseas_pct'] / 100 * change_30d, 2)
                high_fx_stocks.append({
                    'code': code,
                    'name': info['name'],
                    'est_overseas_pct': info['est_overseas_pct'],
                    'revenue_fx_impact_pct': revenue_impact,
                })
        high_fx_stocks.sort(key=lambda x: abs(x['revenue_fx_impact_pct']), reverse=True)

        result = {
            'latest_rate': round(latest_rate, 4),
            'latest_date': latest_date,
            'change_7d_pct': change_7d,
            'change_30d_pct': change_30d,
            'change_90d_pct': change_90d,
            'trend': trend,
            'trend_desc': trend_desc,
            'export_impact': export_impact,
            'high_fx_sensitivity_stocks': high_fx_stocks[:10],
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_source': 'AKShare -> 中国银行外汇牌价',
        }

        _set_cached(cache_key, result)
        return result
    except Exception as e:
        logger.warning(f"获取汇率数据失败: {e}")
        return None


# ============================================================
# 关税/贸易政策风险量化评估
# ============================================================

# 行业关税风险矩阵 (2024-2025年最新政策)
TARIFF_RISK_MATRIX = {
    '光伏': {
        'risk_level': 'critical',
        'score': 95,
        'detail': '美国对华光伏组件关税累计超100%(301条款+AD/CVD)，欧盟CBAM碳关税2026年实施',
        'mitigation': '东南亚产能转移(隆基越南/晶澳马来)可部分规避',
        'recent_policy': '2024年5月拜登将光伏关税从25%提升至50%(Section 301)',
        'fx_hedge': '美元结算为主，汇率自然对冲',
    },
    '动力电池': {
        'risk_level': 'high',
        'score': 80,
        'detail': '美国IRA法案限制中国电池享受补贴，欧盟反补贴调查',
        'mitigation': '宁德时代与福特技术授权模式、欧洲建厂',
        'recent_policy': '2024年欧盟对中国电动汽车加征17-36%反补贴关税',
        'fx_hedge': '欧元/美元结算，汇率风险中等',
    },
    '新能源车': {
        'risk_level': 'high',
        'score': 85,
        'detail': '美国100%关税(2024)、欧盟17-36%反补贴关税',
        'mitigation': '东南亚/中东/南美市场分散化，海外建厂',
        'recent_policy': '2024年美国对中国电动车关税从25%提升至100%',
        'fx_hedge': '多币种结算，需关注各市场汇率',
    },
    '半导体': {
        'risk_level': 'high',
        'score': 80,
        'detail': '美国出口管制+实体清单限制高端芯片和设备',
        'mitigation': '韦尔为Fabless设计公司，代工在台积电/中芯，限制相对较小',
        'recent_policy': '2024年美国进一步收紧对华半导体出口管制',
        'fx_hedge': '美元结算为主',
    },
    '安防设备': {
        'risk_level': 'high',
        'score': 75,
        'detail': '海康威视已被列入实体清单，美国市场受限',
        'mitigation': '已退出美国市场，聚焦欧洲/东南亚/中东',
        'recent_policy': 'NDAA禁令覆盖联邦采购，部分州扩展至商业',
        'fx_hedge': '欧元/美元结算为主',
    },
    '通信设备': {
        'risk_level': 'high',
        'score': 75,
        'detail': '中兴曾遭制裁(2018)，美国/澳洲/部分欧洲国家禁用5G设备',
        'mitigation': '聚焦发展中国家市场(东南亚/非洲/中东)',
        'recent_policy': '部分国家逐步排除中国5G设备',
        'fx_hedge': '多币种结算，新兴市场汇率波动大',
    },
    'CXO': {
        'risk_level': 'high',
        'score': 70,
        'detail': '美国《生物安全法案》(BIOSECURE Act)可能限制药明等中资CXO',
        'mitigation': '法案尚未最终通过，药明持续建设海外产能',
        'recent_policy': '2024年BIOSECURE Act在众议院通过，参议院待审',
        'fx_hedge': '美元结算为主，汇率自然对冲',
    },
    '汽车出口': {
        'risk_level': 'medium',
        'score': 55,
        'detail': '欧盟反补贴关税、部分国家本地化要求',
        'mitigation': '长城/吉利在东南亚建厂，本地化生产规避',
        'recent_policy': '2024年欧盟反补贴关税落地',
        'fx_hedge': '多币种结算',
    },
    '消费电子': {
        'risk_level': 'medium',
        'score': 50,
        'detail': '终端品牌(苹果)承担关税，供应链转移压力',
        'mitigation': '越南/印度产能布局，苹果承担部分关税成本',
        'recent_policy': '消费电子暂未被大幅加征关税',
        'fx_hedge': '美元结算为主',
    },
    '家电出口': {
        'risk_level': 'medium',
        'score': 45,
        'detail': '已有反倾销税但整体可控，海外建厂规避',
        'mitigation': '海尔/美的全球工厂布局成熟',
        'recent_policy': '关税稳定，无大幅升级风险',
        'fx_hedge': '多币种+海外本地生产自然对冲',
    },
    '工程机械': {
        'risk_level': 'medium',
        'score': 40,
        'detail': '非贸易制裁重点行业，部分市场有准入限制',
        'mitigation': '三一海外工厂布局+代理商网络',
        'recent_policy': '无重大政策变化',
        'fx_hedge': '美元+当地货币结算',
    },
    '化工': {
        'risk_level': 'low',
        'score': 25,
        'detail': 'MDI等化工品属全球化大宗商品，贸易壁垒较低',
        'mitigation': '万华匈牙利工厂+全球化产能布局',
        'recent_policy': '无重大贸易限制',
        'fx_hedge': '美元定价为主，汇率自然对冲',
    },
    '面板': {
        'risk_level': 'low',
        'score': 20,
        'detail': '面板属全球化供应链，贸易壁垒低',
        'mitigation': '京东方全球产能布局',
        'recent_policy': '无贸易限制',
        'fx_hedge': '美元定价',
    },
    '船舶制造': {
        'risk_level': 'low',
        'score': 15,
        'detail': '造船业全球招标，无明显贸易壁垒',
        'mitigation': '全球第一造船大国，订单排期长',
        'recent_policy': '无贸易限制',
        'fx_hedge': '美元定价',
    },
    '发动机': {
        'risk_level': 'medium',
        'score': 40,
        'detail': '非制裁重点，但需关注地缘政治风险',
        'mitigation': '潍柴海外并购(林德液压)+本地化',
        'recent_policy': '无重大政策变化',
        'fx_hedge': '多币种结算',
    },
    '油服设备': {
        'risk_level': 'low',
        'score': 25,
        'detail': '油服设备面向全球油气公司，贸易壁垒低',
        'mitigation': '杰瑞中东/北美本地化服务',
        'recent_policy': '无贸易限制',
        'fx_hedge': '美元定价为主',
    },
    '锂矿': {
        'risk_level': 'low',
        'score': 20,
        'detail': '锂资源属全球化大宗商品',
        'mitigation': '赣锋全球锂资源布局(澳洲/南美/非洲)',
        'recent_policy': '无贸易限制',
        'fx_hedge': '美元定价',
    },
    '潮玩': {
        'risk_level': 'low',
        'score': 15,
        'detail': '消费品类，贸易壁垒极低',
        'mitigation': '泡泡玛特海外门店快速扩张',
        'recent_policy': '无贸易限制',
        'fx_hedge': '当地货币结算+少量汇率风险',
    },
    '珠宝': {
        'risk_level': 'low',
        'score': 10,
        'detail': '零售消费品，贸易壁垒极低',
        'mitigation': '周大福以港澳和东南亚为主',
        'recent_policy': '无贸易限制',
        'fx_hedge': '港币+当地货币',
    },
    '电子制造': {
        'risk_level': 'medium',
        'score': 45,
        'detail': '代工模式受品牌方影响，产能转移压力',
        'mitigation': '工业富联全球工厂布局(中国/越南/印度/墨西哥)',
        'recent_policy': '消费电子暂未被大幅加征关税',
        'fx_hedge': '美元结算为主',
    },
}


def get_peer_comparison(stocks_data: List[dict]) -> Dict[str, dict]:
    """
    同行业公司对比分析

    对每只股票，计算其所在行业的均值/中位数，并给出该股票在行业内的排名。
    """
    # 按行业分组
    industry_stocks: Dict[str, List[dict]] = {}
    for stock in stocks_data:
        industry = stock.get('industry', '未分类')
        if industry not in industry_stocks:
            industry_stocks[industry] = []
        industry_stocks[industry].append(stock)

    result = {}
    for industry, group in industry_stocks.items():
        if len(group) < 2:
            # 单一公司无对比意义
            result[industry] = {
                'count': len(group),
                'companies': [s.get('name', '') for s in group],
                'has_comparison': False,
            }
            continue

        # 计算行业均值/中位数
        metrics = ['roe', 'gross_margin', 'net_margin', 'debt_ratio', 'dividend_yield',
                    'pe', 'pb', 'revenue_growth', 'profit_growth', 'est_overseas_pct']

        industry_stats = {}
        for metric in metrics:
            values = [s.get(metric) for s in group if s.get(metric) is not None]
            if values:
                sorted_vals = sorted(values)
                n = len(sorted_vals)
                median = sorted_vals[n // 2] if n % 2 == 1 else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
                industry_stats[metric] = {
                    'mean': round(sum(values) / len(values), 2),
                    'median': round(median, 2),
                    'min': round(min(values), 2),
                    'max': round(max(values), 2),
                    'count': len(values),
                }

        # 为每只股票计算行业排名
        stock_rankings = {}
        for stock in group:
            code = stock.get('code', '')
            name = stock.get('name', '')
            rankings = {}

            # ROE排名 (越高越好)
            roe_vals = sorted([(s.get('roe', 0) or 0, s.get('code', '')) for s in group], reverse=True)
            for rank, (val, c) in enumerate(roe_vals, 1):
                if c == code:
                    rankings['roe_rank'] = rank
                    rankings['roe_total'] = len(group)
                    break

            # 股息率排名 (越高越好)
            div_vals = sorted([(s.get('dividend_yield', 0) or 0, s.get('code', '')) for s in group], reverse=True)
            for rank, (val, c) in enumerate(div_vals, 1):
                if c == code:
                    rankings['dividend_rank'] = rank
                    rankings['dividend_total'] = len(group)
                    break

            # PE排名 (越低越好)
            pe_vals = sorted([(s.get('pe', 999) or 999, s.get('code', '')) for s in group])
            for rank, (val, c) in enumerate(pe_vals, 1):
                if c == code:
                    rankings['pe_rank'] = rank
                    rankings['pe_total'] = len(group)
                    break

            # 海外营收排名 (越高越好)
            overseas_vals = sorted([(s.get('est_overseas_pct', 0) or 0, s.get('code', '')) for s in group], reverse=True)
            for rank, (val, c) in enumerate(overseas_vals, 1):
                if c == code:
                    rankings['overseas_rank'] = rank
                    rankings['overseas_total'] = len(group)
                    break

            stock_rankings[code] = {
                'name': name,
                'rankings': rankings,
            }

        result[industry] = {
            'count': len(group),
            'companies': [s.get('name', '') for s in group],
            'has_comparison': True,
            'stats': industry_stats,
            'stock_rankings': stock_rankings,
        }

    return result


# ============================================================
# 出口冠军评分体系 (满分100)
# ============================================================

def _score_export_champion(stock: dict) -> tuple:
    """
    出口冠军评分体系 (满分100)
    核心框架: 出口竞争力 + 分红稳健 + 盈利能力 + 财务健康

    改进点:
    1. 数据缺失时大幅降权而非给默认分
    2. 增加风险标签生成
    3. 优化评分公式，更符合投资逻辑
    4. 增加行业差异化权重
    """
    score = 0
    details = []
    missing_data_penalty = 0  # 数据缺失扣分累计
    code = stock.get('code', '')

    # 1. 出口强度 (25分) - 优化公式，考虑行业差异
    export_info = EXPORT_STOCKS.get(code, {})
    intensity = export_info.get('export_intensity', 'low')
    est_pct = export_info.get('est_overseas_pct', 0)
    industry = export_info.get('industry', '')

    # 不同行业的出口强度标准不同
    industry_thresholds = {
        '家电出口': {'high': 35, 'medium': 20},
        '动力电池': {'high': 30, 'medium': 15},
        '光伏': {'high': 40, 'medium': 25},
        '消费电子': {'high': 50, 'medium': 30},
        '汽车出口': {'high': 25, 'medium': 15},
        '船舶制造': {'high': 50, 'medium': 30},
        '工程机械': {'high': 35, 'medium': 20},
        '化工': {'high': 35, 'medium': 20},
        '通信设备': {'high': 25, 'medium': 15},
        '半导体': {'high': 40, 'medium': 25},
        '发动机': {'high': 35, 'medium': 20},
        'CXO': {'high': 50, 'medium': 30},
        '潮玩': {'high': 25, 'medium': 15},
        '珠宝': {'high': 20, 'medium': 10},
    }

    # 行业权重调整：不同行业对各维度的重视程度不同
    industry_weights = {
        '光伏': {'export': 1.2, 'growth': 1.1, 'valuation': 0.9},  # 光伏更看重出口和成长
        '半导体': {'export': 1.1, 'growth': 1.2, 'valuation': 0.9},  # 半导体更看重成长
        '动力电池': {'export': 1.1, 'growth': 1.1, 'valuation': 0.95},
        '消费电子': {'export': 1.2, 'dividend': 0.9, 'valuation': 1.0},  # 消费电子更看出口
        '家电出口': {'dividend': 1.1, 'valuation': 1.1, 'growth': 0.9},  # 家电更看分红和估值
        '汽车出口': {'export': 1.1, 'growth': 1.1, 'dividend': 0.9},
        '船舶制造': {'export': 1.2, 'valuation': 0.9, 'dividend': 0.9},  # 船舶更看出口
        '工程机械': {'export': 1.1, 'valuation': 1.0, 'dividend': 0.9},
        '化工': {'export': 1.0, 'valuation': 1.1, 'dividend': 1.0},
        '通信设备': {'export': 1.1, 'growth': 1.1, 'valuation': 0.9},
        '发动机': {'export': 1.0, 'valuation': 1.1, 'dividend': 1.0},
        'CXO': {'export': 1.1, 'growth': 1.2, 'valuation': 0.9},
        '潮玩': {'export': 1.1, 'growth': 1.2, 'valuation': 0.9},
        '珠宝': {'dividend': 1.1, 'valuation': 1.1, 'growth': 0.9},
    }

    weights = industry_weights.get(industry, {'export': 1.0, 'dividend': 1.0, 'growth': 1.0, 'valuation': 1.0})
    thresholds = industry_thresholds.get(industry, {'high': 30, 'medium': 15})

    if intensity == 'high':
        # 使用更平滑的评分公式：基础分 + 超额部分的对数奖励
        import math
        base_pts = 15
        excess_pct = max(0, est_pct - thresholds['high'])
        bonus = min(10, int(math.log1p(excess_pct) * 3))  # 对数增长，避免极端值
        pts = base_pts + bonus
        # 应用行业权重
        pts = int(pts * weights.get('export', 1.0))
        pts = min(pts, 25)  # 确保不超过满分
        score += pts
        details.append(f"出口强度:高(海外~{est_pct}%) +{pts}")
    elif intensity == 'medium':
        pts = 10
        pts = int(pts * weights.get('export', 1.0))
        pts = min(pts, 25)
        score += pts
        details.append(f"出口强度:中(海外~{est_pct}%) +{pts}")
    else:
        pts = 3  # 低出口强度给更低分
        pts = int(pts * weights.get('export', 1.0))
        pts = min(pts, 25)
        score += pts
        details.append(f"出口强度:低 +{pts}")

    # 2. 股息率 (20分) - 保持原有逻辑，但增加分红可持续性检查
    div_yield = stock.get('dividend_yield') or 0
    dividend_ratio = stock.get('dividend_ratio')  # 分红率（分红/利润）

    if div_yield >= 5:
        # 高股息但分红率过高可能是不可持续的
        if dividend_ratio and dividend_ratio > 80:
            pts = 15  # 降权
            details.append(f"股息率{div_yield:.1f}% 但分红率{dividend_ratio:.0f}%偏高 +{pts}")
        else:
            pts = 20
            details.append(f"股息率{div_yield:.1f}% 高股息 +{pts}")
    elif div_yield >= 3:
        pts = 15
        details.append(f"股息率{div_yield:.1f}% 中等 +{pts}")
    elif div_yield >= 2:
        pts = 10
        details.append(f"股息率{div_yield:.1f}% +{pts}")
    elif div_yield >= 1.5:
        pts = 5
        details.append(f"股息率{div_yield:.1f}% +{pts}")
    else:
        pts = 0
    # 股息率<1.5%不得分，不扣分

    # 应用行业权重
    pts = int(pts * weights.get('dividend', 1.0))
    pts = min(pts, 20)  # 确保不超过满分
    score += pts

    # 3. 连续分红年数 (10分) - 数据缺失时降权
    years = stock.get('consecutive_years')
    if years is not None:
        if years >= 10:
            score += 10
            details.append(f"连续分红{years}年 +10")
        elif years >= 5:
            score += 7
            details.append(f"连续分红{years}年 +7")
        elif years >= 3:
            score += 4
            details.append(f"连续分红{years}年 +4")
        # <3年已被硬过滤
    else:
        # 港股无此数据，给较低默认分
        score += 2
        missing_data_penalty += 3
        details.append("连续分红:无数据 +2")

    # 4. ROE (15分) - 数据缺失时大幅降权
    roe = stock.get('roe')
    if roe is not None:
        if roe >= 20:
            score += 15
            details.append(f"ROE={roe:.1f}% 卓越 +15")
        elif roe >= 15:
            score += 12
            details.append(f"ROE={roe:.1f}% 优秀 +12")
        elif roe >= 10:
            score += 8
            details.append(f"ROE={roe:.1f}% 良好 +8")
        elif roe >= 5:
            score += 4
            details.append(f"ROE={roe:.1f}% +4")
        else:
            score += 1
            details.append(f"ROE={roe:.1f}% 偏低 +1")
    else:
        # ROE缺失是严重问题，大幅降权
        score += 0
        missing_data_penalty += 8
        details.append("ROE无数据 +0 (严重缺失)")

    # 5. 毛利率 - 护城河 (10分) - 数据缺失时降权
    gm = stock.get('gross_margin')
    if gm is not None:
        if gm >= 40:
            score += 10
            details.append(f"毛利率{gm:.1f}% 宽护城河 +10")
        elif gm >= 25:
            score += 7
            details.append(f"毛利率{gm:.1f}% 中护城河 +7")
        elif gm >= 15:
            score += 4
            details.append(f"毛利率{gm:.1f}% +4")
        else:
            score += 1
            details.append(f"毛利率{gm:.1f}% 偏低 +1")
    else:
        # 毛利率缺失，降权
        score += 0
        missing_data_penalty += 5
        details.append("毛利率无数据 +0 (缺失)")

    # 6. 估值合理性 (10分) - 增加PEG检查
    pe = stock.get('pe') or 999
    pb = stock.get('pb') or 999
    profit_growth = stock.get('profit_growth')

    val_pts = 0
    if pe > 0 and pe < 15:
        val_pts += 5
    elif pe < 25:
        val_pts += 3
    elif pe < 35:
        val_pts += 1

    if pb > 0 and pb < 2:
        val_pts += 3
    elif pb < 4:
        val_pts += 2

    if div_yield and div_yield > 2:
        val_pts += 2

    # PEG检查：PE/增长率，PEG<1可能是低估
    if pe > 0 and pe < 999 and profit_growth and profit_growth > 0:
        peg = pe / profit_growth
        if peg < 0.5:
            val_pts += 2  # PEG极低，可能严重低估
            details.append(f"PEG={peg:.1f} 可能低估 +2")
        elif peg > 2:
            val_pts -= 1  # PEG过高，估值偏贵
            details.append(f"PEG={peg:.1f} 估值偏贵 -1")

    # 应用行业权重
    val_pts = int(val_pts * weights.get('valuation', 1.0))
    val_pts = min(val_pts, 10)  # 确保不超过满分
    score += val_pts
    if val_pts > 0:
        details.append(f"估值 PE={pe:.1f} PB={pb:.1f} +{val_pts}")

    # 7. 财务健康 - 负债率 (10分) - 数据缺失时降权
    debt = stock.get('debt_ratio')
    if debt is not None:
        if debt < 40:
            score += 10
            details.append(f"负债率{debt:.1f}% 稳健 +10")
        elif debt < 60:
            score += 7
            details.append(f"负债率{debt:.1f}% 可接受 +7")
        elif debt < 70:
            score += 4
            details.append(f"负债率{debt:.1f}% 偏高 +4")
        else:
            score += 1
            details.append(f"负债率{debt:.1f}% 高风险 +1")
    else:
        # 负债率缺失，降权
        score += 0
        missing_data_penalty += 5
        details.append("负债率无数据 +0 (缺失)")

    # 应用数据缺失惩罚
    if missing_data_penalty > 0:
        score = max(0, score - missing_data_penalty)
        details.append(f"数据缺失扣分 -{missing_data_penalty}")

    return min(score, 100), " | ".join(details)


def generate_risk_tags(stock: dict, fx_data: Optional[dict] = None) -> list:
    """
    为股票生成风险标签 (机构级增强版)

    Args:
        stock: 股票数据
        fx_data: 汇率数据 (可选, 用于汇率风险动态评估)

    Returns:
        list: 风险标签列表，每个标签格式为 {'tag': '标签名', 'level': 'high/medium/low', 'desc': '描述'}
    """
    tags = []
    code = stock.get('code', '')
    export_info = EXPORT_STOCKS.get(code, {})
    industry = export_info.get('industry', '')
    tariff_info = TARIFF_RISK_MATRIX.get(industry, {})
    est_overseas_pct = export_info.get('est_overseas_pct', 0)

    # 1. 关税/贸易政策风险 (使用量化矩阵)
    if tariff_info:
        risk_level_raw = tariff_info.get('risk_level', '')
        tag_level = 'high' if risk_level_raw in ('critical', 'high') else ('medium' if risk_level_raw == 'medium' else 'low')
        recent = tariff_info.get('recent_policy', '')
        detail = tariff_info.get('detail', '')
        mitigation = tariff_info.get('mitigation', '')
        tags.append({
            'tag': '关税/贸易政策风险' if risk_level_raw == 'critical' else '贸易政策风险',
            'level': tag_level,
            'desc': detail,
            'mitigation': mitigation,
            'recent_policy': recent,
            'risk_score': tariff_info.get('score', 0),
        })

    # 2. 估值泡沫风险
    pe = stock.get('pe')
    if pe and pe > 50:
        tags.append({
            'tag': '估值偏高',
            'level': 'high',
            'desc': f'PE={pe:.1f}，估值可能存在泡沫'
        })
    elif pe and pe > 35:
        tags.append({
            'tag': '估值较高',
            'level': 'medium',
            'desc': f'PE={pe:.1f}，估值偏贵'
        })

    # 3. 高负债风险
    debt = stock.get('debt_ratio')
    if debt and debt > 70:
        tags.append({
            'tag': '高负债风险',
            'level': 'high',
            'desc': f'资产负债率{debt:.1f}%，财务风险较高'
        })
    elif debt and debt > 60:
        tags.append({
            'tag': '负债偏高',
            'level': 'medium',
            'desc': f'资产负债率{debt:.1f}%，需关注'
        })

    # 4. 分红不可持续风险
    div_yield = stock.get('dividend_yield', 0)
    dividend_ratio = stock.get('dividend_ratio')
    if div_yield > 4 and dividend_ratio and dividend_ratio > 80:
        tags.append({
            'tag': '分红不可持续',
            'level': 'high',
            'desc': f'股息率{div_yield:.1f}%但分红率{dividend_ratio:.0f}%过高，可能不可持续'
        })

    # 5. 汇率风险 (动态评估)
    if est_overseas_pct >= 60:
        # 高海外营收: 动态汇率影响
        fx_desc = f'海外营收占比~{est_overseas_pct}%，受汇率波动影响较大'
        if fx_data:
            change_30d = fx_data.get('change_30d_pct', 0)
            trend = fx_data.get('trend', '')
            if abs(change_30d) > 1:
                impact = '利好' if change_30d > 0 else '利空'
                fx_desc += f'。当前人民币{trend}({change_30d:+.2f}%)，{impact}出口营收换算'
        tags.append({
            'tag': '汇率风险',
            'level': 'high' if est_overseas_pct >= 75 else 'medium',
            'desc': fx_desc,
        })
    elif est_overseas_pct >= 40:
        tags.append({
            'tag': '汇率敏感',
            'level': 'medium',
            'desc': f'海外营收占比~{est_overseas_pct}%，有一定汇率敞口',
        })

    # 6. 数据缺失风险
    roe = stock.get('roe')
    gross_margin = stock.get('gross_margin')
    if roe is None or gross_margin is None:
        tags.append({
            'tag': '数据不完整',
            'level': 'medium',
            'desc': '关键财务数据缺失，影响评分准确性'
        })

    # 7. 地缘政治风险（特定行业）
    geopolitical_risk_industries = {
        '安防设备': '海康威视已被列入美国实体清单，北美市场受限',
        '通信设备': '5G设备在部分西方国家被禁用，面临技术封锁',
        '半导体': '美国对华半导体出口管制持续收紧',
        'CXO': '美国《生物安全法案》可能限制中资CXO企业',
        '动力电池': 'IRA法案限制中国电池享受美国补贴',
        '新能源车': '美国/欧盟对中国电动车加征高额关税',
    }
    if industry in geopolitical_risk_industries:
        tags.append({
            'tag': '地缘政治风险',
            'level': 'high',
            'desc': geopolitical_risk_industries[industry]
        })

    return tags


# ============================================================
# 缓存 - 分层缓存策略
# ============================================================

from app.core.cache import get_cache as _base_get_cache, set_cache as _set_cached

# 分层缓存时间
CACHE_TTL = {
    'realtime': 60,        # 实时数据1分钟
    'financial': 1800,     # 财务数据30分钟
    'philosophy': 3600,    # 理念数据1小时
    'screener': 300,       # 筛选结果5分钟
}

def _get_cached(key: str, cache_type: str = 'screener'):
    """获取缓存，根据数据类型使用不同的TTL"""
    ttl = CACHE_TTL.get(cache_type, 300)
    return _base_get_cache(key, ttl_seconds=ttl)


# ============================================================
# 主筛选函数
# ============================================================

def screen_export_champions(market: str = 'all', min_score: int = 0,
                            min_dividend_yield: float = 1.5,
                            top_n: int = 50) -> dict:
    """
    出口冠军筛选 (机构级增强版)

    Args:
        market: 'A', 'HK', 'all'
        min_score: 最低分数
        min_dividend_yield: 最低股息率(%)
        top_n: 返回前N只
    """
    cache_key = f"export_{market}_{min_score}_{min_dividend_yield}_{top_n}"
    cached = _get_cached(cache_key, cache_type='screener')
    if cached:
        return cached

    # 获取汇率数据 (全局复用)
    fx_data = get_exchange_rate_data()

    stocks = []

    # Fetch A-share stocks
    if market in ('A', 'all'):
        for code in EXPORT_STOCKS:
            if code in HK_EXPORT_STOCKS:
                continue
            stock = _get_a_stock_data(code)
            if stock:
                stocks.append(stock)

    # Fetch HK stocks
    if market in ('HK', 'all'):
        for code in HK_EXPORT_STOCKS:
            stock = _get_hk_data(code)
            if stock:
                stocks.append(stock)

    # Score and filter
    filtered_stocks = []
    for stock in stocks:
        # Hard filter: dividend yield
        dy = stock.get('dividend_yield') or 0
        if dy < min_dividend_yield:
            continue

        # Hard filter: consecutive years (A-shares only)
        cy = stock.get('consecutive_years')
        if cy is not None and cy < 3:
            continue

        # Value investing hard filters
        pe = stock.get('pe')
        pb = stock.get('pb')
        roe = stock.get('roe')

        # PE must be positive and <= 50 (exclude negative earnings and extreme overvaluation)
        if pe is not None and (pe <= 0 or pe > 50):
            continue

        # PB must be <= 5 if available (exclude extreme overvaluation)
        # Skip HK stocks with PB=None/0 (data quality issue from Tencent API)
        if pb is not None and pb > 5:
            continue

        # ROE must be positive if available (exclude loss-making companies)
        # Skip HK stocks with ROE=None (data quality issue)
        if roe is not None and roe < 0:
            continue

        # Export champion score
        export_score, export_detail = _score_export_champion(stock)

        # Value investing master scores
        buffett_score, buffett_detail = _score_buffett(stock)
        munger_score, munger_detail = _score_munger(stock)
        li_lu_score, li_lu_detail = _score_li_lu(stock)
        duan_score, duan_detail = _score_duan_yongping(stock)
        vi_avg = round((buffett_score + munger_score + li_lu_score + duan_score) / 4)

        # Combined score: export 40% + value investing avg 60%
        combined_score = round(export_score * 0.4 + vi_avg * 0.6)

        # Generate risk tags (with exchange rate data)
        risk_tags = generate_risk_tags(stock, fx_data=fx_data)

        # Calculate risk-adjusted score
        high_risk_count = sum(1 for tag in risk_tags if tag['level'] == 'high')
        medium_risk_count = sum(1 for tag in risk_tags if tag['level'] == 'medium')
        risk_penalty = high_risk_count * 5 + medium_risk_count * 2
        risk_adjusted_score = max(0, combined_score - risk_penalty)

        if combined_score >= min_score:
            filtered_stocks.append({
                **stock,
                'export_score': export_score,
                'export_detail': export_detail,
                'buffett_score': buffett_score,
                'buffett_detail': buffett_detail,
                'munger_score': munger_score,
                'munger_detail': munger_detail,
                'li_lu_score': li_lu_score,
                'li_lu_detail': li_lu_detail,
                'duan_score': duan_score,
                'duan_detail': duan_detail,
                'vi_avg_score': vi_avg,
                'combined_score': combined_score,
                'risk_adjusted_score': risk_adjusted_score,
                'risk_tags': risk_tags,
                'risk_penalty': risk_penalty,
                'tariff_risk': TARIFF_RISK_MATRIX.get(stock.get('industry', ''), {}),
                'main_export_markets': EXPORT_STOCKS.get(stock.get('code', ''), {}).get('main_export_markets', []),
                'competitive_advantage': EXPORT_STOCKS.get(stock.get('code', ''), {}).get('competitive_advantage', ''),
                'match_level': (
                    'excellent' if risk_adjusted_score >= 80 else
                    'good' if risk_adjusted_score >= 65 else
                    'fair' if risk_adjusted_score >= 50 else
                    'poor'
                ),
            })

    # Peer comparison (industry analysis)
    peer_comparison = get_peer_comparison(filtered_stocks)

    # Enrich stocks with peer ranking data
    results = []
    for stock in filtered_stocks:
        industry = stock.get('industry', '')
        code = stock.get('code', '')
        peer = peer_comparison.get(industry, {})
        stock_rankings = peer.get('stock_rankings', {}).get(code, {})
        stock['peer_rankings'] = stock_rankings.get('rankings', {})
        stock['peer_stats'] = peer.get('stats', {}) if peer.get('has_comparison') else None
        stock['peer_count'] = peer.get('count', 1)
        results.append(stock)

    # Sort by risk-adjusted score descending
    results.sort(key=lambda x: x['risk_adjusted_score'], reverse=True)
    results = results[:top_n]

    result = {
        'stocks': results,
        'total': len(results),
        'market': market,
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'criteria': {
            'min_score': min_score,
            'min_dividend_yield': min_dividend_yield,
            'top_n': top_n,
        },
        'exchange_rate': fx_data,
        'peer_comparison': {k: v for k, v in peer_comparison.items() if v.get('has_comparison')},
        'data_sources': {
            'realtime': '通达信/新浪财经/腾讯财经/东方财富 (多源容错)',
            'financials': '东方财富API',
            'exchange_rate': 'AKShare -> 中国银行外汇牌价',
            'export_pct': '公司年报/公告 (静态数据, 定期更新)',
            'tariff_risk': '基于2024-2025年公开贸易政策整理',
        },
    }

    _set_cached(cache_key, result)
    return result


# ============================================================
# 筛选理念
# ============================================================

def get_philosophy() -> dict:
    """返回出口冠军筛选理念 — 出口竞争力 + 价值投资双轮驱动"""
    cache_key = "export_philosophy"
    cached = _get_cached(cache_key, cache_type='philosophy')
    if cached:
        return cached

    philosophy = {
        'name': '出口冠军筛选',
        'title': '出口竞争力 × 价值投资：在日本化时代寻找全球化赢家',
        'core_thesis': '中国正在经历类似日本1990年后的估值中枢下移。日本30年的教训只有一个结论：全球化是估值修复的唯一确定性路径。纯内需消费股的PE从60-70倍永久性下移到12-15倍，而成功全球化的公司（尤妮佳海外营收从20%到60%、资生堂靠中国市场修复估值、优衣库PE长期维持30-40倍）成为唯一的例外者。',
        'core_idea': '在中国经济"日本化"的宏观背景下（人口下降、房地产下行、通缩压力），纯内需企业面临估值中枢永久性下移的风险。本筛选池聚焦那些已经建立全球竞争力、海外营收占比高、有持续出口能力的企业——它们是日本化时代最有可能"逃出生天"的标的。同时要求一定的分红率，在低增长时代提供确定性回报。',
        'japan_mirror': {
            'title': '日本镜鉴：谁逃过了估值下移？',
            'content': '日本消费股PE从1989年的60-70倍永久性下移到2010年代的12-15倍。逃过下移的只有三类公司：(1) 海外扩张成功者——尤妮佳(海外营收20%→60%,PE修复到25-30倍)、资生堂(中国市场爆发,PE回到30倍+)；(2) 品类结构性受益者——亚瑟士(全球跑步热潮,PE从10倍修复到20倍)、养乐多(全球化+健康概念)；(3) 极致效率者——优衣库(制造零售业+全球化,PE长期30-40倍)。它们的共同特征：增长引擎从"日本国内"切换到了"全球市场"。',
            'lesson': '只守着国内市场的消费股，无一例外经历了估值中枢的永久性下移。全球化不是加分项，而是生存条件。',
        },
        'china_context': {
            'title': '中国现状：估值中枢已下移30-50%',
            'content': '茅台PE从35-40倍跌到22-25倍，海天从55-65倍跌到30-35倍，伊利从25-30倍跌到15-18倍。机构共识：新估值中枢在15-25倍PE，回到2020-2021年水平(30-50倍)已无可能。三个剧本：温和日本化(45%概率,PE稳在15-22倍)、深度日本化(25%概率,PE跌到10-15倍)、中国特色路径(30%概率,改革激活内需,PE回到25-30倍)。',
            'implication': '无论哪个剧本，有全球竞争力的企业都处于更有利的位置——它们的增长引擎不依赖单一的国内市场。',
        },
        'why_export_why_dividend': {
            'title': '为什么是"出口+分红"？',
            'reasons': [
                '出口 = 增长引擎的多元化。当国内消费增速从8%降到3%，海外市场的增量就是估值的救命稻草。',
                '分红 = 低增长时代的确定性回报。当估值扩张不再可期，股息率2-4%就是核心回报来源。',
                '出口企业有更强的定价权。面对国内通缩压力，海外市场往往有更好的定价环境。',
                '分红证明管理层愿意与股东分享利润，而非盲目再投资——在低增长时代，这比增长更珍贵。',
            ],
        },
        'scoring_dimensions': [
            {
                'dimension': '出口强度 (25分)',
                'description': '企业海外市场收入占比和全球竞争力——这是筛选的第一权重',
                'criteria': [
                    '高出口强度(海外收入>30%): 15-25分——已建立全球竞争力',
                    '中出口强度(海外收入10-30%): 10分——正在出海',
                    '低出口强度(海外收入<10%): 5分——仍以国内为主',
                ],
                'japan_parallel': '尤妮佳海外营收从20%到60%的过程中，PE从15倍修复到25-30倍',
            },
            {
                'dimension': '股息率 (20分)',
                'description': '低增长时代的核心回报来源',
                'criteria': [
                    '股息率>=5%: 20分',
                    '股息率>=3%: 15分',
                    '股息率>=2%: 10分',
                    '股息率>=1.5%: 5分',
                ],
                'japan_parallel': '日本消费股在估值下移过程中，股息率从0.5-1%上升到2-2.5%，成为主要回报来源',
            },
            {
                'dimension': '连续分红年数 (10分)',
                'description': '分红的持续性证明管理层的股东回报意愿',
                'criteria': [
                    '连续10年以上: 10分',
                    '连续5年以上: 7分',
                    '连续3年以上: 4分',
                ],
            },
            {
                'dimension': 'ROE (15分)',
                'description': '资本回报效率——全球化企业的ROE往往更可持续',
                'criteria': [
                    'ROE>=20%: 卓越 15分',
                    'ROE>=15%: 优秀 12分',
                    'ROE>=10%: 良好 8分',
                    'ROE>=5%: 一般 4分',
                ],
            },
            {
                'dimension': '毛利率 (10分)',
                'description': '定价权和护城河——出口企业的毛利率反映全球竞争力',
                'criteria': [
                    '毛利率>=40%: 宽护城河 10分',
                    '毛利率>=25%: 中护城河 7分',
                    '毛利率>=15%: 窄护城河 4分',
                ],
            },
            {
                'dimension': '估值合理性 (10分)',
                'description': '在估值中枢下移时代，买贵了就是最大的风险',
                'criteria': [
                    'PE<15且PB<2: 估值偏低',
                    'PE<25且PB<4: 估值合理',
                    '高股息率额外加分',
                ],
            },
            {
                'dimension': '财务健康 (10分)',
                'description': '资产负债率——在去杠杆化时代，低负债就是安全边际',
                'criteria': [
                    '负债率<40%: 稳健 10分',
                    '负债率<60%: 可接受 7分',
                    '负债率<70%: 偏高 4分',
                ],
            },
        ],
        'hard_filters': [
            '股息率 >= 1.5% (出口企业reinvest较多，门槛适当降低)',
            '连续分红 >= 3年 (确保分红意愿)',
        ],
        'industry_categories': [
            {'name': '家电出口', 'examples': '美的、海尔、格力、苏泊尔、海信', 'global_note': '家电是中国最早建立全球竞争力的行业，美的海外营收占比~40%，海尔~50%'},
            {'name': '动力电池/新能源车', 'examples': '宁德时代、比亚迪、赣锋锂业、长城汽车', 'global_note': '中国在新能源领域的全球领先优势是结构性的，类似日本汽车业1980年代的崛起'},
            {'name': '光伏/太阳能', 'examples': '隆基绿能、通威股份、晶澳科技', 'global_note': '中国光伏产能占全球80%+，是真正的全球垄断级产业'},
            {'name': '船舶制造/重工', 'examples': '中国船舶、中国重工', 'global_note': '中国已超越韩国成为全球第一造船大国，订单占比50%+'},
            {'name': '工程机械', 'examples': '三一重工、中联重科', 'global_note': '三一海外营收占比~45%，正在复制卡特彼勒的全球化路径'},
            {'name': '电子/消费电子', 'examples': '海康威视、京东方、歌尔股份、立讯精密、工业富联', 'global_note': '消费电子供应链的全球化程度最高，立讯海外占比~80%'},
            {'name': '化工/材料', 'examples': '万华化学、杰瑞股份', 'global_note': '万华化学是全球MDI龙头，海外占比~45%'},
            {'name': '通信/半导体', 'examples': '中兴通讯、韦尔股份', 'global_note': '半导体设计的全球化程度高，韦尔海外占比~60%'},
            {'name': '港股出口龙头', 'examples': '小米、比亚迪H、海尔H、泡泡玛特、药明生物', 'global_note': '港股上市公司往往有更高的国际化程度和更透明的治理结构'},
        ],

        # ============================================================
        # 价值投资四位大师评分体系
        # ============================================================
        'value_investing_integration': {
            'title': '价值投资四位大师评分体系',
            'description': '出口冠军筛选不仅关注全球化竞争力，还必须通过价值投资的严格检验。每只股票同时接受四位投资大师的独立评分，确保既具备出口竞争力，又满足价值投资标准。',
            'scoring_model': '综合评分 = 出口竞争力(40%) + 价值投资均分(60%)。价值投资均分 = (巴菲特 + 芒格 + 李录 + 段永平) / 4',
            'masters': [
                {
                    'name': '巴菲特',
                    'focus': '护城河 + ROE + 安全边际',
                    'framework': 'ROE(25分) + 毛利率护城河(20分) + 净利率(15分) + 估值安全边际(20分) + 财务健康(10分) + 成长性(10分)',
                    'key_insight': '"如果只能用一个指标选股，那就是ROE" — 持续高ROE说明管理层资本配置能力强，护城河宽广',
                    'criteria': ['ROE>=20%: 优秀', '毛利率>=40%: 中等护城河', 'PE<15且PB<2: 低估', '负债率<30%: 财务稳健'],
                },
                {
                    'name': '芒格',
                    'focus': '企业质量 + 管理层理性 + 风险排除',
                    'framework': '企业质量(25分) + 管理层理性(20分) + 风险排除(20分) + 估值(15分) + 净利率(10分) + 成长性(10分)',
                    'key_insight': '"反过来想，总是反过来想" — 先排除风险，再寻找机会。检查清单法系统性排除高负债、负增长、低ROE',
                    'criteria': ['利润增速>营收增速: 管理层高效', '负债率<35%: 理性保守', '风险排除: 无高负债/负增长/低ROE'],
                },
                {
                    'name': '李录',
                    'focus': 'ROE + 护城河 + 结构性增长',
                    'framework': 'ROE质量(25分) + 护城河(20分) + 成长性(20分) + 估值(15分) + 财务健康(10分) + 股息回报(10分)',
                    'key_insight': '只投资自己真正理解的企业，以5-10年为投资周期。在中国市场，管理层品质和行业结构性增长尤为重要',
                    'criteria': ['ROE>=15%: 良好', '毛利率>=30%且净利率>=12%: 护城河', '营收和利润均>8%: 稳健增长'],
                },
                {
                    'name': '段永平',
                    'focus': '商业模式 + 成长性 + 财务健康',
                    'framework': '商业模式(30分) + 成长性(25分) + 财务健康(15分) + 估值(15分) + 股东回报(10分) + 低负债安全(5分)',
                    'key_insight': '"买股票就是买公司，买公司就是买未来现金流的折现" — 好商业模式 > 好管理 > 好价格',
                    'criteria': ['ROE>=18%且毛利率>=30%: 好商业模式', '营收利润均>8%: 好生意自然增长', '负债率<25%: 非常健康'],
                },
            ],
            'match_levels': {
                'excellent': '综合80+分 — 出口竞争力强且四位大师都认可的优秀企业',
                'good': '综合65-79分 — 全球化布局良好，多数大师会关注的优质标的',
                'fair': '综合50-64分 — 部分维度突出，出口或价值投资某一方面有待提升',
                'poor': '综合<50分 — 出口竞争力或价值投资标准不达标',
            },
            'risks': [
                '价值陷阱：低PE/PB可能反映基本面恶化，而非低估',
                '护城河侵蚀：技术变革可能摧毁看似牢固的护城河',
                '出口依赖风险：过度依赖海外市场可能受贸易政策影响',
                '估值锚定：过度依赖历史估值可能错过结构性变化',
                '中国市场特殊性：政策风险、公司治理、信息不对称',
            ],
            'risk_tags_system': {
                'title': '风险标签系统 (机构级增强)',
                'description': '每只股票会根据其行业、财务、估值、汇率、关税政策等多维度特征自动生成风险标签。关税风险使用量化矩阵评估(0-100分)，汇率风险接入实时USD/CNY牌价动态评估。',
                'tags': [
                    {'tag': '关税/贸易政策风险', 'level': 'critical', 'desc': '光伏(关税>100%)、新能源车(美国100%关税)面临极高贸易壁垒'},
                    {'tag': '贸易政策风险', 'level': 'high', 'desc': '动力电池、半导体、安防、通信面临出口管制/实体清单'},
                    {'tag': '地缘政治风险', 'level': 'high', 'desc': '安防、通信、半导体、CXO等行业可能面临制裁或技术封锁'},
                    {'tag': '估值偏高', 'level': 'high', 'desc': 'PE>50，估值可能存在泡沫'},
                    {'tag': '高负债风险', 'level': 'high', 'desc': '资产负债率>70%，财务风险较高'},
                    {'tag': '分红不可持续', 'level': 'high', 'desc': '股息率高但分红率>80%，可能不可持续'},
                    {'tag': '汇率风险', 'level': 'high', 'desc': '海外营收占比>=60%，受汇率波动影响大(实时USD/CNY评估)'},
                    {'tag': '汇率敏感', 'level': 'medium', 'desc': '海外营收占比40-60%，有一定汇率敞口'},
                    {'tag': '数据不完整', 'level': 'medium', 'desc': '关键财务数据缺失，影响评分准确性'},
                ],
                'scoring_impact': '高风险标签每个扣5分，中风险标签每个扣2分，从综合得分中扣除得到风险调整后得分。',
                'new_features': [
                    '关税风险量化矩阵: 基于2024-2025年公开贸易政策，为每个行业打分(0-100)并提供最新政策动态和企业应对措施',
                    '汇率风险实时评估: 接入AKShare中国银行外汇牌价，计算7/30/90天汇率变动对高海外营收企业的影响',
                    '同行业对比排名: 每只股票在其所在行业内进行ROE/股息率/估值/海外占比多维度排名',
                ],
            },
            'tariff_risk_matrix': {
                'title': '关税/贸易政策风险矩阵',
                'description': '基于2024-2025年最新贸易政策，对每个行业进行量化风险评估(0-100分)。分值越高风险越大。',
                'disclaimer': '关税政策变化频繁，本矩阵仅供参考，需定期更新。不构成投资建议。',
                'critical_risks': [
                    {'industry': '光伏', 'score': 95, 'detail': '美国对华光伏关税累计超100%(301+AD/CVD)'},
                    {'industry': '新能源车', 'score': 85, 'detail': '美国100%关税(2024)、欧盟17-36%反补贴关税'},
                ],
                'high_risks': [
                    {'industry': '动力电池', 'score': 80, 'detail': 'IRA法案限制+欧盟反补贴调查'},
                    {'industry': '半导体', 'score': 80, 'detail': '美国出口管制+实体清单'},
                    {'industry': '安防设备', 'score': 75, 'detail': '海康威视已列入实体清单'},
                    {'industry': '通信设备', 'score': 75, 'detail': '5G设备在部分西方国家被禁'},
                    {'industry': 'CXO', 'score': 70, 'detail': 'BIOSECURE Act可能限制中资CXO'},
                ],
                'low_risks': [
                    {'industry': '船舶制造', 'score': 15, 'detail': '全球招标，无明显贸易壁垒'},
                    {'industry': '潮玩', 'score': 15, 'detail': '消费品类，贸易壁垒极低'},
                    {'industry': '面板', 'score': 20, 'detail': '全球化供应链，贸易壁垒低'},
                    {'industry': '化工', 'score': 25, 'detail': 'MDI等化工品属全球化大宗商品'},
                ],
            },
            'exchange_rate_monitoring': {
                'title': '汇率影响实时监控',
                'description': '接入AKShare中国银行外汇牌价数据，实时评估USD/CNY汇率变动对出口冠军企业的影响。',
                'data_source': 'AKShare -> 中国银行外汇牌价 (BOC)',
                'update_frequency': '每日',
                'metrics': [
                    'USD/CNY最新中间价',
                    '7天/30天/90天汇率变动百分比',
                    '汇率趋势判断(人民币升值/贬值/稳定)',
                    '高海外营收企业(>=50%)的营收汇率影响估算',
                ],
                'impact_logic': '人民币贬值(USD/CNY上升) -> 利好出口企业(海外营收换算为更多人民币)。反之亦然。海外营收占比越高，汇率敏感度越大。',
            },
            'peer_comparison': {
                'title': '同行业公司对比分析',
                'description': '对筛选池中同行业的公司进行多维度对比排名，帮助投资者在行业内选出最优标的。',
                'dimensions': [
                    'ROE排名: 行业内资本回报效率对比',
                    '股息率排名: 行业内分红回报对比',
                    'PE排名: 行业内估值水平对比(越低越好)',
                    '海外营收占比排名: 行业内全球化程度对比',
                ],
                'additional_info': '同行业均值/中位数/最高/最低值供参考',
            },
        },
    }

    # Cache the philosophy
    _set_cached(cache_key, philosophy)
    return philosophy
