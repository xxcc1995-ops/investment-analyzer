"""
组合管理服务 — 持仓管理、交易记录、收益跟踪、风险暴露

数据持久化：JSON 文件（与 decision_service 一致的模式）
实时价格：通过 MultiSourceQuoteService 获取
"""

import json
import os
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.models.portfolio import (
    Transaction, Position, PortfolioSummary,
    PerformancePoint, RiskExposure,
)

logger = logging.getLogger(__name__)

# ============================================================
# 数据路径
# ============================================================
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
PORTFOLIO_FILE = os.path.join(DATA_DIR, "portfolio.json")

# ============================================================
# 行业分类（简化版，覆盖常见行业）
# ============================================================
SECTOR_MAP = {
    # 金融
    "银行": "金融", "保险": "金融", "证券": "金融", "信托": "金融",
    "工行": "金融", "建行": "金融", "农行": "金融", "中行": "金融",
    "招行": "金融", "平安": "金融", "兴业": "金融", "民生": "金融",
    "浦发": "金融", "光大": "金融", "华夏": "金融", "中信": "金融",
    # 消费
    "茅台": "消费", "五粮液": "消费", "伊利": "消费", "海天": "消费",
    "美的": "消费", "格力": "消费", "海尔": "消费", "蒙牛": "消费",
    "白酒": "消费", "啤酒": "消费", "乳": "消费", "食品": "消费",
    "饮料": "消费", "调味": "消费", "家电": "消费", "厨卫": "消费",
    # 医药
    "医药": "医药", "药业": "医药", "生物": "医药", "制药": "医药",
    "医疗": "医药", "器械": "医药", "疫苗": "医药", "中药": "医药",
    "恒瑞": "医药", "迈瑞": "医药", "药明": "医药", "片仔癀": "医药",
    # 科技
    "科技": "科技", "电子": "科技", "半导体": "科技", "芯片": "科技",
    "软件": "科技", "信息": "科技", "计算": "科技", "通信": "科技",
    "宁德": "科技", "比亚迪": "科技", "隆基": "科技", "中芯": "科技",
    # 地产
    "地产": "地产", "置地": "地产", "万科": "地产", "保利": "地产",
    "碧桂园": "地产", "融创": "地产", "恒大": "地产",
    # 能源
    "石油": "能源", "石化": "能源", "煤炭": "能源", "电力": "能源",
    "天然气": "能源", "光伏": "能源", "风电": "能源", "新能源": "能源",
    "中石油": "能源", "中石化": "能源", "神华": "能源",
    # 制造
    "机械": "制造", "汽车": "制造", "钢铁": "制造", "化工": "制造",
    "建材": "制造", "水泥": "制造", "玻璃": "制造", "重工": "制造",
    # 互联网
    "腾讯": "互联网", "阿里": "互联网", "美团": "互联网", "京东": "互联网",
    "拼多多": "互联网", "百度": "互联网", "网易": "互联网", "小米": "互联网",
    "快手": "互联网", "抖音": "互联网", "bilibili": "互联网",
    # 交通运输
    "航空": "交通运输", "航运": "交通运输", "物流": "交通运输",
    "快递": "交通运输", "铁路": "交通运输", "港口": "交通运输",
}


def _guess_sector(name: str) -> str:
    """根据股票名称猜测行业"""
    for keyword, sector in SECTOR_MAP.items():
        if keyword in name:
            return sector
    return "其他"


# ============================================================
# 数据持久化
# ============================================================

def _load_data() -> dict:
    """加载组合数据"""
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"transactions": [], "cash": 0}


