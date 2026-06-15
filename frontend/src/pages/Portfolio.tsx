import { useState, useEffect, useCallback } from 'react'
import ReactECharts from 'echarts-for-react'
import { portfolioApi } from '../services/api'
import type { PortfolioSummary, PortfolioTransaction, PortfolioPosition, RiskExposure, PerformancePoint, PortfolioRiskAnalysis } from '../services/api'
import { StatCard, StatCardGroup, PageSection, DataTable, TabBar, LoadingSpinner, EmptyState, Tag } from '../components/ui'
import type { Column } from '../components/ui'
import { useTradingInterceptor } from '../hooks/useTradingInterceptor'
import RationalCheckpoint from '../components/RationalCheckpoint'

// ============ 辅助函数 ============

const formatMoney = (n: number | null | undefined) => {
  if (n === null || n === undefined) return '-'
  if (Math.abs(n) >= 10000) return (n / 10000).toFixed(2) + '亿'
  return n.toFixed(2) + '万'
}

const formatPct = (n: number | null | undefined) => {
  if (n === null || n === undefined) return '-'
  return (n >= 0 ? '+' : '') + n.toFixed(2) + '%'
}

const pnlColor = (n: number) => n >= 0 ? '#ef4444' : '#22c55e'  // A股：红涨绿跌
const pnlBg = (n: number) => n >= 0 ? 'rgba(239,68,68,0.1)' : 'rgba(34,197,94,0.1)'

const txnTypeLabel: Record<string, string> = {
  buy: '买入', sell: '卖出', dividend: '分红', split: '拆股',
}
const txnTypeColor: Record<string, string> = {
  buy: '#ef4444', sell: '#22c55e', dividend: '#f59e0b', split: '#6366f1',
}

// ============ 组件 ============

