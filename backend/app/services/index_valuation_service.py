"""指数估值数据服务 - 全球指数PE/PB/ROE/股息率/历史收益

数据源：
- 中证指数（A股）：akshare
- 恒生指数公司（港股）：akshare + 乐咕乐股
- multpl.com（标普500）：网页爬取
- Yahoo Finance（全球指数）：新浪财经API获取K线
- 东方财富（基金信息）：网页爬取
"""

import requests
import re
import math
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from app.core.cache import get_cache as _base_get_cache, set_cache as _set_cached

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

_CACHE_TTL_VALUATION = 3600   # 估值数据缓存1小时
_CACHE_TTL_RETURN = 86400     # 历史收益缓存1天
_CACHE_TTL_FUND = 86400       # 基金信息缓存1天


def _get_cached(key: str, ttl: int = _CACHE_TTL_VALUATION):
    return _base_get_cache(key, ttl_seconds=ttl)


# ============================================================
# 指数配置 - 全球16个指数
# ============================================================

INDEX_CONFIG = {
    # === 宽基指数 ===
    # 中国
    "000510": {
        "name": "中证A500", "name_en": "CSI A500", "category": "宽基", "country": "中国",
        "csindex": "000510", "lg_name": None, "lg_pe_name": "中证A500",
        "fund_code": "159338", "fund_name": "中证A500ETF",
        "fund_type": "场内ETF", "fund_channel": "券商APP",
        "description": "从A股中选取500只各行业龙头股，覆盖约50%市值。行业分布均衡，兼顾成长与价值，是A股最具代表性的宽基指数之一。",
        "highlights": ["行业均衡配置", "覆盖A股核心资产", "适合长期定投"],
    },
    "000300": {
        "name": "沪深300", "name_en": "CSI 300", "category": "宽基", "country": "中国",
        "csindex": "000300", "lg_name": "沪深300", "lg_pe_name": "沪深300",
        "fund_code": "510300", "fund_name": "沪深300ETF",
        "fund_type": "场内ETF", "fund_channel": "券商APP",
        "description": "沪深两市市值最大、流动性最好的300只股票，占A股总市值约60%。是中国股市的'晴雨表'，机构投资者的核心配置。",
        "highlights": ["A股旗舰指数", "流动性最佳", "机构标配"],
    },
    "000905": {
        "name": "中证500", "name_en": "CSI 500", "category": "宽基", "country": "中国",
        "csindex": "000905", "lg_name": "中证500", "lg_pe_name": "中证500",
        "fund_code": "510500", "fund_name": "中证500ETF",
        "fund_type": "场内ETF", "fund_channel": "券商APP",
        "description": "排除沪深300后，市值排名前500的中盘股。代表中国经济中坚力量，成长性优于大盘股，波动也更大。",
        "highlights": ["中盘股代表", "成长性较强", "弹性较大"],
    },
    "399006": {
        "name": "创业板指", "name_en": "ChiNext", "category": "宽基", "country": "中国",
        "csindex": "399006", "lg_name": None, "lg_pe_name": "创业板指",
        "fund_code": "159915", "fund_name": "创业板ETF",
        "fund_type": "场内ETF", "fund_channel": "券商APP",
        "description": "创业板市值最大、流动性最好的100只股票。以新能源、医药、科技等新兴产业为主，高成长高波动。",
        "highlights": ["新兴产业集中", "高成长高波动", "适合风险偏好者"],
    },
    # 港股
    "HSI": {
        "name": "恒生指数", "name_en": "Hang Seng", "category": "宽基", "country": "中国香港",
        "csindex": None, "lg_name": None, "etf_ticker": "EWH",
        "fund_code": "159920", "fund_name": "恒生ETF",
        "fund_type": "场内ETF", "fund_channel": "券商APP",
        "description": "香港股市旗舰指数，包含港股市值最大、流动性最好的50只股票。金融、地产、科技巨头云集，股息率较高。",
        "highlights": ["港股旗舰", "高股息", "金融地产权重高"],
    },
    "HSTECH": {
        "name": "恒生科技", "name_en": "Hang Seng Tech", "category": "宽基", "country": "中国香港",
        "csindex": None, "lg_name": None, "etf_ticker": "KWEB",
        "fund_code": "513180", "fund_name": "恒生科技ETF",
        "fund_type": "场内ETF", "fund_channel": "券商APP",
        "description": "港股上市的30家最大科技企业，包括腾讯、阿里、美团等。是中国科技行业的风向标，波动较大但成长性强。",
        "highlights": ["中国科技龙头", "腾讯阿里权重高", "高波动高成长"],
    },
    # 美国
    "SPX": {
        "name": "标普500", "name_en": "S&P 500", "category": "宽基", "country": "美国",
        "csindex": None, "lg_name": None, "multpl": "s-p-500-pe-ratio", "etf_ticker": "SPY",
        "fund_code": "513500", "fund_name": "标普500ETF",
        "fund_type": "场内ETF", "fund_channel": "券商APP",
        "description": "美国500家最大上市公司，占美股总市值约80%。全球最重要的股票指数，长期年化约10%，是全球资产配置的核心。",
        "highlights": ["全球第一指数", "长期年化10%", "全球配置核心"],
    },
    "NDX": {
        "name": "纳斯达克100", "name_en": "NASDAQ 100", "category": "宽基", "country": "美国",
        "csindex": None, "lg_name": None, "multpl": None, "etf_ticker": "QQQ",
        "fund_code": "513100", "fund_name": "纳斯达克100ETF",
        "fund_type": "场内ETF", "fund_channel": "券商APP",
        "description": "纳斯达克市值最大的100家非金融公司，苹果、微软、英伟达等科技巨头权重高。代表全球科技创新方向，高成长高波动。",
        "highlights": ["科技股集中", "AI/半导体龙头", "高成长高波动"],
    },
    # 日本
    "N225": {
        "name": "日经225", "name_en": "Nikkei 225", "category": "宽基", "country": "日本",
        "csindex": None, "lg_name": None, "etf_ticker": "EWJ",
        "fund_code": "513880", "fund_name": "日经225ETF",
        "fund_type": "场内ETF", "fund_channel": "券商APP",
        "description": "日本225家蓝筹股，丰田、索尼、软银等。日元贬值+日本央行宽松政策推动近年表现，是分散亚洲风险的选择。",
        "highlights": ["日本经济代表", "日元资产配置", "近年表现亮眼"],
    },
    # 德国
    "DAX": {
        "name": "德国DAX", "name_en": "DAX", "category": "宽基", "country": "德国",
        "csindex": None, "lg_name": None, "etf_ticker": "EWG",
        "fund_code": "513030", "fund_name": "德国DAX ETF",
        "fund_type": "场内ETF", "fund_channel": "券商APP",
        "description": "德国40家最大上市公司，西门子、SAP、奔驰等。欧洲最大经济体的代表，工业和制造业权重高。",
        "highlights": ["欧洲经济龙头", "工业制造业强", "欧元资产配置"],
    },
    # 印度
    "SENSEX": {
        "name": "印度SENSEX", "name_en": "BSE SENSEX", "category": "宽基", "country": "印度",
        "csindex": None, "lg_name": None, "etf_ticker": "INDA",
        "fund_code": "164824", "fund_name": "印度基金LOF",
        "fund_type": "场外LOF", "fund_channel": "券商APP/天天基金",
        "description": "印度30家最大上市公司，代表全球增长最快的主要经济体。人口红利+数字化转型驱动，长期增长潜力大。",
        "highlights": ["人口红利", "高增长经济体", "长期潜力大"],
    },
    # 越南
    "VN30": {
        "name": "越南VN30", "name_en": "VN30", "category": "宽基", "country": "越南",
        "csindex": None, "lg_name": None, "etf_ticker": "VNM",
        "fund_code": "", "fund_name": "无直接ETF",
        "fund_type": "无", "fund_channel": "需通过QDII或港股通",
        "description": "越南30家最大上市公司。东南亚新兴制造业中心，类似20年前的中国，高增长但市场不成熟，波动极大。",
        "highlights": ["新兴制造业中心", "高增长高风险", "市场不成熟"],
    },
    # 澳洲
    "ASX200": {
        "name": "澳洲ASX200", "name_en": "S&P/ASX 200", "category": "宽基", "country": "澳大利亚",
        "csindex": None, "lg_name": None, "etf_ticker": "EWA",
        "fund_code": "", "fund_name": "无直接ETF",
        "fund_type": "无", "fund_channel": "需通过QDII",
        "description": "澳大利亚200家最大上市公司，矿业（必和必拓）和金融（联邦银行）权重高。资源型经济体，高股息特征。",
        "highlights": ["资源型经济", "高股息", "矿业金融为主"],
    },
    # 全球
    "MSCI_EM": {
        "name": "MSCI新兴市场", "name_en": "MSCI EM", "category": "宽基", "country": "全球",
        "csindex": None, "lg_name": None, "etf_ticker": "EEM",
        "fund_code": "513050", "fund_name": "中概互联ETF",
        "fund_type": "场内ETF", "fund_channel": "券商APP",
        "description": "覆盖24个新兴市场国家，中国、印度、巴西、台湾等权重高。分散单一国家风险，分享新兴市场增长红利。",
        "highlights": ["全球分散配置", "新兴市场增长", "分散国家风险"],
    },

    # === 红利指数 ===
    "000922": {
        "name": "中证红利", "name_en": "CSI Dividend", "category": "红利", "country": "中国",
        "csindex": "000922", "lg_name": None,
        "fund_code": "515080", "fund_name": "中证红利ETF",
        "fund_type": "场内ETF", "fund_channel": "券商APP",
        "description": "选取100只现金股息率高、分红稳定的股票。银行、煤炭、钢铁等传统行业为主，股息率通常4-6%，适合追求稳定现金流的投资者。",
        "highlights": ["高股息4-6%", "分红稳定", "防御性强"],
    },
    "SPXDIV": {
        "name": "标普高红利", "name_en": "S&P High Dividend", "category": "红利", "country": "美国",
        "csindex": None, "lg_name": None, "yahoo": None, "etf_ticker": None,
        "fund_code": "515180", "fund_name": "标普红利ETF",
        "fund_type": "场内ETF", "fund_channel": "券商APP",
        "description": "标普500中股息率最高的80只股票。公用事业、消费必需品等防御性行业为主，股息率通常3-5%，适合美股收息。",
        "highlights": ["美股高股息", "防御性行业", "美元收息"],
    },
    "000932": {
        "name": "消费红利", "name_en": "Consumer Dividend", "category": "红利", "country": "中国",
        "csindex": "000932", "lg_name": None,
        "fund_code": "501008", "fund_name": "消费红利基金",
        "fund_type": "场外基金", "fund_channel": "天天基金/蚂蚁财富",
        "description": "消费行业（白酒、食品、家电）中股息率最高的30只股票。兼具消费股成长性和高股息防御性，是红利策略的升级版。",
        "highlights": ["消费+红利", "成长与防御兼顾", "白酒家电权重高"],
    },

    # === 补充宽基指数 ===
    "000016": {
        "name": "上证50", "name_en": "SSE 50", "category": "宽基", "country": "中国",
        "csindex": "000016", "lg_name": "上证50", "lg_pe_name": "上证50",
        "fund_code": "510050", "fund_name": "上证50ETF",
        "fund_type": "场内ETF", "fund_channel": "券商APP",
        "description": "上海证券交易所市值最大、流动性最好的50只股票。金融（银行、保险）权重超50%，是大盘蓝筹的代表。",
        "highlights": ["大盘蓝筹代表", "金融权重高", "估值通常较低"],
    },
    "000852": {
        "name": "中证1000", "name_en": "CSI 1000", "category": "宽基", "country": "中国",
        "csindex": "000852", "lg_name": None, "lg_pe_name": "中证1000",
        "fund_code": "512100", "fund_name": "中证1000ETF",
        "fund_type": "场内ETF", "fund_channel": "券商APP",
        "description": "排除沪深300和中证500后，市值排名前1000的小盘股。弹性最大，适合捕捉小盘股行情，但风险也最高。",
        "highlights": ["小盘股代表", "弹性最大", "风险最高"],
    },
    "000688": {
        "name": "科创50", "name_en": "STAR 50", "category": "宽基", "country": "中国",
        "csindex": "000688", "lg_name": None, "lg_pe_name": "科创50",
        "fund_code": "588000", "fund_name": "科创50ETF",
        "fund_type": "场内ETF", "fund_channel": "券商APP",
        "description": "科创板市值最大的50只股票，半导体、生物医药、新能源为主。是中国硬科技的代表，估值波动大，适合长期看好科技的投资者。",
        "highlights": ["硬科技代表", "半导体权重高", "高估值高波动"],
    },
}


