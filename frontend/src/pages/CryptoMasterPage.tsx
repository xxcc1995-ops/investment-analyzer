import { useState, useEffect, useCallback } from 'react'
import {
  Card, Row, Col, Statistic, Tag, Tabs, Spin, Alert, Table, Progress,
  Collapse, Badge, Tooltip, Button, InputNumber, Select, Space, Divider, Typography
} from 'antd'
import {
  RocketOutlined, BookOutlined, ExperimentOutlined, SafetyOutlined,
  BankOutlined, CheckCircleOutlined, ReloadOutlined, DollarOutlined,
  RiseOutlined, FallOutlined, ThunderboltOutlined, CrownOutlined,
  BulbOutlined, WarningOutlined, HeartOutlined, StarOutlined,
  FireOutlined, InfoCircleOutlined, SecurityScanOutlined
} from '@ant-design/icons'
import { cryptoMasterApi } from '../services/api/cryptoMaster'

const { TabPane } = Tabs
const { Panel } = Collapse
const { Title, Paragraph, Text } = Typography

// ============ 工具函数 ============

const fmt = (n: number, decimals = 2) => {
  if (n === null || n === undefined || isNaN(n)) return 'N/A'
  if (Math.abs(n) >= 1e12) return `$${(n / 1e12).toFixed(decimals)}T`
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(decimals)}B`
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(decimals)}M`
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(decimals)}K`
  return `$${n.toFixed(decimals)}`
}

const fmtPct = (n: number) => {
  if (n === null || n === undefined || isNaN(n)) return 'N/A'
  const color = n >= 0 ? '#52c41a' : '#ff4d4f'
  const prefix = n >= 0 ? '+' : ''
  return <span style={{ color }}>{prefix}{n.toFixed(2)}%</span>
}

const fmtPrice = (n: number) => {
  if (!n) return 'N/A'
  if (n >= 1000) return `$${n.toLocaleString()}`
  if (n >= 1) return `$${n.toFixed(2)}`
  if (n >= 0.01) return `$${n.toFixed(4)}`
  return `$${n.toFixed(6)}`
}

// ============ Tab1: 市场全景 ============

function MarketOverview() {
  const [data, setData] = useState<any>(null)
  const [trending, setTrending] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [mkt, trd] = await Promise.all([
        cryptoMasterApi.getMarketOverview(),
        cryptoMasterApi.getTrending(),
      ])
      setData(mkt.data)
      setTrending(trd.data)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />
  if (!data) return <Alert type="error" message="加载失败，请检查网络连接" />

  const fng = data.fear_greed_index || {}
  const fngColor = fng.value <= 25 ? '#ff4d4f' : fng.value <= 50 ? '#faad14' : fng.value <= 75 ? '#1890ff' : '#52c41a'
  const hasCoinGecko = data.btc_price > 0
  const hasDefiLlama = data.total_tvl > 0

  return (
    <div>
      {/* CoinGecko不可达提示 */}
      {!hasCoinGecko && hasDefiLlama && (
        <Alert
          type="warning" showIcon closable
          message="CoinGecko行情API暂不可达"
          description="当前使用DefiLlama链上数据。如需完整行情数据，请配置代理（设置POLYMARKET_PROXY环境变量）。"
          style={{ marginBottom: 16, background: '#161b22', border: '1px solid #30363d' }}
        />
      )}

      {/* 恐惧贪婪指数 */}
      <Card style={{ marginBottom: 16, background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)', border: '1px solid #30363d' }}>
        <Row gutter={24} align="middle">
          <Col span={6} style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 14, color: '#8b949e', marginBottom: 8 }}>恐惧 & 贪婪指数</div>
            <Progress
              type="dashboard"
              percent={fng.value || 50}
              strokeColor={fngColor}
              format={() => <span style={{ color: fngColor, fontSize: 28, fontWeight: 700 }}>{fng.value || 'N/A'}</span>}
              size={120}
            />
            <div style={{ color: fngColor, fontSize: 16, fontWeight: 600, marginTop: 8 }}>{fng.label || 'N/A'}</div>
          </Col>
          <Col span={6}>
            {hasCoinGecko ? (
              <>
                <Statistic title="总市值" value={fmt(data.total_market_cap_usd)} valueStyle={{ color: '#e6edf3', fontSize: 22 }} />
                <div style={{ color: '#8b949e', fontSize: 12, marginTop: 4 }}>24h变化: {fmtPct(data.market_cap_change_24h)}</div>
              </>
            ) : (
              <>
                <Statistic title="DeFi总锁仓量" value={fmt(data.total_tvl)} valueStyle={{ color: '#52c41a', fontSize: 22 }} />
                <div style={{ color: '#8b949e', fontSize: 12, marginTop: 4 }}>公链数量: {data.chain_count}</div>
              </>
            )}
          </Col>
          <Col span={6}>
            {hasCoinGecko ? (
              <>
                <Statistic title="24h交易量" value={fmt(data.total_volume_24h)} valueStyle={{ color: '#e6edf3', fontSize: 22 }} />
                <div style={{ color: '#8b949e', fontSize: 12, marginTop: 4 }}>活跃币种: {data.active_cryptocurrencies?.toLocaleString()}</div>
              </>
            ) : (
              <>
                <Statistic title="ETH锁仓量" value={fmt(data.eth_tvl)} valueStyle={{ color: '#627eea', fontSize: 22 }} />
                <div style={{ color: '#8b949e', fontSize: 12, marginTop: 4 }}>ETH TVL占比: {data.eth_tvl_dominance}%</div>
              </>
            )}
          </Col>
          <Col span={6}>
            {hasCoinGecko ? (
              <>
                <div style={{ marginBottom: 12 }}>
                  <Statistic title="BTC主导率" value={`${data.btc_dominance}%`} valueStyle={{ color: '#f7931a', fontSize: 22 }} />
                </div>
                <div>
                  <Statistic title="ETH主导率" value={`${data.eth_dominance}%`} valueStyle={{ color: '#627eea', fontSize: 22 }} />
                </div>
              </>
            ) : (
              <div>
                <div style={{ color: '#8b949e', fontSize: 13, marginBottom: 8 }}>Top公链TVL</div>
                {data.top_chains_tvl?.slice(0, 3).map((c: any, i: number) => (
                  <div key={i} style={{ color: '#e6edf3', fontSize: 13, marginBottom: 2 }}>
                    {c.name}: {fmt(c.tvl)}
                  </div>
                ))}
              </div>
            )}
          </Col>
        </Row>
      </Card>

      {/* BTC & ETH */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Card style={{ background: '#161b22', border: '1px solid #30363d' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 28 }}>₿</span>
              <div>
                <div style={{ color: '#8b949e', fontSize: 13 }}>Bitcoin</div>
                <div style={{ color: '#e6edf3', fontSize: 24, fontWeight: 700 }}>{fmtPrice(data.btc_price)}</div>
                <div style={{ fontSize: 14 }}>{fmtPct(data.btc_24h_change)}</div>
              </div>
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card style={{ background: '#161b22', border: '1px solid #30363d' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 28 }}>⟠</span>
              <div>
                <div style={{ color: '#8b949e', fontSize: 13 }}>Ethereum</div>
                <div style={{ color: '#e6edf3', fontSize: 24, fontWeight: 700 }}>{fmtPrice(data.eth_price)}</div>
                <div style={{ fontSize: 14 }}>{fmtPct(data.eth_24h_change)}</div>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      {/* BTC主导率解读 */}
      {hasCoinGecko && data.btc_dominance > 0 && (
        <Alert
          type="info"
          showIcon
          icon={<BulbOutlined />}
          message="BTC主导率解读"
          description={data.btc_dominance > 55
            ? "BTC主导率较高，市场处于避险模式。资金集中于BTC，山寨币表现通常较弱。适合持有BTC，谨慎投资山寨币。"
            : data.btc_dominance > 45
              ? "BTC主导率适中，市场相对均衡。优质山寨币开始有机会，可以关注ETH和头部Layer1。"
              : "BTC主导率较低，可能是山寨季！资金从BTC流向山寨币，DeFi/NFT/Meme等板块可能爆发。注意风险管理。"
          }
          style={{ marginBottom: 16, background: '#161b22', border: '1px solid #30363d' }}
        />
      )}

      {/* 热门币种 */}
      {trending?.trending?.length > 0 && (
        <Card title={<><FireOutlined /> 热门趋势币种</>} style={{ background: '#161b22', border: '1px solid #30363d' }}>
          <Row gutter={[12, 12]}>
            {trending.trending.slice(0, 7).map((t: any, i: number) => (
              <Col span={3} key={i} style={{ textAlign: 'center' }}>
                <Badge count={t.market_cap_rank || '?'} style={{ backgroundColor: '#30363d' }}>
                  <div style={{
                    width: 64, height: 64, borderRadius: '50%', background: '#21262d',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 11, color: '#e6edf3', fontWeight: 600, border: '1px solid #30363d'
                  }}>
                    {t.symbol?.slice(0, 4)?.toUpperCase() || '?'}
                  </div>
                </Badge>
                <div style={{ color: '#e6edf3', fontSize: 12, marginTop: 6 }}>{t.name?.slice(0, 10)}</div>
              </Col>
            ))}
          </Row>
        </Card>
      )}

      <div style={{ color: '#484f58', fontSize: 11, textAlign: 'right', marginTop: 8 }}>
        数据更新: {data.timestamp} | 来源: CoinGecko, Alternative.me
      </div>
    </div>
  )
}

// ============ Tab2: 知识体系 ============

function KnowledgeSystem() {
  const [level, setLevel] = useState('beginner')
  const [data, setData] = useState<any>(null)
  const [glossary, setGlossary] = useState<any>(null)
  const [path, setPath] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [subTab, setSubTab] = useState('learn')

  const loadKnowledge = useCallback(async (lv: string) => {
    setLoading(true)
    try {
      const res = await cryptoMasterApi.getKnowledge(lv)
      setData(res.data)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [])

  const loadGlossary = useCallback(async () => {
    try {
      const res = await cryptoMasterApi.getGlossary()
      setGlossary(res.data)
    } catch (e) { console.error(e) }
  }, [])

  const loadPath = useCallback(async () => {
    try {
      const res = await cryptoMasterApi.getLearningPath()
      setPath(res.data)
    } catch (e) { console.error(e) }
  }, [])

  useEffect(() => { loadKnowledge(level) }, [level, loadKnowledge])
  useEffect(() => { loadGlossary(); loadPath() }, [loadGlossary, loadPath])

  const levelColors: Record<string, string> = {
    beginner: '#52c41a', intermediate: '#1890ff', advanced: '#faad14', master: '#f5222d'
  }
  const levelLabels: Record<string, string> = {
    beginner: '🔰 入门', intermediate: '📊 进阶', advanced: '🎯 高级', master: '👑 大师'
  }

  return (
    <div>
      <Tabs activeKey={subTab} onChange={setSubTab} style={{ marginBottom: 16 }}>
        <TabPane tab={<span><BookOutlined /> 知识课程</span>} key="learn" />
        <TabPane tab={<span><BulbOutlined /> 术语词典</span>} key="glossary" />
        <TabPane tab={<span><RocketOutlined /> 学习路径</span>} key="path" />
      </Tabs>

      {subTab === 'learn' && (
        <div>
          {/* 级别选择 */}
          <Space style={{ marginBottom: 16 }}>
            {Object.entries(levelLabels).map(([k, v]) => (
              <Button
                key={k}
                type={level === k ? 'primary' : 'default'}
                onClick={() => setLevel(k)}
                style={level === k ? { background: levelColors[k], borderColor: levelColors[k] } : {}}
              >
                {v}
              </Button>
            ))}
          </Space>

          {loading ? <Spin size="large" style={{ display: 'block', margin: '60px auto' }} /> : data ? (
            <div>
              <Card style={{ background: '#161b22', border: '1px solid #30363d', marginBottom: 16 }}>
                <Title level={3} style={{ color: '#e6edf3', margin: 0 }}>{data.title}</Title>
                <Text style={{ color: '#8b949e' }}>{data.subtitle}</Text>
              </Card>

              {data.sections?.map((sec: any, i: number) => (
                <Card
                  key={i}
                  style={{ background: '#161b22', border: '1px solid #30363d', marginBottom: 12 }}
                  title={<span style={{ color: '#e6edf3' }}>{sec.title}</span>}
                >
                  <Paragraph style={{ color: '#c9d1d9', fontSize: 15 }}>{sec.content}</Paragraph>

                  {sec.key_points && (
                    <div style={{ margin: '12px 0' }}>
                      <Text strong style={{ color: '#8b949e' }}>核心要点：</Text>
                      <ul style={{ color: '#c9d1d9', marginTop: 8 }}>
                        {sec.key_points.map((p: string, j: number) => (
                          <li key={j} style={{ marginBottom: 4 }}>{p}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {sec.analogy && (
                    <Alert type="info" showIcon icon={<BulbOutlined />}
                      message="类比理解" description={sec.analogy}
                      style={{ marginTop: 8, background: '#1c2128', border: '1px solid #30363d' }}
                    />
                  )}

                  {sec.warning && (
                    <Alert type="warning" showIcon icon={<WarningOutlined />}
                      message="重要警告" description={sec.warning}
                      style={{ marginTop: 8, background: '#1c2128', border: '1px solid #30363d' }}
                    />
                  )}

                  {sec.why_matters && (
                    <Alert type="success" showIcon
                      message="为什么重要" description={sec.why_matters}
                      style={{ marginTop: 8, background: '#1c2128', border: '1px solid #30363d' }}
                    />
                  )}

                  {sec.wisdom && (
                    <div style={{ marginTop: 12, padding: '12px 16px', background: '#1c2128', borderRadius: 8, borderLeft: '3px solid #faad14' }}>
                      <Text style={{ color: '#faad14', fontStyle: 'italic' }}>💡 {sec.wisdom}</Text>
                    </div>
                  )}

                  {sec.tools && (
                    <div style={{ marginTop: 8, color: '#8b949e', fontSize: 13 }}>
                      <Text strong style={{ color: '#8b949e' }}>🔧 推荐工具：</Text> {sec.tools}
                    </div>
                  )}

                  {sec.red_flags && (
                    <Alert type="error" showIcon icon={<WarningOutlined />}
                      message="🚩 危险信号" description={sec.red_flags}
                      style={{ marginTop: 8, background: '#1c2128', border: '1px solid #30363d' }}
                    />
                  )}

                  {sec.formula && (
                    <div style={{ marginTop: 8, padding: '8px 12px', background: '#1c2128', borderRadius: 6, fontFamily: 'monospace', color: '#58a6ff' }}>
                      📐 {sec.formula}
                    </div>
                  )}

                  {sec.discipline && (
                    <Alert type="warning" showIcon
                      message="纪律要求" description={sec.discipline}
                      style={{ marginTop: 8, background: '#1c2128', border: '1px solid #30363d' }}
                    />
                  )}

                  {sec.system && (
                    <div style={{ marginTop: 8, padding: '8px 12px', background: '#1c2128', borderRadius: 6, color: '#52c41a' }}>
                      ⚙️ {sec.system}
                    </div>
                  )}

                  {sec.reality && (
                    <Alert type="info" showIcon
                      message="现实情况" description={sec.reality}
                      style={{ marginTop: 8, background: '#1c2128', border: '1px solid #30363d' }}
                    />
                  )}

                  {sec.calculation && (
                    <div style={{ marginTop: 8, padding: '8px 12px', background: '#1c2128', borderRadius: 6, color: '#52c41a', fontFamily: 'monospace' }}>
                      🧮 {sec.calculation}
                    </div>
                  )}
                </Card>
              ))}
            </div>
          ) : <Alert type="error" message="加载失败" />}
        </div>
      )}

      {subTab === 'glossary' && glossary?.categories && (
        <div>
          <Alert
            type="info" showIcon
            message={`共收录 ${glossary.total_terms} 个术语，涵盖${glossary.categories.length}个类别`}
            style={{ marginBottom: 16, background: '#161b22', border: '1px solid #30363d' }}
          />
          <Collapse ghost>
            {glossary.categories.map((cat: any, i: number) => (
              <Panel header={<span style={{ color: '#e6edf3', fontWeight: 600 }}>{cat.name} ({cat.terms.length}个)</span>} key={i}>
                <Table
                  dataSource={cat.terms}
                  rowKey="term"
                  pagination={false}
                  size="small"
                  columns={[
                    { title: '术语', dataIndex: 'term', width: 100, render: (t: string) => <Text strong style={{ color: '#58a6ff' }}>{t}</Text> },
                    { title: '英文', dataIndex: 'en', width: 160, render: (t: string) => <Text style={{ color: '#8b949e' }}>{t}</Text> },
                    { title: '释义', dataIndex: 'def', render: (t: string) => <Text style={{ color: '#c9d1d9' }}>{t}</Text> },
                  ]}
                  style={{ background: 'transparent' }}
                />
              </Panel>
            ))}
          </Collapse>
        </div>
      )}

      {subTab === 'path' && path?.phases && (
        <div>
          <Alert
            type="success" showIcon icon={<RocketOutlined />}
            message="从零到大师的完整学习路线"
            description="每个阶段都有明确的目标和里程碑。不要跳级，扎实的基础是长期盈利的关键。"
            style={{ marginBottom: 16, background: '#161b22', border: '1px solid #30363d' }}
          />

          {path.phases.map((phase: any) => (
            <Card
              key={phase.phase}
              style={{ background: '#161b22', border: '1px solid #30363d', marginBottom: 12 }}
              title={
                <span style={{ color: '#e6edf3' }}>
                  <Tag color={['green', 'blue', 'gold', 'orange', 'red', 'purple'][phase.phase - 1]}>
                    阶段{phase.phase}
                  </Tag>
                  {phase.name}
                  <Tag style={{ marginLeft: 8 }}>{phase.risk_level}</Tag>
                </span>
              }
            >
              <Paragraph style={{ color: '#8b949e', marginBottom: 12 }}>🎯 目标：{phase.goal}</Paragraph>
              <ul style={{ color: '#c9d1d9' }}>
                {phase.tasks.map((t: string, i: number) => <li key={i} style={{ marginBottom: 4 }}>{t}</li>)}
              </ul>
              <div style={{ marginTop: 8, padding: '8px 12px', background: '#1c2128', borderRadius: 6 }}>
                <Text style={{ color: '#52c41a' }}>✅ 里程碑：{phase.milestone}</Text>
              </div>
            </Card>
          ))}

          {path.golden_rules && (
            <Card title={<span style={{ color: '#faad14' }}>⭐ 铁律（必须遵守）</span>}
              style={{ background: '#161b22', border: '1px solid #30363d' }}>
              <ol style={{ color: '#c9d1d9', fontSize: 15 }}>
                {path.golden_rules.map((r: string, i: number) => (
                  <li key={i} style={{ marginBottom: 8, fontWeight: 500 }}>{r}</li>
                ))}
              </ol>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}

// ============ Tab3: 策略工具箱 ============

function StrategyToolbox() {
  const [strategies, setStrategies] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  // DCA模拟器状态
  const [dcaCoin, setDcaCoin] = useState('bitcoin')
  const [dcaAmount, setDcaAmount] = useState(1000)
  const [dcaMonths, setDcaMonths] = useState(12)
  const [dcaResult, setDcaResult] = useState<any>(null)
  const [dcaLoading, setDcaLoading] = useState(false)

  // 仓位计算器状态
  const [capital, setCapital] = useState(100000)
  const [riskPerTrade, setRiskPerTrade] = useState(2)
  const [winRate, setWinRate] = useState(55)
  const [avgWin, setAvgWin] = useState(15)
  const [avgLoss, setAvgLoss] = useState(8)
  const [posResult, setPosResult] = useState<any>(null)
  const [posLoading, setPosLoading] = useState(false)

  const [subTab, setSubTab] = useState('overview')

  useEffect(() => {
    cryptoMasterApi.getStrategies().then(r => {
      setStrategies(r.data?.strategies || [])
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const runDca = async () => {
    setDcaLoading(true)
    try {
      const res = await cryptoMasterApi.runDcaSimulation({
        coin: dcaCoin, monthly_amount: dcaAmount, months: dcaMonths
      })
      setDcaResult(res.data)
    } catch (e) { console.error(e) }
    finally { setDcaLoading(false) }
  }

  const calcPosition = async () => {
    setPosLoading(true)
    try {
      const res = await cryptoMasterApi.calculatePosition({
        total_capital: capital,
        risk_per_trade: riskPerTrade / 100,
        win_rate: winRate / 100,
        avg_win: avgWin / 100,
        avg_loss: avgLoss / 100,
      })
      setPosResult(res.data)
    } catch (e) { console.error(e) }
    finally { setPosLoading(false) }
  }

  const difficultyColor: Record<string, string> = {
    '初级': 'green', '中级': 'blue', '高级': 'red'
  }

  return (
    <div>
      <Tabs activeKey={subTab} onChange={setSubTab} style={{ marginBottom: 16 }}>
        <TabPane tab={<span><ExperimentOutlined /> 策略总览</span>} key="overview" />
        <TabPane tab={<span><DollarOutlined /> 定投模拟器</span>} key="dca" />
        <TabPane tab={<span><SafetyOutlined /> 仓位计算器</span>} key="position" />
      </Tabs>

      {subTab === 'overview' && (
        loading ? <Spin size="large" style={{ display: 'block', margin: '60px auto' }} /> : (
          <Row gutter={[16, 16]}>
            {strategies.map((s: any) => (
              <Col span={12} key={s.id}>
                <Card
                  style={{ background: '#161b22', border: '1px solid #30363d', height: '100%' }}
                  title={
                    <span style={{ color: '#e6edf3' }}>
                      {s.name} <Tag color={difficultyColor[s.difficulty] || 'default'}>{s.difficulty}</Tag>
                    </span>
                  }
                >
                  <Paragraph style={{ color: '#c9d1d9' }}>{s.description}</Paragraph>
                  <Paragraph style={{ color: '#8b949e', fontSize: 13 }}><strong>原理：</strong>{s.how_it_works}</Paragraph>
                  <div style={{ marginBottom: 8 }}>
                    <Text strong style={{ color: '#52c41a' }}>✅ 优势：</Text>
                    <ul style={{ color: '#c9d1d9', margin: '4px 0', paddingLeft: 20 }}>
                      {s.advantages?.map((a: string, i: number) => <li key={i}>{a}</li>)}
                    </ul>
                  </div>
                  <div style={{ marginBottom: 8 }}>
                    <Text strong style={{ color: '#ff4d4f' }}>❌ 劣势：</Text>
                    <ul style={{ color: '#c9d1d9', margin: '4px 0', paddingLeft: 20 }}>
                      {s.disadvantages?.map((d: string, i: number) => <li key={i}>{d}</li>)}
                    </ul>
                  </div>
                  <div style={{ color: '#8b949e', fontSize: 13, marginBottom: 8 }}>
                    <strong>适合：</strong>{s.best_for}
                  </div>
                  <div style={{ padding: '8px 12px', background: '#1c2128', borderRadius: 6, color: '#58a6ff', fontSize: 13 }}>
                    📌 <strong>实例：</strong>{s.example}
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
        )
      )}

      {subTab === 'dca' && (
        <div>
          <Card title="💰 定投模拟器 (DCA Calculator)" style={{ background: '#161b22', border: '1px solid #30363d', marginBottom: 16 }}>
            <Paragraph style={{ color: '#8b949e' }}>
              定投是最适合新手的策略。定期定额买入，不管价格涨跌，长期下来能获得一个相对平均的成本。
            </Paragraph>
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={6}>
                <div style={{ color: '#8b949e', marginBottom: 4 }}>币种</div>
                <Select value={dcaCoin} onChange={setDcaCoin} style={{ width: '100%' }}
                  options={[
                    { value: 'bitcoin', label: 'Bitcoin (BTC)' },
                    { value: 'ethereum', label: 'Ethereum (ETH)' },
                    { value: 'solana', label: 'Solana (SOL)' },
                  ]}
                />
              </Col>
              <Col span={6}>
                <div style={{ color: '#8b949e', marginBottom: 4 }}>每月投入 (¥)</div>
                <InputNumber value={dcaAmount} onChange={v => setDcaAmount(v || 1000)} min={100} step={500} style={{ width: '100%' }} />
              </Col>
              <Col span={6}>
                <div style={{ color: '#8b949e', marginBottom: 4 }}>定投月数</div>
                <InputNumber value={dcaMonths} onChange={v => setDcaMonths(v || 12)} min={1} max={120} style={{ width: '100%' }} />
              </Col>
              <Col span={6}>
                <div style={{ color: '#8b949e', marginBottom: 4 }}>&nbsp;</div>
                <Button type="primary" icon={<ThunderboltOutlined />} onClick={runDca} loading={dcaLoading} block>
                  模拟计算
                </Button>
              </Col>
            </Row>

            {dcaResult && (
              <div>
                <Divider />
                <Row gutter={16} style={{ marginBottom: 16 }}>
                  <Col span={4}><Statistic title="总投入" value={`¥${dcaResult.total_invested?.toLocaleString()}`} valueStyle={{ color: '#e6edf3', fontSize: 18 }} /></Col>
                  <Col span={4}><Statistic title="最终价值" value={`¥${dcaResult.final_value?.toLocaleString()}`} valueStyle={{ color: '#52c41a', fontSize: 18 }} /></Col>
                  <Col span={4}><Statistic title="总收益率" value={`${dcaResult.total_return_pct}%`} valueStyle={{ color: dcaResult.total_return_pct >= 0 ? '#52c41a' : '#ff4d4f', fontSize: 18 }} /></Col>
                  <Col span={4}><Statistic title="累计币量" value={dcaResult.total_coins} valueStyle={{ color: '#e6edf3', fontSize: 18 }} /></Col>
                  <Col span={4}><Statistic title="平均成本" value={`$${dcaResult.avg_cost?.toLocaleString()}`} valueStyle={{ color: '#e6edf3', fontSize: 18 }} /></Col>
                  <Col span={4}><Statistic title="定投月数" value={dcaResult.months} valueStyle={{ color: '#e6edf3', fontSize: 18 }} /></Col>
                </Row>
                <Alert type="warning" showIcon message={dcaResult.note} style={{ background: '#1c2128', border: '1px solid #30363d' }} />
              </div>
            )}
          </Card>
        </div>
      )}

      {subTab === 'position' && (
        <div>
          <Card title="📐 仓位计算器 (Kelly + 固定风险法)" style={{ background: '#161b22', border: '1px solid #30363d', marginBottom: 16 }}>
            <Paragraph style={{ color: '#8b949e' }}>
              凯利公式帮你计算最优仓位比例。实际操作建议使用半凯利（Half-Kelly），降低波动性。
            </Paragraph>
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={4}>
                <div style={{ color: '#8b949e', marginBottom: 4 }}>总资金 (¥)</div>
                <InputNumber value={capital} onChange={v => setCapital(v || 100000)} min={1000} step={10000} style={{ width: '100%' }} />
              </Col>
              <Col span={4}>
                <div style={{ color: '#8b949e', marginBottom: 4 }}>单笔风险 (%)</div>
                <InputNumber value={riskPerTrade} onChange={v => setRiskPerTrade(v || 2)} min={0.5} max={10} step={0.5} style={{ width: '100%' }} />
              </Col>
              <Col span={4}>
                <div style={{ color: '#8b949e', marginBottom: 4 }}>胜率 (%)</div>
                <InputNumber value={winRate} onChange={v => setWinRate(v || 55)} min={10} max={90} style={{ width: '100%' }} />
              </Col>
              <Col span={4}>
                <div style={{ color: '#8b949e', marginBottom: 4 }}>平均盈利 (%)</div>
                <InputNumber value={avgWin} onChange={v => setAvgWin(v || 15)} min={1} max={100} style={{ width: '100%' }} />
              </Col>
              <Col span={4}>
                <div style={{ color: '#8b949e', marginBottom: 4 }}>平均亏损 (%)</div>
                <InputNumber value={avgLoss} onChange={v => setAvgLoss(v || 8)} min={1} max={50} style={{ width: '100%' }} />
              </Col>
              <Col span={4}>
                <div style={{ color: '#8b949e', marginBottom: 4 }}>&nbsp;</div>
                <Button type="primary" icon={<ThunderboltOutlined />} onClick={calcPosition} loading={posLoading} block>
                  计算仓位
                </Button>
              </Col>
            </Row>

            {posResult && (
              <div>
                <Divider />
                <Row gutter={16} style={{ marginBottom: 16 }}>
                  <Col span={4}><Statistic title="Kelly比例" value={`${posResult.kelly_fraction}%`} valueStyle={{ color: '#faad14', fontSize: 18 }} /></Col>
                  <Col span={4}><Statistic title="半Kelly(Half)" value={`${posResult.half_kelly_fraction}%`} valueStyle={{ color: '#52c41a', fontSize: 18 }} /></Col>
                  <Col span={4}><Statistic title="建议仓位" value={`¥${posResult.recommended_position?.toLocaleString()}`} valueStyle={{ color: '#e6edf3', fontSize: 18 }} /></Col>
                  <Col span={4}><Statistic title="单笔最大亏损" value={`¥${posResult.max_loss_per_trade?.toLocaleString()}`} valueStyle={{ color: '#ff4d4f', fontSize: 18 }} /></Col>
                  <Col span={4}><Statistic title="期望收益/笔" value={`${posResult.expected_return_per_trade}%`} valueStyle={{ color: posResult.expected_return_per_trade >= 0 ? '#52c41a' : '#ff4d4f', fontSize: 18 }} /></Col>
                  <Col span={4}><Statistic title="盈亏比" value={posResult.risk_reward_ratio} valueStyle={{ color: '#1890ff', fontSize: 18 }} /></Col>
                </Row>
                <Alert type="info" showIcon message="计算结果解读" description={posResult.interpretation}
                  style={{ background: '#1c2128', border: '1px solid #30363d' }} />
                <div style={{ marginTop: 12, padding: '8px 12px', background: '#1c2128', borderRadius: 6, fontFamily: 'monospace', color: '#58a6ff' }}>
                  📐 {posResult.formula?.kelly}，其中 {posResult.formula?.where}
                </div>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}

// ============ Tab4: 风险管理 ============

function RiskManagement() {
  const [mistakes, setMistakes] = useState<any>(null)
  const [security, setSecurity] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      cryptoMasterApi.getCommonMistakes(),
      cryptoMasterApi.getSecurityGuide(),
    ]).then(([m, s]) => {
      setMistakes(m.data)
      setSecurity(s.data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />

  return (
    <div>
      <Alert
        type="error" showIcon icon={<WarningOutlined />}
        message="⚠️ 风险管理是投资中最重要的技能"
        description="在加密市场，风险管理比选币更重要。学会保护本金，才能在市场中长期生存。"
        style={{ marginBottom: 16, background: '#161b22', border: '1px solid #30363d' }}
      />

      {/* 常见亏损原因 */}
      <Card title={<><FallOutlined /> 常见亏损原因 & 解决方案</>}
        style={{ background: '#161b22', border: '1px solid #30363d', marginBottom: 16 }}>
        {mistakes?.mistakes?.map((m: any, i: number) => (
          <Card key={i} size="small" style={{ background: '#1c2128', border: '1px solid #30363d', marginBottom: 8 }}>
            <Row gutter={16} align="middle">
              <Col span={16}>
                <div style={{ color: '#e6edf3', fontSize: 15, fontWeight: 600, marginBottom: 4 }}>
                  {i + 1}. {m.name} <span style={{ fontSize: 12 }}>{m.frequency}</span>
                </div>
                <div style={{ color: '#8b949e', fontSize: 13, marginBottom: 6 }}>{m.description}</div>
                <div style={{ color: '#52c41a', fontSize: 13 }}>✅ 解决：{m.solution}</div>
              </Col>
              <Col span={8}>
                <div style={{ padding: '8px 12px', background: '#161b22', borderRadius: 6, borderLeft: '3px solid #ff4d4f' }}>
                  <Text style={{ color: '#ff4d4f', fontSize: 12 }}>📌 真实案例：</Text>
                  <div style={{ color: '#c9d1d9', fontSize: 12, marginTop: 4 }}>{m.example}</div>
                </div>
              </Col>
            </Row>
          </Card>
        ))}
      </Card>

      {/* 安全指南 */}
      {security && (
        <Row gutter={16}>
          {Object.entries(security).map(([key, section]: [string, any]) => (
            <Col span={8} key={key}>
              <Card
                title={<span style={{ color: '#e6edf3' }}>
                  {key === 'wallet_security' ? '🔐' : key === 'exchange_security' ? '🏦' : '🛡️'} {section.title}
                </span>}
                style={{ background: '#161b22', border: '1px solid #30363d', height: '100%' }}
              >
                <ul style={{ color: '#c9d1d9', paddingLeft: 16 }}>
                  {section.rules.map((r: string, i: number) => (
                    <li key={i} style={{ marginBottom: 8, fontSize: 13 }}>{r}</li>
                  ))}
                </ul>
              </Card>
            </Col>
          ))}
        </Row>
      )}
    </div>
  )
}

// ============ Tab5: DeFi指南 ============

function DeFiGuide() {
  const [defi, setDefi] = useState<any>(null)
  const [airdrop, setAirdrop] = useState<any>(null)
  const [tvl, setTvl] = useState<any>(null)
  const [payment, setPayment] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [subTab, setSubTab] = useState('payment')

  useEffect(() => {
    Promise.all([
      cryptoMasterApi.getDefiGuide(),
      cryptoMasterApi.getAirdropGuide(),
      cryptoMasterApi.getDefiTvl(),
      cryptoMasterApi.getPaymentTools(),
    ]).then(([d, a, t, p]) => {
      setDefi(d.data)
      setAirdrop(a.data)
      setTvl(t.data)
      setPayment(p.data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />

  return (
    <div>
      <Tabs activeKey={subTab} onChange={setSubTab} style={{ marginBottom: 16 }}>
        <TabPane tab={<span><DollarOutlined /> 出入金工具</span>} key="payment" />
        <TabPane tab={<span><BankOutlined /> DeFi实操</span>} key="defi" />
        <TabPane tab={<span><RocketOutlined /> 空投指南</span>} key="airdrop" />
        <TabPane tab={<span><RiseOutlined /> 链上数据</span>} key="onchain" />
      </Tabs>

      {/* 出入金工具 */}
      {subTab === 'payment' && payment && (
        <div>
          <Alert type="info" showIcon icon={<DollarOutlined />}
            message="加密货币出入金工具"
            description={payment.intro}
            style={{ marginBottom: 16, background: '#161b22', border: '1px solid #30363d' }}
          />

          <div style={{ marginBottom: 16 }}>
            <Title level={5} style={{ color: '#e6edf3', marginBottom: 12 }}>💳 加密支付卡</Title>
            <Row gutter={[16, 16]}>
              {payment.tools?.map((tool: any, i: number) => (
                <Col span={8} key={i}>
                  <Card style={{ background: '#161b22', border: i === 0 ? '1px solid #52c41a' : '1px solid #30363d', height: '100%' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                      <span style={{ fontSize: 20 }}>💳</span>
                      <div>
                        <div style={{ color: '#e6edf3', fontWeight: 700, fontSize: 16 }}>{tool.name}</div>
                        <div style={{ color: '#8b949e', fontSize: 12 }}>{tool.type}</div>
                      </div>
                      {i === 0 && <Tag color="green" style={{ marginLeft: 'auto' }}>推荐</Tag>}
                    </div>
                    <div style={{ color: '#52c41a', fontSize: 13, marginBottom: 8, fontWeight: 600 }}>✨ {tool.highlight}</div>
                    <ul style={{ color: '#c9d1d9', fontSize: 13, paddingLeft: 16, marginBottom: 12 }}>
                      {tool.features?.map((f: string, j: number) => <li key={j} style={{ marginBottom: 3 }}>{f}</li>)}
                    </ul>
                    {tool.fees && (
                      <div style={{ background: '#1c2128', borderRadius: 6, padding: '8px 12px', marginBottom: 8 }}>
                        <div style={{ color: '#8b949e', fontSize: 12, marginBottom: 4 }}>费率明细：</div>
                        {Object.entries(tool.fees).map(([k, v]: [string, any]) => (
                          <div key={k} style={{ color: '#c9d1d9', fontSize: 12, display: 'flex', justifyContent: 'space-between' }}>
                            <span>{k}:</span><span style={{ color: v === '免费' ? '#52c41a' : '#faad14' }}>{v}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    <div style={{ color: '#8b949e', fontSize: 12 }}>
                      适合：{tool.best_for}
                    </div>
                  </Card>
                </Col>
              ))}
            </Row>
          </div>

          {payment.fiat_channels && (
            <div style={{ marginBottom: 16 }}>
              <Title level={5} style={{ color: '#e6edf3', marginBottom: 12 }}>🏦 法币入金渠道</Title>
              <Row gutter={[16, 16]}>
                {payment.fiat_channels.map((ch: any, i: number) => (
                  <Col span={12} key={i}>
                    <Card style={{ background: '#161b22', border: '1px solid #30363d' }}>
                      <div style={{ color: '#e6edf3', fontWeight: 600, fontSize: 15, marginBottom: 8 }}>{ch.name}</div>
                      <div style={{ color: '#8b949e', fontSize: 13, marginBottom: 8 }}>{ch.description}</div>
                      <div style={{ marginBottom: 8 }}>
                        <Text strong style={{ color: '#8b949e', fontSize: 12 }}>平台：</Text>
                        <Space style={{ marginLeft: 4 }}>
                          {ch.platforms?.map((p: string, j: number) => <Tag key={j}>{p}</Tag>)}
                        </Space>
                      </div>
                      <div style={{ marginBottom: 6 }}>
                        <Text strong style={{ color: '#52c41a', fontSize: 12 }}>✅ 优势：</Text>
                        <ul style={{ color: '#c9d1d9', fontSize: 12, margin: '4px 0', paddingLeft: 16 }}>
                          {ch.advantages?.map((a: string, j: number) => <li key={j}>{a}</li>)}
                        </ul>
                      </div>
                      <div style={{ marginBottom: 6 }}>
                        <Text strong style={{ color: '#ff4d4f', fontSize: 12 }}>⚠️ 风险：</Text>
                        <ul style={{ color: '#c9d1d9', fontSize: 12, margin: '4px 0', paddingLeft: 16 }}>
                          {ch.risks?.map((r: string, j: number) => <li key={j}>{r}</li>)}
                        </ul>
                      </div>
                      <div style={{ padding: '6px 10px', background: '#1c2128', borderRadius: 4, color: '#faad14', fontSize: 12 }}>
                        💡 {ch.tips}
                      </div>
                    </Card>
                  </Col>
                ))}
              </Row>
            </div>
          )}

          {payment.safety_tips && (
            <Card title={<span style={{ color: '#ff4d4f' }}>🛡️ 出入金安全须知</span>}
              style={{ background: '#161b22', border: '1px solid #30363d' }}>
              <ul style={{ color: '#c9d1d9' }}>
                {payment.safety_tips.map((t: string, i: number) => (
                  <li key={i} style={{ marginBottom: 6, fontSize: 13 }}>{t}</li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}

      {subTab === 'defi' && defi?.levels && (
        <div>
          {defi.levels.map((level: any, i: number) => (
            <Card key={i} style={{ background: '#161b22', border: '1px solid #30363d', marginBottom: 12 }}
              title={<span style={{ color: '#e6edf3' }}>
                <Tag color={['green', 'blue', 'red'][i]}>{level.level}</Tag> {level.name}
              </span>}
            >
              <Row gutter={[12, 12]}>
                {level.protocols.map((p: any, j: number) => (
                  <Col span={12} key={j}>
                    <Card size="small" style={{ background: '#1c2128', border: '1px solid #30363d' }}>
                      <div style={{ color: '#e6edf3', fontWeight: 600, marginBottom: 4 }}>
                        {p.name} <Tag>{p.type}</Tag> <Tag>{p.risk}</Tag>
                      </div>
                      <div style={{ color: '#8b949e', fontSize: 12, marginBottom: 4 }}>链：{p.chain}</div>
                      <div style={{ color: '#58a6ff', fontSize: 13 }}>🎯 {p.action}</div>
                    </Card>
                  </Col>
                ))}
              </Row>
              <div style={{ marginTop: 8, padding: '8px 12px', background: '#1c2128', borderRadius: 6, color: '#faad14', fontSize: 13 }}>
                💡 {level.tips}
              </div>
            </Card>
          ))}

          {defi.gas_optimization && (
            <Card title={<span style={{ color: '#e6edf3' }}>⛽ {defi.gas_optimization.title}</span>}
              style={{ background: '#161b22', border: '1px solid #30363d' }}>
              <ul style={{ color: '#c9d1d9' }}>
                {defi.gas_optimization.tips.map((t: string, i: number) => <li key={i} style={{ marginBottom: 6 }}>{t}</li>)}
              </ul>
            </Card>
          )}
        </div>
      )}

      {subTab === 'airdrop' && airdrop && (
        <div>
          <Alert type="info" showIcon icon={<RocketOutlined />}
            message="空投猎人指南"
            description={airdrop.intro}
            style={{ marginBottom: 16, background: '#161b22', border: '1px solid #30363d' }}
          />

          <Card title="空投运作原理" style={{ background: '#161b22', border: '1px solid #30363d', marginBottom: 12 }}>
            <ol style={{ color: '#c9d1d9' }}>
              {airdrop.how_it_works?.map((w: string, i: number) => <li key={i} style={{ marginBottom: 6 }}>{w}</li>)}
            </ol>
          </Card>

          <Card title="空投策略" style={{ background: '#161b22', border: '1px solid #30363d', marginBottom: 12 }}>
            <Row gutter={[12, 12]}>
              {airdrop.strategies?.map((s: any, i: number) => (
                <Col span={12} key={i}>
                  <Card size="small" style={{ background: '#1c2128', border: '1px solid #30363d' }}>
                    <div style={{ color: '#e6edf3', fontWeight: 600, marginBottom: 4 }}>{s.name}</div>
                    <div style={{ color: '#8b949e', fontSize: 13, marginBottom: 6 }}>{s.description}</div>
                    <Space>
                      <Tag>精力: {s.effort}</Tag>
                      <Tag color="green">收益潜力: {s.potential}</Tag>
                    </Space>
                  </Card>
                </Col>
              ))}
            </Row>
          </Card>

          <Card title="⚠️ 风险警告" style={{ background: '#161b22', border: '1px solid #30363d', marginBottom: 12 }}>
            <ul style={{ color: '#ff4d4f' }}>
              {airdrop.risk_warning?.map((w: string, i: number) => <li key={i} style={{ marginBottom: 6 }}>{w}</li>)}
            </ul>
          </Card>

          {airdrop.tools && (
            <Card title="🔧 推荐工具" style={{ background: '#161b22', border: '1px solid #30363d' }}>
              {airdrop.tools.map((t: any, i: number) => (
                <div key={i} style={{ marginBottom: 8 }}>
                  <Text strong style={{ color: '#58a6ff' }}>{t.name}</Text>
                  <Text style={{ color: '#8b949e', marginLeft: 8 }}>— {t.purpose}</Text>
                </div>
              ))}
            </Card>
          )}
        </div>
      )}

      {subTab === 'onchain' && tvl && (
        <div>
          <Card title="🔗 DeFi总锁仓量 (TVL)" style={{ background: '#161b22', border: '1px solid #30363d', marginBottom: 12 }}>
            <Row gutter={16}>
              <Col span={8}>
                <Statistic title="总TVL" value={fmt(tvl.total_tvl)} valueStyle={{ color: '#52c41a', fontSize: 24 }} />
              </Col>
              <Col span={8}>
                <Statistic title="公链数量" value={tvl.chain_count} valueStyle={{ color: '#e6edf3', fontSize: 24 }} />
              </Col>
            </Row>
          </Card>

          <Card title="📊 Top 10 公链 TVL" style={{ background: '#161b22', border: '1px solid #30363d' }}>
            <Table
              dataSource={tvl.chains?.slice(0, 10)}
              rowKey="name"
              pagination={false}
              size="small"
              columns={[
                { title: '排名', render: (_: any, __: any, i: number) => i + 1, width: 60 },
                { title: '公链', dataIndex: 'name', render: (n: string) => <Text strong style={{ color: '#e6edf3' }}>{n}</Text> },
                { title: 'TVL', dataIndex: 'tvl', render: (v: number) => <Text style={{ color: '#52c41a' }}>{fmt(v)}</Text> },
                { title: '代币', dataIndex: 'tokenSymbol', render: (t: string) => <Tag>{t || 'N/A'}</Tag> },
                {
                  title: '占比', render: (_: any, r: any) => {
                    const pct = tvl.total_tvl > 0 ? (r.tvl / tvl.total_tvl * 100) : 0
                    return <Progress percent={Math.min(pct, 100)} size="small" format={() => `${pct.toFixed(1)}%`} strokeColor="#58a6ff" />
                  }
                },
              ]}
              style={{ background: 'transparent' }}
            />
          </Card>
        </div>
      )}
    </div>
  )
}

// ============ Tab6: 情报搜集 ============

function IntelCollector() {
  const [items, setItems] = useState<any[]>([])
  const [trending, setTrending] = useState<any>(null)
  const [sources, setSources] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [crawling, setCrawling] = useState(false)
  const [filter, setFilter] = useState<string>('all')
  const [impactFilter, setImpactFilter] = useState<string>('all')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [latest, trd, src] = await Promise.all([
        cryptoMasterApi.getIntelLatest({ limit: 100 }),
        cryptoMasterApi.getIntelTrending(),
        cryptoMasterApi.getIntelSources(),
      ])
      setItems(latest.data?.items || [])
      setTrending(trd.data)
      setSources(src.data)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleCrawl = async () => {
    setCrawling(true)
    try {
      await cryptoMasterApi.triggerCrawl()
      await load()
    } catch (e) { console.error(e) }
    finally { setCrawling(false) }
  }

  const impactColor: Record<string, string> = { high: '#ff4d4f', medium: '#faad14', low: '#8b949e' }
  const impactLabel: Record<string, string> = { high: '🔴 高', medium: '🟡 中', low: '⚪ 低' }
  const categoryLabel: Record<string, string> = {
    news: '📰 新闻', btc: '₿ BTC', defi: '🏦 DeFi', research: '📊 研究', onchain: '🔗 链上'
  }

  const filtered = items.filter(i => {
    if (filter !== 'all' && i.source_category !== filter) return false
    if (impactFilter !== 'all' && i.impact !== impactFilter) return false
    return true
  })

  return (
    <div>
      {/* 头部状态栏 */}
      <Card style={{ background: '#161b22', border: '1px solid #30363d', marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col span={6}>
            <Statistic title="情报总数" value={sources?.total_items || 0} valueStyle={{ color: '#e6edf3' }} />
          </Col>
          <Col span={6}>
            <Statistic title="数据源" value={Object.keys(sources?.sources || {}).length} suffix="个" valueStyle={{ color: '#58a6ff' }} />
          </Col>
          <Col span={6}>
            <div style={{ color: '#8b949e', fontSize: 13 }}>上次搜集</div>
            <div style={{ color: '#c9d1d9', fontSize: 13 }}>
              {sources?.last_crawl ? new Date(sources.last_crawl).toLocaleString('zh-CN') : '尚未搜集'}
            </div>
          </Col>
          <Col span={6}>
            <Button type="primary" icon={<ReloadOutlined />} onClick={handleCrawl} loading={crawling} block>
              立即搜集
            </Button>
          </Col>
        </Row>
      </Card>

      {/* 热门话题 */}
      {trending?.trending?.length > 0 && (
        <Card title={<><FireOutlined /> 热门话题</>} style={{ background: '#161b22', border: '1px solid #30363d', marginBottom: 16 }}>
          <Space wrap>
            {trending.trending.slice(0, 12).map((t: any, i: number) => (
              <Tag key={i} color={i < 3 ? 'red' : i < 6 ? 'orange' : 'default'} style={{ cursor: 'pointer' }}
                onClick={() => setFilter('all')}>
                {t.topic} ({t.count})
              </Tag>
            ))}
          </Space>
        </Card>
      )}

      {/* 过滤器 */}
      <Space style={{ marginBottom: 12 }} wrap>
        {[{ k: 'all', l: '全部' }, { k: 'news', l: '📰 新闻' }, { k: 'btc', l: '₿ BTC' }, { k: 'defi', l: '🏦 DeFi' }, { k: 'research', l: '📊 研究' }, { k: 'onchain', l: '🔗 链上' }].map(f => (
          <Button key={f.k} size="small" type={filter === f.k ? 'primary' : 'default'} onClick={() => setFilter(f.k)}>{f.l}</Button>
        ))}
        <span style={{ color: '#30363d', margin: '0 4px' }}>|</span>
        {[{ k: 'all', l: '全部影响力' }, { k: 'high', l: '🔴 高' }, { k: 'medium', l: '🟡 中' }, { k: 'low', l: '⚪ 低' }].map(f => (
          <Button key={f.k} size="small" type={impactFilter === f.k ? 'primary' : 'default'} onClick={() => setImpactFilter(f.k)}>{f.l}</Button>
        ))}
      </Space>

      {/* 情报列表 */}
      {loading ? <Spin size="large" style={{ display: 'block', margin: '60px auto' }} /> : (
        <div>
          {filtered.length === 0 ? (
            <Alert type="info" showIcon message="暂无情报" description="点击'立即搜集'按钮开始从互联网抓取币圈情报。首次搜集需要等待几分钟。" />
          ) : (
            filtered.slice(0, 80).map((item, i) => (
              <Card key={item.hash || i} size="small"
                style={{ background: '#161b22', border: '1px solid #30363d', marginBottom: 8 }}>
                <Row gutter={12} align="middle">
                  <Col span={1}>
                    <div style={{
                      width: 8, height: 8, borderRadius: '50%',
                      background: impactColor[item.impact] || '#30363d'
                    }} />
                  </Col>
                  <Col span={14}>
                    <a href={item.url} target="_blank" rel="noopener noreferrer"
                      style={{ color: '#58a6ff', fontSize: 14, fontWeight: 500, textDecoration: 'none' }}>
                      {item.title}
                    </a>
                    {item.summary && (
                      <div style={{ color: '#8b949e', fontSize: 12, marginTop: 2, lineHeight: 1.4 }}>
                        {item.summary.slice(0, 120)}{item.summary.length > 120 ? '...' : ''}
                      </div>
                    )}
                  </Col>
                  <Col span={3}>
                    <Tag>{item.source}</Tag>
                  </Col>
                  <Col span={3}>
                    <Tag color={item.source_lang === 'zh' ? 'blue' : 'default'}>
                      {item.source_lang === 'zh' ? '中文' : 'EN'}
                    </Tag>
                    <Tag>{categoryLabel[item.source_category] || item.source_category}</Tag>
                  </Col>
                  <Col span={3} style={{ textAlign: 'right' }}>
                    <div style={{ color: impactColor[item.impact], fontSize: 12 }}>
                      {impactLabel[item.impact] || item.impact}
                    </div>
                    <div style={{ color: '#484f58', fontSize: 11 }}>
                      {item.collected_at ? new Date(item.collected_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''}
                    </div>
                  </Col>
                </Row>
                {item.tags?.length > 0 && (
                  <div style={{ marginTop: 4, marginLeft: 20 }}>
                    {item.tags.slice(0, 5).map((tag: string, j: number) => (
                      <Tag key={j} style={{ fontSize: 11, padding: '0 4px' }}>{tag}</Tag>
                    ))}
                  </div>
                )}
              </Card>
            ))
          )}
        </div>
      )}

      {/* 数据源状态 */}
      {sources?.sources && (
        <Collapse ghost style={{ marginTop: 16 }}>
          <Panel header={<span style={{ color: '#8b949e' }}>📡 数据源状态 ({Object.keys(sources.sources).length}个)</span>} key="sources">
            <Row gutter={[8, 8]}>
              {Object.entries(sources.sources).map(([name, status]: [string, any]) => (
                <Col span={6} key={name}>
                  <div style={{
                    padding: '6px 10px', background: '#1c2128', borderRadius: 4,
                    borderLeft: `3px solid ${status.status === 'ok' ? '#52c41a' : '#ff4d4f'}`,
                    fontSize: 12
                  }}>
                    <div style={{ color: '#e6edf3' }}>{name}</div>
                    <div style={{ color: '#8b949e' }}>
                      {status.status === 'ok' ? `✅ ${status.fetched}条` : `❌ ${status.error?.slice(0, 30)}`}
                    </div>
                  </div>
                </Col>
              ))}
            </Row>
          </Panel>
        </Collapse>
      )}
    </div>
  )
}

// ============ Tab7: 实战检查清单 ============

function TradingPractice() {
  const [checklist, setChecklist] = useState<any>(null)
  const [wisdom, setWisdom] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      cryptoMasterApi.getTradingChecklist(),
      cryptoMasterApi.getMasterWisdom(),
    ]).then(([c, w]) => {
      setChecklist(c.data)
      setWisdom(w.data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />

  return (
    <div>
      {/* 交易检查清单 */}
      {checklist && (
        <div style={{ marginBottom: 24 }}>
          <Title level={4} style={{ color: '#e6edf3' }}>📋 交易检查清单</Title>
          <Row gutter={16}>
            {Object.entries(checklist).map(([key, phase]: [string, any]) => (
              <Col span={8} key={key}>
                <Card title={<span style={{ color: '#e6edf3' }}>{phase.title}</span>}
                  style={{ background: '#161b22', border: '1px solid #30363d', height: '100%' }}>
                  {phase.items.map((item: any, i: number) => (
                    <div key={i} style={{
                      padding: '8px 12px', marginBottom: 6, borderRadius: 6,
                      background: '#1c2128', borderLeft: `3px solid ${item.critical ? '#ff4d4f' : '#30363d'}`
                    }}>
                      <div style={{ color: '#e6edf3', fontSize: 13, fontWeight: 500 }}>
                        {item.critical && <span style={{ color: '#ff4d4f', marginRight: 4 }}>⚠️</span>}
                        {item.check}
                      </div>
                      <div style={{ color: '#8b949e', fontSize: 12 }}>{item.detail}</div>
                      {item.time && <Tag style={{ marginTop: 4 }} color="blue">{item.time}</Tag>}
                      {item.frequency && <Tag style={{ marginTop: 4 }} color="green">{item.frequency}</Tag>}
                    </div>
                  ))}
                </Card>
              </Col>
            ))}
          </Row>
        </div>
      )}

      {/* 大师语录 */}
      {wisdom?.wisdom && (
        <div>
          <Title level={4} style={{ color: '#e6edf3' }}>👑 大师智慧</Title>
          <Row gutter={[16, 16]}>
            {wisdom.wisdom.map((w: any, i: number) => (
              <Col span={12} key={i}>
                <Card style={{ background: '#161b22', border: '1px solid #30363d', height: '100%' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                    <div style={{
                      width: 48, height: 48, borderRadius: '50%', background: '#21262d',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20
                    }}>
                      <CrownOutlined style={{ color: '#faad14' }} />
                    </div>
                    <div>
                      <div style={{ color: '#e6edf3', fontWeight: 600 }}>{w.person}</div>
                      <div style={{ color: '#8b949e', fontSize: 12 }}>{w.role}</div>
                    </div>
                  </div>
                  {w.quotes.map((q: string, j: number) => (
                    <div key={j} style={{
                      padding: '8px 12px', marginBottom: 8, background: '#1c2128', borderRadius: 6,
                      borderLeft: '3px solid #faad14', fontStyle: 'italic', color: '#c9d1d9', fontSize: 13
                    }}>
                      "{q}"
                    </div>
                  ))}
                  <div style={{ color: '#58a6ff', fontSize: 13, marginTop: 8 }}>💡 {w.lesson}</div>
                </Card>
              </Col>
            ))}
          </Row>
        </div>
      )}
    </div>
  )
}

// ============ 主页面 ============

export default function CryptoMasterPage() {
  return (
    <div style={{ padding: '0 4px' }}>
      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ fontSize: 28 }}>₿</span>
        <div>
          <h2 style={{ color: '#e6edf3', margin: 0, fontSize: 22 }}>
            币圈大师 <Tag color="gold">从零到专家</Tag>
          </h2>
          <div style={{ color: '#8b949e', fontSize: 13 }}>
            完整的加密货币学习+实战体系 · 市场数据 · 知识课程 · 策略工具 · 风险管理 · DeFi指南
          </div>
        </div>
      </div>

      <Tabs defaultActiveKey="market" type="card" size="large">
        <TabPane tab={<span><RiseOutlined /> 市场全景</span>} key="market">
          <MarketOverview />
        </TabPane>
        <TabPane tab={<span><ThunderboltOutlined /> 情报搜集</span>} key="intel">
          <IntelCollector />
        </TabPane>
        <TabPane tab={<span><BookOutlined /> 知识体系</span>} key="knowledge">
          <KnowledgeSystem />
        </TabPane>
        <TabPane tab={<span><ExperimentOutlined /> 策略工具箱</span>} key="strategy">
          <StrategyToolbox />
        </TabPane>
        <TabPane tab={<span><SafetyOutlined /> 风险管理</span>} key="risk">
          <RiskManagement />
        </TabPane>
        <TabPane tab={<span><BankOutlined /> DeFi指南</span>} key="defi">
          <DeFiGuide />
        </TabPane>
        <TabPane tab={<span><CheckCircleOutlined /> 实战清单</span>} key="practice">
          <TradingPractice />
        </TabPane>
      </Tabs>
    </div>
  )
}
