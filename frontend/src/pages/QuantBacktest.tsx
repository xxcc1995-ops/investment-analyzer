import { useState, useEffect, useCallback } from 'react'
import { Card, Select, Button, Table, Statistic, Row, Col, Spin, message, Tabs, Tag, Space, InputNumber, Switch, Tooltip } from 'antd'
import {
  PlayCircleOutlined,
  ExperimentOutlined,
  TrophyOutlined,
  WarningOutlined,
  InfoCircleOutlined,
  ThunderboltOutlined,
  FundOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import apiClient from '../services/api/client'

const { Option } = Select
const { TabPane } = Tabs

interface StrategyInfo {
  name: string
  display_name: string
  description: string
  version: string
  params: Record<string, any>
  inspiration: string
}

interface BacktestResult {
  strategy: string
  params: Record<string, any>
  start_date: string
  end_date: string
  walk_forward: boolean
  metrics: {
    total_return?: number
    annual_return?: number
    volatility?: number
    max_drawdown?: number
    sharpe_ratio?: number
    sortino_ratio?: number
    calmar_ratio?: number
    alpha?: number
    beta?: number
    monthly_win_rate?: number
    profit_loss_ratio?: number
    benchmark_total_return?: number
    excess_return?: number
    n_folds?: number
    fold_returns?: number[]
    param_stability?: Record<string, number>
    yearly_returns?: Record<string, number>
  }
  equity_curve: number[]
  final_value: number
  trade_log?: any[]
  walk_forward_report?: string
  fold_details?: any[]
  strategy_contributions?: Record<string, any>
  weights?: Record<string, number>
  correlation_matrix?: number[][]
  high_correlation_warning?: boolean
}

export default function QuantBacktest() {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([])
  const [selectedStrategy, setSelectedStrategy] = useState('multi_factor')
  const [startDate, setStartDate] = useState('2020-01-01')
  const [endDate, setEndDate] = useState('2025-12-31')
  const [initialCapital, setInitialCapital] = useState(1000000)
  const [topN, setTopN] = useState(20)
  const [walkForward, setWalkForward] = useState(true)
  const [rebalanceFreq, setRebalanceFreq] = useState('monthly')
  const [benchmark, setBenchmark] = useState('000300')

  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<BacktestResult | null>(null)

  // 加载策略列表
  useEffect(() => {
    apiClient.get('/quant/strategies')
      .then(res => setStrategies(res.data.strategies || []))
      .catch(() => message.error('加载策略列表失败'))
  }, [])

  // 运行回测
  const runBacktest = useCallback(async () => {
    setLoading(true)
    setResult(null)
    try {
      const res = await apiClient.post('/quant/backtest', {
        strategy: selectedStrategy,
        start_date: startDate,
        end_date: endDate,
        initial_capital: initialCapital,
        top_n: topN,
        walk_forward: walkForward,
        rebalance_freq: rebalanceFreq,
        benchmark,
      })
      setResult(res.data)
      message.success('回测完成')
    } catch (err: any) {
      message.error(err.response?.data?.detail || '回测失败')
    } finally {
      setLoading(false)
    }
  }, [selectedStrategy, startDate, endDate, initialCapital, topN, walkForward, rebalanceFreq, benchmark])

  // 净值曲线配置
  const getEquityChartOption = () => {
    if (!result?.equity_curve?.length) return {}
    const data = result.equity_curve
    const xData = data.map((_, i) => {
      const d = new Date(result.start_date)
      d.setDate(d.getDate() + Math.floor(i * (data.length > 500 ? 1.5 : 1)))
      return d.toISOString().slice(0, 10)
    })

    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['策略净值'], top: 10 },
      grid: { left: 60, right: 30, top: 50, bottom: 30 },
      xAxis: { type: 'category', data: xData, show: false },
      yAxis: {
        type: 'value',
        name: '净值',
        axisLabel: { formatter: (v: number) => (v / initialCapital).toFixed(2) },
      },
      series: [{
        name: '策略净值',
        type: 'line',
        data: data,
        smooth: true,
        lineStyle: { width: 2, color: '#1890ff' },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(24,144,255,0.3)' },
              { offset: 1, color: 'rgba(24,144,255,0.02)' },
            ],
          },
        },
        showSymbol: false,
      }],
    }
  }

  // 回撤曲线
  const getDrawdownChartOption = () => {
    if (!result?.equity_curve?.length) return {}
    const data = result.equity_curve
    const peak = data.reduce((acc: number[], v) => {
      acc.push(acc.length ? Math.max(acc[acc.length - 1], v) : v)
      return acc
    }, [])
    const drawdown = data.map((v, i) => ((v - peak[i]) / peak[i]) * 100)

    return {
      tooltip: { trigger: 'axis', formatter: (p: any) => `${p[0]?.axisValue}<br/>回撤: ${p[0]?.data?.toFixed(2)}%` },
      grid: { left: 60, right: 30, top: 20, bottom: 30 },
      xAxis: { type: 'category', data: data.map((_, i) => i), show: false },
      yAxis: { type: 'value', name: '回撤 %', axisLabel: { formatter: '{value}%' } },
      series: [{
        type: 'line',
        data: drawdown,
        smooth: true,
        lineStyle: { width: 1.5, color: '#ff4d4f' },
        areaStyle: { color: 'rgba(255,77,79,0.15)' },
        showSymbol: false,
      }],
    }
  }

  // 分年度收益柱状图
  const getYearlyChartOption = () => {
    const yr = result?.metrics?.yearly_returns
    if (!yr || Object.keys(yr).length === 0) return {}
    const years = Object.keys(yr).sort()
    const values = years.map(y => (yr[y] * 100).toFixed(1))

    return {
      tooltip: { trigger: 'axis', formatter: (p: any) => `${p[0]?.name}年: ${p[0]?.data}%` },
      grid: { left: 50, right: 20, top: 20, bottom: 30 },
      xAxis: { type: 'category', data: years },
      yAxis: { type: 'value', name: '收益率 %', axisLabel: { formatter: '{value}%' } },
      series: [{
        type: 'bar',
        data: values.map((v: string) => ({
          value: parseFloat(v),
          itemStyle: { color: parseFloat(v) >= 0 ? '#52c41a' : '#ff4d4f' },
        })),
        label: { show: true, position: 'top', formatter: '{c}%' },
      }],
    }
  }

  // Walk-Forward 各折收益
  const getFoldChartOption = () => {
    const folds = result?.fold_details || result?.metrics?.fold_returns
    if (!folds?.length) return {}

    if (Array.isArray(folds) && typeof folds[0] === 'number') {
      // fold_returns array
      return {
        tooltip: { trigger: 'axis' },
        grid: { left: 50, right: 20, top: 20, bottom: 30 },
        xAxis: { type: 'category', data: folds.map((_: any, i: number) => `Fold ${i + 1}`) },
        yAxis: { type: 'value', name: '收益率 %', axisLabel: { formatter: '{value}%' } },
        series: [{
          type: 'bar',
          data: folds.map((v: number) => ({
            value: parseFloat((v * 100).toFixed(1)),
            itemStyle: { color: v >= 0 ? '#52c41a' : '#ff4d4f' },
          })),
        }],
      }
    }

    // fold_details array
    const details = folds as any[]
    return {
      tooltip: { trigger: 'axis' },
      grid: { left: 50, right: 20, top: 20, bottom: 30 },
      xAxis: { type: 'category', data: details.map(f => `Fold ${f.fold_id + 1}`) },
      yAxis: { type: 'value', name: '收益率 %', axisLabel: { formatter: '{value}%' } },
      series: [{
        type: 'bar',
        data: details.map(f => ({
          value: parseFloat((f.total_return * 100).toFixed(1)),
          itemStyle: { color: f.total_return >= 0 ? '#52c41a' : '#ff4d4f' },
        })),
      }],
    }
  }

  const m = result?.metrics

  return (
    <div style={{ padding: 16 }}>
      <h2 style={{ marginBottom: 16 }}>
        <ExperimentOutlined /> 量化策略回测
        <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>
          融合全球顶级量化机构策略
        </span>
      </h2>

      {/* 配置区 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col span={4}>
            <div style={{ marginBottom: 4, fontSize: 12, color: '#999' }}>策略</div>
            <Select value={selectedStrategy} onChange={setSelectedStrategy} style={{ width: '100%' }}>
              {strategies.map(s => (
                <Option key={s.name} value={s.name}>
                  <Tooltip title={`${s.inspiration} — ${s.description}`}>
                    {s.display_name}
                  </Tooltip>
                </Option>
              ))}
              <Option value="ensemble">
                <Tooltip title="Citadel/Millennium风格：风险平价分配多个策略">
                  多策略集成
                </Tooltip>
              </Option>
            </Select>
          </Col>
          <Col span={3}>
            <div style={{ marginBottom: 4, fontSize: 12, color: '#999' }}>开始日期</div>
            <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
              style={{ width: '100%', padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 4 }} />
          </Col>
          <Col span={3}>
            <div style={{ marginBottom: 4, fontSize: 12, color: '#999' }}>结束日期</div>
            <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
              style={{ width: '100%', padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 4 }} />
          </Col>
          <Col span={3}>
            <div style={{ marginBottom: 4, fontSize: 12, color: '#999' }}>初始资金</div>
            <InputNumber value={initialCapital} onChange={v => setInitialCapital(v || 1000000)}
              formatter={v => `¥ ${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
              parser={v => Number((v || '').replace(/¥\s?|(,*)/g, '')) as any}
              style={{ width: '100%' }} />
          </Col>
          <Col span={2}>
            <div style={{ marginBottom: 4, fontSize: 12, color: '#999' }}>选股数</div>
            <InputNumber value={topN} onChange={v => setTopN(v || 20)} min={5} max={50} style={{ width: '100%' }} />
          </Col>
          <Col span={3}>
            <div style={{ marginBottom: 4, fontSize: 12, color: '#999' }}>再平衡</div>
            <Select value={rebalanceFreq} onChange={setRebalanceFreq} style={{ width: '100%' }}>
              <Option value="weekly">周度</Option>
              <Option value="monthly">月度</Option>
              <Option value="quarterly">季度</Option>
            </Select>
          </Col>
          <Col span={3}>
            <div style={{ marginBottom: 4, fontSize: 12, color: '#999' }}>Walk-Forward</div>
            <Switch checked={walkForward} onChange={setWalkForward}
              checkedChildren="开" unCheckedChildren="关" />
          </Col>
          <Col span={3}>
            <Button type="primary" icon={<PlayCircleOutlined />} onClick={runBacktest}
              loading={loading} block size="large">
              运行回测
            </Button>
          </Col>
        </Row>
      </Card>

      {/* 策略说明 */}
      {strategies.find(s => s.name === selectedStrategy) && (
        <Card size="small" style={{ marginBottom: 16, background: '#f6ffed', border: '1px solid #b7eb8f' }}>
          <Space>
            <ThunderboltOutlined style={{ color: '#52c41a' }} />
            <span style={{ fontWeight: 600 }}>
              {strategies.find(s => s.name === selectedStrategy)?.display_name}
            </span>
            <span style={{ color: '#666' }}>
              — {strategies.find(s => s.name === selectedStrategy)?.description}
            </span>
            <Tag color="blue">
              {strategies.find(s => s.name === selectedStrategy)?.inspiration}
            </Tag>
          </Space>
        </Card>
      )}

      {loading && <Spin size="large" style={{ display: 'block', margin: '40px auto' }} />}

      {/* 结果 */}
      {result && m && (
        <Tabs defaultActiveKey="overview">
          <TabPane tab="概览" key="overview">
            {/* 核心指标 */}
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={4}>
                <Card size="small">
                  <Statistic title="年化收益" value={m.annual_return ? m.annual_return * 100 : 0}
                    precision={1} suffix="%" valueStyle={{ color: (m.annual_return || 0) >= 0 ? '#3f8600' : '#cf1322' }} />
                </Card>
              </Col>
              <Col span={4}>
                <Card size="small">
                  <Statistic title="总收益" value={m.total_return ? m.total_return * 100 : 0}
                    precision={1} suffix="%" valueStyle={{ color: (m.total_return || 0) >= 0 ? '#3f8600' : '#cf1322' }} />
                </Card>
              </Col>
              <Col span={4}>
                <Card size="small">
                  <Statistic title="Sharpe比率" value={m.sharpe_ratio || 0} precision={2}
                    valueStyle={{ color: (m.sharpe_ratio || 0) >= 1 ? '#3f8600' : '#faad14' }} />
                </Card>
              </Col>
              <Col span={4}>
                <Card size="small">
                  <Statistic title="最大回撤" value={m.max_drawdown ? m.max_drawdown * 100 : 0}
                    precision={1} suffix="%" valueStyle={{ color: '#cf1322' }} />
                </Card>
              </Col>
              <Col span={4}>
                <Card size="small">
                  <Statistic title="Sortino比率" value={m.sortino_ratio || 0} precision={2} />
                </Card>
              </Col>
              <Col span={4}>
                <Card size="small">
                  <Statistic title="Calmar比率" value={m.calmar_ratio || 0} precision={2} />
                </Card>
              </Col>
            </Row>

            {/* 基准对比 */}
            {m.benchmark_total_return !== undefined && (
              <Row gutter={16} style={{ marginBottom: 16 }}>
                <Col span={6}>
                  <Card size="small">
                    <Statistic title="基准总收益" value={m.benchmark_total_return * 100} precision={1} suffix="%" />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small">
                    <Statistic title="超额收益(年)" value={(m.excess_return || 0) * 100} precision={1} suffix="%"
                      valueStyle={{ color: (m.excess_return || 0) >= 0 ? '#3f8600' : '#cf1322' }} />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small">
                    <Statistic title="Alpha" value={m.alpha || 0} precision={3} />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small">
                    <Statistic title="Beta" value={m.beta || 1} precision={2} />
                  </Card>
                </Col>
              </Row>
            )}

            {/* Walk-Forward 指标 */}
            {walkForward && m.n_folds && (
              <Card size="small" style={{ marginBottom: 16, background: '#fff7e6', border: '1px solid #ffd591' }}>
                <Space>
                  <InfoCircleOutlined style={{ color: '#fa8c16' }} />
                  <span>Walk-Forward验证: {m.n_folds}折</span>
                  {m.param_stability && Object.keys(m.param_stability).length > 0 && (
                    <span>
                      参数稳定性: {Object.values(m.param_stability).filter(v => v > 0.5).length > 0
                        ? <Tag color="red">{Object.values(m.param_stability).filter(v => v > 0.5).length}个不稳定</Tag>
                        : <Tag color="green">全部稳定</Tag>
                      }
                    </span>
                  )}
                </Space>
              </Card>
            )}

            {/* 净值曲线 */}
            <Card title="净值曲线" size="small" style={{ marginBottom: 16 }}>
              <ReactECharts option={getEquityChartOption()} style={{ height: 300 }} />
            </Card>
          </TabPane>

          <TabPane tab="回撤分析" key="drawdown">
            <Card title="回撤曲线" size="small" style={{ marginBottom: 16 }}>
              <ReactECharts option={getDrawdownChartOption()} style={{ height: 300 }} />
            </Card>
            <Row gutter={16}>
              <Col span={8}>
                <Card size="small">
                  <Statistic title="最大回撤" value={m.max_drawdown ? m.max_drawdown * 100 : 0} precision={1} suffix="%" />
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small">
                  <Statistic title="月度胜率" value={m.monthly_win_rate ? m.monthly_win_rate * 100 : 0} precision={1} suffix="%" />
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small">
                  <Statistic title="盈亏比" value={m.profit_loss_ratio || 0} precision={2} />
                </Card>
              </Col>
            </Row>
          </TabPane>

          <TabPane tab="分年度" key="yearly">
            <Card title="分年度收益率" size="small">
              <ReactECharts option={getYearlyChartOption()} style={{ height: 300 }} />
            </Card>
          </TabPane>

          {walkForward && (
            <TabPane tab="Walk-Forward" key="wf">
              <Card title="各折样本外收益" size="small" style={{ marginBottom: 16 }}>
                <ReactECharts option={getFoldChartOption()} style={{ height: 250 }} />
              </Card>
              {result.walk_forward_report && (
                <Card title="验证报告" size="small">
                  <pre style={{ fontSize: 12, lineHeight: 1.6, maxHeight: 400, overflow: 'auto' }}>
                    {result.walk_forward_report}
                  </pre>
                </Card>
              )}
              {result.fold_details && (
                <Card title="各折详情" size="small" style={{ marginTop: 16 }}>
                  <Table
                    size="small"
                    dataSource={result.fold_details}
                    rowKey="fold_id"
                    pagination={false}
                    columns={[
                      { title: 'Fold', dataIndex: 'fold_id', key: 'fold_id' },
                      { title: '测试开始', dataIndex: 'test_start', key: 'test_start' },
                      { title: '测试结束', dataIndex: 'test_end', key: 'test_end' },
                      { title: '收益率', dataIndex: 'total_return', key: 'total_return',
                        render: (v: number) => <span style={{ color: v >= 0 ? '#3f8600' : '#cf1322' }}>{(v * 100).toFixed(1)}%</span> },
                      { title: 'Sharpe', dataIndex: 'sharpe_ratio', key: 'sharpe', render: (v: number) => v?.toFixed(2) },
                      { title: '最大回撤', dataIndex: 'max_drawdown', key: 'dd', render: (v: number) => `${(v * 100).toFixed(1)}%` },
                      { title: '交易次数', dataIndex: 'trade_count', key: 'trades' },
                    ]}
                  />
                </Card>
              )}
            </TabPane>
          )}

          {result.strategy === 'ensemble' && result.strategy_contributions && (
            <TabPane tab="策略贡献" key="contributions">
              <Card title="各策略贡献" size="small" style={{ marginBottom: 16 }}>
                <Table
                  size="small"
                  dataSource={Object.entries(result.strategy_contributions).map(([name, info]: any) => ({
                    name, ...info
                  }))}
                  rowKey="name"
                  pagination={false}
                  columns={[
                    { title: '策略', dataIndex: 'name', key: 'name' },
                    { title: '权重', dataIndex: 'weight', key: 'weight', render: (v: number) => `${(v * 100).toFixed(1)}%` },
                    { title: '年化收益', dataIndex: 'annual_return', key: 'ar',
                      render: (v: number) => <span style={{ color: v >= 0 ? '#3f8600' : '#cf1322' }}>{(v * 100).toFixed(1)}%</span> },
                    { title: 'Sharpe', dataIndex: 'sharpe_ratio', key: 'sr', render: (v: number) => v?.toFixed(2) },
                    { title: '最大回撤', dataIndex: 'max_drawdown', key: 'dd', render: (v: number) => `${(v * 100).toFixed(1)}%` },
                  ]}
                />
              </Card>
              {result.high_correlation_warning && (
                <Card size="small" style={{ background: '#fff2e8', border: '1px solid #ffbb96' }}>
                  <Space>
                    <WarningOutlined style={{ color: '#fa541c' }} />
                    <span>警告：策略间相关性较高（{'>'}0.7），集成效果可能受限</span>
                  </Space>
                </Card>
              )}
            </TabPane>
          )}
        </Tabs>
      )}
    </div>
  )
}
