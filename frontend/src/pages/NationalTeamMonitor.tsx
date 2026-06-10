import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import ReactECharts from '../lib/ECharts'

const API_BASE = '/api/national-team'

interface Holding {
  code: string
  name: string
  holder_name: string
  hold_num: number
  hold_ratio: number
  hold_change: number
  hold_change_ratio: number
  hold_market_value: number
  end_date: string
  rank: number
  holder_type: string
}

interface ETFInfo {
  name: string
  price: number
  change_pct: number
  turnover: number
  super_inflow: number
  big_inflow: number
  mid_inflow: number
  small_inflow: number
  main_inflow: number
}

interface VolumeAlert {
  code: string
  name: string
  price: number
  change_pct: number
  volume_ratio: number
  volume: number
  turnover: number
  severity: 'high' | 'medium' | 'low'
  alert_type: string
  description: string
}

type TabType = 'holdings' | 'etfFlows' | 'alerts'

export default function NationalTeamMonitor() {
  const [activeTab, setActiveTab] = useState<TabType>('holdings')

  // Holdings state
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [holdingsSummary, setHoldingsSummary] = useState<any>(null)
  const [holdingsEndDate, setHoldingsEndDate] = useState('')
  const [holdingsLoading, setHoldingsLoading] = useState(false)
  const [groupBy, setGroupBy] = useState<'stock' | 'institution'>('institution')

  // ETF flows state
  const [etfData, setEtfData] = useState<Record<string, ETFInfo>>({})
  const [totalMainInflow, setTotalMainInflow] = useState(0)
  const [etfLoading, setEtfLoading] = useState(false)
  const [etfDataType, setEtfDataType] = useState('')

  // Volume alerts state
  const [alerts, setAlerts] = useState<VolumeAlert[]>([])
  const [alertsLoading, setAlertsLoading] = useState(false)
  const [alertThreshold, setAlertThreshold] = useState(2.0)
  const [scannedCount, setScannedCount] = useState(0)

  const loadHoldings = useCallback(async () => {
    setHoldingsLoading(true)
    try {
      const params: any = {}
      if (holdingsEndDate) params.end_date = holdingsEndDate
      const res = await axios.get(`${API_BASE}/shareholdings`, { params })
      setHoldings(res.data.holdings || [])
      setHoldingsSummary(res.data.summary || null)
      if (res.data.end_date) setHoldingsEndDate(res.data.end_date)
    } catch (e) {
      console.error('加载持仓数据失败:', e)
    }
    setHoldingsLoading(false)
  }, [holdingsEndDate])

  const loadETFFlows = useCallback(async () => {
    setEtfLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/etf-flows`)
      setEtfData(res.data.etfs || {})
      setTotalMainInflow(res.data.total_main_inflow || 0)
      setEtfDataType(res.data.data_type || '')
    } catch (e) {
      console.error('加载ETF流向失败:', e)
    }
    setEtfLoading(false)
  }, [])

  const loadAlerts = useCallback(async () => {
    setAlertsLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/volume-alerts`, { params: { threshold: alertThreshold } })
      setAlerts(res.data.alerts || [])
      setScannedCount(res.data.scanned || 0)
    } catch (e) {
      console.error('加载异动数据失败:', e)
    }
    setAlertsLoading(false)
  }, [alertThreshold])

  useEffect(() => {
    if (activeTab === 'holdings') loadHoldings()
    else if (activeTab === 'etfFlows') loadETFFlows()
    else if (activeTab === 'alerts') loadAlerts()
  }, [activeTab, loadHoldings, loadETFFlows, loadAlerts])

  const formatAmount = (val: number) => {
    if (Math.abs(val) >= 1e8) return (val / 1e8).toFixed(2) + '亿'
    if (Math.abs(val) >= 1e4) return (val / 1e4).toFixed(2) + '万'
    return val.toFixed(2)
  }

  const formatShares = (val: number) => {
    if (Math.abs(val) >= 1e8) return (val / 1e8).toFixed(2) + '亿股'
    if (Math.abs(val) >= 1e4) return (val / 1e4).toFixed(2) + '万股'
    return val.toFixed(0) + '股'
  }

  const changeColor = (val: number) => val > 0 ? '#e74c3c' : val < 0 ? '#27ae60' : '#999'
  const severityColor = (s: string) => s === 'high' ? '#e74c3c' : s === 'medium' ? '#f39c12' : '#3498db'
  const severityLabel = (s: string) => s === 'high' ? '严重' : s === 'medium' ? '中等' : '一般'

  // Group holdings
  const groupedHoldings = () => {
    if (groupBy === 'institution') {
      const groups: Record<string, Holding[]> = {}
      holdings.forEach(h => {
        if (!groups[h.holder_type]) groups[h.holder_type] = []
        groups[h.holder_type].push(h)
      })
      return groups
    }
    return null
  }

  // ETF flow chart option
  const getETFFlowChartOption = () => {
    const etfEntries = Object.entries(etfData)
    if (etfEntries.length === 0) return {}

    return {
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const p = params[0]
          const [code, etf] = etfEntries[p.dataIndex]
          return `<b>${etf.name} (${code})</b><br/>` +
            `价格: ${etf.price.toFixed(3)} (${etf.change_pct >= 0 ? '+' : ''}${etf.change_pct.toFixed(2)}%)<br/>` +
            `成交额: ${formatAmount(etf.turnover)}<br/>` +
            `<hr style="margin:4px 0"/>` +
            `主力净流入: <span style="color:${etf.main_inflow >= 0 ? '#e74c3c' : '#27ae60'}">${formatAmount(etf.main_inflow)}</span><br/>` +
            `超大单: ${formatAmount(etf.super_inflow)}<br/>` +
            `大单: ${formatAmount(etf.big_inflow)}<br/>` +
            `中单: ${formatAmount(etf.mid_inflow)}<br/>` +
            `小单: ${formatAmount(etf.small_inflow)}`
        },
      },
      grid: { left: 80, right: 30, top: 20, bottom: 60 },
      xAxis: {
        type: 'category',
        data: etfEntries.map(([_, e]) => e.name),
        axisLabel: { fontSize: 12 },
      },
      yAxis: {
        type: 'value',
        name: '主力净流入',
        axisLabel: {
          formatter: (v: number) => formatAmount(v),
        },
      },
      series: [{
        type: 'bar',
        data: etfEntries.map(([_, e]) => ({
          value: e.main_inflow,
          itemStyle: { color: e.main_inflow >= 0 ? '#e74c3c' : '#27ae60' },
        })),
        barWidth: '50%',
        label: {
          show: true,
          position: 'top',
          formatter: (params: any) => formatAmount(params.value),
          fontSize: 11,
        },
      }],
    }
  }

  // Volume alert chart option
  const getAlertChartOption = () => {
    if (alerts.length === 0) return {}
    const top10 = alerts.slice(0, 10)

    return {
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const p = params[0]
          const alert = top10[p.dataIndex]
          return `<b>${alert.name}</b><br/>` +
            `量比: ${alert.volume_ratio.toFixed(2)}<br/>` +
            `涨跌幅: ${alert.change_pct.toFixed(2)}%<br/>` +
            `价格: ${alert.price.toFixed(2)}`
        },
      },
      grid: { left: 80, right: 30, top: 20, bottom: 40 },
      xAxis: {
        type: 'category',
        data: top10.map(a => a.name),
        axisLabel: { rotate: 30, fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        name: '量比',
      },
      series: [{
        type: 'bar',
        data: top10.map(a => ({
          value: a.volume_ratio,
          itemStyle: { color: severityColor(a.severity) },
        })),
        barWidth: '60%',
      }],
    }
  }

  const renderHoldings = () => {
    if (holdingsLoading) return <p style={{ color: '#999', textAlign: 'center', padding: 40 }}>加载中...</p>
    if (holdings.length === 0) return <p style={{ color: '#999', textAlign: 'center', padding: 40 }}>暂无持仓数据</p>

    const groups = groupedHoldings()

    return (
      <div>
        {/* Summary cards */}
        {holdingsSummary && (
          <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 150, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
              <div style={{ color: '#999', fontSize: 12 }}>持仓总市值</div>
              <div style={{ color: '#f39c12', fontSize: 20, fontWeight: 700 }}>
                {formatAmount(holdingsSummary.total_market_value)}
              </div>
            </div>
            <div style={{ flex: 1, minWidth: 150, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
              <div style={{ color: '#999', fontSize: 12 }}>持仓数量</div>
              <div style={{ color: '#3498db', fontSize: 20, fontWeight: 700 }}>
                {holdingsSummary.total_positions} 只
              </div>
            </div>
            {Object.entries(holdingsSummary.by_type || {}).map(([type, info]: [string, any]) => (
              <div key={type} style={{ flex: 1, minWidth: 120, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
                <div style={{ color: '#999', fontSize: 12 }}>{type}</div>
                <div style={{ color: '#2ecc71', fontSize: 16, fontWeight: 600 }}>
                  {formatAmount(info.total_value)}
                </div>
                <div style={{ color: '#666', fontSize: 11 }}>{info.count} 只</div>
              </div>
            ))}
          </div>
        )}

        {/* Controls */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center' }}>
          <span style={{ color: '#999', fontSize: 13 }}>报告期: {holdingsEndDate}</span>
          <div style={{ flex: 1 }} />
          <button
            onClick={() => setGroupBy(g => g === 'institution' ? 'stock' : 'institution')}
            style={{ background: '#1a1a2e', color: '#ccc', border: '1px solid #333', borderRadius: 4, padding: '4px 12px', cursor: 'pointer', fontSize: 12 }}
          >
            {groupBy === 'institution' ? '按股票分组' : '按机构分组'}
          </button>
        </div>

        {/* Table */}
        {groupBy === 'institution' && groups ? (
          Object.entries(groups).map(([type, items]) => (
            <div key={type} style={{ marginBottom: 16 }}>
              <div style={{ color: '#f39c12', fontSize: 14, fontWeight: 600, marginBottom: 8, borderBottom: '1px solid #333', paddingBottom: 4 }}>
                {type} ({items.length}只)
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, tableLayout: 'fixed' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #333' }}>
                      <th style={{ ...thStyle, width: '12%' }}>代码</th>
                      <th style={{ ...thStyle, width: '18%' }}>名称</th>
                      <th style={{ ...thStyle, width: '18%' }}>持股数</th>
                      <th style={{ ...thStyle, width: '16%' }}>占流通比</th>
                      <th style={{ ...thStyle, width: '16%' }}>变动</th>
                      <th style={{ ...thStyle, width: '20%' }}>持仓市值</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((h, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                        <td style={tdStyle}>{h.code}</td>
                        <td style={tdStyle}>{h.name}</td>
                        <td style={tdStyle}>{formatShares(h.hold_num)}</td>
                        <td style={tdStyle}>{h.hold_ratio.toFixed(2)}%</td>
                        <td style={{ ...tdStyle, color: changeColor(h.hold_change) }}>
                          {h.hold_change > 0 ? '+' : ''}{formatShares(h.hold_change)}
                        </td>
                        <td style={tdStyle}>{formatAmount(h.hold_market_value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, tableLayout: 'fixed' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #333' }}>
                  <th style={{ ...thStyle, width: '10%' }}>代码</th>
                  <th style={{ ...thStyle, width: '10%' }}>名称</th>
                  <th style={{ ...thStyle, width: '16%' }}>机构</th>
                  <th style={{ ...thStyle, width: '8%' }}>类型</th>
                  <th style={{ ...thStyle, width: '14%' }}>持股数</th>
                  <th style={{ ...thStyle, width: '12%' }}>占流通比</th>
                  <th style={{ ...thStyle, width: '12%' }}>变动</th>
                  <th style={{ ...thStyle, width: '18%' }}>持仓市值</th>
                </tr>
              </thead>
              <tbody>
                {holdings.map((h, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                    <td style={tdStyle}>{h.code}</td>
                    <td style={tdStyle}>{h.name}</td>
                    <td style={tdStyle}>{h.holder_name}</td>
                    <td style={tdStyle}>
                      <span style={{ background: '#1a1a2e', padding: '2px 6px', borderRadius: 3, fontSize: 11 }}>
                        {h.holder_type}
                      </span>
                    </td>
                    <td style={tdStyle}>{formatShares(h.hold_num)}</td>
                    <td style={tdStyle}>{h.hold_ratio.toFixed(2)}%</td>
                    <td style={{ ...tdStyle, color: changeColor(h.hold_change) }}>
                      {h.hold_change > 0 ? '+' : ''}{formatShares(h.hold_change)}
                    </td>
                    <td style={tdStyle}>{formatAmount(h.hold_market_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    )
  }

  const renderETFFlows = () => {
    if (etfLoading) return <p style={{ color: '#999', textAlign: 'center', padding: 40 }}>加载中...</p>

    const etfEntries = Object.entries(etfData)

    return (
      <div>
        {/* Summary */}
        {etfDataType === 'history' && (
          <div style={{ background: '#2a2a1e', border: '1px solid #f39c12', borderRadius: 6, padding: '8px 14px', marginBottom: 12, color: '#f39c12', fontSize: 12 }}>
            当前为盘前/盘后，显示上一交易日行情数据，资金流向数据仅交易时段可获取
          </div>
        )}
        <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 180, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
            <div style={{ color: '#999', fontSize: 12 }}>今日主力净流入合计</div>
            <div style={{ color: totalMainInflow >= 0 ? '#e74c3c' : '#27ae60', fontSize: 22, fontWeight: 700 }}>
              {totalMainInflow >= 0 ? '+' : ''}{formatAmount(totalMainInflow)}
            </div>
          </div>
          {etfEntries.map(([code, etf]) => (
            <div key={code} style={{ flex: 1, minWidth: 140, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
              <div style={{ color: '#999', fontSize: 12 }}>{etf.name}</div>
              <div style={{ color: etf.main_inflow >= 0 ? '#e74c3c' : '#27ae60', fontSize: 16, fontWeight: 600 }}>
                {etf.main_inflow >= 0 ? '+' : ''}{formatAmount(etf.main_inflow)}
              </div>
              <div style={{ color: etf.change_pct >= 0 ? '#e74c3c' : '#27ae60', fontSize: 12 }}>
                {etf.change_pct >= 0 ? '+' : ''}{etf.change_pct.toFixed(2)}%
              </div>
            </div>
          ))}
        </div>

        {/* Chart */}
        {etfEntries.length > 0 && (
          <div style={{ background: '#1a1a2e', borderRadius: 8, padding: 16, marginBottom: 16 }}>
            <div style={{ color: '#ccc', fontSize: 13, marginBottom: 8 }}>大盘ETF主力资金净流入</div>
            <ReactECharts option={getETFFlowChartOption()} style={{ height: 300 }} />
          </div>
        )}

        {/* Detail table */}
        <div style={{ color: '#ccc', fontSize: 14, fontWeight: 600, marginBottom: 8 }}>资金流向明细</div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, tableLayout: 'fixed' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #333' }}>
                <th style={{ ...thStyle, width: '14%' }}>ETF</th>
                <th style={{ ...thStyle, width: '9%' }}>价格</th>
                <th style={{ ...thStyle, width: '9%' }}>涨跌幅</th>
                <th style={{ ...thStyle, width: '11%' }}>成交额</th>
                <th style={{ ...thStyle, width: '11%' }}>主力净流入</th>
                <th style={{ ...thStyle, width: '11%' }}>超大单</th>
                <th style={{ ...thStyle, width: '11%' }}>大单</th>
                <th style={{ ...thStyle, width: '11%' }}>中单</th>
                <th style={{ ...thStyle, width: '13%' }}>小单</th>
              </tr>
            </thead>
            <tbody>
              {etfEntries.map(([code, etf]) => (
                <tr key={code} style={{ borderBottom: '1px solid #222' }}>
                  <td style={tdStyle}>
                    <div style={{ fontWeight: 600 }}>{code}</div>
                    <div style={{ fontSize: 11, color: '#999' }}>{etf.name}</div>
                  </td>
                  <td style={tdStyle}>{etf.price.toFixed(3)}</td>
                  <td style={{ ...tdStyle, color: changeColor(etf.change_pct) }}>
                    {etf.change_pct >= 0 ? '+' : ''}{etf.change_pct.toFixed(2)}%
                  </td>
                  <td style={tdStyle}>{formatAmount(etf.turnover)}</td>
                  <td style={{ ...tdStyle, color: changeColor(etf.main_inflow), fontWeight: 700 }}>
                    {formatAmount(etf.main_inflow)}
                  </td>
                  <td style={{ ...tdStyle, color: changeColor(etf.super_inflow) }}>{formatAmount(etf.super_inflow)}</td>
                  <td style={{ ...tdStyle, color: changeColor(etf.big_inflow) }}>{formatAmount(etf.big_inflow)}</td>
                  <td style={{ ...tdStyle, color: changeColor(etf.mid_inflow) }}>{formatAmount(etf.mid_inflow)}</td>
                  <td style={{ ...tdStyle, color: changeColor(etf.small_inflow) }}>{formatAmount(etf.small_inflow)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  const renderAlerts = () => {
    if (alertsLoading) return <p style={{ color: '#999', textAlign: 'center', padding: 40 }}>加载中...</p>

    return (
      <div>
        {/* Controls */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center' }}>
          <span style={{ color: '#999', fontSize: 13 }}>量比阈值:</span>
          {[1.5, 2.0, 2.5, 3.0].map(t => (
            <button key={t} onClick={() => setAlertThreshold(t)}
              style={{ background: alertThreshold === t ? '#e74c3c' : '#1a1a2e', color: '#ccc', border: '1px solid #333', borderRadius: 4, padding: '4px 12px', cursor: 'pointer', fontSize: 12 }}>
              {t}
            </button>
          ))}
          <span style={{ color: '#666', fontSize: 12 }}>扫描 {scannedCount} 只蓝筹</span>
        </div>

        {alerts.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>-</div>
            <div>当前无量比 &gt;= {alertThreshold} 的异动</div>
            <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>蓝筹股表现平稳</div>
          </div>
        ) : (
          <>
            {/* Chart */}
            <div style={{ background: '#1a1a2e', borderRadius: 8, padding: 16, marginBottom: 16 }}>
              <div style={{ color: '#ccc', fontSize: 13, marginBottom: 8 }}>Top10 量比</div>
              <ReactECharts option={getAlertChartOption()} style={{ height: 280 }} />
            </div>

            {/* Alert list */}
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, tableLayout: 'fixed' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #333' }}>
                    <th style={{ ...thStyle, width: '8%' }}>严重度</th>
                    <th style={{ ...thStyle, width: '10%' }}>代码</th>
                    <th style={{ ...thStyle, width: '10%' }}>名称</th>
                    <th style={{ ...thStyle, width: '9%' }}>价格</th>
                    <th style={{ ...thStyle, width: '9%' }}>涨跌幅</th>
                    <th style={{ ...thStyle, width: '8%' }}>量比</th>
                    <th style={{ ...thStyle, width: '11%' }}>成交额</th>
                    <th style={{ ...thStyle, width: '35%' }}>说明</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.map((a, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                      <td style={tdStyle}>
                        <span style={{
                          background: severityColor(a.severity),
                          color: '#fff',
                          padding: '2px 8px',
                          borderRadius: 3,
                          fontSize: 11,
                          fontWeight: 600,
                        }}>
                          {severityLabel(a.severity)}
                        </span>
                      </td>
                      <td style={tdStyle}>{a.code}</td>
                      <td style={tdStyle}>{a.name}</td>
                      <td style={tdStyle}>{a.price.toFixed(2)}</td>
                      <td style={{ ...tdStyle, color: changeColor(a.change_pct) }}>
                        {a.change_pct > 0 ? '+' : ''}{a.change_pct.toFixed(2)}%
                      </td>
                      <td style={{ ...tdStyle, color: severityColor(a.severity), fontWeight: 700 }}>
                        {a.volume_ratio.toFixed(2)}
                      </td>
                      <td style={tdStyle}>{formatAmount(a.turnover)}</td>
                      <td style={{ ...tdStyle, color: '#999', fontSize: 12, whiteSpace: 'normal', wordBreak: 'break-all' }}>{a.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    )
  }

  return (
    <div className="cb-page">
      <div className="stock-header">
        <h2>国家队监控</h2>
        <p style={{ color: '#999', margin: '4px 0 0' }}>
          汇金/证金/社保/养老保险持仓追踪 · ETF资金流向 · 蓝筹异动检测
        </p>
      </div>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 16, borderBottom: '1px solid #333' }}>
        {[
          { key: 'holdings' as TabType, label: '持仓追踪' },
          { key: 'etfFlows' as TabType, label: 'ETF资金流向' },
          { key: 'alerts' as TabType, label: '异动检测' },
        ].map(tab => (
          <button key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              background: 'transparent',
              color: activeTab === tab.key ? '#f39c12' : '#999',
              border: 'none',
              borderBottom: activeTab === tab.key ? '2px solid #f39c12' : '2px solid transparent',
              padding: '10px 20px',
              cursor: 'pointer',
              fontSize: 14,
              fontWeight: activeTab === tab.key ? 600 : 400,
              transition: 'all 0.2s',
            }}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {activeTab === 'holdings' && renderHoldings()}
      {activeTab === 'etfFlows' && renderETFFlows()}
      {activeTab === 'alerts' && renderAlerts()}
    </div>
  )
}

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '8px 12px',
  color: '#999',
  fontWeight: 500,
  fontSize: 12,
  whiteSpace: 'nowrap',
}

const tdStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '8px 12px',
  color: '#ddd',
  whiteSpace: 'nowrap',
}
