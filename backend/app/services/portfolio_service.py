"""
组合管理服务 — 持仓管理、交易记录、收益跟踪、风险暴露、VaR/CVaR/压力测试

数据持久化：SQLite（invest.db）
实时价格：通过 MultiSourceQuoteService 获取
"""

import json
import os
import uuid
import logging
import math
import numpy as np
from datetime import datetime, timedelta
from typing import Optional

from app.models.portfolio import (
    Transaction, Position, PortfolioSummary,
    PerformancePoint, RiskExposure,
    PortfolioRiskAnalysis, StressTestScenario,
)
from app.core.database import get_db

logger = logging.getLogger(__name__)

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
# 数据持久化（SQLite）
# ============================================================

def _get_cash() -> float:
    """获取现金余额"""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT value FROM portfolio_settings WHERE key='cash'"
        ).fetchone()
        return row["value"] if row else 0.0
    finally:
        conn.close()


def _set_cash(cash: float):
    """设置现金余额"""
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO portfolio_settings(key, value) VALUES(?, ?)",
            ("cash", cash),
        )
        conn.commit()
    finally:
        conn.close()


def _load_data() -> dict:
    """加载组合数据（兼容旧接口）"""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM transactions ORDER BY created_at"
        ).fetchall()
        txns = [dict(r) for r in rows]
        cash = _get_cash()
        return {"transactions": txns, "cash": cash}
    finally:
        conn.close()


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

    conn = get_db()
    try:
        # 插入交易记录
        conn.execute(
            """INSERT INTO transactions
               (id, code, name, market, type, shares, price, amount, fee, reason, decision_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (txn.id, txn.code, txn.name, txn.market, txn.type,
             txn.shares, txn.price, txn.amount, txn.fee,
             txn.reason, txn.decision_id, txn.created_at),
        )

        # 更新现金余额
        cash = _get_cash()
        if txn_type == "buy":
            cash -= (amount + fee)
        elif txn_type == "sell":
            cash += (amount - fee)
        elif txn_type == "dividend":
            cash += amount
        conn.execute(
            "INSERT OR REPLACE INTO portfolio_settings(key, value) VALUES(?, ?)",
            ("cash", cash),
        )

        conn.commit()
    finally:
        conn.close()

    logger.info(f"交易记录已添加: {txn_type} {code} {name} {shares}股 @ {price}")
    return txn


def get_transactions(code: str = None, limit: int = 100) -> list[Transaction]:
    """获取交易记录"""
    conn = get_db()
    try:
        if code:
            rows = conn.execute(
                "SELECT * FROM transactions WHERE code=? ORDER BY created_at DESC LIMIT ?",
                (code, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM transactions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [Transaction(**dict(r)) for r in rows]
    finally:
        conn.close()


def delete_transaction(txn_id: str) -> bool:
    """删除交易记录（同时回滚现金余额）"""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM transactions WHERE id=?", (txn_id,)
        ).fetchone()
        if not row:
            return False

        target = dict(row)

        # 回滚现金
        cash = _get_cash()
        if target["type"] == "buy":
            cash += (target["amount"] + target["fee"])
        elif target["type"] == "sell":
            cash -= (target["amount"] - target["fee"])
        elif target["type"] == "dividend":
            cash -= target["amount"]

        conn.execute("DELETE FROM transactions WHERE id=?", (txn_id,))
        conn.execute(
            "INSERT OR REPLACE INTO portfolio_settings(key, value) VALUES(?, ?)",
            ("cash", cash),
        )
        conn.commit()
        logger.info(f"交易记录已删除: {txn_id}")
        return True
    finally:
        conn.close()


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


# ============================================================
# 组合级风险分析（VaR / CVaR / 压力测试）
# ============================================================

def _get_historical_returns(code: str, market: str = "A", days: int = 250) -> list[float]:
    """
    获取个股历史日收益率序列（用于VaR计算）。
    优先使用 AKShare 获取日线数据，失败时返回空列表。
    """
    try:
        import akshare as ak
        # A股日线
        if market == "A":
            # akshare 需要纯数字代码
            pure_code = code.replace(".", "").strip()
            df = ak.stock_zh_a_hist(
                symbol=pure_code, period="daily",
                start_date=(datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d"),
                end_date=datetime.now().strftime("%Y%m%d"),
                adjust="qfq",
            )
            if df is not None and len(df) > 5:
                closes = df["收盘"].tolist()
                returns = []
                for i in range(1, len(closes)):
                    if closes[i - 1] > 0:
                        returns.append((closes[i] - closes[i - 1]) / closes[i - 1])
                return returns[-days:]
        # 港股
        elif market == "HK":
            df = ak.stock_hk_hist(
                symbol=code, period="daily",
                start_date=(datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d"),
                end_date=datetime.now().strftime("%Y%m%d"),
                adjust="qfq",
            )
            if df is not None and len(df) > 5:
                closes = df["收盘"].tolist()
                returns = []
                for i in range(1, len(closes)):
                    if closes[i - 1] > 0:
                        returns.append((closes[i] - closes[i - 1]) / closes[i - 1])
                return returns[-days:]
    except Exception as e:
        logger.warning(f"获取 {code} 历史收益率失败: {e}")
    return []


def calculate_portfolio_var(
    positions: list[Position],
    confidence: float = 0.95,
    days: int = 250,
) -> dict:
    """
    组合 VaR（历史模拟法）。

    步骤：
    1. 获取每只持仓的历史日收益率
    2. 按市值加权得到组合日收益率序列
    3. 取分位数作为 VaR

    Returns:
        {"var_pct": float, "var_amount": float, "confidence": float, "data_days": int}
    """
    if not positions:
        return {"var_pct": 0, "var_amount": 0, "confidence": confidence, "data_days": 0}

    total_value = sum(p.market_value for p in positions)
    if total_value <= 0:
        return {"var_pct": 0, "var_amount": 0, "confidence": confidence, "data_days": 0}

    # 收集各持仓收益率
    all_returns = []
    weights = []
    min_len = float("inf")

    for p in positions:
        rets = _get_historical_returns(p.code, p.market, days)
        if len(rets) >= 20:  # 至少20个交易日数据
            all_returns.append(rets)
            weights.append(p.market_value / total_value)
            min_len = min(min_len, len(rets))

    if not all_returns or min_len < 20:
        return {"var_pct": 0, "var_amount": 0, "confidence": confidence, "data_days": 0}

    # 对齐长度
    all_returns = [r[-int(min_len):] for r in all_returns]

    # 加权组合收益率
    portfolio_returns = []
    for i in range(int(min_len)):
        weighted = sum(w * r[i] for w, r in zip(weights, all_returns))
        portfolio_returns.append(weighted)

    arr = np.array(portfolio_returns)
    var_pct = float(np.percentile(arr, (1 - confidence) * 100))
    var_amount = abs(var_pct) * total_value

    return {
        "var_pct": round(var_pct * 100, 4),
        "var_amount": round(var_amount, 2),
        "confidence": confidence,
        "data_days": int(min_len),
    }


def calculate_portfolio_cvar(
    positions: list[Position],
    confidence: float = 0.95,
    days: int = 250,
) -> dict:
    """
    组合 CVaR / Expected Shortfall（历史模拟法）。
    CVaR = VaR 以下所有损失的均值。

    Returns:
        {"cvar_pct": float, "cvar_amount": float, "confidence": float}
    """
    if not positions:
        return {"cvar_pct": 0, "cvar_amount": 0, "confidence": confidence}

    total_value = sum(p.market_value for p in positions)
    if total_value <= 0:
        return {"cvar_pct": 0, "cvar_amount": 0, "confidence": confidence}

    all_returns = []
    weights = []
    min_len = float("inf")

    for p in positions:
        rets = _get_historical_returns(p.code, p.market, days)
        if len(rets) >= 20:
            all_returns.append(rets)
            weights.append(p.market_value / total_value)
            min_len = min(min_len, len(rets))

    if not all_returns or min_len < 20:
        return {"cvar_pct": 0, "cvar_amount": 0, "confidence": confidence}

    all_returns = [r[-int(min_len):] for r in all_returns]
    portfolio_returns = []
    for i in range(int(min_len)):
        weighted = sum(w * r[i] for w, r in zip(weights, all_returns))
        portfolio_returns.append(weighted)

    arr = np.array(portfolio_returns)
    var_threshold = np.percentile(arr, (1 - confidence) * 100)
    tail_losses = arr[arr <= var_threshold]

    if len(tail_losses) == 0:
        return {"cvar_pct": 0, "cvar_amount": 0, "confidence": confidence}

    cvar_pct = float(np.mean(tail_losses))
    cvar_amount = abs(cvar_pct) * total_value

    return {
        "cvar_pct": round(cvar_pct * 100, 4),
        "cvar_amount": round(cvar_amount, 2),
        "confidence": confidence,
    }


def calculate_portfolio_stress_test(
    positions: list[Position],
    scenarios: list[dict] = None,
) -> list[StressTestScenario]:
    """
    组合压力测试。

    默认场景：
    - 市场暴跌 10% / 20% / 30%
    - 利率上升 100bp / 200bp

    每个持仓按行业对利率敏感度做差异化冲击。
    """
    if not positions:
        return []

    if scenarios is None:
        scenarios = [
            {"name": "市场暴跌10%", "type": "market", "shock": -0.10},
            {"name": "市场暴跌20%", "type": "market", "shock": -0.20},
            {"name": "市场暴跌30%", "type": "market", "shock": -0.30},
            {"name": "利率上升100bp", "type": "rate", "shock": 0.01},
            {"name": "利率上升200bp", "type": "rate", "shock": 0.02},
        ]

    total_value = sum(p.market_value for p in positions)
    if total_value <= 0:
        return []

    # 行业对利率敏感度（利率上升时的跌幅系数）
    RATE_SENSITIVITY = {
        "金融": -0.3,      # 银行受益于息差扩大，保险受益于投资收益
        "地产": -2.5,      # 高杠杆，利率敏感
        "消费": -0.8,
        "医药": -0.5,
        "科技": -1.2,      # 成长股对利率敏感
        "能源": -0.4,
        "制造": -0.7,
        "互联网": -1.0,
        "交通运输": -0.6,
        "其他": -0.8,
    }

    results = []
    for scenario in scenarios:
        scenario_type = scenario["type"]
        shock = scenario["shock"]
        scenario_name = scenario["name"]

        total_loss = 0.0
        position_impacts = []

        for p in positions:
            if scenario_type == "market":
                # 市场冲击：所有持仓等比例下跌
                loss = p.market_value * shock
            elif scenario_type == "rate":
                # 利率冲击：按行业敏感度差异化
                sector = _guess_sector(p.name)
                sensitivity = RATE_SENSITIVITY.get(sector, -0.8)
                # shock 是利率变动（正数=加息），敏感度是负数
                pct_change = sensitivity * shock  # 加息 -> 负收益
                loss = p.market_value * pct_change
            else:
                loss = 0

            total_loss += loss
            position_impacts.append({
                "code": p.code,
                "name": p.name,
                "loss": round(loss, 2),
                "loss_pct": round(loss / p.market_value * 100, 2) if p.market_value > 0 else 0,
            })

        results.append(StressTestScenario(
            name=scenario_name,
            type=scenario_type,
            shock=shock,
            total_loss=round(total_loss, 2),
            total_loss_pct=round(total_loss / total_value * 100, 2) if total_value > 0 else 0,
            portfolio_after=round(total_value + total_loss, 2),
            position_impacts=sorted(position_impacts, key=lambda x: x["loss"]),
        ))

    return results


def get_portfolio_risk_summary() -> PortfolioRiskAnalysis:
    """
    综合风险摘要：VaR / CVaR / 最大回撤 / 波动率 / 集中度 / 压力测试。
    """
    positions = get_positions()

    if not positions:
        return PortfolioRiskAnalysis(
            has_data=False,
            message="暂无持仓，无法进行风险分析",
        )

    total_value = sum(p.market_value for p in positions)

    # 获取组合历史收益率用于波动率和最大回撤
    all_returns = []
    weights = []
    min_len = float("inf")

    for p in positions:
        rets = _get_historical_returns(p.code, p.market, 250)
        if len(rets) >= 20:
            all_returns.append(rets)
            weights.append(p.market_value / total_value)
            min_len = min(min_len, len(rets))

    # 默认值
    volatility_annual = 0.0
    max_drawdown = 0.0
    sharpe_ratio = 0.0
    data_days = 0

    if all_returns and min_len >= 20:
        all_returns = [r[-int(min_len):] for r in all_returns]
        portfolio_returns = []
        for i in range(int(min_len)):
            weighted = sum(w * r[i] for w, r in zip(weights, all_returns))
            portfolio_returns.append(weighted)

        arr = np.array(portfolio_returns)
        volatility_daily = float(np.std(arr))
        volatility_annual = volatility_daily * math.sqrt(252) * 100  # 年化波动率(%)

        # 最大回撤
        cumulative = np.cumprod(1 + arr)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / running_max
        max_drawdown = float(np.min(drawdowns)) * 100

        # Sharpe (假设无风险利率2%)
        annual_return = float(np.mean(arr)) * 252
        if volatility_annual > 0:
            sharpe_ratio = (annual_return - 0.02) / (volatility_annual / 100)

        data_days = int(min_len)

    # VaR / CVaR
    var_95 = calculate_portfolio_var(positions, 0.95)
    var_99 = calculate_portfolio_var(positions, 0.99)
    cvar_95 = calculate_portfolio_cvar(positions, 0.95)

    # 集中度
    hhi = sum((p.market_value / total_value) ** 2 for p in positions) if total_value > 0 else 0
    top3_pct = sum(
        p.market_value / total_value * 100
        for p in sorted(positions, key=lambda x: x.market_value, reverse=True)[:3]
    ) if total_value > 0 else 0

    # 压力测试
    stress_results = calculate_portfolio_stress_test(positions)

    return PortfolioRiskAnalysis(
        has_data=True,
        total_value=round(total_value, 2),
        position_count=len(positions),
        var_95=var_95,
        var_99=var_99,
        cvar_95=cvar_95,
        volatility_annual=round(volatility_annual, 2),
        max_drawdown=round(max_drawdown, 2),
        sharpe_ratio=round(sharpe_ratio, 3),
        concentration_hhi=round(hhi, 4),
        top3_pct=round(top3_pct, 2),
        stress_test=stress_results,
        data_days=data_days,
    )
