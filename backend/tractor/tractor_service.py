# -*- coding: utf-8 -*-
"""拖拉机套利自动化服务 (V2 - 机构级)

核心能力：
1. 多账户管理 - 增删改查、资金查询、持仓追踪
2. 套利策略引擎 - LOF溢价/折价机会扫描与评估
3. 资金分配算法 - 基于限购/余额/风控的最优分配
4. 风险控制 - 交易时段/流动性/溢价阈值/仓位上限
5. 操作历史与损益追踪 - 持久化记录、已实现损益计算

通过AutoIt脚本控制华宝证券/银河证券客户端执行实际交易。
"""

import subprocess
import time
import logging
import json
import os
import threading
import uuid
from typing import Optional, List
from pathlib import Path
from datetime import datetime, date

from .tractor_config import (
    load_accounts,
    sync_to_autoit,
    list_accounts,
    add_account,
    remove_account,
    update_account,
)
from .tractor_models import (
    OperationType,
    BrokerType,
    ArbitrageDirection,
    RiskLevel,
    TractorAccount,
    AccountWithBalance,
    ArbitrageOpportunity,
    AccountAllocation,
    AllocationPlan,
    RiskSettings,
    RiskCheckResult,
    OperationRecord,
    PnLSummary,
    StrategyRecommendation,
    StrategyOverview,
)

logger = logging.getLogger(__name__)

# ==================== 常量 ====================

# AutoIt操作类型常量（保持与前端中文标签一致）
OP_LOGIN_ONLY = OperationType.LOGIN_ONLY
OP_SUBSCRIBE = OperationType.SUBSCRIBE
OP_SELL = OperationType.SELL
OP_REDEEM = OperationType.REDEEM
OP_CANCEL = OperationType.CANCEL
OP_REVERSE_REPO = OperationType.REVERSE_REPO
OP_TRANSFER = OperationType.TRANSFER

# 交易时段（A股）
TRADING_HOURS = [
    ((9, 15), (11, 30)),    # 上午集合竞价+连续竞价
    ((13, 0), (15, 0)),     # 下午连续竞价
]

# 费用常量
DEFAULT_APPLY_FEE_PCT = 0.12    # 默认申购费率 %
TRADE_COMMISSION_PCT = 0.03     # 交易佣金 %
TRANSFER_FEE_PCT = 0.01         # 转托管费 %

# 历史记录文件路径
HISTORY_FILE = Path(__file__).parent / "operation_history.json"
RISK_SETTINGS_FILE = Path(__file__).parent / "risk_settings.json"


def _safe_float(val, default=0.0) -> float:
    """安全转换为float"""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _parse_limit_amount(limit_str: str) -> float:
    """解析限购金额字符串

    Args:
        limit_str: 如 "限10万", "100000", "限购100万", "不限" 等

    Returns:
        限购金额(元)，无法解析返回0
    """
    if not limit_str:
        return 0.0

    import re
    limit_str = str(limit_str).strip()

    # "不限" 或 "开放"
    if any(kw in limit_str for kw in ["不限", "开放", "正常"]):
        return float('inf')

    # 提取数字
    m = re.search(r'([\d.]+)\s*万', limit_str)
    if m:
        return float(m.group(1)) * 10000

    m = re.search(r'([\d.]+)\s*百万', limit_str)
    if m:
        return float(m.group(1)) * 1000000

    m = re.search(r'([\d.]+)', limit_str)
    if m:
        val = float(m.group(1))
        # 如果数字很大（>10000），直接返回
        if val > 10000:
            return val
        # 否则假设单位是万
        return val * 10000

    return 0.0


# ==================== 交易时段检查 ====================

def is_trading_hours() -> tuple:
    """检查是否在交易时段

    Returns:
        (is_trading: bool, status_str: str)
    """
    now = datetime.now()
    weekday = now.weekday()

    # 周末
    if weekday >= 5:
        return False, "周末休市"

    hour, minute = now.hour, now.minute
    current_minutes = hour * 60 + minute

    for (start_h, start_m), (end_h, end_m) in TRADING_HOURS:
        start = start_h * 60 + start_m
        end = end_h * 60 + end_m
        if start <= current_minutes <= end:
            return True, "交易中"

    # 集合竞价前
    if current_minutes < 9 * 60 + 15:
        return False, "盘前"
    # 午休
    if 11 * 60 + 30 < current_minutes < 13 * 60:
        return False, "午休"
    # 收盘后
    if current_minutes > 15 * 60:
        return False, "已收盘"

    return False, "非交易时段"


