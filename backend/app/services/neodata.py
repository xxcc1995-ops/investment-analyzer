"""
NeoData 金融数据服务（腾讯）
数据源：腾讯 NeoData（需要 NEODATA_TOKEN）
配置：通过环境变量 NEODATA_TOKEN 设置Token

状态（2026-07-15 审查）：当前未被任何路由调用。
作为 CLAUDE.md 登记的数据源对接层保留；接入时需配置 NEODATA_TOKEN。
"""
import os
import httpx
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

class NeoDataService:
    """NeoData金融数据服务"""

    def __init__(self):
        self.base_url = "https://copilot.tencent.com/agenttool/v1/neodata"
        self.token = os.getenv("NEODATA_TOKEN")

    async def query(self, query: str, data_type: str = "api") -> dict:
        """执行自然语言查询"""
        if not self.token:
            raise Exception("NEODATA_TOKEN未设置，请先获取token")

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        payload = {
            "query": query,
            "channel": "neodata",
            "sub_channel": "workbuddy",
            "data_type": data_type
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=30.0
                )

                if response.status_code == 401:
                    # Token过期，需要重新获取
                    raise Exception("Token已过期，请重新获取")

                data = response.json()

                if data.get("code") != "200":
                    raise Exception(f"查询失败: {data.get('msg', '未知错误')}")

                return data.get("data", {})
        except httpx.TimeoutException:
            logger.error(f"NeoData查询超时: {query}")
            raise Exception("NeoData查询超时，请稍后重试")
        except httpx.ConnectError:
            logger.error(f"NeoData连接失败: {query}")
            raise Exception("NeoData服务连接失败，请检查网络")
        except httpx.HTTPStatusError as e:
            logger.error(f"NeoData HTTP错误 {e.response.status_code}: {query}")
            raise Exception(f"NeoData请求失败: HTTP {e.response.status_code}")
        except Exception:
            raise  # 重新抛出已有的业务异常

    async def get_stock_metrics(self, stock_code: str) -> dict:
        """获取股票关键指标"""
        data = await self.query(f"{stock_code} PE PB ROE 市盈率 市净率 净资产收益率")
        return self._parse_metrics(data)

    async def get_financial_growth(self, stock_code: str) -> dict:
        """获取财务增长数据"""
        data = await self.query(f"{stock_code} 营业收入 净利润 同比增长率 自由现金流")
        return self._parse_growth(data)

    def _parse_metrics(self, data: dict) -> dict:
        """解析指标数据"""
        api_data = data.get("apiData", {})
        recall = api_data.get("apiRecall", [])

        result = {}
        for item in recall:
            content = item.get("content", {})
            if not isinstance(content, dict):
                continue
            # NeoData返回的key-value对，提取常见财务指标
            for key, value in content.items():
                key_lower = str(key).lower()
                if any(k in key_lower for k in ('pe', '市盈率')):
                    result['pe'] = value
                elif any(k in key_lower for k in ('pb', '市净率')):
                    result['pb'] = value
                elif any(k in key_lower for k in ('roe', '净资产收益率')):
                    result['roe'] = value
                elif any(k in key_lower for k in ('市值', 'market_cap')):
                    result['market_cap'] = value
                elif any(k in key_lower for k in ('股息', 'dividend')):
                    result['dividend_yield'] = value

        return result

    def _parse_growth(self, data: dict) -> dict:
        """解析增长数据"""
        api_data = data.get("apiData", {})
        recall = api_data.get("apiRecall", [])

        result = {}
        for item in recall:
            content = item.get("content", {})
            if not isinstance(content, dict):
                continue
            for key, value in content.items():
                key_lower = str(key).lower()
                if any(k in key_lower for k in ('营收增长', 'revenue_growth')):
                    result['revenue_growth'] = value
                elif any(k in key_lower for k in ('净利润增长', 'profit_growth')):
                    result['profit_growth'] = value
                elif any(k in key_lower for k in ('营收', 'revenue')):
                    result['revenue'] = value
                elif any(k in key_lower for k in ('净利润', 'net_profit')):
                    result['net_profit'] = value
                elif any(k in key_lower for k in ('自由现金流', 'free_cash_flow')):
                    result['free_cash_flow'] = value

        return result
