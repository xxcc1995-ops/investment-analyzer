/**
 * 市场总览标签页
 * 展示 A股/港股/美股指数 + 多维情绪评分 + 投资摘要
 */
import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import type { DailyBriefing, MarketIndex, SentimentV3 } from './types'
import { formatPct, formatPrice, getChangeColor, getSentimentColor, getSentimentLabel } from './utils'

interface Props {
  data: DailyBriefing | null
  loading: boolean
}

export default function MarketOverviewTab({ data, loading }: Props) {
  if (loading) return <div className="ui-loading">加载中...</div>
  if (!data) return <div className="ui-empty">暂无数据</div>

  const china = data.market_overview?.china
  const us = data.market_overview?.us
  const sentiment = data.market_sentiment
  const sentimentV3 = data.market_sentiment_v3
  const summary = data.investment_summary

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* 指数行情 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
        {china?.a_share?.map((idx, i) => <IndexCard key={`a-${i}`} index={idx} />)}
        {china?.hk?.map((idx, i) => <IndexCard key={`hk-${i}`} index={idx} />)}
        {us?.indices?.map((idx, i) => <IndexCard key={`us-${i}`} index={idx} />)}
      </div>

      {/* 情绪 + 摘要 */}
      <div style={{ display: 'grid', gridTemplateColumns: sentimentV3 ? '1fr 1fr' : '1fr', gap: 16 }}>
        {/* 情绪仪表盘 */}
        {sentimentV3 && <SentimentGauge sentiment={sentimentV3} sentimentV1={sentiment} />}
        {/* 投资摘要 */}
        {summary && <SummaryPanel summary={summary} sentiment={sentiment} />}
      </div>
    </div>
  )
}

// ==================== 子组件 ====================

function IndexCard({ index }: { index: MarketIndex }) {
  const color = getChangeColor(index.change_pct)
  return (
    <div style={{
      background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-md)', padding: '12px 16px',
    }}>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>{index.name}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)' }}>
        {formatPrice(index.close)}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color }}>{formatPct(index.change_pct)}</span>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {index.change > 0 ? '+' : ''}{index.change?.toFixed(2)}
        </span>
      </div>
    </div>
  )
}

function SentimentGauge({ sentimentV1, sentiment }: { sentiment: SentimentV3; sentimentV1: any }) {
  const score = sentiment?.composite || 50
  const gaugeOption = useMemo(() => ({
    series: [{
      type: 'gauge',
      startAngle: 200,
      endAngle: -20,
      min: 0,
      max: 100,
      splitNumber: 10,
      axisLine: {
        lineStyle: {
          width: 20,
          color: [
            [0.3, '#3fb950'],
            [0.45, '#58a6ff'],
            [0.6, '#8b949e'],
            [0.75, '#d29922'],
            [1, '#f85149'],
          ],
        },
      },
      pointer: { itemStyle: { color: 'auto' }, length: '60%', width: 4 },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      detail: {
        valueAnimation: true,
        formatter: '{value}',
        fontSize: 28,
        fontWeight: 700,
        color: getSentimentColor(score),
        offsetCenter: [0, '30%'],
      },
      title: {
        offsetCenter: [0, '60%'],
        fontSize: 14,
        color: 'var(--text-secondary)',
      },
      data: [{ value: Math.round(score), name: sentiment?.level || '中性' }],
    }],
  }), [score, sentiment?.level])

  return (
    <div style={{
      background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-md)', padding: 16,
    }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
        📊 市场情绪评分
      </div>
      <ReactECharts option={gaugeOption} style={{ height: 220 }} />
      {/* 子分数 */}
      {sentiment && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 8 }}>
          <ScoreBar label="价格动量" value={sentiment.momentum} weight="40%" />
          <ScoreBar label="市场广度" value={sentiment.breadth} weight="25%" />
          <ScoreBar label="资金动向" value={sentiment.fund_flow} weight="20%" />
          <ScoreBar label="波动率" value={sentiment.volatility} weight="15%" />
        </div>
      )}
    </div>
  )
}

function ScoreBar({ label, value, weight }: { label: string; value: number; weight: string }) {
  const color = getSentimentColor(value)
  return (
    <div style={{ fontSize: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
        <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
        <span style={{ color, fontWeight: 600 }}>{Math.round(value)}</span>
      </div>
      <div style={{ height: 4, background: 'var(--bg-tertiary)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${value}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.3s' }} />
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 1 }}>权重 {weight}</div>
    </div>
  )
}

function SummaryPanel({ summary, sentiment }: { summary: any; sentiment: any }) {
  const advices = summary?.advices || []
  const risks = summary?.risks || []

  return (
    <div style={{
      background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-md)', padding: 16,
    }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>
        📋 投资摘要
      </div>

      {/* 情绪标签 */}
      <div style={{ marginBottom: 12 }}>
        <span style={{
          display: 'inline-block', padding: '4px 12px', borderRadius: 16,
          fontSize: 13, fontWeight: 600,
          background: sentiment?.sentiment === '强势' || sentiment?.sentiment === '偏多'
            ? 'rgba(248,81,73,0.15)' : sentiment?.sentiment === '弱势' || sentiment?.sentiment === '偏空'
            ? 'rgba(63,185,80,0.15)' : 'rgba(139,148,158,0.15)',
          color: sentiment?.sentiment === '强势' || sentiment?.sentiment === '偏多'
            ? '#f85149' : sentiment?.sentiment === '弱势' || sentiment?.sentiment === '偏空'
            ? '#3fb950' : '#8b949e',
        }}>
          {getSentimentLabel(sentiment?.sentiment || '中性')}
        </span>
        <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 8 }}>
          {sentiment?.description}
        </span>
      </div>

      {/* 机会 */}
      {advices.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: '#f85149', marginBottom: 6 }}>📈 机会信号</div>
          {advices.map((a: string, i: number) => (
            <div key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', paddingLeft: 12, marginBottom: 4, borderLeft: '2px solid #f85149' }}>
              {a}
            </div>
          ))}
        </div>
      )}

      {/* 风险 */}
      {risks.length > 0 && (
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: '#3fb950', marginBottom: 6 }}>⚠️ 风险提示</div>
          {risks.map((r: string, i: number) => (
            <div key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', paddingLeft: 12, marginBottom: 4, borderLeft: '2px solid #3fb950' }}>
              {r}
            </div>
          ))}
        </div>
      )}

      {advices.length === 0 && risks.length === 0 && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>暂无特殊信号，市场平稳运行</div>
      )}
    </div>
  )
}
