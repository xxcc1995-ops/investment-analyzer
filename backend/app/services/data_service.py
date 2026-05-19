"""数据服务 - 使用新浪财经和东方财富获取A股数据"""

import requests
import json
from typing import Optional
from datetime import datetime


class DataService:
    """金融数据服务"""

    @staticmethod
    def get_stock_basic(stock_code: str) -> dict:
        """获取股票基本信息和实时行情"""
        try:
            # 判断市场
            if stock_code.startswith('6'):
                symbol = f"sh{stock_code}"
                market = "1"
            else:
                symbol = f"sz{stock_code}"
                market = "0"

            # 新浪实时行情
            url = f"https://hq.sinajs.cn/list={symbol}"
            headers = {"Referer": "https://finance.sina.com.cn"}
            r = requests.get(url, headers=headers, timeout=10)
            r.encoding = 'gbk'

            # 解析数据
            data = r.text.split('"')[1].split(',')
            if len(data) < 32:
                return {"code": stock_code, "error": "未找到行情数据"}

            name = data[0]
            open_price = float(data[1]) if data[1] else 0
            pre_close = float(data[2]) if data[2] else 0
            price = float(data[3]) if data[3] else 0
            high = float(data[4]) if data[4] else 0
            low = float(data[5]) if data[5] else 0
            volume = int(float(data[8])) if data[8] else 0
            amount = float(data[9]) if data[9] else 0
            trade_date = data[30]  # 交易日期
            trade_time = data[31]  # 交易时间

            change_pct = ((price - pre_close) / pre_close * 100) if pre_close > 0 else 0

            # 获取总股本和PE/PB
            total_shares, pe, pb = DataService._get_valuation_data(stock_code, market, price)

            market_cap = price * total_shares / 1e8  # 亿元

            return {
                "code": stock_code,
                "name": name,
                "price": price,
                "open": open_price,
                "high": high,
                "low": low,
                "pre_close": pre_close,
                "change_pct": round(change_pct, 2),
                "volume": volume,
                "amount": amount,
                "pe": pe,
                "pb": pb,
                "market_cap": round(market_cap, 2),
                "trade_date": trade_date,
                "trade_time": trade_time,
                "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception as e:
            return {"code": stock_code, "error": str(e)}

    @staticmethod
    def _get_valuation_data(stock_code: str, market: str, price: float) -> tuple:
        """获取估值数据：总股本、PE、PB"""
        try:
            url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
            params = {
                "reportName": "RPT_F10_FINANCE_MAINFINADATA",
                "columns": "TOTAL_SHARE,EPSJB,BPS",
                "filter": f"(SECURITY_CODE=\"{stock_code}\")",
                "pageNumber": "1",
                "pageSize": "1",
                "sortTypes": "-1",
                "sortColumns": "REPORT_DATE",
                "source": "HSF10",
                "client": "PC"
            }
            r = requests.get(url, params=params, timeout=15)
            data = r.json()

            if data.get("result") and data["result"].get("data"):
                item = data["result"]["data"][0]
                total_share = item.get("TOTAL_SHARE", 0) / 1e8  # 转换为亿股
                eps = item.get("EPSJB", 0)
                bps = item.get("BPS", 0)

                pe = round(price / eps, 2) if eps and eps > 0 else None
                pb = round(price / bps, 2) if bps and bps > 0 else None

                return total_share, pe, pb

            return 0, None, None
        except:
            return 0, None, None

    @staticmethod
    def get_financial_indicators(stock_code: str) -> dict:
        """获取财务指标 - 从东方财富API实时获取"""
        try:
            url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
            params = {
                "reportName": "RPT_F10_FINANCE_MAINFINADATA",
                "columns": "REPORT_DATE,REPORT_DATE_NAME,EPSJB,BPS,ROEJQ,TOTALOPERATEREVE,PARENTNETPROFIT,TOTALOPERATEREVETZ,PARENTNETPROFITTZ,XSMLL,XSJLL,ZCFZL",
                "filter": f"(SECURITY_CODE=\"{stock_code}\")",
                "pageNumber": "1",
                "pageSize": "8",
                "sortTypes": "-1",
                "sortColumns": "REPORT_DATE",
                "source": "HSF10",
                "client": "PC"
            }

            r = requests.get(url, params=params, timeout=15)
            data = r.json()

            if not data.get("result") or not data["result"].get("data"):
                return {"code": stock_code, "error": "未找到财务数据", "reports": []}

            reports = []
            latest_date = None

            for item in data["result"]["data"]:
                report_date = item.get("REPORT_DATE", "")[:10]
                if latest_date is None:
                    latest_date = report_date

                report = {
                    "date": report_date,
                    "report_name": item.get("REPORT_DATE_NAME", ""),
                    "eps": _safe_float(item.get("EPSJB")),
                    "bps": _safe_float(item.get("BPS")),
                    "roe": _safe_float(item.get("ROEJQ")),
                    "revenue": _safe_float(item.get("TOTALOPERATEREVE")),
                    "net_profit": _safe_float(item.get("PARENTNETPROFIT")),
                    "revenue_growth": _safe_float(item.get("TOTALOPERATEREVETZ")),
                    "profit_growth": _safe_float(item.get("PARENTNETPROFITTZ")),
                    "gross_margin": _safe_float(item.get("XSMLL")),
                    "net_margin": _safe_float(item.get("XSJLL")),
                    "debt_ratio": _safe_float(item.get("ZCFZL")),
                }
                reports.append(report)

            return {
                "code": stock_code,
                "reports": reports,
                "latest_report_date": latest_date,
                "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception as e:
            return {"code": stock_code, "error": str(e), "reports": []}

    @staticmethod
    def search_stock(keyword: str) -> list:
        """搜索股票"""
        try:
            # 新浪搜索API
            url = f"https://suggest3.sinajs.cn/suggest/type=11,12&key={keyword}"
            r = requests.get(url, timeout=10)
            r.encoding = 'utf-8'

            # 解析结果
            results = []
            items = r.text.split('"')[1].split(';')
            for item in items:
                parts = item.split(',')
                if len(parts) >= 4:
                    code = parts[2]
                    name = parts[1]
                    if code.startswith('6') or code.startswith('0') or code.startswith('3'):
                        results.append({"code": code, "name": name})
                        if len(results) >= 10:
                            break

            return results
        except Exception as e:
            return []


def _safe_float(val) -> Optional[float]:
    """安全转换为浮点数"""
    if val is None:
        return None
    try:
        return round(float(val), 4)
    except (ValueError, TypeError):
        return None
