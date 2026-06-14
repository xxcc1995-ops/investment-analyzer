/**
 * 空投机会扫描器 - 系统化空投机会发现与评分
 *
 * 六大模块：
 * 1. 未发币协议 - DefiLlama高TVL未发币协议扫描
 * 2. 交易所活动 - 币安/OKX/Bybit/Gate活动汇总
 * 3. 链上打新 - Virtuals/Kaito/MegaETH等打新追踪
 * 4. 空投资讯 - RSS多源空投新闻聚合
 * 5. 机会评分 - 多维度加权评分系统
 * 6. 多号管理 - localStorage多账号进度追踪
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Tabs, Table, Tag, Card, Row, Col, Statistic, Button, Space,
  Badge, Tooltip, Progress, Collapse, Checkbox, Input, Select,
  message, Empty, Spin, Divider,
} from 'antd'
import {
  GiftOutlined, ThunderboltOutlined, RocketOutlined,
  FileTextOutlined, BarChartOutlined, TeamOutlined,
  ReloadOutlined, LinkOutlined, StarFilled,
  PlusOutlined, DeleteOutlined, ExportOutlined, ImportOutlined,
  CheckCircleFilled, ClockCircleFilled, FireFilled,
} from '@ant-design/icons'
import { airdropScannerApi } from '../services/api'

const { TabPane } = Tabs
const { Panel } = Collapse

// ============ 颜色映射 ============

const SCORE_COLORS: Record<string, string> = {
  high: '#52c41a',
  medium: '#1890ff',
  low: '#faad14',
  very_low: '#8b949e',
}

const TIER_COLORS: Record<string, string> = {
  '确定赚钱': '#52c41a',
  '必做': '#1890ff',
  '高潜力': '#faad14',
  '探索性': '#8b949e',
}

const IMPACT_COLORS: Record<string, string> = {
  high: '#ff4d4f',
  medium: '#faad14',
  low: '#8b949e',
}

function getScoreColor(score: number): string {
  if (score >= 75) return SCORE_COLORS.high
  if (score >= 50) return SCORE_COLORS.medium
  if (score >= 25) return SCORE_COLORS.low
  return SCORE_COLORS.very_low
}

function getScoreLabel(score: number): string {
  if (score >= 75) return '高'
  if (score >= 50) return '中'
  if (score >= 25) return '低'
  return '极低'
}

// ============ 主组件 ============

export default function AirdropScannerPage() {
  return (
    <div style={{ padding: '0 4px' }}>
      {/* 页面标题 */}
      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ fontSize: 28 }}>🪂</span>
        <div>
          <h2 style={{ color: '#e6edf3', margin: 0, fontSize: 22 }}>
            空投机会扫描器 <Tag color="gold">系统化空投</Tag>
          </h2>
          <div style={{ color: '#8b949e', fontSize: 13 }}>
            未发币协议扫描 · 交易所活动 · 链上打新 · 空投资讯 · 机会评分 · 多号管理
          </div>
        </div>
      </div>

      <Tabs defaultActiveKey="scoring" type="card" size="large">
        <TabPane tab={<span><BarChartOutlined /> 机会评分</span>} key="scoring">
          <OpportunityScoring />
        </TabPane>
        <TabPane tab={<span><GiftOutlined /> 未发币协议</span>} key="protocols">
          <UntokenizedProtocols />
        </TabPane>
        <TabPane tab={<span><ThunderboltOutlined /> 交易所活动</span>} key="exchange">
          <ExchangeActivities />
        </TabPane>
        <TabPane tab={<span><RocketOutlined /> 链上打新</span>} key="launchpad">
          <LaunchpadProjects />
        </TabPane>
        <TabPane tab={<span><FileTextOutlined /> 空投资讯</span>} key="news">
          <AirdropNews />
        </TabPane>
        <TabPane tab={<span><TeamOutlined /> 多号管理</span>} key="accounts">
          <MultiAccountManager />
        </TabPane>
      </Tabs>
    </div>
  )
}

// ============ Tab 1: 机会评分 ============

