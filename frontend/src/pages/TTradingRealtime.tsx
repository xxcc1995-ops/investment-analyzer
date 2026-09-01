import { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'
import { Card, Tag, Button, Modal, InputNumber, message, Switch, Input, Collapse } from 'antd'
import ReactECharts from 'echarts-for-react'

const API_BASE = '/api/t-realtime'
const T_TRADING_API = '/api/t-trading'
const TARGET_CODE = '00700'
const TARGET_NAME = '腾讯控股'

// ============================================================
// 类型
// ============================================================

interface QuoteData {
  code: string; name: string; price: number; open: number; high: number; low: number
  pre_close: number; volume: number; amount: number; change_pct: number; change_amount: number
  bids: { price: number; volume: number }[]
  asks: { price: number; volume: number }[]
  trade_time: string; source: string
}

interface OrderBook {
  bids: { price: number; volume: number }[]
  asks: { price: number; volume: number }[]
  spread: number; spread_pct: number; mid_price: number
  total_bid_volume: number; total_ask_volume: number
  imbalance: number; imbalance_pct: number; current_price: number; timestamp: string
}

interface MinuteBar { time: string; price: number; avg: number; volume: number }

interface SignalData {
  code: string; name: string
  signal_type: 'buy' | 'sell' | 'hold'
  strength: 'strong' | 'medium' | 'weak' | 'neutral'
  current_price: number; buy_price: number; sell_price: number
  expected_profit_pct: number; expected_profit_hkd: number
  reasons: string[]; indicators: Record<string, any>; timestamp: string
}

interface MonitorConfig {
  enabled: boolean; monitor_interval_sec: number; signal_cooldown_sec: number
  spread_threshold_pct: number; stop_loss_pct: number; max_t_ratio_pct: number
}

interface RiskMsg { severity: string; message: string; action: string; timestamp: string }

interface SignalItem extends SignalData { id: string }

// ============================================================
// 工具
// ============================================================

const fmtHKD = (n: number) => `HK$${n.toFixed(2)}`
const colorByChange = (pct: number) => (pct >= 0 ? '#e24b4a' : '#1d9e75') // 涨红跌绿
const strengthColor: Record<string, string> = {
  strong: '#e24b4a', medium: '#ef9f27', weak: '#85b7eb', neutral: '#888',
}
const strengthLabel: Record<string, string> = {
  strong: '强信号', medium: '中信号', weak: '弱信号', neutral: '观望',
}

// 提示音（Web Audio API 生成，避免依赖音频文件）
const playBeep = (type: 'buy' | 'sell' | 'risk' = 'buy') => {
  try {
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain); gain.connect(ctx.destination)
    osc.type = 'sine'
    osc.frequency.value = type === 'risk' ? 440 : type === 'sell' ? 660 : 880
    gain.gain.setValueAtTime(0.3, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3)
    osc.start(); osc.stop(ctx.currentTime + 0.3)
    setTimeout(() => ctx.close(), 400)
  } catch (e) { /* 静默 */ }
}

// 桌面通知
const notifyDesktop = (title: string, body: string) => {
  if ('Notification' in window && Notification.permission === 'granted') {
    try { new Notification(title, { body }) } catch { /* ignore */ }
  }
}

// ============================================================
// 主组件
// ============================================================