# ============================================================
# 数据获取：中证指数（A股）
# ============================================================

def _get_csindex_data(code: str) -> Dict:
    """从中证指数获取当前PE和股息率"""
    try:
        import akshare as ak
        df = ak.stock_zh_index_value_csindex(symbol=code)
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            pe = None
            div = None
            pb = None
            if "市盈率1" in df.columns and latest["市盈率1"]:
                pe = round(float(latest["市盈率1"]), 2)
            if "股息率1" in df.columns and latest["股息率1"]:
                div = round(float(latest["股息率1"]), 2)
            if "市净率1" in df.columns and latest["市净率1"]:
                pb = round(float(latest["市净率1"]), 2)
            return {"pe": pe, "dividend_yield": div, "pb": pb}
    except Exception as e:
        logger.warning(f"获取中证指数{code}数据失败: {e}")
    return {"pe": None, "dividend_yield": None, "pb": None}


def _get_csindex_pe_history(code: str, years: int = 10) -> List[float]:
    """获取中证指数历史PE数据"""
    try:
        import akshare as ak
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=years * 365)).strftime("%Y%m%d")
        df = ak.stock_zh_index_hist_csindex(symbol=code, start_date=start_date, end_date=end_date)
        if df is not None and not df.empty and "滚动市盈率" in df.columns:
            pe_values = df["滚动市盈率"].dropna().tolist()
            return [float(v) for v in pe_values if v and float(v) > 0]
    except Exception as e:
        logger.warning(f"获取中证指数{code}历史PE失败: {e}")
    return []


