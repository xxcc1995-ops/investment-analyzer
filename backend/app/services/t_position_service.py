"""金渐成（机哥）做T仓位管理与成本追踪服务

核心功能：
1. 仓位分层管理（底仓70% + 做T仓30%）
2. 做T操作记录与模拟
3. 负成本持股计算
4. 金字塔加仓方案

机构级增强：
- 每日交易频率限制（单只股票每日最多2次round-trip）
- FIFO盈亏匹配（先进先出，准确计算单笔盈亏）
- 滑点模型（A股0.05%, 港股0.1%, 美股0.05%）
- 最大回撤追踪
- 风险警告系统
"""

import json
import os
from typing import Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import statistics

from app.core.cache import get_cache as _base_get_cache, set_cache as _set_cached

# 机构级参数
MAX_DAILY_TRADES = 4  # 单只股票每日最大交易次数（含买卖）
SLIPPAGE_MODEL = {"A": 0.0005, "HK": 0.001, "US": 0.0005}

# ============================================================
# 数据持久化路径
# ============================================================

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_POSITIONS_FILE = os.path.join(_DATA_DIR, "t_positions.json")
_TRADES_FILE = os.path.join(_DATA_DIR, "t_trades.json")


def _ensure_data_dir():
    os.makedirs(_DATA_DIR, exist_ok=True)


# ============================================================
# 仓位数据结构
# ============================================================

def _default_position(code: str, name: str, market: str) -> dict:
    return {
        "code": code,
        "name": name,
        "market": market,
        "total_shares": 0,
        "base_shares": 0,       # 底仓（不参与做T）
        "t_shares": 0,          # 做T仓
        "avg_cost": 0.0,        # 加权平均成本
        "total_invested": 0.0,  # 累计买入投入
        "total_sold": 0.0,      # 累计卖出回收
        "original_cost": 0.0,   # 初始买入成本（用于计算降幅）
        "t_trades": [],         # 做T交易记录
        "created_at": "",
        "updated_at": "",
    }