export default function Portfolio() {
  const [tab, setTab] = useState('positions')
  const [loading, setLoading] = useState(true)
  const [summary, setSummary] = useState<PortfolioSummary | null>(null)
  const [transactions, setTransactions] = useState<PortfolioTransaction[]>([])
  const [performance, setPerformance] = useState<PerformancePoint[]>([])
  const [risk, setRisk] = useState<RiskExposure | null>(null)
  const [riskAnalysis, setRiskAnalysis] = useState<PortfolioRiskAnalysis | null>(null)
  const [riskLoading, setRiskLoading] = useState(false)
  const [showAddTxn, setShowAddTxn] = useState(false)
  const [addLoading, setAddLoading] = useState(false)

  // 交易拦截器
  const { intercept, checkpointOpen, checkpointMeta, handlePass, handleCancel } = useTradingInterceptor()

  // 加载数据
  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [summaryRes, txnRes, perfRes, riskRes] = await Promise.all([
        portfolioApi.getSummary(),
        portfolioApi.getTransactions(),
        portfolioApi.getPerformance(),
        portfolioApi.getRisk(),
      ])
      setSummary(summaryRes.data)
      setTransactions(txnRes.data.transactions || [])
      setPerformance(perfRes.data.points || [])
      setRisk(riskRes.data)

      // 异步加载风险分析（数据量较大，不阻塞主界面）
      setRiskLoading(true)
      portfolioApi.getRiskAnalysis()
        .then(res => setRiskAnalysis(res.data))
        .catch(e => console.error('加载风险分析失败:', e))
        .finally(() => setRiskLoading(false))
    } catch (e) {
      console.error('加载组合数据失败:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  // 添加交易（实际执行）
  const doAddTransaction = async (form: {
    code: string; name: string; type: string; shares: number; price: number; fee: number; reason: string
  }) => {
    setAddLoading(true)
    try {
      await portfolioApi.addTransaction({
        code: form.code,
        name: form.name,
        type: form.type as 'buy' | 'sell' | 'dividend' | 'split',
        shares: form.type === 'sell' ? -Math.abs(form.shares) : form.shares,
        price: form.price,
        fee: form.fee,
        reason: form.reason,
      })
      setShowAddTxn(false)
      loadData()
    } catch (e: any) {
      alert('添加失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setAddLoading(false)
    }
  }

  // 添加交易（带拦截）
  const handleAddTransaction = (form: {
    code: string; name: string; type: string; shares: number; price: number; fee: number; reason: string
  }) => {
    intercept(() => doAddTransaction(form), {
      actionType: form.type === 'sell' ? 'sell' : 'buy',
      target: form.name || form.code,
    })
  }

  // 删除交易
  const handleDelete = async (txnId: string) => {
    if (!confirm('确认删除此交易记录？')) return
    try {
      await portfolioApi.deleteTransaction(txnId)
      loadData()
    } catch (e: any) {
      alert('删除失败: ' + (e.response?.data?.detail || e.message))
    }
  }

  if (loading) return <LoadingSpinner text="加载组合数据..." />

  const TAB_ITEMS = [
    { key: 'positions', label: '持仓总览' },
    { key: 'transactions', label: '交易记录' },
    { key: 'performance', label: '收益曲线' },
    { key: 'risk', label: '风险暴露' },
    { key: 'risk_analysis', label: '风险分析' },
  ]

  return (
    <div>
      <PageSection title="💼 我的持仓">
        {/* 组合概览卡片 */}
        <PortfolioSummaryCards summary={summary} />

        <TabBar tabs={TAB_ITEMS} activeKey={tab} onChange={setTab} style={{ marginTop: 16 }} />

        {tab === 'positions' && (
          <PositionsTab
            positions={summary?.positions || []}
            onClickStock={(code) => {
              (window as any).__navigateTo?.('stock')
              // 通过全局搜索触发
              const event = new CustomEvent('portfolio-navigate-stock', { detail: code })
              window.dispatchEvent(event)
            }}
          />
        )}

        {tab === 'transactions' && (
          <TransactionsTab
            transactions={transactions}
            onAdd={() => setShowAddTxn(true)}
            onDelete={handleDelete}
          />
        )}

        {tab === 'performance' && (
          <PerformanceTab points={performance} summary={summary} />
        )}

        {tab === 'risk' && (
          <RiskTab risk={risk} />
        )}

        {tab === 'risk_analysis' && (
          <RiskAnalysisTab data={riskAnalysis} loading={riskLoading} />
        )}
      </PageSection>

      {/* 添加交易弹窗 */}
      {showAddTxn && (
        <AddTransactionModal
          loading={addLoading}
          onSubmit={handleAddTransaction}
          onClose={() => setShowAddTxn(false)}
        />
      )}

      {/* 理性检查点 */}
      <RationalCheckpoint
        open={checkpointOpen}
        actionType={checkpointMeta.actionType}
        target={checkpointMeta.target}
        onPass={handlePass}
        onCancel={handleCancel}
      />
    </div>
  )
}

// ============ 组合概览卡片 ============

function PortfolioSummaryCards({ summary }: { summary: PortfolioSummary | null }) {
  if (!summary) return null

  return (
    <StatCardGroup>
      <StatCard
        label="总市值"
        value={formatMoney(summary.total_value)}
        suffix={summary.position_count + '只持仓'}
      />
      <StatCard
        label="总盈亏"
        value={formatMoney(summary.total_pnl)}
        color={pnlColor(summary.total_pnl)}
        suffix={formatPct(summary.total_pnl_pct)}
      />
      <StatCard
        label="今日盈亏"
        value={formatMoney(summary.today_pnl)}
        color={pnlColor(summary.today_pnl)}
      />
      <StatCard
        label="现金余额"
        value={formatMoney(summary.cash)}
        color="#8b949e"
      />
      <StatCard
        label="总投入"
        value={formatMoney(summary.total_cost)}
        color="#8b949e"
      />
    </StatCardGroup>
  )
}

// ============ 持仓总览 ============

function PositionsTab({
  positions,
  onClickStock,
}: {
  positions: PortfolioPosition[]
  onClickStock: (code: string) => void
}) {
  if (positions.length === 0) {
    return <EmptyState icon="📊" title="暂无持仓" description="点击「交易记录」添加你的第一笔交易" />
  }

  const columns: Column<PortfolioPosition>[] = [
    { key: 'name', title: '股票', width: 140, render: (_, r) => (
      <div>
        <div style={{ fontWeight: 600 }}>{r.name}</div>
        <div style={{ fontSize: 11, color: '#8b949e' }}>{r.code}</div>
      </div>
    )},
    { key: 'shares', title: '持股', width: 80, render: (_, r) => r.shares.toLocaleString() },
    { key: 'avg_cost', title: '成本价', width: 80, render: (_, r) => r.avg_cost.toFixed(2) },
    { key: 'current_price', title: '现价', width: 80, render: (_, r) => (
      <span style={{ color: pnlColor(r.unrealized_pnl) }}>{r.current_price.toFixed(2)}</span>
    )},
    { key: 'market_value', title: '市值', width: 100, render: (_, r) => formatMoney(r.market_value) },
    { key: 'unrealized_pnl', title: '浮盈盈亏', width: 100, render: (_, r) => (
      <span style={{ color: pnlColor(r.unrealized_pnl), fontWeight: 600 }}>
        {formatMoney(r.unrealized_pnl)}
      </span>
    )},
    { key: 'unrealized_pnl_pct', title: '收益率', width: 90, render: (_, r) => (
      <Tag color={r.unrealized_pnl_pct >= 0 ? '#ef4444' : '#22c55e'} style={{ fontSize: 12 }}>
        {formatPct(r.unrealized_pnl_pct)}
      </Tag>
    )},
    { key: 'position_pct', title: '仓位', width: 70, render: (_, r) => r.position_pct.toFixed(1) + '%' },
    { key: 'holding_days', title: '持有天数', width: 80, render: (_, r) => r.holding_days + '天' },
  ]

  return (
    <div style={{ marginTop: 16 }}>
      <DataTable
        columns={columns}
        data={positions}
        rowKey={(r) => r.code}
        onRowClick={(r) => onClickStock(r.code)}
      />
    </div>
  )
}

// ============ 交易记录 ============

function TransactionsTab({
  transactions,
  onAdd,
  onDelete,
}: {
  transactions: PortfolioTransaction[]
  onAdd: () => void
  onDelete: (id: string) => void
}) {
  const columns: Column<PortfolioTransaction>[] = [
    { key: 'created_at', title: '时间', width: 160, render: (_, r) => r.created_at },
    { key: 'type', title: '类型', width: 70, render: (_, r) => (
      <Tag color={txnTypeColor[r.type] || '#8b949e'}>{txnTypeLabel[r.type] || r.type}</Tag>
    )},
    { key: 'name', title: '股票', width: 120, render: (_, r) => (
      <div>
        <div style={{ fontWeight: 600 }}>{r.name}</div>
        <div style={{ fontSize: 11, color: '#8b949e' }}>{r.code}</div>
      </div>
    )},
    { key: 'shares', title: '股数', width: 80, render: (_, r) => Math.abs(r.shares).toLocaleString() },
    { key: 'price', title: '价格', width: 80, render: (_, r) => r.price.toFixed(2) },
    { key: 'amount', title: '金额', width: 100, render: (_, r) => formatMoney(r.amount) },
    { key: 'fee', title: '手续费', width: 70, render: (_, r) => r.fee.toFixed(2) },
    { key: 'reason', title: '理由', width: 200, render: (_, r) => (
      <span style={{ color: '#8b949e', fontSize: 12 }}>{r.reason || '-'}</span>
    )},
    { key: 'actions', title: '操作', width: 60, render: (_, r) => (
      <button
        onClick={(e) => { e.stopPropagation(); onDelete(r.id) }}
        style={{
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
          color: '#ef4444', borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontSize: 12,
        }}
      >
        删除
      </button>
    )},
  ]

  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'flex-end' }}>
        <button
          onClick={onAdd}
          style={{
            background: '#58a6ff', color: '#fff', border: 'none',
            borderRadius: 6, padding: '8px 16px', cursor: 'pointer', fontWeight: 600,
          }}
        >
          + 添加交易
        </button>
      </div>
      {transactions.length === 0 ? (
        <EmptyState icon="📝" title="暂无交易记录" description="点击上方按钮记录你的第一笔交易" />
      ) : (
        <DataTable columns={columns} data={transactions} rowKey={(r) => r.id} />
      )}
    </div>
  )
}