def _save_data(data: dict):
    """保存组合数据"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================
# 交易管理
# ============================================================

def add_transaction(
    code: str,
    name: str,
    txn_type: str,
    shares: float,
    price: float,
    fee: float = 0,
    market: str = "A",
    reason: str = "",
    decision_id: str = "",
) -> Transaction:
    """
    添加交易记录

    Args:
        code: 股票代码
        name: 股票名称
        txn_type: 交易类型 (buy/sell/dividend/split)
        shares: 交易股数（买入为正，卖出为负）
        price: 交易价格
        fee: 手续费
        market: 市场 (A/HK/US)
        reason: 交易理由
        decision_id: 关联决策ID

    Returns:
        Transaction: 创建的交易记录
    """
    txn_id = str(uuid.uuid4())[:8]
    amount = abs(shares) * price

    txn = Transaction(
        id=txn_id,
        code=code,
        name=name,
        market=market,
        type=txn_type,
        shares=shares,
        price=price,
        amount=amount,
        fee=fee,
        reason=reason,
        decision_id=decision_id,
    )

    data = _load_data()
    data["transactions"].append(txn.model_dump())

    # 更新现金余额
    if txn_type == "buy":
        data["cash"] -= (amount + fee)
    elif txn_type == "sell":
        data["cash"] += (amount - fee)
    elif txn_type == "dividend":
        data["cash"] += amount

    _save_data(data)
    logger.info(f"交易记录已添加: {txn_type} {code} {name} {shares}股 @ {price}")
    return txn


def get_transactions(code: str = None, limit: int = 100) -> list[Transaction]:
    """获取交易记录"""
    data = _load_data()
    txns = [Transaction(**t) for t in data.get("transactions", [])]

    if code:
        txns = [t for t in txns if t.code == code]

    # 按时间倒序
    txns.sort(key=lambda t: t.created_at, reverse=True)
    return txns[:limit]


def delete_transaction(txn_id: str) -> bool:
    """删除交易记录（同时回滚现金余额）"""
    data = _load_data()
    txns = data.get("transactions", [])

    target = None
    for t in txns:
        if t["id"] == txn_id:
            target = t
            break

    if not target:
        return False

    # 回滚现金
    if target["type"] == "buy":
        data["cash"] += (target["amount"] + target["fee"])
    elif target["type"] == "sell":
        data["cash"] -= (target["amount"] - target["fee"])
    elif target["type"] == "dividend":
        data["cash"] -= target["amount"]

    data["transactions"] = [t for t in txns if t["id"] != txn_id]
    _save_data(data)
    logger.info(f"交易记录已删除: {txn_id}")
    return True


# ============================================================
# 持仓计算
# ============================================================

def _calculate_positions(transactions: list[dict]) -> list[dict]:
    """从交易记录计算当前持仓"""
    holdings: dict[str, dict] = {}

    for txn in transactions:
        code = txn["code"]
        txn_type = txn["type"]
        shares = txn["shares"]
        price = txn["price"]
        amount = txn["amount"]

        if code not in holdings:
            holdings[code] = {
                "code": code,
                "name": txn.get("name", ""),
                "market": txn.get("market", "A"),
                "shares": 0,
                "total_cost": 0,
                "avg_cost": 0,
                "buy_date": txn.get("created_at", ""),
                "decision_id": txn.get("decision_id", ""),
            }

        h = holdings[code]

        if txn_type == "buy":
            old_cost = h["shares"] * h["avg_cost"]
            new_cost = shares * price
            h["shares"] += shares
            if h["shares"] > 0:
                h["avg_cost"] = (old_cost + new_cost) / h["shares"]
            h["total_cost"] += amount + txn.get("fee", 0)

        elif txn_type == "sell":
            h["shares"] -= abs(shares)
            h["total_cost"] -= abs(shares) * h["avg_cost"]  # 按成本价减少

        elif txn_type == "split":
            # 拆股：股数变化，成本不变
            h["shares"] = shares  # 新股数
            # avg_cost 在调用处已按比例调整

    # 过滤掉已清仓的
    result = []
    for h in holdings.values():
        if h["shares"] > 0.01:  # 允许微小浮点误差
            result.append(h)

    return result


def get_positions() -> list[Position]:
    """获取当前持仓（含实时价格）"""
    data = _load_data()
    txns = data.get("transactions", [])
    raw_positions = _calculate_positions(txns)

    positions = []
    total_value = 0

    # 尝试获取实时价格
    quote_map: dict[str, float] = {}
    try:
        from app.services.multi_source_quote import multi_source_service
        for p in raw_positions:
            code = p["code"]
            market = p.get("market", "A")
            quote = multi_source_service.get_quote(code, market)
            if quote and quote.price > 0:
                quote_map[code] = quote.price
    except Exception as e:
        logger.warning(f"获取实时行情失败，使用成本价: {e}")

    # 计算持仓
    for p in raw_positions:
        code = p["code"]
        current_price = quote_map.get(code, p["avg_cost"])
        market_value = p["shares"] * current_price
        unrealized_pnl = market_value - p["total_cost"]
        unrealized_pnl_pct = (unrealized_pnl / p["total_cost"] * 100) if p["total_cost"] > 0 else 0

        # 计算持有天数
        holding_days = 0
        if p.get("buy_date"):
            try:
                buy_dt = datetime.strptime(p["buy_date"][:10], "%Y-%m-%d")
                holding_days = (datetime.now() - buy_dt).days
            except (ValueError, TypeError):
                pass

        positions.append(Position(
            code=code,
            name=p["name"],
            market=p.get("market", "A"),
            shares=p["shares"],
            avg_cost=round(p["avg_cost"], 4),
            current_price=round(current_price, 2),
            market_value=round(market_value, 2),
            unrealized_pnl=round(unrealized_pnl, 2),
            unrealized_pnl_pct=round(unrealized_pnl_pct, 2),
            position_pct=0,  # 后面计算
            total_cost=round(p["total_cost"], 2),
            buy_date=p.get("buy_date", ""),
            holding_days=holding_days,
            decision_id=p.get("decision_id", ""),
        ))
        total_value += market_value

    # 计算仓位占比
    for pos in positions:
        if total_value > 0:
            pos.position_pct = round(pos.market_value / total_value * 100, 2)

    # 按市值排序
    positions.sort(key=lambda p: p.market_value, reverse=True)
    return positions


# ============================================================
# 组合概览
# ============================================================

def get_portfolio_summary() -> PortfolioSummary:
    """获取组合概览"""
    positions = get_positions()
    data = _load_data()
    cash = data.get("cash", 0)

    total_value = sum(p.market_value for p in positions)
    total_cost = sum(p.total_cost for p in positions)
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

    # 行业暴露
    sector_exposure: dict[str, float] = {}
    for p in positions:
        sector = _guess_sector(p.name)
        sector_exposure[sector] = sector_exposure.get(sector, 0) + p.market_value

    # 转为百分比
    if total_value > 0:
        sector_exposure = {k: round(v / total_value * 100, 2) for k, v in sector_exposure.items()}

    # 今日盈亏（用涨跌幅估算）
    today_pnl = 0
    try:
        from app.services.multi_source_quote import multi_source_service
        for p in positions:
            quote = multi_source_service.get_quote(p.code, p.market)
            if quote and quote.change_pct != 0:
                # 昨日市值 = 今日市值 / (1 + 涨跌幅%)
                prev_value = p.market_value / (1 + quote.change_pct / 100)
                today_pnl += p.market_value - prev_value
    except Exception:
        pass

    return PortfolioSummary(
        total_cost=round(total_cost, 2),
        total_value=round(total_value, 2),
        total_pnl=round(total_pnl, 2),
        total_pnl_pct=round(total_pnl_pct, 2),
        cash=round(cash, 2),
        position_count=len(positions),
        positions=positions,
        sector_exposure=sector_exposure,
        today_pnl=round(today_pnl, 2),
    )


# ============================================================
# 收益曲线
# ============================================================

def get_performance_history() -> list[PerformancePoint]:
    """
    基于交易记录推算收益曲线。

    简化方法：以每笔交易为时间点，计算当时的持仓市值。
    """
    data = _load_data()
    txns = data.get("transactions", [])
    if not txns:
        return []

    # 按时间排序
    txns_sorted = sorted(txns, key=lambda t: t.get("created_at", ""))

    # 逐步累加交易，计算每个时间点的总投入和持仓
    cumulative_cost = 0
    points = []

    for txn in txns_sorted:
        txn_type = txn["type"]
        amount = txn["amount"]
        fee = txn.get("fee", 0)

        if txn_type == "buy":
            cumulative_cost += amount + fee
        elif txn_type == "sell":
            cumulative_cost -= amount - fee
        elif txn_type == "dividend":
            cumulative_cost -= amount  # 分红减少成本

        date = txn.get("created_at", "")[:10]
        if date:
            points.append(PerformancePoint(
                date=date,
                value=round(cumulative_cost, 2),
                pnl=0,  # 需要当前市值才能算
                pnl_pct=0,
            ))

    # 用当前总市值修正最后一点
    if points:
        positions = get_positions()
        current_value = sum(p.market_value for p in positions)
        total_cost = sum(p.total_cost for p in positions)
        cash = data.get("cash", 0)

        points[-1].value = round(current_value + cash, 2)
        points[-1].pnl = round(current_value + cash - total_cost, 2)
        if total_cost > 0:
            points[-1].pnl_pct = round((current_value + cash - total_cost) / total_cost * 100, 2)

    return points


# ============================================================
# 风险暴露
# ============================================================

def get_risk_exposure() -> RiskExposure:
    """风险暴露分析"""
    positions = get_positions()
    total_value = sum(p.market_value for p in positions)

    if total_value == 0:
        return RiskExposure()

    # 行业暴露
    sector_map: dict[str, float] = {}
    for p in positions:
        sector = _guess_sector(p.name)
        sector_map[sector] = sector_map.get(sector, 0) + p.market_value

    sector_pct = {k: round(v / total_value * 100, 2) for k, v in sector_map.items()}

    # 前N大持仓
    top_holdings = [
        {
            "code": p.code,
            "name": p.name,
            "pct": round(p.market_value / total_value * 100, 2),
            "value": p.market_value,
        }
        for p in positions[:10]
    ]

    # 集中度警告
    warnings = []
    max_single = max((p.market_value / total_value * 100) for p in positions) if positions else 0
    max_sector = max(sector_pct.values()) if sector_pct else 0

    if max_single > 40:
        warnings.append(f"⚠️ 单一持仓占比 {max_single:.1f}%，高度集中（建议<30%）")
    elif max_single > 30:
        warnings.append(f"⚡ 单一持仓占比 {max_single:.1f}%，偏高（建议<30%）")

    if max_sector > 50:
        warnings.append(f"⚠️ 单一行业占比 {max_sector:.1f}%，高度集中（建议<40%）")
    elif max_sector > 40:
        warnings.append(f"⚡ 单一行业占比 {max_sector:.1f}%，偏高（建议<40%）")

    if len(positions) < 3:
        warnings.append(f"⚡ 持仓数量仅 {len(positions)} 只，分散度不足（建议5-15只）")
    elif len(positions) > 20:
        warnings.append(f"⚡ 持仓数量 {len(positions)} 只，可能过度分散（建议5-15只）")

    return RiskExposure(
        sector_exposure=sector_pct,
        top_holdings=top_holdings,
        concentration_warnings=warnings,
        max_single_pct=round(max_single, 2),
        max_sector_pct=round(max_sector, 2),
    )