def _get_csindex_pe_pb_series(code: str, years: int = 10) -> Dict:
    """获取中证指数历史PE/PB时间序列（用于图表展示，月频采样）"""
    try:
        import akshare as ak
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=years * 365)).strftime("%Y%m%d")
        df = ak.stock_zh_index_hist_csindex(symbol=code, start_date=start_date, end_date=end_date)
        if df is not None and not df.empty:
            pe_series = []
            pb_series = []
            for _, row in df.iterrows():
                date_str = str(row.get("日期", row.get("TRADE_DATE", "")))[:10]
                pe_val = row.get("滚动市盈率")
                pb_val = row.get("市净率1") or row.get("市净率")
                if date_str and pe_val and float(pe_val) > 0:
                    pe_series.append({"date": date_str, "value": round(float(pe_val), 2)})
                if date_str and pb_val and float(pb_val) > 0:
                    pb_series.append({"date": date_str, "value": round(float(pb_val), 2)})
            return {"pe_series": pe_series, "pb_series": pb_series}
    except Exception as e:
        logger.warning(f"获取中证指数{code}历史PE/PB序列失败: {e}")
    return {"pe_series": [], "pb_series": []}


def _get_lg_pb_data(name: str) -> Dict:
    """从乐咕乐股获取PB数据及历史PB"""
    try:
        import akshare as ak
        df = ak.stock_index_pb_lg(symbol=name)
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            pb = round(float(latest["市净率"]), 2) if latest["市净率"] else None
            pb_history = [float(v) for v in df["市净率"].dropna().tolist() if v and float(v) > 0]
            pb_percentile = _calc_percentile(pb, pb_history) if pb and pb_history else None
            return {"pb": pb, "pb_percentile": pb_percentile}
    except Exception as e:
        logger.warning(f"获取{name}PB数据失败: {e}")
    return {"pb": None, "pb_percentile": None}


def _get_lg_pe_data(name: str) -> Dict:
    """从乐咕乐股获取PE数据及历史PE（比csindex更完整）"""
    try:
        import akshare as ak
        df = ak.stock_index_pe_lg(symbol=name)
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            pe = round(float(latest["滚动市盈率"]), 2) if "滚动市盈率" in df.columns and latest["滚动市盈率"] else None
            pe_history = [float(v) for v in df["滚动市盈率"].dropna().tolist() if v and float(v) > 0]
            pe_percentile = _calc_percentile(pe, pe_history) if pe and pe_history else None
            return {"pe": pe, "pe_percentile": pe_percentile}
    except Exception as e:
        logger.warning(f"获取{name}PE数据失败: {e}")
    return {"pe": None, "pe_percentile": None}


def _get_hsi_pe() -> Dict:
    """获取恒生指数PE/PB（从akshare乐咕乐股接口）"""
    try:
        import akshare as ak
        # 恒生指数PE
        df = ak.stock_hk_gxl_lg()
        if df is not None and not df.empty:
            div = round(float(df.iloc[-1]["股息率"]), 2) if "股息率" in df.columns else None
            return {"dividend_yield": div}
    except Exception as e:
        logger.warning(f"获取恒生数据失败: {e}")
    return {"dividend_yield": None}


# ============================================================
# 数据获取：multpl.com（标普500）
# ============================================================

def _fetch_multpl_text(url: str) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.text
    except requests.exceptions.RequestException as e:
        logger.warning(f"_fetch_multpl_text failed for {url}: {e}")
        raise


