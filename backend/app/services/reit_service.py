"""
REIT数据服务 - 中国公募REITs机构级分析

数据源：
- 实时行情：新浪财经API（REIT在沪深交易所上市）
- NAV数据：东方财富基金API（REIT按基金产品披露净值）
- 分派率：基于累计NAV差值估算（累计NAV - 单位NAV = 历史累计分红）

关键概念：
- 现金分派率(Cash Distribution Yield) = 近12个月现金分红 / 当前市价
- P/NAV = 当前市价 / 最新单位NAV
- NAV溢价率 = (市价 - NAV) / NAV * 100%
- 杠杆率 = 总负债 / 总资产（REIT监管上限为净资产的140%）

数据局限性说明：
- 每只REIT的实际出租率/负债率需从定期报告获取，当前使用行业估计值
- 现金分派率使用累计NAV差值估算，可能与实际分红有偏差
- NAV更新频率为季度（季报/半年报/年报），非实时
"""

import logging
import requests
import re
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from functools import lru_cache

logger = logging.getLogger(__name__)

# 共享HTTP会话
_session = requests.Session()
_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})


class REITService:
    """REIT机构级数据服务"""

    # ========================================================================
    # 中国公募REITs完整列表（截至2025年6月）
    # 包含所有已上市基础设施公募REITs
    # 来源：沪深交易所公告、证监会注册批文
    # ========================================================================
    REIT_LIST = [
        # === 仓储物流 ===
        {"code": "508056", "name": "中金普洛斯REIT", "type": "仓储物流",
         "underlying": "普洛斯物流园", "location": "北京/广州/昆明",
         "est_occupancy": 92, "est_debt_ratio": 35,
         "concession_years": None, "concession_start": None},
        {"code": "180301", "name": "红土盐田港REIT", "type": "仓储物流",
         "underlying": "盐田港物流中心", "location": "深圳",
         "est_occupancy": 94, "est_debt_ratio": 33,
         "concession_years": None, "concession_start": None},
        {"code": "508088", "name": "嘉实京东仓储REIT", "type": "仓储物流",
         "underlying": "京东仓储物流中心", "location": "廊坊/武汉/重庆",
         "est_occupancy": 95, "est_debt_ratio": 30,
         "concession_years": None, "concession_start": None},
        {"code": "508098", "name": "嘉实物美消费REIT", "type": "商业/消费",
         "underlying": "物美集团商超物业", "location": "北京",
         "est_occupancy": 88, "est_debt_ratio": 42,
         "concession_years": None, "concession_start": None},

        # === 产业园区 ===
        {"code": "508000", "name": "华安张江光大REIT", "type": "产业园区",
         "underlying": "张江光大园", "location": "上海",
         "est_occupancy": 90, "est_debt_ratio": 38,
         "concession_years": None, "concession_start": None},
        {"code": "508027", "name": "东吴苏园产业REIT", "type": "产业园区",
         "underlying": "苏州工业园区", "location": "苏州",
         "est_occupancy": 88, "est_debt_ratio": 40,
         "concession_years": None, "concession_start": None},
        {"code": "508006", "name": "博时蛇口产园REIT", "type": "产业园区",
         "underlying": "蛇口网谷产业园", "location": "深圳",
         "est_occupancy": 87, "est_debt_ratio": 42,
         "concession_years": None, "concession_start": None},
        {"code": "508058", "name": "建信中关村REIT", "type": "产业园区",
         "underlying": "中关村软件园", "location": "北京",
         "est_occupancy": 82, "est_debt_ratio": 45,
         "concession_years": None, "concession_start": None},
        {"code": "508003", "name": "华夏合肥高新产园REIT", "type": "产业园区",
         "underlying": "合肥高新区产业园", "location": "合肥",
         "est_occupancy": 85, "est_debt_ratio": 40,
         "concession_years": None, "concession_start": None},
        {"code": "508007", "name": "国泰君安临港创新产业园REIT", "type": "产业园区",
         "underlying": "临港新片区产业园", "location": "上海",
         "est_occupancy": 88, "est_debt_ratio": 38,
         "concession_years": None, "concession_start": None},
        {"code": "508097", "name": "国泰君安东久新经济REIT", "type": "产业园区",
         "underlying": "东久新经济产业园", "location": "上海/昆山",
         "est_occupancy": 90, "est_debt_ratio": 36,
         "concession_years": None, "concession_start": None},
        {"code": "508089", "name": "国泰君安城投宽庭REIT", "type": "产业园区",
         "underlying": "城投宽庭公寓", "location": "上海",
         "est_occupancy": 92, "est_debt_ratio": 38,
         "concession_years": None, "concession_start": None},

        # === 高速公路 ===
        {"code": "508001", "name": "浙商沪杭甬REIT", "type": "高速公路",
         "underlying": "杭徽高速浙江段", "location": "浙江",
         "est_occupancy": 95, "est_debt_ratio": 48,
         "concession_years": 25, "concession_start": 2004},
        {"code": "508008", "name": "国金铁建REIT", "type": "高速公路",
         "underlying": "渝遂高速", "location": "重庆/四川",
         "est_occupancy": 90, "est_debt_ratio": 52,
         "concession_years": 25, "concession_start": 2004},
        {"code": "508009", "name": "中金安徽交控REIT", "type": "高速公路",
         "underlying": "沿江高速", "location": "安徽",
         "est_occupancy": 88, "est_debt_ratio": 50,
         "concession_years": 25, "concession_start": 2008},
        {"code": "508018", "name": "华夏中国交建REIT", "type": "高速公路",
         "underlying": "嘉通高速", "location": "浙江",
         "est_occupancy": 85, "est_debt_ratio": 55,
         "concession_years": 25, "concession_start": 2010},
        {"code": "508068", "name": "华泰江苏交控REIT", "type": "高速公路",
         "underlying": "沿江高速(江苏段)", "location": "江苏",
         "est_occupancy": 90, "est_debt_ratio": 48,
         "concession_years": 25, "concession_start": 2006},
        {"code": "508005", "name": "中金山东高速REIT", "type": "高速公路",
         "underlying": "鄄菏高速", "location": "山东",
         "est_occupancy": 85, "est_debt_ratio": 50,
         "concession_years": 25, "concession_start": 2012},
        {"code": "508069", "name": "华夏越秀高速REIT", "type": "高速公路",
         "underlying": "汉孝高速", "location": "湖北",
         "est_occupancy": 88, "est_debt_ratio": 48,
         "concession_years": 30, "concession_start": 2006},
        {"code": "508012", "name": "平安广州广河REIT", "type": "高速公路",
         "underlying": "广河高速广州段", "location": "广州",
         "est_occupancy": 92, "est_debt_ratio": 45,
         "concession_years": 25, "concession_start": 2011},

        # === 能源基础设施 ===
        {"code": "180201", "name": "鹏华深圳能源REIT", "type": "能源基础设施",
         "underlying": "深圳东部垃圾焚烧厂", "location": "深圳",
         "est_occupancy": 98, "est_debt_ratio": 50,
         "concession_years": 30, "concession_start": 2019},
        {"code": "508011", "name": "中信建投国家电投新能源REIT", "type": "能源基础设施",
         "underlying": "海上风电项目", "location": "盐城",
         "est_occupancy": 98, "est_debt_ratio": 52,
         "concession_years": 25, "concession_start": 2020},
        {"code": "508099", "name": "中航京能光伏REIT", "type": "能源基础设施",
         "underlying": "光伏发电项目", "location": "湖北/新疆",
         "est_occupancy": 99, "est_debt_ratio": 48,
         "concession_years": 20, "concession_start": 2018},
        {"code": "508070", "name": "嘉实中国电建清洁能源REIT", "type": "能源基础设施",
         "underlying": "水电项目", "location": "四川",
         "est_occupancy": 98, "est_debt_ratio": 50,
         "concession_years": 30, "concession_start": 2015},

        # === 生态环保 ===
        {"code": "508096", "name": "中航首钢绿能REIT", "type": "生态环保",
         "underlying": "生物质能源项目", "location": "北京",
         "est_occupancy": 95, "est_debt_ratio": 42,
         "concession_years": 30, "concession_start": 2018},
        {"code": "508002", "name": "富国首创水务REIT", "type": "生态环保",
         "underlying": "污水处理项目", "location": "深圳",
         "est_occupancy": 96, "est_debt_ratio": 40,
         "concession_years": 30, "concession_start": 2016},

        # === 保障性租赁住房 ===
        {"code": "508066", "name": "中金厦门安居REIT", "type": "保障性租赁住房",
         "underlying": "保障性租赁住房", "location": "厦门",
         "est_occupancy": 97, "est_debt_ratio": 32,
         "concession_years": None, "concession_start": None},
        {"code": "508077", "name": "华夏北京保障房REIT", "type": "保障性租赁住房",
         "underlying": "保障性租赁住房", "location": "北京",
         "est_occupancy": 98, "est_debt_ratio": 30,
         "concession_years": None, "concession_start": None},
        {"code": "180501", "name": "红土创新深圳安居REIT", "type": "保障性租赁住房",
         "underlying": "保障性租赁住房", "location": "深圳",
         "est_occupancy": 97, "est_debt_ratio": 35,
         "concession_years": None, "concession_start": None},
        {"code": "508028", "name": "华夏华润有巢REIT", "type": "保障性租赁住房",
         "underlying": "有巢国际公寓", "location": "上海/杭州",
         "est_occupancy": 95, "est_debt_ratio": 36,
         "concession_years": None, "concession_start": None},

        # === 商业/消费 ===
        {"code": "508091", "name": "华安百联消费REIT", "type": "商业/消费",
         "underlying": "百联又一城购物中心", "location": "上海",
         "est_occupancy": 85, "est_debt_ratio": 48,
         "concession_years": None, "concession_start": None},
        {"code": "180801", "name": "中金印力消费REIT", "type": "商业/消费",
         "underlying": "杭州西溪印象城", "location": "杭州",
         "est_occupancy": 90, "est_debt_ratio": 45,
         "concession_years": None, "concession_start": None},
        {"code": "508078", "name": "华夏金茂商业REIT", "type": "商业/消费",
         "underlying": "长沙金茂览秀城", "location": "长沙",
         "est_occupancy": 88, "est_debt_ratio": 46,
         "concession_years": None, "concession_start": None},
        {"code": "508080", "name": "华夏华润商业REIT", "type": "商业/消费",
         "underlying": "青岛万象城", "location": "青岛",
         "est_occupancy": 92, "est_debt_ratio": 44,
         "concession_years": None, "concession_start": None},
    ]

    # 资产类型特性配置（用于利率敏感性和综合评分）
    ASSET_PROFILES = {
        "仓储物流": {
            "risk_level": "低",
            "rate_sensitivity": "低",       # 短期租约，租金可调整
            "growth_potential": "中",
            "economic_cycle": "低",          # 电商驱动，受经济周期影响较小
            "description": "电商/第三方物流需求驱动，租约灵活，现金流稳定",
        },
        "产业园区": {
            "risk_level": "中",
            "rate_sensitivity": "中",
            "growth_potential": "中",
            "economic_cycle": "高",           # 受宏观经济和产业政策影响大
            "description": "受科技/制造业景气度影响，出租率波动较大",
        },
        "高速公路": {
            "risk_level": "中低",
            "rate_sensitivity": "高",         # 长期限，利率变动影响大
            "growth_potential": "低",
            "economic_cycle": "中",
            "description": "车流量与经济相关，有经营期限限制，到期后资产无偿移交",
        },
        "能源基础设施": {
            "risk_level": "中",
            "rate_sensitivity": "中高",       # 重资产，高杠杆
            "growth_potential": "中",
            "economic_cycle": "低",           # 刚性需求
            "description": "政策驱动，电价/气价受管制，现金流可预测性强",
        },
        "生态环保": {
            "risk_level": "中低",
            "rate_sensitivity": "中",
            "growth_potential": "低",
            "economic_cycle": "低",
            "description": "政府付费为主，现金流稳定但增长空间有限",
        },
        "保障性租赁住房": {
            "risk_level": "低",
            "rate_sensitivity": "低",
            "growth_potential": "低",
            "economic_cycle": "低",
            "description": "政策大力支持，出租率高但租金增长空间有限",
        },
        "商业/消费": {
            "risk_level": "中高",
            "rate_sensitivity": "中",
            "growth_potential": "中高",
            "economic_cycle": "高",           # 消费景气度直接影响
            "description": "受消费趋势影响大，运营能力决定价值，新品种样本少",
        },
    }

    # 风险提示（按资产类型）
    RISK_NOTES = {
        "仓储物流": [
            "受电商物流需求影响，关注行业增速放缓风险",
            "关注租户集中度，大租户退租风险",
            "新增供给可能压低租金水平",
        ],
        "产业园区": [
            "受经济周期影响较大，衰退期出租率可能大幅下滑",
            "关注产业转移风险（如制造业外迁）",
            "科技园区受政策和行业景气度影响显著",
        ],
        "高速公路": [
            "有经营期限，到期后资产无偿移交（剩余年限影响估值）",
            "车流量受经济周期和政策影响（如节假日免费政策）",
            "新建平行路线分流风险",
            "利率上行环境对长久期资产冲击最大",
        ],
        "能源基础设施": [
            "受能源政策影响大（如碳中和政策）",
            "电价/气价受管制，上行空间有限",
            "技术迭代风险（如光伏效率提升对存量项目冲击）",
        ],
        "生态环保": [
            "政府付费为主，关注财政支付能力",
            "运营成本上升可能侵蚀利润",
            "环保政策变化可能影响项目运营",
        ],
        "保障性租赁住房": [
            "政策支持力度大，但租金增长空间有限",
            "受房地产市场调控政策影响",
            "空置风险较低但收益率上限也较低",
        ],
        "商业/消费": [
            "受消费景气度影响大，经济下行时风险最高",
            "新品种上市时间短，历史数据有限",
            "电商冲击实体商业的长期趋势",
            "运营方能力差异导致分化加剧",
        ],
    }

    # ========================================================================
    # 数据获取 - 实时行情 + NAV
    # ========================================================================

    def _fetch_batch_realtime(self) -> Dict[str, Dict]:
        """批量获取REIT实时数据（新浪财经API）

        返回: {code: {name, price, pre_close, change_pct, volume, amount}}
        """
        codes = []
        for reit in self.REIT_LIST:
            code = reit["code"]
            prefix = "sh" if code.startswith("5") else "sz"
            codes.append(f"{prefix}{code}")

        url = f"https://hq.sinajs.cn/list={','.join(codes)}"
        headers = {'Referer': 'https://finance.sina.com.cn'}

        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.encoding = 'gbk'
            text = resp.text
        except Exception as e:
            logger.warning(f"获取REIT批量行情失败: {e}")
            return {}

        result = {}
        for line in text.strip().split('\n'):
            if '=' not in line:
                continue

            var_part, _, val_part = line.partition('=')
            match = re.search(r'hq_str_(sh|sz)(\d+)', var_part)
            if not match:
                continue

            code = match.group(2)
            val_part = val_part.strip(';').strip('"')
            if not val_part:
                continue

            fields = val_part.split(',')
            if len(fields) < 10:
                continue

            try:
                price = float(fields[3]) if fields[3] else 0
                pre_close = float(fields[2]) if fields[2] else 0
                volume = int(fields[8]) if fields[8] else 0
                amount = float(fields[9]) if fields[9] else 0

                if price <= 0:
                    continue

                change_pct = round((price - pre_close) / pre_close * 100, 2) if pre_close > 0 else 0

                result[code] = {
                    "name": fields[0],
                    "price": price,
                    "pre_close": pre_close,
                    "change_pct": change_pct,
                    "volume": volume,
                    "amount": amount,
                }
            except (ValueError, IndexError):
                continue

        return result

    def _fetch_fund_nav(self, code: str) -> Optional[Dict]:
        """从东方财富基金API获取REIT净值数据

        返回: {unit_nav, cum_nav, nav_date, inception_nav, inception_date}
        """
        url = f'https://fund.eastmoney.com/pingzhongdata/{code}.js'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': f'https://fund.eastmoney.com/{code}.html'
        }

        try:
            r = _session.get(url, headers=headers, timeout=10)
            r.encoding = 'utf-8'
            text = r.text

            if not text or 'netWorthTrend' not in text:
                return None

            # 解析单位净值趋势
            m_nav = re.search(r'var Data_netWorthTrend\s*=\s*(\[.*?\]);', text, re.DOTALL)
            m_ac = re.search(r'var Data_ACWorthTrend\s*=\s*(\[.*?\]);', text, re.DOTALL)

            if not m_nav:
                return None

            nav_data = json.loads(m_nav.group(1))
            if not nav_data:
                return None

            latest = nav_data[-1]
            unit_nav = latest.get('y', 0)
            nav_timestamp = latest.get('x', 0) / 1000  # 毫秒转秒
            nav_date = datetime.fromtimestamp(nav_timestamp).strftime('%Y-%m-%d') if nav_timestamp else ''

            # 解析累计净值趋势
            cum_nav = None
            if m_ac:
                ac_data = json.loads(m_ac.group(1))
                if ac_data:
                    cum_nav = ac_data[-1][1] if ac_data[-1] else None

            # 起始数据（用于计算年化分派率）
            inception = nav_data[0]
            inception_nav = inception.get('y', 0)
            inception_timestamp = inception.get('x', 0) / 1000
            inception_date = datetime.fromtimestamp(inception_timestamp).strftime('%Y-%m-%d') if inception_timestamp else ''

            return {
                "unit_nav": unit_nav,
                "cum_nav": cum_nav,
                "nav_date": nav_date,
                "inception_nav": inception_nav,
                "inception_date": inception_date,
            }
        except Exception as e:
            logger.warning(f"获取REIT {code} NAV失败: {e}")
            return None

    def _fetch_batch_nav(self) -> Dict[str, Dict]:
        """批量获取所有REIT的NAV数据

        返回: {code: {unit_nav, cum_nav, nav_date, ...}}
        """
        results = {}
        for reit in self.REIT_LIST:
            code = reit["code"]
            nav_data = self._fetch_fund_nav(code)
            if nav_data:
                results[code] = nav_data
            time.sleep(0.1)  # 避免请求过快
        return results

    # ========================================================================
    # 分派率计算
    # ========================================================================

    def _calc_distribution_yield(self, nav_data: Dict, current_price: float) -> Dict:
        """计算REIT分派率

        方法：
        1. 累计NAV差值法：累计NAV - 单位NAV = 累计历史分红总额
           年化分派率 = (累计分红 / 上市年限) / 当前市价 * 100%
        2. 如果累计NAV等于单位NAV（无分红记录），返回估算值

        Returns:
            {
                "total_distributions": float,  # 累计分红总额（每份）
                "years_listed": float,          # 上市年限
                "annual_yield": float,          # 年化分派率(%)
                "method": str,                  # 计算方法
            }
        """
        unit_nav = nav_data.get("unit_nav", 0)
        cum_nav = nav_data.get("cum_nav")
        inception_date = nav_data.get("inception_date", "")

        if not unit_nav or not current_price or current_price <= 0:
            return {"total_distributions": 0, "years_listed": 0, "annual_yield": 0, "method": "无数据"}

        # 计算上市年限
        years_listed = 0
        if inception_date:
            try:
                d = datetime.strptime(inception_date, "%Y-%m-%d")
                years_listed = (datetime.now() - d).days / 365.25
            except ValueError:
                pass

        if not cum_nav or cum_nav <= 0:
            # 没有累计NAV数据，无法计算
            return {"total_distributions": 0, "years_listed": years_listed, "annual_yield": 0, "method": "NAV数据不完整"}

        # 累计分红 = 累计NAV - 单位NAV
        total_distributions = cum_nav - unit_nav
        if total_distributions < 0:
            total_distributions = 0

        # 年化分派率 = (累计分红 / 上市年限) / 当前市价 * 100
        annual_yield = 0
        method = "累计NAV差值法"
        if years_listed > 0 and total_distributions > 0:
            annual_distributions = total_distributions / years_listed
            annual_yield = round(annual_distributions / current_price * 100, 2)
        elif total_distributions > 0:
            # 有分红但上市时间不足1年
            method = "累计NAV差值法(不足1年)"
        else:
            method = "无分红记录"

        return {
            "total_distributions": round(total_distributions, 4),
            "years_listed": round(years_listed, 1),
            "annual_yield": annual_yield,
            "method": method,
        }

    # ========================================================================
    # NAV折溢价估算
    # ========================================================================

    def _calc_p_nav(self, current_price: float, nav_data: Dict) -> Dict:
        """计算P/NAV及溢价率

        Returns:
            {
                "p_nav": float,          # P/NAV比率
                "premium_pct": float,    # 溢价率(%)，正=溢价，负=折价
                "unit_nav": float,       # 最新单位NAV
                "nav_date": str,         # NAV日期
                "assessment": str,       # 评估（深度折价/折价/合理/溢价/高溢价）
            }
        """
        unit_nav = nav_data.get("unit_nav", 0)

        if not unit_nav or unit_nav <= 0 or not current_price or current_price <= 0:
            return {
                "p_nav": None, "premium_pct": None, "unit_nav": unit_nav,
                "nav_date": nav_data.get("nav_date", ""),
                "assessment": "数据不足",
            }

        p_nav = round(current_price / unit_nav, 3)
        premium_pct = round((current_price - unit_nav) / unit_nav * 100, 2)

        if p_nav < 0.8:
            assessment = "深度折价"
        elif p_nav < 0.95:
            assessment = "折价"
        elif p_nav <= 1.05:
            assessment = "合理"
        elif p_nav <= 1.2:
            assessment = "溢价"
        else:
            assessment = "高溢价"

        return {
            "p_nav": p_nav,
            "premium_pct": premium_pct,
            "unit_nav": round(unit_nav, 4),
            "nav_date": nav_data.get("nav_date", ""),
            "assessment": assessment,
        }

    # ========================================================================
    # 杠杆率和负债结构分析
    # ========================================================================

    def _analyze_leverage(self, reit_info: Dict, asset_type: str) -> Dict:
        """分析REIT杠杆率和负债结构

        中国公募REITs杠杆率限制：
        - 借款总额不得超过净资产的140%（即资产负债率上限约58%）
        - 通常实际杠杆率在30-55%之间

        Returns:
            {
                "est_debt_ratio": float,      # 估算资产负债率(%)
                "leverage_level": str,         # 杠杆水平（低/中/高）
                "interest_burden": str,        # 利息负担评估
                "rate_risk": str,              # 利率风险评估
                "max_leverage": float,         # 监管杠杆上限(%)
                "headroom": float,             # 杠杆空间(%)
            }
        """
        est_debt_ratio = reit_info.get("est_debt_ratio", 45)
        profile = self.ASSET_PROFILES.get(asset_type, {})

        # 杠杆水平评估
        if est_debt_ratio <= 35:
            leverage_level = "低"
            interest_burden = "利息负担轻，财务弹性大"
        elif est_debt_ratio <= 45:
            leverage_level = "中"
            interest_burden = "利息负担适中，需关注利率变动"
        elif est_debt_ratio <= 55:
            leverage_level = "高"
            interest_burden = "利息负担较重，利率上行时侵蚀分红"
        else:
            leverage_level = "过高"
            interest_burden = "杠杆接近监管上限，财务风险大"

        # 利率风险评估
        rate_sensitivity = profile.get("rate_sensitivity", "中")
        if rate_sensitivity == "高" and est_debt_ratio > 45:
            rate_risk = "高风险：长久期+高杠杆，利率上行冲击最大"
        elif rate_sensitivity == "高" or est_debt_ratio > 45:
            rate_risk = "中高风险：利率上行时需密切关注"
        elif rate_sensitivity == "低" and est_debt_ratio <= 35:
            rate_risk = "低风险：短久期+低杠杆，利率变动影响有限"
        else:
            rate_risk = "中等风险：利率变动有一定影响"

        # 监管上限（净资产的140%，对应资产负债率约58.3%）
        max_leverage = 58.3
        headroom = round(max_leverage - est_debt_ratio, 1)

        return {
            "est_debt_ratio": est_debt_ratio,
            "leverage_level": leverage_level,
            "interest_burden": interest_burden,
            "rate_risk": rate_risk,
            "max_leverage": max_leverage,
            "headroom": headroom,
        }

    # ========================================================================
    # 利率敏感性分析
    # ========================================================================

    def _analyze_rate_sensitivity(self, asset_type: str, est_debt_ratio: float,
                                   dividend_yield: float, p_nav: float) -> Dict:
        """分析REIT对利率环境的敏感性

        逻辑：
        - 利率上行 → 融资成本上升 → 利润承压 → 分红减少
        - 利率上行 → 无风险收益率上升 → REIT相对吸引力下降 → 估值承压
        - 不同资产类型对利率的敏感度不同

        计算：假设LPR变动100bp(1%)，估算对分红和估值的影响

        Returns:
            {
                "rate_sensitivity": str,           # 整体敏感度（低/中/高）
                "yield_impact_bps": int,           # 100bp利率上升对分派率的影响(bp)
                "nav_impact_pct": float,           # 100bp利率上升对NAV的影响(%)
                "price_impact_pct": float,         # 100bp利率上升对市价的估算影响(%)
                "current_spread": float,           # 当前利差(分派率 - LPR)
                "spread_assessment": str,          # 利差评估
            }
        """
        profile = self.ASSET_PROFILES.get(asset_type, {})
        rate_sensitivity = profile.get("rate_sensitivity", "中")

        # LPR基准（5年期以上，2024年10月调整后为3.6%，2025年估算）
        current_lpr = 3.6

        # 敏感度系数（100bp利率上升对分派率的影响bp）
        sensitivity_coeff = {
            "低": 15,    # 分派率下降约15bp
            "中": 30,    # 分派率下降约30bp
            "中高": 45,  # 分派率下降约45bp
            "高": 60,    # 分派率下降约60bp
        }
        base_impact = sensitivity_coeff.get(rate_sensitivity, 30)

        # 杠杆放大效应
        leverage_multiplier = 1 + (est_debt_ratio - 40) / 100  # 40%为基准
        yield_impact = int(base_impact * leverage_multiplier)

        # NAV影响估算（利率上升100bp）
        nav_impact_map = {"低": -2.0, "中": -4.0, "中高": -6.0, "高": -8.0}
        nav_impact = nav_impact_map.get(rate_sensitivity, -4.0)
        nav_impact = round(nav_impact * leverage_multiplier, 1)

        # 市价影响估算（通常比NAV影响更大，因为市场情绪放大）
        price_impact = round(nav_impact * 1.3, 1)

        # 当前利差
        current_spread = round(dividend_yield - current_lpr, 2) if dividend_yield else 0

        if current_spread > 3:
            spread_assessment = "利差充裕，即使利率上行仍有吸引力"
        elif current_spread > 1.5:
            spread_assessment = "利差合理，但利率上行时吸引力下降"
        elif current_spread > 0:
            spread_assessment = "利差偏窄，利率上行可能导致估值承压"
        else:
            spread_assessment = "利差倒挂，REIT相对无风险资产缺乏吸引力"

        return {
            "rate_sensitivity": rate_sensitivity,
            "yield_impact_bps": yield_impact,
            "nav_impact_pct": nav_impact,
            "price_impact_pct": price_impact,
            "current_spread": current_spread,
            "spread_assessment": spread_assessment,
            "current_lpr": current_lpr,
        }

    # ========================================================================
    # 经营期限分析
    # ========================================================================

    def _analyze_concession(self, reit_info: Dict) -> Optional[Dict]:
        """分析有经营期限的REIT（主要是高速公路）

        Returns:
            {
                "total_years": int,         # 总经营年限
                "elapsed_years": float,     # 已过去年限
                "remaining_years": float,   # 剩余年限
                "remaining_pct": float,     # 剩余比例(%)
                "warning": str,             # 风险提示
            }
        """
        concession_years = reit_info.get("concession_years")
        concession_start = reit_info.get("concession_start")

        if not concession_years or not concession_start:
            return None

        elapsed = (datetime.now().year - concession_start) + datetime.now().month / 12
        remaining = max(0, concession_years - elapsed)
        remaining_pct = round(remaining / concession_years * 100, 1)

        if remaining_pct < 20:
            warning = "经营期限即将届满，资产残值快速衰减，不建议长期持有"
        elif remaining_pct < 40:
            warning = "进入经营后期，资产残值逐步下降，需关注分红可持续性"
        elif remaining_pct < 60:
            warning = "经营中期，资产价值相对稳定"
        else:
            warning = "经营早期，资产价值较高"

        return {
            "total_years": concession_years,
            "elapsed_years": round(elapsed, 1),
            "remaining_years": round(remaining, 1),
            "remaining_pct": remaining_pct,
            "warning": warning,
        }

    # ========================================================================
    # 综合评分（100分制）
    # ========================================================================

    def _calculate_score(self, data: Dict) -> Dict:
        """计算REIT综合评分（满分100分）

        维度：
        1. 分派率（25分）- 核心收益指标
        2. P/NAV估值（20分）- 安全边际
        3. 资产质量（20分）- 出租率 + 资产类型
        4. 财务健康（20分）- 杠杆率 + 利率风险
        5. 流动性（15分）- 日均成交额

        Returns:
            {
                "total": int,
                "breakdown": {
                    "distribution": int,   # 分派率得分
                    "valuation": int,      # 估值得分
                    "asset_quality": int,  # 资产质量得分
                    "financial": int,      # 财务健康得分
                    "liquidity": int,      # 流动性得分
                },
                "grade": str,              # 等级(A/B/C/D)
            }
        """
        breakdown = {}

        # --- 1. 分派率（25分）---
        dy = data.get("dividend_yield", 0)
        if dy >= 8:
            breakdown["distribution"] = 25
        elif dy >= 7:
            breakdown["distribution"] = 22
        elif dy >= 6:
            breakdown["distribution"] = 19
        elif dy >= 5:
            breakdown["distribution"] = 15
        elif dy >= 4:
            breakdown["distribution"] = 10
        elif dy >= 3:
            breakdown["distribution"] = 5
        else:
            breakdown["distribution"] = 0

        # --- 2. P/NAV估值（20分）---
        p_nav = data.get("p_nav", 999)
        if p_nav is not None and p_nav <= 0.80:
            breakdown["valuation"] = 20   # 深度折价
        elif p_nav is not None and p_nav <= 0.90:
            breakdown["valuation"] = 17
        elif p_nav is not None and p_nav <= 1.00:
            breakdown["valuation"] = 14
        elif p_nav is not None and p_nav <= 1.05:
            breakdown["valuation"] = 10
        elif p_nav is not None and p_nav <= 1.15:
            breakdown["valuation"] = 6
        elif p_nav is not None and p_nav <= 1.30:
            breakdown["valuation"] = 3
        else:
            breakdown["valuation"] = 0

        # --- 3. 资产质量（20分）---
        occupancy = data.get("occupancy_rate", 0)
        # 出租率基础分（12分）
        if occupancy >= 97:
            occ_score = 12
        elif occupancy >= 95:
            occ_score = 10
        elif occupancy >= 90:
            occ_score = 8
        elif occupancy >= 85:
            occ_score = 5
        elif occupancy >= 80:
            occ_score = 3
        else:
            occ_score = 0

        # 资产类型加分（8分）- 基于经济周期敏感性和成长性
        asset_type = data.get("asset_type", "")
        profile = self.ASSET_PROFILES.get(asset_type, {})
        econ_cycle = profile.get("economic_cycle", "中")
        growth = profile.get("growth_potential", "中")

        type_score = 4  # 基准
        if econ_cycle == "低":
            type_score += 2
        elif econ_cycle == "高":
            type_score -= 2
        if growth == "中高":
            type_score += 2
        elif growth == "低":
            type_score -= 1
        type_score = max(0, min(8, type_score))

        breakdown["asset_quality"] = occ_score + type_score

        # --- 4. 财务健康（20分）---
        debt_ratio = data.get("debt_ratio", 100)
        leverage = data.get("leverage", {})

        # 杠杆率得分（12分）
        if debt_ratio <= 30:
            debt_score = 12
        elif debt_ratio <= 35:
            debt_score = 10
        elif debt_ratio <= 40:
            debt_score = 8
        elif debt_ratio <= 45:
            debt_score = 6
        elif debt_ratio <= 50:
            debt_score = 4
        elif debt_ratio <= 55:
            debt_score = 2
        else:
            debt_score = 0

        # 利率风险得分（8分）
        rate_info = data.get("rate_sensitivity", {})
        rate_sens = rate_info.get("rate_sensitivity", "中")
        rate_scores = {"低": 8, "中": 6, "中高": 3, "高": 1}
        rate_score = rate_scores.get(rate_sens, 5)

        breakdown["financial"] = debt_score + rate_score

        # --- 5. 流动性（15分）---
        turnover = data.get("daily_turnover", 0)
        if turnover >= 500:
            breakdown["liquidity"] = 15
        elif turnover >= 300:
            breakdown["liquidity"] = 12
        elif turnover >= 200:
            breakdown["liquidity"] = 10
        elif turnover >= 100:
            breakdown["liquidity"] = 7
        elif turnover >= 50:
            breakdown["liquidity"] = 4
        else:
            breakdown["liquidity"] = 1

        total = sum(breakdown.values())

        # 等级
        if total >= 80:
            grade = "A"
        elif total >= 65:
            grade = "B"
        elif total >= 50:
            grade = "C"
        elif total >= 35:
            grade = "D"
        else:
            grade = "E"

        return {"total": total, "breakdown": breakdown, "grade": grade}

    # ========================================================================
    # 主入口
    # ========================================================================

    def get_all_reits(self, filters: Dict = None) -> List[Dict]:
        """获取所有REIT数据并应用筛选（机构级分析）"""
        if filters is None:
            filters = {}

        min_dividend_yield = filters.get("min_dividend_yield", 3)
        max_p_nav = filters.get("max_p_nav", 1.5)
        min_occupancy = filters.get("min_occupancy", 80)
        max_debt_ratio = filters.get("max_debt_ratio", 60)
        min_turnover = filters.get("min_turnover", 50)
        asset_type = filters.get("asset_type", "all")

        logger.info("开始获取REIT数据（实时行情+NAV+分析）")

        # 1. 批量获取实时行情
        realtime_data = self._fetch_batch_realtime()
        logger.info(f"实时行情获取成功: {len(realtime_data)}/{len(self.REIT_LIST)}")

        # 2. 批量获取NAV数据
        nav_data = self._fetch_batch_nav()
        logger.info(f"NAV数据获取成功: {len(nav_data)}/{len(self.REIT_LIST)}")

        results = []
        for reit_info in self.REIT_LIST:
            code = reit_info["code"]
            name = reit_info["name"]
            rtype = reit_info["type"]

            # 资产类型筛选
            if asset_type != "all" and rtype != asset_type:
                continue

            # 实时数据
            realtime = realtime_data.get(code)
            if not realtime:
                continue

            current_price = realtime["price"]

            # NAV数据
            nav = nav_data.get(code, {})

            # 计算P/NAV
            p_nav_info = self._calc_p_nav(current_price, nav)

            # 计算分派率
            dist_info = self._calc_distribution_yield(nav, current_price)
            dividend_yield = dist_info["annual_yield"]

            # 出租率和负债率（使用每只REIT的估计值）
            occupancy_rate = reit_info.get("est_occupancy", 90)
            debt_ratio = reit_info.get("est_debt_ratio", 45)

            # 日均成交额（万元）
            daily_turnover = realtime.get("amount", 0) / 10000

            # 筛选条件应用
            p_nav_val = p_nav_info.get("p_nav")
            if dividend_yield < min_dividend_yield:
                continue
            if p_nav_val is not None and p_nav_val > max_p_nav:
                continue
            if occupancy_rate < min_occupancy:
                continue
            if debt_ratio > max_debt_ratio:
                continue
            if daily_turnover < min_turnover:
                continue

            # 杠杆分析
            leverage_info = self._analyze_leverage(reit_info, rtype)

            # 利率敏感性分析
            rate_info = self._analyze_rate_sensitivity(
                rtype, debt_ratio, dividend_yield, p_nav_val
            )

            # 经营期限分析
            concession_info = self._analyze_concession(reit_info)

            # 资产类型配置
            profile = self.ASSET_PROFILES.get(rtype, {})

            # 综合评分
            score_data = {
                "dividend_yield": dividend_yield,
                "p_nav": p_nav_val,
                "occupancy_rate": occupancy_rate,
                "debt_ratio": debt_ratio,
                "daily_turnover": daily_turnover,
                "asset_type": rtype,
                "leverage": leverage_info,
                "rate_sensitivity": rate_info,
            }
            score_result = self._calculate_score(score_data)

            results.append({
                # 基本信息
                "code": code,
                "name": name,
                "asset_type": rtype,
                "underlying": reit_info.get("underlying", ""),
                "location": reit_info.get("location", ""),
                # 行情
                "price": current_price,
                "pre_close": realtime.get("pre_close", 0),
                "change_pct": realtime.get("change_pct", 0),
                "daily_turnover": round(daily_turnover, 2),
                "volume": realtime.get("volume", 0),
                # NAV
                "unit_nav": p_nav_info.get("unit_nav"),
                "p_nav": p_nav_info.get("p_nav"),
                "premium_pct": p_nav_info.get("premium_pct"),
                "nav_assessment": p_nav_info.get("assessment", ""),
                "nav_date": p_nav_info.get("nav_date", ""),
                # 分派率
                "dividend_yield": dividend_yield,
                "total_distributions": dist_info.get("total_distributions", 0),
                "distribution_method": dist_info.get("method", ""),
                "years_listed": dist_info.get("years_listed", 0),
                # 资产质量
                "occupancy_rate": occupancy_rate,
                "asset_description": profile.get("description", ""),
                # 财务
                "debt_ratio": debt_ratio,
                "leverage_level": leverage_info.get("leverage_level", ""),
                "interest_burden": leverage_info.get("interest_burden", ""),
                "leverage_headroom": leverage_info.get("headroom", 0),
                # 利率敏感性
                "rate_sensitivity": rate_info.get("rate_sensitivity", ""),
                "rate_yield_impact_bps": rate_info.get("yield_impact_bps", 0),
                "rate_price_impact_pct": rate_info.get("price_impact_pct", 0),
                "current_spread": rate_info.get("current_spread", 0),
                "spread_assessment": rate_info.get("spread_assessment", ""),
                # 经营期限
                "concession": concession_info,
                # 评分
                "score": score_result["total"],
                "score_breakdown": score_result["breakdown"],
                "score_grade": score_result["grade"],
                # 风险
                "risk_level": profile.get("risk_level", "中"),
                "risk_notes": self.RISK_NOTES.get(rtype, []),
            })

        # 按评分排序
        results.sort(key=lambda x: x["score"], reverse=True)
        logger.info(f"REIT筛选完成: {len(results)}只通过筛选")
        return results

    def get_market_overview(self, filters: Dict = None) -> Dict:
        """获取REIT市场概览"""
        reits = self.get_all_reits(filters)

        if not reits:
            return {
                "total": 0,
                "avg_yield": 0,
                "avg_p_nav": 0,
                "avg_occupancy": 0,
                "type_distribution": {},
                "rate_environment": {},
            }

        # 统计
        yields = [r["dividend_yield"] for r in reits if r["dividend_yield"] > 0]
        p_navs = [r["p_nav"] for r in reits if r["p_nav"] is not None]
        occupancies = [r["occupancy_rate"] for r in reits]

        # 资产类型分布
        type_dist = {}
        for r in reits:
            t = r["asset_type"]
            if t not in type_dist:
                type_dist[t] = {"count": 0, "avg_yield": 0, "reits": []}
            type_dist[t]["count"] += 1
            type_dist[t]["reits"].append(r["code"])

        for t in type_dist:
            type_reits = [r for r in reits if r["asset_type"] == t]
            t_yields = [r["dividend_yield"] for r in type_reits if r["dividend_yield"] > 0]
            type_dist[t]["avg_yield"] = round(sum(t_yields) / len(t_yields), 2) if t_yields else 0

        # 利率环境概览
        rate_overview = {
            "current_lpr_5y": 3.6,
            "description": "当前5年期LPR为3.6%，处于历史低位",
            "implication": "低利率环境利好REIT估值，但需关注利率拐点风险",
            "high_sensitivity_count": sum(1 for r in reits if r.get("rate_sensitivity") in ("高", "中高")),
        }

        return {
            "total": len(reits),
            "avg_yield": round(sum(yields) / len(yields), 2) if yields else 0,
            "avg_p_nav": round(sum(p_navs) / len(p_navs), 3) if p_navs else 0,
            "avg_occupancy": round(sum(occupancies) / len(occupancies), 1) if occupancies else 0,
            "type_distribution": type_dist,
            "rate_environment": rate_overview,
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }


# 单例
reit_service = REITService()
