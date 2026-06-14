/**
 * QuantDinger AI分析面板
 * 展示AI驱动的技术分析、趋势展望、交易计划等
 */

import { useState, useEffect, useCallback } from 'react'
import { quantdingerApi } from '../services/api'
import type { AIAnalysisResult, AnalysisHistory, PerformanceStats } from '../services/api'
import { LoadingSpinner, EmptyState } from './ui'

interface AIAnalysisPanelProps {
  code: string
  stockName?: string
}

// 决策颜色映射
const decisionColors: Record<string, string> = {
  BUY: '#16a34a',
  SELL: '#dc2626',
  HOLD: '#ca8a04',
}

// 决策中文映射
const decisionLabels: Record<string, string> = {
  BUY: '买入',
  SELL: '卖出',
  HOLD: '持有',
}

// 强度中文映射
const strengthLabels: Record<string, string> = {
  strong: '强烈',
  moderate: '中等',
  mild: '温和',
  weak: '微弱',
}

export function AIAnalysisPanel({ code, stockName }: AIAnalysisPanelProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<AIAnalysisResult | null>(null)
  const [history, setHistory] = useState<AnalysisHistory[]>([])
  const [performance, setPerformance] = useState<PerformanceStats | null>(null)
  const [serviceAvailable, setServiceAvailable] = useState<boolean | null>(null)
  const [activeTab, setActiveTab] = useState<'analysis' | 'history' | 'performance'>('analysis')
  const [timeframe, setTimeframe] = useState<'1H' | '4H' | '1D' | '1W'>('1D')

  // 检查服务是否可用
  useEffect(() => {
    const checkService = async () => {
      try {
        const resp = await quantdingerApi.checkHealth()
        setServiceAvailable(resp.data.available)
      } catch {
        setServiceAvailable(false)
      }
    }
    checkService()
  }, [])

  // 执行AI分析
  const handleAnalyze = useCallback(async () => {
    if (!code) return

    setLoading(true)
    setError(null)

    try {
      const resp = await quantdingerApi.analyzeStock(code, { timeframe })
      if (resp.data.code === 1) {
        setResult(resp.data.data)
      } else {
        setError(resp.data.msg || '分析失败')
      }
    } catch (err: any) {
      if (err.response?.status === 503) {
        setServiceAvailable(false)
        setError('QuantDinger服务未启动')
      } else if (err.response?.status === 402) {
        setError('QuantDinger积分不足')
      } else {
        setError(err.response?.data?.detail || '分析请求失败')
      }
    } finally {
      setLoading(false)
    }
  }, [code, timeframe])

  // 加载历史记录
  const loadHistory = useCallback(async () => {
    if (!code) return

    try {
      const resp = await quantdingerApi.getHistory(code, { days: 30, limit: 20 })
      if (resp.data.code === 1) {
        setHistory(resp.data.data)
      }
    } catch {
      // 静默失败
    }
  }, [code])

  // 加载绩效统计
  const loadPerformance = useCallback(async () => {
    try {
      const resp = await quantdingerApi.getPerformance({ code, days: 90 })
      if (resp.data.code === 1) {
        setPerformance(resp.data.data)
      }
    } catch {
      // 静默失败
    }
  }, [code])

  // 切换Tab时加载数据
  useEffect(() => {
    if (activeTab === 'history') loadHistory()
    if (activeTab === 'performance') loadPerformance()
  }, [activeTab, loadHistory, loadPerformance])

  // 服务不可用提示
  if (serviceAvailable === false) {
    return (
      <div style={{
        background: 'var(--bg-card)',
        borderRadius: 12,
        padding: 24,
        border: '1px solid var(--border)',
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          marginBottom: 16,
        }}>
          <span style={{ fontSize: 24 }}>🤖</span>
          <div>
            <div style={{ fontSize: 16, fontWeight: 600 }}>QuantDinger AI 分析</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              AI驱动的技术分析与趋势展望
            </div>
          </div>
        </div>

        <div style={{
          background: '#fef3c7',
          borderRadius: 8,
          padding: 16,
          color: '#92400e',
        }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>⚠️ 服务未连接</div>
          <div style={{ fontSize: 13 }}>
            QuantDinger服务未启动，请先启动服务：
          </div>
          <div style={{
            background: '#1f2937',
            color: '#e5e7eb',
            borderRadius: 6,
            padding: '8px 12px',
            marginTop: 8,
            fontSize: 12,
            fontFamily: 'monospace',
          }}>
            双击 start-quantdinger.bat
          </div>
          <div style={{ fontSize: 12, marginTop: 8, color: '#92400e' }}>
            默认地址: http://localhost:8888
          </div>
        </div>
      </div>
    )
  }

  // 评分环形图
  const ScoreRing = ({ score, label, size = 64 }: { score: number; label: string; size?: number }) => {
    const radius = (size - 8) / 2
    const circumference = 2 * Math.PI * radius
    const progress = (score / 100) * circumference
    const color = score >= 70 ? '#16a34a' : score >= 50 ? '#ca8a04' : '#dc2626'

    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
        <svg width={size} height={size}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="var(--border)"
            strokeWidth={4}
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={4}
            strokeDasharray={circumference}
            strokeDashoffset={circumference - progress}
            strokeLinecap="round"
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
          />
          <text
            x={size / 2}
            y={size / 2}
            textAnchor="middle"
            dominantBaseline="central"
            fontSize={size * 0.25}
            fontWeight={700}
            fill={color}
          >
            {score}
          </text>
        </svg>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{label}</span>
      </div>
    )
  }

  // 渲染分析结果
  const renderAnalysis = () => {
    if (loading) {
      return (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <LoadingSpinner text="AI正在分析中，预计需要10-30秒..." />
        </div>
      )
    }

    if (error) {
      return (
        <div style={{
          background: '#fef2f2',
          borderRadius: 8,
          padding: 16,
          color: '#991b1b',
        }}>
          <div style={{ fontWeight: 600 }}>❌ 分析失败</div>
          <div style={{ fontSize: 13, marginTop: 4 }}>{error}</div>
        </div>
      )
    }

    if (!result) {
      return (
        <div style={{ textAlign: 'center', padding: 32 }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🤖</div>
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>
            {stockName ? `分析 ${stockName}` : '开始AI分析'}
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
            AI将从技术面、基本面、市场情绪三个维度进行分析
          </div>
          <button
            onClick={handleAnalyze}
            style={{
              background: '#3b82f6',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              padding: '10px 24px',
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            开始分析
          </button>
        </div>
      )
    }

    const { decision, confidence, scores, trading_plan, reasons, risks, trend_outlook, trend_outlook_summary, market_data, detailed_analysis, consensus } = result

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* 核心决策 */}
        <div style={{
          background: `${decisionColors[decision]}10`,
          border: `1px solid ${decisionColors[decision]}30`,
          borderRadius: 10,
          padding: 16,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span style={{
                fontSize: 20,
                fontWeight: 800,
                color: decisionColors[decision],
              }}>
                {decisionLabels[decision]}
              </span>
              <span style={{ fontSize: 13, color: 'var(--text-muted)', marginLeft: 8 }}>
                置信度 {confidence}%
              </span>
            </div>
            <button
              onClick={handleAnalyze}
              style={{
                background: 'transparent',
                border: '1px solid var(--border)',
                borderRadius: 6,
                padding: '4px 12px',
                fontSize: 12,
                cursor: 'pointer',
                color: 'var(--text-muted)',
              }}
            >
              重新分析
            </button>
          </div>
          <div style={{ fontSize: 13, marginTop: 8, lineHeight: 1.6 }}>
            {result.summary}
          </div>
        </div>

        {/* 评分概览 */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-around',
          padding: '12px 0',
        }}>
          <ScoreRing score={scores.technical} label="技术面" />
          <ScoreRing score={scores.fundamental} label="基本面" />
          <ScoreRing score={scores.sentiment} label="情绪面" />
          <ScoreRing score={scores.overall} label="综合" size={72} />
        </div>

        {/* 多周期共识 */}
        {consensus && (
          <div style={{
            background: 'var(--bg-secondary)',
            borderRadius: 8,
            padding: 12,
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>📊 多周期共识</div>
            <div style={{ display: 'flex', gap: 16, fontSize: 12 }}>
              <span>共识决策:
                <strong style={{ color: decisionColors[consensus.consensus_decision], marginLeft: 4 }}>
                  {decisionLabels[consensus.consensus_decision] || consensus.consensus_decision}
                </strong>
              </span>
              <span>共识分数: <strong>{consensus.consensus_score.toFixed(1)}</strong></span>
              <span>一致性: <strong>{(consensus.agreement_ratio * 100).toFixed(0)}%</strong></span>
              <span>市场状态: <strong>{consensus.market_regime}</strong></span>
            </div>
          </div>
        )}

        {/* 趋势展望 */}
        {trend_outlook && Object.keys(trend_outlook).length > 0 && (
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>📈 趋势展望</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
              {Object.entries(trend_outlook).map(([key, value]) => (
                <div key={key} style={{
                  background: 'var(--bg-secondary)',
                  borderRadius: 8,
                  padding: '8px 12px',
                  textAlign: 'center',
                }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {key.replace('next_', '')}
                  </div>
                  <div style={{
                    fontSize: 14,
                    fontWeight: 700,
                    color: decisionColors[value.trend] || 'var(--text)',
                  }}>
                    {decisionLabels[value.trend] || value.trend}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                    {strengthLabels[value.strength] || value.strength}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 市场数据 */}
        {market_data && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 8,
          }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>当前价格</div>
              <div style={{ fontSize: 15, fontWeight: 600 }}>{market_data.current_price}</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>24h涨跌</div>
              <div style={{
                fontSize: 15,
                fontWeight: 600,
                color: market_data.change_24h >= 0 ? '#16a34a' : '#dc2626',
              }}>
                {market_data.change_24h >= 0 ? '+' : ''}{market_data.change_24h?.toFixed(2)}%
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>支撑位</div>
              <div style={{ fontSize: 15, fontWeight: 600, color: '#16a34a' }}>{market_data.support}</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>阻力位</div>
              <div style={{ fontSize: 15, fontWeight: 600, color: '#dc2626' }}>{market_data.resistance}</div>
            </div>
          </div>
        )}

        {/* 交易计划 */}
        {trading_plan && trading_plan.entry_price && (
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>🎯 交易计划</div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: 8,
            }}>
              <div style={{
                background: 'var(--bg-secondary)',
                borderRadius: 8,
                padding: '8px 12px',
                textAlign: 'center',
              }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>入场价</div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{trading_plan.entry_price}</div>
              </div>
              <div style={{
                background: '#fef2f2',
                borderRadius: 8,
                padding: '8px 12px',
                textAlign: 'center',
              }}>
                <div style={{ fontSize: 11, color: '#991b1b' }}>止损</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#dc2626' }}>{trading_plan.stop_loss}</div>
              </div>
              <div style={{
                background: '#f0fdf4',
                borderRadius: 8,
                padding: '8px 12px',
                textAlign: 'center',
              }}>
                <div style={{ fontSize: 11, color: '#166534' }}>止盈</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#16a34a' }}>{trading_plan.take_profit}</div>
              </div>
              <div style={{
                background: 'var(--bg-secondary)',
                borderRadius: 8,
                padding: '8px 12px',
                textAlign: 'center',
              }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>仓位</div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{trading_plan.position_size_pct}%</div>
              </div>
            </div>
          </div>
        )}

        {/* 买入理由与风险 */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          {reasons.length > 0 && (
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: '#16a34a' }}>
                ✅ 买入理由
              </div>
              <ul style={{ margin: 0, padding: '0 0 0 16px', fontSize: 12, lineHeight: 1.8 }}>
                {reasons.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
          )}
          {risks.length > 0 && (
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: '#dc2626' }}>
                ⚠️ 风险提示
              </div>
              <ul style={{ margin: 0, padding: '0 0 0 16px', fontSize: 12, lineHeight: 1.8 }}>
                {risks.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
          )}
        </div>

        {/* 详细分析（可折叠） */}
        {detailed_analysis && (
          <details>
            <summary style={{ fontSize: 13, fontWeight: 600, cursor: 'pointer', color: 'var(--text-muted)' }}>
              📄 查看详细分析
            </summary>
            <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 12 }}>
              {detailed_analysis.technical && (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, color: '#3b82f6' }}>技术分析</div>
                  <div style={{ fontSize: 12, lineHeight: 1.8, color: 'var(--text-muted)' }}>
                    {detailed_analysis.technical}
                  </div>
                </div>
              )}
              {detailed_analysis.fundamental && (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, color: '#8b5cf6' }}>基本面分析</div>
                  <div style={{ fontSize: 12, lineHeight: 1.8, color: 'var(--text-muted)' }}>
                    {detailed_analysis.fundamental}
                  </div>
                </div>
              )}
              {detailed_analysis.sentiment && (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, color: '#f59e0b' }}>市场情绪</div>
                  <div style={{ fontSize: 12, lineHeight: 1.8, color: 'var(--text-muted)' }}>
                    {detailed_analysis.sentiment}
                  </div>
                </div>
              )}
            </div>
          </details>
        )}

        {/* 元数据 */}
        <div style={{
          fontSize: 11,
          color: 'var(--text-muted)',
          textAlign: 'right',
          borderTop: '1px solid var(--border)',
          paddingTop: 8,
        }}>
          模型: {result.model} | 分析耗时: {(result.analysis_time_ms / 1000).toFixed(1)}s | 分析时间: {new Date(result.analyzed_at).toLocaleString('zh-CN')}
        </div>
      </div>
    )
  }

  // 渲染历史记录
  const renderHistory = () => {
    if (history.length === 0) {
      return <EmptyState icon="📊" title="暂无分析历史" />
    }

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {history.map((item) => (
          <div
            key={item.id}
            style={{
              background: 'var(--bg-secondary)',
              borderRadius: 8,
              padding: 12,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <span style={{
                fontWeight: 700,
                color: decisionColors[item.decision],
                marginRight: 8,
              }}>
                {decisionLabels[item.decision]}
              </span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                置信度 {item.confidence}%
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              {item.was_correct !== null && (
                <span style={{
                  fontSize: 11,
                  padding: '2px 8px',
                  borderRadius: 4,
                  background: item.was_correct ? '#f0fdf4' : '#fef2f2',
                  color: item.was_correct ? '#166534' : '#991b1b',
                }}>
                  {item.was_correct ? '✓ 正确' : '✗ 错误'}
                  {item.actual_return_pct !== null && ` (${item.actual_return_pct > 0 ? '+' : ''}${item.actual_return_pct.toFixed(1)}%)`}
                </span>
              )}
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                {new Date(item.created_at).toLocaleDateString('zh-CN')}
              </span>
            </div>
          </div>
        ))}
      </div>
    )
  }

  // 渲染绩效统计
  const renderPerformance = () => {
    if (!performance) {
      return <EmptyState icon="📈" title="暂无绩效数据" />
    }

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 12,
        }}>
          <div style={{
            background: 'var(--bg-secondary)',
            borderRadius: 8,
            padding: 12,
            textAlign: 'center',
          }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>总分析次数</div>
            <div style={{ fontSize: 20, fontWeight: 700 }}>{performance.total_analyses}</div>
          </div>
          <div style={{
            background: 'var(--bg-secondary)',
            borderRadius: 8,
            padding: 12,
            textAlign: 'center',
          }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>准确率</div>
            <div style={{
              fontSize: 20,
              fontWeight: 700,
              color: performance.accuracy_pct >= 60 ? '#16a34a' : performance.accuracy_pct >= 40 ? '#ca8a04' : '#dc2626',
            }}>
              {performance.accuracy_pct?.toFixed(1)}%
            </div>
          </div>
          <div style={{
            background: 'var(--bg-secondary)',
            borderRadius: 8,
            padding: 12,
            textAlign: 'center',
          }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>平均收益</div>
            <div style={{
              fontSize: 20,
              fontWeight: 700,
              color: performance.avg_return_pct >= 0 ? '#16a34a' : '#dc2626',
            }}>
              {performance.avg_return_pct > 0 ? '+' : ''}{performance.avg_return_pct?.toFixed(2)}%
            </div>
          </div>
        </div>

        {/* 分决策统计 */}
        {performance.by_decision && (
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>分决策统计</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {Object.entries(performance.by_decision).map(([key, stats]) => (
                <div
                  key={key}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    background: 'var(--bg-secondary)',
                    borderRadius: 8,
                    padding: '8px 12px',
                  }}
                >
                  <span style={{ fontWeight: 600, color: decisionColors[key] }}>
                    {decisionLabels[key]}
                  </span>
                  <div style={{ display: 'flex', gap: 16, fontSize: 12 }}>
                    <span>次数: {stats.count}</span>
                    <span>正确: {stats.correct}</span>
                    <span>
                      收益:
                      <span style={{ color: stats.avg_return >= 0 ? '#16a34a' : '#dc2626', marginLeft: 4 }}>
                        {stats.avg_return > 0 ? '+' : ''}{stats.avg_return?.toFixed(2)}%
                      </span>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div style={{
      background: 'var(--bg-card)',
      borderRadius: 12,
      padding: 20,
      border: '1px solid var(--border)',
    }}>
      {/* 标题栏 */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 16,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 22 }}>🤖</span>
          <div>
            <div style={{ fontSize: 16, fontWeight: 600 }}>QuantDinger AI 分析</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              AI驱动的技术分析 · 趋势展望 · 交易计划
            </div>
          </div>
        </div>

        {/* 时间周期选择 */}
        {activeTab === 'analysis' && (
          <div style={{ display: 'flex', gap: 4 }}>
            {(['1H', '4H', '1D', '1W'] as const).map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                style={{
                  background: timeframe === tf ? '#3b82f6' : 'transparent',
                  color: timeframe === tf ? '#fff' : 'var(--text-muted)',
                  border: '1px solid var(--border)',
                  borderRadius: 4,
                  padding: '2px 8px',
                  fontSize: 11,
                  cursor: 'pointer',
                }}
              >
                {tf}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Tab栏 */}
      <div style={{
        display: 'flex',
        gap: 0,
        marginBottom: 16,
        borderBottom: '1px solid var(--border)',
      }}>
        {[
          { key: 'analysis', label: 'AI分析' },
          { key: 'history', label: '分析历史' },
          { key: 'performance', label: '绩效统计' },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as any)}
            style={{
              background: 'transparent',
              border: 'none',
              borderBottom: activeTab === tab.key ? '2px solid #3b82f6' : '2px solid transparent',
              padding: '8px 16px',
              fontSize: 13,
              fontWeight: activeTab === tab.key ? 600 : 400,
              color: activeTab === tab.key ? '#3b82f6' : 'var(--text-muted)',
              cursor: 'pointer',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* 内容区 */}
      {activeTab === 'analysis' && renderAnalysis()}
      {activeTab === 'history' && renderHistory()}
      {activeTab === 'performance' && renderPerformance()}
    </div>
  )
}