def _get_sp500_pe_with_percentile() -> Dict:
    """获取标普500 PE及历史百分位"""
    try:
        from bs4 import BeautifulSoup
        text = BeautifulSoup(_fetch_multpl_text("https://www.multpl.com/s-p-500-pe-ratio"), 'html.parser').get_text()
        current_match = re.search(r'Current.*?(\d+\.\d+)', text, re.DOTALL)
        current_pe = _validate_range(float(current_match.group(1)) if current_match else None, 1, 200)

        text_hist = BeautifulSoup(_fetch_multpl_text("https://www.multpl.com/s-p-500-pe-ratio/table/by-month"), 'html.parser').get_text()
        matches = re.findall(r'(\w+ \d+, \d+)\s+(\d+\.\d+)', text_hist)
        if matches:
            pe_values = [float(pe) for _, pe in matches if 1 <= float(pe) <= 200]
            percentile = _calc_percentile(current_pe, pe_values) if current_pe else None
            return {"pe": current_pe, "percentile": percentile}
        return {"pe": current_pe, "percentile": None}
    except Exception as e:
        logger.warning(f"获取标普500 PE失败: {e}")
    return {"pe": None, "percentile": None}


def _get_sp500_pb_with_percentile() -> Dict:
    try:
        from bs4 import BeautifulSoup
        text = BeautifulSoup(_fetch_multpl_text("https://www.multpl.com/s-p-500-price-to-book"), 'html.parser').get_text()
        current_match = re.search(r'Current.*?(\d+\.\d+)', text, re.DOTALL)
        current_pb = _validate_range(float(current_match.group(1)) if current_match else None, 0.1, 50)

        text_hist = BeautifulSoup(_fetch_multpl_text("https://www.multpl.com/s-p-500-price-to-book/table/by-year"), 'html.parser').get_text()
        matches = re.findall(r'(\w+ \d+, \d+)\s+(\d+\.\d+)', text_hist)
        if matches:
            pb_values = [float(pb) for _, pb in matches if 0.1 <= float(pb) <= 50]
            percentile = _calc_percentile(current_pb, pb_values) if current_pb else None
            return {"pb": current_pb, "percentile": percentile}
        return {"pb": current_pb, "percentile": None}
    except Exception as e:
        logger.warning(f"获取标普500 PB失败: {e}")
    return {"pb": None, "percentile": None}


def _get_sp500_dividend_with_percentile() -> Dict:
    try:
        from bs4 import BeautifulSoup
        text = BeautifulSoup(_fetch_multpl_text("https://www.multpl.com/s-p-500-dividend-yield"), 'html.parser').get_text()
        current_match = re.search(r'Current.*?(\d+\.\d+)', text, re.DOTALL)
        current_yield = _validate_range(float(current_match.group(1)) if current_match else None, 0.1, 20)

        text_hist = BeautifulSoup(_fetch_multpl_text("https://www.multpl.com/s-p-500-dividend-yield/table/by-month"), 'html.parser').get_text()
        matches = re.findall(r'(\w+ \d+, \d+)\s+(\d+\.\d+)', text_hist)
        if matches:
            yield_values = [float(y) for _, y in matches if 0.1 <= float(y) <= 20]
            percentile = _calc_percentile(current_yield, yield_values) if current_yield else None
            return {"dividend_yield": current_yield, "percentile": percentile}
        return {"dividend_yield": current_yield, "percentile": None}
    except Exception as e:
        logger.warning(f"获取标普500 股息率失败: {e}")
    return {"dividend_yield": None, "percentile": None}


# ============================================================
# 数据获取：stockanalysis.com（纳斯达克100）
# ============================================================

# NDX 只保留 PE（stockanalysis.com 实时数据，可靠）
# PB、百分位、股息率等数据源不可靠，不提供：
#   - PB: 无权威自动数据源（yfinance ETF PB≈2.0 不准确，gurufocus 403 禁止抓取）
#   - 百分位: 无真实月度历史数据，估算参考值不可靠
#   - 股息率: ETF级数据，非指数级


def _get_ndx_pe() -> Optional[float]:
    """获取纳斯达克100 PE（仅PE，其他指标不可靠不提供）

    数据源：stockanalysis.com 爬取（实时数据）
    PB/百分位/股息率等因数据源不可靠，已移除：
      - PB: 无权威自动数据源（yfinance ETF priceToBook≈2.0 不准确）
      - 百分位: 无真实月度历史数据，估算参考值不可靠
      - 股息率: ETF级数据，非指数级
    """
    pe = None

    # 优先从 stockanalysis.com 获取
    try:
        url = "https://stockanalysis.com/etf/qqq/"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        text = resp.text

        # 从页面提取 PE Ratio
        pe_match = re.search(r'PE Ratio\s*([\d.]+)', text)
        if pe_match:
            pe_val = float(pe_match.group(1))
            if 1 < pe_val < 1000:
                pe = round(pe_val, 2)
                logger.info(f"从stockanalysis获取QQQ PE: {pe}")
    except Exception as e:
        logger.warning(f"从stockanalysis获取QQQ PE失败: {e}")

    # 备用：yfinance（仅取PE，PB不准确故不取）
    if pe is None:
        etf_data = _get_etf_pe_pb("QQQ")
        if etf_data["pe"]:
            pe = etf_data["pe"]
            logger.info(f"从yfinance获取QQQ PE(备用): {pe}")

    return pe


# ============================================================
# 数据获取：腾讯财经（A股/港股指数K线）
# ============================================================

def _fetch_index_klines_tencent(symbol: str, days: int = 1000) -> List[Dict]:
    """从腾讯财经获取指数K线数据（A股/港股，最多1000天）"""
    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=min(days, 1000) + 30)).strftime("%Y-%m-%d")
        url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        params = {"param": f"{symbol},day,{start_date},{end_date},{min(days, 1000) + 30},qfq"}
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = r.json()
        if "data" in data and isinstance(data["data"], dict) and symbol in data["data"]:
            klines = data["data"][symbol]
            rows = klines.get("qfqday") or klines.get("day") or []
            records = []
            for row in rows:
                if len(row) >= 5:
                    records.append({"date": str(row[0]), "close": float(row[2])})
            return records[-days:]
    except Exception as e:
        logger.warning(f"获取{symbol}K线失败: {e}")
    return []


