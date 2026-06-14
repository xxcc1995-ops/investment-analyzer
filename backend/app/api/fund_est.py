"""LOF基金EST净值估算 - 校准值法（纯函数库）

API端点已迁移到 fund_arb.py，本文件仅保留配置和函数供 import。
"""

import logging
from typing import Dict, List, Optional

from app.api.fund_utils import (
    get_fund_nav_from_eastmoney,
    get_hkdcny_rate,
    get_sina_fund_code,
    get_sina_realtime,
    parse_underlying_price,
)
from app.core.utils import safe_float

logger = logging.getLogger(__name__)


# ==================== LOF基金配置 ====================
# 基金代码 -> 底层资产代码、仓位比例、校准值
# 校准值 = 基金官方净值 / (底层资产价格 x 汇率 x 仓位比例)
# 港股基金：校准值 = 基金官方净值 / (指数价格 x 港币汇率 x 仓位比例)
# 底层资产说明：gb_xxx = 美股ETF（美元），hf_xxx = 期货（点数），rt_hkxxx = 港股指数（点数）

LOF_FUND_CONFIG = {
    # === 美股QDII LOF ===
    "SZ161130": {"name": "纳斯达克100LOF", "underlying": "gb_qqq", "position": 0.95, "calibration": 0.001012},
    "SZ161125": {"name": "标普500LOF", "underlying": "gb_spy", "position": 0.95, "calibration": 0.000660},
    "SZ162415": {"name": "美国消费LOF", "underlying": "gb_xly", "position": 0.95, "calibration": 0.003913},
    "SZ161126": {"name": "标普医疗保健LOF", "underlying": "gb_xlv", "position": 0.95, "calibration": 0.001888},
    "SZ161128": {"name": "标普信息科技LOF", "underlying": "gb_xlk", "position": 0.95, "calibration": 0.005944},
    "SZ161127": {"name": "标普生物科技LOF", "underlying": "gb_xbi", "position": 0.95, "calibration": 0.002163},
    "SZ162411": {"name": "华宝油气LOF", "underlying": "gb_xop", "position": 0.95, "calibration": 0.000846},
    "SZ160416": {"name": "石油基金LOF", "underlying": "gb_uso", "position": 0.95, "calibration": 0.002474},
    "SZ162719": {"name": "石油LOF", "underlying": "gb_uso", "position": 0.95, "calibration": 0.003201},
    "SZ164906": {"name": "中概互联网LOF", "underlying": "gb_kweb", "position": 0.95, "calibration": 0.005742},
    "SH501300": {"name": "美元债LOF", "underlying": "gb_agg", "position": 0.95, "calibration": 0.001492},
    "SZ160140": {"name": "美国REIT精选LOF", "underlying": "gb_vnq", "position": 0.95, "calibration": 0.002249},
    "SZ164824": {"name": "印度基金LOF", "underlying": "gb_inda", "position": 0.95, "calibration": 0.004203},
    "SZ163208": {"name": "全球油气能源LOF", "underlying": "gb_xle", "position": 0.95, "calibration": 0.003575},
    "SH501018": {"name": "南方原油LOF", "underlying": "gb_uso", "position": 0.95, "calibration": 0.002159},
    "SZ160723": {"name": "嘉实原油LOF", "underlying": "gb_uso", "position": 0.95, "calibration": 0.002458},
    "SZ161129": {"name": "原油LOF易方达", "underlying": "gb_uso", "position": 0.95, "calibration": 0.002060},
    "SZ160216": {"name": "国泰商品LOF", "underlying": "gb_gsg", "position": 0.95, "calibration": 0.003553},
    "SZ161815": {"name": "抗通胀LOF", "underlying": "gb_tip", "position": 0.95, "calibration": 0.001585},
    "SZ160719": {"name": "嘉实黄金LOF", "underlying": "gb_gld", "position": 0.95, "calibration": 0.000787},
    "SZ161116": {"name": "黄金主题LOF", "underlying": "gb_gld", "position": 0.95, "calibration": 0.000654},
    "SZ164701": {"name": "黄金LOF", "underlying": "gb_gld", "position": 0.95, "calibration": 0.000690},
    "SZ165513": {"name": "中信保诚商品LOF", "underlying": "gb_djp", "position": 0.95, "calibration": 0.003499},
    "SH501225": {"name": "全球芯片LOF", "underlying": "gb_soxx", "position": 0.95, "calibration": 0.000969},
    "SZ160644": {"name": "港美互联网LOF", "underlying": "gb_kweb", "position": 0.95, "calibration": 0.012235},
    "SZ161226": {"name": "国投白银LOF", "underlying": "gb_slv", "position": 0.95, "calibration": 0.005081},
    # === 港股QDII LOF ===
    "SH501025": {"name": "香港银行LOF", "underlying": "rt_hkHSCEI", "position": 0.95, "calibration": 0.000245},
    "SZ161124": {"name": "港股小盘LOF", "underlying": "rt_hkHSCCI", "position": 0.95, "calibration": 0.000265},
    "SZ160717": {"name": "H股LOF", "underlying": "rt_hkHSCEI", "position": 0.95, "calibration": 0.000101},
    "SZ161831": {"name": "恒生国企LOF", "underlying": "rt_hkHSCEI", "position": 0.95, "calibration": 0.000102},
    "SH501302": {"name": "恒生指数基金LOF", "underlying": "rt_hkHSI", "position": 0.95, "calibration": 0.000054},
    "SZ160924": {"name": "恒生指数LOF", "underlying": "rt_hkHSI", "position": 0.95, "calibration": 0.000047},
    "SZ164705": {"name": "恒生LOF", "underlying": "rt_hkHSI", "position": 0.95, "calibration": 0.000053},
}


