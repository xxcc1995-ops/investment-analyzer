import { useState, useEffect, useCallback } from 'react'
import { dailyInfoApi } from '../services/api'
import { PageSection, LoadingSpinner, EmptyState } from '../components/ui'

// ==================== 类型定义 ====================

interface SourceStatus {
  name: string
  name_cn: string
  tier: number
  count: number
}

interface OverseasNewsItem {
  title: string
  summary: string
  link: string
  published: string
  source: string
  category: string
  impact: 'high' | 'medium' | 'low'
  key_points: string[]
}

interface OverseasCategoryData {
  items: OverseasNewsItem[]
  sources_ok: SourceStatus[]
  sources_failed: string[]
  count?: number
  high_impact_count?: number
  medium_impact_count?: number
  update_time?: string
}

interface OverseasNewsData {
  us_stock: OverseasCategoryData
  crypto: OverseasCategoryData
  update_time: string
}

// ==================== 信息源配置 ====================

const SOURCE_INFO = {
  us_stock: {
    label: '美股市场',
    icon: '🇺🇸',
    sources: [
      { name: 'Reuters', tier: 1, desc: '路透社 — 全球最大通讯社，一手财经信息源', url: 'https://www.reuters.com' },
      { name: 'MarketWatch', tier: 1, desc: '道琼斯旗下，美股市场深度报道', url: 'https://www.marketwatch.com' },
      { name: 'Yahoo Finance', tier: 1, desc: '综合财经门户，覆盖面广', url: 'https://finance.yahoo.com' },
      { name: 'Seeking Alpha', tier: 2, desc: '深度分析社区，机构级研报', url: 'https://seekingalpha.com' },
    ]
  },
  crypto: {
    label: '加密市场',
    icon: '₿',
    sources: [
      { name: 'CoinDesk', tier: 1, desc: '领先加密媒体，行业标准信息源', url: 'https://www.coindesk.com' },
      { name: 'The Block', tier: 1, desc: '研究导向，机构级加密分析', url: 'https://www.theblock.co' },
      { name: 'CoinTelegraph', tier: 2, desc: '综合加密新闻，覆盖面广', url: 'https://cointelegraph.com' },
      { name: 'Decrypt', tier: 2, desc: 'Web3/DeFi 聚焦，深度报道', url: 'https://decrypt.co' },
    ]
  }
}

// ==================== 主组件 ====================