def _fetch_etf_klines_sina(fund_code: str, days: int = 3650) -> List[Dict]:
    """从新浪财经获取ETF K线数据（用于计算国际指数历史收益）"""
    try:
        # A股ETF用新浪A股接口
        prefix = "sh" if fund_code.startswith(("5", "6")) else "sz"
        url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
        params = {"symbol": f"{prefix}{fund_code}", "scale": "240", "ma": "no", "datalen": days}
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        rows = r.json()
        return [{"date": row["day"], "close": float(row["close"])} for row in rows]
    except Exception as e:
        logger.warning(f"获取ETF {fund_code} K线失败: {e}")
    return []


def _fetch_index_klines_sina(symbol: str, days: int = 3650) -> List[Dict]:
    """从新浪获取A股指数K线数据（支持10年历史，symbol格式：sh000300/sz399006）"""
    try:
        url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
        params = {"symbol": symbol, "scale": "240", "ma": "no", "datalen": days}
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        rows = r.json()
        return [{"date": row["day"], "close": float(row["close"])} for row in rows if float(row["close"]) > 0]
    except Exception as e:
        logger.warning(f"获取指数{symbol} K线失败: {e}")
    return []


# ============================================================
# 数据获取：富途OpenAPI（全球ETF PE/PB/K线）
# ============================================================

def _get_futu_snapshot(code: str) -> Dict:
    """通过富途OpenAPI获取ETF/股票快照（PE/PB/股息率）"""
    try:
        from futu import OpenQuoteContext, RET_OK
        ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        ret, data = ctx.get_market_snapshot([code])
        ctx.close()

        if ret == RET_OK and len(data) > 0:
            row = data.iloc[0]
            pe = row.get('pe_ttm_ratio')
            pb = row.get('pb_ratio')
            # ETF用trust_dividend_yield，个股用dividend_ratio_ttm
            div = row.get('trust_dividend_yield') or row.get('dividend_ratio_ttm')

            return {
                "pe": round(float(pe), 2) if pe and not (pe != pe) and 1 < pe < 1000 else None,  # pe != pe 检查NaN
                "pb": round(float(pb), 2) if pb and not (pb != pb) and 0.01 < pb < 100 else None,
                "dividend_yield": round(float(div), 2) if div and not (div != div) and 0.01 < div < 30 else None,
            }
    except Exception as e:
        logger.warning(f"获取富途{code}快照失败: {e}")
    return {"pe": None, "pb": None, "dividend_yield": None}


def _get_futu_klines(code: str, years: int = 10) -> List[Dict]:
    """通过富途OpenAPI获取历史K线"""
    try:
        from futu import OpenQuoteContext, RET_OK, KLType
        from datetime import datetime, timedelta

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=years * 365)).strftime("%Y-%m-%d")

        ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        ret, data, _ = ctx.request_history_kline(code, start=start_date, end=end_date,
                                                  ktype=KLType.K_DAY, max_count=5000)
        ctx.close()

        if ret == RET_OK and len(data) > 0:
            return [{"date": row["time_key"][:10], "close": float(row["close"])}
                    for _, row in data.iterrows() if row["close"] > 0]
    except Exception as e:
        logger.warning(f"获取富途{code}K线失败: {e}")
    return []


# ============================================================
# 富途代码映射
# ============================================================

FUTU_CODES = {
    "HSI": {"snapshot": "HK.02800", "kline": "HK.02800"},       # 盈富基金
    "HSTECH": {"snapshot": "HK.03067", "kline": "HK.03067"},    # 恒生科技ETF
    "399006": {"snapshot": "SZ.159915", "kline": "SZ.159915"},  # 创业板ETF
    "NDX": {"snapshot": "US.QQQ", "kline": "US.QQQ"},           # 纳指100
    "SPXDIV": {"snapshot": "US.SPYD", "kline": "US.SPYD"},      # 标普高红利
    "N225": {"snapshot": "US.EWJ", "kline": "US.EWJ"},          # 日本ETF
    "DAX": {"snapshot": "US.EWG", "kline": "US.EWG"},           # 德国ETF
    "SENSEX": {"snapshot": "US.INDA", "kline": "US.INDA"},      # 印度ETF
    "VN30": {"snapshot": "US.VNM", "kline": "US.VNM"},          # 越南ETF
    "ASX200": {"snapshot": "US.EWA", "kline": "US.EWA"},        # 澳洲ETF
    "MSCI_EM": {"snapshot": "US.EEM", "kline": "US.EEM"},       # MSCI新兴市场
}


# ============================================================
# 数据获取：yfinance（备用方案）
# ============================================================

def _get_etf_pe_pb(ticker_symbol: str) -> Dict:
    """通过yfinance获取ETF的PE/PB/股息率"""
    try:
        import yfinance as yf
        import os
        # 设置代理
        proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
        if proxy:
            os.environ['HTTP_PROXY'] = proxy
            os.environ['HTTPS_PROXY'] = proxy

        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info

        pe = info.get('trailingPE') or info.get('forwardPE')
        pb = info.get('priceToBook')

        # 优先使用trailingAnnualDividendYield（更可靠，是小数形式如0.0275表示2.75%）
        div_yield_raw = info.get('trailingAnnualDividendYield')
        if div_yield_raw and div_yield_raw > 0:
            div_yield = round(div_yield_raw * 100, 2)
        else:
            # fallback: dividendYield（已经是百分比形式如0.38表示0.38%）
            div_yield = info.get('dividendYield')
            if div_yield and div_yield > 10:
                div_yield = div_yield / 100

        return {
            "pe": round(pe, 2) if pe and 1 < pe < 1000 else None,
            "pb": round(pb, 2) if pb and 0.01 < pb < 100 else None,
            "dividend_yield": round(div_yield, 2) if div_yield and 0.01 < div_yield < 30 else None,
        }
    except Exception as e:
        logger.warning(f"获取ETF {ticker_symbol}估值失败: {e}")
    return {"pe": None, "pb": None, "dividend_yield": None}


# ============================================================
# 指数K线符号映射
# ============================================================