# ==================== 多标的基金配置 ====================
# 这些基金跟踪多个标的，配置已知的持仓标的和权重
# 配置说明：
#   - fund_code: 基金代码
#   - name: 基金名称
#   - holdings: 已知的持仓标的和权重（基于基金招募说明书和历史持仓）
#   - position: 仓位比例
#   - calibration: 校准值

MULTI_UNDERLYING_FUNDS = {
    "SH501312": {
        "name": "海外科技LOF",
        "fund_code_eastmoney": "501312",
        "position": 0.95,
        "calibration": 0.005036,
        "holdings": [
            # 基于基金招募说明书和历史持仓数据
            # 权重基于历史持仓比例估算
            {"code": "gb_arkk", "name": "ARK Innovation ETF", "weight": 25.0},
            {"code": "gb_arkg", "name": "ARK Genomic Revolution ETF", "weight": 20.0},
            {"code": "gb_arkw", "name": "ARK Next Generation Internet ETF", "weight": 20.0},
            {"code": "gb_arkq", "name": "ARK Autonomous Technology & Robotics ETF", "weight": 15.0},
            {"code": "gb_arkf", "name": "ARK Fintech Innovation ETF", "weight": 10.0},
            {"code": "gb_arkx", "name": "ARK Space Exploration ETF", "weight": 10.0},
        ],
    },
}

# 合法代码集合（用于标准化）
_VALID_FUND_CODES = set(LOF_FUND_CONFIG.keys()) | set(MULTI_UNDERLYING_FUNDS.keys())

# HKD/CNY 汇率 - 动态获取（从fund_utils）
# 旧的硬编码常量 _HKD_TO_CNY = 0.9 已废弃，改用 get_hkdcny_rate()
_HKD_TO_CNY = 0.9  # 仅作为fallback默认值


