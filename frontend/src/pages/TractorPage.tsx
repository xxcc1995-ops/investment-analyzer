import { useState, useEffect, useCallback, useMemo } from 'react'
import axios from 'axios'
import { tractorApi } from '../services/api'

const API_BASE = '/api/tractor'

// ==================== 类型定义 ====================

interface TractorAccount {
  account_id: string
  name: string
  broker_type: string
  enabled: boolean
}

interface AccountBalance extends TractorAccount {
  available_cash: number
  total_assets: number
  fund_shares: number
  fund_cost: number
  fund_profit: number
  last_query_time: string | null
}

interface SystemStatus {
  autoit: { installed: boolean; path: string }
  clients: {
    huabao: { installed: boolean; path: string; name: string }
    yinhe: { installed: boolean; path: string; name: string }
  }
  accounts: TractorAccount[]
  running: boolean
  current_operation: string | null
  market_status: string
  is_trading: boolean
}

interface ArbitrageOpportunity {
  fund_code: string
  fund_name: string
  direction: string
  premium_pct: number
  est_nav: number
  fund_price: number
  official_nav: number
  apply_limit: string
  apply_status: string
  turnover: number
  net_profit_pct: number
  risk_level: string
  est_confidence: string
}

interface AccountAllocation {
  account_id: string
  account_name: string
  broker_type: string
  available_cash: number
  recommended_amount: number
  max_amount: number
  shares_to_sell: number
  notes: string[]
}

interface AllocationPlan {
  fund_code: string
  fund_name: string
  direction: string
  premium_pct: number
  apply_limit_per_account: number
  total_accounts: number
  enabled_accounts: number
  allocations: AccountAllocation[]
  total_amount: number
  estimated_profit: number
  warnings: string[]
}

interface StrategyRecommendation {
  fund_code: string
  fund_name: string
  direction: string
  action: string
  confidence: string
  premium_pct: number
  net_profit_pct: number
  apply_limit: string
  apply_status: string
  reasons: string[]
  risk_warnings: string[]
  allocation_plan: AllocationPlan | null
}

interface RiskSettings {
  min_premium_pct: number
  max_single_amount: number
  max_total_amount: number
  min_cash_reserve: number
  max_daily_operations: number
  require_trading_hours: boolean
  block_low_liquidity: boolean
  min_turnover: number
}

interface RiskCheckResult {
  passed: boolean
  level: string
  checks: { name: string; passed: boolean; message: string; level: string }[]
  warnings: string[]
  blocked_reasons: string[]
}

interface OperationRecord {
  id: string
  timestamp: string
  operation: string
  fund_code: string
  fund_name: string
  direction: string
  premium_pct: number
  success: boolean
  message: string
  realized_pnl: number | null
  elapsed_seconds: number
}

interface PnLSummary {
  total_operations: number
  total_subscribes: number
  total_sells: number
  total_redeems: number
  total_realized_pnl: number
  win_rate: number
  avg_pnl_per_trade: number
  best_trade_pnl: number
  worst_trade_pnl: number
  operations: OperationRecord[]
}

interface OperationStatus {
  running: boolean
  current_operation: string | null
  log: string[]
  last_result: { success: boolean; message: string } | null
}

// ==================== 常量 ====================

const TABS = [
  { id: 'strategy', label: '策略总览', icon: ' ' },
  { id: 'accounts', label: '账户管理', icon: ' ' },
  { id: 'risk', label: '风险控制', icon: ' ' },
  { id: 'history', label: '操作历史', icon: ' ' },
]

const OPERATIONS = [
  { id: '仅登录查询', label: '仅登录查询', desc: '登录所有账户，查询持仓和资金', color: '#6b7280' },
  { id: '场内申购', label: '场内申购', desc: '溢价套利第一步：按限购金额申购', color: '#22c55e' },
  { id: '卖出', label: '场内卖出', desc: '溢价套利最后一步：按市价卖出', color: '#ef4444' },
  { id: '赎回', label: '赎回', desc: '折价套利最后一步：按净值赎回', color: '#3b82f6' },
  { id: '全部撤单', label: '全部撤单', desc: '撤销选中基金的全部订单', color: '#f97316' },
  { id: '逆回购', label: '逆回购', desc: '用剩余资金做204001逆回购', color: '#8b5cf6' },
  { id: '转账回银行', label: '转账回银行', desc: '把剩余资金全部转回银行', color: '#6366f1' },
]

// ==================== 工具函数 ====================

function formatMoney(val: number): string {
  if (val >= 10000) return `${(val / 10000).toFixed(1)}万`
  return val.toFixed(0)
}

function formatPct(val: number): string {
  return `${val >= 0 ? '+' : ''}${val.toFixed(2)}%`
}

function riskColor(level: string): string {
  switch (level) {
    case 'low': return '#22c55e'
    case 'medium': return '#f59e0b'
    case 'high': return '#f97316'
    case 'critical': return '#ef4444'
    default: return '#64748b'
  }
}

function directionColor(dir: string): string {
  if (dir === '溢价') return '#ef4444'
  if (dir === '折价') return '#22c55e'
  return '#64748b'
}

// ==================== 主页面 ====================

