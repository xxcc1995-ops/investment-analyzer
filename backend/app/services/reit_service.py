"""
REIT数据服务 - 获取中国公募REITs数据
数据源：新浪财经API

TODO: FUNDAMENTALS使用行业平均值而非每只REIT的实际数据。
应改为从基金公司披露或CSRC获取每只REIT的实际NAV/分红/出租率数据。
"""

import logging
import requests
import re
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class REITService:
    """REIT数据服务"""

    # 中国公募REITs列表（硬编码，定期更新）
    REIT_LIST = [
        {"code": "508056", "name": "中金普洛斯REIT", "type": "仓储物流"},
        {"code": "508000", "name": "华安张江光大REIT", "type": "产业园区"},
        {"code": "508027", "name": "东吴苏园产业REIT", "type": "产业园区"},
        {"code": "508006", "name": "博时蛇口产园REIT", "type": "产业园区"},
        {"code": "508001", "name": "浙商沪杭甬REIT", "type": "高速公路"},
        {"code": "508008", "name": "国金铁建REIT", "type": "高速公路"},
        {"code": "508009", "name": "中金安徽交控REIT", "type": "高速公路"},
        {"code": "508018", "name": "华夏中国交建REIT", "type": "高速公路"},
        {"code": "508068", "name": "华泰江苏交控REIT", "type": "高速公路"},
        {"code": "508058", "name": "建信中关村REIT", "type": "产业园区"},
        {"code": "180301", "name": "红土盐田港REIT", "type": "仓储物流"},
        {"code": "180201", "name": "鹏华深圳能源REIT", "type": "能源基础设施"},
        {"code": "508096", "name": "中航首钢绿能REIT", "type": "生态环保"},
        {"code": "508007", "name": "国泰君安临港创新产业园REIT", "type": "产业园区"},
        {"code": "508088", "name": "嘉实京东仓储REIT", "type": "仓储物流"},
        {"code": "508098", "name": "嘉实物美消费REIT", "type": "商业/消费"},
        {"code": "508003", "name": "华夏合肥高新产园REIT", "type": "产业园区"},
        {"code": "508066", "name": "中金厦门安居REIT", "type": "保障性租赁住房"},
        {"code": "508077", "name": "华夏北京保障房REIT", "type": "保障性租赁住房"},
        {"code": "180501", "name": "红土创新深圳安居REIT", "type": "保障性租赁住房"},
        {"code": "508028", "name": "华夏华润有巢REIT", "type": "保障性租赁住房"},
        {"code": "508011", "name": "中信建投国家电投新能源REIT", "type": "能源基础设施"},
        {"code": "508099", "name": "中航京能光伏REIT", "type": "能源基础设施"},
        {"code": "508097", "name": "国泰君安东久新经济REIT", "type": "产业园区"},
        {"code": "508091", "name": "华安百联消费REIT", "type": "商业/消费"},
        {"code": "180801", "name": "中金印力消费REIT", "type": "商业/消费"},
        {"code": "508002", "name": "富国首创水务REIT", "type": "生态环保"},
        {"code": "508005", "name": "中金山东高速REIT", "type": "高速公路"},
        {"code": "508069", "name": "华夏越秀高速REIT", "type": "高速公路"},
        {"code": "508012", "name": "平安广州广河REIT", "type": "高速公路"},
    ]

    # 估算的基本面数据（实际应从定期报告获取）
    FUNDAMENTALS = {
        "仓储物流": {"dividend_yield": 5.5, "p_nav": 0.95, "occupancy_rate": 92, "debt_ratio": 35},
        "产业园区": {"dividend_yield": 5.2, "p_nav": 1.05, "occupancy_rate": 88, "debt_ratio": 40},
        "高速公路": {"dividend_yield": 7.5, "p_nav": 0.85, "occupancy_rate": 95, "debt_ratio": 45},
        "能源基础设施": {"dividend_yield": 6.8, "p_nav": 0.90, "occupancy_rate": 98, "debt_ratio": 50},
        "生态环保": {"dividend_yield": 6.0, "p_nav": 0.92, "occupancy_rate": 95, "debt_ratio": 42},
        "保障性租赁住房": {"dividend_yield": 4.5, "p_nav": 1.10, "occupancy_rate": 96, "debt_ratio": 38},
        "商业/消费": {"dividend_yield": 4.8, "p_nav": 1.15, "occupancy_rate": 85, "debt_ratio": 48},
    }

    def get_all_reits(self, filters: Dict = None) -> List[Dict]:
        """
        获取所有REIT数据并应用筛选
        """
        # TODO: FUNDAMENTALS使用行业平均值，应改为每只REIT的实际数据
        logger.warning("REIT基本面数据使用行业平均值，非实际数据。建议从定期报告获取。")

        if filters is None:
            filters = {}

        min_dividend_yield = filters.get("min_dividend_yield", 5)
        max_p_nav = filters.get("max_p_nav", 1.2)
        min_occupancy = filters.get("min_occupancy", 85)
        max_debt_ratio = filters.get("max_debt_ratio", 50)
        min_turnover = filters.get("min_turnover", 100)
        asset_type = filters.get("asset_type", "all")

        # 批量获取实时数据
        realtime_data = self._fetch_batch_realtime()

        results = []
        for reit_info in self.REIT_LIST:
            code = reit_info["code"]
            name = reit_info["name"]
            rtype = reit_info["type"]

            # 资产类型筛选
            if asset_type != "all" and rtype != asset_type:
                continue

            # 获取实时数据
            realtime = realtime_data.get(code)
            if not realtime:
                continue

            # 获取基本面数据
            fundamentals = self.FUNDAMENTALS.get(rtype, {
                "dividend_yield": 5.0, "p_nav": 1.0, "occupancy_rate": 90, "debt_ratio": 45
            })

            # 日均成交额（万元）
            daily_turnover = realtime.get("amount", 0) / 10000

            # 应用筛选条件
            dividend_yield = fundamentals["dividend_yield"]
            p_nav = fundamentals["p_nav"]
            occupancy = fundamentals["occupancy_rate"]
            debt_ratio = fundamentals["debt_ratio"]

            if dividend_yield < min_dividend_yield:
                continue
            if p_nav > max_p_nav:
                continue
            if occupancy < min_occupancy:
                continue
            if debt_ratio > max_debt_ratio:
                continue
            if daily_turnover < min_turnover:
                continue

            # 计算评分
            score = self._calculate_score({
                "dividend_yield": dividend_yield,
                "p_nav": p_nav,
                "occupancy_rate": occupancy,
                "debt_ratio": debt_ratio,
                "daily_turnover": daily_turnover,
            })

            results.append({
                "code": code,
                "name": name,
                "asset_type": rtype,
                "price": realtime["price"],
                "change_pct": realtime["change_pct"],
                "daily_turnover": round(daily_turnover, 2),
                "dividend_yield": dividend_yield,
                "p_nav": p_nav,
                "occupancy_rate": occupancy,
                "debt_ratio": debt_ratio,
                "score": score,
                "risk_level": self._get_risk_level(rtype),
                "risk_notes": self._get_risk_notes(rtype),
            })

        # 按评分排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def _fetch_batch_realtime(self) -> Dict[str, Dict]:
        """批量获取REIT实时数据（新浪财经API）"""
        # 构建代码列表
        codes = []
        for reit in self.REIT_LIST:
            code = reit["code"]
            prefix = "sh" if code.startswith("5") else "sz"
            codes.append(f"{prefix}{code}")

        # 批量请求
        url = f"https://hq.sinajs.cn/list={','.join(codes)}"
        headers = {'Referer': 'https://finance.sina.com.cn'}

        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.encoding = 'gbk'
            text = resp.text
        except Exception as e:
            print(f"获取REIT批量数据失败: {e}")
            return {}

        result = {}
        for line in text.strip().split('\n'):
            if '=' not in line:
                continue

            # 提取代码
            var_part, _, val_part = line.partition('=')
            match = re.search(r'hq_str_(sh|sz)(\d+)', var_part)
            if not match:
                continue

            prefix = match.group(1)
            code = match.group(2)
            val_part = val_part.strip(';').strip('"')

            if not val_part:
                continue

            fields = val_part.split(',')
            if len(fields) < 10:
                continue

            try:
                # 格式: 名称,今开,昨收,当前,最高,最低,买一,卖一,成交量,成交额,...
                name = fields[0]
                price = float(fields[3]) if fields[3] else 0
                pre_close = float(fields[2]) if fields[2] else 0
                volume = int(fields[8]) if fields[8] else 0
                amount = float(fields[9]) if fields[9] else 0

                if price <= 0:
                    continue

                change_pct = round((price - pre_close) / pre_close * 100, 2) if pre_close > 0 else 0

                result[code] = {
                    "name": name,
                    "price": price,
                    "pre_close": pre_close,
                    "change_pct": change_pct,
                    "volume": volume,
                    "amount": amount,
                }
            except (ValueError, IndexError):
                continue

        return result

    def _calculate_score(self, data: Dict) -> int:
        """计算REIT综合评分 (满分100)"""
        score = 0

        # 现金分派率 (35分)
        dividend_yield = data.get("dividend_yield", 0)
        if dividend_yield >= 8:
            score += 35
        elif dividend_yield >= 6:
            score += 28
        elif dividend_yield >= 5:
            score += 21

        # P/NAV (25分)
        p_nav = data.get("p_nav", 999)
        if p_nav <= 0.8:
            score += 25
        elif p_nav <= 1.0:
            score += 20
        elif p_nav <= 1.2:
            score += 12

        # 出租率 (20分)
        occupancy = data.get("occupancy_rate", 0)
        if occupancy >= 95:
            score += 20
        elif occupancy >= 90:
            score += 16
        elif occupancy >= 85:
            score += 10

        # 资产负债率 (10分)
        debt_ratio = data.get("debt_ratio", 100)
        if debt_ratio <= 30:
            score += 10
        elif debt_ratio <= 40:
            score += 8
        elif debt_ratio <= 50:
            score += 5

        # 流动性 (10分)
        daily_turnover = data.get("daily_turnover", 0)
        if daily_turnover >= 500:
            score += 10
        elif daily_turnover >= 200:
            score += 8
        elif daily_turnover >= 100:
            score += 5

        return score

    def _get_risk_level(self, asset_type: str) -> str:
        """获取资产类型风险等级"""
        risk_map = {
            "仓储物流": "低",
            "产业园区": "中",
            "高速公路": "中低",
            "能源基础设施": "中",
            "生态环保": "中低",
            "保障性租赁住房": "低",
            "商业/消费": "中高",
        }
        return risk_map.get(asset_type, "中")

    def _get_risk_notes(self, asset_type: str) -> List[str]:
        """获取资产类型风险提示"""
        notes_map = {
            "仓储物流": ["受电商物流需求影响", "关注租户集中度"],
            "产业园区": ["受经济周期影响较大", "关注出租率变化趋势"],
            "高速公路": ["有经营期限，到期后资产无偿移交", "车流量受经济和政策影响"],
            "能源基础设施": ["受能源政策影响大", "电价波动影响收益"],
            "生态环保": ["受环保政策影响", "运营成本可能上升"],
            "保障性租赁住房": ["政策支持力度大", "租金增长空间有限"],
            "商业/消费": ["受消费景气度影响", "新品种样本少，风险较高"],
        }
        return notes_map.get(asset_type, [])


# 单例
reit_service = REITService()