INDEX_KLINE_SYMBOLS = {
    "000510": {"tencent": "sh000510"},
    "000300": {"tencent": "sh000300"},
    "000905": {"tencent": "sh000905"},
    "399006": {"tencent": "sz399006"},
    "HSI": {"tencent": "hkHSI"},
    "HSTECH": {"tencent": "hkHSTECH"},
    "000922": {"tencent": "sh000922"},
    "000932": {"tencent": "sh000932"},
    # 国际指数用对应ETF的K线
    "SPX": {"etf": "513500"},
    "NDX": {"etf": "513100"},
    "N225": {"etf": "513880"},
    "DAX": {"etf": "513030"},
    "SENSEX": {"etf": "164824"},
    "VN30": {},
    "ASX200": {},
    "MSCI_EM": {"etf": "513050"},
    "SPXDIV": {"etf": "515180"},
    "000016": {"tencent": "sh000016"},
    "000852": {"tencent": "sh000852"},
    "000688": {"tencent": "sh000688"},
}


# ============================================================
# 历史收益率计算
# ============================================================

def calc_index_returns(closes: List[float], dates: List[str]) -> Dict:
    """根据收盘价序列计算各时间段收益率"""
    if not closes or len(closes) < 2:
        return {"return_1y": None, "return_3y": None, "return_5y": None, "return_10y": None,
                "cagr": None, "max_drawdown": None}

    current = closes[-1]
    result = {}

    # 各时间段收益率
    for label, trading_days in [("return_1y", 252), ("return_3y", 756), ("return_5y", 1260), ("return_10y", 2520)]:
        if len(closes) >= trading_days:
            past_price = closes[-trading_days]
            if past_price > 0:
                result[label] = round((current / past_price - 1) * 100, 2)
            else:
                result[label] = None
        else:
            result[label] = None

    # 年化收益率（CAGR）
    years = len(closes) / 252
    if years > 1 and closes[0] > 0:
        result["cagr"] = round((pow(current / closes[0], 1 / years) - 1) * 100, 2)
    else:
        result["cagr"] = None

    # 最大回撤
    peak = closes[0]
    max_dd = 0
    for price in closes:
        if price > peak:
            peak = price
        dd = (peak - price) / peak * 100
        if dd > max_dd:
            max_dd = dd
    result["max_drawdown"] = round(max_dd, 2)

    return result


# ============================================================
# 基金信息获取
# ============================================================

def _get_fund_info(fund_code: str) -> Dict:
    """获取基金详细信息"""
    if not fund_code:
        return {"fee": None, "name": None, "purchase_fee": None}

    cache_key = f"fund_info_{fund_code}"
    cached = _get_cached(cache_key, _CACHE_TTL_FUND)
    if cached:
        return cached

    result = {"fee": None, "name": None, "purchase_fee": None}
    try:
        resp = requests.get(f"https://fundf10.eastmoney.com/jbgk_{fund_code}.html", headers=HEADERS, timeout=10)
        resp.encoding = "utf-8"
        text = resp.text

        # 管理费率
        fee_match = re.search(r"管理费率.*?(\d+\.\d+)%", text)
        if fee_match:
            result["fee"] = f"{fee_match.group(1)}%"

        # 基金名称
        name_match = re.search(r'<title>(.*?)(?:基金基本概况|_|<)', text)
        if name_match:
            result["name"] = name_match.group(1).strip()

        # 申购费率
        purchase_match = re.search(r"申购费率.*?(\d+\.\d+)%", text)
        if purchase_match:
            result["purchase_fee"] = f"{purchase_match.group(1)}%"
    except Exception as e:
        logger.warning(f"获取基金{fund_code}信息失败: {e}")

    _set_cached(cache_key, result)
    return result


# ============================================================
# 主数据接口
# ============================================================

def _calc_percentile(current: float, historical: List[float]) -> Optional[float]:
    if not historical or current is None:
        return None
    count = sum(1 for v in historical if v <= current)
    return round(count / len(historical) * 100, 1)


def _validate_range(value: Optional[float], min_val: float, max_val: float) -> Optional[float]:
    if value is None:
        return None
    if min_val <= value <= max_val:
        return value
    return None


# 10年期国债收益率近似值（用于风险溢价计算）
_BOND_YIELDS = {
    "中国": 2.3, "中国香港": 4.0, "美国": 4.3, "日本": 1.0,
    "德国": 2.5, "印度": 7.0, "越南": 3.0, "澳大利亚": 4.2, "全球": 4.0,
}


def _calc_risk_premium(pe: Optional[float], country: str) -> Optional[float]:
    """计算股权风险溢价 = 盈利收益率 - 10年期国债收益率"""
    if not pe or pe <= 0:
        return None
    earnings_yield = 1 / pe * 100
    bond_yield = _BOND_YIELDS.get(country, 3.5)
    return round(earnings_yield - bond_yield, 2)


def _calc_investment_signal(pe_p: Optional[float], pb_p: Optional[float],
                             div_yield: Optional[float], risk_premium: Optional[float]) -> Dict:
    """综合投资信号：加权评分（分越低越低估）

    PE/PB百分位：直接使用百分位值（越低越便宜）
    股息率：转换为百分位等价分（股息率越高越便宜，分数越低）
        - 股息率5% -> 分数0，股息率1% -> 分数80，股息率0% -> 分数100
    风险溢价：转换为百分位等价分（溢价越高越有吸引力，分数越低）
        - 溢价5% -> 分数10，溢价0% -> 分数50，溢价-3% -> 分数74
    """
    scores, weights = [], []
    if pe_p is not None:
        scores.append(pe_p); weights.append(0.35)
    if pb_p is not None:
        scores.append(pb_p); weights.append(0.35)
    if div_yield is not None and div_yield > 0:
        # 股息率越高 -> 分数越低（越低估）：5%->0, 2%->60, 1%->80
        div_score = max(0, min(100, 100 - div_yield * 20))
        scores.append(div_score); weights.append(0.15)
    if risk_premium is not None:
        # 风险溢价越高 -> 分数越低（越有吸引力）：5%->10, 0%->50, -3%->74
        rp_score = max(0, min(100, 50 - risk_premium * 8))
        scores.append(rp_score); weights.append(0.15)

    if not scores:
        return {"score": None, "signal": "数据不足", "color": "var(--text-muted)"}

    composite = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
    if composite < 20:
        return {"score": round(composite, 1), "signal": "极度低估", "color": "#238636"}
    elif composite < 35:
        return {"score": round(composite, 1), "signal": "低估", "color": "#3fb950"}
    elif composite <= 55:
        return {"score": round(composite, 1), "signal": "合理", "color": "var(--text-secondary)"}
    elif composite <= 70:
        return {"score": round(composite, 1), "signal": "偏高", "color": "#d29922"}
    else:
        return {"score": round(composite, 1), "signal": "高估", "color": "#f85149"}