export default function TractorPage() {
  const [activeTab, setActiveTab] = useState('strategy')
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [opStatus, setOpStatus] = useState<OperationStatus | null>(null)
  const [loading, setLoading] = useState(false)

  // 策略数据
  const [opportunities, setOpportunities] = useState<ArbitrageOpportunity[]>([])
  const [recommendations, setRecommendations] = useState<StrategyRecommendation[]>([])
  const [strategyLoading, setStrategyLoading] = useState(false)
  const [scanFilter, setScanFilter] = useState({ min_premium: 2.0, min_amount: 1000, direction: 'all' })

  // 账户数据
  const [accounts, setAccounts] = useState<AccountBalance[]>([])
  const [showAddAccount, setShowAddAccount] = useState(false)
  const [newAccount, setNewAccount] = useState({ account_id: '', name: '', password: '', broker_type: 'huabao' })

  // 操作表单
  const [selectedOp, setSelectedOp] = useState('场内申购')
  const [fundCode, setFundCode] = useState('162411')
  const [fundName, setFundName] = useState('')
  const [sellPrice, setSellPrice] = useState('')
  const [sellQuantity, setSellQuantity] = useState('')
  const [premiumPct, setPremiumPct] = useState(0)

  // 风控设置
  const [riskSettings, setRiskSettings] = useState<RiskSettings | null>(null)
  const [riskCheck, setRiskCheck] = useState<RiskCheckResult | null>(null)

  // 历史数据
  const [history, setHistory] = useState<OperationRecord[]>([])
  const [pnlSummary, setPnlSummary] = useState<PnLSummary | null>(null)

  // 选中的基金（用于分配计算）
  const [selectedFund, setSelectedFund] = useState<ArbitrageOpportunity | null>(null)
  const [allocationPlan, setAllocationPlan] = useState<AllocationPlan | null>(null)

  // ==================== 数据加载 ====================

  const loadStatus = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/status`)
      setStatus(res.data)
    } catch (e) {
      console.error('获取系统状态失败:', e)
    }
  }, [])

  const loadOpStatus = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/operation-status`)
      setOpStatus(res.data)
    } catch (e) {
      console.error('获取操作状态失败:', e)
    }
  }, [])

  const loadAccounts = useCallback(async () => {
    try {
      const res = await tractorApi.getAccountBalances()
      setAccounts((res.data as any)?.accounts || [])
    } catch {
      // fallback to basic accounts
      try {
        const res = await tractorApi.getAccounts()
        setAccounts(((res.data as any)?.accounts || []).map((a: any) => ({
          ...a, available_cash: 0, total_assets: 0, fund_shares: 0,
          fund_cost: 0, fund_profit: 0, last_query_time: null,
        })))
      } catch (e2) {
        console.error('获取账户失败:', e2)
      }
    }
  }, [])

  const loadRiskSettings = useCallback(async () => {
    try {
      const res = await tractorApi.getRiskSettings()
      setRiskSettings((res.data as any)?.data || null)
    } catch (e) {
      console.error('获取风控设置失败:', e)
    }
  }, [])

  const loadHistory = useCallback(async () => {
    try {
      const [histRes, pnlRes] = await Promise.all([
        tractorApi.getHistory({ limit: 50 }),
        tractorApi.getPnLSummary(30),
      ])
      setHistory(((histRes.data as any)?.data?.records) || [])
      setPnlSummary((pnlRes.data as any)?.data || null)
    } catch (e) {
      console.error('获取历史数据失败:', e)
    }
  }, [])

  // 策略扫描
  const loadStrategy = useCallback(async () => {
    setStrategyLoading(true)
    try {
      const res = await tractorApi.getStrategyOverview(scanFilter)
      const data = (res.data as any)?.data || {}
      setOpportunities(data.opportunities || [])
      setRecommendations(data.recommendations || [])
    } catch (e) {
      console.error('策略扫描失败:', e)
    } finally {
      setStrategyLoading(false)
    }
  }, [scanFilter])

  // 初始化
  useEffect(() => {
    loadStatus()
    loadOpStatus()
    loadAccounts()
    loadRiskSettings()
    loadHistory()
  }, [loadStatus, loadOpStatus, loadAccounts, loadRiskSettings, loadHistory])

  // 定期刷新操作状态
  useEffect(() => {
    if (!opStatus?.running) return
    const timer = setInterval(loadOpStatus, 2000)
    return () => clearInterval(timer)
  }, [opStatus?.running, loadOpStatus])

  // ==================== 操作处理 ====================

  const handleAddAccount = async () => {
    if (!newAccount.account_id || !newAccount.password) return
    try {
      await tractorApi.addAccount(newAccount)
      setShowAddAccount(false)
      setNewAccount({ account_id: '', name: '', password: '', broker_type: 'huabao' })
      loadAccounts()
      loadStatus()
    } catch (e) {
      alert('添加账户失败')
    }
  }

  const handleDeleteAccount = async (accountId: string) => {
    if (!confirm(`确定删除账户 ${accountId}？`)) return
    try {
      await tractorApi.deleteAccount(accountId)
      loadAccounts()
      loadStatus()
    } catch (e) {
      alert('删除账户失败')
    }
  }

  const handleRun = async () => {
    setLoading(true)
    try {
      const res = await tractorApi.runOperation({
        operation: selectedOp,
        fund_code: fundCode,
        sell_price: sellPrice,
        sell_quantity: sellQuantity,
        premium_pct: premiumPct,
        fund_name: fundName,
      })
      const data = res.data as any
      if (data.success) {
        loadOpStatus()
        // 如果有风控拦截
        if (data.risk_check && !data.risk_check.passed) {
          alert(`风控拦截: ${data.risk_check.blocked_reasons?.join('; ')}`)
        }
      } else {
        alert(data.message)
      }
    } catch (e) {
      alert('执行失败')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectFund = async (opp: ArbitrageOpportunity) => {
    setSelectedFund(opp)
    setFundCode(opp.fund_code)
    setFundName(opp.fund_name)
    setPremiumPct(opp.premium_pct)

    // 计算分配方案
    try {
      const res = await tractorApi.calculateAllocation({
        fund_code: opp.fund_code,
        fund_name: opp.fund_name,
        direction: opp.direction,
        premium_pct: opp.premium_pct,
        apply_limit: opp.apply_limit,
        apply_status: opp.apply_status,
        est_nav: opp.est_nav,
        fund_price: opp.fund_price,
      })
      setAllocationPlan((res.data as any)?.data || null)
    } catch (e) {
      console.error('计算分配失败:', e)
    }

    // 切换到对应操作
    if (opp.direction === '溢价') {
      setSelectedOp('场内申购')
    } else if (opp.direction === '折价') {
      setSelectedOp('赎回')
    }
  }

  const handleSaveRiskSettings = async () => {
    if (!riskSettings) return
    try {
      await tractorApi.updateRiskSettings(riskSettings as unknown as Record<string, unknown>)
      alert('风控设置已保存')
    } catch (e) {
      alert('保存失败')
    }
  }

  const handleRiskCheck = async () => {
    try {
      const res = await tractorApi.checkRisk({
        operation: selectedOp,
        fund_code: fundCode,
        premium_pct: premiumPct,
        turnover: selectedFund?.turnover || 0,
        apply_status: selectedFund?.apply_status || '',
      })
      setRiskCheck((res.data as any)?.data || null)
    } catch (e) {
      console.error('风控检查失败:', e)
    }
  }

  // ==================== 计算属性 ====================

  const isAutoItInstalled = status?.autoit?.installed
  const isHuabaoInstalled = status?.clients?.huabao?.installed
  const hasAccounts = (status?.accounts?.length || 0) > 0
  const canRun = isAutoItInstalled && isHuabaoInstalled && hasAccounts && !opStatus?.running

  const totalCash = useMemo(
    () => accounts.reduce((sum, a) => sum + (a.available_cash || 0), 0),
    [accounts]
  )

  // ==================== 渲染 ====================

  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)', padding: '24px' }}>
      {/* 标题栏 */}
      <div style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '48px', height: '48px', borderRadius: '12px',
            background: 'linear-gradient(135deg, #f97316, #ea580c)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '24px',
          }}>🚜</div>
          <div>
            <h1 style={{ fontSize: '28px', fontWeight: 700, color: '#f1f5f9', margin: 0 }}>拖拉机套利</h1>
            <p style={{ fontSize: '13px', color: '#94a3b8', margin: '4px 0 0' }}>
              {status?.market_status || '加载中'} · {accounts.length}个账户 ·
              {totalCash > 0 ? ` 总资金${formatMoney(totalCash)}` : ' 资金未查询'}
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button onClick={() => { loadStatus(); loadOpStatus(); loadAccounts() }} style={btnPrimaryStyle}>
            刷新状态
          </button>
          <button onClick={loadStrategy} style={btnAccentStyle}>
            扫描套利
          </button>
        </div>
      </div>

      {/* 系统状态条 */}
      {(!isAutoItInstalled || !isHuabaoInstalled) && (
        <div style={{
          background: 'rgba(239, 68, 68, 0.1)', borderRadius: '12px', padding: '14px 20px',
          marginBottom: '20px', border: '1px solid rgba(239, 68, 68, 0.3)',
          display: 'flex', alignItems: 'center', gap: '12px', fontSize: '13px', color: '#fca5a5',
        }}>
          <span style={{ fontSize: '18px' }}> </span>
          <span>
            {!isAutoItInstalled && '需要安装 AutoIt (x86版本) '}
            {!isHuabaoInstalled && '需要安装华宝证券通达信版独立交易'}
          </span>
        </div>
      )}

      {/* 选项卡导航 */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: '20px', background: 'rgba(15, 23, 42, 0.6)', borderRadius: '12px', padding: '4px' }}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              flex: 1, padding: '10px 16px', borderRadius: '10px', border: 'none',
              background: activeTab === tab.id ? 'rgba(249, 115, 22, 0.2)' : 'transparent',
              color: activeTab === tab.id ? '#f97316' : '#94a3b8',
              cursor: 'pointer', fontSize: '14px', fontWeight: activeTab === tab.id ? 600 : 400,
              transition: 'all 0.2s',
            }}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* ==================== 策略总览 Tab ==================== */}
      {activeTab === 'strategy' && (
        <div>
          {/* 扫描过滤器 */}
          <div style={cardStyle}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontSize: '12px', color: '#94a3b8' }}>最低溢价率</span>
                <input
                  type="number" step="0.5" min="0"
                  value={scanFilter.min_premium}
                  onChange={e => setScanFilter(f => ({ ...f, min_premium: +e.target.value }))}
                  style={{ ...inputStyle, width: '80px' }}
                />
                <span style={{ fontSize: '12px', color: '#64748b' }}>%</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontSize: '12px', color: '#94a3b8' }}>最低成交额</span>
                <input
                  type="number" step="500" min="0"
                  value={scanFilter.min_amount}
                  onChange={e => setScanFilter(f => ({ ...f, min_amount: +e.target.value }))}
                  style={{ ...inputStyle, width: '100px' }}
                />
                <span style={{ fontSize: '12px', color: '#64748b' }}>万</span>
              </div>
              <div style={{ display: 'flex', gap: '4px' }}>
                {['all', '溢价', '折价'].map(d => (
                  <button
                    key={d}
                    onClick={() => setScanFilter(f => ({ ...f, direction: d }))}
                    style={{
                      padding: '6px 14px', borderRadius: '8px', border: 'none', cursor: 'pointer',
                      fontSize: '12px', fontWeight: 500,
                      background: scanFilter.direction === d ? 'rgba(249, 115, 22, 0.2)' : 'rgba(51, 65, 85, 0.5)',
                      color: scanFilter.direction === d ? '#f97316' : '#94a3b8',
                    }}
                  >
                    {d === 'all' ? '全部' : d}
                  </button>
                ))}
              </div>
              <button onClick={loadStrategy} disabled={strategyLoading} style={btnAccentStyle}>
                {strategyLoading ? '扫描中...' : '开始扫描'}
              </button>
            </div>
          </div>

          {/* 套利机会列表 */}
          <div style={cardStyle}>
            <h3 style={sectionTitleStyle}>
              套利机会 ({opportunities.length})
            </h3>
            {opportunities.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>
                {strategyLoading ? '正在扫描...' : '暂无符合条件的套利机会，点击"开始扫描"'}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {opportunities.map(opp => (
                  <div
                    key={opp.fund_code}
                    onClick={() => handleSelectFund(opp)}
                    style={{
                      background: selectedFund?.fund_code === opp.fund_code
                        ? 'rgba(249, 115, 22, 0.1)' : 'rgba(15, 23, 42, 0.6)',
                      border: `1px solid ${selectedFund?.fund_code === opp.fund_code
                        ? 'rgba(249, 115, 22, 0.4)' : 'rgba(148, 163, 184, 0.1)'}`,
                      borderRadius: '12px', padding: '14px 16px', cursor: 'pointer',
                      display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr 1fr',
                      alignItems: 'center', gap: '12px', transition: 'all 0.2s',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: '14px', fontWeight: 600, color: '#f1f5f9' }}>
                        {opp.fund_name}
                      </div>
                      <div style={{ fontSize: '11px', color: '#64748b', fontFamily: 'monospace' }}>
                        {opp.fund_code}
                      </div>
                    </div>
                    <div>
                      <span style={{
                        padding: '3px 10px', borderRadius: '6px', fontSize: '12px', fontWeight: 600,
                        background: `${directionColor(opp.direction)}20`,
                        color: directionColor(opp.direction),
                      }}>
                        {opp.direction}
                      </span>
                    </div>
                    <div>
                      <div style={{ fontSize: '15px', fontWeight: 700, color: opp.premium_pct > 0 ? '#ef4444' : '#22c55e' }}>
                        {formatPct(opp.premium_pct)}
                      </div>
                      <div style={{ fontSize: '10px', color: '#64748b' }}>溢价率</div>
                    </div>
                    <div>
                      <div style={{ fontSize: '14px', fontWeight: 600, color: '#22c55e' }}>
                        {opp.net_profit_pct.toFixed(2)}%
                      </div>
                      <div style={{ fontSize: '10px', color: '#64748b' }}>净收益</div>
                    </div>
                    <div>
                      <div style={{ fontSize: '13px', color: '#f1f5f9' }}>
                        {formatMoney(opp.turnover)}万
                      </div>
                      <div style={{ fontSize: '10px', color: '#64748b' }}>成交额</div>
                    </div>
                    <div>
                      <span style={{
                        padding: '2px 8px', borderRadius: '4px', fontSize: '11px',
                        background: `${riskColor(opp.risk_level)}20`,
                        color: riskColor(opp.risk_level),
                      }}>
                        {opp.risk_level === 'low' ? '低风险' : opp.risk_level === 'medium' ? '中风险' : '高风险'}
                      </span>
                      <div style={{ fontSize: '10px', color: '#64748b', marginTop: '2px' }}>
                        {opp.apply_limit || '不限'}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 策略建议 */}
          {recommendations.length > 0 && (
            <div style={cardStyle}>
              <h3 style={sectionTitleStyle}>策略建议</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {recommendations.map((rec, i) => (
                  <div key={i} style={{
                    background: 'rgba(15, 23, 42, 0.6)', borderRadius: '12px', padding: '16px',
                    border: `1px solid ${rec.confidence === 'high' ? 'rgba(34, 197, 94, 0.3)' :
                      rec.confidence === 'medium' ? 'rgba(245, 158, 11, 0.3)' : 'rgba(100, 116, 139, 0.3)'}`,
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                      <div>
                        <span style={{ fontSize: '15px', fontWeight: 600, color: '#f1f5f9' }}>{rec.fund_name}</span>
                        <span style={{ fontSize: '12px', color: '#64748b', marginLeft: '8px' }}>{rec.fund_code}</span>
                      </div>
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <span style={{
                          padding: '4px 12px', borderRadius: '8px', fontSize: '13px', fontWeight: 600,
                          background: rec.action.includes('立即') ? 'rgba(34, 197, 94, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                          color: rec.action.includes('立即') ? '#4ade80' : '#fbbf24',
                        }}>
                          {rec.action}
                        </span>
                        <span style={{
                          padding: '2px 8px', borderRadius: '4px', fontSize: '11px',
                          background: rec.confidence === 'high' ? 'rgba(34, 197, 94, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                          color: rec.confidence === 'high' ? '#4ade80' : '#fbbf24',
                        }}>
                          {rec.confidence === 'high' ? '高置信' : rec.confidence === 'medium' ? '中置信' : '低置信'}
                        </span>
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginBottom: '10px' }}>
                      <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                        溢价率: <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{formatPct(rec.premium_pct)}</span>
                      </div>
                      <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                        净收益: <span style={{ color: '#22c55e', fontWeight: 600 }}>{rec.net_profit_pct.toFixed(2)}%</span>
                      </div>
                      <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                        限购: <span style={{ color: '#f1f5f9' }}>{rec.apply_limit || '不限'}</span>
                      </div>
                    </div>

                    {/* 分配方案摘要 */}
                    {rec.allocation_plan && rec.allocation_plan.allocations.length > 0 && (
                      <div style={{
                        background: 'rgba(0, 0, 0, 0.2)', borderRadius: '8px', padding: '10px',
                        marginBottom: '8px',
                      }}>
                        <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>
                          资金分配方案
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                          {rec.allocation_plan.allocations.map(alloc => (
                            <span key={alloc.account_id} style={{
                              padding: '3px 10px', borderRadius: '6px', fontSize: '11px',
                              background: 'rgba(249, 115, 22, 0.1)', color: '#f97316',
                            }}>
                              {alloc.account_name}: {formatMoney(alloc.recommended_amount)}
                            </span>
                          ))}
                        </div>
                        <div style={{ fontSize: '12px', color: '#22c55e', marginTop: '6px' }}>
                          总分配: {formatMoney(rec.allocation_plan.total_amount)} |
                          预估利润: {formatMoney(rec.allocation_plan.estimated_profit)}
                        </div>
                      </div>
                    )}

                    {/* 风险提示 */}
                    {rec.risk_warnings.length > 0 && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {rec.risk_warnings.map((w, j) => (
                          <span key={j} style={{
                            padding: '2px 8px', borderRadius: '4px', fontSize: '10px',
                            background: 'rgba(245, 158, 11, 0.1)', color: '#fbbf24',
                          }}>
                            {w}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 操作面板（从策略页快速执行） */}
          {selectedFund && (
            <div style={cardStyle}>
              <h3 style={sectionTitleStyle}>
                执行操作 - {selectedFund.fund_name} ({selectedFund.fund_code})
              </h3>
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '16px' }}>
                {OPERATIONS.filter(op =>
                  selectedFund.direction === '溢价'
                    ? ['场内申购', '卖出', '仅登录查询'].includes(op.id)
                    : ['赎回', '仅登录查询'].includes(op.id)
                ).map(op => (
                  <button
                    key={op.id}
                    onClick={() => setSelectedOp(op.id)}
                    style={{
                      padding: '10px 20px', borderRadius: '10px', cursor: 'pointer',
                      background: selectedOp === op.id ? `${op.color}20` : 'rgba(51, 65, 85, 0.5)',
                      border: `1px solid ${selectedOp === op.id ? op.color : 'rgba(148, 163, 184, 0.1)'}`,
                      color: selectedOp === op.id ? op.color : '#94a3b8',
                      fontSize: '13px', fontWeight: 500,
                    }}
                  >
                    {op.label}
                  </button>
                ))}
              </div>

              {selectedOp === '卖出' && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                  <div>
                    <label style={labelStyle}>卖出价格</label>
                    <input value={sellPrice} onChange={e => setSellPrice(e.target.value)} placeholder={selectedFund.fund_price.toFixed(3)} style={inputStyle} />
                  </div>
                  <div>
                    <label style={labelStyle}>卖出数量</label>
                    <input value={sellQuantity} onChange={e => setSellQuantity(e.target.value)} placeholder="1000" style={inputStyle} />
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <button
                  onClick={handleRun}
                  disabled={!canRun || loading}
                  style={{
                    ...btnPrimaryStyle,
                    padding: '12px 28px', fontSize: '15px', fontWeight: 700,
                    opacity: canRun && !loading ? 1 : 0.5,
                    cursor: canRun && !loading ? 'pointer' : 'not-allowed',
                  }}
                >
                  {loading || opStatus?.running ? '执行中...' : `执行${selectedOp}`}
                </button>
                <button onClick={handleRiskCheck} style={btnGrayStyle}>
                  风控预检
                </button>
                {!canRun && (
                  <span style={{ fontSize: '12px', color: '#f87171' }}>
                    {!isAutoItInstalled ? '需要安装AutoIt' :
                     !isHuabaoInstalled ? '需要安装华宝证券' :
                     !hasAccounts ? '需要添加账户' :
                     opStatus?.running ? '有操作正在运行' : ''}
                  </span>
                )}
              </div>

              {/* 风控检查结果 */}
              {riskCheck && (
                <div style={{
                  marginTop: '12px', padding: '12px', borderRadius: '8px',
                  background: riskCheck.passed ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                  border: `1px solid ${riskCheck.passed ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                }}>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: riskCheck.passed ? '#4ade80' : '#f87171', marginBottom: '8px' }}>
                    风控检查: {riskCheck.passed ? '通过' : '未通过'}
                  </div>
                  {riskCheck.checks.map((c, i) => (
                    <div key={i} style={{ fontSize: '12px', color: c.passed ? '#94a3b8' : '#f87171', marginLeft: '8px' }}>
                      {c.passed ? '  ' : '  '} {c.name}: {c.message}
                    </div>
                  ))}
                  {riskCheck.blocked_reasons.map((r, i) => (
                    <div key={i} style={{ fontSize: '12px', color: '#f87171', marginLeft: '8px', marginTop: '4px' }}>
                       {r}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ==================== 账户管理 Tab ==================== */}
      {activeTab === 'accounts' && (
        <div>
          {/* 账户概览 */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', marginBottom: '20px' }}>
            <StatusCard icon=" " label="账户总数" value={`${accounts.length}个`} color="#f97316" />
            <StatusCard icon=" " label="总可用资金" value={formatMoney(totalCash)} color="#22c55e" />
            <StatusCard icon=" " label="已启用" value={`${accounts.filter(a => a.enabled).length}个`} color="#3b82f6" />
            <StatusCard icon="⚙️" label="AutoIt" value={isAutoItInstalled ? '已安装' : '未安装'} color={isAutoItInstalled ? '#22c55e' : '#ef4444'} />
          </div>

          {/* 添加账户 */}
          <div style={cardStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={sectionTitleStyle}>拖拉机账户</h3>
              <button onClick={() => setShowAddAccount(!showAddAccount)} style={btnGreenStyle}>
                + 添加账户
              </button>
            </div>

            {showAddAccount && (
              <div style={{
                background: 'rgba(15, 23, 42, 0.6)', borderRadius: '12px', padding: '16px',
                marginBottom: '16px', border: '1px solid rgba(148, 163, 184, 0.2)',
              }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
                  <div>
                    <label style={labelStyle}>资金账号</label>
                    <input value={newAccount.account_id} onChange={e => setNewAccount(a => ({ ...a, account_id: e.target.value }))} placeholder="230500060000" style={inputStyle} />
                  </div>
                  <div>
                    <label style={labelStyle}>备注名称</label>
                    <input value={newAccount.name} onChange={e => setNewAccount(a => ({ ...a, name: e.target.value }))} placeholder="可选" style={inputStyle} />
                  </div>
                  <div>
                    <label style={labelStyle}>交易密码</label>
                    <input type="password" value={newAccount.password} onChange={e => setNewAccount(a => ({ ...a, password: e.target.value }))} style={inputStyle} />
                  </div>
                  <div>
                    <label style={labelStyle}>券商类型</label>
                    <select value={newAccount.broker_type} onChange={e => setNewAccount(a => ({ ...a, broker_type: e.target.value }))} style={inputStyle}>
                      <option value="huabao">华宝证券</option>
                      <option value="yinhe">银河证券</option>
                    </select>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                  <button onClick={handleAddAccount} style={btnGreenStyle}>确认添加</button>
                  <button onClick={() => setShowAddAccount(false)} style={btnGrayStyle}>取消</button>
                </div>
              </div>
            )}

            {/* 账户列表 */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {accounts.map(acc => (
                <div key={acc.account_id} style={{
                  background: 'rgba(15, 23, 42, 0.6)', borderRadius: '12px', padding: '14px 16px',
                  border: '1px solid rgba(148, 163, 184, 0.1)',
                  display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr auto',
                  alignItems: 'center', gap: '12px',
                }}>
                  <div>
                    <div style={{ fontSize: '14px', fontWeight: 600, color: '#f1f5f9' }}>{acc.name}</div>
                    <div style={{ fontSize: '11px', color: '#64748b', fontFamily: 'monospace' }}>{acc.account_id}</div>
                    <div style={{ fontSize: '10px', color: acc.broker_type === 'huabao' ? '#f97316' : '#3b82f6', marginTop: '2px' }}>
                      {acc.broker_type === 'huabao' ? '华宝证券' : '银河证券'}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '13px', color: '#94a3b8' }}>可用资金</div>
                    <div style={{ fontSize: '15px', fontWeight: 600, color: '#22c55e' }}>
                      {acc.available_cash > 0 ? formatMoney(acc.available_cash) : '未查询'}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '13px', color: '#94a3b8' }}>基金持仓</div>
                    <div style={{ fontSize: '15px', fontWeight: 600, color: '#f1f5f9' }}>
                      {acc.fund_shares > 0 ? `${acc.fund_shares}份` : '无'}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '11px', color: '#64748b' }}>
                      {acc.last_query_time ? `查询: ${new Date(acc.last_query_time).toLocaleString()}` : '未查询'}
                    </div>
                  </div>
                  <button onClick={() => handleDeleteAccount(acc.account_id)} style={{
                    padding: '6px 12px', background: 'rgba(239, 68, 68, 0.1)',
                    color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.2)',
                    borderRadius: '6px', cursor: 'pointer', fontSize: '12px',
                  }}>删除</button>
                </div>
              ))}
              {accounts.length === 0 && (
                <div style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>
                  暂无账户，点击"添加账户"开始
                </div>
              )}
            </div>
          </div>

          {/* 分配方案详情 */}
          {allocationPlan && (
            <div style={cardStyle}>
              <h3 style={sectionTitleStyle}>
                资金分配方案 - {allocationPlan.fund_name} ({allocationPlan.fund_code})
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '16px' }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '11px', color: '#94a3b8' }}>方向</div>
                  <div style={{ fontSize: '16px', fontWeight: 600, color: directionColor(allocationPlan.direction) }}>
                    {allocationPlan.direction}
                  </div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '11px', color: '#94a3b8' }}>溢价率</div>
                  <div style={{ fontSize: '16px', fontWeight: 600, color: '#f1f5f9' }}>
                    {formatPct(allocationPlan.premium_pct)}
                  </div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '11px', color: '#94a3b8' }}>每户限购</div>
                  <div style={{ fontSize: '16px', fontWeight: 600, color: '#f1f5f9' }}>
                    {formatMoney(allocationPlan.apply_limit_per_account)}
                  </div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '11px', color: '#94a3b8' }}>预估利润</div>
                  <div style={{ fontSize: '16px', fontWeight: 600, color: '#22c55e' }}>
                    {formatMoney(allocationPlan.estimated_profit)}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {allocationPlan.allocations.map(alloc => (
                  <div key={alloc.account_id} style={{
                    background: 'rgba(15, 23, 42, 0.6)', borderRadius: '8px', padding: '10px 14px',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  }}>
                    <div>
                      <span style={{ fontSize: '13px', fontWeight: 600, color: '#f1f5f9' }}>{alloc.account_name}</span>
                      <span style={{ fontSize: '11px', color: '#64748b', marginLeft: '8px' }}>{alloc.account_id}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                        余额: {formatMoney(alloc.available_cash)}
                      </span>
                      <span style={{ fontSize: '15px', fontWeight: 700, color: '#f97316' }}>
                        {alloc.shares_to_sell > 0 ? `${alloc.shares_to_sell}份` : formatMoney(alloc.recommended_amount)}
                      </span>
                    </div>
                    {alloc.notes.length > 0 && (
                      <span style={{ fontSize: '10px', color: '#fbbf24' }}>{alloc.notes.join('; ')}</span>
                    )}
                  </div>
                ))}
              </div>

              {allocationPlan.warnings.length > 0 && (
                <div style={{ marginTop: '10px' }}>
                  {allocationPlan.warnings.map((w, i) => (
                    <div key={i} style={{ fontSize: '12px', color: '#fbbf24', marginLeft: '8px' }}> {w}</div>
                  ))}
                </div>
              )}

              <div style={{ marginTop: '12px', display: 'flex', gap: '8px', alignItems: 'center' }}>
                <div style={{ fontSize: '14px', fontWeight: 600, color: '#f1f5f9' }}>
                  总分配: {formatMoney(allocationPlan.total_amount)} |
                  {allocationPlan.enabled_accounts}/{allocationPlan.total_accounts} 个账户
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ==================== 风险控制 Tab ==================== */}
      {activeTab === 'risk' && (
        <div>
          <div style={cardStyle}>
            <h3 style={sectionTitleStyle}>风控参数设置</h3>
            {riskSettings && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
                <RiskSettingItem
                  label="最低溢价率"
                  value={riskSettings.min_premium_pct}
                  unit="%"
                  desc="低于此值不执行溢价套利"
                  onChange={v => setRiskSettings(s => s ? { ...s, min_premium_pct: v } : s)}
                />
                <RiskSettingItem
                  label="单账户最大申购金额"
                  value={riskSettings.max_single_amount}
                  unit="元"
                  desc="单个账户单次申购上限"
                  onChange={v => setRiskSettings(s => s ? { ...s, max_single_amount: v } : s)}
                />
                <RiskSettingItem
                  label="全部账户最大总金额"
                  value={riskSettings.max_total_amount}
                  unit="元"
                  desc="所有账户单次总申购上限"
                  onChange={v => setRiskSettings(s => s ? { ...s, max_total_amount: v } : s)}
                />
                <RiskSettingItem
                  label="每账户最低保留资金"
                  value={riskSettings.min_cash_reserve}
                  unit="元"
                  desc="操作后每账户至少保留的资金"
                  onChange={v => setRiskSettings(s => s ? { ...s, min_cash_reserve: v } : s)}
                />
                <RiskSettingItem
                  label="每日最大操作次数"
                  value={riskSettings.max_daily_operations}
                  unit="次"
                  desc="防止误操作的每日次数限制"
                  onChange={v => setRiskSettings(s => s ? { ...s, max_daily_operations: v } : s)}
                  isInt
                />
                <RiskSettingItem
                  label="最低成交额"
                  value={riskSettings.min_turnover}
                  unit="万元"
                  desc="低于此成交额的基金标记为低流动性"
                  onChange={v => setRiskSettings(s => s ? { ...s, min_turnover: v } : s)}
                />
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <label style={{ fontSize: '13px', color: '#94a3b8' }}>
                    <input
                      type="checkbox"
                      checked={riskSettings.require_trading_hours}
                      onChange={e => setRiskSettings(s => s ? { ...s, require_trading_hours: e.target.checked } : s)}
                      style={{ marginRight: '6px' }}
                    />
                    仅交易时段操作
                  </label>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <label style={{ fontSize: '13px', color: '#94a3b8' }}>
                    <input
                      type="checkbox"
                      checked={riskSettings.block_low_liquidity}
                      onChange={e => setRiskSettings(s => s ? { ...s, block_low_liquidity: e.target.checked } : s)}
                      style={{ marginRight: '6px' }}
                    />
                    屏蔽低流动性基金
                  </label>
                </div>
              </div>
            )}
            <div style={{ marginTop: '16px' }}>
              <button onClick={handleSaveRiskSettings} style={btnAccentStyle}>保存设置</button>
            </div>
          </div>

          {/* 风控纪律清单说明 */}
          <div style={cardStyle}>
            <h3 style={sectionTitleStyle}>风控纪律清单</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '12px' }}>
              {[
                { name: '溢价率 >= 阈值', level: 'critical', desc: '低于阈值无法覆盖申购费和佣金' },
                { name: '申购状态正常', level: 'critical', desc: '暂停申购或限购影响套利执行' },
                { name: '交易时段', level: 'critical', desc: '非交易时段无法下单' },
                { name: '流动性充足', level: 'high', desc: '成交额不足会导致滑点增大' },
                { name: '单账户金额不超限', level: 'high', desc: '防止超限购申购被退回' },
                { name: '账户余额充足', level: 'medium', desc: '操作后余额不低于保留线' },
                { name: '每日操作不超限', level: 'medium', desc: '防止误操作导致重复下单' },
                { name: 'T+2结算风险', level: 'low', desc: 'QDII基金底层资产波动风险' },
              ].map((item, i) => (
                <div key={i} style={{
                  background: 'rgba(15, 23, 42, 0.6)', borderRadius: '8px', padding: '12px',
                  borderLeft: `3px solid ${riskColor(item.level)}`,
                }}>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: '#f1f5f9' }}>{item.name}</div>
                  <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>{item.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ==================== 操作历史 Tab ==================== */}
      {activeTab === 'history' && (
        <div>
          {/* P&L 摘要 */}
          {pnlSummary && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', marginBottom: '20px' }}>
              <StatusCard icon=" " label="总操作" value={`${pnlSummary.total_operations}次`} color="#f1f5f9" />
              <StatusCard icon=" " label="申购" value={`${pnlSummary.total_subscribes}次`} color="#22c55e" />
              <StatusCard icon=" " label="卖出/赎回" value={`${pnlSummary.total_sells + pnlSummary.total_redeems}次`} color="#ef4444" />
              <StatusCard icon=" " label="已实现损益" value={formatMoney(pnlSummary.total_realized_pnl)} color={pnlSummary.total_realized_pnl >= 0 ? '#22c55e' : '#ef4444'} />
              <StatusCard icon=" " label="胜率" value={`${pnlSummary.win_rate.toFixed(0)}%`} color={pnlSummary.win_rate >= 50 ? '#22c55e' : '#f97316'} />
              <StatusCard icon=" " label="单笔均值" value={formatMoney(pnlSummary.avg_pnl_per_trade)} color="#3b82f6" />
            </div>
          )}

          {/* 操作记录 */}
          <div style={cardStyle}>
            <h3 style={sectionTitleStyle}>操作记录 (近50条)</h3>
            {history.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>暂无操作记录</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {history.map(record => (
                  <div key={record.id} style={{
                    background: 'rgba(15, 23, 42, 0.6)', borderRadius: '8px', padding: '10px 14px',
                    display: 'grid', gridTemplateColumns: '180px 1fr 100px 100px',
                    alignItems: 'center', gap: '12px',
                  }}>
                    <div style={{ fontSize: '11px', color: '#64748b', fontFamily: 'monospace' }}>
                      {new Date(record.timestamp).toLocaleString()}
                    </div>
                    <div>
                      <span style={{ fontSize: '13px', fontWeight: 500, color: '#f1f5f9' }}>
                        {record.operation}
                      </span>
                      {record.fund_code && (
                        <span style={{ fontSize: '12px', color: '#94a3b8', marginLeft: '8px' }}>
                          {record.fund_name || record.fund_code}
                        </span>
                      )}
                      {record.premium_pct !== 0 && (
                        <span style={{ fontSize: '11px', color: '#64748b', marginLeft: '8px' }}>
                          溢价{record.premium_pct.toFixed(2)}%
                        </span>
                      )}
                    </div>
                    <div>
                      <span style={{
                        padding: '2px 8px', borderRadius: '4px', fontSize: '11px',
                        background: record.success ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                        color: record.success ? '#4ade80' : '#f87171',
                      }}>
                        {record.success ? '成功' : '失败'}
                      </span>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      {record.realized_pnl !== null && record.realized_pnl !== undefined ? (
                        <span style={{
                          fontSize: '13px', fontWeight: 600,
                          color: record.realized_pnl >= 0 ? '#22c55e' : '#ef4444',
                        }}>
                          {record.realized_pnl >= 0 ? '+' : ''}{formatMoney(record.realized_pnl)}
                        </span>
                      ) : (
                        <span style={{ fontSize: '11px', color: '#64748b' }}>-</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 操作日志 */}
          {opStatus?.log && opStatus.log.length > 0 && (
            <div style={cardStyle}>
              <h3 style={sectionTitleStyle}>实时操作日志</h3>
              <div style={{
                background: 'rgba(0, 0, 0, 0.3)', borderRadius: '8px', padding: '12px',
                maxHeight: '300px', overflowY: 'auto',
                fontFamily: 'monospace', fontSize: '12px', lineHeight: '1.8',
              }}>
                {opStatus.log.map((line, i) => (
                  <div key={i} style={{
                    color: line.includes('失败') || line.includes('错误') ? '#f87171' :
                           line.includes('完成') ? '#4ade80' : '#94a3b8',
                  }}>
                    {line}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ==================== 使用说明（底部折叠） ==================== */}
      <details style={{ marginTop: '24px' }}>
        <summary style={{
          cursor: 'pointer', padding: '14px 20px', borderRadius: '12px',
          background: 'rgba(30, 41, 59, 0.8)', border: '1px solid rgba(148, 163, 184, 0.1)',
          color: '#a78bfa', fontSize: '14px', fontWeight: 600,
        }}>
          使用说明与套利流程
        </summary>
        <div style={{
          background: 'rgba(30, 41, 59, 0.8)', borderRadius: '0 0 12px 12px', padding: '20px',
          border: '1px solid rgba(148, 163, 184, 0.1)', borderTop: 'none',
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
            <InfoCard title="溢价套利流程" color="#ef4444" steps={[
              '1. 在"策略总览"页扫描套利机会',
              '2. 选择溢价率 > 2% 且净收益 > 0 的基金',
              '3. 确认资金分配方案（自动按限购和余额计算）',
              '4. 执行"场内申购"（T日）',
              '5. 等待T+2份额到账',
              '6. 执行"卖出"（T+2或T+3日）',
            ]} />
            <InfoCard title="折价套利流程" color="#22c55e" steps={[
              '1. 在"策略总览"页扫描折价机会',
              '2. 选择折价率 > 2% 的基金',
              '3. 场内手动买入（T日）',
              '4. 转托管到场外（T+1日）',
              '5. 执行"赎回"（T+2日）',
            ]} />
            <InfoCard title="安全注意事项" color="#f97316" steps={[
              '• 运行期间不能碰键盘鼠标',
              '• 网速要好，建议有线网络',
              '• 华宝证券暂不支持赎回和撤单',
              '• 首次使用需手工操作一次登录',
              '• 废弃电脑前记得清除账户记录',
              '• 建议先用"仅登录查询"验证环境',
            ]} />
          </div>
        </div>
      </details>
    </div>
  )
}

// ==================== 子组件 ====================

function StatusCard({ icon, label, value, color, sub }: {
  icon: string; label: string; value: string; color: string; sub?: string
}) {
  return (
    <div style={{
      background: 'rgba(30, 41, 59, 0.8)', borderRadius: '12px', padding: '16px',
      border: '1px solid rgba(148, 163, 184, 0.1)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
        <span style={{ fontSize: '11px', color: '#94a3b8' }}>{label}</span>
        <span style={{ fontSize: '16px' }}>{icon}</span>
      </div>
      <div style={{ fontSize: '18px', fontWeight: 700, color }}>{value}</div>
      {sub && <div style={{ fontSize: '10px', color: '#64748b', marginTop: '2px' }}>{sub}</div>}
    </div>
  )
}

function RiskSettingItem({ label, value, unit, desc, onChange, isInt }: {
  label: string; value: number; unit: string; desc: string;
  onChange: (v: number) => void; isInt?: boolean
}) {
  return (
    <div style={{ background: 'rgba(15, 23, 42, 0.6)', borderRadius: '10px', padding: '14px' }}>
      <div style={{ fontSize: '13px', fontWeight: 600, color: '#f1f5f9', marginBottom: '4px' }}>{label}</div>
      <div style={{ fontSize: '11px', color: '#64748b', marginBottom: '8px' }}>{desc}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <input
          type="number"
          value={value}
          onChange={e => onChange(isInt ? parseInt(e.target.value) || 0 : parseFloat(e.target.value) || 0)}
          style={{ ...inputStyle, width: '140px' }}
        />
        <span style={{ fontSize: '12px', color: '#64748b' }}>{unit}</span>
      </div>
    </div>
  )
}

function InfoCard({ title, color, steps }: { title: string; color: string; steps: string[] }) {
  return (
    <div style={{
      background: 'rgba(15, 23, 42, 0.6)', borderRadius: '12px', padding: '16px',
      border: `1px solid ${color}30`,
    }}>
      <h4 style={{ fontSize: '14px', fontWeight: 600, color, margin: '0 0 12px' }}>{title}</h4>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {steps.map((step, i) => (
          <div key={i} style={{ fontSize: '12px', color: '#d1d5db', lineHeight: '1.6' }}>{step}</div>
        ))}
      </div>
    </div>
  )
}

// ==================== 样式常量 ====================

const cardStyle: React.CSSProperties = {
  background: 'rgba(30, 41, 59, 0.8)', borderRadius: '16px', padding: '20px',
  marginBottom: '16px', border: '1px solid rgba(148, 163, 184, 0.1)',
}

const sectionTitleStyle: React.CSSProperties = {
  fontSize: '16px', fontWeight: 600, color: '#f1f5f9', margin: '0 0 16px',
}

const labelStyle: React.CSSProperties = {
  display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px',
}

const inputStyle: React.CSSProperties = {
  padding: '8px 12px', border: '1px solid rgba(148, 163, 184, 0.2)',
  borderRadius: '8px', background: 'rgba(15, 23, 42, 0.8)', color: '#f1f5f9',
  fontSize: '13px', outline: 'none', boxSizing: 'border-box' as const,
}

const btnPrimaryStyle: React.CSSProperties = {
  padding: '8px 18px', background: 'linear-gradient(135deg, #f97316, #ea580c)',
  color: '#fff', border: 'none', borderRadius: '10px',
  cursor: 'pointer', fontWeight: 600, fontSize: '13px',
  boxShadow: '0 4px 12px rgba(249, 115, 22, 0.3)',
}

const btnAccentStyle: React.CSSProperties = {
  padding: '8px 18px', background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
  color: '#fff', border: 'none', borderRadius: '10px',
  cursor: 'pointer', fontWeight: 600, fontSize: '13px',
  boxShadow: '0 4px 12px rgba(59, 130, 246, 0.3)',
}

const btnGreenStyle: React.CSSProperties = {
  padding: '8px 16px', background: 'rgba(34, 197, 94, 0.2)',
  color: '#4ade80', border: '1px solid rgba(34, 197, 94, 0.3)',
  borderRadius: '8px', cursor: 'pointer', fontSize: '13px', fontWeight: 600,
}

const btnGrayStyle: React.CSSProperties = {
  padding: '8px 16px', background: 'rgba(51, 65, 85, 0.5)',
  color: '#94a3b8', border: '1px solid rgba(148, 163, 184, 0.2)',
  borderRadius: '8px', cursor: 'pointer', fontSize: '13px',
}