# ==================== 持久化 ====================

def _load_history() -> list:
    """加载操作历史"""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_history(records: list) -> bool:
    """保存操作历史"""
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"保存操作历史失败: {e}")
        return False


def _load_risk_settings() -> dict:
    """加载风控设置"""
    if RISK_SETTINGS_FILE.exists():
        try:
            with open(RISK_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_risk_settings(settings: dict) -> bool:
    """保存风控设置"""
    try:
        with open(RISK_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"保存风控设置失败: {e}")
        return False


# ==================== 核心服务 ====================

class TractorService:
    """拖拉机套利自动化服务 (V2)"""

    def __init__(self):
        self._config = load_accounts()
        self._autoit_path = self._config.get(
            "autoit_path",
            r"C:\Program Files (x86)\AutoIt3\AutoIt3.exe"
        )
        self._script_path = self._config.get(
            "script_path",
            str(Path(__file__).parent / "yinhe.au3")
        )
        self._running = False
        self._last_result = None
        self._log_lines = []
        self._current_operation = None
        self._start_time = None

        # 加载持久化数据
        self._operation_history: List[dict] = _load_history()
        self._risk_settings = RiskSettings(**_load_risk_settings()).model_dump()

        # 每账户资金缓存 (account_id -> balance_info)
        self._account_balances: dict = {}

        # 每日操作计数
        self._daily_op_count = 0
        self._daily_op_date = ""

    # ==================== 环境检查 ====================

    def check_autoit_installed(self) -> dict:
        """检查AutoIt是否已安装"""
        if os.path.exists(self._autoit_path):
            return {"installed": True, "path": self._autoit_path}
        alt_paths = [
            r"C:\Program Files\AutoIt3\AutoIt3.exe",
            r"C:\AutoIt3\AutoIt3.exe",
        ]
        for p in alt_paths:
            if os.path.exists(p):
                self._autoit_path = p
                return {"installed": True, "path": p}
        return {"installed": False, "path": self._autoit_path}

    def check_broker_client(self, broker_type: str = "huabao") -> dict:
        """检查券商客户端是否已安装"""
        if broker_type == "huabao":
            client_path = r"C:\tc_hbzq\Tc.exe"
            client_name = "华宝证券通达信版独立交易"
        else:
            client_path = r"C:\中国银河证券海王星独立交易\Tc.exe"
            client_name = "银河证券海王星"

        exists = os.path.exists(client_path)
        return {
            "installed": exists,
            "path": client_path,
            "name": client_name,
            "broker_type": broker_type,
        }

    def get_system_status(self) -> dict:
        """获取系统状态"""
        autoit = self.check_autoit_installed()
        huabao = self.check_broker_client("huabao")
        yinhe = self.check_broker_client("yinhe")
        accounts = list_accounts()
        is_trading, market_status = is_trading_hours()

        return {
            "autoit": autoit,
            "clients": {
                "huabao": huabao,
                "yinhe": yinhe,
            },
            "accounts": accounts,
            "running": self._running,
            "current_operation": self._current_operation,
            "script_path": self._script_path,
            "market_status": market_status,
            "is_trading": is_trading,
        }

    # ==================== 账户资金管理 ====================

    def get_account_balances(self) -> List[AccountWithBalance]:
        """获取所有账户的资金信息

        注意：资金信息需要通过'仅登录查询'操作获取。
        此处返回缓存的余额数据，如需刷新请先执行查询操作。
        """
        config = load_accounts()
        result = []
        for acc in config["accounts"]:
            acc_id = acc["account_id"]
            balance = self._account_balances.get(acc_id, {})
            result.append(AccountWithBalance(
                account_id=acc_id,
                name=acc.get("name", acc_id),
                broker_type=acc.get("broker_type", "huabao"),
                enabled=acc.get("enabled", True),
                available_cash=_safe_float(balance.get("available_cash")),
                total_assets=_safe_float(balance.get("total_assets")),
                fund_shares=int(balance.get("fund_shares", 0)),
                fund_cost=_safe_float(balance.get("fund_cost")),
                fund_profit=_safe_float(balance.get("fund_profit")),
                last_query_time=balance.get("last_query_time"),
            ))
        return result

    def update_account_balance(self, account_id: str, balance_info: dict):
        """更新账户资金信息（由查询操作回填）"""
        balance_info["last_query_time"] = datetime.now().isoformat()
        self._account_balances[account_id] = balance_info

    # ==================== 风险控制 ====================

    def get_risk_settings(self) -> dict:
        """获取风控设置"""
        return self._risk_settings.copy()

    def update_risk_settings(self, **kwargs) -> dict:
        """更新风控设置"""
        for key, value in kwargs.items():
            if key in self._risk_settings:
                self._risk_settings[key] = value
        _save_risk_settings(self._risk_settings)
        return self._risk_settings.copy()

    def check_risk(
        self,
        operation: str,
        fund_code: str = "",
        premium_pct: float = 0.0,
        amount: float = 0.0,
        apply_status: str = "",
        turnover: float = 0.0,
        account_ids: list = None,
    ) -> RiskCheckResult:
        """风控预检

        Args:
            operation: 操作类型
            fund_code: 基金代码
            premium_pct: 溢价率(溢价为正，折价为负)
            amount: 操作金额
            apply_status: 申购状态
            turnover: 成交额(万元)
            account_ids: 指定账户

        Returns:
            风控检查结果
        """
        checks = []
        warnings = []
        blocked = []
        settings = self._risk_settings

        # 1. 交易时段检查
        if settings.get("require_trading_hours", True):
            is_trading, status_str = is_trading_hours()
            checks.append({
                "name": "交易时段",
                "passed": is_trading,
                "message": status_str,
                "level": "critical" if not is_trading else "low",
            })
            if not is_trading:
                blocked.append(f"当前非交易时段: {status_str}")

        # 2. 每日操作次数限制
        today = date.today().isoformat()
        if self._daily_op_date != today:
            self._daily_op_count = 0
            self._daily_op_date = today

        max_ops = settings.get("max_daily_operations", 10)
        ops_passed = self._daily_op_count < max_ops
        checks.append({
            "name": "每日操作次数",
            "passed": ops_passed,
            "message": f"今日已操作{self._daily_op_count}次，上限{max_ops}次",
            "level": "high" if not ops_passed else "low",
        })
        if not ops_passed:
            blocked.append(f"今日操作次数已达上限({max_ops}次)")

        # 3. 申购操作的溢价率检查
        if operation in [OperationType.SUBSCRIBE, "场内申购"]:
            min_premium = settings.get("min_premium_pct", 2.0)
            premium_ok = abs(premium_pct) >= min_premium
            checks.append({
                "name": "溢价率",
                "passed": premium_ok,
                "message": f"当前溢价率{premium_pct:.2f}%，阈值{min_premium}%",
                "level": "critical" if not premium_ok else "low",
            })
            if not premium_ok:
                blocked.append(f"溢价率{premium_pct:.2f}%低于阈值{min_premium}%")

        # 4. 申购状态检查
        if operation in [OperationType.SUBSCRIBE, "场内申购"] and apply_status:
            is_normal = "暂停" not in apply_status and "停止" not in apply_status
            checks.append({
                "name": "申购状态",
                "passed": is_normal,
                "message": f"申购状态: {apply_status}",
                "level": "critical" if not is_normal else "low",
            })
            if not is_normal:
                blocked.append(f"申购状态异常: {apply_status}")

        # 5. 流动性检查
        if settings.get("block_low_liquidity", True):
            min_turnover = settings.get("min_turnover", 1000)
            if turnover > 0:
                liq_ok = turnover >= min_turnover
                checks.append({
                    "name": "流动性",
                    "passed": liq_ok,
                    "message": f"成交额{turnover:.0f}万，阈值{min_turnover:.0f}万",
                    "level": "high" if not liq_ok else "low",
                })
                if not liq_ok:
                    warnings.append(f"成交额偏低({turnover:.0f}万)，可能导致滑点")

        # 6. 单账户金额限制
        if amount > 0:
            max_single = settings.get("max_single_amount", 500000)
            single_ok = amount <= max_single
            checks.append({
                "name": "单账户金额",
                "passed": single_ok,
                "message": f"操作金额{amount:.0f}元，上限{max_single:.0f}元",
                "level": "high" if not single_ok else "low",
            })
            if not single_ok:
                blocked.append(f"单账户金额{amount:.0f}元超过上限{max_single:.0f}元")

        # 7. 总金额限制
        if amount > 0 and account_ids:
            total_amount = amount * len(account_ids)
            max_total = settings.get("max_total_amount", 2000000)
            total_ok = total_amount <= max_total
            checks.append({
                "name": "总金额",
                "passed": total_ok,
                "message": f"总金额{total_amount:.0f}元，上限{max_total:.0f}元",
                "level": "high" if not total_ok else "low",
            })
            if not total_ok:
                blocked.append(f"总金额{total_amount:.0f}元超过上限{max_total:.0f}元")

        # 8. 运行状态检查
        if self._running:
            checks.append({
                "name": "运行状态",
                "passed": False,
                "message": "已有操作正在运行",
                "level": "critical",
            })
            blocked.append("已有操作正在运行，请等待完成")

        # 9. 账户余额检查（如果有缓存的余额数据）
        if operation in [OperationType.SUBSCRIBE, "场内申购"] and amount > 0:
            config = load_accounts()
            target_accounts = account_ids or [a["account_id"] for a in config["accounts"] if a.get("enabled", True)]
            min_reserve = settings.get("min_cash_reserve", 10000)
            for acc_id in target_accounts:
                balance = self._account_balances.get(acc_id, {})
                cash = _safe_float(balance.get("available_cash"))
                if cash > 0 and (cash - amount) < min_reserve:
                    warnings.append(
                        f"账户{acc_id}操作后余额{cash - amount:.0f}元，低于保留线{min_reserve:.0f}元"
                    )

        passed = len(blocked) == 0
        level = RiskLevel.LOW
        if blocked:
            level = RiskLevel.CRITICAL
        elif warnings:
            level = RiskLevel.MEDIUM

        return RiskCheckResult(
            passed=passed,
            level=level,
            checks=checks,
            warnings=warnings,
            blocked_reasons=blocked,
        )

    # ==================== 资金分配算法 ====================

    def calculate_allocation(
        self,
        fund_code: str,
        fund_name: str,
        direction: str,
        premium_pct: float = 0.0,
        apply_limit_str: str = "",
        apply_status: str = "",
        est_nav: float = 0.0,
        fund_price: float = 0.0,
        account_ids: list = None,
    ) -> AllocationPlan:
        """计算资金分配方案

        算法逻辑：
        1. 解析每户限购金额（从套利扫描结果获取）
        2. 获取所有启用账户及其可用余额
        3. 每账户分配 = min(限购金额, 可用余额 - 保留资金, 单账户上限)
        4. 生成分配方案和预警信息

        Args:
            fund_code: 基金代码
            fund_name: 基金名称
            direction: "溢价" or "折价"
            premium_pct: 溢价率%
            apply_limit_str: 限购字符串
            apply_status: 申购状态
            est_nav: 估算净值
            fund_price: 场内价格
            account_ids: 指定账户（None=全部启用账户）

        Returns:
            资金分配方案
        """
        settings = self._risk_settings
        config = load_accounts()

        # 解析限购
        limit_per_account = _parse_limit_amount(apply_limit_str)
        if limit_per_account <= 0:
            limit_per_account = settings.get("max_single_amount", 500000)

        # 单账户上限
        max_single = settings.get("max_single_amount", 500000)
        limit_per_account = min(limit_per_account, max_single) if max_single > 0 else limit_per_account

        # 最低保留资金
        min_reserve = settings.get("min_cash_reserve", 10000)

        # 获取目标账户
        all_accounts = config["accounts"]
        if account_ids:
            target_accounts = [a for a in all_accounts if a["account_id"] in account_ids and a.get("enabled", True)]
        else:
            target_accounts = [a for a in all_accounts if a.get("enabled", True)]

        allocations = []
        warnings = []
        total_amount = 0.0

        for acc in target_accounts:
            acc_id = acc["account_id"]
            balance = self._account_balances.get(acc_id, {})
            available_cash = _safe_float(balance.get("available_cash"))

            notes = []

            if direction == ArbitrageDirection.PREMIUM or direction == "溢价":
                # 溢价套利：场内申购
                if available_cash <= 0:
                    # 无余额数据时，假设充足（需手动确认）
                    recommended = limit_per_account
                    notes.append("无余额数据，请确认资金充足")
                else:
                    usable = max(0, available_cash - min_reserve)
                    recommended = min(limit_per_account, usable)
                    if recommended < limit_per_account:
                        notes.append(f"余额不足，可用{usable:.0f}元")

                if recommended <= 0:
                    notes.append("资金不足，跳过")
                    continue

                alloc = AccountAllocation(
                    account_id=acc_id,
                    account_name=acc.get("name", acc_id),
                    broker_type=acc.get("broker_type", "huabao"),
                    available_cash=available_cash,
                    recommended_amount=recommended,
                    max_amount=limit_per_account,
                    notes=notes,
                )

            elif direction == ArbitrageDirection.DISCOUNT or direction == "折价":
                # 折价套利：场内卖出（需要持有份额）
                shares = int(balance.get("fund_shares", 0))
                cost = _safe_float(balance.get("fund_cost"))

                if shares <= 0:
                    notes.append("无持仓，无法卖出")
                    continue

                alloc = AccountAllocation(
                    account_id=acc_id,
                    account_name=acc.get("name", acc_id),
                    broker_type=acc.get("broker_type", "huabao"),
                    available_cash=available_cash,
                    recommended_amount=shares * fund_price if fund_price > 0 else 0,
                    max_amount=shares * fund_price if fund_price > 0 else 0,
                    shares_to_sell=shares,
                    notes=notes,
                )
            else:
                continue

            allocations.append(alloc)
            total_amount += alloc.recommended_amount

        # 估算利润
        estimated_profit = 0.0
        if premium_pct != 0 and total_amount > 0:
            # 简化估算：净收益 = 总金额 * (溢价率 - 申购费 - 佣金)%
            net_rate = abs(premium_pct) - DEFAULT_APPLY_FEE_PCT - TRADE_COMMISSION_PCT
            estimated_profit = total_amount * net_rate / 100

        # 总金额限制检查
        max_total = settings.get("max_total_amount", 2000000)
        if total_amount > max_total > 0:
            warnings.append(f"总分配金额{total_amount:.0f}元超过上限{max_total:.0f}元")

        if not allocations:
            warnings.append("无可操作账户，请检查账户状态和资金余额")

        return AllocationPlan(
            fund_code=fund_code,
            fund_name=fund_name,
            direction=direction,
            premium_pct=premium_pct,
            apply_limit_per_account=limit_per_account,
            total_accounts=len(all_accounts),
            enabled_accounts=len(target_accounts),
            allocations=allocations,
            total_amount=total_amount,
            estimated_profit=estimated_profit,
            warnings=warnings,
        )

    # ==================== 策略扫描 ====================

    def scan_opportunities(
        self,
        min_premium: float = 2.0,
        min_amount: float = 1000,
        direction: str = "all",
    ) -> List[ArbitrageOpportunity]:
        """扫描LOF套利机会

        通过内部HTTP调用fund-arb的扫描接口获取数据，避免代码重复。

        Returns:
            套利机会列表
        """
        try:
            import httpx
            # 内部调用fund-arb扫描接口
            params = {
                "min_premium": min_premium,
                "min_amount": min_amount,
                "direction": direction,
            }
            # 使用localhost调用自身API
            resp = httpx.get(
                "http://127.0.0.1:8002/api/fund-arb/scan",
                params=params,
                timeout=30,
            )
            if resp.status_code != 200:
                logger.warning(f"fund-arb扫描返回{resp.status_code}")
                return []

            data = resp.json()
            if not data.get("success"):
                logger.warning(f"fund-arb扫描失败: {data.get('error')}")
                return []

            funds = data.get("data", {}).get("funds", [])
            opportunities = []

            for fund in funds:
                arb_eval = fund.get("arb_eval") or {}
                direction_val = arb_eval.get("direction", fund.get("direction", "none"))

                # 映射方向
                if direction_val in ("溢价", "premium"):
                    arb_dir = ArbitrageDirection.PREMIUM
                elif direction_val in ("折价", "discount"):
                    arb_dir = ArbitrageDirection.DISCOUNT
                else:
                    continue

                # 风险评级
                net_profit = _safe_float(arb_eval.get("net_profit_pct", 0))
                turnover = _safe_float(fund.get("turnover", 0))
                risk_level = RiskLevel.LOW
                if net_profit < 0.5 or turnover < 2000:
                    risk_level = RiskLevel.HIGH
                elif net_profit < 1.0 or turnover < 5000:
                    risk_level = RiskLevel.MEDIUM

                opp = ArbitrageOpportunity(
                    fund_code=fund.get("fund_code", ""),
                    fund_name=fund.get("fund_name", ""),
                    direction=arb_dir,
                    premium_pct=_safe_float(fund.get("premium_pct", 0)),
                    est_nav=_safe_float(fund.get("est_nav", 0)),
                    fund_price=_safe_float(fund.get("fund_price", 0)),
                    official_nav=_safe_float(fund.get("official_nav", 0)),
                    apply_limit=fund.get("apply_limit", ""),
                    apply_status=fund.get("apply_status", ""),
                    turnover=turnover,
                    apply_fee=_safe_float(arb_eval.get("apply_fee_pct", 0.12)),
                    redeem_fee=_safe_float(arb_eval.get("redeem_fee_pct", 0)),
                    net_profit_pct=net_profit,
                    risk_level=risk_level,
                    est_confidence=fund.get("est_confidence", "unknown"),
                    arb_eval=arb_eval,
                )
                opportunities.append(opp)

            # 按净收益排序
            opportunities.sort(key=lambda x: x.net_profit_pct, reverse=True)
            return opportunities

        except Exception as e:
            logger.error(f"扫描套利机会失败: {e}", exc_info=True)
            return []

    def get_strategy_overview(
        self,
        min_premium: float = 2.0,
        min_amount: float = 1000,
        direction: str = "all",
    ) -> StrategyOverview:
        """获取策略总览

        整合扫描、分配、风控，输出一站式策略建议。
        """
        is_trading, market_status = is_trading_hours()

        # 扫描机会
        opportunities = self.scan_opportunities(min_premium, min_amount, direction)

        # 生成建议
        recommendations = []
        for opp in opportunities:
            # 风控检查
            risk = self.check_risk(
                operation=OperationType.SUBSCRIBE if opp.direction == ArbitrageDirection.PREMIUM else OperationType.SELL,
                fund_code=opp.fund_code,
                premium_pct=opp.premium_pct,
                apply_status=opp.apply_status,
                turnover=opp.turnover,
            )

            # 资金分配
            alloc = self.calculate_allocation(
                fund_code=opp.fund_code,
                fund_name=opp.fund_name,
                direction=opp.direction.value,
                premium_pct=opp.premium_pct,
                apply_limit_str=opp.apply_limit,
                apply_status=opp.apply_status,
                est_nav=opp.est_nav,
                fund_price=opp.fund_price,
            )

            # 生成建议
            reasons = []
            risk_warnings = []

            if opp.direction == ArbitrageDirection.PREMIUM:
                if opp.premium_pct >= 3.0:
                    reasons.append(f"高溢价{opp.premium_pct:.2f}%，收益空间充足")
                elif opp.premium_pct >= 2.0:
                    reasons.append(f"溢价率{opp.premium_pct:.2f}%，满足基本套利条件")

                if opp.turnover >= 5000:
                    reasons.append(f"成交额{opp.turnover:.0f}万，流动性充足")
                elif opp.turnover >= 2000:
                    risk_warnings.append(f"成交额{opp.turnover:.0f}万，注意滑点")

                if "暂停" in opp.apply_status or "停止" in opp.apply_status:
                    risk_warnings.append(f"申购状态: {opp.apply_status}")

                action = "立即申购" if risk.passed and opp.net_profit_pct > 1.0 else "谨慎申购" if risk.passed else "暂不操作"
                confidence = "high" if opp.net_profit_pct > 2.0 and risk.passed else "medium" if risk.passed else "low"
            else:
                if opp.premium_pct <= -2.0:
                    reasons.append(f"折价{abs(opp.premium_pct):.2f}%，赎回套利空间充足")
                action = "建议赎回" if risk.passed else "暂不操作"
                confidence = "high" if abs(opp.premium_pct) > 3.0 and risk.passed else "medium" if risk.passed else "low"

            risk_warnings.extend(risk.warnings)

            rec = StrategyRecommendation(
                fund_code=opp.fund_code,
                fund_name=opp.fund_name,
                direction=opp.direction,
                action=action,
                confidence=confidence,
                premium_pct=opp.premium_pct,
                net_profit_pct=opp.net_profit_pct,
                apply_limit=opp.apply_limit,
                apply_status=opp.apply_status,
                reasons=reasons,
                risk_warnings=risk_warnings,
                allocation_plan=alloc,
            )
            recommendations.append(rec)

        # 计算总可用资金
        total_cash = sum(
            _safe_float(b.get("available_cash"))
            for b in self._account_balances.values()
        )

        return StrategyOverview(
            scan_time=datetime.now().isoformat(),
            market_status=market_status,
            opportunities=opportunities,
            recommendations=recommendations,
            risk_settings=RiskSettings(**self._risk_settings),
            account_count=len(list_accounts()),
            total_available_cash=total_cash,
        )

    # ==================== 操作历史 ====================

    def _record_operation(self, record: OperationRecord):
        """记录操作到历史"""
        record.id = str(uuid.uuid4())[:8]
        record.timestamp = datetime.now().isoformat()
        self._operation_history.append(record.model_dump())
        # 保留最近500条
        if len(self._operation_history) > 500:
            self._operation_history = self._operation_history[-500:]
        _save_history(self._operation_history)

    def get_operation_history(
        self,
        limit: int = 50,
        fund_code: str = "",
        operation: str = "",
    ) -> List[dict]:
        """获取操作历史"""
        records = self._operation_history

        if fund_code:
            records = [r for r in records if r.get("fund_code") == fund_code]
        if operation:
            records = [r for r in records if r.get("operation") == operation]

        return records[-limit:]

    def get_pnl_summary(self, days: int = 30) -> PnLSummary:
        """获取损益汇总"""
        records = self._operation_history

        # 按天数过滤
        if days > 0:
            cutoff = datetime.now().timestamp() - days * 86400
            records = [
                r for r in records
                if datetime.fromisoformat(r.get("timestamp", "2000-01-01")).timestamp() > cutoff
            ]

        total_subscribes = sum(1 for r in records if r.get("operation") == OperationType.SUBSCRIBE)
        total_sells = sum(1 for r in records if r.get("operation") == OperationType.SELL)
        total_redeems = sum(1 for r in records if r.get("operation") == OperationType.REDEEM)

        # 已实现损益
        pnls = [_safe_float(r.get("realized_pnl")) for r in records if r.get("realized_pnl") is not None]
        total_realized = sum(pnls)
        wins = sum(1 for p in pnls if p > 0)
        win_rate = (wins / len(pnls) * 100) if pnls else 0.0

        return PnLSummary(
            total_operations=len(records),
            total_subscribes=total_subscribes,
            total_sells=total_sells,
            total_redeems=total_redeems,
            total_realized_pnl=total_realized,
            total_estimated_pnl=0.0,  # TODO: 基于当前持仓估算
            win_rate=win_rate,
            avg_pnl_per_trade=total_realized / len(pnls) if pnls else 0.0,
            best_trade_pnl=max(pnls) if pnls else 0.0,
            worst_trade_pnl=min(pnls) if pnls else 0.0,
            operations=[OperationRecord(**r) for r in records[-20:]],
        )

    def update_operation_pnl(self, operation_id: str, realized_pnl: float, exit_price: float = 0.0):
        """回填操作损益"""
        for record in self._operation_history:
            if record.get("id") == operation_id:
                record["realized_pnl"] = realized_pnl
                record["exit_price"] = exit_price
                if record.get("entry_price") and exit_price:
                    record["pnl_pct"] = (exit_price / record["entry_price"] - 1) * 100
                _save_history(self._operation_history)
                return True
        return False

    # ==================== AutoIt执行 ====================

    def _run_autoit_operation(
        self,
        operation: str,
        fund_code: str = "",
        sell_price: str = "",
        sell_quantity: str = "",
        account_ids: list = None,
        extra_context: dict = None,
    ) -> dict:
        """执行AutoIt脚本操作"""
        if self._running:
            return {"success": False, "message": "已有操作正在运行，请等待完成"}

        self._running = True
        self._current_operation = operation
        self._log_lines = []
        self._start_time = datetime.now()

        try:
            # 确保账户配置已同步
            if not sync_to_autoit():
                self._running = False
                self._current_operation = None
                return {"success": False, "message": "同步账户配置失败"}

            # 检查AutoIt
            autoit_check = self.check_autoit_installed()
            if not autoit_check["installed"]:
                self._running = False
                self._current_operation = None
                return {
                    "success": False,
                    "message": "AutoIt未安装，请先安装: https://www.autoitscript.com/site/autoit/downloads/"
                }

            self._log_lines.append(f"[{datetime.now():%H:%M:%S}] 准备执行: {operation}")
            self._log_lines.append(f"[{datetime.now():%H:%M:%S}] 基金代码: {fund_code}")
            if sell_price:
                self._log_lines.append(f"[{datetime.now():%H:%M:%S}] 卖出价格: {sell_price}")
            if sell_quantity:
                self._log_lines.append(f"[{datetime.now():%H:%M:%S}] 卖出数量: {sell_quantity}")

            # 构建执行命令
            cmd = [self._autoit_path, self._script_path]

            self._log_lines.append(f"[{datetime.now():%H:%M:%S}] 启动AutoIt脚本...")

            # 启动AutoIt进程
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )

            self._log_lines.append(f"[{datetime.now():%H:%M:%S}] 脚本已启动 (PID: {process.pid})")
            self._log_lines.append(f"[{datetime.now():%H:%M:%S}] 请在弹出的AutoIt界面中操作...")

            # 操作记录（先记录，完成后再更新）
            op_record = OperationRecord(
                operation=operation,
                fund_code=fund_code,
                sell_price=_safe_float(sell_price) if sell_price else 0,
                sell_quantity=int(sell_quantity) if sell_quantity else 0,
                account_ids=account_ids or [],
            )
            if extra_context:
                op_record.premium_pct = _safe_float(extra_context.get("premium_pct"))
                op_record.est_nav = _safe_float(extra_context.get("est_nav"))
                op_record.fund_price = _safe_float(extra_context.get("fund_price"))
                op_record.fund_name = extra_context.get("fund_name", "")

            # 更新每日操作计数
            today = date.today().isoformat()
            if self._daily_op_date != today:
                self._daily_op_count = 0
                self._daily_op_date = today
            self._daily_op_count += 1

            # 等待进程完成（异步模式，不阻塞）
            def wait_completion():
                try:
                    stdout, stderr = process.communicate(timeout=600)
                    elapsed = (datetime.now() - self._start_time).total_seconds()
                    if process.returncode == 0:
                        self._log_lines.append(f"[{datetime.now():%H:%M:%S}] 操作完成 (耗时: {elapsed:.1f}秒)")
                        op_record.success = True
                        op_record.message = f"{operation}操作已完成"
                        op_record.elapsed_seconds = elapsed
                        self._last_result = {
                            "success": True,
                            "message": f"{operation}操作已完成",
                            "elapsed": elapsed,
                        }
                    else:
                        self._log_lines.append(f"[{datetime.now():%H:%M:%S}] 操作失败 (返回码: {process.returncode})")
                        if stderr:
                            self._log_lines.append(f"[{datetime.now():%H:%M:%S}] 错误: {stderr.decode('utf-8', errors='replace')}")
                        op_record.success = False
                        op_record.message = f"操作失败 (返回码: {process.returncode})"
                        self._last_result = {
                            "success": False,
                            "message": f"操作失败 (返回码: {process.returncode})",
                        }
                except subprocess.TimeoutExpired:
                    process.kill()
                    self._log_lines.append(f"[{datetime.now():%H:%M:%S}] 操作超时（10分钟），已终止")
                    op_record.success = False
                    op_record.message = "操作超时"
                    self._last_result = {"success": False, "message": "操作超时"}
                except Exception as e:
                    self._log_lines.append(f"[{datetime.now():%H:%M:%S}] 异常: {str(e)}")
                    op_record.success = False
                    op_record.message = str(e)
                    self._last_result = {"success": False, "message": str(e)}
                finally:
                    self._running = False
                    self._current_operation = None
                    # 记录操作历史
                    self._record_operation(op_record)

            thread = threading.Thread(target=wait_completion, daemon=True)
            thread.start()

            return {
                "success": True,
                "message": f"{operation}操作已启动，请在AutoIt界面中完成操作",
                "pid": process.pid,
            }

        except Exception as e:
            self._running = False
            self._current_operation = None
            logger.error(f"执行AutoIt操作失败: {e}", exc_info=True)
            return {"success": False, "message": str(e)}

    def run_operation(
        self,
        operation: str,
        fund_code: str = "162411",
        sell_price: str = "",
        sell_quantity: str = "",
        account_ids: list = None,
        extra_context: dict = None,
    ) -> dict:
        """执行拖拉机操作（带风控）"""
        # 风控预检
        risk = self.check_risk(
            operation=operation,
            fund_code=fund_code,
            premium_pct=_safe_float(extra_context.get("premium_pct")) if extra_context else 0,
            apply_status=extra_context.get("apply_status", "") if extra_context else "",
            turnover=_safe_float(extra_context.get("turnover")) if extra_context else 0,
            account_ids=account_ids,
        )

        if not risk.passed:
            return {
                "success": False,
                "message": f"风控拦截: {'; '.join(risk.blocked_reasons)}",
                "risk_check": risk.model_dump(),
            }

        return self._run_autoit_operation(
            operation=operation,
            fund_code=fund_code,
            sell_price=sell_price,
            sell_quantity=sell_quantity,
            account_ids=account_ids,
            extra_context=extra_context,
        )

    def get_status(self) -> dict:
        """获取当前操作状态"""
        return {
            "running": self._running,
            "current_operation": self._current_operation,
            "log": self._log_lines[-50:] if self._log_lines else [],
            "last_result": self._last_result,
        }

    def get_log(self, tail: int = 50) -> list:
        """获取操作日志"""
        return self._log_lines[-tail:] if self._log_lines else []


# ==================== 单例 ====================

_tractor_service = None


def get_tractor_service() -> TractorService:
    """获取拖拉机服务单例"""
    global _tractor_service
    if _tractor_service is None:
        _tractor_service = TractorService()
    return _tractor_service