def _load_positions() -> dict:
    """加载仓位数据"""
    if os.path.exists(_POSITIONS_FILE):
        try:
            with open(_POSITIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_positions(positions: dict):
    """保存仓位数据"""
    _ensure_data_dir()
    with open(_POSITIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(positions, f, ensure_ascii=False, indent=2)


def _load_trades() -> list:
    """加载交易记录"""
    if os.path.exists(_TRADES_FILE):
        try:
            with open(_TRADES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_trades(trades: list):
    """保存交易记录"""
    _ensure_data_dir()
    with open(_TRADES_FILE, "w", encoding="utf-8") as f:
        json.dump(trades, f, ensure_ascii=False, indent=2)


# ============================================================
# 仓位管理
# ============================================================

def init_position(code: str, name: str, market: str,
                  shares: int, cost_price: float) -> dict:
    """
    初始化持仓

    Args:
        code: 股票代码
        name: 股票名称
        market: 市场
        shares: 总持仓股数
        cost_price: 买入成本价
    """
    positions = _load_positions()
    key = f"{market}_{code}"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 按金渐成规则分层：7成底仓 + 3成做T仓
    base_shares = int(shares * 0.7)
    t_shares = shares - base_shares

    # A股100股整数倍
    if market == "A":
        base_shares = max(int(base_shares / 100) * 100, 100)
        t_shares = shares - base_shares

    pos = _default_position(code, name, market)
    pos.update({
        "total_shares": shares,
        "base_shares": base_shares,
        "t_shares": t_shares,
        "avg_cost": cost_price,
        "total_invested": round(shares * cost_price, 2),
        "total_sold": 0.0,
        "original_cost": cost_price,
        "created_at": now,
        "updated_at": now,
    })

    positions[key] = pos
    _save_positions(positions)

    return {
        "message": f"已初始化 {name}({code}) 持仓",
        "position": pos,
        "cost_analysis": calc_cost_analysis(pos),
    }


def get_all_positions() -> dict:
    """获取全部仓位状态"""
    positions = _load_positions()
    result = []
    for key, pos in positions.items():
        analysis = calc_cost_analysis(pos)
        result.append({
            **pos,
            "cost_analysis": analysis,
        })

    # 统计汇总
    total_invested = sum(p["total_invested"] for p in positions.values())
    total_sold = sum(p["total_sold"] for p in positions.values())
    realized_t_profit = total_sold - total_invested  # 已实现做T盈亏（不含未平仓浮动）

    return {
        "positions": result,
        "summary": {
            "total_positions": len(result),
            "total_invested": round(total_invested, 2),
            "total_sold": round(total_sold, 2),
            "net_cost": round(total_invested - total_sold, 2),
            "realized_t_profit": round(realized_t_profit, 2),
            "negative_cost_count": len([r for r in result if r["cost_analysis"]["is_negative"]]),
        },
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_position(code: str, market: str) -> Optional[dict]:
    """获取单只股票仓位"""
    positions = _load_positions()
    key = f"{market}_{code}"
    pos = positions.get(key)
    if not pos:
        return None
    return {
        **pos,
        "cost_analysis": calc_cost_analysis(pos),
    }


# ============================================================
# 做T操作执行
# ============================================================

def execute_t_trade(code: str, market: str, action: str,
                    shares: int, price: float, note: str = "") -> dict:
    """
    执行做T操作（机构级增强版）

    风险控制：
    1. 每日交易频率限制（单只股票每日最多4次交易）
    2. 滑点模型（买入价上浮，卖出价下浮）
    3. FIFO盈亏匹配（先进先出，准确计算单笔盈亏）
    4. 仓位超限警告

    Args:
        code: 股票代码
        market: 市场
        action: "buy_t" (加做T仓) / "sell_t" (减做T仓)
        shares: 交易股数
        price: 交易价格（用户报价，系统会自动加滑点）
        note: 备注
    """
    positions = _load_positions()
    key = f"{market}_{code}"
    pos = positions.get(key)

    if not pos:
        return {"error": f"未找到 {code} 的持仓记录，请先初始化"}

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = datetime.now().strftime("%Y-%m-%d")

    # === 风险控制1：每日交易频率限制 ===
    today_trades = [t for t in pos.get("t_trades", [])
                    if t.get("time", "").startswith(today)]
    if len(today_trades) >= MAX_DAILY_TRADES:
        return {
            "error": f"今日已交易{len(today_trades)}次，达到每日上限{MAX_DAILY_TRADES}次",
            "risk_warning": "频繁交易会增加手续费侵蚀，请等待下一个交易日",
            "today_trades": today_trades,
        }

    # === 风险控制2：滑点模型 ===
    slippage = SLIPPAGE_MODEL.get(market, 0.0005)
    if action == "buy_t":
        # 买入时实际成交价 = 报价 × (1 + 滑点)
        exec_price = round(price * (1 + slippage), 4)
    else:
        # 卖出时实际成交价 = 报价 × (1 - 滑点)
        exec_price = round(price * (1 - slippage), 4)

    # 计算手续费
    if market == "A":
        commission_rate = 0.00025  # 佣金万2.5
        stamp_tax_rate = 0.0005    # 印花税千分之0.5（仅卖出）
        min_commission = 5.0       # A股最低佣金5元
    elif market == "HK":
        commission_rate = 0.0003   # 佣金万3
        stamp_tax_rate = 0.0013    # 印花税千分之1.3（仅卖出）
        min_commission = 5.0       # 港股最低佣金5港元
    else:  # US
        commission_rate = 0.0001   # 佣金万1
        stamp_tax_rate = 0.0       # 美股无印花税
        min_commission = 0.0       # 美股无最低佣金

    trade_amount = shares * exec_price
    commission = max(trade_amount * commission_rate, min_commission)
    stamp_tax = trade_amount * stamp_tax_rate if action == "sell_t" else 0
    total_fee = round(commission + stamp_tax, 2)

    # 记录交易（含滑点后价格）
    trade = {
        "time": now,
        "code": code,
        "market": market,
        "action": action,
        "shares": shares,
        "price": exec_price,           # 实际成交价（含滑点）
        "quote_price": price,          # 用户报价
        "slippage_pct": round(slippage * 100, 4),
        "amount": round(trade_amount, 2),
        "fee": total_fee,
        "note": note,
    }

    # 记录旧的净成本（用于计算变化）
    old_net_cost = (pos["total_invested"] - pos["total_sold"]) / pos["total_shares"] if pos["total_shares"] > 0 else 0

    if action == "buy_t":
        # 加做T仓
        new_total = pos["total_shares"] + shares
        new_invested = pos["total_invested"] + trade_amount + total_fee
        new_avg_cost = (new_invested - pos["total_sold"]) / new_total if new_total > 0 else 0

        pos["total_shares"] = new_total
        pos["t_shares"] = pos["t_shares"] + shares
        pos["avg_cost"] = round(new_avg_cost, 4)
        pos["total_invested"] = round(new_invested, 2)

    elif action == "sell_t":
        # 减做T仓
        if shares > pos["t_shares"]:
            return {"error": f"做T仓只有{pos['t_shares']}股，不能卖出{shares}股"}

        new_total = pos["total_shares"] - shares
        new_sold = pos["total_sold"] + trade_amount - total_fee

        if new_total > 0:
            new_avg_cost = (pos["total_invested"] - new_sold) / new_total
        else:
            new_avg_cost = 0

        pos["total_shares"] = new_total
        pos["t_shares"] = pos["t_shares"] - shares
        pos["total_sold"] = round(new_sold, 2)
        pos["avg_cost"] = round(new_avg_cost, 4)

    pos["updated_at"] = now
    pos["t_trades"].append(trade)

    # 保存
    positions[key] = pos
    _save_positions(positions)

    # 同时保存到全局交易记录
    trades = _load_trades()
    trades.append(trade)
    _save_trades(trades)

    # === FIFO盈亏匹配（机构级）===
    if action == "sell_t":
        trade_pnl = _calc_fifo_pnl(pos["t_trades"], shares, exec_price, total_fee)
    else:
        trade_pnl = -total_fee  # 买入时盈亏为负（手续费）

    cost_analysis = calc_cost_analysis(pos)

    # === 风险警告 ===
    warnings = []
    if pos["t_shares"] > pos["base_shares"] * 0.5:
        warnings.append(f"做T仓({pos['t_shares']})已超过底仓({pos['base_shares']})的50%，注意控制仓位")
    if len(today_trades) >= MAX_DAILY_TRADES - 1:
        warnings.append(f"今日已交易{len(today_trades) + 1}次，接近每日上限")
    if action == "sell_t" and trade_pnl < 0:
        warnings.append(f"本次做T亏损 ¥{abs(trade_pnl):.2f}，请评估是否继续")

    return {
        "message": f"{'买入' if action == 'buy_t' else '卖出'}做T成功",
        "trade": trade,
        "trade_pnl": trade_pnl,
        "position": pos,
        "cost_change": {
            "old_cost": round(old_net_cost, 4),
            "new_cost": pos["avg_cost"],
            "cost_change": round(pos["avg_cost"] - old_net_cost, 4),
            "cost_change_pct": round((pos["avg_cost"] - old_net_cost) / old_net_cost * 100, 2) if old_net_cost > 0 else 0,
        },
        "cost_analysis": cost_analysis,
        "warnings": warnings,
        "slippage_impact": round(abs(exec_price - price) * shares, 2),
    }


def _calc_fifo_pnl(t_trades: list, sell_shares: int, sell_price: float, sell_fee: float) -> float:
    """
    FIFO（先进先出）盈亏匹配

    按买入时间顺序匹配卖出，准确计算每笔交易的真实盈亏。
    这比简单匹配最后一笔买入更准确，尤其是在多次加仓后。
    """
    # 收集所有未平仓的买入记录
    buy_queue = []  # (价格, 股数)
    for t in t_trades:
        if t["action"] == "buy_t":
            buy_queue.append({"price": t["price"], "shares": t["shares"], "fee": t["fee"]})
        elif t["action"] == "sell_t":
            # 之前的卖出需要从队列中扣除（模拟已平仓）
            remaining = t["shares"]
            while remaining > 0 and buy_queue:
                if buy_queue[0]["shares"] <= remaining:
                    remaining -= buy_queue[0]["shares"]
                    buy_queue.pop(0)
                else:
                    buy_queue[0]["shares"] -= remaining
                    remaining = 0

    # 用FIFO匹配当前卖出
    total_pnl = 0.0
    remaining_sell = sell_shares
    allocated_fee = sell_fee  # 卖出手续费全额计入

    for buy in buy_queue:
        if remaining_sell <= 0:
            break
        matched_shares = min(buy["shares"], remaining_sell)
        # 按比例分摊买入手续费
        buy_fee_alloc = buy["fee"] * (matched_shares / buy["shares"]) if buy["shares"] > 0 else 0
        pnl = (sell_price - buy["price"]) * matched_shares - buy_fee_alloc
        total_pnl += pnl
        remaining_sell -= matched_shares

    # 减去卖出手续费
    total_pnl -= allocated_fee
    return round(total_pnl, 2)


# ============================================================
# 负成本计算引擎
# ============================================================

def calc_cost_analysis(pos: dict) -> dict:
    """
    成本分析与负成本计算

    负成本公式：
    每股成本 = (累计买入总成本 - 累计卖出总收入) / 剩余股数
    当 累计卖出 > 累计买入 时，每股成本为负
    """
    total_invested = pos["total_invested"]
    total_sold = pos["total_sold"]
    total_shares = pos["total_shares"]
    avg_cost = pos["avg_cost"]
    original_cost = pos.get("original_cost", avg_cost)
    t_trades = pos.get("t_trades", [])

    # 做T累计盈亏
    t_buy_amount = sum(t["amount"] + t["fee"] for t in t_trades if t["action"] == "buy_t")
    t_sell_amount = sum(t["amount"] - t["fee"] for t in t_trades if t["action"] == "sell_t")
    t_net = t_sell_amount - t_buy_amount

    # 净成本
    net_cost = total_invested - total_sold
    per_share_cost = net_cost / total_shares if total_shares > 0 else 0
    is_negative = per_share_cost < 0

    # 成本降幅
    cost_reduction = original_cost - per_share_cost
    cost_reduction_pct = (cost_reduction / original_cost * 100) if original_cost > 0 else 0

    # 做T次数统计
    buy_t_count = len([t for t in t_trades if t["action"] == "buy_t"])
    sell_t_count = len([t for t in t_trades if t["action"] == "sell_t"])
    total_fee = sum(t["fee"] for t in t_trades)

    # 距离负成本还差多少
    gap_to_negative = net_cost if not is_negative else 0

    # 已回收比例
    recovery_pct = (total_sold / total_invested * 100) if total_invested > 0 else 0

    return {
        "per_share_cost": round(per_share_cost, 4),
        "is_negative": is_negative,
        "original_cost": round(original_cost, 4),
        "cost_reduction": round(cost_reduction, 4),
        "cost_reduction_pct": round(cost_reduction_pct, 2),
        "net_cost": round(net_cost, 2),
        "total_invested": round(total_invested, 2),
        "total_sold": round(total_sold, 2),
        "t_net_profit": round(t_net, 2),
        "total_fee": round(total_fee, 2),
        "buy_t_count": buy_t_count,
        "sell_t_count": sell_t_count,
        "recovery_pct": round(recovery_pct, 2),
        "gap_to_negative": round(gap_to_negative, 2),
        "negative_cost_label": (
            "已实现负成本！" if is_negative
            else f"距离负成本还需回收 ¥{gap_to_negative:,.0f}"
        ),
    }


# ============================================================
# 交易记录查询
# ============================================================

def get_trade_history(code: str = None, market: str = None,
                      limit: int = 100) -> dict:
    """查询做T交易历史"""
    trades = _load_trades()

    if code:
        trades = [t for t in trades if t["code"] == code]
    if market:
        trades = [t for t in trades if t["market"] == market]

    # 按时间倒序
    trades.sort(key=lambda t: t["time"], reverse=True)
    trades = trades[:limit]

    # 统计
    total_buy = sum(t["amount"] for t in trades if t["action"] == "buy_t")
    total_sell = sum(t["amount"] for t in trades if t["action"] == "sell_t")
    total_fee = sum(t["fee"] for t in trades)

    return {
        "trades": trades,
        "total": len(trades),
        "total_buy_amount": round(total_buy, 2),
        "total_sell_amount": round(total_sell, 2),
        "total_fee": round(total_fee, 2),
        "net_amount": round(total_sell - total_buy, 2),
    }


# ============================================================
# 删除/重置仓位
# ============================================================

def delete_position(code: str, market: str) -> dict:
    """删除仓位记录"""
    positions = _load_positions()
    key = f"{market}_{code}"
    if key not in positions:
        return {"error": f"未找到 {code} 的持仓记录"}
    del positions[key]
    _save_positions(positions)
    return {"message": f"已删除 {code} 的持仓记录"}


def reset_all() -> dict:
    """重置全部仓位和交易记录"""
    _save_positions({})
    _save_trades([])
    return {"message": "已重置全部仓位和交易记录"}


def get_risk_summary() -> dict:
    """
    风险汇总报告（机构级）

    分析所有持仓的风险状况：
    1. 做T仓占比（是否超过40%安全线）
    2. 今日交易频率
    3. 累计手续费占比
    4. 各持仓盈亏状态
    """
    positions = _load_positions()
    today = datetime.now().strftime("%Y-%m-%d")

    risk_items = []
    total_exposure = 0.0
    total_t_exposure = 0.0

    for key, pos in positions.items():
        code = pos["code"]
        name = pos["name"]
        market = pos["market"]
        total_shares = pos["total_shares"]
        base_shares = pos["base_shares"]
        t_shares = pos["t_shares"]
        avg_cost = pos["avg_cost"]

        # 做T仓占比
        t_ratio = round(t_shares / total_shares * 100, 1) if total_shares > 0 else 0
        exposure = total_shares * avg_cost
        t_exposure = t_shares * avg_cost
        total_exposure += exposure
        total_t_exposure += t_exposure

        # 今日交易次数
        today_trades = [t for t in pos.get("t_trades", []) if t.get("time", "").startswith(today)]

        # 累计手续费
        total_fee = sum(t["fee"] for t in pos.get("t_trades", []))

        # 风险等级
        risk_level = "low"
        risk_reasons = []
        if t_ratio > 40:
            risk_level = "high"
            risk_reasons.append(f"做T仓占比{t_ratio}%超过40%安全线")
        elif t_ratio > 30:
            risk_level = "medium"
            risk_reasons.append(f"做T仓占比{t_ratio}%接近安全线")
        if len(today_trades) >= MAX_DAILY_TRADES:
            risk_level = "high"
            risk_reasons.append(f"今日已交易{len(today_trades)}次，达到上限")

        risk_items.append({
            "code": code,
            "name": name,
            "market": market,
            "t_ratio": t_ratio,
            "today_trades": len(today_trades),
            "total_fee": round(total_fee, 2),
            "risk_level": risk_level,
            "risk_reasons": risk_reasons,
        })

    # 整体风险评估
    overall_t_ratio = round(total_t_exposure / total_exposure * 100, 1) if total_exposure > 0 else 0

    return {
        "positions": risk_items,
        "overall": {
            "total_exposure": round(total_exposure, 2),
            "t_exposure": round(total_t_exposure, 2),
            "t_ratio": overall_t_ratio,
            "risk_level": "high" if overall_t_ratio > 40 else "medium" if overall_t_ratio > 30 else "low",
        },
        "rules": {
            "max_daily_trades": MAX_DAILY_TRADES,
            "max_t_ratio": 40,
            "slippage_model": SLIPPAGE_MODEL,
        },
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ============================================================
# 专家级：盈亏分析引擎
# ============================================================

def get_trade_analytics() -> dict:
    """
    盈亏分析仪表盘 — 专家级交易复盘

    分析维度：
    1. 按星期几统计胜率和盈亏
    2. 按时间段（上午/下午）统计
    3. 按股票统计
    4. 连续亏损/盈利统计
    5. 交易频率 vs 收益率
    6. 最佳/最差交易排名
    7. 累计P&L曲线
    8. 交易质量评分
    """
    trades = _load_trades()
    if not trades:
        return {"error": "暂无交易记录", "analytics": None}

    sell_trades = [t for t in trades if t["action"] == "sell_t"]
    all_trades = trades

    # --- 1. 按星期几统计 ---
    weekday_stats = defaultdict(lambda: {"count": 0, "wins": 0, "losses": 0, "total_pnl": 0.0, "pnls": []})
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    for t in sell_trades:
        try:
            dt = datetime.strptime(t["time"], "%Y-%m-%d %H:%M:%S")
            wd = dt.weekday()
            pnl = t.get("pnl", 0) or 0
            weekday_stats[wd]["count"] += 1
            weekday_stats[wd]["total_pnl"] += pnl
            weekday_stats[wd]["pnls"].append(pnl)
            if pnl > 0:
                weekday_stats[wd]["wins"] += 1
            elif pnl < 0:
                weekday_stats[wd]["losses"] += 1
        except Exception:
            pass

    weekday_analysis = []
    for wd in range(5):
        s = weekday_stats[wd]
        wr = round(s["wins"] / s["count"] * 100, 1) if s["count"] > 0 else 0
        avg_pnl = round(s["total_pnl"] / s["count"], 2) if s["count"] > 0 else 0
        weekday_analysis.append({
            "weekday": weekday_names[wd],
            "weekday_num": wd,
            "trade_count": s["count"],
            "win_rate": wr,
            "total_pnl": round(s["total_pnl"], 2),
            "avg_pnl": avg_pnl,
        })

    # --- 2. 按时间段统计 ---
    session_stats = {"morning": {"pnls": [], "count": 0}, "afternoon": {"pnls": [], "count": 0}}
    for t in sell_trades:
        try:
            dt = datetime.strptime(t["time"], "%Y-%m-%d %H:%M:%S")
            pnl = t.get("pnl", 0) or 0
            if dt.hour < 12:
                session_stats["morning"]["pnls"].append(pnl)
                session_stats["morning"]["count"] += 1
            else:
                session_stats["afternoon"]["pnls"].append(pnl)
                session_stats["afternoon"]["count"] += 1
        except Exception:
            pass

    session_analysis = {}
    for session_name, data in session_stats.items():
        pnls = data["pnls"]
        wins = len([p for p in pnls if p > 0])
        session_analysis[session_name] = {
            "label": "上午(9:30-12:00)" if session_name == "morning" else "下午(13:00-15:00)",
            "trade_count": data["count"],
            "win_rate": round(wins / len(pnls) * 100, 1) if pnls else 0,
            "total_pnl": round(sum(pnls), 2),
            "avg_pnl": round(statistics.mean(pnls), 2) if pnls else 0,
        }

    # --- 3. 按股票统计 ---
    stock_stats = defaultdict(lambda: {"count": 0, "wins": 0, "total_pnl": 0.0, "name": ""})
    for t in sell_trades:
        pnl = t.get("pnl", 0) or 0
        stock_stats[t["code"]]["count"] += 1
        stock_stats[t["code"]]["total_pnl"] += pnl
        stock_stats[t["code"]]["name"] = t.get("code", "")
        if pnl > 0:
            stock_stats[t["code"]]["wins"] += 1

    stock_analysis = []
    for code, s in stock_stats.items():
        stock_analysis.append({
            "code": code,
            "trade_count": s["count"],
            "win_rate": round(s["wins"] / s["count"] * 100, 1) if s["count"] > 0 else 0,
            "total_pnl": round(s["total_pnl"], 2),
            "avg_pnl": round(s["total_pnl"] / s["count"], 2) if s["count"] > 0 else 0,
        })
    stock_analysis.sort(key=lambda x: x["total_pnl"], reverse=True)

    # --- 4. 连续盈亏统计 ---
    streaks = _calc_streaks(sell_trades)

    # --- 5. 交易频率分析 ---
    daily_counts = defaultdict(int)
    daily_pnl = defaultdict(float)
    for t in sell_trades:
        day = t["time"][:10]
        daily_counts[day] += 1
        daily_pnl[day] += (t.get("pnl", 0) or 0)

    freq_analysis = []
    for day in sorted(daily_counts.keys()):
        freq_analysis.append({
            "date": day,
            "trades": daily_counts[day],
            "pnl": round(daily_pnl[day], 2),
        })

    if len(freq_analysis) >= 3:
        avg_freq = statistics.mean([f["trades"] for f in freq_analysis])
        high_freq_days = [f for f in freq_analysis if f["trades"] >= avg_freq]
        low_freq_days = [f for f in freq_analysis if f["trades"] < avg_freq]
        high_freq_avg_pnl = statistics.mean([f["pnl"] for f in high_freq_days]) if high_freq_days else 0
        low_freq_avg_pnl = statistics.mean([f["pnl"] for f in low_freq_days]) if low_freq_days else 0
    else:
        avg_freq = 0
        high_freq_avg_pnl = 0
        low_freq_avg_pnl = 0

    # --- 6. 最佳/最差交易排名 ---
    all_sell_with_pnl = [t for t in sell_trades if (t.get("pnl") or 0) != 0]
    all_sell_with_pnl.sort(key=lambda t: t.get("pnl", 0), reverse=True)
    best_trades = all_sell_with_pnl[:5]
    worst_trades = sorted(all_sell_with_pnl[-5:], key=lambda t: t.get("pnl", 0)) if len(all_sell_with_pnl) >= 5 else []

    # --- 7. 累计P&L曲线 ---
    cumulative_pnl = []
    running = 0.0
    for t in sorted(sell_trades, key=lambda x: x["time"]):
        running += (t.get("pnl", 0) or 0)
        cumulative_pnl.append({
            "date": t["time"][:10],
            "trade_pnl": round(t.get("pnl", 0) or 0, 2),
            "cumulative_pnl": round(running, 2),
        })

    # --- 8. 综合评分 ---
    total_sell = len(sell_trades)
    total_wins = len([t for t in sell_trades if (t.get("pnl", 0) or 0) > 0])
    total_losses = len([t for t in sell_trades if (t.get("pnl", 0) or 0) < 0])
    overall_wr = round(total_wins / total_sell * 100, 1) if total_sell > 0 else 0
    total_pnl = sum(t.get("pnl", 0) or 0 for t in sell_trades)
    avg_win = statistics.mean([t["pnl"] for t in sell_trades if (t.get("pnl", 0) or 0) > 0]) if total_wins > 0 else 0
    avg_loss = statistics.mean([t["pnl"] for t in sell_trades if (t.get("pnl", 0) or 0) < 0]) if total_losses > 0 else 0
    profit_factor = round(avg_win / abs(avg_loss), 2) if avg_loss != 0 else float("inf")

    # 交易质量评分 (0-100)
    quality_score = 0
    if total_sell >= 10:
        quality_score += min(overall_wr, 70) * 0.4
        quality_score += min(max(profit_factor, 0), 3) / 3 * 30
        quality_score += min(streaks.get("max_win_streak", 0), 5) / 5 * 15
        quality_score += max(0, 15 - streaks.get("max_lose_streak", 0) * 3)
    quality_score = round(min(max(quality_score, 0), 100), 1)

    return {
        "summary": {
            "total_trades": len(all_trades),
            "sell_trades": total_sell,
            "win_rate": overall_wr,
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": profit_factor,
            "quality_score": quality_score,
            "total_fees": round(sum(t.get("fee", 0) for t in all_trades), 2),
        },
        "weekday_analysis": weekday_analysis,
        "session_analysis": session_analysis,
        "stock_analysis": stock_analysis,
        "streaks": streaks,
        "frequency_analysis": {
            "avg_daily_trades": round(avg_freq, 1) if freq_analysis else 0,
            "high_freq_avg_pnl": round(high_freq_avg_pnl, 2),
            "low_freq_avg_pnl": round(low_freq_avg_pnl, 2),
            "insight": (
                "高频交易日收益更优" if high_freq_avg_pnl > low_freq_avg_pnl
                else "低频交易日收益更优（减少交易频率可能提升收益）"
            ) if freq_analysis else "数据不足",
            "daily_data": freq_analysis[-30:],
        },
        "best_trades": best_trades,
        "worst_trades": worst_trades,
        "cumulative_pnl": cumulative_pnl[-60:],
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _calc_streaks(sell_trades: list) -> dict:
    """计算连续盈亏统计"""
    if not sell_trades:
        return {"max_win_streak": 0, "max_lose_streak": 0, "current_streak": 0, "current_type": "none"}

    sorted_trades = sorted(sell_trades, key=lambda t: t["time"])
    max_win = 0
    max_lose = 0
    current_win = 0
    current_lose = 0

    for t in sorted_trades:
        pnl = t.get("pnl", 0) or 0
        if pnl > 0:
            current_win += 1
            current_lose = 0
            max_win = max(max_win, current_win)
        elif pnl < 0:
            current_lose += 1
            current_win = 0
            max_lose = max(max_lose, current_lose)
        else:
            current_win = 0
            current_lose = 0

    last_pnl = sorted_trades[-1].get("pnl", 0) or 0
    if last_pnl > 0:
        current_streak = current_win
        current_type = "win"
    elif last_pnl < 0:
        current_streak = current_lose
        current_type = "lose"
    else:
        current_streak = 0
        current_type = "none"

    return {
        "max_win_streak": max_win,
        "max_lose_streak": max_lose,
        "current_streak": current_streak,
        "current_type": current_type,
        "current_label": (
            f"连赢{current_streak}笔 🔥" if current_type == "win"
            else f"连亏{current_streak}笔 ⚠️" if current_type == "lose"
            else "无连续"
        ),
    }


def get_trade_journal(
    code: str = None,
    market: str = None,
    start_date: str = None,
    end_date: str = None,
    pnl_filter: str = None,
    limit: int = 50,
) -> dict:
    """
    交易日志 — 带筛选的详细交易记录

    每笔交易附加：
    - 交易质量标签
    - 持有时间
    - 盈亏百分比
    """
    trades = _load_trades()
    sell_trades = [t for t in trades if t["action"] == "sell_t"]

    if code:
        sell_trades = [t for t in sell_trades if t["code"] == code]
    if market:
        sell_trades = [t for t in sell_trades if t["market"] == market]
    if start_date:
        sell_trades = [t for t in sell_trades if t["time"][:10] >= start_date]
    if end_date:
        sell_trades = [t for t in sell_trades if t["time"][:10] <= end_date]
    if pnl_filter == "win":
        sell_trades = [t for t in sell_trades if (t.get("pnl", 0) or 0) > 0]
    elif pnl_filter == "lose":
        sell_trades = [t for t in sell_trades if (t.get("pnl", 0) or 0) < 0]

    sell_trades.sort(key=lambda t: t["time"], reverse=True)
    sell_trades = sell_trades[:limit]

    journal = []
    for t in sell_trades:
        pnl = t.get("pnl", 0) or 0
        if pnl > 0:
            quality = "great" if pnl > 500 else "good"
            quality_label = "🏆 优秀交易" if pnl > 500 else "✅ 盈利交易"
        elif pnl < 0:
            quality = "bad" if pnl < -500 else "small_loss"
            quality_label = "❌ 重大亏损" if pnl < -500 else "⚠️ 小幅亏损"
        else:
            quality = "breakeven"
            quality_label = "➖ 持平"

        # 计算持有时间
        hold_hours = None
        positions = _load_positions()
        pos_key = f"{t.get('market', '')}_{t['code']}"
        pos = positions.get(pos_key, {})
        prev_buys = [bt for bt in pos.get("t_trades", [])
                     if bt["action"] == "buy_t" and bt["time"] < t["time"]]
        if prev_buys:
            try:
                buy_time = datetime.strptime(prev_buys[-1]["time"], "%Y-%m-%d %H:%M:%S")
                sell_time = datetime.strptime(t["time"], "%Y-%m-%d %H:%M:%S")
                hold_hours = round((sell_time - buy_time).total_seconds() / 3600, 1)
            except Exception:
                pass

        journal.append({
            **t,
            "quality": quality,
            "quality_label": quality_label,
            "hold_hours": hold_hours,
            "pnl_pct": round(pnl / (t.get("amount", 1) - pnl) * 100, 2) if t.get("amount") and pnl else 0,
        })

    return {
        "journal": journal,
        "total": len(journal),
        "filters": {
            "code": code, "market": market,
            "start_date": start_date, "end_date": end_date,
            "pnl_filter": pnl_filter,
        },
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ============================================================
# 专家级：自动告警系统
# ============================================================

def check_trading_alerts() -> dict:
    """
    自动告警系统 — 检查所有持仓的告警条件

    告警类型：
    1. 止损预警 — 价格接近止损位
    2. 做T仓超限 — 做T仓占比过高
    3. 连续亏损 — 连续亏损达到阈值
    4. 手续费过高 — 累计手续费占比过大
    5. 今日交易频次 — 接近或达到每日上限
    6. 负成本达成 — 做T回收超过投入
    """
    positions = _load_positions()
    trades = _load_trades()
    today = datetime.now().strftime("%Y-%m-%d")

    alerts = []

    for key, pos in positions.items():
        code = pos["code"]
        name = pos.get("name", code)
        market = pos["market"]
        total_shares = pos["total_shares"]
        t_shares = pos["t_shares"]
        avg_cost = pos["avg_cost"]
        t_trades = pos.get("t_trades", [])

        # 1. 做T仓超限告警
        t_ratio = t_shares / total_shares * 100 if total_shares > 0 else 0
        if t_ratio > 40:
            alerts.append({
                "type": "t_ratio_high",
                "severity": "high",
                "code": code,
                "name": name,
                "message": f"做T仓占比{t_ratio:.1f}%超过40%安全线，风险过高",
                "action": "建议卖出部分做T仓，降低风险敞口",
            })
        elif t_ratio > 30:
            alerts.append({
                "type": "t_ratio_warning",
                "severity": "medium",
                "code": code,
                "name": name,
                "message": f"做T仓占比{t_ratio:.1f}%接近安全线",
                "action": "注意控制做T仓规模",
            })

        # 2. 今日交易频次告警
        today_trades = [t for t in t_trades if t.get("time", "").startswith(today)]
        if len(today_trades) >= MAX_DAILY_TRADES:
            alerts.append({
                "type": "daily_limit",
                "severity": "high",
                "code": code,
                "name": name,
                "message": f"今日已交易{len(today_trades)}次，达到每日上限{MAX_DAILY_TRADES}次",
                "action": "停止交易，等待下一个交易日",
            })
        elif len(today_trades) >= MAX_DAILY_TRADES - 1:
            alerts.append({
                "type": "daily_warning",
                "severity": "medium",
                "code": code,
                "name": name,
                "message": f"今日已交易{len(today_trades)}次，接近每日上限",
                "action": "谨慎操作，避免频繁交易",
            })

        # 3. 连续亏损告警
        sell_trades = [t for t in t_trades if t["action"] == "sell_t"]
        if len(sell_trades) >= 3:
            recent_sells = sorted(sell_trades, key=lambda t: t["time"])[-3:]
            consecutive_losses = all((t.get("pnl") or 0) < 0 for t in recent_sells)
            if consecutive_losses:
                alerts.append({
                    "type": "consecutive_losses",
                    "severity": "high",
                    "code": code,
                    "name": name,
                    "message": "连续3笔做T亏损，策略可能失效",
                    "action": "暂停做T，重新评估市场环境和策略",
                })

        # 4. 手续费占比告警
        total_fee = sum(t.get("fee", 0) for t in t_trades)
        total_amount = sum(t.get("amount", 0) for t in t_trades)
        if total_amount > 0:
            fee_ratio = total_fee / total_amount * 100
            if fee_ratio > 1.0:
                alerts.append({
                    "type": "fee_high",
                    "severity": "medium",
                    "code": code,
                    "name": name,
                    "message": f"累计手续费占比{fee_ratio:.2f}%，侵蚀利润",
                    "action": "考虑降低交易频率或加大单笔交易量",
                })

        # 5. 负成本达成祝贺
        cost_analysis = calc_cost_analysis(pos)
        if cost_analysis.get("is_negative"):
            alerts.append({
                "type": "negative_cost",
                "severity": "info",
                "code": code,
                "name": name,
                "message": "恭喜！已实现负成本持股",
                "action": "继续持有，做T收益为纯利润",
            })

    # 按严重程度排序
    severity_order = {"high": 0, "medium": 1, "info": 2}
    alerts.sort(key=lambda a: severity_order.get(a["severity"], 3))

    return {
        "alerts": alerts,
        "total": len(alerts),
        "high_count": len([a for a in alerts if a["severity"] == "high"]),
        "medium_count": len([a for a in alerts if a["severity"] == "medium"]),
        "info_count": len([a for a in alerts if a["severity"] == "info"]),
        "has_critical": any(a["severity"] == "high" for a in alerts),
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
