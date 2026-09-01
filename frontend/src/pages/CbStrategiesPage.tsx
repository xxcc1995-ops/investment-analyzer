import { useState, useEffect, useCallback, useMemo, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Table, Tag, Button, Select, Space, Typography, Empty, Spin, Tabs, Alert, Tooltip,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { ReloadOutlined, ReadOutlined, FundOutlined } from '@ant-design/icons'
import { cbApi, type CBStrategy, type ConvertibleBond } from '../services/api'

const { Title, Text, Paragraph } = Typography

// 每个战法的视觉标识（图标 + 主题色）
const STRATEGY_VISUAL: Record<string, { icon: string; color: string }> = {
  ytm_defense: { icon: '🏦', color: '#722ed1' },
  dual_low: { icon: '📊', color: '#1890ff' },
  rotation: { icon: '🔄', color: '#13c2c2' },
  grid: { icon: '🔲', color: '#fa8c16' },
  revision_game: { icon: '🎯', color: '#f5222d' },
  redeem_game: { icon: '🔥', color: '#ff4d4f' },
  problem_bond: { icon: '💀', color: '#a0d911' },
  negative_premium: { icon: '💎', color: '#eb2f96' },
}

// 风险等级 → antd Tag 颜色
function riskTag(level?: string): { color: string; text: string } {
  const l = level || ''
  if (l.includes('高')) return { color: 'red', text: l }
  if (l.includes('中')) return { color: 'gold', text: l }
  if (l.includes('低')) return { color: 'green', text: l }
  return { color: 'default', text: l || '未知' }
}

// 质量评级 → 颜色
function verdictColor(v?: string): string {
  switch (v) {
    case 'A': return '#52c41a'
    case 'B': return '#1890ff'
    case 'C': return '#faad14'
    case 'D': return '#ff4d4f'
    default: return '#8b949e'
  }
}

export default function CbStrategiesPage() {
  const navigate = useNavigate()
  const [strategies, setStrategies] = useState<Record<string, CBStrategy>>({})
  const [order, setOrder] = useState<string[]>([])
  const [activeKey, setActiveKey] = useState<string>('')
  const [bonds, setBonds] = useState<ConvertibleBond[]>([])
  const [loading, setLoading] = useState(false)
  const [fetchTime, setFetchTime] = useState('')
  const [total, setTotal] = useState(0)
  const [dataSource, setDataSource] = useState('')
  const [error, setError] = useState('')
  const [topN, setTopN] = useState(20)

  // 加载八大战法定义
  useEffect(() => {
    cbApi.getStrategies()
      .then(res => {
        const s = res.data.strategies || {}
        const o = (res.data.eight_order || []).filter(k => s[k])
        setStrategies(s)
        setOrder(o)
        if (o.length > 0) setActiveKey(o[0])
      })
      .catch(() => {})
  }, [])

  const runStrategy = useCallback(async (key: string, n = topN) => {
    if (!key) return
    setLoading(true)
    setError('')
    try {
      const res = await cbApi.getMasterStrategy({ strategy: key, top_n: n })
      setBonds(res.data.bonds || [])
      setFetchTime(res.data.fetch_time || '')
      setTotal(res.data.total || 0)
      setDataSource(res.data.data_source || '')
      setError(res.data.error || '')
    } catch (e) {
      setError('运行策略失败，请确认后端服务可用、集思录已登录')
      setBonds([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [topN])

  // 切换战法 / 调整数量时自动运行
  useEffect(() => {
    if (activeKey) runStrategy(activeKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeKey, topN, runStrategy])

  const active = strategies[activeKey]
  const activeVis = activeKey ? STRATEGY_VISUAL[activeKey] : undefined

  // ===== 结果表列 =====
  const columns: ColumnsType<ConvertibleBond> = useMemo(() => [
    {
      title: '#', dataIndex: '_idx', width: 48,
      render: (_: any, __: any, i: number) => <Text style={{ color: '#8b949e' }}>{i + 1}</Text>,
    },
    { title: '代码', dataIndex: 'bond_id', width: 90, render: (v: string) => <Text style={{ fontFamily: 'monospace', fontSize: 12 }}>{v}</Text> },
    { title: '转债名称', dataIndex: 'bond_nm', width: 120, render: (v: string) => <Text strong>{v}</Text> },
    {
      title: '现价', dataIndex: 'price', width: 80, sorter: (a, b) => a.price - b.price,
      render: (v: number) => <Text>{v?.toFixed(2)}</Text>,
    },
    {
      title: '溢价率%', dataIndex: 'premium_rt', width: 90, sorter: (a, b) => a.premium_rt - b.premium_rt,
      render: (v: number) => (
        <Text style={{ color: v <= 0 ? '#52c41a' : '#e6edf3', fontWeight: v <= 0 ? 600 : 400 }}>
          {v?.toFixed(2)}
        </Text>
      ),
    },
    {
      title: '双低值', dataIndex: 'double_low', width: 90, sorter: (a, b) => a.double_low - b.double_low,
      render: (v: number) => (
        <Text strong style={{ color: v <= 120 ? '#52c41a' : v <= 130 ? '#1890ff' : '#faad14' }}>
          {v?.toFixed(2)}
        </Text>
      ),
    },
    {
      title: 'YTM%', dataIndex: 'ytm_rt', width: 80, sorter: (a, b) => a.ytm_rt - b.ytm_rt,
      render: (v: number) =>
        v < -100
          ? <Text type="secondary">—</Text>
          : <Text style={{ color: v >= 0 ? '#52c41a' : '#ff4d4f', fontWeight: 600 }}>{v?.toFixed(2)}</Text>,
    },
    {
      title: '质量', dataIndex: 'quality_score', width: 80, sorter: (a, b) => a.quality_score - b.quality_score,
      render: (_: any, r: ConvertibleBond) => (
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 10,
          fontSize: 12, fontWeight: 700, color: verdictColor(r.verdict),
          background: `${verdictColor(r.verdict)}22`, border: `1px solid ${verdictColor(r.verdict)}44`,
        }}>
          {r.quality_score}<span style={{ fontSize: 10, opacity: 0.8 }}>{r.verdict}</span>
        </span>
      ),
    },
    { title: '评级', dataIndex: 'rating_cd', width: 70 },
    {
      title: '剩余年限', dataIndex: 'year_left', width: 90, sorter: (a, b) => a.year_left - b.year_left,
      render: (v: number) => <Text>{v < 0 ? '—' : `${v?.toFixed(1)} 年`}</Text>,
    },
    {
      title: '正股', dataIndex: 'stock_nm', width: 110, render: (v: string) => <Text style={{ color: '#8b949e', fontSize: 12 }}>{v}</Text>,
    },
  ], [])

  // ===== 渲染 =====
  return (
    <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
      {/* 左侧：八大战法主列表 */}
      <div style={{ width: 290, flexShrink: 0 }}>
        <Title level={5} style={{ marginTop: 0, marginBottom: 12 }}>
          <ReadOutlined style={{ marginRight: 8, color: '#58a6ff' }} />
          八大战法
        </Title>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {order.map((key, idx) => {
            const s = strategies[key]
            if (!s) return null
            const vis = STRATEGY_VISUAL[key]
            const isActive = activeKey === key
            const rt = riskTag(s.risk_level)
            return (
              <div
                key={key}
                onClick={() => setActiveKey(key)}
                style={{
                  cursor: 'pointer', padding: '10px 12px', borderRadius: 8,
                  background: isActive ? `${vis.color}1f` : '#161b22',
                  border: `1px solid ${isActive ? vis.color : '#30363d'}`,
                  borderLeft: `3px solid ${isActive ? vis.color : 'transparent'}`,
                  transition: 'all 0.15s',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontWeight: 700, fontSize: 13, color: isActive ? vis.color : '#e6edf3' }}>
                    <span style={{ marginRight: 6 }}>{vis?.icon}</span>{s.name}
                  </span>
                  <Tag color={rt.color} style={{ margin: 0, fontSize: 11 }}>{rt.text}</Tag>
                </div>
                <div style={{ fontSize: 11, color: '#8b949e', marginTop: 4 }}>
                  第{idx + 1}战法 · {s.master} · {s.expected_return}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* 右侧：详情 + 结果 */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {active ? (
          <Card
            style={{ background: '#161b22', borderColor: '#30363d' }}
            styles={{ body: { padding: 20 } }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
              <div>
                <Title level={4} style={{ margin: 0 }}>
                  <span style={{ marginRight: 8 }}>{activeVis?.icon}</span>{active.name}
                </Title>
                <Space size={[6, 6]} wrap style={{ marginTop: 8 }}>
                  <Tag color={riskTag(active.risk_level).color}>风险 {active.risk_level}</Tag>
                  <Tag>复杂度 {active.complexity}</Tag>
                  <Tag color="blue">期望 {active.expected_return}</Tag>
                  <Tag color="purple">门槛 {active.min_capital}</Tag>
                  <Tooltip title={active.source}><Tag>{active.master}</Tag></Tooltip>
                </Space>
              </div>
              {activeKey === 'grid' && (
                <Button icon={<FundOutlined />} onClick={() => navigate('/grid-trading')}>
                  进入网格交易工具
                </Button>
              )}
            </div>

            <Paragraph style={{ marginTop: 14, marginBottom: 4, fontStyle: 'italic', color: '#8b949e', borderLeft: `3px solid ${activeVis?.color}`, paddingLeft: 12 }}>
              「{active.philosophy}」
            </Paragraph>

            <Tabs
              defaultActiveKey="result"
              items={[
                {
                  key: 'result',
                  label: '筛选结果',
                  children: (
                    <div>
                      {/* 控制条 */}
                      <Space style={{ marginBottom: 12, width: '100%', justifyContent: 'space-between', flexWrap: 'wrap' }} wrap>
                        <Space wrap>
                          <Text style={{ color: '#8b949e' }}>显示数量</Text>
                          <Select
                            value={topN}
                            onChange={(v) => setTopN(v)}
                            style={{ width: 110 }}
                            options={[
                              { value: 10, label: '前 10 只' },
                              { value: 20, label: '前 20 只' },
                              { value: 30, label: '前 30 只' },
                              { value: 50, label: '前 50 只' },
                            ]}
                          />
                          <Button type="primary" icon={<ReloadOutlined />} loading={loading} onClick={() => runStrategy(activeKey)}>
                            运行筛选
                          </Button>
                        </Space>
                        <Space wrap>
                          {fetchTime && <Text type="secondary" style={{ fontSize: 12 }}>更新: {fetchTime}</Text>}
                          {total > 0 && <Tag color="green">符合条件 {total} 只</Tag>}
                          {dataSource && (
                            <Tag color={['jisilu', 'jisilu_web'].includes(dataSource) ? 'green' : 'gold'}>
                              数据源: {dataSource === 'jisilu' ? '集思录' : dataSource === 'jisilu_web' ? '集思录(网页版)' : dataSource === 'akshare' ? 'AKShare(兜底)' : dataSource}
                            </Tag>
                          )}
                        </Space>
                      </Space>

                      {error && <Alert type="warning" showIcon message={error} style={{ marginBottom: 12 }} />}

                      {dataSource === 'akshare' && !error && (
                        <Alert
                          type="info" showIcon style={{ marginBottom: 12 }}
                          message="数据来源说明"
                          description="当前使用 AKShare 兜底数据，不含「剩余年限 / 成交额 / 到期收益率(YTM)」。依赖这些字段的策略会严格返回空（不展示伪候选）。请登录集思录（或启用集思录网页版爬取）以获取完整字段。"
                        />
                      )}

                      {loading ? (
                        <div style={{ textAlign: 'center', padding: 48 }}><Spin tip="筛选中…"><div style={{ height: 1 }} /></Spin></div>
                      ) : bonds.length === 0 ? (
                        <Empty
                          style={{ padding: 48 }}
                          description={
                            error
                              ? error
                              : dataSource === 'akshare'
                                ? '该策略需「剩余年限 / 成交额 / 到期收益率」等字段，AKShare 兜底数据不提供，故无结果。请登录集思录后重试。'
                                : `当前市场暂无符合「${active.name}」条件的标的`
                          }
                        />
                      ) : (
                        <Table<ConvertibleBond>
                          rowKey="bond_id"
                          size="small"
                          columns={columns}
                          dataSource={bonds}
                          pagination={bonds.length > topN ? { pageSize: topN, showSizeChanger: false } : false}
                          scroll={{ x: 880 }}
                          style={{ marginTop: 4 }}
                        />
                      )}
                    </div>
                  ),
                },
                {
                  key: 'detail',
                  label: '战法详解',
                  children: <StrategyDetail s={active} />,
                },
                {
                  key: 'compare',
                  label: '横向对比',
                  children: <CompareTable strategies={strategies} order={order} current={activeKey} onSelect={setActiveKey} />,
                },
              ]}
            />
          </Card>
        ) : (
          <Card style={{ background: '#161b22', borderColor: '#30363d' }}>
            <Empty description="加载八大战法中…" />
          </Card>
        )}
      </div>
    </div>
  )
}

// ===== 战法详解 =====
function StrategyDetail({ s }: { s: CBStrategy }) {
  const Section = ({ title, children }: { title: string; children: ReactNode }) => (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8, color: '#e6edf3' }}>{title}</div>
      {children}
    </div>
  )
  return (
    <div>
      <Section title="✅ 适合什么样的人">
        <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.9, color: '#c9d1d9' }}>
          {s.suitable_for.map((it, i) => <li key={i}>{it}</li>)}
        </ul>
      </Section>
      <Section title="📋 操作规则">
        <ol style={{ margin: 0, paddingLeft: 20, lineHeight: 1.9, color: '#c9d1d9' }}>
          {s.rules.map((it, i) => <li key={i}>{it}</li>)}
        </ol>
      </Section>
      <Section title="⚠️ 风险应对">
        <div style={{ display: 'grid', gap: 8 }}>
          {s.risks.map((r, i) => (
            <div key={i} style={{ padding: 10, background: '#0d1117', borderRadius: 6, border: '1px solid #30363d', fontSize: 12.5 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <Text strong style={{ color: '#ff4d4f' }}>{r.name}</Text>
                <Tag color={r.probability.includes('高') ? 'red' : r.probability.includes('中') ? 'gold' : 'green'}>
                  概率 {r.probability}
                </Tag>
              </div>
              <div style={{ color: '#8b949e' }}>
                影响: {r.impact}　|　应对: <Text style={{ color: '#52c41a' }}>{r.solution}</Text>
              </div>
            </div>
          ))}
        </div>
      </Section>
      <Section title="🕳️ 常见陷阱">
        <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.9, color: '#c9d1d9' }}>
          {s.pitfalls.map((it, i) => <li key={i}>{it}</li>)}
        </ul>
      </Section>
      <Section title="📌 注意事项">
        <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.9, color: '#c9d1d9' }}>
          {s.warnings.map((it, i) => <li key={i}>{it}</li>)}
        </ul>
      </Section>
      <div style={{ fontSize: 11.5, color: '#8b949e' }}>📚 出处: {s.source}</div>
    </div>
  )
}

// ===== 横向对比 =====
function CompareTable({ strategies, order, current, onSelect }: {
  strategies: Record<string, CBStrategy>
  order: string[]
  current: string
  onSelect: (k: string) => void
}) {
  const data = order.map(k => strategies[k]).filter(Boolean).map((s, i) => ({
    key: s.key,
    idx: i + 1,
    name: s.name,
    risk: s.risk_level,
    complexity: s.complexity,
    ret: s.expected_return,
    capital: s.min_capital,
    philo: s.philosophy,
    active: s.key === current,
  }))
  const columns: ColumnsType<typeof data[number]> = [
    { title: '#', dataIndex: 'idx', width: 40 },
    {
      title: '战法', dataIndex: 'name', width: 130,
      render: (v: string, r) => (
        <a onClick={() => onSelect(r.key)} style={{ color: r.active ? '#58a6ff' : undefined, fontWeight: r.active ? 700 : 400 }}>
          {v}
        </a>
      ),
    },
    { title: '风险', dataIndex: 'risk', width: 70, render: (v: string) => <Tag color={riskTag(v).color}>{v}</Tag> },
    { title: '复杂度', dataIndex: 'complexity', width: 80 },
    { title: '期望年化', dataIndex: 'ret', width: 100 },
    { title: '最低资金', dataIndex: 'capital', width: 90 },
    { title: '核心逻辑', dataIndex: 'philo', render: (v: string) => <Text style={{ color: '#8b949e', fontSize: 12 }}>{v}</Text> },
  ]
  return (
    <Table
      rowKey="key"
      size="small"
      columns={columns}
      dataSource={data}
      pagination={false}
      scroll={{ x: 700 }}
      style={{ marginTop: 4 }}
    />
  )
}