def _calc_multi_underlying_est_nav(
    fund_config: dict,
    underlying_data: Dict[str, List[str]],
    usdcny_rate: float,
    official_nav: float,
) -> Optional[Dict]:
    """计算多标的基金的EST净值

    使用配置的持仓数据，计算加权涨跌幅，然后估算净值。

    Args:
        fund_config: 基金配置
        underlying_data: 底层资产行情数据
        usdcny_rate: USD/CNY 汇率
        official_nav: 官方净值（T-1日）

    Returns:
        {
            'est_nav': float,           # 估算净值
            'underlying_change_pct': float,  # 加权涨跌幅
            'holdings_detail': list,    # 持仓详情
        }
        计算失败返回 None
    """
    try:
        # 获取配置的持仓数据
        holdings_config = fund_config.get("holdings", [])
        if not holdings_config:
            logger.warning(f"基金 {fund_config.get('name', '')} 无持仓配置")
            return None

        # 计算加权涨跌幅
        total_weight = 0
        weighted_change = 0
        holdings_detail = []

        for holding in holdings_config:
            sina_code = holding.get("code", "")
            stock_name = holding.get("name", "")
            weight = holding.get("weight", 0)

            if weight <= 0 or not sina_code:
                continue

            # 获取底层资产行情
            underlying_info = underlying_data.get(sina_code, [])
            if not underlying_info:
                logger.warning(f"未获取到 {sina_code} 的行情数据")
                continue

            parsed = parse_underlying_price(sina_code, underlying_info)
            if not parsed or parsed["price"] <= 0:
                continue

            change_pct = parsed["change_pct"]
            weighted_change += change_pct * weight
            total_weight += weight

            holdings_detail.append({
                "stock_code": sina_code,
                "stock_name": stock_name,
                "sina_code": sina_code,
                "weight": weight,
                "price": parsed["price"],
                "change_pct": change_pct,
            })

        if total_weight <= 0:
            logger.warning(f"基金 {fund_config.get('name', '')} 无有效持仓数据")
            return None

        # 计算加权涨跌幅
        avg_change_pct = weighted_change / total_weight

        # 使用官方净值和加权涨跌幅估算净值
        # EST净值 = 官方净值 × (1 + 加权涨跌幅% / 100)
        if official_nav > 0:
            est_nav = official_nav * (1 + avg_change_pct / 100)
        else:
            logger.warning(f"基金 {fund_config.get('name', '')} 无官方净值")
            return None

        return {
            "est_nav": est_nav,
            "underlying_change_pct": round(avg_change_pct, 2),
            "holdings_detail": holdings_detail,
            "total_weight": total_weight,
        }

    except Exception as e:
        logger.error(f"计算多标的基金净值失败: {e}")
        return None


def _calc_est_nav(
    underlying_code: str,
    underlying_price: float,
    usdcny_rate: float,
    position: float,
    calibration: float,
) -> float:
    """使用校准值法计算EST净值

    Args:
        underlying_code: 底层资产代码
        underlying_price: 底层资产当前价格
        usdcny_rate: USD/CNY 汇率
        position: 仓位比例
        calibration: 校准值

    Returns:
        估算净值
    """
    if underlying_code.startswith("gb_") or underlying_code.startswith("hf_"):
        return underlying_price * usdcny_rate * position * calibration
    else:
        # 港股资产 - 使用动态汇率
        hkdcny_rate = get_hkdcny_rate()
        return underlying_price * hkdcny_rate * position * calibration