// ============ 收益曲线 ============

function PerformanceTab({
  points,
  summary,
}: {
  points: PerformancePoint[]
  summary: PortfolioSummary | null
}) {
  if (points.length === 0) {
    return <EmptyState icon="📈" title="暂无收益数据" description="添加交易记录后自动生成收益曲线" />
  }

  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1c2333',
      borderColor: '#30363d',
      textStyle: { color: '#e6edf3', fontSize: 12 },
      formatter: (params: any) => {
        const p = params[0]
        return `${p.name}<br/>累计投入: ${formatMoney(p.value)}`
      },
    },
    grid: { top: 30, right: 20, bottom: 30, left: 60 },
    xAxis: {
      type: 'category',
      data: points.map(p => p.date),
      axisLine: { lineStyle: { color: '#30363d' } },
      axisLabel: { color: '#8b949e', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#21262d' } },
      axisLabel: {
        color: '#8b949e', fontSize: 11,
        formatter: (v: number) => formatMoney(v),
      },
    },
    series: [{
      type: 'line',
      data: points.map(p => p.value),
      smooth: true,
      lineStyle: { color: '#58a6ff', width: 2 },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(88,166,255,0.3)' },
            { offset: 1, color: 'rgba(88,166,255,0.02)' },
          ],
        },
      },
      itemStyle: { color: '#58a6ff' },
    }],
  }

  return (
    <div style={{ marginTop: 16 }}>
      {/* 收益概览 */}
      {summary && (
        <div style={{
          display: 'flex', gap: 24, marginBottom: 16, padding: 16,
          background: '#161b22', borderRadius: 8, border: '1px solid #30363d',
        }}>
          <div>
            <div style={{ color: '#8b949e', fontSize: 12 }}>总收益率</div>
            <div style={{ color: pnlColor(summary.total_pnl), fontSize: 20, fontWeight: 700 }}>
              {formatPct(summary.total_pnl_pct)}
            </div>
          </div>
          <div>
            <div style={{ color: '#8b949e', fontSize: 12 }}>总盈亏</div>
            <div style={{ color: pnlColor(summary.total_pnl), fontSize: 20, fontWeight: 700 }}>
              {formatMoney(summary.total_pnl)}
            </div>
          </div>
          <div>
            <div style={{ color: '#8b949e', fontSize: 12 }}>总投入</div>
            <div style={{ color: '#e6edf3', fontSize: 20, fontWeight: 700 }}>
              {formatMoney(summary.total_cost)}
            </div>
          </div>
        </div>
      )}
      <ReactECharts option={option} style={{ height: 350 }} />
    </div>
  )
}

