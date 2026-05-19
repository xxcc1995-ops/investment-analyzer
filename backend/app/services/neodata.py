import os
import httpx
from dotenv import load_dotenv

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
        # 根据NeoData的实际响应格式解析
        api_data = data.get("apiData", {})
        recall = api_data.get("apiRecall", [])

        result = {}
        for item in recall:
            content = item.get("content", {})
            # 解析具体字段
            # 这里需要根据实际返回的数据结构调整
            pass

        return result

    def _parse_growth(self, data: dict) -> dict:
        """解析增长数据"""
        return {}
