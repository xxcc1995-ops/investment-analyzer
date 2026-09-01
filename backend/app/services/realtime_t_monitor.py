"""实时做T监控调度器（WebSocket 推送后台）

架构：单生产者 → 多订阅者
- 后台 asyncio 循环每 N 秒拉行情 → 算信号 → 风控过滤 → 广播给该 code 的所有 WebSocket 订阅者
- 同步行情拉取（requests）用 asyncio.to_thread 包装，不阻塞事件循环
- 风控熔断：复用 t_position_service 的今日交易次数 / T仓占比 / 止损线
- 信号冷却：同方向信号 N 秒内不重复推送，避免刷屏

交易时段控制（港股 9:30-12:00 / 13:00-16:00 周一至周五）：
- 非交易时段不拉行情，仅每60秒发一次心跳
- 避免无效请求和数据源限流

推送消息类型：
- signal: 做T信号（含买卖价/预期收益/原因）
- quote: 实时行情快照（每轮附带）
- risk: 风控告警（次数达上限/止损/超限）
- heartbeat: 心跳
"""

import asyncio
import logging
import time
import socket
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from fastapi import WebSocket

from app.services.quote_sources.tencent_source import TencentSource

# 富途 OpenAPI 港股真实五档盘口（用户本地 FutuOpenD，默认 127.0.0.1:11111）
# 免费源(腾讯/东方财富)港股盘口量全0；富途需 LV2 权限 + subscribe(ORDER_BOOK) 后
# get_order_book() 才返回真实五档量（get_market_snapshot 仅一档 bid/ask，无五档列表）
try:
    import futu
    from futu import OpenQuoteContext, RET_OK, SubType, KLType
    from app.services.futu_option_service import OPEND_HOST, OPEND_PORT, check_connection
    FUTU_AVAILABLE = True
except (ImportError, Exception):
    FUTU_AVAILABLE = False
    OpenQuoteContext = None
    OPEND_HOST = '127.0.0.1'
    OPEND_PORT = 11111

from app.services.intraday_t_signal_service import (
    analyze_intraday_signal, DEFAULT_CONFIG as SIGNAL_DEFAULT_CONFIG,
)
from app.services.t_position_service import get_position, MAX_DAILY_TRADES

logger = logging.getLogger(__name__)


# 港股交易时段（北京时间）
HK_MARKET_HOURS = {
    "morning": (9, 30, 12, 0),   # 9:30 - 12:00
    "afternoon": (13, 0, 16, 0), # 13:00 - 16:00
}


def _is_hk_market_open(now: Optional[datetime] = None) -> bool:
    """判断港股是否在交易时段"""
    now = now or datetime.now()
    # 周末休市
    if now.weekday() >= 5:
        return False
    h, m = now.hour, now.minute
    minutes = h * 60 + m
    am_start, am_end = 9 * 60 + 30, 12 * 60
    pm_start, pm_end = 13 * 60, 16 * 60
    return (am_start <= minutes <= am_end) or (pm_start <= minutes <= pm_end)


@dataclass
class MonitorConfig:
    """监控配置"""
    enabled: bool = True
    monitor_interval_sec: int = 5          # 交易时段轮询间隔
    idle_interval_sec: int = 60            # 非交易时段心跳间隔
    signal_cooldown_sec: int = 300         # 同方向信号冷却（5分钟）
    spread_threshold_pct: float = 0.30     # 价差阈值
    stop_loss_pct: float = 2.0             # 止损线
    max_t_ratio_pct: float = 30.0          # T仓占比上限（超此值不推买入）
    # 信号引擎参数（透传给 analyze_intraday_signal）
    signal_config: dict = field(default_factory=lambda: dict(SIGNAL_DEFAULT_CONFIG))