// ============ 风险暴露 ============

function RiskTab({ risk }: { risk: RiskExposure | null }) {
  if (!risk) return <EmptyState icon="⚠️" title="暂无风险数据" />

  const sectorData = Object.entries(risk.sector_exposure)
    .sort((a, b) => b[1] - a[1])
    .map(([name, value]) => ({ name, value }))

  const pieOption = {
    tooltip: {
      trigger: 'item',
      backgroundColor: '#1c2333',
      borderColor: '#30363d',
      textStyle: { color: '#e6edf3' },
      formatter: '{b}: {c}% ({d}%)',
    },
    legend: {
      orient: 'vertical', right: 10, top: 'center',
      textStyle: { color: '#8b949e', fontSize: 12 },
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['40%', '50%'],
      avoidLabelOverlap: false,
      label: { show: false },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold', color: '#e6edf3' },
      },
      data: sectorData.map(d => ({
        ...d,
        itemStyle: { borderColor: '#0d1117', borderWidth: 2 },
      })),
    }],
  }

  const barOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1c2333',
      borderColor: '#30363d',
      textStyle: { color: '#e6edf3' },
    },
    grid: { top: 10, right: 20, bottom: 30, left: 100 },
    xAxis: {
      type: 'value',
      axisLabel: { color: '#8b949e', formatter: '{c}%' },
      splitLine: { lineStyle: { color: '#21262d' } },
    },
    yAxis: {
      type: 'category',
      data: risk.top_holdings.map(h => h.name),
      axisLine: { lineStyle: { color: '#30363d' } },
      axisLabel: { color: '#e6edf3', fontSize: 12 },
    },
    series: [{
      type: 'bar',
      data: risk.top_holdings.map(h => ({
        value: h.pct,
        itemStyle: {
          color: h.pct > 30 ? '#ef4444' : h.pct > 20 ? '#f59e0b' : '#58a6ff',
          borderRadius: [0, 4, 4, 0],
        },
      })),
      barWidth: 20,
      label: {
        show: true, position: 'right',
        formatter: '{c}%', color: '#8b949e', fontSize: 11,
      },
    }],
  }

  return (
    <div style={{ marginTop: 16 }}>
      {/* 集中度警告 */}
      {risk.concentration_warnings.length > 0 && (
        <div style={{
          marginBottom: 16, padding: 12, borderRadius: 8,
          background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
        }}>
          {risk.concentration_warnings.map((w, i) => (
            <div key={i} style={{ color: '#f87171', fontSize: 13, marginBottom: i < risk.concentration_warnings.length - 1 ? 4 : 0 }}>
              {w}
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* 行业分布 */}
        <div style={{ background: '#161b22', borderRadius: 8, border: '1px solid #30363d', padding: 16 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>行业分布</div>
          {sectorData.length > 0 ? (
            <ReactECharts option={pieOption} style={{ height: 280 }} />
          ) : (
            <EmptyState icon="📊" title="暂无数据" />
          )}
        </div>

        {/* 个股集中度 */}
        <div style={{ background: '#161b22', borderRadius: 8, border: '1px solid #30363d', padding: 16 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>个股集中度 (Top 10)</div>
          {risk.top_holdings.length > 0 ? (
            <ReactECharts option={barOption} style={{ height: 280 }} />
          ) : (
            <EmptyState icon="📊" title="暂无数据" />
          )}
        </div>
      </div>
    </div>
  )
}

// ============ 风险分析（VaR/CVaR/压力测试） ============

function RiskAnalysisTab({ data, loading }: { data: PortfolioRiskAnalysis | null; loading: boolean }) {
  if (loading) return <LoadingSpinner text="加载风险分析数据（正在获取历史行情）..." />
  if (!data || !data.has_data) {
    return <EmptyState icon="📉" title="暂无风险分析数据" description={data?.message || '请先添加持仓'} />
  }

  const riskLevel = (var_pct: number) => {
    const abs = Math.abs(var_pct)
    if (abs >= 5) return { label: '高风险', color: '#ef4444' }
    if (abs >= 3) return { label: '中高风险', color: '#f59e0b' }
    if (abs >= 1.5) return { label: '中等风险', color: '#3b82f6' }
    return { label: '低风险', color: '#22c55e' }
  }

  const var95Level = riskLevel(data.var_95?.var_pct || 0)

  return (
    <div style={{ marginTop: 16 }}>
      {/* 核心指标卡片 */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: 12, marginBottom: 20,
      }}>
        <MetricCard
          label="VaR (95%)"
          value={`${Math.abs(data.var_95?.var_pct || 0).toFixed(2)}%`}
          subValue={formatMoney(data.var_95?.var_amount || 0)}
          color={var95Level.color}
          tip="95%置信度下，单日最大预期损失"
        />
        <MetricCard
          label="VaR (99%)"
          value={`${Math.abs(data.var_99?.var_pct || 0).toFixed(2)}%`}
          subValue={formatMoney(data.var_99?.var_amount || 0)}
          color="#f59e0b"
          tip="99%置信度下，单日最大预期损失"
        />
        <MetricCard
          label="CVaR (95%)"
          value={`${Math.abs(data.cvar_95?.cvar_pct || 0).toFixed(2)}%`}
          subValue={formatMoney(data.cvar_95?.cvar_amount || 0)}
          color="#ef4444"
          tip="尾部平均损失（超过VaR后的平均亏损）"
        />
        <MetricCard
          label="年化波动率"
          value={`${data.volatility_annual.toFixed(2)}%`}
          color={data.volatility_annual > 30 ? '#ef4444' : data.volatility_annual > 20 ? '#f59e0b' : '#22c55e'}
          tip="年化收益率的标准差"
        />
        <MetricCard
          label="最大回撤"
          value={`${data.max_drawdown.toFixed(2)}%`}
          color={data.max_drawdown < -30 ? '#ef4444' : data.max_drawdown < -15 ? '#f59e0b' : '#22c55e'}
          tip="历史上从峰值到谷底的最大跌幅"
        />
        <MetricCard
          label="夏普比率"
          value={data.sharpe_ratio.toFixed(3)}
          color={data.sharpe_ratio > 1 ? '#22c55e' : data.sharpe_ratio > 0 ? '#3b82f6' : '#ef4444'}
          tip="风险调整后收益（无风险利率2%）"
        />
        <MetricCard
          label="集中度 HHI"
          value={data.concentration_hhi.toFixed(4)}
          color={data.concentration_hhi > 0.25 ? '#ef4444' : data.concentration_hhi > 0.15 ? '#f59e0b' : '#22c55e'}
          tip="赫芬达尔指数，越接近1越集中"
        />
        <MetricCard
          label="前3大持仓占比"
          value={`${data.top3_pct.toFixed(1)}%`}
          color={data.top3_pct > 70 ? '#ef4444' : data.top3_pct > 50 ? '#f59e0b' : '#22c55e'}
          tip="前3大持仓市值占总仓位比例"
        />
      </div>

      {/* 数据说明 */}
      <div style={{
        marginBottom: 16, padding: '8px 12px', borderRadius: 6,
        background: 'rgba(88,166,255,0.08)', border: '1px solid rgba(88,166,255,0.2)',
        color: '#8b949e', fontSize: 12,
      }}>
        基于 {data.data_days} 个交易日历史数据，使用历史模拟法（非参数化）计算。持仓 {data.position_count} 只，总市值 {formatMoney(data.total_value)}。
      </div>

      {/* 压力测试 */}
      {data.stress_test && data.stress_test.length > 0 && (
        <div style={{ background: '#161b22', borderRadius: 8, border: '1px solid #30363d', padding: 16 }}>
          <div style={{ fontWeight: 600, marginBottom: 12, fontSize: 15 }}>压力测试场景</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #30363d' }}>
                <th style={{ textAlign: 'left', padding: '8px 12px', color: '#8b949e' }}>场景</th>
                <th style={{ textAlign: 'right', padding: '8px 12px', color: '#8b949e' }}>损失金额</th>
                <th style={{ textAlign: 'right', padding: '8px 12px', color: '#8b949e' }}>损失比例</th>
                <th style={{ textAlign: 'right', padding: '8px 12px', color: '#8b949e' }}>冲击后市值</th>
                <th style={{ textAlign: 'left', padding: '8px 12px', color: '#8b949e', paddingLeft: 20 }}>影响最大个股</th>
              </tr>
            </thead>
            <tbody>
              {data.stress_test.map((s, idx) => {
                const worst = s.position_impacts?.[0]
                return (
                  <tr key={idx} style={{ borderBottom: '1px solid #21262d' }}>
                    <td style={{ padding: '10px 12px' }}>
                      <span style={{ color: s.type === 'market' ? '#ef4444' : '#f59e0b', fontWeight: 600 }}>
                        {s.name}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right', padding: '10px 12px', color: '#ef4444', fontWeight: 600 }}>
                      {formatMoney(s.total_loss)}
                    </td>
                    <td style={{ textAlign: 'right', padding: '10px 12px' }}>
                      <Tag color="#ef4444">{s.total_loss_pct.toFixed(2)}%</Tag>
                    </td>
                    <td style={{ textAlign: 'right', padding: '10px 12px', color: '#e6edf3' }}>
                      {formatMoney(s.portfolio_after)}
                    </td>
                    <td style={{ padding: '10px 12px', paddingLeft: 20, color: '#8b949e' }}>
                      {worst ? `${worst.name} (${worst.loss_pct.toFixed(1)}%)` : '-'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// 指标卡片子组件
function MetricCard({
  label, value, subValue, color, tip,
}: {
  label: string; value: string; subValue?: string; color: string; tip?: string
}) {
  return (
    <div style={{
      background: '#161b22', borderRadius: 8, border: '1px solid #30363d',
      padding: '12px 16px', position: 'relative',
    }} title={tip}>
      <div style={{ color: '#8b949e', fontSize: 12, marginBottom: 4 }}>{label}</div>
      <div style={{ color, fontSize: 22, fontWeight: 700 }}>{value}</div>
      {subValue && <div style={{ color: '#8b949e', fontSize: 12, marginTop: 2 }}>{subValue}</div>}
    </div>
  )
}


// ============ 添加交易弹窗 ============

function AddTransactionModal({
  loading,
  onSubmit,
  onClose,
}: {
  loading: boolean
  onSubmit: (form: { code: string; name: string; type: string; shares: number; price: number; fee: number; reason: string }) => void
  onClose: () => void
}) {
  const [form, setForm] = useState({
    code: '', name: '', type: 'buy', shares: '', price: '', fee: '', reason: '',
  })

  const handleSubmit = () => {
    if (!form.code.trim() || !form.name.trim()) { alert('请填写股票代码和名称'); return }
    const shares = parseFloat(form.shares)
    const price = parseFloat(form.price)
    if (isNaN(shares) || shares <= 0) { alert('请填写有效的股数'); return }
    if (isNaN(price) || price <= 0) { alert('请填写有效的价格'); return }
    onSubmit({
      code: form.code.trim(),
      name: form.name.trim(),
      type: form.type,
      shares,
      price,
      fee: parseFloat(form.fee) || 0,
      reason: form.reason.trim(),
    })
  }

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '8px 12px', background: '#0d1117',
    border: '1px solid #30363d', borderRadius: 6, color: '#e6edf3',
    fontSize: 14, outline: 'none',
  }
  const labelStyle: React.CSSProperties = {
    display: 'block', marginBottom: 4, color: '#8b949e', fontSize: 13,
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }} onClick={onClose}>
      <div style={{
        background: '#161b22', borderRadius: 12, padding: 24, width: 420,
        border: '1px solid #30363d', maxHeight: '80vh', overflow: 'auto',
      }} onClick={e => e.stopPropagation()}>
        <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>添加交易记录</div>

        <div style={{ display: 'grid', gap: 12 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={labelStyle}>股票代码</label>
              <input style={inputStyle} placeholder="600519" value={form.code}
                onChange={e => setForm({ ...form, code: e.target.value })} />
            </div>
            <div>
              <label style={labelStyle}>股票名称</label>
              <input style={inputStyle} placeholder="贵州茅台" value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })} />
            </div>
          </div>

          <div>
            <label style={labelStyle}>交易类型</label>
            <div style={{ display: 'flex', gap: 8 }}>
              {(['buy', 'sell', 'dividend'] as const).map(t => (
                <button key={t} onClick={() => setForm({ ...form, type: t })} style={{
                  flex: 1, padding: '8px 0', borderRadius: 6, cursor: 'pointer',
                  background: form.type === t ? (t === 'buy' ? 'rgba(239,68,68,0.15)' : t === 'sell' ? 'rgba(34,197,94,0.15)' : 'rgba(245,158,11,0.15)') : '#0d1117',
                  border: `1px solid ${form.type === t ? (t === 'buy' ? '#ef4444' : t === 'sell' ? '#22c55e' : '#f59e0b') : '#30363d'}`,
                  color: form.type === t ? (t === 'buy' ? '#ef4444' : t === 'sell' ? '#22c55e' : '#f59e0b') : '#8b949e',
                  fontWeight: 600, fontSize: 13,
                }}>
                  {t === 'buy' ? '买入' : t === 'sell' ? '卖出' : '分红'}
                </button>
              ))}
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
            <div>
              <label style={labelStyle}>股数</label>
              <input style={inputStyle} type="number" placeholder="100" value={form.shares}
                onChange={e => setForm({ ...form, shares: e.target.value })} />
            </div>
            <div>
              <label style={labelStyle}>价格</label>
              <input style={inputStyle} type="number" step="0.01" placeholder="1800.00" value={form.price}
                onChange={e => setForm({ ...form, price: e.target.value })} />
            </div>
            <div>
              <label style={labelStyle}>手续费</label>
              <input style={inputStyle} type="number" step="0.01" placeholder="5.00" value={form.fee}
                onChange={e => setForm({ ...form, fee: e.target.value })} />
            </div>
          </div>

          <div>
            <label style={labelStyle}>交易理由</label>
            <textarea
              style={{ ...inputStyle, minHeight: 60, resize: 'vertical' }}
              placeholder="记录你的投资逻辑..."
              value={form.reason}
              onChange={e => setForm({ ...form, reason: e.target.value })}
            />
          </div>

          <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 8 }}>
            <button onClick={onClose} style={{
              padding: '8px 16px', borderRadius: 6, cursor: 'pointer',
              background: '#0d1117', border: '1px solid #30363d', color: '#8b949e',
            }}>取消</button>
            <button onClick={handleSubmit} disabled={loading} style={{
              padding: '8px 20px', borderRadius: 6, cursor: loading ? 'not-allowed' : 'pointer',
              background: '#58a6ff', border: 'none', color: '#fff', fontWeight: 600,
            }}>
              {loading ? '添加中...' : '确认添加'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