export default function DailyInfo() {
  const [overseasNews, setOverseasNews] = useState<OverseasNewsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showSources, setShowSources] = useState(false)

  const fetchNews = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await dailyInfoApi.getOverseasNews()
      setOverseasNews(res.data as unknown as OverseasNewsData)
    } catch (err: any) {
      setError(err.message || '获取海外资讯失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchNews()
  }, [fetchNews])

  // ==================== 渲染辅助 ====================

  const getImpactBadge = (impact: string) => {
    switch (impact) {
      case 'high':
        return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-red-100 text-red-700 border border-red-200">🔴 重要</span>
      case 'medium':
        return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">🟡 关注</span>
      default:
        return null
    }
  }

  const getSourceBadge = (source: string, sourcesOk?: SourceStatus[]) => {
    const status = sourcesOk?.find(s => s.name === source)
    const isTier1 = status?.tier === 1
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
        isTier1
          ? 'bg-slate-100 text-slate-700 border border-slate-200'
          : 'bg-gray-50 text-gray-500 border border-gray-200'
      }`}>
        {status?.name_cn || source}
        {isTier1 && <span className="ml-1 text-blue-500">★</span>}
      </span>
    )
  }

  // ==================== 新闻分类渲染 ====================

  const renderNewsCategory = (title: string, icon: string, data: OverseasCategoryData) => {
    const highItems = data.items.filter(i => i.impact === 'high')
    const mediumItems = data.items.filter(i => i.impact === 'medium')
    const lowItems = data.items.filter(i => i.impact === 'low')

    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        {/* 分类头部 */}
        <div className="px-6 py-4 bg-gradient-to-r from-gray-50 to-white border-b border-gray-100">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <span className="text-2xl">{icon}</span>
              <div>
                <h3 className="text-lg font-bold text-gray-900">{title}</h3>
                <p className="text-xs text-gray-500 mt-0.5">
                  {data.count || 0} 条资讯 · {data.sources_ok?.length || 0} 个信源
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              {highItems.length > 0 && (
                <span className="px-2.5 py-1 bg-red-50 text-red-700 rounded-lg text-xs font-bold border border-red-100">
                  {highItems.length} 条重要
                </span>
              )}
              {mediumItems.length > 0 && (
                <span className="px-2.5 py-1 bg-amber-50 text-amber-700 rounded-lg text-xs font-semibold border border-amber-100">
                  {mediumItems.length} 条关注
                </span>
              )}
            </div>
          </div>
        </div>

        {/* 新闻列表 */}
        <div className="divide-y divide-gray-50">
          {data.items.length === 0 ? (
            <div className="px-6 py-12 text-center">
              <div className="text-gray-300 text-4xl mb-3">📭</div>
              <div className="text-gray-400 text-sm">暂无数据，信源可能暂时不可用</div>
              {data.sources_failed.length > 0 && (
                <div className="text-xs text-gray-300 mt-2">
                  失败源: {data.sources_failed.join(', ')}
                </div>
              )}
            </div>
          ) : (
            <>
              {/* 重要新闻 */}
              {highItems.length > 0 && (
                <div className="px-6 py-3 bg-red-50/50">
                  <div className="text-xs font-bold text-red-600 uppercase tracking-wider mb-3">⚡ Market Moving</div>
                  <div className="space-y-3">
                    {highItems.map((item, i) => (
                      <div key={`high-${i}`} className="bg-white rounded-lg border border-red-100 hover:border-red-300 hover:shadow-sm transition-all overflow-hidden">
                        <div className="p-4">
                          <div className="flex items-start space-x-3">
                            <div className="flex-shrink-0 mt-0.5">{getImpactBadge(item.impact)}</div>
                            <div className="flex-1 min-w-0">
                              <a href={item.link} target="_blank" rel="noopener noreferrer"
                                className="font-semibold text-gray-900 hover:text-red-700 line-clamp-2 text-sm leading-relaxed">
                                {item.title}
                              </a>
                              <div className="flex items-center space-x-3 mt-1.5">
                                {getSourceBadge(item.source, data.sources_ok)}
                                {item.published && <span className="text-xs text-gray-400">{item.published}</span>}
                              </div>
                            </div>
                          </div>
                          {(item.key_points?.length > 0 || item.summary) && (
                            <div className="mt-3 ml-8 space-y-1.5">
                              {item.key_points?.length > 0 ? (
                                item.key_points.slice(0, 3).map((point, j) => (
                                  <div key={j} className="flex items-start space-x-2">
                                    <span className="text-red-400 text-xs mt-0.5 flex-shrink-0">▸</span>
                                    <span className="text-sm text-gray-700 leading-relaxed">{point}</span>
                                  </div>
                                ))
                              ) : item.summary ? (
                                <div className="flex items-start space-x-2">
                                  <span className="text-red-400 text-xs mt-0.5 flex-shrink-0">▸</span>
                                  <span className="text-sm text-gray-600 leading-relaxed">{item.summary}</span>
                                </div>
                              ) : null}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 关注新闻 */}
              {mediumItems.length > 0 && (
                <div className="px-6 py-3">
                  <div className="text-xs font-bold text-amber-600 uppercase tracking-wider mb-3">📌 值得关注</div>
                  <div className="space-y-1.5">
                    {mediumItems.map((item, i) => (
                      <div key={`med-${i}`} className="p-2.5 rounded-lg hover:bg-gray-50 transition-colors">
                        <a href={item.link} target="_blank" rel="noopener noreferrer"
                          className="flex items-start space-x-3 group">
                          <div className="flex-shrink-0 mt-0.5">{getImpactBadge(item.impact)}</div>
                          <div className="flex-1 min-w-0">
                            <div className="font-medium text-gray-800 group-hover:text-blue-700 line-clamp-2 text-sm">{item.title}</div>
                            <div className="flex items-center space-x-3 mt-1">
                              {getSourceBadge(item.source, data.sources_ok)}
                              {item.published && <span className="text-xs text-gray-400">{item.published}</span>}
                            </div>
                          </div>
                        </a>
                        {item.summary && (
                          <div className="ml-8 mt-1.5">
                            <p className="text-xs text-gray-500 line-clamp-2 leading-relaxed">{item.summary}</p>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 一般新闻（折叠） */}
              {lowItems.length > 0 && (
                <details className="group">
                  <summary className="px-6 py-3 cursor-pointer hover:bg-gray-50 transition-colors flex items-center justify-between">
                    <span className="text-xs font-medium text-gray-500">📰 更多资讯 ({lowItems.length})</span>
                    <svg className="w-4 h-4 text-gray-400 group-open:rotate-180 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </summary>
                  <div className="px-6 pb-3 space-y-1">
                    {lowItems.map((item, i) => (
                      <a key={`low-${i}`} href={item.link} target="_blank" rel="noopener noreferrer"
                        className="flex items-start space-x-3 p-2 rounded hover:bg-gray-50 transition-colors group">
                        <div className="flex-1 min-w-0">
                          <span className="text-sm text-gray-700 group-hover:text-blue-600 line-clamp-1">{item.title}</span>
                        </div>
                        <div className="flex items-center space-x-2 flex-shrink-0">
                          <span className="text-xs text-gray-400">{item.source}</span>
                          {item.published && <span className="text-xs text-gray-300">{item.published}</span>}
                        </div>
                      </a>
                    ))}
                  </div>
                </details>
              )}
            </>
          )}
        </div>

        {/* 信源状态栏 */}
        <div className="px-6 py-2.5 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            {data.sources_ok?.map((src, i) => (
              <span key={i} className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-green-50 text-green-600 border border-green-100">
                {src.name_cn}
                {src.tier === 1 && <span className="ml-0.5 text-blue-400">★</span>}
                <span className="ml-1 text-green-400">✓</span>
              </span>
            ))}
            {data.sources_failed.map((name, i) => (
              <span key={i} className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-gray-100 text-gray-400 line-through">{name}</span>
            ))}
          </div>
          <span className="text-xs text-gray-400">
            {data.update_time ? new Date(data.update_time).toLocaleTimeString('zh-CN') : ''}
          </span>
        </div>
      </div>
    )
  }

  // ==================== 信息源说明面板 ====================

  const renderSourcesPanel = () => (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className="px-6 py-4 bg-gradient-to-r from-blue-50 to-white border-b border-gray-100">
        <h3 className="text-lg font-bold text-gray-900">📡 信息源说明</h3>
        <p className="text-xs text-gray-500 mt-1">所有资讯均来自海外专业财经媒体，通过 RSS + HTML 解析获取</p>
      </div>
      <div className="p-6 space-y-6">
        {Object.entries(SOURCE_INFO).map(([key, category]) => (
          <div key={key}>
            <div className="flex items-center space-x-2 mb-3">
              <span className="text-xl">{category.icon}</span>
              <h4 className="font-bold text-gray-800">{category.label}</h4>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {category.sources.map((src, i) => (
                <div key={i} className="flex items-start space-x-3 p-3 rounded-lg bg-gray-50 border border-gray-100">
                  <div className="flex-shrink-0">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold ${
                      src.tier === 1 ? 'bg-blue-100 text-blue-700' : 'bg-gray-200 text-gray-600'
                    }`}>
                      T{src.tier}
                      {src.tier === 1 && ' ★'}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <a href={src.url} target="_blank" rel="noopener noreferrer"
                      className="font-semibold text-sm text-gray-900 hover:text-blue-600">
                      {src.name}
                    </a>
                    <p className="text-xs text-gray-500 mt-0.5">{src.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}

        {/* 数据获取说明 */}
        <div className="mt-4 p-4 bg-amber-50 rounded-lg border border-amber-100">
          <h4 className="font-bold text-amber-800 text-sm mb-2">📋 数据获取说明</h4>
          <ul className="text-xs text-amber-700 space-y-1">
            <li>• <strong>获取方式：</strong>RSS Feed 优先，HTML 爬取作为 Fallback</li>
            <li>• <strong>更新频率：</strong>每 30 分钟自动刷新</li>
            <li>• <strong>影响力评估：</strong>基于关键词自动标注（美联储/CPI/ETF/暴跌等 → 重要）</li>
            <li>• <strong>广告过滤：</strong>自动识别并过滤赞助内容和推广信息</li>
            <li>• <strong>代理支持：</strong>通过 POLYMARKET_PROXY 环境变量配置代理</li>
            <li>• <strong>代码位置：</strong><code className="bg-amber-100 px-1 rounded">backend/app/services/overseas_news_service.py</code></li>
          </ul>
        </div>
      </div>
    </div>
  )

  // ==================== 主渲染 ====================

  if (loading) {
    return (
      <PageSection title="🌍 海外资讯">
        <LoadingSpinner />
      </PageSection>
    )
  }

  if (error) {
    return (
      <PageSection title="🌍 海外资讯">
        <EmptyState
          icon="⚠️"
          title="获取海外资讯失败"
          description={error}
          action={<button onClick={fetchNews} className="mt-3 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">重试</button>}
        />
      </PageSection>
    )
  }

  const totalItems = (overseasNews?.us_stock.count || 0) + (overseasNews?.crypto.count || 0)
  const totalHigh = (overseasNews?.us_stock.high_impact_count || 0) + (overseasNews?.crypto.high_impact_count || 0)
  const totalSources = (overseasNews?.us_stock.sources_ok?.length || 0) + (overseasNews?.crypto.sources_ok?.length || 0)

  return (
    <PageSection title="🌍 海外资讯">
      <div className="mb-4 text-sm text-gray-500">
        美股 + 加密市场实时新闻，来源：Reuters / MarketWatch / Yahoo Finance / Seeking Alpha / CoinDesk / The Block / CoinTelegraph / Decrypt
      </div>
      <div className="space-y-6">
        {/* 顶部统计栏 */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="bg-white rounded-lg border border-gray-200 px-4 py-3">
            <div className="text-2xl font-bold text-gray-900">{totalItems}</div>
            <div className="text-xs text-gray-500 mt-0.5">资讯总量</div>
          </div>
          <div className="bg-white rounded-lg border border-red-100 px-4 py-3">
            <div className="text-2xl font-bold text-red-600">{totalHigh}</div>
            <div className="text-xs text-red-400 mt-0.5">重要资讯</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 px-4 py-3">
            <div className="text-2xl font-bold text-gray-900">{totalSources}</div>
            <div className="text-xs text-gray-500 mt-0.5">活跃信源</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 px-4 py-3">
            <div className="text-sm font-medium text-gray-600">
              {overseasNews?.update_time ? new Date(overseasNews.update_time).toLocaleTimeString('zh-CN') : '--'}
            </div>
            <div className="text-xs text-gray-500 mt-0.5">最后更新</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 px-4 py-3 flex items-center justify-center">
            <button
              onClick={() => setShowSources(!showSources)}
              className="text-sm text-blue-600 hover:text-blue-800 font-medium"
            >
              {showSources ? '隐藏信息源' : '📡 查看信息源'}
            </button>
          </div>
        </div>

        {/* 信息源说明（可折叠） */}
        {showSources && renderSourcesPanel()}

        {/* 美股市场 */}
        {overseasNews?.us_stock && renderNewsCategory('美股市场', '🇺🇸', overseasNews.us_stock)}

        {/* 加密市场 */}
        {overseasNews?.crypto && renderNewsCategory('加密市场', '₿', overseasNews.crypto)}

        {/* 刷新按钮 */}
        <div className="text-center">
          <button
            onClick={fetchNews}
            className="px-6 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm hover:bg-gray-200 transition-colors"
          >
            🔄 刷新资讯
          </button>
        </div>
      </div>
    </PageSection>
  )
}
