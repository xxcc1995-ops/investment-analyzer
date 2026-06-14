import { useState, useEffect, useMemo, useCallback } from 'react'
import ReactECharts from 'echarts-for-react'
import { stockApi } from '../services/api'
import { PageSection, TabBar, LoadingSpinner, EmptyState } from '../components/ui'
import type {
  FinancialStatementsData,
  IncomeStatement,
  BalanceSheet,
  CashFlowStatement,
  FinancialAnalysisResult,
} from '../services/api'

// ============ 辅助函数 ============

const formatWan = (num: number | null | undefined) => {
  if (num === null || num === undefined) return '-'
  const wan = num / 10000
  if (Math.abs(wan) >= 10000) return (wan / 10000).toFixed(2) + '亿'
  return wan.toFixed(2) + '万'
}

const formatYi = (num: number | null | undefined) => {
  if (num === null || num === undefined) return '-'
  return (num / 100000000).toFixed(2) + '亿'
}

const formatRatio = (num: number | null | undefined) => {
  if (num === null || num === undefined) return '-'
  return num.toFixed(2) + '%'
}

const formatRatioNum = (num: number | null | undefined) => {
  if (num === null || num === undefined) return '-'
  return num.toFixed(2)
}

/** 计算同比变化率 */
const calcYoY = (current: number | null | undefined, previous: number | null | undefined): number | null => {
  if (current === null || current === undefined || previous === null || previous === undefined) return null
  if (previous === 0) return null
  return ((current - previous) / Math.abs(previous)) * 100
}

/** 同比增长率显示 */
const formatYoY = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return '-'
  const sign = val >= 0 ? '+' : ''
  return sign + val.toFixed(1) + '%'
}

/** 同比增长率颜色 */
const yoyColor = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return 'var(--text-muted)'
  if (val > 20) return COLORS.green
  if (val > 0) return '#6bc46d'
  if (val > -20) return COLORS.orange
  return COLORS.red
}

// ============ 报告类型配置 ============

const REPORT_TYPES = [
  { key: 'all', label: '全部' },
  { key: 'annual', label: '年报' },
  { key: 'q3', label: '三季报' },
  { key: 'semi', label: '中报' },
  { key: 'q1', label: '一季报' },
]

const STATEMENT_TABS = [
  { key: 'income', label: '利润表' },
  { key: 'balance', label: '资产负债表' },
  { key: 'cashflow', label: '现金流量表' },
  { key: 'expense', label: '费用率分析' },
]

// ============ 颜色配置 ============

const COLORS = {
  blue: '#58a6ff',
  green: '#3fb950',
  red: '#f85149',
  orange: '#d29922',
  purple: '#bc8cff',
  cyan: '#39d2c0',
  pink: '#f778ba',
  yellow: '#e3b341',
}

// ============ CSV导出工具 ============