def get_all_indices_data() -> Dict:
    """获取全部指数估值数据（带缓存）"""
    cache_key = "index_valuation_all"
    cached = _get_cached(cache_key, _CACHE_TTL_VALUATION)
    if cached:
        return cached

    # 预获取标普500数据（只请求一次）
    sp500_pe = _get_sp500_pe_with_percentile()
    sp500_pb = _get_sp500_pb_with_percentile()
    sp500_div = _get_sp500_dividend_with_percentile()

    results = []
    for code, config in INDEX_CONFIG.items():
        item = {
            "code": code,
            "name": config["name"],
            "name_en": config.get("name_en", ""),
            "category": config["category"],
            "country": config.get("country", ""),
            "description": config.get("description", ""),
            "highlights": config.get("highlights", []),
            "pe": None, "pe_percentile": None,
            "pb": None, "pb_percentile": None,
            "roe": None,
            "dividend_yield": None, "dividend_percentile": None,
            "fund_code": config.get("fund_code", ""),
            "fund_name": config.get("fund_name", ""),
            "fund_type": config.get("fund_type", ""),
            "fund_channel": config.get("fund_channel", ""),
            "fund_fee": None, "fund_purchase_fee": None,
            "fund_holdings_url": f"https://fundf10.eastmoney.com/ccmx_{config.get('fund_code', '')}.html",
            "return_1y": None, "return_3y": None, "return_5y": None,
            "cagr": None, "max_drawdown": None,
            "risk_premium": None,
            "investment_signal": {"score": None, "signal": "数据不足", "color": "var(--text-muted)"},
        }

        # A股指数：中证指数 + 乐咕乐股补充
        if config.get("csindex"):
            cs_data = _get_csindex_data(config["csindex"])
            item["pe"] = cs_data["pe"]
            item["dividend_yield"] = cs_data["dividend_yield"]
            if cs_data.get("pb"):
                item["pb"] = cs_data["pb"]

            pe_history = _get_csindex_pe_history(config["csindex"])
            if pe_history and cs_data["pe"]:
                item["pe_percentile"] = _calc_percentile(cs_data["pe"], pe_history)

            # 乐咕乐股PE补充（csindex无数据时）
            if item["pe"] is None and config.get("lg_pe_name"):
                lg_pe = _get_lg_pe_data(config["lg_pe_name"])
                if lg_pe["pe"]:
                    item["pe"] = lg_pe["pe"]
                    item["pe_percentile"] = lg_pe["pe_percentile"]

            # 乐咕乐股PB补充
            if config.get("lg_name"):
                pb_data = _get_lg_pb_data(config["lg_name"])
                if pb_data["pb"]:
                    item["pb"] = pb_data["pb"]
                    item["pb_percentile"] = pb_data["pb_percentile"]

            if item["pb"] and item["pe"] and item["pe"] > 0:
                item["roe"] = round(item["pb"] / item["pe"] * 100, 2)

        # 标普500
        elif code == "SPX":
            item["pe"] = sp500_pe["pe"]
            item["pe_percentile"] = sp500_pe["percentile"]
            item["pb"] = sp500_pb["pb"]
            item["pb_percentile"] = sp500_pb["percentile"]
            item["dividend_yield"] = sp500_div["dividend_yield"]
            item["dividend_percentile"] = sp500_div["percentile"]
            if item["pb"] and item["pe"] and item["pe"] > 0:
                item["roe"] = round(item["pb"] / item["pe"] * 100, 2)

        # 纳斯达克100：仅保留PE（PB/百分位/股息率数据源不可靠）
        elif code == "NDX":
            item["pe"] = _get_ndx_pe()
            # PB、百分位、股息率、ROE 均不设置（保持 None）

        # 恒生指数/恒生科技：富途API优先
        elif code in ("HSI", "HSTECH"):
            futu_code = FUTU_CODES.get(code, {}).get("snapshot")
            if futu_code:
                futu_data = _get_futu_snapshot(futu_code)
                item["pe"] = futu_data["pe"]
                item["pb"] = futu_data["pb"]
                item["dividend_yield"] = futu_data.get("dividend_yield")
            else:
                hsi_data = _get_hsi_pe()
                item["dividend_yield"] = hsi_data.get("dividend_yield")
            if item["pb"] and item["pe"] and item["pe"] > 0:
                item["roe"] = round(item["pb"] / item["pe"] * 100, 2)

        # 创业板指：富途API
        elif code == "399006":
            futu_code = FUTU_CODES.get(code, {}).get("snapshot")
            if futu_code:
                futu_data = _get_futu_snapshot(futu_code)
                item["pe"] = futu_data["pe"]
                item["pb"] = futu_data["pb"]
                item["dividend_yield"] = futu_data.get("dividend_yield")
                if item["pb"] and item["pe"] and item["pe"] > 0:
                    item["roe"] = round(item["pb"] / item["pe"] * 100, 2)

        # 其他全球指数：富途API优先，yfinance备用
        elif config.get("etf_ticker") or FUTU_CODES.get(code):
            # 优先用富途
            futu_code = FUTU_CODES.get(code, {}).get("snapshot")
            if futu_code:
                futu_data = _get_futu_snapshot(futu_code)
                item["pe"] = futu_data["pe"]
                item["pb"] = futu_data["pb"]
                item["dividend_yield"] = futu_data.get("dividend_yield")
            # 备用yfinance
            yf_ticker = config.get("etf_ticker") or config.get("yahoo")
            if item["pe"] is None and yf_ticker:
                etf_data = _get_etf_pe_pb(yf_ticker)
                item["pe"] = etf_data["pe"]
                item["pb"] = etf_data["pb"]
                if not item["dividend_yield"]:
                    item["dividend_yield"] = etf_data.get("dividend_yield")
            if item["pb"] and item["pe"] and item["pe"] > 0:
                item["roe"] = round(item["pb"] / item["pe"] * 100, 2)

        # 计算历史收益率（优先富途K线，备用新浪指数10年/腾讯）
        kline_cfg = INDEX_KLINE_SYMBOLS.get(code, {})
        futu_kline_code = FUTU_CODES.get(code, {}).get("kline")
        klines = []

        if futu_kline_code:
            klines = _get_futu_klines(futu_kline_code, 10)
        # A股指数优先用新浪获取10年数据（腾讯限制1000天）
        if not klines and kline_cfg.get("tencent"):
            sina_symbol = kline_cfg["tencent"]  # sh000300 / sz399006 格式
            klines = _fetch_index_klines_sina(sina_symbol, 3650)
        if not klines and kline_cfg.get("tencent"):
            klines = _fetch_index_klines_tencent(kline_cfg["tencent"], 1000)
        if not klines and kline_cfg.get("etf"):
            klines = _fetch_etf_klines_sina(kline_cfg["etf"], 3000)

        if klines:
            closes = [k["close"] for k in klines if k["close"] > 0]
            if closes:
                returns = calc_index_returns(closes, [])
                item.update(returns)

        # 获取基金信息
        fund_code = config.get("fund_code", "")
        if fund_code:
            fund_info = _get_fund_info(fund_code)
            item["fund_fee"] = fund_info["fee"]
            if fund_info.get("name"):
                item["fund_name"] = fund_info["name"]
            item["fund_purchase_fee"] = fund_info.get("purchase_fee")

        # 计算风险溢价和综合投资信号
        item["risk_premium"] = _calc_risk_premium(item["pe"], config.get("country", ""))
        item["investment_signal"] = _calc_investment_signal(
            item["pe_percentile"], item["pb_percentile"],
            item["dividend_yield"], item["risk_premium"]
        )

        results.append(item)

    # 按国家/地区排序
    country_order = {"中国": 0, "中国香港": 1, "美国": 2, "日本": 3, "德国": 4, "印度": 5, "越南": 6, "澳大利亚": 7, "全球": 8}
    results.sort(key=lambda x: (0 if x["category"] == "宽基" else 1, country_order.get(x["country"], 9), x["name"]))

    result = {
        "indices": results,
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(results),
        "data_sources": ["中证指数", "multpl.com", "yfinance", "富途OpenAPI", "乐咕乐股", "东方财富"],
    }

    _set_cached(cache_key, result)
    return result