class RealtimeTMonitor:
    """实时做T监控调度器（单例）"""

    _instance: Optional["RealtimeTMonitor"] = None
    _lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._subscribers: dict[str, set[WebSocket]] = {}  # code -> set(ws)
        self._watching_codes: set[str] = set()
        self._last_signal: dict[str, tuple[str, str]] = {}  # code -> (timestamp, direction)
        self._config = MonitorConfig()
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._tencent = TencentSource()
        self._futu_ctx = None  # 富途 OpenQuoteContext 懒初始化（真实五档盘口）
        self._futu_subscribed = set()  # 已订阅 ORDER_BOOK 的标的（富途五档前置条件）
        self._futu_failed_time = 0.0  # 富途失败时间戳（失败后冷却，避免拖慢轮询）

    @property
    def config(self) -> MonitorConfig:
        return self._config

    def update_config(self, **kwargs):
        """更新监控配置"""
        for k, v in kwargs.items():
            if k == "signal_config" and isinstance(v, dict):
                self._config.signal_config.update(v)
            elif hasattr(self._config, k):
                setattr(self._config, k, v)
        logger.info(f"实时做T监控配置已更新: {kwargs}")

    def get_status(self) -> dict:
        """获取监控状态"""
        return {
            "running": self._running,
            "watching_codes": list(self._watching_codes),
            "subscriber_count": {c: len(s) for c, s in self._subscribers.items()},
            "config": {
                "enabled": self._config.enabled,
                "monitor_interval_sec": self._config.monitor_interval_sec,
                "signal_cooldown_sec": self._config.signal_cooldown_sec,
                "spread_threshold_pct": self._config.spread_threshold_pct,
                "stop_loss_pct": self._config.stop_loss_pct,
                "max_t_ratio_pct": self._config.max_t_ratio_pct,
                "market_open": _is_hk_market_open(),
            },
        }

    async def start(self):
        """启动监控后台任务"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("实时做T监控调度器已启动")

    async def stop(self):
        """停止监控"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("实时做T监控调度器已停止")

    async def subscribe(self, code: str, ws: WebSocket):
        """订阅某只股票的实时信号"""
        if code not in self._subscribers:
            self._subscribers[code] = set()
        self._subscribers[code].add(ws)
        self._watching_codes.add(code)
        # 首次订阅立即推一次状态
        await ws.send_json({
            "type": "subscribed",
            "code": code,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "market_open": _is_hk_market_open(),
            "message": f"已订阅 {code} 实时做T信号",
        })
        logger.info(f"WebSocket 订阅 {code}，当前订阅者: {len(self._subscribers[code])}")

    async def unsubscribe(self, code: str, ws: WebSocket):
        """取消订阅"""
        if code in self._subscribers:
            self._subscribers[code].discard(ws)
            if not self._subscribers[code]:
                del self._subscribers[code]
                self._watching_codes.discard(code)
        logger.info(f"WebSocket 取消订阅 {code}，剩余订阅者: {len(self._subscribers.get(code, set()))}")

    def watch(self, code: str):
        """启动时预订阅标的（无需打开页面即开始监控计算，满足"每次启动即调用"）"""
        self._watching_codes.add(code)
        logger.info(f"预订阅监控标的 {code}（后端启动即激活）")

    async def _monitor_loop(self):
        """监控主循环"""
        logger.info("实时做T监控循环开始")
        while self._running:
            try:
                if not self._config.enabled:
                    await asyncio.sleep(self._config.idle_interval_sec)
                    continue

                if not self._watching_codes:
                    await asyncio.sleep(self._config.idle_interval_sec)
                    continue

                market_open = _is_hk_market_open()

                if market_open:
                    # 交易时段：拉行情算信号
                    for code in list(self._watching_codes):
                        try:
                            await self._process_one(code)
                        except Exception as e:
                            logger.warning(f"处理 {code} 异常: {e}")
                    await asyncio.sleep(self._config.monitor_interval_sec)
                else:
                    # 非交易时段：发心跳
                    for code in list(self._watching_codes):
                        await self._broadcast(code, {
                            "type": "heartbeat",
                            "code": code,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "market_open": False,
                            "message": "非交易时段，监控休眠",
                        })
                    await asyncio.sleep(self._config.idle_interval_sec)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控循环异常: {e}", exc_info=True)
                await asyncio.sleep(self._config.idle_interval_sec)

    async def _process_one(self, code: str):
        """处理单只股票：拉行情 → 算信号 → 风控 → 广播"""
        # 同步行情拉取放线程池
        quote_data = await asyncio.to_thread(self._fetch_quote_bundle, code)
        if not quote_data:
            return

        minute_klines, kline_5min, order_book, quote = quote_data

        # 推送实时行情快照
        if quote:
            await self._broadcast(code, {
                "type": "quote",
                "code": code,
                "data": quote,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

        # 算信号
        signal = analyze_intraday_signal(
            code=code,
            name=quote.get("name", code) if quote else code,
            minute_klines=minute_klines,
            kline_5min=kline_5min,
            order_book=order_book,
            config=self._config.signal_config,
        )

        # 风控过滤
        signal, risk_msg = self._apply_risk_control(code, signal)

        # 常驻操作参考：即便 hold 也每轮广播，供前端常驻展示买卖区间/倾向
        await self._broadcast(code, {
            "type": "assessment",
            "code": code,
            "data": signal.to_dict(),
            "timestamp": signal.timestamp,
        })

        # 信号冷却
        if signal.signal_type != "hold" and not self._is_cooled_down(code, signal.signal_type):
            # 推送信号
            await self._broadcast(code, {
                "type": "signal",
                "code": code,
                "data": signal.to_dict(),
                "timestamp": signal.timestamp,
            })
            self._last_signal[code] = (signal.timestamp, signal.signal_type)
        elif signal.signal_type != "hold":
            # 冷却中，不推
            logger.debug(f"{code} {signal.signal_type} 信号冷却中，跳过推送")

        # 推送风控告警（独立于信号）
        if risk_msg:
            await self._broadcast(code, {
                "type": "risk",
                "code": code,
                "severity": risk_msg.get("severity", "medium"),
                "message": risk_msg["message"],
                "action": risk_msg.get("action", ""),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

    def _ensure_futu_ctx(self) -> bool:
        """确保富途连接可用（socket 预检 + 失败冷却），可用返回 True。

        socket 预检必要性：FutuOpenD 未运行时 OpenQuoteContext 构造会内部重试
        14 次 × 8 秒 ≈ 112 秒，足以拖垮 5 秒轮询的监控循环。
        """
        if not FUTU_AVAILABLE:
            return False
        if self._futu_failed_time and time.time() - self._futu_failed_time < 300:
            return False
        if self._futu_ctx is not None:
            return True
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect((OPEND_HOST, OPEND_PORT))
            s.close()
        except Exception:
            self._futu_failed_time = time.time()
            return False
        try:
            self._futu_ctx = OpenQuoteContext(host=OPEND_HOST, port=OPEND_PORT)
            return True
        except Exception as e:
            logger.warning(f"富途连接建立失败: {e}")
            self._futu_failed_time = time.time()
            return False

    def _get_futu_5min_kline(self, code: str, count: int = 300) -> list:
        """富途 5 分钟 K 线（腾讯 mkline 接口对港股已失效，见 get_best_5min_kline 说明）

        返回 [{'time','open','close','high','low','volume','amount'}, ...]，
        失败返回空列表（不编造）。
        """
        if not self._ensure_futu_ctx():
            return []
        try:
            stock_code = code if code.startswith('HK.') else f'HK.{code}'
            sub_key = f'{stock_code}#K5'
            if sub_key not in self._futu_subscribed:
                sret, smsg = self._futu_ctx.subscribe([stock_code], [SubType.K_5M])
                if sret != RET_OK:
                    logger.warning(f"富途订阅5分钟K失败 {stock_code}: {smsg}")
                    return []
                self._futu_subscribed.add(sub_key)

            ret, kl = self._futu_ctx.get_cur_kline(stock_code, min(count, 1000), KLType.K_5M)
            if ret != RET_OK or kl is None or getattr(kl, 'empty', True):
                return []
            out = []
            for _, r in kl.iterrows():
                try:
                    out.append({
                        'time': str(r['time_key']),
                        'open': float(r['open']),
                        'close': float(r['close']),
                        'high': float(r['high']),
                        'low': float(r['low']),
                        'volume': float(r['volume']),
                        'amount': float(r.get('turnover', 0) or 0),
                    })
                except (KeyError, ValueError, TypeError):
                    continue
            return out
        except Exception as e:
            logger.warning(f"富途5分钟K获取失败 {code}: {e}")
            self._futu_failed_time = time.time()
            return []

    def _get_futu_order_book(self, code: str) -> Optional[dict]:
        """富途 OpenAPI 港股真实五档盘口（用户本地 FutuOpenD，需港股 LV2 权限）

        必须先 subscribe(SubType.ORDER_BOOK) 才能 get_order_book()；
        get_market_snapshot 只返回一档 bid_price/ask_price，没有五档列表。
        富途连不上返回 None，由调用方落回腾讯（腾讯港股盘口量恒为 0）。
        """
        if not self._ensure_futu_ctx():
            return None
        try:
            stock_code = code if code.startswith('HK.') else f'HK.{code}'

            # 五档盘口前置条件：必须先订阅 ORDER_BOOK（需 LV2 权限），
            # get_market_snapshot 只返回一档 bid_price/ask_price，没有五档列表
            if stock_code not in self._futu_subscribed:
                sret, smsg = self._futu_ctx.subscribe([stock_code], [SubType.ORDER_BOOK])
                if sret != RET_OK:
                    logger.warning(f"富途订阅五档盘口失败 {stock_code}: {smsg}（需港股LV2权限）")
                    self._futu_failed_time = time.time()
                    return None
                self._futu_subscribed.add(stock_code)

            ret, ob_raw = self._futu_ctx.get_order_book(stock_code, num=5)
            if ret != RET_OK or not isinstance(ob_raw, dict):
                return None

            # 富途返回 {'Bid': [(price, volume, order_count, {}), ...], 'Ask': [...]}
            def _levels(raw):
                out = []
                for item in (raw or [])[:5]:
                    try:
                        out.append({
                            'price': float(item[0]),
                            'volume': float(item[1]),
                            'order_count': int(item[2]) if len(item) > 2 else 0,
                        })
                    except (TypeError, ValueError, IndexError):
                        continue
                while len(out) < 5:
                    out.append({'price': 0.0, 'volume': 0.0, 'order_count': 0})
                return out

            bids = _levels(ob_raw.get('Bid'))
            asks = _levels(ob_raw.get('Ask'))
            b1, a1 = bids[0]['price'], asks[0]['price']
            if b1 <= 0 and a1 <= 0:
                return None  # 盘口无有效价（休市/停牌），交给腾讯兜底

            spread = a1 - b1 if b1 > 0 and a1 > 0 else 0
            mid = (a1 + b1) / 2 if spread > 0 else (b1 or a1)
            current_price = mid
            total_bid = sum(b['volume'] for b in bids)
            total_ask = sum(a['volume'] for a in asks)
            imbalance = total_bid - total_ask
            imbalance_pct = round(imbalance / (total_bid + total_ask) * 100, 2) if (total_bid + total_ask) > 0 else 0
            return {
                'bids': bids, 'asks': asks,
                'spread': round(spread, 3),
                'spread_pct': round(spread / mid * 100, 3) if mid > 0 else 0,
                'mid_price': round(mid, 3),
                'total_bid_volume': total_bid,
                'total_ask_volume': total_ask,
                'imbalance': imbalance,
                'imbalance_pct': imbalance_pct,
                'current_price': current_price,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'source': '富途OpenAPI',
            }
        except Exception as e:
            logger.warning(f"富途盘口获取失败 {code}: {e}")
            self._futu_failed_time = time.time()
            try:
                if self._futu_ctx:
                    self._futu_ctx.close()
            except Exception:
                pass
            self._futu_ctx = None
            self._futu_subscribed.clear()  # 连接重建后需重新订阅
            return None

    def _fetch_quote_bundle(self, code: str) -> Optional[tuple]:
        """同步拉取行情包（在线程池中执行）

        返回 (minute_klines, kline_5min, order_book, quote_dict)
        """
        try:
            if not self._tencent.is_connected():
                self._tencent.connect()

            minute = self._tencent.get_minute_kline(code, "HK")
            # 5分钟K优先富途（腾讯 mkline 接口对港股已失效）
            k5 = self._get_futu_5min_kline(code, 300) or self._tencent.get_5min_kline(code, "HK", 300)
            # 盘口优先富途（真实五档量），腾讯兜底（量0）
            ob = self._get_futu_order_book(code)
            if ob is None:
                ob = self._tencent.get_order_book(code, "HK")
            quote = self._tencent.get_quote(code, "HK")

            if not quote:
                logger.warning(f"腾讯行情拉取失败 {code}")
                return None

            return (minute, k5, ob, quote.to_dict())
        except Exception as e:
            logger.warning(f"行情包拉取异常 {code}: {e}")
            return None

    def _apply_risk_control(self, code: str, signal) -> tuple:
        """风控过滤：决定信号是否推送，并生成风控告警

        返回 (可能修改后的signal, risk_msg或None)
        """
        risk_msg = None
        try:
            pos = get_position(code, "HK")
        except Exception:
            pos = None

        if not pos:
            # 无持仓，买入信号需要先初始化（提醒用户）
            if signal.signal_type == "buy" and signal.strength in ("strong", "medium"):
                risk_msg = {
                    "severity": "info",
                    "message": f"检测到买入信号但无 {code} 持仓记录，做T需先初始化底仓",
                    "action": "前往做T系统初始化持仓（7成底仓+3成T仓）",
                }
            return signal, risk_msg

        # 有持仓：检查风控
        total_shares = pos.get("total_shares", 0)
        base_shares = pos.get("base_shares", 0)
        t_shares = pos.get("t_shares", 0)
        avg_cost = pos.get("avg_cost", 0)
        t_trades = pos.get("t_trades", [])
        today = datetime.now().strftime("%Y-%m-%d")
        today_trades = [t for t in t_trades if t.get("time", "").startswith(today)]

        # 1. 今日交易次数
        if len(today_trades) >= MAX_DAILY_TRADES:
            if signal.signal_type == "buy":
                signal.signal_type = "hold"
                signal.strength = "neutral"
                signal.reasons.append(f"[风控] 今日已交易{len(today_trades)}次达上限{MAX_DAILY_TRADES}，买入信号被抑制")
            risk_msg = {
                "severity": "high",
                "message": f"今日已交易{len(today_trades)}次，达到每日上限{MAX_DAILY_TRADES}次",
                "action": "停止做T，等待下一交易日",
            }

        # 2. T仓占比
        if total_shares > 0:
            t_ratio = t_shares / total_shares * 100
            if t_ratio > self._config.max_t_ratio_pct and signal.signal_type == "buy":
                signal.signal_type = "hold"
                signal.strength = "neutral"
                signal.reasons.append(f"[风控] T仓占比{t_ratio:.1f}%超{self._config.max_t_ratio_pct}%上限，买入信号被抑制（优先卖出降仓）")
                if not risk_msg:
                    risk_msg = {
                        "severity": "high",
                        "message": f"T仓占比{t_ratio:.1f}%超过{self._config.max_t_ratio_pct}%安全线",
                        "action": "优先卖出做T仓降低风险敞口",
                    }

        # 3. 止损线（持仓浮亏）
        if avg_cost > 0 and signal.current_price > 0:
            loss_pct = (avg_cost - signal.current_price) / avg_cost * 100
            if loss_pct >= self._config.stop_loss_pct:
                risk_msg = {
                    "severity": "high",
                    "message": f"持仓浮亏{loss_pct:.2f}%达止损线{self._config.stop_loss_pct}%（成本HK${avg_cost:.2f} vs 现价HK${signal.current_price:.2f}）",
                    "action": f"考虑止损卖出，避免扩大亏损",
                }

        return signal, risk_msg

    def _is_cooled_down(self, code: str, direction: str) -> bool:
        """检查信号是否在冷却期内（同方向 N 秒内不重复）"""
        last = self._last_signal.get(code)
        if not last:
            return False
        last_ts_str, last_dir = last
        if last_dir != direction:
            return False  # 反方向信号不冷却
        try:
            last_ts = datetime.strptime(last_ts_str, "%Y-%m-%d %H:%M:%S")
            elapsed = (datetime.now() - last_ts).total_seconds()
            return elapsed < self._config.signal_cooldown_sec
        except ValueError:
            return False

    async def _broadcast(self, code: str, message: dict):
        """广播消息给该 code 的所有订阅者"""
        subs = self._subscribers.get(code, set()).copy()
        dead = []
        for ws in subs:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        # 清理断开的连接
        for ws in dead:
            await self.unsubscribe(code, ws)


# 全局单例
realtime_monitor = RealtimeTMonitor()


def get_best_5min_kline(code: str, market: str = "HK", count: int = 300) -> list:
    """获取 5 分钟 K 线：优先富途，腾讯 mkline 兜底。

    ⚠️ 实测（2026-08-06）：腾讯 mkline 接口 web.ifzq.gtimg.cn 已 301 重定向到
    web3.ifzq.gtimg.cn（DNS 不可解析），裸域 ifzq.gtimg.cn 返回 param error，
    该免费接口对港股实质失效。故 5 分钟 K 以富途为主源。
    """
    if market.upper() == "HK":
        kl = realtime_monitor._get_futu_5min_kline(code, count)
        if kl:
            return kl
    return realtime_monitor._tencent.get_5min_kline(code, market, count) or []


def get_best_order_book(code: str, market: str = "HK") -> Optional[dict]:
    """获取最优可用盘口：优先富途真实五档（LV2），失败落回腾讯。

    供 REST 端点与监控循环共用，避免两处逻辑分叉。
    腾讯免费港股源盘口量恒为 0（实测），仅在富途不可用时作为价格占位兜底，
    返回结果的 source 字段标明真实来源，前端据此判断盘口失衡是否可信。
    """
    if market.upper() == "HK":
        ob = realtime_monitor._get_futu_order_book(code)
        if ob:
            return ob
    ob = realtime_monitor._tencent.get_order_book(code, market)
    if ob and 'source' not in ob:
        ob['source'] = '腾讯(盘口量恒为0,仅价格可用)'
    return ob
