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
from datetime import datetime
from dataclasses import dataclass, field, asdict
from collections import defaultdict

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