def get_index_history(code: str) -> Dict:
    """获取单个指数的PE/PB历史时间序列（用于估值走势图）"""
    cache_key = f"index_history_{code}"
    cached = _get_cached(cache_key, _CACHE_TTL_RETURN)
    if cached:
        return cached

    config = INDEX_CONFIG.get(code)
    if not config:
        return {"error": f"未知指数代码: {code}"}

    pe_series, pb_series = [], []

    # A股指数：从中证指数获取历史PE/PB
    if config.get("csindex"):
        series_data = _get_csindex_pe_pb_series(config["csindex"], years=10)
        pe_series = series_data.get("pe_series", [])
        pb_series = series_data.get("pb_series", [])

    # 标普500：从multpl.com获取历史
    elif code == "SPX":
        try:
            from bs4 import BeautifulSoup
            text_hist = BeautifulSoup(
                _fetch_multpl_text("https://www.multpl.com/s-p-500-pe-ratio/table/by-month"),
                'html.parser'
            ).get_text()
            for date_str, val in re.findall(r'(\w+ \d+, \d+)\s+(\d+\.\d+)', text_hist):
                try:
                    dt = datetime.strptime(date_str, "%B %d, %Y")
                    pe_series.append({"date": dt.strftime("%Y-%m-%d"), "value": round(float(val), 2)})
                except ValueError:
                    continue
            pe_series.sort(key=lambda x: x["date"])

            text_pb = BeautifulSoup(
                _fetch_multpl_text("https://www.multpl.com/s-p-500-price-to-book/table/by-year"),
                'html.parser'
            ).get_text()
            for date_str, val in re.findall(r'(\w+ \d+, \d+)\s+(\d+\.\d+)', text_pb):
                try:
                    dt = datetime.strptime(date_str, "%B %d, %Y")
                    pb_series.append({"date": dt.strftime("%Y-%m-%d"), "value": round(float(val), 2)})
                except ValueError:
                    continue
            pb_series.sort(key=lambda x: x["date"])
        except Exception as e:
            logger.warning(f"获取标普500历史PE/PB失败: {e}")

    # 纳斯达克100：无可靠历史数据源，不提供历史序列
    elif code == "NDX":
        pass  # PE/PB历史数据不可靠，返回空序列

    result = {
        "code": code,
        "name": config["name"],
        "pe_series": pe_series,
        "pb_series": pb_series,
        "pe_stats": {
            "current": pe_series[-1]["value"] if pe_series else None,
            "min": min(d["value"] for d in pe_series) if pe_series else None,
            "max": max(d["value"] for d in pe_series) if pe_series else None,
            "avg": round(sum(d["value"] for d in pe_series) / len(pe_series), 2) if pe_series else None,
        },
        "pb_stats": {
            "current": pb_series[-1]["value"] if pb_series else None,
            "min": min(d["value"] for d in pb_series) if pb_series else None,
            "max": max(d["value"] for d in pb_series) if pb_series else None,
            "avg": round(sum(d["value"] for d in pb_series) / len(pb_series), 2) if pb_series else None,
        },
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    _set_cached(cache_key, result)
    return result