export default function TTradingRealtime() {
  const [quote, setQuote] = useState<QuoteData | null>(null)
  const [orderbook, setOrderbook] = useState<OrderBook | null>(null)
  const [minuteData, setMinuteData] = useState<MinuteBar[]>([])
  const [signals, setSignals] = useState<SignalItem[]>([])
  const [riskMsgs, setRiskMsgs] = useState<RiskMsg[]>([])
  const [config, setConfig] = useState<MonitorConfig | null>(null)
  const [status, setStatus] = useState<any>(null)
  const [assessment, setAssessment] = useState<SignalData | null>(null)
  const [wsConnected, setWsConnected] = useState(false)
  const [execModal, setExecModal] = useState<{ open: boolean; signal: SignalData | null }>({ open: false, signal: null })
  const [execShares, setExecShares] = useState(100)
  const [execPrice, setExecPrice] = useState(0)
  const [soundOn, setSoundOn] = useState(true)
  const [notifyOn, setNotifyOn] = useState(true)
  const wsRef = useRef<WebSocket | null>(null)

  // ---------- 请求桌面通知权限 ----------
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }, [])

  // ---------- 拉取初始数据 ----------
  const loadInitial = useCallback(async () => {
    try {
      const [q, ob, min, cfg, st, sig] = await Promise.all([
        axios.get(`${API_BASE}/quote/${TARGET_CODE}`).catch(() => null),
        axios.get(`${API_BASE}/orderbook/${TARGET_CODE}`).catch(() => null),
        axios.get(`${API_BASE}/minute/${TARGET_CODE}`).catch(() => null),
        axios.get(`${API_BASE}/config`).catch(() => null),
        axios.get(`${API_BASE}/status`).catch(() => null),
        axios.get(`${API_BASE}/signal/${TARGET_CODE}`).catch(() => null),
      ])
      if (q?.data && !q.data.error) setQuote(q.data)
      if (ob?.data && !ob.data.error) setOrderbook(ob.data)
      if (min?.data?.data) setMinuteData(min.data.data)
      if (cfg?.data) setConfig(cfg.data)
      if (st?.data) setStatus(st.data)
      if (sig?.data && !sig.data.error) setAssessment(sig.data)
    } catch (e) { console.error('初始数据加载失败', e) }
  }, [])

  // ---------- WebSocket 连接 ----------
  useEffect(() => {
    loadInitial()
    const wsUrl = `ws://${window.location.host}/api/t-realtime/ws/${TARGET_CODE}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => setWsConnected(true)
    ws.onclose = () => {
      setWsConnected(false)
      // 3秒后自动重连
      setTimeout(() => {
        if (wsRef.current?.readyState !== WebSocket.OPEN) {
          wsRef.current = new WebSocket(wsUrl)
        }
      }, 3000)
    }
    ws.onerror = () => setWsConnected(false)
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        switch (msg.type) {
          case 'quote':
            if (msg.data) {
              setQuote(msg.data)
              setOrderbook(prev => {
                // 从 quote 更新盘口（quote 含 bids/asks）
                const q = msg.data
                if (q.bids && q.asks) {
                  const total_bid = q.bids.reduce((s: number, b: any) => s + b.volume, 0)
                  const total_ask = q.asks.reduce((s: number, a: any) => s + a.volume, 0)
                  const spread = q.asks[0]?.price - q.bids[0]?.price || 0
                  const mid = (q.asks[0]?.price + q.bids[0]?.price) / 2 || q.price
                  return {
                    bids: q.bids, asks: q.asks, spread,
                    spread_pct: mid > 0 ? spread / mid * 100 : 0,
                    mid_price: mid, total_bid_volume: total_bid, total_ask_volume: total_ask,
                    imbalance: total_bid - total_ask,
                    imbalance_pct: (total_bid + total_ask) > 0 ? (total_bid - total_ask) / (total_bid + total_ask) * 100 : 0,
                    current_price: q.price, timestamp: q.trade_time,
                  }
                }
                return prev
              })
            }
            break
          case 'signal':
            if (msg.data && msg.data.signal_type !== 'hold') {
              const sig: SignalItem = { ...msg.data, id: `${Date.now()}-${Math.random()}` }
              setSignals(prev => [sig, ...prev].slice(0, 50))
              if (soundOn) playBeep(sig.signal_type)
              if (notifyOn) {
                notifyDesktop(
                  `${sig.signal_type === 'buy' ? '买入' : '卖出'}信号 · ${TARGET_NAME}`,
                  `建议${sig.signal_type === 'buy' ? '买' : '卖'}价 ${fmtHKD(sig.signal_type === 'buy' ? sig.buy_price : sig.sell_price)}，预期收益 ${sig.expected_profit_pct}%`
                )
              }
              message.info({
                content: `${strengthLabel[sig.strength]}：建议${sig.signal_type === 'buy' ? '买入' : '卖出'} ${fmtHKD(sig.signal_type === 'buy' ? sig.buy_price : sig.sell_price)}`,
                duration: 5,
              })
            }
            break
          case 'assessment':
            if (msg.data) setAssessment(msg.data)
            break
          case 'risk':
            if (msg.message) {
              setRiskMsgs(prev => [{ severity: msg.severity, message: msg.message, action: msg.action, timestamp: msg.timestamp }, ...prev].slice(0, 20))
              if (soundOn) playBeep('risk')
              if (notifyOn) notifyDesktop(`风控提醒 · ${TARGET_NAME}`, msg.message)
            }
            break
          case 'heartbeat':
            // 更新市场状态
            setStatus((prev: any) => prev ? { ...prev, market_open: msg.market_open } : prev)
            break
        }
      } catch (e) { /* 解析失败忽略 */ }
    }

    return () => { ws.close() }
  }, [loadInitial, soundOn, notifyOn])

  // ---------- 一键录入做T ----------
  const openExecModal = (signal: SignalData) => {
    setExecModal({ open: true, signal })
    setExecShares(100)
    setExecPrice(signal.signal_type === 'sell' ? signal.sell_price : signal.buy_price)
  }

  const handleExecute = async () => {
    if (!execModal.signal) return
    const action = execModal.signal.signal_type === 'buy' ? 'buy_t' : 'sell_t'
    try {
      const res = await axios.post(`${T_TRADING_API}/execute`, {
        code: TARGET_CODE, market: 'HK', action, shares: execShares, price: execPrice,
        note: `实时做T信号(${strengthLabel[execModal.signal.strength]})`,
      })
      if (res.data.error) {
        message.error(res.data.error)
      } else {
        message.success(`${action === 'buy_t' ? '买入' : '卖出'}做T记录成功，盈亏 ${fmtHKD(res.data.trade_pnl || 0)}`)
        setExecModal({ open: false, signal: null })
      }
    } catch (e: any) {
      message.error(e?.response?.data?.error || '录入失败，请先在做T系统初始化持仓')
    }
  }

  // ---------- 更新配置 ----------
  const updateConfig = async (key: keyof MonitorConfig, value: any) => {
    try {
      await axios.post(`${API_BASE}/config?${key}=${value}`)
      message.success(`${key} 已更新为 ${value}`)
      loadInitial()
    } catch { message.error('配置更新失败') }
  }

  // ---------- ECharts 分时图 ----------
  const getMinuteChartOption = () => {
    if (!minuteData.length) return { title: { text: '暂无分时数据', left: 'center', top: 'center', textStyle: { color: '#888' } } }
    const times = minuteData.map(d => d.time)
    const prices = minuteData.map(d => d.price)
    const avgs = minuteData.map(d => d.avg)
    const vwap = quote && orderbook ? orderbook.mid_price : prices[prices.length - 1]
    const support = assessment?.indicators?.nearest_support || signals[0]?.indicators?.nearest_support
    const resistance = assessment?.indicators?.nearest_resistance || signals[0]?.indicators?.nearest_resistance

    return {
      backgroundColor: 'transparent',
      grid: { left: 50, right: 50, top: 30, bottom: 30 },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: times, axisLabel: { fontSize: 10 } },
      yAxis: { type: 'value', scale: true, axisLabel: { formatter: (v: number) => v.toFixed(1) } },
      series: [
        {
          name: '价格', type: 'line', data: prices, smooth: true, symbol: 'none',
          lineStyle: { width: 1.5, color: '#185fa5' },
          areaStyle: { color: 'rgba(24,95,165,0.08)' },
          markLine: {
            symbol: 'none', silent: true,
            data: [
              support > 0 ? { yAxis: support, name: '支撑', lineStyle: { color: '#1d9e75', type: 'dashed' }, label: { formatter: '支撑 {c}', color: '#1d9e75' } } : null,
              resistance > 0 ? { yAxis: resistance, name: '阻力', lineStyle: { color: '#e24b4a', type: 'dashed' }, label: { formatter: '阻力 {c}', color: '#e24b4a' } } : null,
              { yAxis: vwap, name: 'VWAP', lineStyle: { color: '#ef9f27', type: 'dotted' }, label: { formatter: 'VWAP', color: '#ef9f27' } },
            ].filter(Boolean),
          },
        },
        { name: '均价', type: 'line', data: avgs, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#ef9f27', type: 'dotted' } },
      ],
    }
  }

  // ---------- 渲染 ----------
  const changePct = quote?.change_pct || 0
  const changeColor = colorByChange(changePct)

  return (
    <div style={{ padding: 16, background: '#f6f8fa', minHeight: 'calc(100vh - 60px)' }}>
      {/* 顶部行情条 */}
      <Card size="small" style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
            <span style={{ fontSize: 18, fontWeight: 500 }}>{TARGET_NAME}</span>
            <span style={{ fontSize: 12, color: '#888' }}>{TARGET_CODE}.HK</span>
            {quote && (
              <>
                <span style={{ fontSize: 28, fontWeight: 600, color: changeColor }}>{fmtHKD(quote.price)}</span>
                <span style={{ color: changeColor, fontSize: 14 }}>
                  {changePct >= 0 ? '+' : ''}{changePct}% ({changePct >= 0 ? '+' : ''}{quote.change_amount})
                </span>
              </>
            )}
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <Tag color={wsConnected ? 'green' : 'red'}>{wsConnected ? 'WS已连接' : 'WS断开'}</Tag>
            <Tag color={status?.market_open ? 'blue' : 'default'}>{status?.market_open ? '交易中' : '休市'}</Tag>
            <Switch checked={soundOn} onChange={setSoundOn} checkedChildren="声音" unCheckedChildren="静音" size="small" />
            <Switch checked={notifyOn} onChange={setNotifyOn} checkedChildren="通知" unCheckedChildren="关" size="small" />
          </div>
        </div>
        {quote && (
          <div style={{ marginTop: 8, fontSize: 12, color: '#666', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            <span>开 {fmtHKD(quote.open)}</span>
            <span>高 <span style={{ color: '#e24b4a' }}>{fmtHKD(quote.high)}</span></span>
            <span>低 <span style={{ color: '#1d9e75' }}>{fmtHKD(quote.low)}</span></span>
            <span>昨收 {fmtHKD(quote.pre_close)}</span>
            <span>量 {(quote.volume / 1000).toFixed(0)}K股</span>
            <span>额 {(quote.amount / 1000000).toFixed(2)}M</span>
            <span style={{ color: '#888' }}>{quote.trade_time} · {quote.source}</span>
          </div>
        )}
      </Card>

      {/* 常驻操作参考横幅：始终显示买卖区间与倾向，出信号时高亮提示 */}
      {assessment && (() => {
        const isAction = assessment.signal_type !== 'hold'
        const aColor = isAction
          ? (assessment.signal_type === 'buy' ? '#e24b4a' : '#1d9e75')
          : (assessment.bias === 'bullish' ? '#e24b4a' : assessment.bias === 'bearish' ? '#1d9e75' : '#888')
        const aLabel = isAction
          ? (assessment.signal_type === 'buy' ? '买入做T' : '卖出做T')
          : (assessment.bias_text || '观望')
        const refPrice = isAction
          ? (assessment.signal_type === 'buy' ? assessment.buy_price : assessment.sell_price)
          : assessment.buy_price
        const sup = assessment.indicators?.nearest_support
        const res = assessment.indicators?.nearest_resistance
        return (
          <Card size="small" style={{
            marginBottom: 12,
            border: `1px solid ${isAction ? aColor : '#e8e8e8'}`,
            background: isAction
              ? (assessment.signal_type === 'buy' ? '#fff5f5' : '#f5fff9')
              : '#fafafa',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <Tag color={isAction ? (assessment.signal_type === 'buy' ? 'red' : 'green') : 'default'}
                  style={{ fontSize: 14, padding: '4px 10px' }}>{aLabel}</Tag>
                {isAction ? (
                  <span style={{ fontSize: 20, fontWeight: 700, color: aColor }}>
                    建议{assessment.signal_type === 'buy' ? '买入' : '卖出'}做T @ {fmtHKD(refPrice)}
                  </span>
                ) : (
                  <span style={{ fontSize: 15, color: '#555' }}>
                    当前观望（{assessment.bias_text}），参考下方买卖区间
                  </span>
                )}
              </div>
              <div style={{ fontSize: 13, color: '#666', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                <span>可买区(支撑) <b style={{ color: '#1d9e75' }}>{sup ? fmtHKD(sup) : '—'}</b></span>
                <span>可卖区(阻力) <b style={{ color: '#e24b4a' }}>{res ? fmtHKD(res) : '—'}</b></span>
              </div>
              <Button type="primary" onClick={() => openExecModal(assessment)}>一键录入做T</Button>
            </div>
            {assessment.reasons?.length > 0 && (
              <div style={{ marginTop: 6, fontSize: 12, color: '#666' }}>
                {assessment.reasons.slice(0, 2).map((r: string, i: number) => <div key={i}>{r}</div>)}
              </div>
            )}
          </Card>
        )
      })()}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 12 }}>
        {/* 左：分时图 + 五档 */}
        <div>
          <Card size="small" title="分时走势（1分钟）" extra={<Button size="small" onClick={loadInitial}>刷新</Button>} style={{ marginBottom: 12 }}>
            <ReactECharts option={getMinuteChartOption()} style={{ height: 320 }} />
          </Card>
          <Card size="small" title="五档买卖盘">
            {orderbook ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 13 }}>
                <div>
                  <div style={{ fontWeight: 500, marginBottom: 4, color: '#1d9e75' }}>买盘</div>
                  {orderbook.bids.map((b, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
                      <span>买{i + 1}</span>
                      <span style={{ color: '#1d9e75' }}>{fmtHKD(b.price)}</span>
                      <span style={{ color: '#888' }}>{b.volume}</span>
                    </div>
                  ))}
                </div>
                <div>
                  <div style={{ fontWeight: 500, marginBottom: 4, color: '#e24b4a' }}>卖盘</div>
                  {orderbook.asks.map((a, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
                      <span>卖{i + 1}</span>
                      <span style={{ color: '#e24b4a' }}>{fmtHKD(a.price)}</span>
                      <span style={{ color: '#888' }}>{a.volume}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : <div style={{ color: '#888' }}>暂无盘口数据</div>}
            {orderbook && (
              <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid #eee', fontSize: 12, color: '#666' }}>
                <span>价差 {orderbook.spread.toFixed(3)} ({orderbook.spread_pct.toFixed(3)}%) · </span>
                <span>失衡 <span style={{ color: orderbook.imbalance_pct >= 0 ? '#e24b4a' : '#1d9e75' }}>{orderbook.imbalance_pct.toFixed(1)}%</span> · </span>
                <span>买总量 {orderbook.total_bid_volume} / 卖总量 {orderbook.total_ask_volume}</span>
              </div>
            )}
          </Card>
        </div>

        {/* 右：信号流 + 风控 */}
        <div>
          <Card size="small" title={`实时信号流 (${signals.length})`} style={{ marginBottom: 12, maxHeight: 400, overflow: 'auto' }}>
            {signals.length === 0 ? (
              <div style={{ color: '#888', textAlign: 'center', padding: 20 }}>等待信号推送...</div>
            ) : (
              signals.map(s => (
                <div key={s.id} style={{ padding: 8, marginBottom: 8, background: '#f6f8fa', borderRadius: 6, borderLeft: `3px solid ${strengthColor[s.strength]}` }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Tag color={s.signal_type === 'buy' ? 'red' : 'green'}>{s.signal_type === 'buy' ? '买入' : '卖出'}</Tag>
                    <Tag color={s.strength === 'strong' ? 'red' : s.strength === 'medium' ? 'orange' : 'blue'}>{strengthLabel[s.strength]}</Tag>
                    <span style={{ fontSize: 11, color: '#999' }}>{s.timestamp.slice(11)}</span>
                  </div>
                  <div style={{ marginTop: 6, fontSize: 13 }}>
                    <span>买 {fmtHKD(s.buy_price)} → 卖 {fmtHKD(s.sell_price)}</span>
                    <span style={{ marginLeft: 8, color: s.expected_profit_pct >= 0 ? '#e24b4a' : '#1d9e75' }}>
                      预期 {s.expected_profit_pct}% ({fmtHKD(s.expected_profit_hkd)}/手)
                    </span>
                  </div>
                  <div style={{ marginTop: 4, fontSize: 11, color: '#666' }}>
                    {s.reasons.slice(0, 2).map((r, i) => <div key={i}>{r}</div>)}
                  </div>
                  <Button size="small" type="primary" style={{ marginTop: 6 }} onClick={() => openExecModal(s)}>
                    一键录入做T
                  </Button>
                </div>
              ))
            )}
          </Card>

          <Card size="small" title="风控提醒" style={{ marginBottom: 12, maxHeight: 200, overflow: 'auto' }}>
            {riskMsgs.length === 0 ? (
              <div style={{ color: '#888', textAlign: 'center', padding: 12 }}>暂无风控告警</div>
            ) : riskMsgs.map((r, i) => (
              <div key={i} style={{ padding: 6, marginBottom: 6, background: r.severity === 'high' ? '#fff1f0' : r.severity === 'medium' ? '#fffbe6' : '#f6ffed', borderRadius: 4, fontSize: 12 }}>
                <Tag color={r.severity === 'high' ? 'red' : r.severity === 'medium' ? 'orange' : 'green'} style={{ marginRight: 4 }}>
                  {r.severity}
                </Tag>
                <span>{r.message}</span>
                {r.action && <div style={{ color: '#888', marginTop: 2 }}>{r.action}</div>}
              </div>
            ))}
          </Card>

          <Card size="small" title="监控参数">
            {config ? (
              <div style={{ fontSize: 12 }}>
                <div style={{ marginBottom: 6 }}>
                  <span>启用监控：</span>
                  <Switch size="small" checked={config.enabled} onChange={v => updateConfig('enabled', v)} />
                </div>
                <div style={{ marginBottom: 6 }}>
                  <span>轮询间隔(秒)：</span>
                  <InputNumber size="small" min={2} max={60} value={config.monitor_interval_sec}
                    onChange={v => v && updateConfig('monitor_interval_sec', v)} style={{ width: 70 }} />
                </div>
                <div style={{ marginBottom: 6 }}>
                  <span>信号冷却(秒)：</span>
                  <InputNumber size="small" min={0} max={3600} value={config.signal_cooldown_sec}
                    onChange={v => v !== null && updateConfig('signal_cooldown_sec', v)} style={{ width: 70 }} />
                </div>
                <div style={{ marginBottom: 6 }}>
                  <span>价差阈值(%)：</span>
                  <InputNumber size="small" min={0} max={5} step={0.05} value={config.spread_threshold_pct}
                    onChange={v => v !== null && updateConfig('spread_threshold_pct', v)} style={{ width: 70 }} />
                </div>
                <div style={{ marginBottom: 6 }}>
                  <span>止损线(%)：</span>
                  <InputNumber size="small" min={0} max={20} step={0.5} value={config.stop_loss_pct}
                    onChange={v => v !== null && updateConfig('stop_loss_pct', v)} style={{ width: 70 }} />
                </div>
                <div>
                  <span>T仓上限(%)：</span>
                  <InputNumber size="small" min={0} max={100} value={config.max_t_ratio_pct}
                    onChange={v => v !== null && updateConfig('max_t_ratio_pct', v)} style={{ width: 70 }} />
                </div>
              </div>
            ) : <div style={{ color: '#888' }}>加载中...</div>}
          </Card>
        </div>
      </div>

      {/* 录入做T Modal */}
      <Modal
        title="录入做T记录"
        open={execModal.open}
        onOk={handleExecute}
        onCancel={() => setExecModal({ open: false, signal: null })}
        okText="确认录入"
        cancelText="取消"
      >
        {execModal.signal && (
          <div style={{ fontSize: 14 }}>
            <p>方向：<Tag color={execModal.signal.signal_type === 'buy' ? 'red' : 'green'}>{execModal.signal.signal_type === 'buy' ? '买入做T' : '卖出做T'}</Tag></p>
            <p>当前价：{fmtHKD(execModal.signal.current_price)}</p>
            <p>建议价：{fmtHKD(execModal.signal.signal_type === 'buy' ? execModal.signal.buy_price : execModal.signal.sell_price)}</p>
            <div style={{ margin: '12px 0' }}>
              <span>实际成交价：</span>
              <InputNumber value={execPrice} onChange={v => v && setExecPrice(v)} step={0.05} style={{ width: 120 }} />
              <span style={{ marginLeft: 8, color: '#888' }}>HK$</span>
            </div>
            <div style={{ margin: '12px 0' }}>
              <span>股数：</span>
              <InputNumber value={execShares} onChange={v => v && setExecShares(v)} min={1} step={100} style={{ width: 120 }} />
              <span style={{ marginLeft: 8, color: '#888' }}>(港股1手=100股)</span>
            </div>
            <p style={{ color: '#888', fontSize: 12 }}>
              提示：录入后系统自动计算滑点、手续费、FIFO盈亏，并更新持仓成本。需先在「做T系统」初始化腾讯持仓。
            </p>
          </div>
        )}
      </Modal>
    </div>
  )
}