function exportToCSV(filename: string, headers: string[], rows: (string | number)[][]) {
  const csvContent = [
    headers.join(','),
    ...rows.map(row => row.map(cell => {
      const s = String(cell ?? '')
      return s.includes(',') || s.includes('"') ? `"${s.replace(/"/g, '""')}"` : s
    }).join(','))
  ].join('\n')

  const BOM = '﻿'
  const blob = new Blob([BOM + csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

// ============ 组件属性 ============

interface FinancialStatementsProps {
  code: string
}

// ============ 主组件 ============

export default function FinancialStatements({ code }: FinancialStatementsProps) {
  const [data, setData] = useState<FinancialStatementsData | null>(null)
  const [analysis, setAnalysis] = useState<FinancialAnalysisResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [reportType, setReportType] = useState<string>('annual')
  const [statementTab, setStatementTab] = useState<string>('income')

  // 加载数据
  useEffect(() => {
    if (!code) return
    setLoading(true)
    setData(null)
    setAnalysis(null)
    Promise.all([
      stockApi.getFinancialStatements(code),
      stockApi.getFinancialAnalysis(code).catch(() => null),
    ])
      .then(([finRes, anaRes]) => {
        setData(finRes.data)
        if (anaRes?.data) setAnalysis(anaRes.data)
      })
      .catch(err => {
        console.error('获取三大报表失败:', err)
      })
      .finally(() => setLoading(false))
  }, [code])

  // 按报告类型过滤
  const filterByType = <T extends { report_type: string }>(list: T[]): T[] => {
    if (reportType === 'all') return list
    return list.filter(item => item.report_type === reportType)
  }

  // 按日期正序（图表用）
  const sortedIncome = useMemo(() => {
    if (!data) return []
    return filterByType(data.income).slice().reverse()
  }, [data, reportType])

  const sortedBalance = useMemo(() => {
    if (!data) return []
    return filterByType(data.balance).slice().reverse()
  }, [data, reportType])

  const sortedCashflow = useMemo(() => {
    if (!data) return []
    return filterByType(data.cashflow).slice().reverse()
  }, [data, reportType])

  // 按日期倒序（表格用）
  const tableIncome = useMemo(() => filterByType(data?.income || []), [data, reportType])
  const tableBalance = useMemo(() => filterByType(data?.balance || []), [data, reportType])
  const tableCashflow = useMemo(() => filterByType(data?.cashflow || []), [data, reportType])

  // ============ 导出功能 ============
  const handleExportIncome = useCallback(() => {
    const headers = ['报告期', '营业收入', '营业成本', '销售费用', '管理费用', '研发费用', '财务费用', '营业利润', '归母净利润', '毛利率%', '营业利润率%', '净利率%', '营收同比%', '利润同比%']
    const yoyMap = buildYoYMap(data?.income || [])
    const rows = tableIncome.map(row => {
      const yoy = yoyMap.get(row.report_date)
      return [
        row.report_name || row.report_date,
        row.total_revenue ?? '',
        row.operating_cost ?? '',
        row.sell_expense ?? '',
        row.manage_expense ?? '',
        row.research_expense ?? '',
        row.finance_expense ?? '',
        row.operate_profit ?? '',
        row.parent_net_profit ?? '',
        row.gross_margin ?? '',
        row.operating_margin ?? '',
        row.net_margin ?? '',
        yoy?.revenue_yoy?.toFixed(1) ?? '',
        yoy?.profit_yoy?.toFixed(1) ?? '',
      ]
    })
    exportToCSV(`${code}_利润表.csv`, headers, rows)
  }, [code, tableIncome, data])

  const handleExportBalance = useCallback(() => {
    const headers = ['报告期', '货币资金', '应收账款', '存货', '总资产', '总负债', '股东权益', '资产负债率%', '流动比率', '速动比率']
    const rows = tableBalance.map(row => [
      row.report_name || row.report_date,
      row.monetary_funds ?? '',
      row.accounts_receivable ?? '',
      row.inventory ?? '',
      row.total_assets ?? '',
      row.total_liabilities ?? '',
      row.total_equity ?? '',
      row.debt_ratio ?? '',
      row.current_ratio ?? '',
      row.quick_ratio ?? '',
    ])
    exportToCSV(`${code}_资产负债表.csv`, headers, rows)
  }, [code, tableBalance])

  const handleExportCashflow = useCallback(() => {
    const headers = ['报告期', '经营现金流', '投资现金流', '融资现金流', 'CAPEX', '折旧摊销', '自由现金流', '期末现金', '现金流/净利润%']
    const rows = tableCashflow.map(row => [
      row.report_name || row.report_date,
      row.netcash_operate ?? '',
      row.netcash_invest ?? '',
      row.netcash_finance ?? '',
      row.capex ?? '',
      row.depreciation_amortization ?? '',
      row.free_cashflow ?? '',
      row.cash_end ?? '',
      row.operating_to_profit_ratio ?? '',
    ])
    exportToCSV(`${code}_现金流量表.csv`, headers, rows)
  }, [code, tableCashflow])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '60px 0' }}>
        <div className="spinner" />
        <p style={{ color: 'var(--text-secondary)', marginTop: 12 }}>加载三大报表数据...</p>
      </div>
    )
  }

  if (!data || (!data.income.length && !data.balance.length && !data.cashflow.length)) {
    return (
      <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
        暂无三大报表数据
      </div>
    )
  }

  const exportButtons: Record<string, () => void> = {
    income: handleExportIncome,
    balance: handleExportBalance,
    cashflow: handleExportCashflow,
  }

  return (
    <div>
      {/* 财务分析摘要 */}
      {analysis && <AnalysisSummary analysis={analysis} />}

      {/* 报告类型切换 + 导出按钮 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
        <div className="report-type-switcher">
          {REPORT_TYPES.map(t => (
            <button
              key={t.key}
              className={`report-type-btn ${reportType === t.key ? 'active' : ''}`}
              onClick={() => setReportType(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
        {statementTab !== 'expense' && (
          <button
            onClick={exportButtons[statementTab]}
            style={{
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--border-primary)',
              borderRadius: 6,
              padding: '6px 14px',
              fontSize: 12,
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            导出CSV
          </button>
        )}
      </div>

      {/* 报表Tab切换 */}
      <div className="tabs" style={{ marginBottom: 16 }}>
        {STATEMENT_TABS.map(t => (
          <button
            key={t.key}
            className={`tab ${statementTab === t.key ? 'active' : ''}`}
            onClick={() => setStatementTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab内容 */}
      {statementTab === 'income' && (
        <IncomeTab data={tableIncome} chartData={sortedIncome} allData={data.income} />
      )}
      {statementTab === 'balance' && (
        <BalanceTab data={tableBalance} chartData={sortedBalance} allData={data.balance} />
      )}
      {statementTab === 'cashflow' && (
        <CashflowTab data={tableCashflow} chartData={sortedCashflow} />
      )}
      {statementTab === 'expense' && (
        <ExpenseTab data={tableIncome} chartData={sortedIncome} />
      )}
    </div>
  )
}

// ============ 同比计算工具 ============

/** 为利润表构建同比增长率映射: report_date -> { revenue_yoy, profit_yoy } */
function buildYoYMap(allIncome: IncomeStatement[]) {
  const map = new Map<string, { revenue_yoy: number | null; profit_yoy: number | null }>()
  // 按 report_type 分组
  const byType = new Map<string, IncomeStatement[]>()
  for (const item of allIncome) {
    const arr = byType.get(item.report_type) || []
    arr.push(item)
    byType.set(item.report_type, arr)
  }

  // 每种类型内按日期排序后计算同比
  for (const [, items] of byType) {
    const sorted = items.slice().sort((a, b) => b.report_date.localeCompare(a.report_date))
    for (let i = 0; i < sorted.length; i++) {
      const current = sorted[i]
      // 找上一年同期
      const prevDate = current.report_date.replace(/^\d{4}/, (y) => String(Number(y) - 1))
      const prev = sorted.find(s => s.report_date === prevDate)
      map.set(current.report_date, {
        revenue_yoy: calcYoY(current.total_revenue, prev?.total_revenue),
        profit_yoy: calcYoY(current.parent_net_profit, prev?.parent_net_profit),
      })
    }
  }
  return map
}

/** 为资产负债表构建同比变化率映射 */
function buildBalanceYoYMap(allBalance: BalanceSheet[]) {
  const map = new Map<string, { assets_yoy: number | null; equity_yoy: number | null; debt_yoy: number | null }>()
  const byType = new Map<string, BalanceSheet[]>()
  for (const item of allBalance) {
    const arr = byType.get(item.report_type) || []
    arr.push(item)
    byType.set(item.report_type, arr)
  }
  for (const [, items] of byType) {
    const sorted = items.slice().sort((a, b) => b.report_date.localeCompare(a.report_date))
    for (let i = 0; i < sorted.length; i++) {
      const current = sorted[i]
      const prevDate = current.report_date.replace(/^\d{4}/, (y) => String(Number(y) - 1))
      const prev = sorted.find(s => s.report_date === prevDate)
      map.set(current.report_date, {
        assets_yoy: calcYoY(current.total_assets, prev?.total_assets),
        equity_yoy: calcYoY(current.total_equity, prev?.total_equity),
        debt_yoy: calcYoY(current.total_liabilities, prev?.total_liabilities),
      })
    }
  }
  return map
}

/** 为现金流量表构建同比变化率映射 */
function buildCashflowYoYMap(allCashflow: CashFlowStatement[]) {
  const map = new Map<string, { ocf_yoy: number | null; fcf_yoy: number | null }>()
  const byType = new Map<string, CashFlowStatement[]>()
  for (const item of allCashflow) {
    const arr = byType.get(item.report_type) || []
    arr.push(item)
    byType.set(item.report_type, arr)
  }
  for (const [, items] of byType) {
    const sorted = items.slice().sort((a, b) => b.report_date.localeCompare(a.report_date))
    for (let i = 0; i < sorted.length; i++) {
      const current = sorted[i]
      const prevDate = current.report_date.replace(/^\d{4}/, (y) => String(Number(y) - 1))
      const prev = sorted.find(s => s.report_date === prevDate)
      map.set(current.report_date, {
        ocf_yoy: calcYoY(current.netcash_operate, prev?.netcash_operate),
        fcf_yoy: calcYoY(current.free_cashflow, prev?.free_cashflow),
      })
    }
  }
  return map
}

// ============ 利润表Tab ============

function IncomeTab({ data, chartData, allData }: { data: IncomeStatement[]; chartData: IncomeStatement[]; allData?: IncomeStatement[] }) {
  const yoyMap = useMemo(() => buildYoYMap(allData || data), [allData, data])

  // YoY图表数据
  const yoyChartData = useMemo(() => {
    return chartData.map(d => {
      const yoy = yoyMap.get(d.report_date)
      return { ...d, revenue_yoy: yoy?.revenue_yoy ?? null, profit_yoy: yoy?.profit_yoy ?? null }
    })
  }, [chartData, yoyMap])

  const getRevenueProfitChart = () => ({
    tooltip: { trigger: 'axis' },
    legend: { data: ['营业收入', '归母净利润'], textStyle: { color: '#8b949e' }, top: 0 },
    grid: { left: 60, right: 60, top: 40, bottom: 60 },
    xAxis: {
      type: 'category',
      data: chartData.map(d => d.report_date),
      axisLabel: { color: '#8b949e', rotate: 45, fontSize: 10 },
    },
    yAxis: [
      { type: 'value', name: '营业收入(亿)', axisLabel: { color: '#8b949e', formatter: (v: number) => (v / 1e8).toFixed(0) }, splitLine: { lineStyle: { color: '#21262d' } } },
      { type: 'value', name: '净利润(亿)', axisLabel: { color: '#8b949e', formatter: (v: number) => (v / 1e8).toFixed(0) }, splitLine: { show: false } },
    ],
    series: [
      { name: '营业收入', type: 'bar', data: chartData.map(d => d.total_revenue), itemStyle: { color: COLORS.blue }, barMaxWidth: 30 },
      { name: '归母净利润', type: 'line', yAxisIndex: 1, data: chartData.map(d => d.parent_net_profit), smooth: true, itemStyle: { color: COLORS.red }, lineStyle: { width: 2 } },
    ],
  })

  const getMarginChart = () => ({
    tooltip: { trigger: 'axis' },
    legend: { data: ['毛利率', '营业利润率', '净利率'], textStyle: { color: '#8b949e' }, top: 0 },
    grid: { left: 60, right: 30, top: 40, bottom: 60 },
    xAxis: {
      type: 'category',
      data: chartData.map(d => d.report_date),
      axisLabel: { color: '#8b949e', rotate: 45, fontSize: 10 },
    },
    yAxis: { type: 'value', name: '%', axisLabel: { color: '#8b949e' }, splitLine: { lineStyle: { color: '#21262d' } } },
    series: [
      { name: '毛利率', type: 'line', data: chartData.map(d => d.gross_margin), smooth: true, itemStyle: { color: COLORS.red }, lineStyle: { width: 2 } },
      { name: '营业利润率', type: 'line', data: chartData.map(d => d.operating_margin), smooth: true, itemStyle: { color: COLORS.orange }, lineStyle: { width: 2 } },
      { name: '净利率', type: 'line', data: chartData.map(d => d.net_margin), smooth: true, itemStyle: { color: COLORS.blue }, lineStyle: { width: 2 } },
    ],
  })

  // 同比增长率图表
  const getYoYGrowthChart = () => ({
    tooltip: {
      trigger: 'axis',
      formatter: (params: { seriesName: string; value: number | null; color: string; axisValue?: string }[]) => {
        let result = `<b>${params[0]?.axisValue}</b><br/>`
        params.forEach(p => {
          const val = p.value
          if (val !== null && val !== undefined) {
            result += `<span style="color:${p.color}">${p.seriesName}: ${val >= 0 ? '+' : ''}${val.toFixed(1)}%</span><br/>`
          }
        })
        return result
      },
    },
    legend: { data: ['营收同比', '净利润同比'], textStyle: { color: '#8b949e' }, top: 0 },
    grid: { left: 60, right: 30, top: 40, bottom: 60 },
    xAxis: {
      type: 'category',
      data: yoyChartData.map(d => d.report_date),
      axisLabel: { color: '#8b949e', rotate: 45, fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      name: '%',
      axisLabel: { color: '#8b949e' },
      splitLine: { lineStyle: { color: '#21262d' } },
    },
    series: [
      {
        name: '营收同比',
        type: 'bar',
        data: yoyChartData.map(d => d.revenue_yoy),
        itemStyle: {
          color: (params: { value: number | null }) => (params.value !== null && params.value >= 0) ? COLORS.blue : '#3d5a80',
        },
        barMaxWidth: 20,
      },
      {
        name: '净利润同比',
        type: 'line',
        data: yoyChartData.map(d => d.profit_yoy),
        smooth: true,
        itemStyle: { color: COLORS.orange },
        lineStyle: { width: 2 },
        connectNulls: true,
      },
    ],
  })

  return (
    <>
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>报告期</th>
              <th>营业收入</th>
              <th>同比</th>
              <th>营业成本</th>
              <th>销售费用</th>
              <th>管理费用</th>
              <th>研发费用</th>
              <th>财务费用</th>
              <th>营业利润</th>
              <th>归母净利润</th>
              <th>同比</th>
              <th>毛利率</th>
              <th>净利率</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => {
              const yoy = yoyMap.get(row.report_date)
              return (
                <tr key={i}>
                  <td>{row.report_name || row.report_date}</td>
                  <td>{formatWan(row.total_revenue)}</td>
                  <td style={{ color: yoyColor(yoy?.revenue_yoy), fontSize: 12 }}>{formatYoY(yoy?.revenue_yoy)}</td>
                  <td>{formatWan(row.operating_cost)}</td>
                  <td>{formatWan(row.sell_expense)}</td>
                  <td>{formatWan(row.manage_expense)}</td>
                  <td>{formatWan(row.research_expense)}</td>
                  <td>{formatWan(row.finance_expense)}</td>
                  <td>{formatWan(row.operate_profit)}</td>
                  <td style={{ color: (row.parent_net_profit || 0) >= 0 ? COLORS.green : COLORS.red }}>
                    {formatWan(row.parent_net_profit)}
                  </td>
                  <td style={{ color: yoyColor(yoy?.profit_yoy), fontSize: 12 }}>{formatYoY(yoy?.profit_yoy)}</td>
                  <td>{formatRatio(row.gross_margin)}</td>
                  <td>{formatRatio(row.net_margin)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="charts-row">
        <div className="chart-container">
          <div className="chart-title">营收与净利润趋势</div>
          <ReactECharts option={getRevenueProfitChart()} style={{ height: 320 }} />
        </div>
        <div className="chart-container">
          <div className="chart-title">利润率趋势</div>
          <ReactECharts option={getMarginChart()} style={{ height: 320 }} />
        </div>
      </div>
      <div className="charts-row">
        <div className="chart-container">
          <div className="chart-title">同比增长率</div>
          <ReactECharts option={getYoYGrowthChart()} style={{ height: 320 }} />
        </div>
      </div>
    </>
  )
}

// ============ 资产负债表Tab ============

function BalanceTab({ data, chartData, allData }: { data: BalanceSheet[]; chartData: BalanceSheet[]; allData?: BalanceSheet[] }) {
  const balanceYoYMap = useMemo(() => buildBalanceYoYMap(allData || data), [allData, data])

  const getAssetLiabilityChart = () => ({
    tooltip: { trigger: 'axis' },
    legend: { data: ['总资产', '总负债', '股东权益'], textStyle: { color: '#8b949e' }, top: 0 },
    grid: { left: 60, right: 30, top: 40, bottom: 60 },
    xAxis: {
      type: 'category',
      data: chartData.map(d => d.report_date),
      axisLabel: { color: '#8b949e', rotate: 45, fontSize: 10 },
    },
    yAxis: { type: 'value', name: '亿元', axisLabel: { color: '#8b949e', formatter: (v: number) => (v / 1e8).toFixed(0) }, splitLine: { lineStyle: { color: '#21262d' } } },
    series: [
      { name: '总资产', type: 'bar', stack: 'total', data: chartData.map(d => d.total_assets), itemStyle: { color: COLORS.blue }, barMaxWidth: 30 },
      { name: '总负债', type: 'bar', stack: 'debt', data: chartData.map(d => d.total_liabilities), itemStyle: { color: COLORS.red }, barMaxWidth: 30 },
      { name: '股东权益', type: 'line', data: chartData.map(d => d.total_equity), smooth: true, itemStyle: { color: COLORS.green }, lineStyle: { width: 2 } },
    ],
  })

  const getDebtStructureChart = () => ({
    tooltip: { trigger: 'axis' },
    legend: { data: ['短期借款', '长期借款'], textStyle: { color: '#8b949e' }, top: 0 },
    grid: { left: 60, right: 30, top: 40, bottom: 60 },
    xAxis: {
      type: 'category',
      data: chartData.map(d => d.report_date),
      axisLabel: { color: '#8b949e', rotate: 45, fontSize: 10 },
    },
    yAxis: { type: 'value', name: '亿元', axisLabel: { color: '#8b949e', formatter: (v: number) => (v / 1e8).toFixed(0) }, splitLine: { lineStyle: { color: '#21262d' } } },
    series: [
      { name: '短期借款', type: 'bar', stack: 'loan', data: chartData.map(d => d.short_term_borrowing), itemStyle: { color: COLORS.orange }, barMaxWidth: 30 },
      { name: '长期借款', type: 'bar', stack: 'loan', data: chartData.map(d => d.long_term_borrowing), itemStyle: { color: COLORS.purple }, barMaxWidth: 30 },
    ],
  })

  const getRatioChart = () => ({
    tooltip: { trigger: 'axis' },
    legend: { data: ['资产负债率', '流动比率', '速动比率'], textStyle: { color: '#8b949e' }, top: 0 },
    grid: { left: 60, right: 30, top: 40, bottom: 60 },
    xAxis: {
      type: 'category',
      data: chartData.map(d => d.report_date),
      axisLabel: { color: '#8b949e', rotate: 45, fontSize: 10 },
    },
    yAxis: { type: 'value', axisLabel: { color: '#8b949e' }, splitLine: { lineStyle: { color: '#21262d' } } },
    series: [
      { name: '资产负债率', type: 'line', data: chartData.map(d => d.debt_ratio), smooth: true, itemStyle: { color: COLORS.red }, lineStyle: { width: 2 } },
      { name: '流动比率', type: 'line', data: chartData.map(d => d.current_ratio), smooth: true, itemStyle: { color: COLORS.blue }, lineStyle: { width: 2 } },
      { name: '速动比率', type: 'line', data: chartData.map(d => d.quick_ratio), smooth: true, itemStyle: { color: COLORS.green }, lineStyle: { width: 2 } },
    ],
  })

  // 资产结构饼图
  const getAssetStructureChart = () => {
    const latest = chartData.length > 0 ? chartData[chartData.length - 1] : null
    if (!latest) return {}
    const currentAssets = latest.total_current_assets || 0
    const nonCurrentAssets = latest.total_non_current_assets || (latest.total_assets && latest.total_current_assets ? latest.total_assets - latest.total_current_assets : 0)
    return {
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend: { orient: 'vertical', right: 10, top: 'center', textStyle: { color: '#8b949e', fontSize: 11 } },
      series: [{
        type: 'pie',
        radius: ['35%', '65%'],
        center: ['40%', '50%'],
        data: [
          { value: currentAssets, name: '流动资产', itemStyle: { color: COLORS.blue } },
          { value: nonCurrentAssets, name: '非流动资产', itemStyle: { color: COLORS.purple } },
        ],
        label: { color: '#8b949e', fontSize: 11, formatter: '{b}\n{d}%' },
        emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' } },
      }],
    }
  }

  return (
    <>
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>报告期</th>
              <th>货币资金</th>
              <th>应收账款</th>
              <th>存货</th>
              <th>总资产</th>
              <th>同比</th>
              <th>总负债</th>
              <th>股东权益</th>
              <th>同比</th>
              <th>资产负债率</th>
              <th>流动比率</th>
              <th>速动比率</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => {
              const yoy = balanceYoYMap.get(row.report_date)
              return (
                <tr key={i}>
                  <td>{row.report_name || row.report_date}</td>
                  <td>{formatWan(row.monetary_funds)}</td>
                  <td>{formatWan(row.accounts_receivable)}</td>
                  <td>{formatWan(row.inventory)}</td>
                  <td>{formatWan(row.total_assets)}</td>
                  <td style={{ color: yoyColor(yoy?.assets_yoy), fontSize: 12 }}>{formatYoY(yoy?.assets_yoy)}</td>
                  <td>{formatWan(row.total_liabilities)}</td>
                  <td>{formatWan(row.total_equity)}</td>
                  <td style={{ color: yoyColor(yoy?.equity_yoy), fontSize: 12 }}>{formatYoY(yoy?.equity_yoy)}</td>
                  <td style={{ color: (row.debt_ratio || 0) > 60 ? COLORS.red : (row.debt_ratio || 0) > 40 ? COLORS.orange : COLORS.green }}>
                    {formatRatio(row.debt_ratio)}
                  </td>
                  <td style={{ color: (row.current_ratio || 0) >= 1.5 ? COLORS.green : (row.current_ratio || 0) >= 1 ? COLORS.orange : COLORS.red }}>
                    {formatRatioNum(row.current_ratio)}
                  </td>
                  <td style={{ color: (row.quick_ratio || 0) >= 1 ? COLORS.green : (row.quick_ratio || 0) >= 0.5 ? COLORS.orange : COLORS.red }}>
                    {formatRatioNum(row.quick_ratio)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="charts-row">
        <div className="chart-container">
          <div className="chart-title">资产与负债趋势</div>
          <ReactECharts option={getAssetLiabilityChart()} style={{ height: 320 }} />
        </div>
        <div className="chart-container">
          <div className="chart-title">资产结构（最新期）</div>
          <ReactECharts option={getAssetStructureChart()} style={{ height: 320 }} />
        </div>
      </div>
      <div className="charts-row">
        <div className="chart-container">
          <div className="chart-title">债务结构</div>
          <ReactECharts option={getDebtStructureChart()} style={{ height: 320 }} />
        </div>
        <div className="chart-container">
          <div className="chart-title">偿债能力指标</div>
          <ReactECharts option={getRatioChart()} style={{ height: 320 }} />
        </div>
      </div>
    </>
  )
}

// ============ 现金流量表Tab ============

function CashflowTab({ data, chartData }: { data: CashFlowStatement[]; chartData: CashFlowStatement[] }) {
  const getCashflowChart = () => ({
    tooltip: { trigger: 'axis' },
    legend: { data: ['经营现金流', '投资现金流', '融资现金流'], textStyle: { color: '#8b949e' }, top: 0 },
    grid: { left: 60, right: 30, top: 40, bottom: 60 },
    xAxis: {
      type: 'category',
      data: chartData.map(d => d.report_date),
      axisLabel: { color: '#8b949e', rotate: 45, fontSize: 10 },
    },
    yAxis: { type: 'value', name: '亿元', axisLabel: { color: '#8b949e', formatter: (v: number) => (v / 1e8).toFixed(0) }, splitLine: { lineStyle: { color: '#21262d' } } },
    series: [
      { name: '经营现金流', type: 'bar', data: chartData.map(d => d.netcash_operate), itemStyle: { color: COLORS.green }, barMaxWidth: 20 },
      { name: '投资现金流', type: 'bar', data: chartData.map(d => d.netcash_invest), itemStyle: { color: COLORS.red }, barMaxWidth: 20 },
      { name: '融资现金流', type: 'bar', data: chartData.map(d => d.netcash_finance), itemStyle: { color: COLORS.blue }, barMaxWidth: 20 },
    ],
  })

  const getFcfChart = () => ({
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 30, top: 30, bottom: 60 },
    xAxis: {
      type: 'category',
      data: chartData.map(d => d.report_date),
      axisLabel: { color: '#8b949e', rotate: 45, fontSize: 10 },
    },
    yAxis: { type: 'value', name: '亿元', axisLabel: { color: '#8b949e', formatter: (v: number) => (v / 1e8).toFixed(0) }, splitLine: { lineStyle: { color: '#21262d' } } },
    series: [{
      name: '自由现金流',
      type: 'bar',
      data: chartData.map(d => d.free_cashflow),
      itemStyle: {
        color: (params: { value: number }) => params.value >= 0 ? COLORS.green : COLORS.red,
      },
      barMaxWidth: 30,
    }],
  })

  const getQualityChart = () => ({
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 30, top: 30, bottom: 60 },
    xAxis: {
      type: 'category',
      data: chartData.map(d => d.report_date),
      axisLabel: { color: '#8b949e', rotate: 45, fontSize: 10 },
    },
    yAxis: { type: 'value', name: '%', axisLabel: { color: '#8b949e' }, splitLine: { lineStyle: { color: '#21262d' } } },
    series: [
      {
        name: '经营现金流/净利润',
        type: 'line',
        data: chartData.map(d => d.operating_to_profit_ratio),
        smooth: true,
        itemStyle: { color: COLORS.cyan },
        lineStyle: { width: 2 },
        markLine: {
          data: [{ yAxis: 100, name: '100%', lineStyle: { color: '#8b949e', type: 'dashed' } }],
          label: { formatter: '100%', color: '#8b949e' },
        },
      },
    ],
  })

  // CAPEX趋势图
  const getCapexChart = () => ({
    tooltip: { trigger: 'axis' },
    legend: { data: ['CAPEX', '自由现金流'], textStyle: { color: '#8b949e' }, top: 0 },
    grid: { left: 60, right: 30, top: 40, bottom: 60 },
    xAxis: {
      type: 'category',
      data: chartData.map(d => d.report_date),
      axisLabel: { color: '#8b949e', rotate: 45, fontSize: 10 },
    },
    yAxis: { type: 'value', name: '亿元', axisLabel: { color: '#8b949e', formatter: (v: number) => (v / 1e8).toFixed(0) }, splitLine: { lineStyle: { color: '#21262d' } } },
    series: [
      {
        name: 'CAPEX',
        type: 'bar',
        data: chartData.map(d => d.capex),
        itemStyle: { color: COLORS.orange },
        barMaxWidth: 20,
      },
      {
        name: '自由现金流',
        type: 'line',
        data: chartData.map(d => d.free_cashflow),
        smooth: true,
        itemStyle: { color: COLORS.green },
        lineStyle: { width: 2 },
      },
    ],
  })

  return (
    <>
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>报告期</th>
              <th>经营现金流</th>
              <th>投资现金流</th>
              <th>融资现金流</th>
              <th>CAPEX</th>
              <th>折旧摊销</th>
              <th>自由现金流</th>
              <th>期末现金</th>
              <th>现金流/净利润</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr key={i}>
                <td>{row.report_name || row.report_date}</td>
                <td style={{ color: (row.netcash_operate || 0) >= 0 ? COLORS.green : COLORS.red }}>
                  {formatWan(row.netcash_operate)}
                </td>
                <td style={{ color: (row.netcash_invest || 0) >= 0 ? COLORS.green : COLORS.red }}>
                  {formatWan(row.netcash_invest)}
                </td>
                <td style={{ color: (row.netcash_finance || 0) >= 0 ? COLORS.green : COLORS.red }}>
                  {formatWan(row.netcash_finance)}
                </td>
                <td style={{ color: COLORS.orange }}>
                  {formatWan(row.capex)}
                </td>
                <td style={{ color: 'var(--text-secondary)' }}>
                  {formatWan(row.depreciation_amortization)}
                </td>
                <td style={{ color: (row.free_cashflow || 0) >= 0 ? COLORS.green : COLORS.red }}>
                  {formatWan(row.free_cashflow)}
                </td>
                <td>{formatWan(row.cash_end)}</td>
                <td style={{ color: (row.operating_to_profit_ratio || 0) >= 100 ? COLORS.green : COLORS.orange }}>
                  {formatRatio(row.operating_to_profit_ratio)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="charts-row">
        <div className="chart-container">
          <div className="chart-title">三大现金流趋势</div>
          <ReactECharts option={getCashflowChart()} style={{ height: 320 }} />
        </div>
        <div className="chart-container">
          <div className="chart-title">自由现金流</div>
          <ReactECharts option={getFcfChart()} style={{ height: 320 }} />
        </div>
      </div>
      <div className="charts-row">
        <div className="chart-container">
          <div className="chart-title">CAPEX与自由现金流</div>
          <ReactECharts option={getCapexChart()} style={{ height: 320 }} />
        </div>
        <div className="chart-container">
          <div className="chart-title">现金流质量（经营现金流/净利润）</div>
          <ReactECharts option={getQualityChart()} style={{ height: 320 }} />
        </div>
      </div>
    </>
  )
}

// ============ 费用率分析Tab ============

function ExpenseTab({ data, chartData }: { data: IncomeStatement[]; chartData: IncomeStatement[] }) {
  const getExpenseStackChart = () => ({
    tooltip: {
      trigger: 'axis',
      formatter: (params: { seriesName: string; value: number; color: string; axisValue?: string }[]) => {
        let result = `<b>${params[0]?.axisValue}</b><br/>`
        params.forEach(p => {
          result += `<span style="color:${p.color}">${p.seriesName}: ${p.value?.toFixed(2) ?? '-'}%</span><br/>`
        })
        return result
      },
    },
    legend: { data: ['销售费用率', '管理费用率', '研发费用率', '财务费用率'], textStyle: { color: '#8b949e' }, top: 0 },
    grid: { left: 60, right: 30, top: 40, bottom: 60 },
    xAxis: {
      type: 'category',
      data: chartData.map(d => d.report_date),
      axisLabel: { color: '#8b949e', rotate: 45, fontSize: 10 },
    },
    yAxis: { type: 'value', name: '%', axisLabel: { color: '#8b949e' }, splitLine: { lineStyle: { color: '#21262d' } } },
    series: [
      { name: '销售费用率', type: 'line', stack: 'expense', areaStyle: {}, data: chartData.map(d => d.sell_expense_ratio), smooth: true, itemStyle: { color: COLORS.red }, lineStyle: { width: 1 } },
      { name: '管理费用率', type: 'line', stack: 'expense', areaStyle: {}, data: chartData.map(d => d.manage_expense_ratio), smooth: true, itemStyle: { color: COLORS.orange }, lineStyle: { width: 1 } },
      { name: '研发费用率', type: 'line', stack: 'expense', areaStyle: {}, data: chartData.map(d => d.research_expense_ratio), smooth: true, itemStyle: { color: COLORS.purple }, lineStyle: { width: 1 } },
      { name: '财务费用率', type: 'line', stack: 'expense', areaStyle: {}, data: chartData.map(d => d.finance_expense_ratio), smooth: true, itemStyle: { color: COLORS.blue }, lineStyle: { width: 1 } },
    ],
  })

  const getMarginCompareChart = () => ({
    tooltip: { trigger: 'axis' },
    legend: { data: ['毛利率', '营业利润率', '净利率'], textStyle: { color: '#8b949e' }, top: 0 },
    grid: { left: 60, right: 30, top: 40, bottom: 60 },
    xAxis: {
      type: 'category',
      data: chartData.map(d => d.report_date),
      axisLabel: { color: '#8b949e', rotate: 45, fontSize: 10 },
    },
    yAxis: { type: 'value', name: '%', axisLabel: { color: '#8b949e' }, splitLine: { lineStyle: { color: '#21262d' } } },
    series: [
      { name: '毛利率', type: 'line', data: chartData.map(d => d.gross_margin), smooth: true, itemStyle: { color: COLORS.red }, lineStyle: { width: 2.5 } },
      { name: '营业利润率', type: 'line', data: chartData.map(d => d.operating_margin), smooth: true, itemStyle: { color: COLORS.orange }, lineStyle: { width: 2 } },
      { name: '净利率', type: 'line', data: chartData.map(d => d.net_margin), smooth: true, itemStyle: { color: COLORS.blue }, lineStyle: { width: 2 } },
    ],
  })

  const getExpenseBarChart = () => ({
    tooltip: { trigger: 'axis' },
    legend: { data: ['销售费用率', '管理费用率', '研发费用率', '财务费用率'], textStyle: { color: '#8b949e' }, top: 0 },
    grid: { left: 60, right: 30, top: 40, bottom: 60 },
    xAxis: {
      type: 'category',
      data: chartData.map(d => d.report_date),
      axisLabel: { color: '#8b949e', rotate: 45, fontSize: 10 },
    },
    yAxis: { type: 'value', name: '%', axisLabel: { color: '#8b949e' }, splitLine: { lineStyle: { color: '#21262d' } } },
    series: [
      { name: '销售费用率', type: 'bar', stack: 'expense', data: chartData.map(d => d.sell_expense_ratio), itemStyle: { color: COLORS.red }, barMaxWidth: 30 },
      { name: '管理费用率', type: 'bar', stack: 'expense', data: chartData.map(d => d.manage_expense_ratio), itemStyle: { color: COLORS.orange }, barMaxWidth: 30 },
      { name: '研发费用率', type: 'bar', stack: 'expense', data: chartData.map(d => d.research_expense_ratio), itemStyle: { color: COLORS.purple }, barMaxWidth: 30 },
      { name: '财务费用率', type: 'bar', stack: 'expense', data: chartData.map(d => d.finance_expense_ratio), itemStyle: { color: COLORS.blue }, barMaxWidth: 30 },
    ],
  })

  return (
    <>
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>报告期</th>
              <th>销售费用率</th>
              <th>管理费用率</th>
              <th>研发费用率</th>
              <th>财务费用率</th>
              <th>毛利率</th>
              <th>营业利润率</th>
              <th>净利率</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr key={i}>
                <td>{row.report_name || row.report_date}</td>
                <td>{formatRatio(row.sell_expense_ratio)}</td>
                <td>{formatRatio(row.manage_expense_ratio)}</td>
                <td>{formatRatio(row.research_expense_ratio)}</td>
                <td>{formatRatio(row.finance_expense_ratio)}</td>
                <td style={{ color: COLORS.green }}>{formatRatio(row.gross_margin)}</td>
                <td style={{ color: COLORS.orange }}>{formatRatio(row.operating_margin)}</td>
                <td style={{ color: COLORS.blue }}>{formatRatio(row.net_margin)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="charts-row">
        <div className="chart-container">
          <div className="chart-title">费用率堆叠趋势（成本结构变化）</div>
          <ReactECharts option={getExpenseStackChart()} style={{ height: 350 }} />
        </div>
        <div className="chart-container">
          <div className="chart-title">利润率对比</div>
          <ReactECharts option={getMarginCompareChart()} style={{ height: 350 }} />
        </div>
      </div>
      <div className="charts-row">
        <div className="chart-container">
          <div className="chart-title">费用率堆叠柱状图</div>
          <ReactECharts option={getExpenseBarChart()} style={{ height: 320 }} />
        </div>
      </div>
    </>
  )
}

// ============ 机构级财务分析摘要 ============

function AnalysisSummary({ analysis }: { analysis: FinancialAnalysisResult }) {
  const { score, grade, conclusion, strengths, risks, dimension_scores, dimensions } = analysis
  const scores = dimension_scores || { earnings: 0, growth: 0, safety: 0, efficiency: 0, cashflow: 0, moat: 0, management: 0 }

  const getGradeColor = (g: string) => {
    switch (g) {
      case 'A': return '#3fb950'
      case 'B': return '#58a6ff'
      case 'C': return '#d29922'
      case 'D': return '#f85149'
      case 'F': return '#8b949e'
      default: return '#8b949e'
    }
  }

  const getScoreColor = (s: number) => {
    if (s >= 70) return '#3fb950'
    if (s >= 50) return '#58a6ff'
    if (s >= 30) return '#d29922'
    return '#f85149'
  }

  const DIM_LABELS: Record<string, string> = {
    earnings: '盈利能力',
    growth: '成长性',
    safety: '财务安全',
    efficiency: '经营效率',
    cashflow: '现金流',
    moat: '护城河',
    management: '管理层',
  }

  // 7维雷达图
  const radarOption = {
    radar: {
      indicator: Object.keys(scores).map(k => ({ name: DIM_LABELS[k] || k, max: 100 })),
      shape: 'circle',
      splitArea: { areaStyle: { color: ['rgba(88,166,255,0.05)', 'rgba(88,166,255,0.1)'] } },
      axisLine: { lineStyle: { color: '#30363d' } },
      splitLine: { lineStyle: { color: '#21262d' } },
      axisName: { color: '#8b949e', fontSize: 11 },
    },
    series: [{
      type: 'radar',
      data: [{
        value: Object.values(scores),
        areaStyle: { color: 'rgba(88,166,255,0.2)' },
        lineStyle: { color: '#58a6ff', width: 2 },
        itemStyle: { color: '#58a6ff' },
      }],
    }],
  }

  // 提取关键指标
  const dimDetails = dimensions || {}
  const keyMetrics: { label: string; value: string; color?: string }[] = []
  const moatMetrics = dimDetails.moat?.metrics || {}
  if (moatMetrics.gross_margin_avg) keyMetrics.push({ label: '毛利率均值', value: `${moatMetrics.gross_margin_avg}%` })
  if (moatMetrics.roe_above_15_count !== undefined) keyMetrics.push({ label: 'ROE>15%年数', value: `${moatMetrics.roe_above_15_count}/${moatMetrics.roe_total_years}` })
  const earnMetrics = dimDetails.earnings?.metrics || {}
  if (earnMetrics.roic) keyMetrics.push({ label: 'ROIC', value: `${earnMetrics.roic}%` })
  if (earnMetrics.accruals_ratio !== undefined) keyMetrics.push({ label: '应计利润比率', value: `${(earnMetrics.accruals_ratio as number * 100).toFixed(1)}%` })
  const growthMetrics = dimDetails.growth?.metrics || {}
  if (growthMetrics.revenue_cagr) keyMetrics.push({ label: `营收${growthMetrics.revenue_cagr_years}年CAGR`, value: `${growthMetrics.revenue_cagr}%` })
  if (growthMetrics.profit_cagr) keyMetrics.push({ label: '利润CAGR', value: `${growthMetrics.profit_cagr}%` })
  const cfMetrics = dimDetails.cashflow?.metrics || {}
  if (cfMetrics.avg_cash_to_profit) keyMetrics.push({ label: '现金流/利润', value: `${cfMetrics.avg_cash_to_profit}%` })
  const mgmtMetrics = dimDetails.management?.metrics || {}
  if (mgmtMetrics.retention_return) keyMetrics.push({ label: '留存收益回报率', value: `${mgmtMetrics.retention_return}%` })
  const safetyMetrics = dimDetails.safety?.metrics || {}
  if (safetyMetrics.interest_coverage) keyMetrics.push({ label: '利息保障倍数', value: `${safetyMetrics.interest_coverage}x` })

  return (
    <div style={{
      background: 'var(--bg-secondary)',
      borderRadius: 12,
      padding: 20,
      marginBottom: 20,
      border: '1px solid var(--border-primary)',
    }}>
      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start', flexWrap: 'wrap' }}>
        {/* 评分 */}
        <div style={{ textAlign: 'center', minWidth: 100 }}>
          <div style={{ fontSize: 48, fontWeight: 800, color: getGradeColor(grade), lineHeight: 1 }}>
            {grade}
          </div>
          <div style={{ fontSize: 24, fontWeight: 700, color: getScoreColor(score), marginTop: 4 }}>
            {score}分
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>综合评级</div>
        </div>

        {/* 雷达图 */}
        <div style={{ flex: '0 0 280px' }}>
          <ReactECharts option={radarOption} style={{ height: 220 }} />
        </div>

        {/* 结论 + 关键指标 */}
        <div style={{ flex: 1, minWidth: 250 }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12, lineHeight: 1.6 }}>
            {conclusion}
          </div>

          {/* 关键指标 */}
          {keyMetrics.length > 0 && (
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 12 }}>
              {keyMetrics.map((m, i) => (
                <div key={i} style={{
                  background: 'rgba(88,166,255,0.1)',
                  borderRadius: 6,
                  padding: '4px 10px',
                  fontSize: 12,
                }}>
                  <span style={{ color: 'var(--text-muted)' }}>{m.label}: </span>
                  <span style={{ color: '#58a6ff', fontWeight: 600 }}>{m.value}</span>
                </div>
              ))}
            </div>
          )}

          {/* 优势 */}
          {strengths.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              {strengths.map((s, i) => (
                <div key={i} style={{ fontSize: 13, color: '#3fb950', lineHeight: 1.8 }}>&#10003; {s}</div>
              ))}
            </div>
          )}
          {/* 风险 */}
          {risks.length > 0 && (
            <div>
              {risks.map((r, i) => (
                <div key={i} style={{ fontSize: 13, color: '#f85149', lineHeight: 1.8 }}>&#9888; {r}</div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 7维评分条 */}
      <div style={{ display: 'flex', gap: 12, marginTop: 16, flexWrap: 'wrap' }}>
        {Object.entries(scores).map(([key, val]) => (
          <div key={key} style={{ flex: '1 1 100px', minWidth: 90 }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 3 }}>{DIM_LABELS[key] || key}</div>
            <div style={{ height: 5, borderRadius: 3, background: '#21262d', overflow: 'hidden' }}>
              <div style={{ height: '100%', borderRadius: 3, width: `${val}%`, background: getScoreColor(val), transition: 'width 0.5s ease' }} />
            </div>
            <div style={{ fontSize: 11, color: getScoreColor(val), marginTop: 2, fontWeight: 600 }}>{val}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