function OpportunityScoring() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await airdropScannerApi.getOpportunityScores()
      setData(res.data)
    } catch (e) {
      console.error('加载机会评分失败:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '60px auto' }} />
  if (!data) return <Empty description="暂无数据" />

  const tierCounts = data.tier_counts || {}
  const opportunities = data.opportunities || []

  const columns = [
    {
      title: '排名',
      key: 'rank',
      width: 60,
      render: (_: any, __: any, index: number) => (
        <span style={{
          color: index < 3 ? '#faad14' : '#8b949e',
          fontWeight: index < 3 ? 'bold' : 'normal',
          fontSize: index < 3 ? 16 : 14,
        }}>
          {index < 3 ? ['🥇', '🥈', '🥉'][index] : index + 1}
        </span>
      ),
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      render: (name: string, record: any) => (
        <div>
          <div style={{ color: '#e6edf3', fontWeight: 500 }}>{name}</div>
          <div style={{ color: '#8b949e', fontSize: 12 }}>{record.detail}</div>
        </div>
      ),
    },
    {
      title: '来源',
      dataIndex: 'source_label',
      key: 'source_label',
      width: 100,
      render: (label: string, record: any) => {
        const colorMap: Record<string, string> = {
          defi: 'purple', exchange: 'blue', launchpad: 'orange',
        }
        return <Tag color={colorMap[record.source] || 'default'}>{label}</Tag>
      },
    },
    {
      title: '确定性',
      dataIndex: 'certainty',
      key: 'certainty',
      width: 80,
      sorter: (a: any, b: any) => a.certainty - b.certainty,
      render: (v: number) => <ScoreCell value={v} />,
    },
    {
      title: '预期收益',
      dataIndex: 'expected_return',
      key: 'expected_return',
      width: 80,
      sorter: (a: any, b: any) => a.expected_return - b.expected_return,
      render: (v: number) => <ScoreCell value={v} />,
    },
    {
      title: '难度',
      dataIndex: 'difficulty',
      key: 'difficulty',
      width: 80,
      sorter: (a: any, b: any) => a.difficulty - b.difficulty,
      render: (v: number) => <ScoreCell value={10 - v} inverted />,
    },
    {
      title: '时间窗口',
      dataIndex: 'time_window',
      key: 'time_window',
      width: 80,
      sorter: (a: any, b: any) => a.time_window - b.time_window,
      render: (v: number) => <ScoreCell value={v} />,
    },
    {
      title: '综合评分',
      dataIndex: 'composite_score',
      key: 'composite_score',
      width: 100,
      defaultSortOrder: 'descend' as const,
      sorter: (a: any, b: any) => a.composite_score - b.composite_score,
      render: (score: number, record: any) => (
        <div style={{ textAlign: 'center' }}>
          <div style={{
            fontSize: 20, fontWeight: 'bold',
            color: TIER_COLORS[record.risk_tier] || '#e6edf3',
          }}>
            {score.toFixed(1)}
          </div>
          <Tag
            color={TIER_COLORS[record.risk_tier]}
            style={{ fontSize: 11, marginTop: 2 }}
          >
            {record.risk_tier}
          </Tag>
        </div>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: any, record: any) => (
        record.url ? (
          <Button
            type="link"
            size="small"
            icon={<LinkOutlined />}
            onClick={() => window.open(record.url, '_blank')}
          >
            详情
          </Button>
        ) : null
      ),
    },
  ]

  return (
    <div>
      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small" style={{ background: '#161b22', border: '1px solid #30363d' }}>
            <Statistic
              title={<span style={{ color: '#8b949e' }}>总机会数</span>}
              value={data.total_count}
              valueStyle={{ color: '#e6edf3' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" style={{ background: '#161b22', border: '1px solid #30363d' }}>
            <Statistic
              title={<span style={{ color: '#8b949e' }}>确定赚钱</span>}
              value={tierCounts['确定赚钱'] || 0}
              valueStyle={{ color: '#52c41a' }}
              prefix={<CheckCircleFilled />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" style={{ background: '#161b22', border: '1px solid #30363d' }}>
            <Statistic
              title={<span style={{ color: '#8b949e' }}>必做</span>}
              value={tierCounts['必做'] || 0}
              valueStyle={{ color: '#1890ff' }}
              prefix={<FireFilled />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" style={{ background: '#161b22', border: '1px solid #30363d' }}>
            <Statistic
              title={<span style={{ color: '#8b949e' }}>高潜力</span>}
              value={tierCounts['高潜力'] || 0}
              valueStyle={{ color: '#faad14' }}
              prefix={<StarFilled />}
            />
          </Card>
        </Col>
      </Row>

      {/* 评分表格 */}
      <Card
        size="small"
        title={<span style={{ color: '#e6edf3' }}>📊 综合机会评分排名</span>}
        extra={
          <Button size="small" icon={<ReloadOutlined />} onClick={loadData}>
            刷新
          </Button>
        }
        style={{ background: '#161b22', border: '1px solid #30363d' }}
      >
        <Table
          dataSource={opportunities}
          columns={columns}
          rowKey="name"
          size="small"
          pagination={{ pageSize: 20 }}
          scroll={{ x: 900 }}
          style={{ background: 'transparent' }}
        />
      </Card>
    </div>
  )
}

// 评分单元格组件
function ScoreCell({ value, inverted }: { value: number; inverted?: boolean }) {
  const displayValue = inverted ? 10 - value : value
  const color = getScoreColor(displayValue * 10)
  return (
    <Tooltip title={`${displayValue.toFixed(1)} / 10`}>
      <Progress
        percent={displayValue * 10}
        size="small"
        strokeColor={color}
        showInfo={false}
        style={{ marginBottom: 0 }}
      />
      <span style={{ fontSize: 12, color }}>{displayValue.toFixed(1)}</span>
    </Tooltip>
  )
}

// ============ Tab 2: 未发币协议 ============

function UntokenizedProtocols() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await airdropScannerApi.getUntokenizedProtocols()
      setData(res.data)
    } catch (e) {
      console.error('加载未发币协议失败:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '60px auto' }} />
  if (!data) return <Empty description="暂无数据" />

  const protocols = data.protocols || []

  const columns = [
    {
      title: '协议',
      dataIndex: 'name',
      key: 'name',
      width: 180,
      render: (name: string, record: any) => (
        <div>
          <div style={{ color: '#e6edf3', fontWeight: 500 }}>{name}</div>
          {record.description && (
            <Tooltip title={record.description}>
              <div style={{ color: '#8b949e', fontSize: 11, maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {record.description}
              </div>
            </Tooltip>
          )}
        </div>
      ),
    },
    {
      title: '链',
      dataIndex: 'chain',
      key: 'chain',
      width: 120,
      render: (chain: string, record: any) => (
        <Space size={4} wrap>
          <Tag color="blue">{chain}</Tag>
          {record.chains && record.chains.length > 1 && (
            <Tooltip title={record.chains.join(', ')}>
              <Tag color="default">+{record.chains.length - 1}</Tag>
            </Tooltip>
          )}
        </Space>
      ),
    },
    {
      title: '赛道',
      dataIndex: 'category',
      key: 'category',
      width: 120,
      render: (cat: string) => <Tag color="purple">{cat}</Tag>,
    },
    {
      title: 'TVL',
      dataIndex: 'tvl',
      key: 'tvl',
      width: 100,
      sorter: (a: any, b: any) => a.tvl - b.tvl,
      render: (tvl: number) => (
        <span style={{ color: '#e6edf3', fontWeight: 500 }}>
          ${tvl >= 1000 ? `${(tvl / 1000).toFixed(1)}B` : `${tvl.toFixed(0)}M`}
        </span>
      ),
    },
    {
      title: '年龄',
      dataIndex: 'age_months',
      key: 'age_months',
      width: 80,
      render: (months: number | null) => {
        if (months === null) return <span style={{ color: '#8b949e' }}>N/A</span>
        const label = months >= 12 ? `${(months / 12).toFixed(1)}年` : `${months}月`
        const color = months >= 6 && months <= 24 ? '#52c41a' : '#faad14'
        return <span style={{ color }}>{label}</span>
      },
    },
    {
      title: '30d TVL变化',
      dataIndex: 'tvl_change_1m',
      key: 'tvl_change_1m',
      width: 110,
      sorter: (a: any, b: any) => (a.tvl_change_1m || 0) - (b.tvl_change_1m || 0),
      render: (change: number | null) => {
        if (change === null) return <span style={{ color: '#8b949e' }}>N/A</span>
        const color = change >= 0 ? '#52c41a' : '#ff4d4f'
        const prefix = change >= 0 ? '+' : ''
        return <span style={{ color }}>{prefix}{change.toFixed(1)}%</span>
      },
    },
    {
      title: '空投评分',
      dataIndex: 'airdrop_score',
      key: 'airdrop_score',
      width: 120,
      defaultSortOrder: 'descend' as const,
      sorter: (a: any, b: any) => a.airdrop_score - b.airdrop_score,
      render: (score: number) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Progress
            percent={score}
            size="small"
            strokeColor={getScoreColor(score)}
            showInfo={false}
            style={{ flex: 1, marginBottom: 0 }}
          />
          <span style={{ color: getScoreColor(score), fontWeight: 'bold', minWidth: 30 }}>
            {score.toFixed(0)}
          </span>
        </div>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 60,
      render: (_: any, record: any) => (
        record.url ? (
          <Button
            type="link"
            size="small"
            icon={<LinkOutlined />}
            onClick={() => window.open(record.url, '_blank')}
          />
        ) : null
      ),
    },
  ]

  return (
    <div>
      {/* 统计 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card size="small" style={{ background: '#161b22', border: '1px solid #30363d' }}>
            <Statistic
              title={<span style={{ color: '#8b949e' }}>未发币协议数</span>}
              value={data.count}
              valueStyle={{ color: '#e6edf3' }}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small" style={{ background: '#161b22', border: '1px solid #30363d' }}>
            <Statistic
              title={<span style={{ color: '#8b949e' }}>高评分协议 (&gt;60)</span>}
              value={protocols.filter((p: any) => p.airdrop_score > 60).length}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small" style={{ background: '#161b22', border: '1px solid #30363d' }}>
            <Statistic
              title={<span style={{ color: '#8b949e' }}>数据更新</span>}
              value={data.update_time ? new Date(data.update_time).toLocaleTimeString('zh-CN') : 'N/A'}
              valueStyle={{ color: '#8b949e', fontSize: 16 }}
            />
          </Card>
        </Col>
      </Row>

      <Card
        size="small"
        title={<span style={{ color: '#e6edf3' }}>🔍 DefiLlama 未发币高TVL协议</span>}
        extra={<Button size="small" icon={<ReloadOutlined />} onClick={loadData}>刷新</Button>}
        style={{ background: '#161b22', border: '1px solid #30363d' }}
      >
        <Table
          dataSource={protocols}
          columns={columns}
          rowKey="name"
          size="small"
          pagination={{ pageSize: 20 }}
          scroll={{ x: 900 }}
        />
      </Card>
    </div>
  )
}

// ============ Tab 3: 交易所活动 ============

function ExchangeActivities() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string>('all')

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await airdropScannerApi.getExchangeActivities()
      setData(res.data)
    } catch (e) {
      console.error('加载交易所活动失败:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '60px auto' }} />
  if (!data) return <Empty description="暂无数据" />

  let campaigns = data.campaigns || []
  if (filter !== 'all') {
    campaigns = campaigns.filter((c: any) => c.status === filter)
  }

  const statusColors: Record<string, string> = {
    active: 'green',
    upcoming: 'blue',
    ended: 'default',
  }
  const difficultyColors: Record<string, string> = {
    easy: 'green',
    medium: 'orange',
    hard: 'red',
  }

  return (
    <div>
      {/* 筛选 */}
      <div style={{ marginBottom: 16, display: 'flex', gap: 8, alignItems: 'center' }}>
        <span style={{ color: '#8b949e' }}>状态筛选：</span>
        {['all', 'active', 'upcoming'].map(f => (
          <Button
            key={f}
            size="small"
            type={filter === f ? 'primary' : 'default'}
            onClick={() => setFilter(f)}
          >
            {{ all: '全部', active: '进行中', upcoming: '即将开始' }[f]}
          </Button>
        ))}
        <span style={{ color: '#8b949e', marginLeft: 'auto' }}>
          共 {campaigns.length} 个活动
        </span>
      </div>

      {/* 按交易所分组 */}
      <Row gutter={[16, 16]}>
        {campaigns.map((campaign: any) => (
          <Col key={campaign.id} xs={24} sm={12} lg={8} xl={6}>
            <Card
              size="small"
              style={{
                background: '#161b22',
                border: '1px solid #30363d',
                height: '100%',
              }}
              title={
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Tag color="blue">{campaign.exchange}</Tag>
                  <Tag color="purple">{campaign.type}</Tag>
                </div>
              }
              extra={
                <Tag color={statusColors[campaign.status]}>
                  {{ active: '进行中', upcoming: '即将', ended: '已结束' }[campaign.status]}
                </Tag>
              }
            >
              <div style={{ color: '#e6edf3', fontWeight: 500, marginBottom: 8 }}>
                {campaign.name}
              </div>
              <div style={{ color: '#8b949e', fontSize: 12, marginBottom: 12, lineHeight: 1.5 }}>
                {campaign.description}
              </div>
              <Divider style={{ margin: '8px 0', borderColor: '#30363d' }} />
              <Row gutter={8}>
                <Col span={12}>
                  <div style={{ color: '#8b949e', fontSize: 11 }}>预期收益</div>
                  <div style={{ color: '#52c41a', fontWeight: 500 }}>{campaign.estimated_value}</div>
                </Col>
                <Col span={12}>
                  <div style={{ color: '#8b949e', fontSize: 11 }}>资金需求</div>
                  <div style={{ color: '#faad14' }}>{campaign.capital_required}</div>
                </Col>
              </Row>
              <div style={{ marginTop: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Tag color={difficultyColors[campaign.difficulty]}>
                  {{ easy: '简单', medium: '中等', hard: '困难' }[campaign.difficulty]}
                </Tag>
                {campaign.url && (
                  <Button
                    type="link"
                    size="small"
                    icon={<LinkOutlined />}
                    onClick={() => window.open(campaign.url, '_blank')}
                  >
                    参与
                  </Button>
                )}
              </div>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  )
}

// ============ Tab 4: 链上打新 ============

function LaunchpadProjects() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await airdropScannerApi.getLaunchpadProjects()
      setData(res.data)
    } catch (e) {
      console.error('加载链上打新失败:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '60px auto' }} />
  if (!data) return <Empty description="暂无数据" />

  const projects = data.projects || []

  const statusColors: Record<string, string> = {
    active: 'green',
    upcoming: 'blue',
    ended: 'default',
  }

  const columns = [
    {
      title: '项目',
      dataIndex: 'project_name',
      key: 'project_name',
      width: 200,
      render: (name: string) => <span style={{ color: '#e6edf3', fontWeight: 500 }}>{name}</span>,
    },
    {
      title: '平台',
      dataIndex: 'platform',
      key: 'platform',
      width: 150,
      render: (platform: string, record: any) => (
        <a
          href={record.platform_url}
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: '#1890ff' }}
        >
          {platform}
        </a>
      ),
    },
    {
      title: '链',
      dataIndex: 'chain',
      key: 'chain',
      width: 100,
      render: (chain: string) => <Tag color="blue">{chain}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: string) => (
        <Tag color={statusColors[status]}>
          {{ active: '进行中', upcoming: '即将', ended: '已结束' }[status]}
        </Tag>
      ),
    },
    {
      title: '预估分配',
      dataIndex: 'estimated_allocation',
      key: 'estimated_allocation',
      width: 120,
    },
    {
      title: '备注',
      dataIndex: 'notes',
      key: 'notes',
      ellipsis: true,
      render: (notes: string) => (
        <Tooltip title={notes}>
          <span style={{ color: '#8b949e', fontSize: 12 }}>{notes}</span>
        </Tooltip>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: any, record: any) => (
        record.participation_link ? (
          <Button
            type="link"
            size="small"
            icon={<LinkOutlined />}
            onClick={() => window.open(record.participation_link, '_blank')}
          >
            参与
          </Button>
        ) : null
      ),
    },
  ]

  return (
    <Card
      size="small"
      title={<span style={{ color: '#e6edf3' }}>🚀 链上打新/IDO项目追踪</span>}
      extra={<Button size="small" icon={<ReloadOutlined />} onClick={loadData}>刷新</Button>}
      style={{ background: '#161b22', border: '1px solid #30363d' }}
    >
      <Table
        dataSource={projects}
        columns={columns}
        rowKey="id"
        size="small"
        pagination={false}
        scroll={{ x: 800 }}
      />
    </Card>
  )
}

// ============ Tab 5: 空投资讯 ============

function AirdropNews() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [impactFilter, setImpactFilter] = useState<string>('all')

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await airdropScannerApi.getNews()
      setData(res.data)
    } catch (e) {
      console.error('加载空投资讯失败:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '60px auto' }} />
  if (!data) return <Empty description="暂无数据" />

  let items = data.items || []
  if (impactFilter !== 'all') {
    items = items.filter((item: any) => item.impact === impactFilter)
  }

  const impactLabels: Record<string, string> = {
    high: '🔴 高影响',
    medium: '🟡 中影响',
    low: '⚪ 低影响',
  }

  const categoryLabels: Record<string, string> = {
    exchange: '交易所',
    defi: 'DeFi',
    l2: 'L2',
    general: '综合',
  }

  return (
    <div>
      {/* 筛选和统计 */}
      <div style={{ marginBottom: 16, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={{ color: '#8b949e' }}>影响级别：</span>
        {['all', 'high', 'medium'].map(f => (
          <Button
            key={f}
            size="small"
            type={impactFilter === f ? 'primary' : 'default'}
            onClick={() => setImpactFilter(f)}
          >
            {{ all: '全部', high: '🔴 高影响', medium: '🟡 中影响' }[f]}
          </Button>
        ))}
        <span style={{ color: '#8b949e', marginLeft: 'auto' }}>
          扫描 {data.total_scanned} 条 · 空投相关 {data.airdrop_related} 条
        </span>
      </div>

      {/* 源状态 */}
      <div style={{ marginBottom: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {data.sources_ok?.map((s: string) => (
          <Tag key={s} color="green">✓ {s}</Tag>
        ))}
        {data.sources_failed?.map((s: string) => (
          <Tag key={s} color="red">✗ {s}</Tag>
        ))}
      </div>

      {/* 新闻列表 */}
      {items.length === 0 ? (
        <Empty description="暂无空投相关新闻" />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {items.map((item: any, index: number) => (
            <Card
              key={index}
              size="small"
              style={{ background: '#161b22', border: '1px solid #30363d' }}
              bodyStyle={{ padding: '12px 16px' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <Tag color={IMPACT_COLORS[item.impact]} style={{ fontSize: 11 }}>
                      {impactLabels[item.impact]}
                    </Tag>
                    <Tag color="default" style={{ fontSize: 11 }}>
                      {categoryLabels[item.category] || item.category}
                    </Tag>
                    <Tag style={{ fontSize: 11 }}>{item.source}</Tag>
                  </div>
                  <a
                    href={item.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: '#e6edf3', fontWeight: 500, fontSize: 14 }}
                  >
                    {item.title}
                  </a>
                  {item.summary && (
                    <div style={{ color: '#8b949e', fontSize: 12, marginTop: 4, lineHeight: 1.5 }}>
                      {item.summary}
                    </div>
                  )}
                </div>
                <span style={{ color: '#8b949e', fontSize: 11, whiteSpace: 'nowrap' }}>
                  {item.published ? new Date(item.published).toLocaleDateString('zh-CN') : ''}
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

// ============ Tab 6: 多号管理 ============

interface Account {
  id: string
  label: string
  type: 'wallet' | 'exchange'
}

interface AccountManagerData {
  accounts: Account[]
  progress: Record<string, Record<string, boolean>>
}

const STORAGE_KEY = 'airdrop_scanner_accounts'

function loadAccountData(): AccountManagerData {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch {}
  return { accounts: [], progress: {} }
}

function saveAccountData(data: AccountManagerData) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
}

function MultiAccountManager() {
  const [data, setData] = useState<AccountManagerData>(loadAccountData)
  const [newLabel, setNewLabel] = useState('')
  const [newType, setNewType] = useState<'wallet' | 'exchange'>('wallet')
  const [opportunityInput, setOpportunityInput] = useState('')

  // 保存到localStorage
  useEffect(() => {
    saveAccountData(data)
  }, [data])

  const addAccount = () => {
    if (!newLabel.trim()) {
      message.warning('请输入账号名称')
      return
    }
    const newAccount: Account = {
      id: Date.now().toString(),
      label: newLabel.trim(),
      type: newType,
    }
    setData(prev => ({
      ...prev,
      accounts: [...prev.accounts, newAccount],
    }))
    setNewLabel('')
    message.success(`已添加${newType === 'wallet' ? '钱包' : '交易所'}账号: ${newLabel.trim()}`)
  }

  const removeAccount = (id: string) => {
    setData(prev => {
      const newProgress = { ...prev.progress }
      Object.keys(newProgress).forEach(oppId => {
        if (newProgress[oppId]) {
          delete newProgress[oppId][id]
        }
      })
      return {
        accounts: prev.accounts.filter(a => a.id !== id),
        progress: newProgress,
      }
    })
  }

  const toggleProgress = (opportunityId: string, accountId: string) => {
    setData(prev => {
      const newProgress = { ...prev.progress }
      if (!newProgress[opportunityId]) {
        newProgress[opportunityId] = {}
      }
      newProgress[opportunityId] = {
        ...newProgress[opportunityId],
        [accountId]: !newProgress[opportunityId][accountId],
      }
      return { ...prev, progress: newProgress }
    })
  }

  const addOpportunity = () => {
    if (!opportunityInput.trim()) {
      message.warning('请输入机会名称')
      return
    }
    const key = opportunityInput.trim().toLowerCase().replace(/\s+/g, '_')
    if (data.progress[key]) {
      message.warning('该机会已存在')
      return
    }
    setData(prev => ({
      ...prev,
      progress: { ...prev.progress, [key]: {} },
    }))
    setOpportunityInput('')
  }

  const exportData = () => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `airdrop_accounts_${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
    message.success('导出成功')
  }

  const importData = () => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.json'
    input.onchange = (e: any) => {
      const file = e.target.files?.[0]
      if (!file) return
      const reader = new FileReader()
      reader.onload = (ev) => {
        try {
          const imported = JSON.parse(ev.target?.result as string)
          if (imported.accounts && imported.progress) {
            setData(imported)
            message.success('导入成功')
          } else {
            message.error('文件格式不正确')
          }
        } catch {
          message.error('文件解析失败')
        }
      }
      reader.readAsText(file)
    }
    input.click()
  }

  const opportunityIds = Object.keys(data.progress)

  return (
    <div>
      {/* 账号管理 */}
      <Card
        size="small"
        title={<span style={{ color: '#e6edf3' }}>👤 账号列表</span>}
        extra={
          <Space>
            <Button size="small" icon={<ExportOutlined />} onClick={exportData}>导出</Button>
            <Button size="small" icon={<ImportOutlined />} onClick={importData}>导入</Button>
          </Space>
        }
        style={{ background: '#161b22', border: '1px solid #30363d', marginBottom: 16 }}
      >
        {/* 添加账号 */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <Select
            value={newType}
            onChange={setNewType}
            size="small"
            style={{ width: 100 }}
            options={[
              { label: '🔑 钱包', value: 'wallet' },
              { label: '🏦 交易所', value: 'exchange' },
            ]}
          />
          <Input
            value={newLabel}
            onChange={e => setNewLabel(e.target.value)}
            placeholder="账号名称（如：主号、小号1、Binance账号）"
            size="small"
            onPressEnter={addAccount}
            style={{ flex: 1 }}
          />
          <Button size="small" type="primary" icon={<PlusOutlined />} onClick={addAccount}>
            添加
          </Button>
        </div>

        {/* 账号列表 */}
        {data.accounts.length === 0 ? (
          <Empty description="暂无账号，添加钱包或交易所账号开始追踪" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <Space wrap>
            {data.accounts.map(acc => (
              <Tag
                key={acc.id}
                closable
                onClose={() => removeAccount(acc.id)}
                color={acc.type === 'wallet' ? 'purple' : 'blue'}
                style={{ fontSize: 13, padding: '4px 8px' }}
              >
                {acc.type === 'wallet' ? '🔑' : '🏦'} {acc.label}
              </Tag>
            ))}
          </Space>
        )}
      </Card>

      {/* 机会进度追踪 */}
      <Card
        size="small"
        title={<span style={{ color: '#e6edf3' }}>📋 完成进度追踪</span>}
        style={{ background: '#161b22', border: '1px solid #30363d' }}
      >
        {/* 添加机会 */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <Input
            value={opportunityInput}
            onChange={e => setOpportunityInput(e.target.value)}
            placeholder="输入机会名称（如：币安Alpha第15期、Virtuals打新）"
            size="small"
            onPressEnter={addOpportunity}
            style={{ flex: 1 }}
          />
          <Button size="small" type="primary" icon={<PlusOutlined />} onClick={addOpportunity}>
            添加机会
          </Button>
        </div>

        {opportunityIds.length === 0 ? (
          <Empty description="暂无追踪机会" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : data.accounts.length === 0 ? (
          <Empty description="请先添加账号" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <Collapse
            size="small"
            style={{ background: 'transparent', border: '1px solid #30363d' }}
          >
            {opportunityIds.map(oppId => {
              const oppProgress = data.progress[oppId] || {}
              const doneCount = Object.values(oppProgress).filter(Boolean).length
              const total = data.accounts.length
              const percent = total > 0 ? Math.round((doneCount / total) * 100) : 0

              return (
                <Panel
                  key={oppId}
                  header={
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, width: '100%' }}>
                      <span style={{ color: '#e6edf3', fontWeight: 500 }}>{oppId}</span>
                      <Progress
                        percent={percent}
                        size="small"
                        style={{ flex: 1, marginBottom: 0 }}
                        strokeColor={percent === 100 ? '#52c41a' : '#1890ff'}
                      />
                      <span style={{ color: '#8b949e', fontSize: 12 }}>
                        {doneCount}/{total}
                      </span>
                    </div>
                  }
                  style={{ background: '#161b22', borderColor: '#30363d' }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {data.accounts.map(acc => (
                      <div
                        key={acc.id}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 8,
                          padding: '4px 0',
                        }}
                      >
                        <Checkbox
                          checked={!!oppProgress[acc.id]}
                          onChange={() => toggleProgress(oppId, acc.id)}
                        >
                          <span style={{ color: oppProgress[acc.id] ? '#52c41a' : '#8b949e' }}>
                            {acc.type === 'wallet' ? '🔑' : '🏦'} {acc.label}
                          </span>
                        </Checkbox>
                        {oppProgress[acc.id] && (
                          <CheckCircleFilled style={{ color: '#52c41a', fontSize: 14 }} />
                        )}
                      </div>
                    ))}
                  </div>
                </Panel>
              )
            })}
          </Collapse>
        )}
      </Card>
    </div>
  )
}