def _process_single_fund(
    fund_code: str,
    config: dict,
    fund_data: dict,
    underlying_data: dict,
    usdcny_rate: float,
    is_multi_underlying: bool = False,
) -> Optional[dict]:
    """处理单只基金的EST净值计算

    Args:
        fund_code: 基金代码（带SH/SZ前缀）
        config: 基金配置
        fund_data: 新浪基金行情数据
        underlying_data: 新浪底层资产行情数据
        usdcny_rate: USD/CNY 汇率
        is_multi_underlying: 是否为多标的基金

    Returns:
        基金EST数据字典，处理失败返回 None
    """
    try:
        # 基金实时价格
        sina_fund_code = get_sina_fund_code(fund_code)
        fund_info = fund_data.get(sina_fund_code, [])
        if len(fund_info) < 10:
            return None

        fund_price = safe_float(fund_info[3], 0)
        fund_change_pct = safe_float(fund_info[32], 0) if len(fund_info) > 32 else 0
        # 使用配置中的名称，因为新浪API返回的名称可能是乱码
        fund_name = config["name"]

        if fund_price <= 0:
            return None

        # 获取基金净值（T-1日）
        fund_nav_code = fund_code[2:]  # 去掉SH/SZ前缀
        nav_info = get_fund_nav_from_eastmoney(fund_nav_code)
        official_nav = nav_info.get("nav", 0)

        # 多标的基金处理
        if is_multi_underlying:
            multi_result = _calc_multi_underlying_est_nav(
                config, underlying_data, usdcny_rate, official_nav
            )
            if multi_result:
                est_nav = multi_result["est_nav"]
                underlying_change_pct = multi_result["underlying_change_pct"]
                holdings_detail = multi_result["holdings_detail"]

                # 溢价率
                premium = (
                    round((fund_price - est_nav) / est_nav * 100, 2) if est_nav > 0 else 0
                )

                # 构建底层资产描述
                if len(holdings_detail) > 1:
                    underlying_code = "多标的加权"
                    underlying_price = 0
                else:
                    underlying_code = holdings_detail[0].get("sina_code", "")
                    underlying_price = holdings_detail[0].get("price", 0)

                return {
                    "fund_code": fund_code,
                    "fund_name": fund_name,
                    "fund_price": fund_price,
                    "fund_change_pct": round(fund_change_pct, 2),
                    "underlying_code": underlying_code,
                    "underlying_price": underlying_price,
                    "underlying_change_pct": underlying_change_pct,
                    "est_nav": round(est_nav, 4),
                    "premium": premium,
                    "official_nav": official_nav,
                    "official_nav_date": nav_info.get("nav_date", ""),
                    "position": config.get("position", 0.95),
                    "usdcny_rate": usdcny_rate,
                    "holdings_detail": holdings_detail,
                    "is_multi_underlying": True,
                }

        # 单标的基金处理（原有逻辑）
        underlying_code = config["underlying"]
        underlying_info = underlying_data.get(underlying_code, [])

        # 尝试备用底层资产
        if not underlying_info and "underlying_alt" in config:
            underlying_code = config["underlying_alt"]
            underlying_info = underlying_data.get(underlying_code, [])

        if not underlying_info:
            return None

        parsed = parse_underlying_price(underlying_code, underlying_info)
        if not parsed or parsed["price"] <= 0:
            return None

        underlying_price = parsed["price"]

        # 计算EST净值
        position = config["position"]
        calibration = config["calibration"]
        est_nav = _calc_est_nav(
            underlying_code, underlying_price, usdcny_rate, position, calibration
        )

        # 溢价率
        premium = (
            round((fund_price - est_nav) / est_nav * 100, 2) if est_nav > 0 else 0
        )

        return {
            "fund_code": fund_code,
            "fund_name": fund_name,
            "fund_price": fund_price,
            "fund_change_pct": round(fund_change_pct, 2),
            "underlying_code": underlying_code,
            "underlying_price": underlying_price,
            "underlying_change_pct": parsed["change_pct"],
            "est_nav": round(est_nav, 4),
            "premium": premium,
            "official_nav": official_nav,
            "official_nav_date": nav_info.get("nav_date", ""),
            "position": position,
            "usdcny_rate": usdcny_rate,
            "is_multi_underlying": False,
        }
    except Exception as e:
        logger.warning(f"处理基金 {fund_code} 失败: {e}")
        return None


# 注意：API端点已迁移到 fund_arb.py，本文件仅保留纯函数供 import
