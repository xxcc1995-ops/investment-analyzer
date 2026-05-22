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
            if not name:
                return {"code": stock_code, "error": "未找到行情数据"}

            open_price = float(data[1]) if data[1] else 0
            pre_close = float(data[2]) if data[2] else 0
            price = float(data[3]) if data[3] else 0
            high = float(data[4]) if data[4] else 0
            low = float(data[5]) if data[5] else 0

            # 校验价格合理性
            if price <= 0:
                return {"code": stock_code, "error": "行情数据异常：价格为0或负数"}
            volume = int(float(data[8])) if data[8] else 0
            amount = float(data[9]) if data[9] else 0
            trade_date = data[30]  # 交易日期
            trade_time = data[31]  # 交易时间

            change_pct = ((price - pre_close) / pre_close * 100) if pre_close > 0 else 0

            # 获取总股本和PE/PB
            total_shares, pe, pb = DataService._get_valuation_data(stock_code, market, price)

            market_cap = price * total_shares  # total_shares already in 亿股, result in 亿元

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
        except Exception:
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
                reports.append(_classify_report(report))

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

    @staticmethod
    def get_dividend_stocks() -> list:
        """获取高股息股票数据 - 用于王文和散户乙筛选器"""
        try:
            # 使用东方财富API获取A股股票数据
            # 先获取沪深300成分股 + 中证红利成分股
            stocks = []

            # 预设的高股息蓝筹股列表（银行、能源、公用事业等）
            blue_chip_codes = [
                # 银行
                "601398", "601288", "601988", "601939", "600036",
                "601166", "600016", "601818", "600000", "601328",
                # 能源
                "601088", "600188", "601857", "600028", "601898",
                "601225", "600395", "601001", "600971", "601666",
                # 电力/公用事业
                "600900", "600886", "600795", "600023", "601985",
                "600025", "600674", "600236", "601991", "600098",
                # 交通运输
                "601006", "600029", "601111", "600115", "601872",
                "600009", "600018", "601598", "600897", "600026",
                # 钢铁/基建
                "600019", "601003", "600507", "601186", "601668",
                "601390", "601800", "601169", "600170", "600820",
                # 白酒/消费
                "600519", "000858", "000568", "600809", "002304",
                "000799", "603369", "600779", "000596", "600702",
                # 家电/制造
                "000333", "000651", "600690", "002032", "002508",
                # 医药
                "600196", "600276", "000538", "002001", "600867",
            ]

            # 去重
            unique_codes = list(set(blue_chip_codes))

            # 批量获取数据
            for code in unique_codes[:50]:  # 限制数量避免请求过多
                try:
                    stock_data = DataService._get_stock_dividend_data(code)
                    if stock_data and stock_data.get("dividend_yield") and stock_data["dividend_yield"] > 0:
                        stocks.append(stock_data)
                except Exception:
                    continue

            # 按股息率排序
            stocks.sort(key=lambda x: x.get("dividend_yield", 0), reverse=True)

            return stocks
        except Exception as e:
            print(f"获取高股息股票数据失败: {e}")
            return []

    @staticmethod
    def _get_stock_dividend_data(stock_code: str) -> dict:
        """获取单只股票的分红数据"""
        try:
            # 获取实时行情
            basic = DataService.get_stock_basic(stock_code)
            if "error" in basic:
                return None

            # 获取财务数据
            financials = DataService.get_financial_indicators(stock_code)
            if "error" in financials:
                return None

            reports = financials.get("reports", [])
            if not reports:
                return None

            latest = _get_annual_report(reports)

            # 获取实际分红数据
            dividend_per_share, consecutive_years, dividend_ratio = DataService._get_actual_dividend(stock_code)

            # 计算股息率（使用实际分红数据）
            if dividend_per_share > 0 and basic["price"] > 0:
                dividend_yield = (dividend_per_share / basic["price"]) * 100
            else:
                dividend_yield = 0

            return {
                "code": stock_code,
                "name": basic["name"],
                "price": basic["price"],
                "pe": basic.get("pe"),
                "pb": basic.get("pb"),
                "roe": latest.get("roe"),
                "dividend_yield": round(dividend_yield, 2),
                "dividend_per_share": dividend_per_share,
                "dividend_ratio": dividend_ratio,
                "debt_ratio": latest.get("debt_ratio"),
                "gross_margin": latest.get("gross_margin"),
                "net_margin": latest.get("net_margin"),
                "revenue_growth": latest.get("revenue_growth"),
                "profit_growth": latest.get("profit_growth"),
                "market_cap": basic.get("market_cap"),
                "consecutive_years": consecutive_years,
                "operating_cashflow": 1,
                "report_period": latest.get("report_period", ""),
            }
        except Exception as e:
            print(f"获取{stock_code}数据失败: {e}")
            return None

    @staticmethod
    def _get_actual_dividend(stock_code: str) -> tuple:
        """获取实际分红数据：每股股息、连续分红年数、分红比例"""
        try:
            from datetime import datetime, timedelta

            # 东方财富分红数据API
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                "reportName": "RPT_SHAREBONUS_DET",
                "columns": "SECURITY_CODE,REPORT_DATE,PRETAX_BONUS_RMB,BASIC_EPS,ASSIGN_PROGRESS",
                "filter": f"(SECURITY_CODE=\"{stock_code}\")",
                "pageNumber": "1",
                "pageSize": "20",
                "sortTypes": "-1",
                "sortColumns": "REPORT_DATE",
                "source": "HSF10",
                "client": "PC"
            }

            r = requests.get(url, params=params, timeout=15)
            data = r.json()

            if not data.get("result") or not data["result"].get("data"):
                return 0, 0, 0

            dividends = data["result"]["data"]

            # 计算过去12个月的总分红（包括中期分红和年终分红）
            # PRETAX_BONUS_RMB 是每10股的分红金额，需要除以10
            now = datetime.now()
            one_year_ago = now - timedelta(days=365)
            total_dividend_per_share = 0
            latest_eps = 0
            has_dividend_in_year = False

            for div in dividends:
                report_date_str = div.get("REPORT_DATE", "")[:10]
                if not report_date_str:
                    continue
                try:
                    report_date = datetime.strptime(report_date_str, "%Y-%m-%d")
                except ValueError:
                    continue

                bonus_per_10 = _safe_float(div.get("PRETAX_BONUS_RMB"))
                if bonus_per_10 and bonus_per_10 > 0:
                    # 检查是否在过去12个月内
                    if report_date >= one_year_ago:
                        total_dividend_per_share += bonus_per_10 / 10
                        has_dividend_in_year = True
                        if latest_eps == 0:
                            latest_eps = _safe_float(div.get("BASIC_EPS")) or 0

            # 如果过去12个月没有分红，取最近一次有分红的数据
            if not has_dividend_in_year:
                for div in dividends:
                    bonus_per_10 = _safe_float(div.get("PRETAX_BONUS_RMB"))
                    if bonus_per_10 and bonus_per_10 > 0:
                        total_dividend_per_share = bonus_per_10 / 10
                        latest_eps = _safe_float(div.get("BASIC_EPS")) or 0
                        break

            # 计算连续分红年数（跳过没有分红金额的数据）
            consecutive_years = 0
            for div in dividends:
                bonus = _safe_float(div.get("PRETAX_BONUS_RMB"))
                if bonus and bonus > 0:
                    consecutive_years += 1
                # 只有当bonus为0时才中断（表示没有分红）
                elif bonus == 0:
                    break
                # bonus为None表示还未公布，跳过继续检查

            # 计算分红比例
            dividend_ratio = 0
            if latest_eps > 0 and total_dividend_per_share > 0:
                dividend_ratio = round((total_dividend_per_share / latest_eps) * 100, 2)

            return total_dividend_per_share, consecutive_years, dividend_ratio

        except Exception as e:
            print(f"获取{stock_code}分红数据失败: {e}")
            return 0, 0, 0


def _safe_float(val) -> Optional[float]:
    """安全转换为浮点数"""
    if val is None:
        return None
    try:
        return round(float(val), 4)
    except (ValueError, TypeError):
        return None


def _classify_report(report: dict) -> dict:
    """给报告添加报告期分类信息"""
    date = report.get("date", "")
    month_day = date[5:] if len(date) >= 10 else ""

    if month_day == "12-31":
        report["report_period"] = f"{date[:4]}年报"
        report["is_annual"] = True
    elif month_day == "09-30":
        report["report_period"] = f"{date[:4]}三季报"
        report["is_annual"] = False
    elif month_day == "06-30":
        report["report_period"] = f"{date[:4]}中报"
        report["is_annual"] = False
    elif month_day == "03-31":
        report["report_period"] = f"{date[:4]}一季报"
        report["is_annual"] = False
    else:
        report["report_period"] = date
        report["is_annual"] = False

    return report


def _get_annual_report(reports: list) -> dict:
    """从报告列表中选取最新一份年报，找不到则回退到最新报告"""
    for r in reports:
        if r.get("is_annual"):
            return r
    return reports[0] if reports else {}
